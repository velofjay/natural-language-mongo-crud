# import os
# import json
# import ollama
# import streamlit as st
# import requests
# import pandas as pd
# from flask import Flask, jsonify, request
# from ariadne import gql, QueryType, MutationType, make_executable_schema, graphql_sync
# from ariadne.explorer import ExplorerGraphiQL
# from pymongo import MongoClient
# from bson import ObjectId
# from dotenv import load_dotenv

# # --- Initial Setup ---
# load_dotenv()
# st.set_page_config(layout="wide")

# # --- Database Connection ---
# MONGO_URI = os.getenv("MONGO_URI")
# if not MONGO_URI:
#     st.error("MONGO_URI not found in environment variables. Please create a .env file.")
#     st.stop()
# try:
#     client = MongoClient(MONGO_URI)
#     db = client.imdb
#     movies_collection = db.movies
#     client.admin.command('ping')
# except Exception as e:
#     st.error(f"Failed to connect to MongoDB: {e}")
#     st.stop()

# # --- LLM Configuration ---
# OLLAMA_HOST = os.getenv("OLLAMA_HOST_DOCKER", "http://localhost:11434")
# try:
#     # **CHANGE 1: Increased timeout to 120 seconds.**
#     ollama_client = ollama.Client(host=OLLAMA_HOST, timeout=120)
# except Exception as e:
#     st.error(f"Failed to connect to Ollama: {e}")
#     st.stop()

# # --- GraphQL Schema Definition ---
# with open("schema.graphql") as f:
#     type_defs = gql(f.read())
# query = QueryType()
# mutation = MutationType()

# # --- LLM Prompt Engineering ---
# PROMPT_TEMPLATE = """
# You are an expert at converting natural language into MongoDB queries.
# Your task is to take the user's request and the database schema and return a JSON object representing the necessary MongoDB operation.

# DATABASE SCHEMA (Collection: "movies"):
# - Ids: Integer
# - Title: String
# - Genre: String (comma-separated)
# - Description: String
# - Director: String
# - Actors: String (comma-separated)
# - Year: Integer
# - Runtime: Integer
# - Rating: Float
# - Votes: Integer
# - Revenue: Float

# Based on the user's request, determine the CRUD operation (find, insert_one, update_one, delete_one).
# For queries, use the exact field names as listed above.
# Return ONLY a single JSON object with the following structure:
# {{
#   "operation": "<operation_name>",
#   "query": {{ ... mongo query filter ... }},
#   "update": {{ ... mongo update document ... }},
#   "document": {{ ... mongo document to insert ... }}
# }}

# Examples:
# User request: "Find all movies with a rating above 8.5"
# Your response: {{"operation": "find", "query": {{ "Rating": {{ "$gt": 8.5 }} }}, "update": null, "document": null}}

# User request: "show me all the records"
# Your response: {{"operation": "find", "query": {{}}, "update": null, "document": null}}

# Now, process the following user request.

# User request: "{user_request}"
# Your response:
# """

# def generate_mongo_query_from_text(text):
#     prompt = PROMPT_TEMPLATE.format(user_request=text)
#     print(f"\n--- DEBUG: PROMPT SENT TO LLM ---\n{prompt}\n---------------------------------")
#     try:
#         response = ollama_client.chat(model='phi3:mini', messages=[{'role': 'user', 'content': prompt}], options={'temperature': 0.0})
#         content = response['message']['content'].strip()
#         print(f"\n--- DEBUG: RAW LLM RESPONSE ---\n{content}\n-----------------------------")
        
#         if "```json" in content:
#             content = content.split("```json\n")[1].split("```")[0]
#         elif "{" in content:
#             start_index = content.find('{')
#             end_index = content.rfind('}')
#             if start_index != -1 and end_index != -1 and end_index > start_index:
#                 content = content[start_index:end_index+1]

#         print(f"\n--- DEBUG: PARSED JSON CONTENT ---\n{content}\n--------------------------------")
#         return json.loads(content)
#     except Exception as e:
#         print(f"\n---!!! ERROR: FAILED TO PARSE JSON FROM LLM !!! ---\nError: {e}\n-------------------------------------------------")
#         return {"error": f"LLM or JSON parsing failed: {e}"}

