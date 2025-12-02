#!/usr/bin/env python3
"""
Demo script to show how the Coordinator aggregates results

Creates sample test results and demonstrates:
1. Result collection from multiple agents
2. Bug deduplication
3. Production readiness assessment
4. Report generation
"""

import sys
import json
import tempfile
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from testing.orchestrator.coordinator import TestCoordinator


def create_sample_results(results_dir: Path):
    """Create sample agent results for demonstration"""

    # Agent 1: Installation tests (mostly passed)
    agent1 = {
        "agent_id": "agent-install",
        "section": "installation",
        "start_time": "2025-11-20T10:00:00",
        "end_time": "2025-11-20T10:45:00",
        "tests": [
            {"test_id": "INST-001", "status": "MANUAL_REQUIRED"},
            {"test_id": "INST-002", "status": "PASS"},
            {"test_id": "INST-003", "status": "PASS"},
            {"test_id": "INST-004", "status": "PASS"},
            {"test_id": "INST-005", "status": "FAIL"},
            {"test_id": "INST-006", "status": "PASS"},
        ],
        "bugs_found": [
            {
                "id": "BUG-DOCKER-001",
                "severity": "HIGH",
                "description": "Qdrant container not accessible at localhost:6333",
                "impact": "Installation fails when Docker is not running",
                "test_id": "INST-005",
            }
        ],
        "summary": {
            "total_tests": 6,
            "passed": 4,
            "failed": 1,
            "skipped": 0,
            "manual_required": 1,
            "errors": 0,
            "pass_rate": 80.0,
            "bugs_found": 1,
        },
    }

    # Agent 2: MCP Memory tests
    agent2 = {
        "agent_id": "agent-mcp-memory",
        "section": "mcp-memory",
        "start_time": "2025-11-20T10:45:00",
        "end_time": "2025-11-20T11:45:00",
        "tests": [
            {"test_id": "MCP-001", "status": "MANUAL_REQUIRED"},
            {"test_id": "MCP-002", "status": "MANUAL_REQUIRED"},
            {"test_id": "MCP-003", "status": "MANUAL_REQUIRED"},
        ],
        "bugs_found": [],
        "summary": {
            "total_tests": 3,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "manual_required": 3,
            "errors": 0,
            "pass_rate": 0.0,
            "bugs_found": 0,
        },
    }

    # Agent 3: CLI tests (some failures)
    agent3 = {
        "agent_id": "agent-cli-core",
        "section": "cli-core",
        "start_time": "2025-11-20T10:45:00",
        "end_time": "2025-11-20T11:45:00",
        "tests": [
            {"test_id": "CLI-001", "status": "PASS"},
            {"test_id": "CLI-002", "status": "PASS"},
            {"test_id": "CLI-003", "status": "PASS"},
            {"test_id": "CLI-004", "status": "MANUAL_REQUIRED"},
            {"test_id": "CLI-005", "status": "PASS"},
            {"test_id": "CLI-006", "status": "MANUAL_REQUIRED"},
            {"test_id": "CLI-007", "status": "PASS"},
            {"test_id": "CLI-008", "status": "MANUAL_REQUIRED"},
        ],
        "bugs_found": [],
        "summary": {
            "total_tests": 8,
            "passed": 5,
            "failed": 0,
            "skipped": 0,
            "manual_required": 3,
            "errors": 0,
            "pass_rate": 100.0,
            "bugs_found": 0,
        },
    }

    # Agent 4: Code search tests (found bug also found by agent 5)
    agent4 = {
        "agent_id": "agent-code-search",
        "section": "code-search",
        "start_time": "2025-11-20T11:00:00",
        "end_time": "2025-11-20T12:30:00",
        "tests": [
            {"test_id": "CODE-001", "status": "FAIL"},
            {"test_id": "CODE-002", "status": "MANUAL_REQUIRED"},
            {"test_id": "CODE-003", "status": "FAIL"},
        ],
        "bugs_found": [
            {
                "id": "BUG-INDEX-001",
                "severity": "MEDIUM",
                "description": "Python parser fallback produces warnings",
                "impact": "Warnings in logs during indexing",
                "test_id": "CODE-001",
            },
            {
                "id": "BUG-INDEX-002",
                "severity": "MEDIUM",
                "description": "Code indexer extracts zero semantic units for empty files",
                "impact": "Empty files indexed but not searchable",
                "test_id": "CODE-003",
            },
        ],
        "summary": {
            "total_tests": 3,
            "passed": 0,
            "failed": 2,
            "skipped": 0,
            "manual_required": 1,
            "errors": 0,
            "pass_rate": 0.0,
            "bugs_found": 2,
        },
    }

    # Agent 5: Features tests (found same bug as agent 4)
    agent5 = {
        "agent_id": "agent-features",
        "section": "features",
        "start_time": "2025-11-20T12:00:00",
        "end_time": "2025-11-20T13:00:00",
        "tests": [
            {"test_id": "MEM-001", "status": "MANUAL_REQUIRED"},
            {"test_id": "MEM-002", "status": "MANUAL_REQUIRED"},
            {"test_id": "PROJ-001", "status": "MANUAL_REQUIRED"},
        ],
        "bugs_found": [
            {
                "id": "BUG-INDEX-001",  # Duplicate!
                "severity": "LOW",  # Different severity
                "description": "Python parser fallback produces warnings",
                "impact": "Warnings in logs during indexing",
                "test_id": "MEM-001",
            }
        ],
        "summary": {
            "total_tests": 3,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "manual_required": 3,
            "errors": 0,
            "pass_rate": 0.0,
            "bugs_found": 1,
        },
    }

    # Save all results
    results = [agent1, agent2, agent3, agent4, agent5]
    for result in results:
        filename = f"{result['agent_id']}_results.json"
        with open(results_dir / filename, "w") as f:
            json.dump(result, f, indent=2)

    print(f"Created {len(results)} sample agent results in {results_dir}")


