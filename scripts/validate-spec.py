#!/usr/bin/env python3
"""
SPEC.md Validation Script

Validates that the normative YAML specification is compliant with all requirements.

Usage:
    python scripts/validate-spec.py
    python scripts/validate-spec.py --format json
    python scripts/validate-spec.py --verbose
"""

import sys
import yaml
import json
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime

# ANSI color codes
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
CYAN = '\033[96m'
BOLD = '\033[1m'
RESET = '\033[0m'


def print_header(text: str):
    """Print a colored header."""
    print(f"\n{BLUE}{BOLD}{'=' * 70}{RESET}")
    print(f"{BLUE}{BOLD}{text:^70}{RESET}")
    print(f"{BLUE}{BOLD}{'=' * 70}{RESET}\n")


def print_section(text: str):
    """Print a section header."""
    print(f"\n{CYAN}{BOLD}{text}{RESET}")
    print(f"{CYAN}{'-' * len(text)}{RESET}")


def load_spec() -> Dict:
    """Load YAML specification from SPEC.md."""
    spec_path = Path("SPEC.md")

    if not spec_path.exists():
        print(f"{RED}Error: SPEC.md not found{RESET}")
        sys.exit(1)

    content = spec_path.read_text()

    # Extract YAML block from markdown
    try:
        yaml_start = content.index('```yaml')
        yaml_end = content.index('```', yaml_start + 7)
        yaml_content = content[yaml_start + 7:yaml_end]

        spec = yaml.safe_load(yaml_content)
        return spec
    except ValueError as e:
        print(f"{RED}Error: Could not find YAML block in SPEC.md{RESET}")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"{RED}Error: Invalid YAML in SPEC.md: {e}{RESET}")
        sys.exit(1)


def validate_metadata(spec: Dict) -> Tuple[bool, List[str]]:
    """Validate metadata section."""
    issues = []

    required_fields = ['version', 'last_updated', 'status', 'purpose']
    for field in required_fields:
        if field not in spec.get('metadata', {}):
            issues.append(f"Missing required metadata field: {field}")

    return len(issues) == 0, issues


def validate_features(spec: Dict) -> Tuple[bool, List[str]]:
    """Validate features section."""
    issues = []

    features = spec.get('features', [])
    if not features:
        issues.append("No features defined in specification")
        return False, issues

    # Check for required fields in each feature
    required_feature_fields = ['id', 'name', 'description', 'priority', 'status', 'requirements']
    for feature in features:
        for field in required_feature_fields:
            if field not in feature:
                issues.append(f"Feature {feature.get('id', 'UNKNOWN')} missing field: {field}")

    return len(issues) == 0, issues


def validate_requirements(spec: Dict) -> Tuple[bool, Dict]:
    """Validate requirements and return detailed statistics."""
    issues = []
    stats = {
        'total': 0,
        'must': 0,
        'should': 0,
        'may': 0,
        'passing': 0,
        'failing': 0,
        'not_implemented': 0,
        'by_feature': {},
        'missing_tests': []
    }

    required_req_fields = ['id', 'type', 'spec', 'acceptance', 'current_status', 'test_refs']
    valid_types = ['MUST', 'SHOULD', 'MAY', 'MUST NOT']
    valid_statuses = ['passing', 'failing', 'not_implemented']

    features = spec.get('features', [])
    for feature in features:
        feature_id = feature.get('id', 'UNKNOWN')
        feature_stats = {
            'total': 0,
            'passing': 0,
            'failing': 0
        }

        requirements = feature.get('requirements', [])
        for req in requirements:
            stats['total'] += 1
            feature_stats['total'] += 1

            # Check required fields
            for field in required_req_fields:
                if field not in req:
                    issues.append(f"Requirement {req.get('id', 'UNKNOWN')} missing field: {field}")

            # Validate requirement type
            req_type = req.get('type', '')
            if req_type not in valid_types:
                issues.append(f"Requirement {req.get('id', 'UNKNOWN')} has invalid type: {req_type}")
            else:
                stats[req_type.lower()] = stats.get(req_type.lower(), 0) + 1

            # Validate status
            status = req.get('current_status', '')
            if status not in valid_statuses:
                issues.append(f"Requirement {req.get('id', 'UNKNOWN')} has invalid status: {status}")
            else:
                stats[status] = stats.get(status, 0) + 1
                if status == 'passing':
                    feature_stats['passing'] += 1
                elif status == 'failing':
                    feature_stats['failing'] += 1

            # Check test references
            test_refs = req.get('test_refs', [])
            if not test_refs:
                stats['missing_tests'].append(req.get('id', 'UNKNOWN'))
                issues.append(f"Requirement {req.get('id', 'UNKNOWN')} has no test references")

            # Validate acceptance criteria
            acceptance = req.get('acceptance', {})
            if not all(k in acceptance for k in ['given', 'when', 'then']):
                issues.append(f"Requirement {req.get('id', 'UNKNOWN')} missing acceptance criteria (given/when/then)")

        stats['by_feature'][feature_id] = feature_stats

    return len(issues) == 0, stats, issues