# # --- GraphQL Resolvers ---
# @query.field("ask")
# def resolve_ask(_, info, question):
#     llm_output = generate_mongo_query_from_text(question)
#     print(f"\n--- DEBUG: LLM OUTPUT RECEIVED BY RESOLVER ---\n{llm_output}\n----------------------------------------------")

#     if "error" in llm_output:
#         return [{"error": f"LLM Error: {llm_output['error']}"}]
    
#     if llm_output.get("operation") != "find":
#         return [{"error": f"Could not process 'find' request. LLM returned operation: {llm_output.get('operation')}"}]
#     try:
#         query_filter = llm_output.get("query", {})
#         if not isinstance(query_filter, dict):
#              return [{"error": f"LLM generated an invalid query filter. Expected a dictionary, got: {type(query_filter)}"}]
        
#         print(f"\n--- DEBUG: QUERY FILTER SENT TO MONGODB ---\n{query_filter}\n-------------------------------------------")
#         projection = {
#             "Title": 1, "Description": 1, "Year": 1, "Runtime": 1,
#             "Rating": 1, "Votes": 1, "Revenue": 1, "Genre": 1,
#             "Actors": 1, "Director": 1
#         }
#         results_from_db = list(movies_collection.find(query_filter, projection).limit(5))
        
#         if not results_from_db:
#             print("\n--- DEBUG: MONGODB FOUND 0 DOCUMENTS ---\n")
#             return []
#         print(f"\n--- DEBUG: RAW DOCUMENT FROM DB (FIRST ONE) ---\n{results_from_db[0]}\n---------------------------------------------")
#         formatted_results = []
#         for doc in results_from_db:
#             genres_str, actors_str, directors_str = doc.get("Genre", ""), doc.get("Actors", ""), doc.get("Director", "")
#             formatted_doc = {
#                 "id": str(doc["_id"]), "title": doc.get("Title"), "description": doc.get("Description"), "year": doc.get("Year"),
#                 "runtime": doc.get("Runtime"), "rating": doc.get("Rating"), "votes": doc.get("Votes"), "revenue": doc.get("Revenue"),
#                 "genres": [g.strip() for g in genres_str.split(',')] if genres_str else [],
#                 "actors": [a.strip() for a in actors_str.split(',')] if actors_str else [],
#                 "directors": [d.strip() for d in directors_str.split(',')] if directors_str else []
#             }
#             formatted_results.append(formatted_doc)
        
#         print(f"\n--- DEBUG: FORMATTED DOCUMENT (FIRST ONE) ---\n{formatted_results[0]}\n---------------------------------------------")
#         return formatted_results
#     except Exception as e:
#         print(f"\n---!!! ERROR: MONGODB QUERY FAILED !!! ---\nError: {e}\n---------------------------------------------")
#         return [{"error": f"Database query failed: {e}"}]

# @mutation.field("processCommand")
# def resolve_process_command(_, info, command):
#     llm_output = generate_mongo_query_from_text(command)
#     if "error" in llm_output: return f"Failed to understand command. LLM Error: {llm_output['error']}"
#     operation = llm_output.get("operation")
#     try:
#         if operation == "insert_one":
#             result = movies_collection.insert_one(llm_output.get("document"))
#             return f"Successfully inserted 1 movie."
#         elif operation == "update_one":
#             result = movies_collection.update_one(llm_output.get("query"), llm_output.get("update"))
#             return f"Successfully updated {result.modified_count} movie(s)."
#         elif operation == "delete_one":
#             result = movies_collection.delete_one(llm_output.get("query"))
#             return f"Successfully deleted {result.deleted_count} movie(s)."
#         else:
#             return f"Operation '{operation}' is not a valid command."
#     except Exception as e:
#         return f"Database command failed: {e}"

