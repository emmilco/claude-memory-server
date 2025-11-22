#!/bin/bash
# Run all 10 E2E test agents in parallel
# TEST-006: Comprehensive E2E Testing

set -e

echo "========================================="
echo "TEST-006: E2E Test Execution"
echo "========================================="
echo ""
echo "Starting all 10 test agents in parallel..."
echo "Estimated completion time: 2-3 hours"
echo ""

# Start timestamp
START_TIME=$(date +%s)

# Run all agents in parallel
docker-compose -f planning_docs/TEST-006_docker_compose.yml up \
  agent-install \
  agent-mcp-memory \
  agent-mcp-code \
  agent-mcp-advanced \
  agent-cli-core \
  agent-cli-management \
  agent-code-search \
  agent-features \
  agent-ui-config \
  agent-quality

# Capture exit code
EXIT_CODE=$?

# End timestamp
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
MINUTES=$((DURATION / 60))
SECONDS=$((DURATION % 60))

echo ""
echo "========================================="
echo "Test Execution Complete"
echo "========================================="
echo "Duration: ${MINUTES}m ${SECONDS}s"
echo "Exit Code: $EXIT_CODE"
echo ""

if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ All agents completed successfully"
else
    echo "⚠️  Some agents reported failures (this is expected - collecting bugs)"
fi

echo ""
echo "Results saved to Docker volumes:"
echo "  - agent_install_results:/test_results"
echo "  - agent_mcp_memory_results:/test_results"
echo "  - agent_mcp_code_results:/test_results"
echo "  - agent_mcp_advanced_results:/test_results"
echo "  - agent_cli_core_results:/test_results"
echo "  - agent_cli_management_results:/test_results"
echo "  - agent_code_search_results:/test_results"
echo "  - agent_features_results:/test_results"
echo "  - agent_ui_config_results:/test_results"
echo "  - agent_quality_results:/test_results"
echo ""
echo "Next steps:"
echo "  1. Run coordinator to aggregate results: docker-compose -f planning_docs/TEST-006_docker_compose.yml up orchestrator"
echo "  2. View consolidated report: cat planning_docs/results/E2E_TEST_REPORT.md"
echo ""

exit $EXIT_CODE