def check_test_files_exist(spec: Dict) -> Tuple[bool, List[str]]:
    """Check if referenced test files actually exist."""
    issues = []

    features = spec.get('features', [])
    for feature in features:
        requirements = feature.get('requirements', [])
        for req in requirements:
            test_refs = req.get('test_refs', [])
            for test_ref in test_refs:
                # Extract file path (before ::)
                test_file = test_ref.split('::')[0]
                test_path = Path(test_file)

                if not test_path.exists():
                    issues.append(f"Test file not found: {test_file} (referenced by {req.get('id', 'UNKNOWN')})")

    return len(issues) == 0, issues


def validate_compliance(spec: Dict) -> Tuple[bool, Dict]:
    """Validate compliance section matches actual requirements."""
    issues = []

    compliance = spec.get('compliance', {})
    req_summary = compliance.get('requirement_summary', {})

    # Count actual requirements
    actual_total = 0
    actual_must = 0
    actual_should = 0
    actual_passing = 0

    features = spec.get('features', [])
    for feature in features:
        requirements = feature.get('requirements', [])
        for req in requirements:
            actual_total += 1
            req_type = req.get('type', '')
            if req_type == 'MUST':
                actual_must += 1
            elif req_type == 'SHOULD':
                actual_should += 1

            if req.get('current_status') == 'passing':
                actual_passing += 1

    # Compare with claimed compliance
    claimed_total = req_summary.get('total_requirements', 0)
    claimed_must = req_summary.get('must_requirements', 0)
    claimed_should = req_summary.get('should_requirements', 0)
    claimed_passing = req_summary.get('passing_requirements', 0)

    discrepancies = {}
    if actual_total != claimed_total:
        discrepancies['total_requirements'] = {
            'claimed': claimed_total,
            'actual': actual_total
        }

    if actual_must != claimed_must:
        discrepancies['must_requirements'] = {
            'claimed': claimed_must,
            'actual': actual_must
        }

    if actual_should != claimed_should:
        discrepancies['should_requirements'] = {
            'claimed': claimed_should,
            'actual': actual_should
        }

    if actual_passing != claimed_passing:
        discrepancies['passing_requirements'] = {
            'claimed': claimed_passing,
            'actual': actual_passing
        }

    if discrepancies:
        for key, values in discrepancies.items():
            issues.append(f"Compliance mismatch for {key}: claimed {values['claimed']}, actual {values['actual']}")

    return len(discrepancies) == 0, discrepancies, issues


