# Natural Language MongoDB CRUD

This project is a web application that fulfills the assignment of creating a system to interact with a MongoDB database using natural language. Users can perform CRUD (Create, Read, Update, Delete) operations on a movie database by simply typing commands in plain English, which are then translated into database queries by a Large Language Model (LLM).

The application is fully containerized using Docker, ensuring it runs consistently across different environments. It leverages a modern technology stack including a Python backend with Flask and GraphQL, a real-time frontend with Streamlit, and a locally-run, open-source LLM managed by Ollama.

## Core Features

-   **Natural Language Interface:** Users can type requests like "find all movies directed by James Cameron" or "update the rating for Inception to 9.0".
-   **Full CRUD Functionality:** Supports creating, reading, updating, and deleting movie records.
-   **GraphQL API:** A robust GraphQL API serves as the bridge between the frontend and the backend logic.
-   **Open-Source LLM:** Uses `phi3:mini`, a powerful and efficient open-source model from Microsoft, run locally via Ollama. No proprietary APIs or keys are needed.
-   **Containerized Deployment:** The entire application stack (backend, frontend, LLM service) is managed by Docker and Docker Compose for easy setup and deployment.

## Technology Stack

-   **Backend:** Python 3.9, Flask
-   **API Layer:** Ariadne (for GraphQL implementation)
-   **Web Server:** Gunicorn
-   **Frontend:** Streamlit
-   **Database:** MongoDB Atlas (Cloud-hosted)
-   **LLM Service:** Ollama
-   **LLM Model:** `phi3:mini` (A powerful, memory-efficient model)
-   **Containerization:** Docker & Docker Compose

## System Architecture

The application follows a simple, robust data flow:

1.  **User Input:** The user types a natural language command into the **Streamlit** frontend.
2.  **API Call:** Streamlit sends the command as a variable in a **GraphQL** query to the **Flask** backend.
3.  **LLM Translation:** The Flask resolver constructs a detailed prompt (including the database schema) and sends it to the **Ollama** service. The `phi3:mini` model translates the user's command into a structured JSON object representing a MongoDB query.
4.  **Database Operation:** The Flask backend parses the JSON from the LLM and uses the `pymongo` library to execute the command against the **MongoDB Atlas** database.
5.  **Response:** The result from MongoDB is returned through the GraphQL API to the Streamlit frontend.
6.  **Display:** Streamlit displays the raw GraphQL response and a user-friendly data table to the user.

## Getting Started

Follow these steps to get the application running on your local machine.

### Prerequisites

