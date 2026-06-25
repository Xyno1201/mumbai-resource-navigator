# Mumbai Resource Navigator — Docker image
# Base: python:3.11-slim
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install Python dependencies first (leverages Docker layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the full project
COPY . .

# Runtime environment — API key must be supplied at `docker run` time via --env
ENV GOOGLE_GENAI_USE_VERTEXAI=FALSE

# Expose the ADK web port
EXPOSE 8000

# Run the ADK web UI bound to all interfaces so it is reachable outside the container
CMD ["adk", "web", "--host", "0.0.0.0", "--port", "8000"]
