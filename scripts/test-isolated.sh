#!/bin/bash
# scripts/test-isolated.sh
# Run tests with an isolated, ephemeral Qdrant instance
#
# Usage: ./scripts/test-isolated.sh [pytest args]
# Example: ./scripts/test-isolated.sh tests/unit/ -v --tb=short
#
# Each worktree gets its own Qdrant container, preventing cross-agent
# test interference during parallel development.

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

# --- Find Available Port ---
# First tries a deterministic port based on worktree name hash,
# then falls back to scanning for any free port
find_free_port() {
    # Try deterministic port first (based on worktree name hash)
    # This gives each worktree a "preferred" port for consistency
    local hash_port=$((BASE_PORT + $(echo "$WORKTREE_NAME" | cksum | cut -d' ' -f1) % 20))
    if ! lsof -i :$hash_port >/dev/null 2>&1; then
        echo $hash_port
        return 0
    fi

    # Fall back to scanning for any free port
    for port in $(seq $BASE_PORT $MAX_PORT); do
        if ! lsof -i :$port >/dev/null 2>&1; then
            echo $port
            return 0
        fi
    done
    echo "ERROR: No free ports in range $BASE_PORT-$MAX_PORT" >&2
    exit 1
}

# --- Check for Existing Container ---
existing_container() {
    docker ps -q -f "name=^${CONTAINER_NAME}$" 2>/dev/null
}

get_container_port() {
    docker port "$CONTAINER_NAME" 6333 2>/dev/null | cut -d: -f2
}

# --- Cleanup Handler ---
cleanup() {
    echo ""
    echo "Stopping test Qdrant instance..."
    docker stop "$CONTAINER_NAME" 2>/dev/null || true
    # --rm flag handles removal
}

# --- Main ---
echo "=== Isolated Test Runner ==="
echo "Worktree: $WORKTREE_NAME"

# Check if container already running for this worktree
if container_id=$(existing_container) && [ -n "$container_id" ]; then
    PORT=$(get_container_port)
    echo "Reusing existing container on port $PORT"
else
    # Try to start container with retry logic for port conflicts
    STARTED=false
    for attempt in $(seq 1 $MAX_RETRIES); do
        PORT=$(find_free_port)
        echo "Starting ephemeral Qdrant on port $PORT (attempt $attempt/$MAX_RETRIES)..."

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
            echo "Port $PORT conflict, retrying..."
            # Small random delay to desynchronize concurrent starts
            sleep 0.$((RANDOM % 5 + 1))
            # Remove failed container if it exists
            docker rm -f "$CONTAINER_NAME" 2>/dev/null || true
        fi
    done

    if [ "$STARTED" = false ]; then
        echo "ERROR: Failed to start container after $MAX_RETRIES attempts" >&2
        exit 1
    fi

    # Wait for Qdrant to be ready
    echo -n "Waiting for Qdrant..."
    for i in $(seq 1 30); do
        if curl -s "http://localhost:${PORT}/readyz" >/dev/null 2>&1; then
            echo " ready!"
            break
        fi
        echo -n "."
        sleep 0.5
    done

    # Pre-warm: create collection pool
    echo "Pre-warming collection pool..."
    for i in 0 1 2 3; do
        curl -s -X PUT "http://localhost:${PORT}/collections/test_pool_${i}" \
            -H "Content-Type: application/json" \
            -d '{
                "vectors": {
                    "size": 768,
                    "distance": "Cosine"
                }
            }' >/dev/null 2>&1 || true
    done
fi

# Register cleanup trap
trap cleanup EXIT INT TERM

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
