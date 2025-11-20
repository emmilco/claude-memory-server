#!/usr/bin/env python3
"""
Simplified Manual Test for FEAT-049: Intelligent Code Importance Scoring

Tests the importance scorer directly without indexing complexity.
"""

import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from src.analysis.importance_scorer import ImportanceScorer
from src.analysis.complexity_analyzer import ComplexityAnalyzer
from src.analysis.usage_analyzer import UsageAnalyzer
from src.analysis.criticality_analyzer import CriticalityAnalyzer


def print_header(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def test_individual_analyzers():
    """Test each analyzer individually."""
    print_header("Testing Individual Analyzers")

    # Test complexity analyzer
    print("1. Complexity Analyzer")
    complexity_analyzer = ComplexityAnalyzer()

    simple_func = {
        "name": "simple_getter",
        "content": "def simple_getter():\n    return value",
        "signature": "simple_getter()",
        "unit_type": "function",
        "language": "python",
    }

    complex_func = {
        "name": "complex_auth_function",
        "content": """def complex_auth_function(user, password, token):
    if not user:
        return None
    if not password:
        if not token:
            raise ValueError("Need password or token")
        else:
            try:
                validated = validate_token(token)
                if validated:
                    return authenticate_with_token(user, token)
                else:
                    return None
            except Exception as e:
                logger.error(f"Token validation failed: {e}")
                return None
    else:
        if check_password_strength(password):
            hashed = hash_password(password)
            return authenticate_with_password(user, hashed)
    return None
""",
        "signature": "complex_auth_function(user, password, token)",
        "unit_type": "function",
        "language": "python",
    }

    simple_result = complexity_analyzer.analyze(simple_func)
    complex_result = complexity_analyzer.analyze(complex_func)

    print(f"   Simple function:")
    print(f"     - Cyclomatic: {simple_result.cyclomatic_complexity}")
    print(f"     - Line count: {simple_result.line_count}")
    print(f"     - Nesting: {simple_result.nesting_depth}")
    print(f"     - Score: {simple_result.complexity_score:.3f}")

    print(f"   Complex function:")
    print(f"     - Cyclomatic: {complex_result.cyclomatic_complexity}")
    print(f"     - Line count: {complex_result.line_count}")
    print(f"     - Nesting: {complex_result.nesting_depth}")
    print(f"     - Score: {complex_result.complexity_score:.3f}")

    if complex_result.complexity_score > simple_result.complexity_score:
        print("   ✅ Complex function scores higher than simple function")
    else:
        print(f"   ❌ Complex ({complex_result.complexity_score:.3f}) should be > Simple ({simple_result.complexity_score:.3f})")

    # Test criticality analyzer
    print("\n2. Criticality Analyzer")
    criticality_analyzer = CriticalityAnalyzer()

    security_func = {
        "name": "authenticate_user",
        "content": """def authenticate_user(username, password):
    '''Authenticate user with password and generate auth token.'''
    if not username or not password:
        raise ValueError("Missing credentials")
    try:
        hashed = hash_password(password)
        user = validate_credentials(username, hashed)
        if user:
            token = generate_auth_token(user)
            session = create_session(user, token)
            return session
        else:
            raise PermissionError("Invalid credentials")
    except Exception as e:
        logger.error(f"Authentication failed: {e}")
        return None
""",
        "signature": "authenticate_user(username, password)",
        "unit_type": "function",
        "language": "python",
    }

    utility_func = {
        "name": "format_name",
        "content": "def format_name(first, last):\n    return f'{first} {last}'",
        "signature": "format_name(first, last)",
        "unit_type": "function",
        "language": "python",
    }

    security_result = criticality_analyzer.analyze(security_func, Path("src/auth/core.py"))
    utility_result = criticality_analyzer.analyze(utility_func, Path("src/utils/formatting.py"))

    print(f"   Security function:")
    print(f"     - Keywords: {security_result.security_keywords}")
    print(f"     - Error handling: {security_result.has_error_handling}")
    print(f"     - Boost: {security_result.criticality_boost:.3f}")

    print(f"   Utility function:")
    print(f"     - Keywords: {utility_result.security_keywords}")
    print(f"     - Error handling: {utility_result.has_error_handling}")
    print(f"     - Boost: {utility_result.criticality_boost:.3f}")

    if security_result.criticality_boost > utility_result.criticality_boost:
        print("   ✅ Security function has higher criticality boost")
    else:
        print(f"   ❌ Security ({security_result.criticality_boost:.3f}) should be > Utility ({utility_result.criticality_boost:.3f})")

    # Test usage analyzer
    print("\n3. Usage Analyzer")
    usage_analyzer = UsageAnalyzer()

    public_func = {
        "name": "export_data",
        "content": "def export_data(format):\n    return serialize(data, format)",
        "signature": "export_data(format)",
        "unit_type": "function",
        "language": "python",
    }

    private_func = {
        "name": "_internal_helper",
        "content": "def _internal_helper(x):\n    return x * 2",
        "signature": "_internal_helper(x)",
        "unit_type": "function",
        "language": "python",
    }

    public_result = usage_analyzer.analyze(public_func, None, "from mymodule import export_data")
    private_result = usage_analyzer.analyze(private_func, None, "")

    print(f"   Public function:")
    print(f"     - Is public: {public_result.is_public}")
    print(f"     - Is exported: {public_result.is_exported}")
    print(f"     - Boost: {public_result.usage_boost:.3f}")

    print(f"   Private function:")
    print(f"     - Is public: {private_result.is_public}")
    print(f"     - Is exported: {private_result.is_exported}")
    print(f"     - Boost: {private_result.usage_boost:.3f}")

    if public_result.usage_boost >= private_result.usage_boost:
        print("   ✅ Public function has higher or equal usage boost")
    else:
        print(f"   ❌ Public ({public_result.usage_boost:.3f}) should be >= Private ({private_result.usage_boost:.3f})")


def test_integrated_scorer():
    """Test the integrated importance scorer."""
    print_header("Testing Integrated Importance Scorer")

    scorer = ImportanceScorer()

    test_cases = [
        {
            "name": "Critical Security Function",
            "code_unit": {
                "name": "authenticate_and_authorize",
                "content": """def authenticate_and_authorize(user, password, resource):
    '''Core authentication and authorization handler.'''
    if not user or not password:
        raise ValueError("Missing credentials")

    try:
        # Authenticate
        hashed = hash_password(password)
        user_obj = validate_credentials(user, hashed)
        if not user_obj:
            raise PermissionError("Authentication failed")

        # Generate token
        token = generate_auth_token(user_obj)
        session = create_session(user_obj, token)

        # Check authorization
        if not check_permission(user_obj, resource):
            raise PermissionError("Insufficient permissions")

        # Audit log
        log_access(user_obj, resource, "granted")
        return session

    except Exception as e:
        log_access(user, resource, "denied", error=str(e))
        raise
""",
                "signature": "authenticate_and_authorize(user, password, resource)",
                "unit_type": "function",
                "language": "python",
            },
            "file_path": Path("src/auth/core.py"),
            "expected_range": (0.7, 1.0),
        },
        {
            "name": "Simple Utility Function",
            "code_unit": {
                "name": "capitalize_name",
                "content": "def capitalize_name(name):\n    return name.capitalize()",
                "signature": "capitalize_name(name)",
                "unit_type": "function",
                "language": "python",
            },
            "file_path": Path("src/utils/string.py"),
            "expected_range": (0.2, 0.5),
        },
        {
            "name": "Medium Complexity Business Logic",
            "code_unit": {
                "name": "calculate_discount",
                "content": """def calculate_discount(price, quantity, customer_type):
    '''Calculate discount based on multiple factors.'''
    base_discount = 0.0

    # Quantity discount
    if quantity >= 100:
        base_discount += 0.15
    elif quantity >= 50:
        base_discount += 0.10
    elif quantity >= 10:
        base_discount += 0.05

    # Customer type discount
    if customer_type == "premium":
        base_discount += 0.10
    elif customer_type == "regular":
        base_discount += 0.05

    # Cap at 30%
    final_discount = min(0.30, base_discount)
    return price * (1 - final_discount)
""",
                "signature": "calculate_discount(price, quantity, customer_type)",
                "unit_type": "function",
                "language": "python",
            },
            "file_path": Path("src/billing/discounts.py"),
            "expected_range": (0.4, 0.7),
        },
    ]

    for test_case in test_cases:
        print(f"\n{test_case['name']}:")
        result = scorer.calculate_importance(
            code_unit=test_case["code_unit"],
            file_path=test_case["file_path"]
        )

        print(f"  Final importance: {result.importance:.3f}")
        print(f"  Breakdown:")
        print(f"    - Complexity score: {result.complexity_score:.3f}")
        print(f"    - Usage boost: {result.usage_boost:.3f}")
        print(f"    - Criticality boost: {result.criticality_boost:.3f}")
        print(f"  Metrics:")
        print(f"    - Cyclomatic complexity: {result.cyclomatic_complexity}")
        print(f"    - Line count: {result.line_count}")
        print(f"    - Security keywords: {result.security_keywords}")
        print(f"    - Has error handling: {result.has_error_handling}")

        expected_min, expected_max = test_case["expected_range"]
        if expected_min <= result.importance <= expected_max:
            print(f"  ✅ Score within expected range ({expected_min:.1f}-{expected_max:.1f})")
        else:
            print(f"  ⚠️  Score {result.importance:.3f} outside expected range ({expected_min:.1f}-{expected_max:.1f})")


def test_configuration_weights():
    """Test configurable weights."""
    print_header("Testing Configurable Weights")

    test_unit = {
        "name": "test_function",
        "content": """def test_function(password):
    if not validate_password(password):
        raise ValueError("Invalid password")
    return hash_password(password)
""",
        "signature": "test_function(password)",
        "unit_type": "function",
        "language": "python",
    }

    # Test with default weights
    scorer_default = ImportanceScorer()
    result_default = scorer_default.calculate_importance(test_unit, file_path=Path("src/auth.py"))

    # Test with high complexity weight
    scorer_complexity = ImportanceScorer(complexity_weight=2.0, usage_weight=0.5, criticality_weight=0.5)
    result_complexity = scorer_complexity.calculate_importance(test_unit, file_path=Path("src/auth.py"))

    # Test with high criticality weight
    scorer_criticality = ImportanceScorer(complexity_weight=0.5, usage_weight=0.5, criticality_weight=2.0)
    result_criticality = scorer_criticality.calculate_importance(test_unit, file_path=Path("src/auth.py"))

    print(f"Default weights (1.0, 1.0, 1.0): {result_default.importance:.3f}")
    print(f"  - Complexity: {result_default.complexity_score:.3f}, Usage: {result_default.usage_boost:.3f}, Criticality: {result_default.criticality_boost:.3f}")

    print(f"\nHigh complexity weight (2.0, 0.5, 0.5): {result_complexity.importance:.3f}")
    print(f"  - Complexity: {result_complexity.complexity_score:.3f} * 2.0 = {result_complexity.complexity_score * 2.0:.3f}")

    print(f"\nHigh criticality weight (0.5, 0.5, 2.0): {result_criticality.importance:.3f}")
    print(f"  - Criticality: {result_criticality.criticality_boost:.3f} * 2.0 = {result_criticality.criticality_boost * 2.0:.3f}")

    if result_criticality.importance > result_default.importance:
        print("\n✅ Higher criticality weight increases score for security function")
    else:
        print(f"\n⚠️  Criticality-weighted score ({result_criticality.importance:.3f}) should be > default ({result_default.importance:.3f})")


def main():
    """Run all tests."""
    print("\n" + "█" * 80)
    print("  FEAT-049: Simplified Manual Test Suite")
    print("█" * 80)

    test_individual_analyzers()
    test_integrated_scorer()
    test_configuration_weights()

    print_header("Summary")
    print("✅ All tests completed! Review output above for detailed results.")
    print("\nKey findings will help identify:")
    print("  1. Whether analyzers are working correctly")
    print("  2. Whether scores discriminate between different function types")
    print("  3. Whether configuration weights have the expected effect")
    print("  4. Areas for potential improvement")


if __name__ == "__main__":
    sys.exit(main())
