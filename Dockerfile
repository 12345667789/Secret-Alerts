# Use an official lightweight Python image.
# Using a specific version tag (e.g., 3.9-slim) is better for reproducibility.
FROM python:3.9-slim

# --- Environment Variables ---
# Set environment variables to prevent Python from writing .pyc files to disc
# and to prevent it from buffering stdout and stderr.
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory in the container.
WORKDIR /app

# --- System Dependencies ---
# Install system dependencies required for the application.
# Here, we only need curl for the health check.
# We clean up the apt cache to keep the image size small.
RUN apt-get update && apt-get install -y curl \
    && rm -rf /var/lib/apt/lists/*

# --- Python Dependencies ---
# *** THE FIX IS HERE ***
# First, upgrade pip to the latest version.
# Then, copy the requirements file and install the packages.
# The newer version of pip is better at resolving binary conflicts like the one
# you are seeing between pandas and numpy.
RUN pip install --upgrade pip
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Application Code ---
# Copy the rest of the application's source code.
# This is placed after dependency installation to ensure that code changes
# don't trigger a full reinstall of all packages.
COPY . .

# --- Port Exposure ---
# Expose the port the app runs on. This is the port that Google Cloud Run
# will use to send traffic to the container.
EXPOSE 8080

# --- Health Check ---
# Add a health check to ensure the application is running correctly.
# Cloud Run uses this to determine if the container is healthy.
# Your new main.py (v4.1) has a specific '/health' endpoint for this.
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# --- Run Command ---
# Specify the command to run on container startup.
# Use gunicorn as the production server and point it to the 'app' object in your 'run.py' file
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "run:app"]
