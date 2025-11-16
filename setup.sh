#!/bin/bash
set -e

echo "=========================================="
echo "Claude Memory + RAG Server - Setup"
echo "=========================================="
echo ""

# Check Python version
echo "Checking Python version..."
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 not found. Please install Python 3.8 or higher."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "Found Python $PYTHON_VERSION"

# Verify Python >= 3.8
PYTHON_MAJOR=$(python3 -c 'import sys; print(sys.version_info[0])')
PYTHON_MINOR=$(python3 -c 'import sys; print(sys.version_info[1])')

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 8 ]); then
    echo "Error: Python 3.8 or higher required. Found $PYTHON_VERSION"
    exit 1
fi

# Install dependencies
echo ""
echo "Installing dependencies..."
pip3 install -r requirements.txt || {
    echo "Error: Failed to install dependencies"
    exit 1
}

# Download embedding model (first-time setup)
echo ""
echo "Downloading embedding model (one-time, ~80MB)..."
echo "This may take a few minutes..."
python3 <<EOF
from sentence_transformers import SentenceTransformer
import sys
try:
    model = SentenceTransformer('all-MiniLM-L6-v2')
    print(' Embedding model downloaded successfully')
except Exception as e:
    print(f'Error downloading model: {e}', file=sys.stderr)
    sys.exit(1)
EOF

if [ $? -ne 0 ]; then
    echo "Error: Failed to download embedding model"
    exit 1
fi

# Initialize database
echo ""
echo "Initializing database..."
python3 <<EOF
from pathlib import Path
import sys
sys.path.insert(0, 'src')
from database import MemoryDatabase

try:
    db_dir = Path.home() / '.claude-rag'
    db_dir.mkdir(exist_ok=True)
    db = MemoryDatabase(str(db_dir / 'memory.db'))
    db.close()
    print(f' Database initialized at: {db_dir / "memory.db"}')
except Exception as e:
    print(f'Error initializing database: {e}', file=sys.stderr)
    sys.exit(1)
EOF

if [ $? -ne 0 ]; then
    echo "Error: Failed to initialize database"
    exit 1
fi

# Get absolute path to mcp_server.py
SERVER_PATH="$(cd "$(dirname "$0")" && pwd)/src/mcp_server.py"

# Add MCP server to Claude Code
echo ""
echo "Adding MCP server to Claude Code..."

# Check if claude command exists
if ! command -v claude &> /dev/null; then
    echo "Warning: 'claude' command not found. Is Claude Code installed?"
    echo "You can manually add the server later with:"
    echo "  claude mcp add --transport stdio --scope user claude-memory-rag -- python3 $SERVER_PATH"
    exit 0
fi

# Add the server
claude mcp add --transport stdio --scope user claude-memory-rag -- python3 "$SERVER_PATH" || {
    echo "Warning: Failed to add MCP server automatically."
    echo "You can add it manually with:"
    echo "  claude mcp add --transport stdio --scope user claude-memory-rag -- python3 $SERVER_PATH"
}

echo ""
echo " MCP server added to Claude Code"

# Test connection
echo ""
echo "Testing connection..."
if claude mcp list 2>&1 | grep -q "claude-memory-rag"; then
    echo " Server connected successfully!"
else
    echo "Warning: Server may not be connected. Run 'claude mcp list' to check."
fi

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Start a new Claude Code session (or restart current one)"
echo "  2. Ask Claude to ingest docs: 'Analyze the current directory for documentation'"
echo "  3. Query your docs: 'How do I install this project?'"
echo "  4. Store preferences: 'I prefer Python for all projects'"
echo ""
echo "Your memories are stored at: ~/.claude-rag/memory.db"
echo "View stats: Ask Claude 'Show me memory statistics'"
echo ""
echo "For help, see README.md and docs/USAGE.md"
echo ""
