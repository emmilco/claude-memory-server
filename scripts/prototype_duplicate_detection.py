#!/usr/bin/env python3
"""
Prototype for code duplicate detection threshold tuning.

Tests semantic similarity thresholds on the claude-memory-server codebase
to validate the duplicate detection approach.

Usage:
    python scripts/prototype_duplicate_detection.py [--threshold 0.85] [--samples 5]
"""

import asyncio
import argparse
import numpy as np
from pathlib import Path
from typing import List, Tuple
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.store.qdrant_store import QdrantMemoryStore
from src.config import get_config
from qdrant_client.models import Filter, FieldCondition, MatchValue


def cosine_similarity_matrix(embeddings: np.ndarray) -> np.ndarray:
    """
    Calculate pairwise cosine similarity matrix (vectorized).

    Args:
        embeddings: Array of shape (N, dim) where N is number of embeddings

    Returns:
        Similarity matrix of shape (N, N) with values in [0, 1]
    """
    # Normalize embeddings to unit length
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)  # Avoid division by zero
    normalized = embeddings / norms

    # Matrix multiplication gives cosine similarity
    # A @ A.T = dot product of normalized vectors = cosine similarity
    similarity = normalized @ normalized.T

    # Clip to [0, 1] range (numerical stability)
    return np.clip(similarity, 0, 1)


async def load_code_units(project_name: str = "claude-memory-server"):
    """
    Load all code units from Qdrant for the specified project.

    Returns:
        Tuple of (points_list, embeddings_array)
    """
    config = get_config()
    store = QdrantMemoryStore(config)
    await store.initialize()

    print(f"Loading code units for project: {project_name}")

    # Filter for code category and project
    project_filter = Filter(
        must=[
            FieldCondition(key="category", match=MatchValue(value="code")),
            FieldCondition(key="project_name", match=MatchValue(value=project_name))
        ]
    )

    # Scroll through all code units
    all_units = []
    offset = None

    while True:
        results, offset = store.client.scroll(
            collection_name=store.collection_name,
            scroll_filter=project_filter,
            limit=100,
            offset=offset,
            with_payload=True,
            with_vectors=True
        )

        all_units.extend(results)

        if offset is None:
            break

    await store.close()

    print(f"Loaded {len(all_units)} code units")
    return all_units


def find_duplicate_pairs(
    similarity_matrix: np.ndarray,
    threshold: float
) -> List[Tuple[int, int, float]]:
    """
    Find pairs of units above similarity threshold.

    Args:
        similarity_matrix: Pairwise similarity matrix
        threshold: Minimum similarity to consider duplicates

    Returns:
        List of (index_i, index_j, similarity) tuples sorted by similarity descending
    """
    pairs = []

    # Only check upper triangle (avoid duplicates and self-comparisons)
    for i in range(len(similarity_matrix)):
        for j in range(i + 1, len(similarity_matrix)):
            sim = similarity_matrix[i][j]
            if sim >= threshold:
                pairs.append((i, j, sim))

    # Sort by similarity descending
    pairs.sort(key=lambda x: x[2], reverse=True)

    return pairs


def format_unit_info(unit) -> str:
    """Format unit information for display."""
    payload = unit.payload if hasattr(unit, 'payload') else {}

    # Try both direct payload and nested metadata
    if 'metadata' in payload:
        metadata = payload['metadata']
    else:
        metadata = payload

    unit_name = metadata.get('unit_name', 'unknown')
    file_path = metadata.get('file_path', 'unknown')
    file_name = file_path.split('/')[-1] if file_path != 'unknown' else 'unknown'
    start_line = metadata.get('start_line', '?')
    end_line = metadata.get('end_line', '?')

    return f"{unit_name} ({file_name}:{start_line}-{end_line})"


