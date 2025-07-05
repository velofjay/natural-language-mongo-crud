import os
import json
import ollama
import streamlit as st
import requests
import pandas as pd
import urllib.parse
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
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)
    db = client.imdb
    movies_collection = db.movies
    client.admin.command('ping')
except Exception as e:
    st.error(f"Failed to connect to MongoDB: {e}")
    st.stop()

# --- LLM Configuration ---
OLLAMA_HOST = os.getenv("OLLAMA_HOST_DOCKER", "http://localhost:11434")
try:
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
# **THE ULTIMATE PROMPT, SIMPLIFIED**: This version is extremely direct and removes all optional keys from the main structure to prevent confusion.
PROMPT_TEMPLATE = """
You are an expert at converting natural language into a MongoDB query JSON object. You must follow all rules exactly.

**JSON OUTPUT RULES:**
1.  Your entire response MUST be ONLY the JSON object. Do not add any text before or after it.
2.  The JSON object can ONLY contain a "query" key and an optional "sort" key.
3.  For text searches (on fields like Title, Genre, Director, Actors), you MUST use a case-insensitive regex: `{{"$regex": "term", "$options": "i"}}`.
4.  For sorting requests ("newest", "highest rated"), use the "sort" key. Use `-1` for descending and `1` for ascending.

**JSON STRUCTURE:**
{{
  "query": {{ <filter_document> }},
  "sort": {{ <sort_document> }} // This key is optional
}}

**EXAMPLES:**

User request: "show me the highest rated action movies"
Your response: {{"query": {{ "Genre": {{"$regex": "Action", "$options": "i"}} }}, "sort": {{"Rating": -1}} }}

User request: "what are the new movies having rating above 7"
Your response: {{"query": {{ "Rating": {{"$gt": 7}} }}, "sort": {{"Year": -1}} }}

User request: "what are the old movies"
Your response: {{"query": {{}}, "sort": {{"Year": 1}} }}

User request: "show all records"
Your response: {{"query": {{}} }}

Now, process the following user request.

User request: "{user_request}"
Your response:
"""

def generate_mongo_query_from_text(text):
    prompt = PROMPT_TEMPLATE.format(user_request=text)
    try:
        # We are only asking the LLM for find operations now, so we simplify the logic
        response = ollama_client.chat(model='phi3:mini', messages=[{'role': 'user', 'content': prompt}], options={'temperature': 0.0})
        content = response['message']['content'].strip()
        
        if "```json" in content:
            content = content.split("```json\n")[1].split("```")[0]
        elif "{" in content:
            start_index = content.find('{')
            end_index = content.rfind('}')
            if start_index != -1 and end_index != -1 and end_index > start_index:
                content = content[start_index:end_index+1]
        
        content = content.replace("'", '"')
        return json.loads(content)
    except Exception as e:
        return {"error": f"LLM or JSON parsing failed: {e}"}

# --- GraphQL Resolvers ---
@query.field("ask")
def resolve_ask(_, info, question):
    # This resolver is now simplified to only handle 'find' operations
    llm_output = generate_mongo_query_from_text(question)

    if "error" in llm_output:
        return [{"error": f"LLM Error: {llm_output['error']}"}]
    
    try:
        query_filter = llm_output.get("query", {})
        sort_criteria = llm_output.get("sort", None)

        if not isinstance(query_filter, dict):
             return [{"error": f"LLM generated an invalid query filter. Expected a dictionary, got: {type(query_filter)}"}]
        
        projection = {
            "Title": 1, "Description": 1, "Year": 1, "Runtime": 1,
            "Rating": 1, "Votes": 1, "Revenue": 1, "Genre": 1,
            "Actors": 1, "Director": 1
        }
        
        cursor = movies_collection.find(query_filter, projection)

        if sort_criteria and isinstance(sort_criteria, dict):
            sort_list = list(sort_criteria.items())
            cursor = cursor.sort(sort_list)
        
        results_from_db = list(cursor.limit(25))
        
        if not results_from_db:
            return []
            
        formatted_results = []
        for doc in results_from_db:
            genres_str, actors_str, directors_str = doc.get("Genre", ""), doc.get("Actors", ""), doc.get("Director", "")
            # **CRITICAL TYPO FIX IS HERE**
            formatted_doc = {
                "id": str(doc["_id"]), "title": doc.get("Title"), "description": doc.get("Description"), "year": doc.get("Year"),
                "runtime": doc.get("Runtime"), "rating": doc.get("Rating"), "votes": doc.get("Votes"), "revenue": doc.get("Revenue"),
                "genres": [g.strip() for g in genres_str.split(',')] if genres_str else [],
                "actors": [a.strip() for a in actors_str.split(',')] if actors_str else [],
                "directors": [d.strip() for d in directors_str.split(',')] if directors_str else []
            }
            formatted_results.append(formatted_doc)
        
        return formatted_results
    except Exception as e:
        return [{"error": f"Database query failed: {e}"}]

