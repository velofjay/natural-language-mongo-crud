# import os
# from pymongo import MongoClient
# from dotenv import load_dotenv

# # --- SCRIPT TO FIX THE MOVIES COLLECTION SCHEMA ---
# # This script converts the 'Genre' and 'Actors' string fields
# # into proper arrays named 'genres' and 'actors'.

# def fix_movie_schema():
#     """
#     Connects to MongoDB and updates movie documents.
#     - Converts 'Genre' string to 'genres' array.
#     - Converts 'Actors' string to 'actors' array.
#     - Removes the old 'Genre' and 'Actors' fields.
#     """
#     load_dotenv()
#     MONGO_URI = os.getenv("MONGO_URI")
    
#     if not MONGO_URI:
#         print("Error: MONGO_URI not found in .env file.")
#         return

#     print("Connecting to MongoDB...")
#     try:
#         client = MongoClient(MONGO_URI)
#         db = client.imdb
#         movies_collection = db.movies
#         print("Connection successful.")
#     except Exception as e:
#         print(f"Failed to connect to DB: {e}")
#         return

#     # Find documents that still have the old string format
#     documents_to_update = list(movies_collection.find({ "Genre": { "$exists": True } }))
    
#     if not documents_to_update:
#         print("No documents found with the old 'Genre' string field. Schema might already be updated.")
#         return

#     print(f"Found {len(documents_to_update)} documents to update...")
#     updated_count = 0

#     for doc in documents_to_update:
#         try:
#             # Split the strings into arrays
#             genres_array = [g.strip() for g in doc['Genre'].split(',')]
#             actors_array = [a.strip() for a in doc['Actors'].split(',')]

#             # Perform the update
#             movies_collection.update_one(
#                 { "_id": doc["_id"] },
#                 {
#                     "$set": {
#                         "genres": genres_array, # Add new array field
#                         "actors": actors_array  # Add new array field
#                     },
#                     "$unset": {
#                         "Genre": "",  # Remove old string field
#                         "Actors": "", # Remove old string field
#                         "Rank": "",   # Also remove Rank and Metascore if they exist
#                         "Metascore": ""
#                     }
#                 }
#             )
#             updated_count += 1
#             if updated_count % 100 == 0:
#                 print(f"Updated {updated_count}/{len(documents_to_update)} documents...")

#         except KeyError as e:
#             print(f"Skipping document {doc['_id']} due to missing key: {e}")
#         except Exception as e:
#             print(f"An error occurred while updating document {doc['_id']}: {e}")
            
#     print(f"\nUpdate complete. Successfully updated {updated_count} documents.")

# if __name__ == "__main__":
#     fix_movie_schema()
##################################################
# lower case version
##################################################
import os
from pymongo import MongoClient
from dotenv import load_dotenv

def fix_and_rename_schema():
    """
    Connects to MongoDB and updates all movie documents.
    1. Converts 'Genre' and 'Actors' strings to arrays.
    2. Renames fields to be lowercase and consistent.
    3. Removes old/unnecessary fields.
    """
    load_dotenv()
    MONGO_URI = os.getenv("MONGO_URI")
    
    if not MONGO_URI:
        print("Error: MONGO_URI not found in .env file.")
        return

    print("Connecting to MongoDB...")
    client = MongoClient(MONGO_URI)
    db = client.imdb
    movies_collection = db.movies
    print("Connection successful.")

    # This single update command with an aggregation pipeline will process all documents.
    # It's much more efficient than fetching and updating one by one.
    print("Starting schema update and field rename process...")
    try:
        result = movies_collection.update_many(
            {},  # Empty filter to match all documents
            [    # Aggregation pipeline for the update
                {
                    "$set": {
                        # Create new lowercase fields from old ones
                        "title": "$Title",
                        "description": "$Description",
                        "directors": { "$split": ["$Director", ", "] }, # Director can also be multiple
                        "year": "$Year",
                        "runtime": { "$ifNull": ["$Runtime (Minutes)", "$Runtime"] }, # Handle potential name variations
                        "rating": "$Rating",
                        "votes": "$Votes",
                        "revenue": { "$ifNull": ["$Revenue (Millions)", "$Revenue"] }, # Handle potential name variations
                        "genres": { "$split": ["$Genre", ","] },
                        "actors": { "$split": ["$Actors", ","] }
                    }
                },
                {
                    "$unset": [
                        # Remove all old, inconsistently named fields
                        "Title", "Genre", "Description", "Director", "Actors",
                        "Year", "Runtime (Minutes)", "Runtime", "Rating", "Votes",
                        "Revenue (Millions)", "Revenue", "Rank", "Metascore", "Ids"
                    ]
                }
            ]
        )
        print(f"\nProcess complete.")
        print(f"Matched {result.matched_count} documents.")
        print(f"Modified {result.modified_count} documents.")
    except Exception as e:
        print(f"An error occurred during the bulk update: {e}")

if __name__ == "__main__":
    fix_and_rename_schema()