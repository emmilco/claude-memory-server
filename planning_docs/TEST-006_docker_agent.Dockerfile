# Dockerfile for E2E Testing Agent
# Each agent runs in an isolated container to execute a portion of the test plan

# Use Python 3.11 (more stable than 3.13)
FROM python:3.11-slim-bookworm

# Set debian mirror and update package lists with retry
RUN echo "Acquire::Retries \"3\";" > /etc/apt/apt.conf.d/80-retries && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get update --fix-missing

# Install system dependencies (one at a time for better error diagnosis)
RUN apt-get install -y --no-install-recommends git && \
    apt-get install -y --no-install-recommends curl && \
    apt-get install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/*

# Install Rust (optional, for Rust parser testing)
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain stable
ENV PATH="/root/.cargo/bin:${PATH}"

# Set working directory
WORKDIR /app

# Copy project files
COPY . /app/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install maturin for Rust builds (if testing Rust parser)
RUN pip install --no-cache-dir maturin

# Build Rust module (optional, will fall back to Python if this fails)
RUN cd rust_core && maturin develop --release 2>&1 || echo "Rust build failed, will use Python fallback"

# Set environment variables for testing
ENV CLAUDE_RAG_STORAGE_BACKEND=qdrant
ENV CLAUDE_RAG_QDRANT_URL=http://qdrant:6333
ENV PYTHONUNBUFFERED=1

# Create directories for test results
RUN mkdir -p /test_results /test_logs

# Entry point will be the test orchestration script
ENTRYPOINT ["python", "-m", "testing.orchestrator.agent"]