# schema = make_executable_schema(type_defs, query, mutation)
# flask_app = Flask(__name__)
# @flask_app.route("/graphql", methods=["POST"])
# def graphql_server():
#     data = request.get_json()
#     success, result = graphql_sync(schema, data, context_value=request, debug=flask_app.debug)
#     status_code = 200 if success else 400
#     return jsonify(result), status_code
# explorer = ExplorerGraphiQL()
# @flask_app.route("/graphql", methods=["GET"])
# def graphql_playground():
#     return explorer.html(None), 200
# st.title("💬 Natural Language MongoDB CRUD")
# st.write("Use natural language to interact with your MongoDB collection (`imdb.movies`).")
# graphql_endpoint = "http://localhost:5000/graphql"
# with st.form("request_form"):
#     request_text = st.text_area("Enter your request:", "e.g., Find all movies with rating above 8", height=100)
#     submitted = st.form_submit_button("🚀 Run")
# if submitted and request_text:
#     with st.spinner("Processing your request..."):
#         is_query = any(word in request_text.lower() for word in ["find", "show", "list", "get", "what", "who", "retrieve"])
#         if is_query: graphql_query = {"query": "query AskQuery($question: String!) { ask(question: $question) { title year rating directors actors genres } }", "variables": {"question": request_text}}
#         else: graphql_query = {"query": "mutation ProcessCommand($command: String!) { processCommand(command: $command) }", "variables": {"command": request_text}}
#         try:
#             api_endpoint = os.getenv("FLASK_API_ENDPOINT", graphql_endpoint)
#             # **CHANGE 2: Increased timeout to 120 seconds.**
#             response = requests.post(api_endpoint, json=graphql_query, timeout=120); response.raise_for_status()
#             result_data = response.json()
#             st.subheader("GraphQL Response"); st.json(result_data)
#             if 'errors' in result_data: st.error(result_data['errors'][0]['message'])
#             else:
#                 st.success("Request successful!")
#                 data = result_data['data']
#                 if is_query:
#                     movies = data.get('ask', []);
#                     if movies and "error" not in movies[0]: st.dataframe(pd.DataFrame(movies))
#                     else: st.warning("No results found or an error occurred.")
#                 else: st.info(data.get('processCommand'))
#         except requests.exceptions.RequestException as e: st.error(f"Failed to connect to the backend API: {e}.")
#         except Exception as e: st.error(f"An unexpected error occurred: {e}")
# app = flask_app

##################################################################
# v2 #
# import os
# import json
# import ollama
# import streamlit as st
# import requests
# import pandas as pd
# from flask import Flask, jsonify, request
# from ariadne import gql, QueryType, MutationType, make_executable_schema, graphql_sync
# from ariadne.explorer import ExplorerGraphiQL
# from pymongo import MongoClient
# from bson import ObjectId
# from dotenv import load_dotenv

# # --- Initial Setup ---
# load_dotenv()
# st.set_page_config(layout="wide")

# # --- Database Connection ---
# MONGO_URI = os.getenv("MONGO_URI")
# if not MONGO_URI:
#     st.error("MONGO_URI not found in environment variables. Please create a .env file.")
#     st.stop()
# try:
#     client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)
#     db = client.imdb
#     movies_collection = db.movies
#     client.admin.command('ping')
# except Exception as e:
#     st.error(f"Failed to connect to MongoDB: {e}")
#     st.stop()

# # --- LLM Configuration ---
# OLLAMA_HOST = os.getenv("OLLAMA_HOST_DOCKER", "http://localhost:11434")
# try:
#     ollama_client = ollama.Client(host=OLLAMA_HOST, timeout=120)
# except Exception as e:
#     st.error(f"Failed to connect to Ollama: {e}")
#     st.stop()

# # --- GraphQL Schema Definition ---
# with open("schema.graphql") as f:
#     type_defs = gql(f.read())
# query = QueryType()
# mutation = MutationType()

# # --- LLM Prompt Engineering ---
# PROMPT_TEMPLATE = """
# You are an expert at converting natural language into MongoDB queries.
# Your task is to take the user's request and the database schema and return a JSON object representing the necessary MongoDB operation.

# DATABASE SCHEMA (Collection: "movies"):
# - Title: String
# - Genre: String (comma-separated, e.g., "Action,Adventure,Sci-Fi")
# - Director: String
# - Actors: String (comma-separated)
# - Year: Integer
# - Runtime: Integer
# - Rating: Float

# **CRITICAL INSTRUCTION**: For any text search on fields like `Title`, `Genre`, `Director`, or `Actors`, you MUST use a case-insensitive regular expression to find matches. The format is `{{"$regex": "search term", "$options": "i"}}`. This allows finding "action" inside "Action,Adventure" and finding "james gunn" when the database has "James Gunn".

# Return ONLY a single JSON object with the following structure:
# {{
#   "operation": "<operation_name>",
#   "query": {{ ... mongo query filter ... }},
#   "update": {{ ... mongo update document ... }},
#   "document": {{ ... mongo document to insert ... }}
# }}

# **EXAMPLES OF REGEX SEARCH:**

