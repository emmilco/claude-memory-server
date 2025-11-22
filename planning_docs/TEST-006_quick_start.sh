#!/bin/bash
# Quick Start Script for E2E Testing Orchestration
# Claude Memory RAG Server v4.0

set -e

echo "============================================"
echo "E2E Testing Orchestration - Quick Start"
echo "============================================"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check prerequisites
echo "Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not found. Please install Docker first.${NC}"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}❌ Docker Compose not found. Please install Docker Compose first.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Docker found: $(docker --version)${NC}"
echo -e "${GREEN}✅ Docker Compose found: $(docker-compose --version)${NC}"
echo ""

# Navigate to project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

echo "Project root: $PROJECT_ROOT"
cd "$PROJECT_ROOT"

# Create results directory
mkdir -p results

# Show menu
echo ""
echo "============================================"
echo "Select an option:"
echo "============================================"
echo "1. Run ALL tests in parallel (10 agents, ~2 hours)"
echo "2. Run CRITICAL tests only (3 agents, ~60 min)"
echo "3. Run installation tests only (1 agent, ~45 min)"
echo "4. Run custom selection"
echo "5. View previous results"
echo "6. Clean up containers and volumes"
echo "7. Exit"
echo ""

read -p "Enter your choice [1-7]: " choice

case $choice in
    1)
        echo -e "${YELLOW}Starting ALL agents in parallel...${NC}"
        docker-compose -f planning_docs/TEST-006_docker_compose.yml up --build
        ;;
    2)
        echo -e "${YELLOW}Starting CRITICAL agents only...${NC}"
        docker-compose -f planning_docs/TEST-006_docker_compose.yml up --build \
            agent-mcp-memory \
            agent-mcp-code \
            agent-code-search \
            orchestrator
        ;;
    3)
        echo -e "${YELLOW}Starting installation tests...${NC}"
        docker-compose -f planning_docs/TEST-006_docker_compose.yml up --build agent-install
        ;;
    4)
        echo ""
        echo "Available agents:"
        echo "  - agent-install (Installation & Setup)"
        echo "  - agent-mcp-memory (MCP Memory Tools)"
        echo "  - agent-mcp-code (MCP Code Tools)"
        echo "  - agent-mcp-advanced (MCP Multi-Project)"
        echo "  - agent-cli-core (CLI Core)"
        echo "  - agent-cli-management (CLI Management)"
        echo "  - agent-code-search (Code Search)"
        echo "  - agent-features (Features)"
        echo "  - agent-ui-config (UI/Config)"
        echo "  - agent-quality (Quality)"
        echo ""
        read -p "Enter agent names (space-separated): " agents
        echo -e "${YELLOW}Starting selected agents: $agents${NC}"
        docker-compose -f planning_docs/TEST-006_docker_compose.yml up --build $agents
        ;;
    5)
        echo ""
        if [ -f "results/E2E_TEST_REPORT.md" ]; then
            echo -e "${GREEN}Previous results found:${NC}"
            echo ""
            cat results/E2E_TEST_REPORT.md
        else
            echo -e "${RED}No previous results found.${NC}"
        fi
        ;;
    6)
        echo -e "${YELLOW}Cleaning up containers and volumes...${NC}"
        docker-compose -f planning_docs/TEST-006_docker_compose.yml down -v
        echo -e "${GREEN}✅ Cleanup complete${NC}"
        ;;
    7)
        echo "Exiting..."
        exit 0
        ;;
    *)
        echo -e "${RED}Invalid choice. Exiting.${NC}"
        exit 1
        ;;
esac

# After completion, show results
echo ""
echo "============================================"
echo "Test Execution Complete!"
echo "============================================"
echo ""

if [ -f "results/E2E_TEST_REPORT.md" ]; then
    echo -e "${GREEN}✅ Results saved to: results/${NC}"
    echo ""
    echo "View full report:"
    echo "  cat results/E2E_TEST_REPORT.md"
    echo ""
    echo "View JSON report:"
    echo "  cat results/consolidated_report.json"
    echo ""
    echo "View individual agent results:"
    echo "  ls results/agents/"
    echo ""

    # Show quick summary
    echo "Quick Summary:"
    grep -A 10 "## Executive Summary" results/E2E_TEST_REPORT.md || true
fi
