import os
import json
import ollama
import streamlit as st
import requests
import pandas as pd
from flask import Flask, jsonify, request
from ariadne import gql, QueryType, MutationType, make_executable_schema, graphql_sync
from ariadne.explorer import ExplorerGraphiQL
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv

# --- Initial Setup ---
load_dotenv()
st.set_page_config(layout="wide")

# --- Database Connection ---
MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    st.error("MONGO_URI not found in environment variables. Please create a .env file.")
    st.stop()
try:
    client = MongoClient(MONGO_URI)
    db = client.imdb
    movies_collection = db.movies
    client.admin.command('ping')
except Exception as e:
    st.error(f"Failed to connect to MongoDB: {e}")
    st.stop()

# --- LLM Configuration ---
OLLAMA_HOST = os.getenv("OLLAMA_HOST_DOCKER", "http://localhost:11434")
try:
    # **CHANGE 1: Increased timeout to 120 seconds.**
    ollama_client = ollama.Client(host=OLLAMA_HOST, timeout=120)
except Exception as e:
    st.error(f"Failed to connect to Ollama: {e}")
    st.stop()

# --- GraphQL Schema Definition ---
with open("schema.graphql") as f:
    type_defs = gql(f.read())
query = QueryType()
mutation = MutationType()

# --- LLM Prompt Engineering ---
PROMPT_TEMPLATE = """
You are an expert at converting natural language into MongoDB queries.
Your task is to take the user's request and the database schema and return a JSON object representing the necessary MongoDB operation.

DATABASE SCHEMA (Collection: "movies"):
- Ids: Integer
- Title: String
- Genre: String (comma-separated)
- Description: String
- Director: String
- Actors: String (comma-separated)
- Year: Integer
- Runtime: Integer
- Rating: Float
- Votes: Integer
- Revenue: Float

Based on the user's request, determine the CRUD operation (find, insert_one, update_one, delete_one).
For queries, use the exact field names as listed above.
Return ONLY a single JSON object with the following structure:
{{
  "operation": "<operation_name>",
  "query": {{ ... mongo query filter ... }},
  "update": {{ ... mongo update document ... }},
  "document": {{ ... mongo document to insert ... }}
}}

Examples:
User request: "Find all movies with a rating above 8.5"
Your response: {{"operation": "find", "query": {{ "Rating": {{ "$gt": 8.5 }} }}, "update": null, "document": null}}

User request: "show me all the records"
Your response: {{"operation": "find", "query": {{}}, "update": null, "document": null}}

Now, process the following user request.

User request: "{user_request}"
Your response:
"""

def generate_mongo_query_from_text(text):
    prompt = PROMPT_TEMPLATE.format(user_request=text)
    print(f"\n--- DEBUG: PROMPT SENT TO LLM ---\n{prompt}\n---------------------------------")
    try:
        response = ollama_client.chat(model='phi3:mini', messages=[{'role': 'user', 'content': prompt}], options={'temperature': 0.0})
        content = response['message']['content'].strip()
        print(f"\n--- DEBUG: RAW LLM RESPONSE ---\n{content}\n-----------------------------")
        
        if "```json" in content:
            content = content.split("```json\n")[1].split("```")[0]
        elif "{" in content:
            start_index = content.find('{')
            end_index = content.rfind('}')
            if start_index != -1 and end_index != -1 and end_index > start_index:
                content = content[start_index:end_index+1]

        print(f"\n--- DEBUG: PARSED JSON CONTENT ---\n{content}\n--------------------------------")
        return json.loads(content)
    except Exception as e:
        print(f"\n---!!! ERROR: FAILED TO PARSE JSON FROM LLM !!! ---\nError: {e}\n-------------------------------------------------")
        return {"error": f"LLM or JSON parsing failed: {e}"}