# User request: "list of movies which has genre Mystery"
# Your response: {{"operation": "find", "query": {{ "Genre": {{"$regex": "Mystery", "$options": "i"}} }} }}

# User request: "find movies directed by james gunn"
# Your response: {{"operation": "find", "query": {{ "Director": {{"$regex": "james gunn", "$options": "i"}} }} }}

# **OTHER EXAMPLES:**

# User request: "Find all movies with a rating above 8.5"
# Your response: {{"operation": "find", "query": {{ "Rating": {{ "$gt": 8.5 }} }} }}

# User request: "add a movie 'Super Film', rating 8, directed by 'Me', starring 'Myself'"
# Your response: {{"operation": "insert_one", "document": {{"Title": "Super Film", "Rating": 8, "Director": "Me", "Actors": "Myself"}} }}

# Now, process the following user request.

# User request: "{user_request}"
# Your response:
# """

# def generate_mongo_query_from_text(text):
#     prompt = PROMPT_TEMPLATE.format(user_request=text)
#     try:
#         response = ollama_client.chat(model='phi3:mini', messages=[{'role': 'user', 'content': prompt}], options={'temperature': 0.0})
#         content = response['message']['content'].strip()
        
#         # Robust JSON extraction and cleaning
#         if "```json" in content:
#             content = content.split("```json\n")[1].split("```")[0]
#         elif "{" in content:
#             start_index = content.find('{')
#             end_index = content.rfind('}')
#             if start_index != -1 and end_index != -1 and end_index > start_index:
#                 content = content[start_index:end_index+1]
        
#         # **THIS IS THE FIX**: Clean the JSON string before parsing.
#         # It replaces single quotes around keys/values with double quotes,
#         # which is a common error from smaller LLMs.
#         content = content.replace("'", '"')

#         return json.loads(content)
#     except Exception as e:
#         return {"error": f"LLM or JSON parsing failed: {e}"}

# # --- GraphQL Resolvers ---
# @query.field("ask")
# def resolve_ask(_, info, question):
#     llm_output = generate_mongo_query_from_text(question)

#     if "error" in llm_output:
#         return [{"error": f"LLM Error: {llm_output['error']}"}]
    
#     if llm_output.get("operation") != "find":
#         return [{"error": f"Could not process 'find' request. LLM returned operation: {llm_output.get('operation')}"}]
#     try:
#         query_filter = llm_output.get("query", {})
#         if not isinstance(query_filter, dict):
#              return [{"error": f"LLM generated an invalid query filter. Expected a dictionary, got: {type(query_filter)}"}]
        
#         projection = {
#             "Title": 1, "Description": 1, "Year": 1, "Runtime": 1,
#             "Rating": 1, "Votes": 1, "Revenue": 1, "Genre": 1,
#             "Actors": 1, "Director": 1
#         }
#         results_from_db = list(movies_collection.find(query_filter, projection).limit(25))
        
#         if not results_from_db:
#             return []
            
#         formatted_results = []
#         for doc in results_from_db:
#             genres_str, actors_str, directors_str = doc.get("Genre", ""), doc.get("Actors", ""), doc.get("Director", "")
#             formatted_doc = {
#                 "id": str(doc["_id"]), "title": doc.get("Title"), "description": doc.get("Description"), "year": doc.get("Year"),
#                 "runtime": doc.get("Runtime"), "rating": doc.get("Rating"), "votes": doc.get("Votes"), "revenue": doc.get("Revenue"),
#                 "genres": [g.strip() for g in genres_str.split(',')] if genres_str else [],
#                 "actors": [a.strip() for a in actors_str.split(',')] if actors_str else [],
#                 "directors": [d.strip() for d in directors_str.split(',')] if directors_str else []
#             }
#             formatted_results.append(formatted_doc)
        
#         return formatted_results
#     except Exception as e:
#         return [{"error": f"Database query failed: {e}"}]

# @mutation.field("processCommand")
# def resolve_process_command(_, info, command):
#     llm_output = generate_mongo_query_from_text(command)
#     if "error" in llm_output: return f"Failed to understand command. LLM Error: {llm_output['error']}"
#     operation = llm_output.get("operation")
#     try:
#         if operation == "insert_one":
#             result = movies_collection.insert_one(llm_output.get("document"))
#             return f"Successfully inserted 1 movie."
#         elif operation == "update_one":
#             result = movies_collection.update_one(llm_output.get("query"), llm_output.get("update"))
#             return f"Successfully updated {result.modified_count} movie(s)."
#         elif operation == "delete_one":
#             result = movies_collection.delete_one(llm_output.get("query"))
#             return f"Successfully deleted {result.deleted_count} movie(s)."
#         else:
#             return f"Operation '{operation}' is not a valid command."
#     except Exception as e:
#         return f"Database command failed: {e}"