def display_results(spec: Dict, results: Dict, verbose: bool = False):
    """Display validation results."""
    print_header("SPEC.md Validation Results")

    # Metadata
    print_section("📋 Metadata")
    metadata = spec.get('metadata', {})
    print(f"  Version:      {metadata.get('version', 'N/A')}")
    print(f"  Last Updated: {metadata.get('last_updated', 'N/A')}")
    print(f"  Status:       {metadata.get('status', 'N/A')}")

    # Overall validation status
    print_section("✅ Validation Status")

    all_passed = True
    for check, result in results.items():
        if check == 'requirements':
            passed = result['passed']
            stats = result['stats']

            if passed:
                print(f"  {GREEN}✓{RESET} Requirements: All {stats['total']} requirements valid")
            else:
                print(f"  {RED}✗{RESET} Requirements: {len(result['issues'])} issues found")
                all_passed = False
        else:
            passed = result['passed']
            if passed:
                print(f"  {GREEN}✓{RESET} {check.title()}: Valid")
            else:
                print(f"  {RED}✗{RESET} {check.title()}: {len(result['issues'])} issues")
                all_passed = False

    # Requirement statistics
    if 'requirements' in results:
        print_section("📊 Requirement Statistics")
        stats = results['requirements']['stats']

        print(f"  Total Requirements: {stats['total']}")
        print(f"  ├─ MUST:            {stats.get('must', 0)}")
        print(f"  ├─ SHOULD:          {stats.get('should', 0)}")
        print(f"  └─ MAY:             {stats.get('may', 0)}")
        print()
        print(f"  Status Breakdown:")
        print(f"  ├─ Passing:         {GREEN}{stats.get('passing', 0)}{RESET}")
        print(f"  ├─ Failing:         {RED}{stats.get('failing', 0)}{RESET}")
        print(f"  └─ Not Implemented: {YELLOW}{stats.get('not_implemented', 0)}{RESET}")
        print()

        if stats['total'] > 0:
            compliance_pct = (stats.get('passing', 0) / stats['total']) * 100
            print(f"  Compliance: {compliance_pct:.1f}%")

        # Per-feature breakdown
        if verbose and stats['by_feature']:
            print_section("📦 Per-Feature Compliance")
            for feature_id, feature_stats in stats['by_feature'].items():
                total = feature_stats['total']
                passing = feature_stats['passing']
                pct = (passing / total * 100) if total > 0 else 0

                status_color = GREEN if pct == 100 else YELLOW if pct >= 80 else RED
                print(f"  {feature_id}: {status_color}{passing}/{total} ({pct:.0f}%){RESET}")

    # Issues
    if verbose:
        print_section("⚠️  Issues")
        total_issues = sum(len(r.get('issues', [])) for r in results.values())

        if total_issues == 0:
            print(f"  {GREEN}No issues found!{RESET}")
        else:
            for check, result in results.items():
                issues = result.get('issues', [])
                if issues:
                    print(f"\n  {check.title()}:")
                    for issue in issues[:10]:  # Limit to first 10
                        print(f"    - {issue}")
                    if len(issues) > 10:
                        print(f"    ... and {len(issues) - 10} more")

    # Compliance discrepancies
    if 'compliance' in results and results['compliance'].get('discrepancies'):
        print_section("⚠️  Compliance Discrepancies")
        for key, values in results['compliance']['discrepancies'].items():
            print(f"  {key}:")
            print(f"    Claimed: {values['claimed']}")
            print(f"    Actual:  {values['actual']}")

    # Final verdict
    print_section("🎯 Final Verdict")
    if all_passed:
        print(f"  {GREEN}{BOLD}✓ SPECIFICATION IS VALID{RESET}")
        print(f"  {GREEN}All validation checks passed!{RESET}")
        return 0
    else:
        print(f"  {RED}{BOLD}✗ SPECIFICATION HAS ISSUES{RESET}")
        print(f"  {RED}Please review and fix the issues above.{RESET}")
        return 1


def main():
    """Main validation entry point."""
    # Parse arguments
    verbose = '--verbose' in sys.argv or '-v' in sys.argv
    json_format = '--format' in sys.argv and 'json' in sys.argv

    # Check if in correct directory
    if not Path("SPEC.md").exists():
        print(f"{RED}Error: SPEC.md not found. Run from project root.{RESET}")
        sys.exit(1)

    # Load specification
    try:
        spec = load_spec()
    except Exception as e:
        print(f"{RED}Error loading specification: {e}{RESET}")
        sys.exit(1)

    # Run validation checks
    results = {}

    # Validate metadata
    passed, issues = validate_metadata(spec)
    results['metadata'] = {'passed': passed, 'issues': issues}

    # Validate features
    passed, issues = validate_features(spec)
    results['features'] = {'passed': passed, 'issues': issues}

    # Validate requirements
    passed, stats, issues = validate_requirements(spec)
    results['requirements'] = {'passed': passed, 'stats': stats, 'issues': issues}

    # Check test files exist
    passed, issues = check_test_files_exist(spec)
    results['test_files'] = {'passed': passed, 'issues': issues}

    # Validate compliance section
    passed, discrepancies, issues = validate_compliance(spec)
    results['compliance'] = {'passed': passed, 'discrepancies': discrepancies, 'issues': issues}

    # Output results
    if json_format:
        # JSON output for CI/CD
        output = {
            'valid': all(r['passed'] for r in results.values()),
            'timestamp': datetime.now().isoformat(),
            'results': results
        }
        print(json.dumps(output, indent=2))
        return 0 if output['valid'] else 1
    else:
        # Human-readable output
        return display_results(spec, results, verbose)


if __name__ == "__main__":
    sys.exit(main())