@mutation.field("processCommand")
def resolve_process_command(_, info, command):
    # This mutation logic is kept separate and simple for reliability
    # A more advanced prompt would be needed for it, but we focus on 'find'
    # For now, we assume simple commands for CUD operations.
    if "add a movie" in command.lower() or "insert" in command.lower():
        operation = "insert_one"
        # This is a simplified parser, not using LLM for reliability
        try:
            doc_to_insert = {"Title": command.split("called")[1].split(",")[0].strip()}
            result = movies_collection.insert_one(doc_to_insert)
            return f"Successfully inserted 1 movie with basic info."
        except Exception:
            return "Failed to parse insert command. Please use a simple format."
    elif "update" in command.lower():
        return "Update via natural language is complex and not fully supported in this version."
    elif "delete" in command.lower():
        try:
            title_to_delete = command.split("title")[1].strip()
            result = movies_collection.delete_one({"Title": title_to_delete})
            return f"Delete command sent. Deleted {result.deleted_count} movie(s)."
        except Exception:
            return "Failed to parse delete command. Please specify '...with title <title>'."
    else:
        return "Command not recognized as a Create, Update, or Delete operation."

# --- Flask App & Streamlit UI (No changes below this line) ---
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

st.title("🎬 Natural Language MongoDB CRUD")
st.write("Use natural language to interact with your MongoDB collection (`imdb.movies`).")
graphql_endpoint = "http://localhost:5000/graphql"
with st.form("request_form"):
    request_text = st.text_area("Enter your request:", "e.g., find all titles", height=100)
    submitted = st.form_submit_button("🚀 Run")
if submitted and request_text:
    with st.spinner("Processing your request..."):
        is_query = any(word in request_text.lower() for word in ["find", "show", "list", "get", "what", "who", "retrieve"])
        if is_query:
            graphql_query = {"query": "query AskQuery($question: String!) { ask(question: $question) { title year rating genres } }", "variables": {"question": request_text}}
        else:
            graphql_query = {"query": "mutation ProcessCommand($command: String!) { processCommand(command: $command) }", "variables": {"command": request_text}}
        try:
            api_endpoint = os.getenv("FLASK_API_ENDPOINT", graphql_endpoint)
            response = requests.post(api_endpoint, json=graphql_query, timeout=120)
            response.raise_for_status()
            result_data = response.json()
            with st.expander("Show GraphQL Response"):
                st.json(result_data)
            if 'errors' in result_data:
                st.error(result_data['errors'][0]['message'])
            else:
                data = result_data['data']
                if is_query:
                    movies = data.get('ask', [])
                    if not movies:
                        st.warning("Query executed successfully, but no matching records were found.")
                    elif "error" in movies[0]:
                        st.error(f"An error occurred: {movies[0]['error']}")
                    else:
                        st.success(f"Found {len(movies)} results.")
                        st.header("Results")
                        num_columns = 5
                        cols = st.columns(num_columns)
                        for i, movie in enumerate(movies):
                            col = cols[i % num_columns]
                            with col:
                                title_safe = urllib.parse.quote(movie.get('title') or "Unknown")
                                image_url = f"https://placehold.co/200x300/222/FFF/png?text={title_safe}"
                                st.image(image_url, use_container_width=True)
                                st.markdown(f"**{movie.get('title', 'No Title')}**")
                                st.caption(f"{movie.get('year', 'N/A')} | ⭐ {movie.get('rating', 'N/A')}")
                else:
                    message = data.get('processCommand')
                    st.success(message)
        except requests.exceptions.RequestException as e:
            st.error(f"Failed to connect to the backend API: {e}.")
        except Exception as e:
            st.error(f"An unexpected error occurred: {e}")
app = flask_app