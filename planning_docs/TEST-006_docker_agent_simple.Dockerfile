# Simplified Dockerfile for E2E Testing Agent (No Rust, Faster Build)
# Use this for quick testing without Rust parser

FROM python:3.11-slim-bookworm

# Set debian retry policy
RUN echo "Acquire::Retries \"3\";" > /etc/apt/apt.conf.d/80-retries && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get update --fix-missing

# Install minimal system dependencies
RUN apt-get install -y --no-install-recommends git curl && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy only requirements first (for better layer caching)
COPY requirements.txt /app/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy rest of project files
COPY . /app/

# Set environment variables for testing
ENV CLAUDE_RAG_STORAGE_BACKEND=qdrant
ENV CLAUDE_RAG_QDRANT_URL=http://qdrant:6333
ENV PYTHONUNBUFFERED=1

# Create directories for test results
RUN mkdir -p /test_results /test_logs

# Entry point will be the test orchestration script
ENTRYPOINT ["python", "-m", "testing.orchestrator.agent"]
