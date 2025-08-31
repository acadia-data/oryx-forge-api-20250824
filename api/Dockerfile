# Use a slim Python base image for smaller size
FROM python:3.9-slim-buster

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file and install dependencies first
# This helps with Docker caching layers if requirements don't change
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code
COPY . .

# Cloud Run injects a PORT environment variable.
# Your application must listen on this port.
# Uvicorn by default listens on 8000, so we pass the PORT from env.
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
