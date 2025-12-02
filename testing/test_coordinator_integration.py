#!/usr/bin/env python3
"""
Integration test for TestCoordinator

Tests:
1. Result collection from multiple agents
2. Bug deduplication
3. Summary calculation
4. Production readiness assessment
5. Report generation
"""

import json
import tempfile
from pathlib import Path
from datetime import datetime
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from testing.orchestrator.coordinator import TestCoordinator


def create_mock_agent_results():
    """Create mock agent result files for testing"""

    # Agent 1: Installation tests - found critical bug
    agent1 = {
        "agent_id": "agent-install",
        "section": "installation",
        "start_time": datetime.now().isoformat(),
        "end_time": datetime.now().isoformat(),
        "tests": [
            {"test_id": "INST-001", "status": "PASS"},
            {"test_id": "INST-002", "status": "FAIL"},
            {"test_id": "INST-003", "status": "PASS"},
        ],
        "bugs_found": [
            {
                "id": "BUG-CRITICAL-001",
                "severity": "CRITICAL",
                "description": "ModuleNotFoundError in git_index_command.py",
                "impact": "CLI completely broken",
                "test_id": "INST-002",
            }
        ],
        "summary": {
            "total_tests": 3,
            "passed": 2,
            "failed": 1,
            "skipped": 0,
            "manual_required": 0,
            "errors": 0,
            "pass_rate": 66.67,
            "bugs_found": 1,
        },
    }

    # Agent 2: MCP tests - found same critical bug + new high bug
    agent2 = {
        "agent_id": "agent-mcp-memory",
        "section": "mcp_tools",
        "start_time": datetime.now().isoformat(),
        "end_time": datetime.now().isoformat(),
        "tests": [
            {"test_id": "MCP-001", "status": "PASS"},
            {"test_id": "MCP-002", "status": "FAIL"},
            {"test_id": "MCP-003", "status": "PASS"},
            {"test_id": "MCP-004", "status": "PASS"},
        ],
        "bugs_found": [
            {
                "id": "BUG-CRITICAL-001",
                "severity": "CRITICAL",
                "description": "ModuleNotFoundError in git_index_command.py",
                "impact": "CLI completely broken",
                "test_id": "MCP-002",
            },
            {
                "id": "BUG-NEW-001",
                "severity": "HIGH",
                "description": "retrieve_memories returns 'results' instead of 'memories'",
                "impact": "API inconsistency",
                "test_id": "MCP-003",
            },
        ],
        "summary": {
            "total_tests": 4,
            "passed": 3,
            "failed": 1,
            "skipped": 0,
            "manual_required": 0,
            "errors": 0,
            "pass_rate": 75.0,
            "bugs_found": 2,
        },
    }

    # Agent 3: Code tests - clean pass
    agent3 = {
        "agent_id": "agent-code-search",
        "section": "code_search",
        "start_time": datetime.now().isoformat(),
        "end_time": datetime.now().isoformat(),
        "tests": [
            {"test_id": "CODE-001", "status": "PASS"},
            {"test_id": "CODE-002", "status": "PASS"},
        ],
        "bugs_found": [],
        "summary": {
            "total_tests": 2,
            "passed": 2,
            "failed": 0,
            "skipped": 0,
            "manual_required": 0,
            "errors": 0,
            "pass_rate": 100.0,
            "bugs_found": 0,
        },
    }

    return [agent1, agent2, agent3]


