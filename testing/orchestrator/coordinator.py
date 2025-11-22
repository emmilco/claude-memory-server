#!/usr/bin/env python3
"""
E2E Testing Coordinator

Aggregates results from all testing agents and generates final report.
"""

import os
import json
import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any
from collections import defaultdict

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TestCoordinator:
    """Coordinates and aggregates results from multiple testing agents"""

    def __init__(self, results_dir: str = '/results'):
        self.results_dir = Path(results_dir)
        self.agent_results = []
        self.consolidated_bugs = []
        self.final_report = {
            'test_session': {
                'date': datetime.now().isoformat(),
                'version': '4.0',
                'total_agents': 0
            },
            'summary': {},
            'agent_results': [],
            'bugs': [],
            'production_readiness': {}
        }

    def collect_results(self):
        """Collect results from all agent containers"""
        logger.info(f"Collecting results from {self.results_dir}")

        # Look for JSON result files in the results directory
        # They can be directly in the results_dir or in subdirectories
        result_files = []

        if self.results_dir.exists():
            # Check for files directly in results_dir
            for item in self.results_dir.iterdir():
                if item.is_file() and item.name.endswith('_results.json'):
                    result_files.append(item)
                elif item.is_dir():
                    # Check in subdirectories (agent-specific volumes)
                    for subitem in item.iterdir():
                        if subitem.is_file() and subitem.name.endswith('_results.json'):
                            result_files.append(subitem)
        else:
            logger.warning(f"Results directory {self.results_dir} does not exist")
            return

        # Load each result file
        for result_file in result_files:
            try:
                logger.info(f"Loading results from {result_file}")
                with open(result_file, 'r') as f:
                    agent_result = json.load(f)
                    self.agent_results.append(agent_result)
                    self.consolidate_bugs(agent_result)
            except Exception as e:
                logger.error(f"Failed to load {result_file}: {e}", exc_info=True)

        self.final_report['test_session']['total_agents'] = len(self.agent_results)
        logger.info(f"Collected results from {len(self.agent_results)} agents")

        if len(self.agent_results) == 0:
            logger.warning("No agent results found - check that tests have been executed")

    def consolidate_bugs(self, agent_result: Dict[str, Any]):
        """
        Extract and consolidate bugs from agent results with deduplication

        Deduplication strategy:
        1. First try exact ID match (e.g., BUG-NEW-001)
        2. If no ID, try matching by description similarity (exact match)
        3. Merge findings from multiple agents when duplicates found
        """
        for bug in agent_result.get('bugs_found', []):
            # Normalize bug ID
            bug_id = bug.get('id') or bug.get('bug_id')
            description = bug.get('description', '').strip()

            # Try to find existing bug by ID or description
            existing = None
            if bug_id:
                existing = next((b for b in self.consolidated_bugs
                               if (b.get('id') == bug_id or b.get('bug_id') == bug_id)), None)

            # If no ID match, try description match (exact)
            if not existing and description:
                existing = next((b for b in self.consolidated_bugs
                               if b.get('description', '').strip() == description), None)

            if existing:
                # Merge findings from multiple agents
                found_by = existing.setdefault('found_by_agents', [])
                agent_id = agent_result['agent_id']
                if agent_id not in found_by:
                    found_by.append(agent_id)

                # Merge test IDs where bug was found
                test_ids = existing.setdefault('found_in_tests', [])
                test_id = bug.get('test_id')
                if test_id and test_id not in test_ids:
                    test_ids.append(test_id)

                # Keep the highest severity if multiple severities reported
                if self._severity_rank(bug.get('severity')) > self._severity_rank(existing.get('severity')):
                    existing['severity'] = bug.get('severity')

                logger.debug(f"Merged duplicate bug {bug_id or description[:50]} from agent {agent_id}")
            else:
                # New bug - add to consolidated list
                normalized_bug = {
                    'id': bug_id,
                    'severity': bug.get('severity', 'UNKNOWN'),
                    'description': description,
                    'impact': bug.get('impact', 'Unknown'),
                    'test_id': bug.get('test_id'),
                    'found_by_agents': [agent_result['agent_id']],
                    'found_in_tests': [bug.get('test_id')] if bug.get('test_id') else []
                }
                self.consolidated_bugs.append(normalized_bug)

    def _severity_rank(self, severity: str) -> int:
        """Return numeric rank for severity (higher = more severe)"""
        severity_map = {
            'CRITICAL': 4,
            'HIGH': 3,
            'MEDIUM': 2,
            'LOW': 1,
            'UNKNOWN': 0
        }
        return severity_map.get(severity, 0)

    def calculate_summary(self):
        """Calculate overall summary statistics"""
        total_tests = 0
        total_passed = 0
        total_failed = 0
        total_skipped = 0
        total_manual = 0
        total_errors = 0

        for agent in self.agent_results:
            summary = agent.get('summary', {})
            total_tests += summary.get('total_tests', 0)
            total_passed += summary.get('passed', 0)
            total_failed += summary.get('failed', 0)
            total_skipped += summary.get('skipped', 0)
            total_manual += summary.get('manual_required', 0)
            total_errors += summary.get('errors', 0)

        # Calculate automated test pass rate (excluding manual tests)
        automated_tests = total_tests - total_manual
        automated_passed = total_passed
        automated_pass_rate = (automated_passed / automated_tests * 100) if automated_tests > 0 else 0

        self.final_report['summary'] = {
            'total_tests': total_tests,
            'tests_passed': total_passed,
            'tests_failed': total_failed,
            'tests_skipped': total_skipped,
            'tests_manual_required': total_manual,
            'tests_error': total_errors,
            'automated_tests': automated_tests,
            'pass_rate': automated_pass_rate,
            'overall_pass_rate': (total_passed / total_tests * 100) if total_tests > 0 else 0,
            'total_bugs_found': len(self.consolidated_bugs),
            'critical_bugs': len([b for b in self.consolidated_bugs if b.get('severity') == 'CRITICAL']),
            'high_bugs': len([b for b in self.consolidated_bugs if b.get('severity') == 'HIGH']),
            'medium_bugs': len([b for b in self.consolidated_bugs if b.get('severity') == 'MEDIUM']),
            'low_bugs': len([b for b in self.consolidated_bugs if b.get('severity') == 'LOW'])
        }

        # Store bug catalog in final report
        self.final_report['bugs'] = self.consolidated_bugs

    def assess_production_readiness(self):
        """
        Assess whether system is production ready

        Production readiness criteria:
        1. Zero critical bugs
        2. Maximum 3 high-priority bugs
        3. Pass rate >= 95% (for automated tests)
        4. Zero test failures
        5. Zero test errors (unexpected exceptions)
        """
        summary = self.final_report['summary']

        critical_bugs = summary['critical_bugs']
        high_bugs = summary['high_bugs']
        medium_bugs = summary['medium_bugs']
        pass_rate = summary['pass_rate']
        failed = summary['tests_failed']
        errors = summary['tests_error']
        automated_tests = summary['automated_tests']

        # Individual criteria checks
        criteria = {
            'zero_critical_bugs': critical_bugs == 0,
            'max_3_high_bugs': high_bugs <= 3,
            'pass_rate_above_95': pass_rate >= 95.0,
            'zero_test_failures': failed == 0,
            'zero_test_errors': errors == 0,
            'sufficient_automated_coverage': automated_tests > 0
        }

        # Production readiness verdict
        is_ready = all(criteria.values())

        # Calculate readiness score (0-100)
        score_components = {
            'critical_bugs': 25 if criteria['zero_critical_bugs'] else 0,
            'high_bugs': 20 if criteria['max_3_high_bugs'] else max(0, 20 - (high_bugs - 3) * 5),
            'pass_rate': min(25, pass_rate / 4),
            'failures': 15 if criteria['zero_test_failures'] else max(0, 15 - failed * 3),
            'errors': 15 if criteria['zero_test_errors'] else max(0, 15 - errors * 3)
        }
        readiness_score = sum(score_components.values())

        self.final_report['production_readiness'] = {
            'ready': is_ready,
            'readiness_score': round(readiness_score, 1),
            'criteria': criteria,
            'recommendation': self.generate_recommendation(
                is_ready, critical_bugs, high_bugs, medium_bugs, pass_rate, failed, errors
            ),
            'blockers': self._identify_blockers(criteria, critical_bugs, high_bugs, failed, errors)
        }

    def _identify_blockers(self, criteria: Dict, critical: int, high: int, failed: int, errors: int) -> List[str]:
        """Identify specific blockers preventing production readiness"""
        blockers = []

        if not criteria['zero_critical_bugs']:
            blockers.append(f"{critical} critical bug(s) must be fixed")

        if not criteria['max_3_high_bugs']:
            blockers.append(f"{high} high-priority bugs found (max: 3)")

        if not criteria['pass_rate_above_95']:
            blockers.append("Pass rate below 95%")

        if not criteria['zero_test_failures']:
            blockers.append(f"{failed} test failure(s) must be resolved")

        if not criteria['zero_test_errors']:
            blockers.append(f"{errors} test error(s) must be fixed")

        return blockers

    def generate_recommendation(self, is_ready: bool, critical: int, high: int, medium: int,
                               pass_rate: float, failed: int, errors: int) -> str:
        """Generate detailed production readiness recommendation"""
        if is_ready:
            return "✅ READY FOR PRODUCTION - All quality criteria met. System passed comprehensive E2E testing."

        # Prioritize blockers by severity
        if critical > 0:
            return f"❌ BLOCKED - {critical} CRITICAL bug(s) must be fixed before release"

        if errors > 0:
            return f"❌ BLOCKED - {errors} test error(s) indicate system instability"

        if failed > 0:
            return f"❌ NOT READY - {failed} test failure(s) must be resolved before release"

        if high > 5:
            return f"⚠️ READY WITH CAUTION - {high} high-priority bugs found (recommend fixing {high - 3} before release)"

        if pass_rate < 90:
            return f"⚠️ NOT READY - Pass rate {pass_rate:.1f}% is below acceptable threshold (90% minimum, 95% target)"

        if high > 3:
            return f"⚠️ READY WITH MINOR ISSUES - {high} high-priority bugs, {medium} medium bugs. Consider fixes before release."

        return "✅ READY WITH ACCEPTABLE RISK - Minor issues found but within acceptable limits"

    def generate_markdown_report(self) -> str:
        """Generate comprehensive markdown summary report"""
        summary = self.final_report['summary']
        readiness = self.final_report['production_readiness']

        report = f"""# E2E Testing Report
## Claude Memory RAG Server v4.0

**Date:** {self.final_report['test_session']['date']}
**Total Agents:** {self.final_report['test_session']['total_agents']}

---

## Executive Summary

**Production Readiness:** {readiness['recommendation']}
**Readiness Score:** {readiness['readiness_score']}/100

"""
        # Show blockers if any
        if readiness.get('blockers'):
            report += "### Blockers\n"
            for blocker in readiness['blockers']:
                report += f"- ❌ {blocker}\n"
            report += "\n"

        report += f"""### Test Statistics
- **Total Tests:** {summary['total_tests']}
  - **Automated:** {summary['automated_tests']}
  - **Manual Required:** {summary['tests_manual_required']}
- **Results:**
  - **Passed:** {summary['tests_passed']} ({summary['pass_rate']:.1f}% of automated)
  - **Failed:** {summary['tests_failed']}
  - **Errors:** {summary['tests_error']}
  - **Skipped:** {summary['tests_skipped']}

### Bugs Found
- **Total:** {summary['total_bugs_found']}
- **Critical:** {summary['critical_bugs']} 🔴
- **High:** {summary['high_bugs']} 🟠
- **Medium:** {summary['medium_bugs']} 🟡
- **Low:** {summary['low_bugs']} 🟢

---

## Production Readiness Criteria

"""
        for criterion, met in readiness['criteria'].items():
            status = "✅" if met else "❌"
            report += f"- {status} {criterion.replace('_', ' ').title()}\n"

        report += f"\n---\n\n## Agent Results\n\n"

        for agent in self.agent_results:
            agent_summary = agent.get('summary', {})
            report += f"""### {agent['agent_id']} - {agent['section']}
- Tests: {agent_summary.get('total_tests', 0)}
- Passed: {agent_summary.get('passed', 0)}
- Failed: {agent_summary.get('failed', 0)}
- Errors: {agent_summary.get('errors', 0)}
- Manual: {agent_summary.get('manual_required', 0)}
- Pass Rate: {agent_summary.get('pass_rate', 0):.1f}%
- Bugs Found: {agent_summary.get('bugs_found', 0)}

"""

        report += f"\n---\n\n## Bugs Found\n\n"

        if len(self.consolidated_bugs) == 0:
            report += "✅ No bugs found during testing!\n\n"
        else:
            # Group bugs by severity
            bugs_by_severity = defaultdict(list)
            for bug in self.consolidated_bugs:
                bugs_by_severity[bug.get('severity', 'UNKNOWN')].append(bug)

            for severity in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'UNKNOWN']:
                bugs = bugs_by_severity.get(severity, [])
                if bugs:
                    severity_emoji = {
                        'CRITICAL': '🔴',
                        'HIGH': '🟠',
                        'MEDIUM': '🟡',
                        'LOW': '🟢',
                        'UNKNOWN': '⚪'
                    }
                    report += f"\n### {severity_emoji.get(severity, '')} {severity} Priority ({len(bugs)})\n\n"
                    for bug in bugs:
                        bug_id = bug.get('id', 'UNKNOWN')
                        description = bug.get('description', 'No description')
                        found_by = ', '.join(bug.get('found_by_agents', []))
                        found_in = ', '.join(bug.get('found_in_tests', []))
                        impact = bug.get('impact', 'Unknown')

                        report += f"- **{bug_id}:** {description}\n"
                        report += f"  - Found by: {found_by}\n"
                        if found_in:
                            report += f"  - Found in tests: {found_in}\n"
                        report += f"  - Impact: {impact}\n\n"

        report += f"\n---\n\n## Detailed Results\n\n"
        report += "See individual agent result files in `/final_results/agents/` for complete test details.\n"

        return report

    def save_results(self, output_dir: str = '/final_results'):
        """Save aggregated results"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Save JSON report
        json_file = output_path / 'consolidated_report.json'
        with open(json_file, 'w') as f:
            json.dump(self.final_report, f, indent=2)
        logger.info(f"JSON report saved to {json_file}")

        # Save Markdown report
        markdown_report = self.generate_markdown_report()
        md_file = output_path / 'E2E_TEST_REPORT.md'
        with open(md_file, 'w') as f:
            f.write(markdown_report)
        logger.info(f"Markdown report saved to {md_file}")

        # Save individual agent results
        agents_dir = output_path / 'agents'
        agents_dir.mkdir(exist_ok=True)
        for agent in self.agent_results:
            agent_file = agents_dir / f"{agent['agent_id']}_results.json"
            with open(agent_file, 'w') as f:
                json.dump(agent, f, indent=2)

        logger.info(f"All results saved to {output_dir}")

        # Print summary to console
        print("\n" + "="*80)
        print(markdown_report)
        print("="*80 + "\n")

    def run(self):
        """Execute coordination workflow"""
        logger.info("Starting test result coordination...")

        self.collect_results()
        self.calculate_summary()
        self.assess_production_readiness()
        self.save_results()

        logger.info("Coordination complete!")

        # Exit with status based on production readiness
        if not self.final_report['production_readiness']['ready']:
            logger.warning("System is NOT production ready")
            return 1
        else:
            logger.info("System is production ready!")
            return 0


def main():
    parser = argparse.ArgumentParser(description='E2E Testing Coordinator')
    parser.add_argument('--aggregate', action='store_true',
                       help='Aggregate results from all agents')
    parser.add_argument('--results-dir', default='/results',
                       help='Directory containing agent results')
    parser.add_argument('--output-dir', default='/final_results',
                       help='Directory for final aggregated results')
    args = parser.parse_args()

    try:
        coordinator = TestCoordinator(results_dir=args.results_dir)
        exit_code = coordinator.run()
        return exit_code

    except Exception as e:
        logger.error(f"Coordination failed: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    exit(main())
