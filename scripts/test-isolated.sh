#!/bin/bash
# scripts/test-isolated.sh
# Run tests with an isolated Qdrant instance (or fallback to existing)
#
# Usage: ./scripts/test-isolated.sh [pytest args]
# Example: ./scripts/test-isolated.sh tests/unit/ -v --tb=short
#
# On macOS Docker Desktop, uses existing Qdrant at localhost:6333
# On Linux, creates isolated test container with unique port per worktree

set -e

# --- Configuration ---
QDRANT_IMAGE="qdrant/qdrant:v1.15.5"
BASE_PORT=6340
MAX_PORT=6359  # 20 possible instances
CONTAINER_PREFIX="qdrant-test"
MAX_RETRIES=5  # Retries for port conflicts

# --- Detect Identity ---
# Use worktree name if in worktree, otherwise use a short UUID
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

if [[ "$PWD" == *".worktrees/"* ]]; then
    # Extract worktree name from path
    WORKTREE_NAME=$(echo "$PWD" | sed 's/.*\.worktrees\///' | cut -d'/' -f1)
else
    WORKTREE_NAME="main"
fi

CONTAINER_NAME="${CONTAINER_PREFIX}-${WORKTREE_NAME}"

# --- Utility Functions ---
check_qdrant_ready() {
    local port=$1
    local max_wait=$2

    echo -n "Waiting for Qdrant..."
    for i in $(seq 1 $max_wait); do
        if curl -s "http://localhost:${port}/readyz" >/dev/null 2>&1; then
            echo " ready!"
            return 0
        fi
        echo -n "."
        sleep 0.5
    done
    echo " TIMEOUT"
    return 1
}

pre_warm_pool() {
    local port=$1
    echo "Pre-warming collection pool..."
    for i in 0 1 2 3; do
        curl -s -X PUT "http://localhost:${port}/collections/test_pool_${i}" \
            -H "Content-Type: application/json" \
            -d '{
                "vectors": {
                    "size": 768,
                    "distance": "Cosine"
                }
            }' >/dev/null 2>&1 || true
    done
}

cleanup() {
    echo ""
    echo "Stopping test Qdrant instance..."
    docker stop "$CONTAINER_NAME" 2>/dev/null || true
    # --rm flag handles removal
}

# --- Main ---
echo "=== Isolated Test Runner ==="
echo "Worktree: $WORKTREE_NAME"

# Try to use existing Qdrant at port 6333
if check_qdrant_ready 6333 3; then
    echo "Using existing Qdrant at port 6333"
    PORT=6333
    REUSING_EXISTING=true
else
    # No existing Qdrant - try to start one
    REUSING_EXISTING=false

    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "ERROR: Qdrant not found at localhost:6333"
        echo "On macOS, please start Qdrant with: docker-compose up -d"
        exit 1
    fi

    # Linux: Find available port and start isolated container
    find_free_port() {
        local hash_port=$((BASE_PORT + $(echo "$WORKTREE_NAME" | cksum | cut -d' ' -f1) % 20))
        if ! lsof -i :$hash_port >/dev/null 2>&1; then
            echo $hash_port
            return 0
        fi

        for port in $(seq $BASE_PORT $MAX_PORT); do
            if ! lsof -i :$port >/dev/null 2>&1; then
                echo $port
                return 0
            fi
        done
        echo "ERROR: No free ports in range $BASE_PORT-$MAX_PORT" >&2
        exit 1
    }

    PORT=$(find_free_port)
    echo "Starting ephemeral Qdrant on port $PORT..."

    # Start container with retry logic
    STARTED=false
    for attempt in $(seq 1 $MAX_RETRIES); do
        if docker run -d \
            --name "$CONTAINER_NAME" \
            --rm \
            -p "${PORT}:6333" \
            -e QDRANT__SERVICE__HTTP_PORT=6333 \
            -e QDRANT__STORAGE__PERFORMANCE__MAX_SEARCH_THREADS=1 \
            -e QDRANT__STORAGE__OPTIMIZERS__INDEXING_THRESHOLD=100 \
            --memory=512m \
            --cpus=1 \
            "$QDRANT_IMAGE" \
            >/dev/null 2>&1; then
            STARTED=true
            break
        else
            if [ $attempt -lt $MAX_RETRIES ]; then
                echo "Start attempt $attempt failed, retrying..."
                sleep 0.$((RANDOM % 5 + 1))
                docker rm -f "$CONTAINER_NAME" 2>/dev/null || true
            fi
        fi
    done

    if [ "$STARTED" = false ]; then
        echo "ERROR: Failed to start Qdrant container" >&2
        exit 1
    fi

    # Wait for Qdrant to be ready
    if ! check_qdrant_ready $PORT 30; then
        docker stop "$CONTAINER_NAME" 2>/dev/null || true
        echo "ERROR: Qdrant failed to start" >&2
        exit 1
    fi

    # Pre-warm collection pool
    pre_warm_pool $PORT
fi

# Register cleanup trap (only if we started a container, not reusing)
if [ "$REUSING_EXISTING" = false ]; then
    trap cleanup EXIT INT TERM
fi

# Export for pytest
export CLAUDE_RAG_QDRANT_URL="http://localhost:${PORT}"
export CLAUDE_RAG_QDRANT_COLLECTION_NAME="test_pool_0"

echo "Qdrant URL: $CLAUDE_RAG_QDRANT_URL"
echo ""
echo "Running: pytest $@"
echo "=========================================="

# Run pytest with all passed arguments
pytest "$@"
EXIT_CODE=$?

echo ""
echo "=========================================="
echo "Tests completed with exit code: $EXIT_CODE"

exit $EXIT_CODE