def test_coordinator():
    """Test coordinator with mock data"""

    print("\n" + "=" * 80)
    print("TEST: TestCoordinator Integration")
    print("=" * 80 + "\n")

    # Create temporary directories for test
    with tempfile.TemporaryDirectory() as tmpdir:
        results_dir = Path(tmpdir) / "results"
        output_dir = Path(tmpdir) / "final_results"
        results_dir.mkdir()

        # Write mock agent results
        mock_results = create_mock_agent_results()
        for agent_result in mock_results:
            result_file = results_dir / f"{agent_result['agent_id']}_results.json"
            with open(result_file, "w") as f:
                json.dump(agent_result, f, indent=2)
            print(f"✓ Created mock result: {result_file.name}")

        print("\n--- Testing Coordinator ---\n")

        # Initialize coordinator
        coordinator = TestCoordinator(results_dir=str(results_dir))

        # Test 1: Collect results
        print("Test 1: Collecting results from agents...")
        coordinator.collect_results()
        assert (
            len(coordinator.agent_results) == 3
        ), f"Expected 3 agents, got {len(coordinator.agent_results)}"
        print(f"✓ Collected {len(coordinator.agent_results)} agent results")

        # Test 2: Bug deduplication
        print("\nTest 2: Verifying bug deduplication...")
        # BUG-CRITICAL-001 appears in both agent1 and agent2, should be deduplicated
        bug_ids = [b["id"] for b in coordinator.consolidated_bugs]
        assert "BUG-CRITICAL-001" in bug_ids, "Critical bug not found"
        assert "BUG-NEW-001" in bug_ids, "New bug not found"

        # Should have 2 unique bugs (BUG-CRITICAL-001 + BUG-NEW-001)
        assert (
            len(coordinator.consolidated_bugs) == 2
        ), f"Expected 2 unique bugs, got {len(coordinator.consolidated_bugs)}"

        # Check that BUG-CRITICAL-001 has both agents listed
        critical_bug = next(
            b for b in coordinator.consolidated_bugs if b["id"] == "BUG-CRITICAL-001"
        )
        assert (
            len(critical_bug["found_by_agents"]) == 2
        ), "Critical bug should be found by 2 agents"
        assert "agent-install" in critical_bug["found_by_agents"]
        assert "agent-mcp-memory" in critical_bug["found_by_agents"]
        print("✓ Deduplication working: 3 bug reports → 2 unique bugs")
        print(
            f"  - BUG-CRITICAL-001 found by {len(critical_bug['found_by_agents'])} agents"
        )

        # Test 3: Summary calculation
        print("\nTest 3: Calculating summary statistics...")
        coordinator.calculate_summary()
        summary = coordinator.final_report["summary"]

        # Verify counts
        assert (
            summary["total_tests"] == 9
        ), f"Expected 9 total tests, got {summary['total_tests']}"
        assert (
            summary["tests_passed"] == 7
        ), f"Expected 7 passed, got {summary['tests_passed']}"
        assert (
            summary["tests_failed"] == 2
        ), f"Expected 2 failed, got {summary['tests_failed']}"
        assert (
            summary["total_bugs_found"] == 2
        ), f"Expected 2 bugs, got {summary['total_bugs_found']}"
        assert (
            summary["critical_bugs"] == 1
        ), f"Expected 1 critical bug, got {summary['critical_bugs']}"
        assert (
            summary["high_bugs"] == 1
        ), f"Expected 1 high bug, got {summary['high_bugs']}"

        print("✓ Summary calculated correctly:")
        print(f"  - Total tests: {summary['total_tests']}")
        print(f"  - Passed: {summary['tests_passed']} ({summary['pass_rate']:.1f}%)")
        print(f"  - Failed: {summary['tests_failed']}")
        print(f"  - Bugs: {summary['total_bugs_found']} (1 CRITICAL, 1 HIGH)")

        # Test 4: Production readiness assessment
        print("\nTest 4: Assessing production readiness...")
        coordinator.assess_production_readiness()
        readiness = coordinator.final_report["production_readiness"]

        # With 1 critical bug, should NOT be production ready
        assert not readiness[
            "ready"
        ], "Should not be production ready with critical bug"
        assert "zero_critical_bugs" in readiness["criteria"]
        assert not readiness["criteria"][
            "zero_critical_bugs"
        ], "Should fail zero_critical_bugs criterion"

        print("✓ Production readiness assessed:")
        print(f"  - Ready: {readiness['ready']}")
        print(f"  - Score: {readiness['readiness_score']}/100")
        print(f"  - Blockers: {len(readiness['blockers'])}")
        for blocker in readiness["blockers"]:
            print(f"    • {blocker}")

        # Test 5: Report generation
        print("\nTest 5: Generating reports...")
        coordinator.save_results(output_dir=str(output_dir))

        # Verify files created
        json_report = output_dir / "consolidated_report.json"
        md_report = output_dir / "E2E_TEST_REPORT.md"
        agents_dir = output_dir / "agents"

        assert json_report.exists(), "JSON report not created"
        assert md_report.exists(), "Markdown report not created"
        assert agents_dir.exists(), "Agents directory not created"
        assert len(list(agents_dir.iterdir())) == 3, "Should have 3 agent result files"

        print("✓ Reports generated successfully:")
        print(f"  - JSON: {json_report.name}")
        print(f"  - Markdown: {md_report.name}")
        print(f"  - Agent files: {len(list(agents_dir.iterdir()))}")

        # Show markdown report excerpt
        with open(md_report, "r") as f:
            md_content = f.read()

        print("\n--- Markdown Report Preview ---\n")
        print(md_content[:800] + "...\n")

        print("\n" + "=" * 80)
        print("✅ ALL COORDINATOR TESTS PASSED")
        print("=" * 80 + "\n")

        return 0


if __name__ == "__main__":
    try:
        exit_code = test_coordinator()
        sys.exit(exit_code)
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}\n")
        import traceback

        traceback.print_exc()
        sys.exit(1)