# # --- Flask App & Streamlit UI (No changes below this line) ---
# schema = make_executable_schema(type_defs, query, mutation)
# flask_app = Flask(__name__)
# @flask_app.route("/graphql", methods=["POST"])
# def graphql_server():
#     data = request.get_json()
#     success, result = graphql_sync(schema, data, context_value=request, debug=flask_app.debug)
#     status_code = 200 if success else 400
#     return jsonify(result), status_code
# explorer = ExplorerGraphiQL()
# @flask_app.route("/graphql", methods=["GET"])
# def graphql_playground():
#     return explorer.html(None), 200
# st.title("💬 Natural Language MongoDB CRUD")
# st.write("Use natural language to interact with your MongoDB collection (`imdb.movies`).")
# graphql_endpoint = "http://localhost:5000/graphql"
# with st.form("request_form"):
#     request_text = st.text_area("Enter your request:", "e.g., Find all movies with rating above 8", height=100)
#     submitted = st.form_submit_button("🚀 Run")
# if submitted and request_text:
#     with st.spinner("Processing your request..."):
#         is_query = any(word in request_text.lower() for word in ["find", "show", "list", "get", "what", "who", "retrieve"])
#         if is_query: graphql_query = {"query": "query AskQuery($question: String!) { ask(question: $question) { title year rating directors actors genres } }", "variables": {"question": request_text}}
#         else: graphql_query = {"query": "mutation ProcessCommand($command: String!) { processCommand(command: $command) }", "variables": {"command": request_text}}
#         try:
#             api_endpoint = os.getenv("FLASK_API_ENDPOINT", graphql_endpoint)
#             response = requests.post(api_endpoint, json=graphql_query, timeout=120); response.raise_for_status()
#             result_data = response.json()
#             st.subheader("GraphQL Response"); st.json(result_data)
#             if 'errors' in result_data: st.error(result_data['errors'][0]['message'])
#             else:
#                 st.success("Request successful!")
#                 data = result_data['data']
#                 if is_query:
#                     movies = data.get('ask', [])
#                     if not movies:
#                         st.warning("Query executed successfully, but no matching records were found in the database.")
#                     elif "error" in movies[0]:
#                         st.error(f"An error occurred: {movies[0]['error']}")
#                     else:
#                         st.dataframe(pd.DataFrame(movies))
#                 else:
#                     st.info(data.get('processCommand'))
#         except requests.exceptions.RequestException as e: st.error(f"Failed to connect to the backend API: {e}.")
#         except Exception as e: st.error(f"An unexpected error occurred: {e}")
# app = flask_app
##########################################################################################
# ai natural resp version
# import os
# import json
# import ollama
# import streamlit as st
# import requests
# import pandas as pd
# from flask import Flask, jsonify, request
# from ariadne import gql, QueryType, MutationType, make_executable_schema, graphql_sync
# from ariadne.explorer import ExplorerGraphiQL
# from pymongo import MongoClient
# from bson import ObjectId
# from dotenv import load_dotenv

# # --- Initial Setup ---
# load_dotenv()
# st.set_page_config(layout="wide")

# # --- Database Connection ---
# MONGO_URI = os.getenv("MONGO_URI")
# if not MONGO_URI:
#     st.error("MONGO_URI not found in environment variables. Please create a .env file.")
#     st.stop()
# try:
#     client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)
#     db = client.imdb
#     movies_collection = db.movies
#     client.admin.command('ping')
# except Exception as e:
#     st.error(f"Failed to connect to MongoDB: {e}")
#     st.stop()

# # --- LLM Configuration ---
# OLLAMA_HOST = os.getenv("OLLAMA_HOST_DOCKER", "http://localhost:11434")
# try:
#     ollama_client = ollama.Client(host=OLLAMA_HOST, timeout=120)
# except Exception as e:
#     st.error(f"Failed to connect to Ollama: {e}")
#     st.stop()