async def prototype_duplicate_detection(args):
    """
    Test duplicate detection on this codebase.

    Args:
        args: Command line arguments with threshold and samples
    """
    # Load code units
    all_units = await load_code_units()

    if not all_units:
        print("No code units found. Please index the codebase first:")
        print("  python -m src.cli index . --project-name claude-memory-server")
        return

    # Extract embeddings
    print("\nExtracting embeddings...")
    embeddings = np.array([u.vector for u in all_units])
    print(f"Embeddings shape: {embeddings.shape}")

    # Calculate similarity matrix
    print("Calculating similarity matrix (this may take a moment)...")
    similarity_matrix = cosine_similarity_matrix(embeddings)

    # Test different thresholds
    thresholds = [0.75, 0.80, 0.85, 0.90, 0.95, 0.98]

    print("\n" + "="*80)
    print("DUPLICATE DETECTION THRESHOLD ANALYSIS")
    print("="*80)

    for threshold in thresholds:
        pairs = find_duplicate_pairs(similarity_matrix, threshold)

        print(f"\n{'─'*80}")
        print(f"Threshold: {threshold:.2f} | Duplicate pairs found: {len(pairs)}")
        print(f"{'─'*80}")

        if not pairs:
            print("  No duplicates found at this threshold")
            continue

        # Show distribution of similarity scores
        if len(pairs) > 0:
            similarities = [p[2] for p in pairs]
            print(f"  Similarity range: {min(similarities):.3f} - {max(similarities):.3f}")
            print(f"  Average similarity: {np.mean(similarities):.3f}")

        # Sample random pairs for manual review
        import random
        num_samples = min(args.samples, len(pairs))
        samples = random.sample(pairs, num_samples) if len(pairs) > num_samples else pairs

        print(f"\n  Sample pairs (showing {num_samples}/{len(pairs)}):")

        for idx, (i, j, score) in enumerate(samples, 1):
            unit_i = all_units[i]
            unit_j = all_units[j]

            print(f"\n  [{idx}] Similarity: {score:.4f}")
            print(f"      A: {format_unit_info(unit_i)}")
            print(f"      B: {format_unit_info(unit_j)}")

            # Show complexity metrics if available
            payload_i = unit_i.payload if hasattr(unit_i, 'payload') else {}
            payload_j = unit_j.payload if hasattr(unit_j, 'payload') else {}

            meta_i = payload_i.get('metadata', payload_i)
            meta_j = payload_j.get('metadata', payload_j)

            if 'cyclomatic_complexity' in meta_i:
                print(f"      Complexity A: {meta_i.get('cyclomatic_complexity', 'N/A')}, "
                      f"Lines: {meta_i.get('line_count', 'N/A')}")
                print(f"      Complexity B: {meta_j.get('cyclomatic_complexity', 'N/A')}, "
                      f"Lines: {meta_j.get('line_count', 'N/A')}")

    # Final recommendations
    print("\n" + "="*80)
    print("RECOMMENDATIONS")
    print("="*80)

    # Analyze distribution at key thresholds
    pairs_095 = find_duplicate_pairs(similarity_matrix, 0.95)
    pairs_085 = find_duplicate_pairs(similarity_matrix, 0.85)
    pairs_075 = find_duplicate_pairs(similarity_matrix, 0.75)

    print(f"""
Based on this analysis:

1. HIGH CONFIDENCE (≥0.95): {len(pairs_095)} pairs
   - Near-identical code (copy-paste, minor variable renames)
   - Safe for auto-merge recommendations
   - Example use: "These functions are duplicates, consider consolidating"

2. MEDIUM CONFIDENCE (0.85-0.95): {len(pairs_085) - len(pairs_095)} pairs
   - Semantic duplicates (same logic, different style)
   - Should prompt user for review
   - Example use: "These functions may be duplicates, review recommended"

3. LOW CONFIDENCE (0.75-0.85): {len(pairs_075) - len(pairs_085)} pairs
   - Similar patterns (related functionality)
   - Flag as related, not duplicates
   - Example use: "These functions have similar patterns"

RECOMMENDED SETTINGS:
- Default threshold: 0.85 (medium confidence)
- Auto-merge threshold: 0.95 (high confidence)
- Related code threshold: 0.75 (low confidence)
""")

    # Statistics
    print("\nSTATISTICS:")
    print(f"  Total code units analyzed: {len(all_units)}")
    print(f"  Total pairwise comparisons: {len(all_units) * (len(all_units) - 1) // 2}")
    print(f"  Duplicate rate (≥0.85): {len(pairs_085) / len(all_units) * 100:.1f}% of units")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Prototype duplicate detection threshold tuning"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="Test a specific threshold (overrides default range)"
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=5,
        help="Number of sample pairs to show at each threshold (default: 5)"
    )

    args = parser.parse_args()

    # Run prototype
    asyncio.run(prototype_duplicate_detection(args))


if __name__ == "__main__":
    main()