-   [Docker](https://www.docker.com/get-started/) and **Docker Desktop** installed.
-   A free [MongoDB Atlas](https://www.mongodb.com/products/platform/atlas-database) account.

### Step 1: Set Up MongoDB Atlas

1.  **Create a Free Cluster:** Log in to MongoDB Atlas and create a new project and a new **free M0 cluster**.
2.  **Create a Database User:** In your cluster's **Database Access** tab, create a new user with a username and password. **Save these credentials securely.**
3.  **Configure Network Access:** In the **Network Access** tab, click "Add IP Address" and choose **"Allow Access From Anywhere"** (0.0.0.0/0).
4.  **Get Connection String:** Go to your cluster's "Overview" and click **Connect -> Drivers**. Copy the provided connection string.
5.  **Import Data:**
    *   In your cluster, click **"Browse Collections"**.
    *   Click **"Add My Own Data"**.
    *   Database Name: `imdb`
    *   Collection Name: `movies`
    *   Click "Create".
    *   Select the `movies` collection and click the **"Import Data"** button.
    *   Choose the `IMDB-Movie-Data.csv` file. **Do not change any field types** on the preview screen. Just click **"Import"**.

### Step 2: Configure Environment Variables

1.  In the project folder, rename the file `env.example` to `.env`.
2.  Open the `.env` file with a text editor.
3.  Paste your MongoDB connection string into the `MONGO_URI` field.
4.  Replace `<username>` and `<password>` with the database user credentials you created in Step 1.

The file should look like this:
```env
MONGO_URI="mongodb+srv://your_username:your_password@yourcluster.mongodb.net/?retryWrites=true&w=majority"
OLLAMA_HOST_DOCKER="http://ollama:11434"
FLASK_API_ENDPOINT="http://webapp:5000/graphql"
```

### Step 3: Configure Docker Resources (Crucial Step!)

Large Language Models require significant RAM. You must ensure Docker has enough memory allocated.

**For Windows Users (with WSL 2):**
1.  Open File Explorer and type `%UserProfile%` in the address bar, then press Enter.
2.  Create a new file named `.wslconfig` in this folder.
3.  Open the file with Notepad and paste the following, which allocates a safe 8GB of RAM to Docker:
    ```ini
    [wsl2]
    memory=8GB
    processors=4
    ```
4.  Save the file.
5.  **Restart your computer** or open PowerShell as an Administrator and run `wsl --shutdown` to apply the changes.

**For Mac Users:**
1.  Open Docker Desktop.
2.  Go to **Settings (gear icon) -> Resources**.
3.  Use the slider to increase the allocated **Memory** to at least **8 GB**.
4.  Click "Apply & restart".

### Step 4: Build and Run the Application

1.  **Download the LLM Model:** Before starting the application, it's best to download the model first. Open a terminal and run:
    ```bash
    ollama pull phi3:mini
    ```

2.  **Launch the Application Stack:** Once the model is downloaded, run the main `docker-compose` command. This will build the Python application image and start all services.
    ```bash
    docker-compose up --build
    ```

3.  **Be Patient on First Run:** The first time you make a query, the application may be slow (30-90 seconds) as the `ollama` service loads the `phi3:mini` model into memory. **Subsequent requests will be much faster.**

### Step 5: Access the Application

Open your web browser and navigate to:
**http://localhost:8501**

## How to Use the Application

Simply type your request in the text box and click "Run".

#### Example Queries:

-   **Read (Find):**
    -   `show me all the records`
    -   `Find all movies with a rating above 8`
    -   `List movies directed by Christopher Nolan`
    -   `Show me movies from 2016 starring Ryan Gosling`
-   **Update:**
    -   `Update the rating for "The Dark Knight" to 9.1`
    -   `Change the revenue of "Prometheus" to 130`
-   **Delete:**
    -   `Delete the movie with title "Split"`
-   **Create:**
    -   `Add a new movie called "My AI Project", year 2024, genre "Tech", rating 10.0`

## Project File Structure

```
/natural-language-mongo-crud
|-- app.py                  # Main Python file with Flask, Streamlit, and all logic.
|-- schema.graphql          # Defines the structure of our GraphQL API.
|-- requirements.txt        # Lists all the Python dependencies for the project.
|-- .env                    # Stores secret keys and environment variables (you create this).
|-- .env.example            # A template for the .env file.
|-- Dockerfile              # Instructions to build the Python application's Docker image.
|-- docker-compose.yml      # Orchestrates all our services (app, ollama) to run together.
|-- IMDB-Movie-Data.csv     # The raw movie data.
|-- README.md               # This documentation file.
```

## Troubleshooting Common Issues

-   **Error: "WORKER TIMEOUT" or "Read timed out"**:
    This means the LLM is taking too long to respond on the first run. The `Dockerfile` and `app.py` have been configured with generous 120-second timeouts, but if this still occurs, the primary cause is insufficient RAM.

-   **Error: "Out of Memory" or the app crashes silently**:
    This is the most common issue. The LLM requires a lot of RAM. Please ensure you have completed **Step 3: Configure Docker Resources** correctly for your operating system. Using `phi3:mini` and allocating 8GB of RAM to Docker should solve this on most modern machines.

-   **Data appears as `null` in the response**:
    This typically means there is a mismatch between the field names in your MongoDB collection and the names the Python code is trying to access. This project is configured to work with the exact field names created by a direct CSV import (e.g., `Title`, `Runtime`, `Revenue`). If you have modified the field names, you must update the `projection` dictionary in the `resolve_ask` function in `app.py`.