def main():
    """Demonstrate coordinator functionality"""
    print("=" * 80)
    print("E2E Testing Coordinator Demonstration")
    print("=" * 80 + "\n")

    with tempfile.TemporaryDirectory() as temp_dir:
        results_dir = Path(temp_dir) / "results"
        results_dir.mkdir()

        # Create sample results
        create_sample_results(results_dir)

        # Run coordinator
        print("\n" + "=" * 80)
        print("Running Coordinator...")
        print("=" * 80 + "\n")

        coordinator = TestCoordinator(results_dir=str(results_dir))
        coordinator.collect_results()
        coordinator.calculate_summary()
        coordinator.assess_production_readiness()

        # Display results
        summary = coordinator.final_report["summary"]
        readiness = coordinator.final_report["production_readiness"]

        print("\n" + "=" * 80)
        print("SUMMARY STATISTICS")
        print("=" * 80)
        print(f"Total Tests:        {summary['total_tests']}")
        print(f"Automated Tests:    {summary['automated_tests']}")
        print(f"Manual Required:    {summary['tests_manual_required']}")
        print(f"Passed:             {summary['tests_passed']}")
        print(f"Failed:             {summary['tests_failed']}")
        print(f"Errors:             {summary['tests_error']}")
        print(f"Pass Rate:          {summary['pass_rate']:.1f}%")

        print("\n" + "=" * 80)
        print("BUGS FOUND")
        print("=" * 80)
        print(f"Total Unique Bugs:  {summary['total_bugs_found']}")
        print(f"Critical:           {summary['critical_bugs']}")
        print(f"High:               {summary['high_bugs']}")
        print(f"Medium:             {summary['medium_bugs']}")
        print(f"Low:                {summary['low_bugs']}")

        print("\n" + "=" * 80)
        print("BUG DETAILS (Demonstrating Deduplication)")
        print("=" * 80)
        for bug in coordinator.consolidated_bugs:
            print(f"\n{bug['id']} [{bug['severity']}]")
            print(f"  Description: {bug['description']}")
            print(f"  Found by: {', '.join(bug['found_by_agents'])}")
            if len(bug["found_by_agents"]) > 1:
                print(
                    f"  ⚠️  DEDUPLICATED: Found by {len(bug['found_by_agents'])} agents"
                )

        print("\n" + "=" * 80)
        print("PRODUCTION READINESS")
        print("=" * 80)
        print(f"Ready:              {readiness['ready']}")
        print(f"Readiness Score:    {readiness['readiness_score']}/100")
        print(f"Recommendation:     {readiness['recommendation']}")

        if readiness.get("blockers"):
            print("\nBlockers:")
            for blocker in readiness["blockers"]:
                print(f"  - {blocker}")

        print("\n" + "=" * 80)
        print("CRITERIA CHECKLIST")
        print("=" * 80)
        for criterion, met in readiness["criteria"].items():
            status = "✅" if met else "❌"
            print(f"{status} {criterion.replace('_', ' ').title()}")

        # Generate and save report
        output_dir = Path(temp_dir) / "final_results"
        output_dir.mkdir()
        coordinator.final_report["test_session"]["total_agents"] = len(
            coordinator.agent_results
        )
        coordinator.save_results(output_dir=str(output_dir))

        # Show report preview
        print("\n" + "=" * 80)
        print("MARKDOWN REPORT PREVIEW (first 1000 chars)")
        print("=" * 80)
        report_file = output_dir / "E2E_TEST_REPORT.md"
        with open(report_file, "r") as f:
            report_content = f.read()
            print(report_content[:1000])
            print("...")
            print(f"\nFull report saved to: {report_file}")

        print("\n" + "=" * 80)
        print("✅ DEMONSTRATION COMPLETE")
        print("=" * 80)


if __name__ == "__main__":
    main()
