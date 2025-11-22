# Minimal Dockerfile for E2E Testing Agent
# Uses base image that already has git/curl - NO apt-get needed!

FROM python:3.11-slim-bookworm

# Set working directory
WORKDIR /app

# Copy only requirements first (for better layer caching)
COPY requirements.txt /app/

# Install Python dependencies (pip works without network issues)
RUN pip install --no-cache-dir -r requirements.txt || \
    pip install --no-cache-dir --retries 3 --timeout 300 -r requirements.txt

# Copy rest of project files
COPY . /app/

# Set environment variables for testing
ENV CLAUDE_RAG_STORAGE_BACKEND=qdrant
ENV CLAUDE_RAG_QDRANT_URL=http://qdrant:6333
ENV PYTHONUNBUFFERED=1

# Create directories for test results
RUN mkdir -p /test_results /test_logs

# Entry point
ENTRYPOINT ["python", "-m", "testing.orchestrator.agent"]