# --- GraphQL Resolvers ---
@query.field("ask")
def resolve_ask(_, info, question):
    llm_output = generate_mongo_query_from_text(question)
    print(f"\n--- DEBUG: LLM OUTPUT RECEIVED BY RESOLVER ---\n{llm_output}\n----------------------------------------------")

    if "error" in llm_output:
        return [{"error": f"LLM Error: {llm_output['error']}"}]
    
    if llm_output.get("operation") != "find":
        return [{"error": f"Could not process 'find' request. LLM returned operation: {llm_output.get('operation')}"}]
    try:
        query_filter = llm_output.get("query", {})
        if not isinstance(query_filter, dict):
             return [{"error": f"LLM generated an invalid query filter. Expected a dictionary, got: {type(query_filter)}"}]
        
        print(f"\n--- DEBUG: QUERY FILTER SENT TO MONGODB ---\n{query_filter}\n-------------------------------------------")
        projection = {
            "Title": 1, "Description": 1, "Year": 1, "Runtime": 1,
            "Rating": 1, "Votes": 1, "Revenue": 1, "Genre": 1,
            "Actors": 1, "Director": 1
        }
        results_from_db = list(movies_collection.find(query_filter, projection).limit(5))
        
        if not results_from_db:
            print("\n--- DEBUG: MONGODB FOUND 0 DOCUMENTS ---\n")
            return []
        print(f"\n--- DEBUG: RAW DOCUMENT FROM DB (FIRST ONE) ---\n{results_from_db[0]}\n---------------------------------------------")
        formatted_results = []
        for doc in results_from_db:
            genres_str, actors_str, directors_str = doc.get("Genre", ""), doc.get("Actors", ""), doc.get("Director", "")
            formatted_doc = {
                "id": str(doc["_id"]), "title": doc.get("Title"), "description": doc.get("Description"), "year": doc.get("Year"),
                "runtime": doc.get("Runtime"), "rating": doc.get("Rating"), "votes": doc.get("Votes"), "revenue": doc.get("Revenue"),
                "genres": [g.strip() for g in genres_str.split(',')] if genres_str else [],
                "actors": [a.strip() for a in actors_str.split(',')] if actors_str else [],
                "directors": [d.strip() for d in directors_str.split(',')] if directors_str else []
            }
            formatted_results.append(formatted_doc)
        
        print(f"\n--- DEBUG: FORMATTED DOCUMENT (FIRST ONE) ---\n{formatted_results[0]}\n---------------------------------------------")
        return formatted_results
    except Exception as e:
        print(f"\n---!!! ERROR: MONGODB QUERY FAILED !!! ---\nError: {e}\n---------------------------------------------")
        return [{"error": f"Database query failed: {e}"}]

@mutation.field("processCommand")
def resolve_process_command(_, info, command):
    llm_output = generate_mongo_query_from_text(command)
    if "error" in llm_output: return f"Failed to understand command. LLM Error: {llm_output['error']}"
    operation = llm_output.get("operation")
    try:
        if operation == "insert_one":
            result = movies_collection.insert_one(llm_output.get("document"))
            return f"Successfully inserted 1 movie."
        elif operation == "update_one":
            result = movies_collection.update_one(llm_output.get("query"), llm_output.get("update"))
            return f"Successfully updated {result.modified_count} movie(s)."
        elif operation == "delete_one":
            result = movies_collection.delete_one(llm_output.get("query"))
            return f"Successfully deleted {result.deleted_count} movie(s)."
        else:
            return f"Operation '{operation}' is not a valid command."
    except Exception as e:
        return f"Database command failed: {e}"

schema = make_executable_schema(type_defs, query, mutation)
flask_app = Flask(__name__)
@flask_app.route("/graphql", methods=["POST"])
def graphql_server():
    data = request.get_json()
    success, result = graphql_sync(schema, data, context_value=request, debug=flask_app.debug)
    status_code = 200 if success else 400
    return jsonify(result), status_code
explorer = ExplorerGraphiQL()
@flask_app.route("/graphql", methods=["GET"])
def graphql_playground():
    return explorer.html(None), 200
st.title("💬 Natural Language MongoDB CRUD")
st.write("Use natural language to interact with your MongoDB collection (`imdb.movies`).")
graphql_endpoint = "http://localhost:5000/graphql"
with st.form("request_form"):
    request_text = st.text_area("Enter your request:", "e.g., Find all movies with rating above 8", height=100)
    submitted = st.form_submit_button("🚀 Run")
if submitted and request_text:
    with st.spinner("Processing your request..."):
        is_query = any(word in request_text.lower() for word in ["find", "show", "list", "get", "what", "who", "retrieve"])
        if is_query: graphql_query = {"query": "query AskQuery($question: String!) { ask(question: $question) { title year rating directors actors genres } }", "variables": {"question": request_text}}
        else: graphql_query = {"query": "mutation ProcessCommand($command: String!) { processCommand(command: $command) }", "variables": {"command": request_text}}
        try:
            api_endpoint = os.getenv("FLASK_API_ENDPOINT", graphql_endpoint)
            # **CHANGE 2: Increased timeout to 120 seconds.**
            response = requests.post(api_endpoint, json=graphql_query, timeout=120); response.raise_for_status()
            result_data = response.json()
            st.subheader("GraphQL Response"); st.json(result_data)
            if 'errors' in result_data: st.error(result_data['errors'][0]['message'])
            else:
                st.success("Request successful!")
                data = result_data['data']
                if is_query:
                    movies = data.get('ask', []);
                    if movies and "error" not in movies[0]: st.dataframe(pd.DataFrame(movies))
                    else: st.warning("No results found or an error occurred.")
                else: st.info(data.get('processCommand'))
        except requests.exceptions.RequestException as e: st.error(f"Failed to connect to the backend API: {e}.")
        except Exception as e: st.error(f"An unexpected error occurred: {e}")
app = flask_app