# # --- GraphQL Schema Definition ---
# with open("schema.graphql") as f:
#     type_defs = gql(f.read())
# query = QueryType()
# mutation = MutationType()

# # --- LLM Prompt Engineering ---

# # PROMPT 1: The "Thinker" - Generates the MongoDB Query
# QUERY_GENERATION_PROMPT = """
# You are an expert at converting natural language into MongoDB queries.
# Your task is to take the user's request and the database schema and return a JSON object with the MongoDB query and the desired fields (projection).

# DATABASE SCHEMA (Collection: "movies"):
# - Title: String, Genre: String, Director: String, Actors: String, Year: Integer, Runtime: Integer, Rating: Float

# **CRITICAL INSTRUCTION**:
# 1. For text searches (`Title`, `Genre`, `Director`, `Actors`), you MUST use a case-insensitive regex: `{{"$regex": "search term", "$options": "i"}}`.
# 2. If the user asks for specific fields (e.g., "just the titles", "what are the genres"), create a `projection` object. For example, ` {{"Title": 1, "_id": 0}}`.
# 3. If the user asks a general question, return all relevant fields in the projection.

# Return ONLY a single JSON object with this structure:
# {{
#   "query": {{ ... mongo query filter ... }},
#   "projection": {{ ... mongo projection object ... }}
# }}

# **EXAMPLES:**
# User request: "list of movies which has genre Mystery"
# Your response: {{"query": {{ "Genre": {{"$regex": "Mystery", "$options": "i"}} }}, "projection": {{"Title": 1, "Year": 1, "Rating": 1}} }}

# User request: "what are the titles of all movies"
# Your response: {{"query": {{}}, "projection": {{"Title": 1, "_id": 0}} }}

# User request: "show me everything about the movie Inception"
# Your response: {{"query": {{ "Title": {{"$regex": "Inception", "$options": "i"}} }}, "projection": null }}

# Now, process the following user request.

# User request: "{user_request}"
# Your response:
# """

# # PROMPT 2: The "Speaker" - Synthesizes a Natural Language Response
# RESPONSE_SYNTHESIS_PROMPT = """
# You are a friendly and helpful movie database assistant.
# A user asked the following question: "{user_question}"

# The database returned the following information (in JSON format):
# {database_results}

# Your task is to answer the user's question in a natural, conversational way based *only* on the provided data.
# - If data was found, summarize it clearly. List items if necessary.
# - If the data is `[]` or `null`, it means nothing was found. Politely state that you couldn't find any matching records.
# - Do not make up information. If a field is not in the data, do not mention it.
# - Keep the response concise and friendly.
# """

# def generate_mongo_query_from_text(text):
#     prompt = QUERY_GENERATION_PROMPT.format(user_request=text)
#     try:
#         response = ollama_client.chat(model='phi3:mini', messages=[{'role': 'user', 'content': prompt}], options={'temperature': 0.0})
#         content = response['message']['content'].strip()
#         if "```json" in content:
#             content = content.split("```json\n")[1].split("```")[0]
#         elif "{" in content:
#             start_index = content.find('{'); end_index = content.rfind('}')
#             if start_index != -1 and end_index != -1: content = content[start_index:end_index+1]
#         return json.loads(content)
#     except Exception as e:
#         return {"error": f"LLM Query Generation failed: {e}"}

# def synthesize_response_from_data(question, data):
#     data_str = json.dumps(data, indent=2)
#     prompt = RESPONSE_SYNTHESIS_PROMPT.format(user_question=question, database_results=data_str)
#     try:
#         response = ollama_client.chat(model='phi3:mini', messages=[{'role': 'user', 'content': prompt}], options={'temperature': 0.7})
#         return response['message']['content'].strip()
#     except Exception as e:
#         return f"I found some data, but I had trouble summarizing it. Error: {e}"


# # --- GraphQL Resolvers ---
# @query.field("ask")
# def resolve_ask(_, info, question):
#     # STEP 1: Generate the MongoDB query
#     llm_output = generate_mongo_query_from_text(question)

#     if "error" in llm_output:
#         return f"Sorry, I had trouble understanding your request. Error: {llm_output['error']}"
    
#     try:
#         query_filter = llm_output.get("query", {})
#         projection = llm_output.get("projection")

#         # STEP 2: Execute the query against the database
#         cursor = movies_collection.find(query_filter, projection).limit(10)
#         results_from_db = list(cursor)
        
