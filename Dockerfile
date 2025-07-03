# # Use an official Python runtime as a parent image
# FROM python:3.9-slim

# # Set the working directory in the container
# WORKDIR /app

# # Copy the requirements file into the container
# COPY requirements.txt .

# # Install packages
# RUN pip install --no-cache-dir -r requirements.txt

# # Copy the rest of the application's code
# COPY . .

# # Expose Streamlit (8501) and Flask (5000) ports
# EXPOSE 8501
# EXPOSE 5000

# # This command starts the Flask API in the background using Gunicorn,
# # and then starts the Streamlit frontend in the foreground.
# CMD sh -c "gunicorn --bind 0.0.0.0:5000 app:app & streamlit run app.py --server.port 8501 --server.address 0.0.0.0"
#######################################
# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install packages
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's code
COPY . .

# Expose Streamlit (8501) and Flask (5000) ports
EXPOSE 8501
EXPOSE 5000

# CHANGED: Added "--timeout 120" to the gunicorn command.
# This gives the worker 120 seconds to respond before being killed.
CMD sh -c "gunicorn --bind 0.0.0.0:5000 --timeout 120 app:app & streamlit run app.py --server.port 8501 --server.address 0.0.0.0"