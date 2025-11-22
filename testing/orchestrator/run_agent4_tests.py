#!/usr/bin/env python3
"""
Quick test runner for Agent 4 test implementations
Demonstrates usage and validates test infrastructure
"""

import sys
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from testing.orchestrator.test_executor import TestExecutor


def main():
    """Run Agent 4 tests and display results"""

    print("=" * 80)
    print("TEST-006 Agent 4 Test Runner")
    print("Performance, Security, Error Handling, Configuration Tests")
    print("=" * 80)
    print()

    executor = TestExecutor(project_root=str(project_root))

    # Test groups
    test_groups = {
        "Performance Tests": ["PERF-001", "PERF-002", "PERF-003"],
        "Security Tests": ["SEC-001", "SEC-002", "SEC-003"],
        "Error Handling Tests": ["ERR-001", "ERR-002", "ERR-003"],
        "Configuration Tests": ["CONFIG-001", "CONFIG-002", "CONFIG-003"],
    }

    all_results = []
    total_pass = 0
    total_fail = 0
    total_error = 0
    total_bugs = 0

    for group_name, test_ids in test_groups.items():
        print(f"\n{'='*80}")
        print(f"{group_name}")
        print(f"{'='*80}")

        for test_id in test_ids:
            print(f"\n[{test_id}] Running...")

            try:
                result = executor.execute_test(test_id)
                all_results.append(result)

                status = result['status']
                status_emoji = {
                    'PASS': '✅',
                    'FAIL': '❌',
                    'ERROR': '⚠️',
                    'MANUAL_REQUIRED': '👤'
                }.get(status, '❓')

                print(f"{status_emoji} [{test_id}] {status}")
                print(f"   Notes: {result['notes'][:200]}...")

                if result.get('bugs_found'):
                    print(f"   🐛 Bugs Found: {len(result['bugs_found'])}")
                    for bug in result['bugs_found']:
                        print(f"      - [{bug['severity']}] {bug['description'][:80]}")
                    total_bugs += len(result['bugs_found'])

                # Update counters
                if status == 'PASS':
                    total_pass += 1
                elif status == 'FAIL':
                    total_fail += 1
                elif status == 'ERROR':
                    total_error += 1

            except Exception as e:
                print(f"❌ [{test_id}] EXCEPTION: {str(e)}")
                total_error += 1

    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    print(f"Total Tests: {len(all_results)}")
    print(f"✅ Passed: {total_pass}")
    print(f"❌ Failed: {total_fail}")
    print(f"⚠️  Errors: {total_error}")
    print(f"🐛 Bugs Found: {total_bugs}")
    print()

    # Save detailed results
    results_file = project_root / "testing" / "results" / "agent4_results.json"
    results_file.parent.mkdir(parents=True, exist_ok=True)

    with open(results_file, 'w') as f:
        json.dump({
            'summary': {
                'total': len(all_results),
                'passed': total_pass,
                'failed': total_fail,
                'errors': total_error,
                'bugs_found': total_bugs
            },
            'results': all_results
        }, f, indent=2, default=str)

    print(f"📊 Detailed results saved to: {results_file}")
    print()

    # Exit code based on results
    if total_fail > 0 or total_error > 0:
        print("❌ Some tests failed or encountered errors")
        return 1
    elif total_pass > 0:
        print("✅ All tests passed!")
        return 0
    else:
        print("⚠️  No tests were executed")
        return 2


if __name__ == "__main__":
    sys.exit(main())