#         for doc in results_from_db:
#             if '_id' in doc:
#                 doc['_id'] = str(doc['_id'])

#         # STEP 3: Synthesize a natural language response
#         final_answer = synthesize_response_from_data(question, results_from_db)
#         return final_answer

#     except Exception as e:
#         return f"I encountered a database error while processing your request: {e}"

# @mutation.field("processCommand")
# def resolve_process_command(_, info, command):
#     # This logic has been simplified for the conversational demo.
#     # To re-enable CUD, a similar two-step process would be needed for confirmation.
#     # For now, we guide the user to use 'ask'.
#     if any(word in command.lower() for word in ["add", "insert", "create", "update", "change", "delete", "remove"]):
#          return "This conversational assistant currently specializes in finding and answering questions about movies. Create, Update, and Delete operations can be added as a future feature!"
#     else:
#         # If it's not a CUD command, process it as a query.
#         return resolve_ask(_, info, command)


# # --- Flask App & Streamlit UI (Updated for new response type) ---
# schema = make_executable_schema(type_defs, query, mutation)
# flask_app = Flask(__name__)
# @flask_app.route("/graphql", methods=["POST"])
# def graphql_server():
#     data = request.get_json()
#     success, result = graphql_sync(schema, data, context_value=request, debug=flask_app.debug)
#     status_code = 200 if success else 400
#     return jsonify(result), status_code
# explorer = ExplorerGraphiQL()
# @flask_app.route("/graphql", methods=["GET"])
# def graphql_playground():
#     return explorer.html(None), 200
# st.title("💬 Natural Language MongoDB CRUD")
# st.write("Use natural language to interact with your MongoDB collection (`imdb.movies`).")
# graphql_endpoint = "http://localhost:5000/graphql"
# with st.form("request_form"):
#     request_text = st.text_area("Enter your request:", "e.g., Find all movies with rating above 8", height=100)
#     submitted = st.form_submit_button("🚀 Run")
# if submitted and request_text:
#     with st.spinner("Processing your request..."):
#         # Heuristic to decide between a query (ask) and a command (mutation)
#         is_cud_command = any(word in request_text.lower() for word in ["add", "insert", "create", "update", "change", "delete", "remove"])
        
#         if is_cud_command:
#             graphql_query = {"query": "mutation ProcessCommand($command: String!) { processCommand(command: $command) }", "variables": {"command": request_text}}
#         else:
#             graphql_query = {"query": "query AskQuery($question: String!) { ask(question: $question) }", "variables": {"question": request_text}}
        
#         try:
#             api_endpoint = os.getenv("FLASK_API_ENDPOINT", graphql_endpoint)
#             response = requests.post(api_endpoint, json=graphql_query, timeout=120); response.raise_for_status()
#             result_data = response.json()
            
#             st.subheader("Raw GraphQL Response (for debugging)")
#             st.json(result_data)

#             if 'errors' in result_data:
#                 st.error(result_data['errors'][0]['message'])
#             else:
#                 st.success("Request successful!")
#                 data = result_data['data']
                
#                 # Get the response from either the query or the mutation
#                 if is_cud_command:
#                     natural_language_response = data.get('processCommand')
#                 else:
#                     natural_language_response = data.get('ask')

