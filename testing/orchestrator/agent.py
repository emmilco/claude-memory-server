#!/usr/bin/env python3
"""
E2E Testing Agent

Executes assigned test section within a Docker container.
Reports results back to orchestrator.
"""

import os
import sys
import json
import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

# Import TestExecutor for actual test execution
try:
    from testing.orchestrator.test_executor import TestExecutor
except ImportError:
    # Fallback for when running directly
    sys.path.insert(0, '/app')
    from testing.orchestrator.test_executor import TestExecutor

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/test_logs/agent.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class TestAgent:
    """Individual testing agent that runs assigned test scenarios"""

    def __init__(self, agent_id: str, section: str, assignments_file: str):
        self.agent_id = agent_id or os.getenv('AGENT_ID', 'unknown')
        self.section = section
        self.assignments_file = assignments_file
        self.results = {
            'agent_id': self.agent_id,
            'section': section,
            'start_time': datetime.now().isoformat(),
            'tests': [],
            'bugs_found': [],
            'summary': {}
        }

        # Load test assignments
        with open(assignments_file, 'r') as f:
            self.assignments = json.load(f)

        self.section_config = self.assignments['test_sections'].get(section, {})
        if not self.section_config:
            raise ValueError(f"Unknown test section: {section}")

        # Initialize TestExecutor
        self.executor = TestExecutor(project_root='/app')

        logger.info(f"Agent {self.agent_id} initialized for section: {section}")
        logger.info(f"Assigned tests: {self.section_config.get('test_ids', [])}")

    def run_tests(self) -> Dict[str, Any]:
        """Execute all assigned tests"""
        logger.info(f"Starting test execution for section: {self.section}")

        test_ids = self.section_config.get('test_ids', [])
        for test_id in test_ids:
            logger.info(f"Running test: {test_id}")
            result = self.run_single_test(test_id)
            self.results['tests'].append(result)

        self.results['end_time'] = datetime.now().isoformat()
        self.calculate_summary()
        self.save_results()

        return self.results

    def run_single_test(self, test_id: str) -> Dict[str, Any]:
        """
        Run a single test scenario using TestExecutor

        Uses the TestExecutor class to:
        1. Look up test details and route to appropriate handler
        2. Execute the test steps (automated or manual)
        3. Capture results and any bugs found
        4. Return structured test result
        """
        logger.info(f"  Executing test {test_id}...")

        try:
            # Execute the test using TestExecutor
            test_result = self.executor.execute_test(test_id)

            # Collect bugs from the test result
            if test_result.get('bugs_found'):
                for bug in test_result['bugs_found']:
                    # Add bug to agent's global bug list if not already there
                    bug_id = bug.get('bug_id') or bug.get('id')
                    if not any(b.get('id') == bug_id or b.get('bug_id') == bug_id
                              for b in self.results['bugs_found']):
                        # Normalize bug structure
                        normalized_bug = {
                            'id': bug_id,
                            'severity': bug.get('severity', 'UNKNOWN'),
                            'description': bug.get('description', 'No description'),
                            'impact': bug.get('impact', 'Unknown'),
                            'test_id': test_id,
                            'found_by': self.agent_id
                        }
                        self.results['bugs_found'].append(normalized_bug)

            return test_result

        except Exception as e:
            logger.error(f"  Test {test_id} failed with exception: {e}", exc_info=True)
            return {
                'test_id': test_id,
                'start_time': datetime.now().isoformat(),
                'status': 'ERROR',
                'notes': f'Unexpected error during test execution: {str(e)}',
                'bugs_found': [],
                'end_time': datetime.now().isoformat()
            }

    def calculate_summary(self):
        """Calculate summary statistics"""
        total = len(self.results['tests'])
        passed = len([t for t in self.results['tests'] if t['status'] == 'PASS'])
        failed = len([t for t in self.results['tests'] if t['status'] == 'FAIL'])
        skipped = len([t for t in self.results['tests'] if t['status'] == 'SKIPPED'])
        manual = len([t for t in self.results['tests'] if t['status'] == 'MANUAL_REQUIRED'])
        errors = len([t for t in self.results['tests'] if t['status'] == 'ERROR'])

        # Count bugs by severity
        bugs_by_severity = {
            'CRITICAL': len([b for b in self.results['bugs_found'] if b.get('severity') == 'CRITICAL']),
            'HIGH': len([b for b in self.results['bugs_found'] if b.get('severity') == 'HIGH']),
            'MEDIUM': len([b for b in self.results['bugs_found'] if b.get('severity') == 'MEDIUM']),
            'LOW': len([b for b in self.results['bugs_found'] if b.get('severity') == 'LOW']),
        }

        self.results['summary'] = {
            'total_tests': total,
            'passed': passed,
            'failed': failed,
            'skipped': skipped,
            'manual_required': manual,
            'errors': errors,
            'pass_rate': (passed / total * 100) if total > 0 else 0,
            'bugs_found': len(self.results['bugs_found']),
            'bugs_by_severity': bugs_by_severity,
            'estimated_duration_minutes': self.section_config.get('estimated_duration_minutes', 0),
            'critical_bugs_verified': self.section_config.get('critical_bugs_to_verify', [])
        }

    def save_results(self):
        """Save results to file"""
        output_file = f'/test_results/{self.agent_id}_results.json'
        with open(output_file, 'w') as f:
            json.dump(self.results, f, indent=2)

        logger.info(f"Results saved to {output_file}")
        logger.info(f"Summary: {self.results['summary']}")


def main():
    parser = argparse.ArgumentParser(description='E2E Testing Agent')
    parser.add_argument('--section', required=True, help='Test section to execute')
    parser.add_argument('--assignments', default='/app/test_assignments.json',
                       help='Path to test assignments JSON file')
    args = parser.parse_args()

    try:
        agent_id = os.getenv('AGENT_ID', 'unknown')
        agent = TestAgent(agent_id, args.section, args.assignments)
        results = agent.run_tests()

        # Exit with non-zero if any tests failed
        if results['summary']['failed'] > 0:
            sys.exit(1)

    except Exception as e:
        logger.error(f"Agent failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
