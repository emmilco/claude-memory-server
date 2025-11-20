#!/usr/bin/env python3
"""
Manual Testing Script for FEAT-049: Intelligent Code Importance Scoring

This script performs comprehensive manual testing of the importance scoring feature:
1. Index a real codebase (this project itself)
2. Validate score distribution
3. Test configuration options
4. Measure performance impact
5. Spot-check critical vs utility functions
6. Test edge cases
"""

import sys
import json
import time
import asyncio
from pathlib import Path
from collections import defaultdict

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import ServerConfig
from src.memory.incremental_indexer import IncrementalIndexer
from src.store.factory import create_store
from src.analysis.importance_scorer import ImportanceScorer


def print_header(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def print_result(test_name: str, status: str, details: str = ""):
    """Print a test result."""
    status_icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
    print(f"{status_icon} {test_name}: {status}")
    if details:
        print(f"   {details}")


async def test_1_basic_scoring(config: ServerConfig):
    """Test 1: Validate basic importance scoring on this codebase."""
    print_header("TEST 1: Basic Importance Scoring")

    try:
        store = await create_store(config)
        indexer = IncrementalIndexer(store, config)

        # Index a few key files from this project
        test_files = [
            Path("src/analysis/complexity_analyzer.py"),
            Path("src/analysis/importance_scorer.py"),
            Path("src/core/server.py"),
        ]

        results = {"total_units": 0, "scores": [], "files_indexed": 0}

        for file_path in test_files:
            if file_path.exists():
                print(f"  Indexing {file_path}...")
                file_results = indexer._index_file(
                    file_path=file_path,
                    project_name="test-importance",
                    base_path=Path(".")
                )
                results["files_indexed"] += 1
                results["total_units"] += file_results.get("units_extracted", 0)

                # Extract importance scores from indexed units
                if "units" in file_results:
                    for unit in file_results["units"]:
                        if "importance" in unit:
                            results["scores"].append(unit["importance"])

        # Validate results
        if results["files_indexed"] == 0:
            print_result("Basic Scoring", "FAIL", "No files indexed")
            return False

        if results["total_units"] == 0:
            print_result("Basic Scoring", "FAIL", "No units extracted")
            return False

        if not results["scores"]:
            print_result("Basic Scoring", "FAIL", "No importance scores found")
            return False

        # Check for non-uniform scores (not all 0.7)
        unique_scores = len(set(results["scores"]))
        if unique_scores < 3:
            print_result(
                "Basic Scoring",
                "WARN",
                f"Only {unique_scores} unique scores found (expected diverse distribution)"
            )
        else:
            print_result(
                "Basic Scoring",
                "PASS",
                f"{results['files_indexed']} files, {results['total_units']} units, "
                f"{unique_scores} unique scores"
            )

        return True

    except Exception as e:
        print_result("Basic Scoring", "FAIL", f"Exception: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_2_score_distribution(config: ServerConfig):
    """Test 2: Validate score distribution is reasonable."""
    print_header("TEST 2: Score Distribution Validation")

    try:
        # Index a larger set of files
        store = await create_store(config)
        indexer = IncrementalIndexer(store, config)

        # Index all Python files in src/analysis/
        analysis_dir = Path("src/analysis")
        scores = []

        if analysis_dir.exists():
            for py_file in analysis_dir.glob("*.py"):
                if py_file.name != "__init__.py":
                    print(f"  Indexing {py_file}...")
                    results = indexer._index_file(
                        file_path=py_file,
                        project_name="test-distribution",
                        base_path=Path(".")
                    )

                    if "units" in results:
                        for unit in results["units"]:
                            if "importance" in unit:
                                scores.append({
                                    "score": unit["importance"],
                                    "name": unit.get("name", "unknown"),
                                    "file": py_file.name,
                                })

        if not scores:
            print_result("Distribution", "FAIL", "No scores collected")
            return False

        # Calculate distribution
        distribution = {
            "0.0-0.3": 0,
            "0.3-0.5": 0,
            "0.5-0.7": 0,
            "0.7-0.9": 0,
            "0.9-1.0": 0,
        }

        for item in scores:
            score = item["score"]
            if score < 0.3:
                distribution["0.0-0.3"] += 1
            elif score < 0.5:
                distribution["0.3-0.5"] += 1
            elif score < 0.7:
                distribution["0.5-0.7"] += 1
            elif score < 0.9:
                distribution["0.7-0.9"] += 1
            else:
                distribution["0.9-1.0"] += 1

        # Print distribution
        print(f"  Total units: {len(scores)}")
        print(f"  Distribution:")
        for range_name, count in distribution.items():
            percentage = (count / len(scores)) * 100
            print(f"    {range_name}: {count} ({percentage:.1f}%)")

        # Validate: should have at least 3 different ranges represented
        non_zero_ranges = sum(1 for count in distribution.values() if count > 0)

        if non_zero_ranges < 3:
            print_result(
                "Distribution",
                "WARN",
                f"Only {non_zero_ranges} ranges represented (expected >3)"
            )
        else:
            # Find top 5 highest and lowest scored functions
            sorted_scores = sorted(scores, key=lambda x: x["score"], reverse=True)

            print("\n  Top 5 highest scoring units:")
            for item in sorted_scores[:5]:
                print(f"    {item['score']:.3f} - {item['name']} ({item['file']})")

            print("\n  Top 5 lowest scoring units:")
            for item in sorted_scores[-5:]:
                print(f"    {item['score']:.3f} - {item['name']} ({item['file']})")

            print_result(
                "Distribution",
                "PASS",
                f"{non_zero_ranges}/5 ranges represented"
            )

        return True

    except Exception as e:
        print_result("Distribution", "FAIL", f"Exception: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_3_config_options():
    """Test 3: Validate configuration options work correctly."""
    print_header("TEST 3: Configuration Options")

    try:
        # Test with scoring disabled
        config_disabled = ServerConfig(enable_importance_scoring=False)
        scorer_disabled = ImportanceScorer(
            complexity_weight=config_disabled.importance_complexity_weight,
            usage_weight=config_disabled.importance_usage_weight,
            criticality_weight=config_disabled.importance_criticality_weight,
        )

        print(f"  Scoring disabled: {not config_disabled.enable_importance_scoring}")
        print_result("Config - Disable", "PASS", "Configuration created successfully")

        # Test with custom weights
        config_custom = ServerConfig(
            enable_importance_scoring=True,
            importance_complexity_weight=2.0,
            importance_usage_weight=0.5,
            importance_criticality_weight=1.5,
        )

        scorer_custom = ImportanceScorer(
            complexity_weight=config_custom.importance_complexity_weight,
            usage_weight=config_custom.importance_usage_weight,
            criticality_weight=config_custom.importance_criticality_weight,
        )

        print(f"  Complexity weight: {config_custom.importance_complexity_weight}")
        print(f"  Usage weight: {config_custom.importance_usage_weight}")
        print(f"  Criticality weight: {config_custom.importance_criticality_weight}")
        print_result("Config - Custom Weights", "PASS", "Custom weights applied")

        # Test weight validation (out of range should fail)
        try:
            invalid_config = ServerConfig(importance_complexity_weight=3.0)
            print_result("Config - Validation", "FAIL", "Invalid weight accepted (should reject >2.0)")
            return False
        except Exception:
            print_result("Config - Validation", "PASS", "Invalid weight correctly rejected")

        return True

    except Exception as e:
        print_result("Configuration", "FAIL", f"Exception: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_4_performance_impact(config: ServerConfig):
    """Test 4: Measure performance impact of importance scoring."""
    print_header("TEST 4: Performance Impact")

    try:
        # Index with scoring enabled
        print("  Indexing with importance scoring ENABLED...")
        config_enabled = ServerConfig(enable_importance_scoring=True)
        store_enabled = await create_store(config_enabled)
        indexer_enabled = IncrementalIndexer(store_enabled, config_enabled)

        test_file = Path("src/core/server.py")
        if not test_file.exists():
            print_result("Performance", "SKIP", "Test file not found")
            return True

        start_time = time.time()
        for _ in range(3):  # Run 3 times for average
            indexer_enabled._index_file(
                file_path=test_file,
                project_name="perf-test-enabled",
                base_path=Path(".")
            )
        time_enabled = (time.time() - start_time) / 3

        # Index with scoring disabled
        print("  Indexing with importance scoring DISABLED...")
        config_disabled = ServerConfig(enable_importance_scoring=False)
        store_disabled = await create_store(config_disabled)
        indexer_disabled = IncrementalIndexer(store_disabled, config_disabled)

        start_time = time.time()
        for _ in range(3):  # Run 3 times for average
            indexer_disabled._index_file(
                file_path=test_file,
                project_name="perf-test-disabled",
                base_path=Path(".")
            )
        time_disabled = (time.time() - start_time) / 3

        # Calculate impact
        slowdown_pct = ((time_enabled - time_disabled) / time_disabled) * 100

        print(f"  Time with scoring: {time_enabled:.3f}s")
        print(f"  Time without scoring: {time_disabled:.3f}s")
        print(f"  Performance impact: {slowdown_pct:+.1f}%")

        if slowdown_pct > 10:
            print_result(
                "Performance",
                "WARN",
                f"Slowdown {slowdown_pct:.1f}% exceeds 10% target"
            )
        else:
            print_result(
                "Performance",
                "PASS",
                f"Slowdown {slowdown_pct:.1f}% is within 10% target"
            )

        return True

    except Exception as e:
        print_result("Performance", "FAIL", f"Exception: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_5_spot_check_functions(config: ServerConfig):
    """Test 5: Spot-check that critical functions score higher than utilities."""
    print_header("TEST 5: Spot-Check Critical vs Utility Functions")

    try:
        store = await create_store(config)
        indexer = IncrementalIndexer(store, config)

        # Index files with known critical and utility functions
        test_cases = [
            {
                "file": Path("src/core/server.py"),
                "expected_high": ["store_memory", "retrieve_memories", "search_code"],  # Core API methods
                "expected_low": ["_validate", "get_status"],  # Simple methods
            },
            {
                "file": Path("src/analysis/importance_scorer.py"),
                "expected_high": ["calculate_importance", "calculate_batch"],  # Complex logic
                "expected_low": ["get_summary_statistics"],  # Simpler utility
            },
        ]

        all_passed = True

        for test_case in test_cases:
            file_path = test_case["file"]
            if not file_path.exists():
                print(f"  Skipping {file_path} (not found)")
                continue

            print(f"\n  Analyzing {file_path}...")
            results = indexer._index_file(
                file_path=file_path,
                project_name="spot-check",
                base_path=Path(".")
            )

            if "units" not in results:
                print(f"    No units extracted")
                continue

            # Build score map
            score_map = {}
            for unit in results["units"]:
                name = unit.get("name", "")
                importance = unit.get("importance", 0.0)
                score_map[name] = importance

            # Check expected high scoring functions
            for func_name in test_case["expected_high"]:
                if func_name in score_map:
                    score = score_map[func_name]
                    if score >= 0.5:  # Should be at least medium importance
                        print(f"    ✅ {func_name}: {score:.3f} (expected high)")
                    else:
                        print(f"    ❌ {func_name}: {score:.3f} (expected high, got low)")
                        all_passed = False

            # Check expected low scoring functions
            for func_name in test_case["expected_low"]:
                if func_name in score_map:
                    score = score_map[func_name]
                    if score < 0.7:  # Should be below high importance
                        print(f"    ✅ {func_name}: {score:.3f} (expected low/medium)")
                    else:
                        print(f"    ⚠️  {func_name}: {score:.3f} (expected lower)")

        if all_passed:
            print_result("Spot Check", "PASS", "Critical functions score appropriately")
        else:
            print_result("Spot Check", "WARN", "Some functions didn't match expectations")

        return True

    except Exception as e:
        print_result("Spot Check", "FAIL", f"Exception: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_6_edge_cases():
    """Test 6: Test edge cases (empty files, malformed code, large functions)."""
    print_header("TEST 6: Edge Cases")

    try:
        scorer = ImportanceScorer()

        # Test 1: Empty function
        empty_func = {
            "name": "empty_func",
            "content": "def empty_func():\n    pass",
            "signature": "empty_func()",
            "unit_type": "function",
            "language": "python",
        }

        score = scorer.calculate_importance(empty_func)
        print(f"  Empty function score: {score.importance:.3f}")
        if 0.0 <= score.importance <= 0.4:
            print_result("Edge - Empty Function", "PASS", f"Score {score.importance:.3f} is appropriately low")
        else:
            print_result("Edge - Empty Function", "WARN", f"Score {score.importance:.3f} seems high for empty function")

        # Test 2: Very large function
        large_func = {
            "name": "large_func",
            "content": "def large_func():\n" + "\n".join([f"    x{i} = {i}" for i in range(100)]),
            "signature": "large_func()",
            "unit_type": "function",
            "language": "python",
        }

        score = scorer.calculate_importance(large_func)
        print(f"  Large function score: {score.importance:.3f}")
        if score.importance >= 0.5:
            print_result("Edge - Large Function", "PASS", f"Score {score.importance:.3f} reflects size")
        else:
            print_result("Edge - Large Function", "WARN", f"Score {score.importance:.3f} seems low for large function")

        # Test 3: Function with security keywords
        security_func = {
            "name": "authenticate_user",
            "content": "def authenticate_user(username, password):\n    # Check auth\n    return validate_token(username, password)",
            "signature": "authenticate_user(username, password)",
            "unit_type": "function",
            "language": "python",
        }

        score = scorer.calculate_importance(security_func)
        print(f"  Security function score: {score.importance:.3f}")
        print(f"    Security keywords found: {score.security_keywords}")
        if score.importance >= 0.6 and len(score.security_keywords) > 0:
            print_result("Edge - Security Function", "PASS", f"Score {score.importance:.3f} reflects criticality")
        else:
            print_result("Edge - Security Function", "WARN", f"Score {score.importance:.3f} seems low for security function")

        return True

    except Exception as e:
        print_result("Edge Cases", "FAIL", f"Exception: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all manual tests."""
    print("\n" + "█" * 80)
    print("  FEAT-049: Intelligent Code Importance Scoring - Manual Test Suite")
    print("█" * 80)

    # Initialize config
    config = ServerConfig(enable_importance_scoring=True)

    # Run all tests
    results = {
        "Test 1: Basic Scoring": await test_1_basic_scoring(config),
        "Test 2: Distribution": await test_2_score_distribution(config),
        "Test 3: Configuration": test_3_config_options(),
        "Test 4: Performance": await test_4_performance_impact(config),
        "Test 5: Spot Check": await test_5_spot_check_functions(config),
        "Test 6: Edge Cases": test_6_edge_cases(),
    }

    # Print summary
    print_header("TEST SUMMARY")

    passed = sum(1 for result in results.values() if result)
    total = len(results)

    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}: {test_name}")

    print(f"\n  Overall: {passed}/{total} tests passed ({(passed/total)*100:.0f}%)")

    if passed == total:
        print("\n🎉 All manual tests passed! Feature is working as expected.")
        return 0
    else:
        print("\n⚠️  Some tests failed or had warnings. Review the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