#                 if natural_language_response:
#                     st.markdown("---")
#                     st.subheader("AI Assistant Response:")
#                     st.markdown(natural_language_response)
#                 else:
#                     st.warning("Received an empty response from the assistant.")
#         except requests.exceptions.RequestException as e: st.error(f"Failed to connect to the backend API: {e}.")
#         except Exception as e: st.error(f"An unexpected error occurred: {e}")
# app = flask_app
#################################################################################
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
    # Add a server selection timeout for better network resilience
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
    # Set a 120-second timeout to be patient with the model loading
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
# This is the final, most robust prompt for intelligent searching.
PROMPT_TEMPLATE = """
You are an expert at converting natural language into MongoDB queries.
Your task is to take the user's request and the database schema and return a JSON object representing the necessary MongoDB operation.

DATABASE SCHEMA (Collection: "movies"):
- Title: String
- Genre: String (comma-separated, e.g., "Action,Adventure,Sci-Fi")
- Director: String
- Actors: String (comma-separated)
- Year: Integer
- Runtime: Integer
- Rating: Float

**CRITICAL INSTRUCTION 1**: For any text search on fields like `Title`, `Genre`, `Director`, or `Actors`, you MUST use a case-insensitive regular expression. The format is `{{"$regex": "search term", "$options": "i"}}`.

**CRITICAL INSTRUCTION 2**: NEVER add a `projection` field to your response. The application will handle which fields to show. ALWAYS return all fields for matched documents. If the user asks for "just the titles", you should still return a 'find' operation with a query that matches the documents, and no projection.

Return ONLY a single JSON object with the following structure:
{{
  "operation": "<operation_name>",
  "query": {{ ... mongo query filter ... }},
  "update": {{ ... mongo update document ... }},
  "document": {{ ... mongo document to insert ... }}
}}

**EXAMPLES:**

User request: "list of movies which has genre Mystery"
Your response: {{"operation": "find", "query": {{ "Genre": {{"$regex": "Mystery", "$options": "i"}} }} }}

User request: "show me the titles of all movies"
Your response: {{"operation": "find", "query": {{}} }}

User request: "find movies directed by james gunn"
Your response: {{"operation": "find", "query": {{ "Director": {{"$regex": "james gunn", "$options": "i"}} }} }}

User request: "add a movie 'Super Film', rating 8, directed by 'Me', starring 'Myself'"
Your response: {{"operation": "insert_one", "document": {{"Title": "Super Film", "Rating": 8, "Director": "Me", "Actors": "Myself"}} }}

Now, process the following user request.

User request: "{user_request}"
Your response:
"""

def generate_mongo_query_from_text(text):
    prompt = PROMPT_TEMPLATE.format(user_request=text)
    try:
        response = ollama_client.chat(model='phi3:mini', messages=[{'role': 'user', 'content': prompt}], options={'temperature': 0.0})
        content = response['message']['content'].strip()
        
        # Robust JSON extraction
        if "```json" in content:
            content = content.split("```json\n")[1].split("```")[0]
        elif "{" in content:
            start_index = content.find('{')
            end_index = content.rfind('}')
            if start_index != -1 and end_index != -1 and end_index > start_index:
                content = content[start_index:end_index+1]
        
        # Clean the JSON string before parsing (handles single quotes)
        content = content.replace("'", '"')
        
        return json.loads(content)
    except Exception as e:
        return {"error": f"LLM or JSON parsing failed: {e}"}

# --- GraphQL Resolvers ---
@query.field("ask")
def resolve_ask(_, info, question):
    llm_output = generate_mongo_query_from_text(question)

    if "error" in llm_output:
        return [{"error": f"LLM Error: {llm_output['error']}"}]
    
    if llm_output.get("operation") != "find":
        return [{"error": f"Could not process 'find' request. LLM returned operation: {llm_output.get('operation')}"}]
    try:
        query_filter = llm_output.get("query", {})
        if not isinstance(query_filter, dict):
             return [{"error": f"LLM generated an invalid query filter. Expected a dictionary, got: {type(query_filter)}"}]
        
        projection = {
            "Title": 1, "Description": 1, "Year": 1, "Runtime": 1,
            "Rating": 1, "Votes": 1, "Revenue": 1, "Genre": 1,
            "Actors": 1, "Director": 1
        }
        # Increased limit to 25
        results_from_db = list(movies_collection.find(query_filter, projection).limit(25))
        
        if not results_from_db:
            return []
            
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
        
        return formatted_results
    except Exception as e:
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

# --- Flask App & Streamlit UI ---
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
            # Set a 120-second timeout for the HTTP request to the backend
            response = requests.post(api_endpoint, json=graphql_query, timeout=120); response.raise_for_status()
            result_data = response.json()
            st.subheader("GraphQL Response"); st.json(result_data)
            if 'errors' in result_data: st.error(result_data['errors'][0]['message'])
            else:
                st.success("Request successful!")
                data = result_data['data']
                if is_query:
                    movies = data.get('ask', [])
                    # Improved UI feedback
                    if not movies:
                        st.warning("Query executed successfully, but no matching records were found in the database.")
                    elif "error" in movies[0]:
                        st.error(f"An error occurred: {movies[0]['error']}")
                    else:
                        st.dataframe(pd.DataFrame(movies))
                else:
                    st.info(data.get('processCommand'))
        except requests.exceptions.RequestException as e: st.error(f"Failed to connect to the backend API: {e}.")
        except Exception as e: st.error(f"An unexpected error occurred: {e}")
app = flask_app