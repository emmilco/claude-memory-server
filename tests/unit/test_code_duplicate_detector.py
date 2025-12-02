"""
Unit tests for CodeDuplicateDetector.

Tests cover:
1. Similarity matrix calculation (basic, empty, single unit)
2. Duplicate pair detection (threshold filtering, sorting, validation)
3. Duplicate clustering (transitive closure, singleton filtering)
4. Edge cases (empty inputs, single units, threshold boundaries)
"""

import pytest
import numpy as np
from src.analysis.code_duplicate_detector import (
    CodeDuplicateDetector,
    DuplicateCluster,
    DuplicatePair,
)


class TestCodeDuplicateDetector:
    """Test suite for CodeDuplicateDetector."""

    def test_initialization_with_valid_threshold(self):
        """Test detector initializes with valid threshold."""
        detector = CodeDuplicateDetector(threshold=0.85)
        assert detector.threshold == 0.85

        detector_low = CodeDuplicateDetector(threshold=0.0)
        assert detector_low.threshold == 0.0

        detector_high = CodeDuplicateDetector(threshold=1.0)
        assert detector_high.threshold == 1.0

    def test_initialization_with_invalid_threshold(self):
        """Test detector raises ValueError for invalid threshold."""
        with pytest.raises(ValueError, match="Threshold must be in"):
            CodeDuplicateDetector(threshold=-0.1)

        with pytest.raises(ValueError, match="Threshold must be in"):
            CodeDuplicateDetector(threshold=1.1)

    def test_calculate_similarity_matrix_basic(self):
        """Test similarity matrix calculation with basic embeddings."""
        detector = CodeDuplicateDetector()

        # Create simple test embeddings
        embeddings = np.array(
            [
                [1.0, 0.0, 0.0],  # Unit A
                [1.0, 0.0, 0.0],  # Unit B (identical to A)
                [0.0, 1.0, 0.0],  # Unit C (orthogonal to A and B)
            ]
        )

        similarity_matrix = detector.calculate_similarity_matrix(embeddings)

        # Check matrix shape
        assert similarity_matrix.shape == (3, 3)

        # Check diagonal (self-similarity should be 1.0)
        assert similarity_matrix[0, 0] == pytest.approx(1.0)
        assert similarity_matrix[1, 1] == pytest.approx(1.0)
        assert similarity_matrix[2, 2] == pytest.approx(1.0)

        # Check A-B similarity (identical vectors)
        assert similarity_matrix[0, 1] == pytest.approx(1.0)
        assert similarity_matrix[1, 0] == pytest.approx(1.0)

        # Check A-C similarity (orthogonal vectors)
        assert similarity_matrix[0, 2] == pytest.approx(0.0)
        assert similarity_matrix[2, 0] == pytest.approx(0.0)

        # Check matrix is symmetric
        assert np.allclose(similarity_matrix, similarity_matrix.T)

    def test_calculate_similarity_matrix_with_real_embeddings(self):
        """Test similarity matrix with realistic embeddings."""
        detector = CodeDuplicateDetector()

        # Generate random embeddings (simulating real code)
        np.random.seed(42)
        embeddings = np.random.randn(5, 768)  # 5 units, 768-dim embeddings

        similarity_matrix = detector.calculate_similarity_matrix(embeddings)

        # Check shape
        assert similarity_matrix.shape == (5, 5)

        # Check all values in [0, 1]
        assert np.all(similarity_matrix >= 0.0)
        assert np.all(similarity_matrix <= 1.0)

        # Check diagonal is 1.0
        assert np.allclose(np.diag(similarity_matrix), 1.0)

        # Check symmetry
        assert np.allclose(similarity_matrix, similarity_matrix.T)

    def test_calculate_similarity_matrix_with_empty_embeddings(self):
        """Test similarity matrix raises error for empty embeddings."""
        detector = CodeDuplicateDetector()

        with pytest.raises(ValueError, match="Embeddings array is empty"):
            detector.calculate_similarity_matrix(np.array([]))

    def test_calculate_similarity_matrix_with_invalid_shape(self):
        """Test similarity matrix raises error for 1D embeddings."""
        detector = CodeDuplicateDetector()

        with pytest.raises(ValueError, match="Embeddings must be 2D array"):
            detector.calculate_similarity_matrix(np.array([1.0, 2.0, 3.0]))

    def test_get_duplicate_pairs_basic(self):
        """Test duplicate pair detection with basic similarity matrix."""
        detector = CodeDuplicateDetector(threshold=0.85)

        # Create similarity matrix
        # A-B: 0.95 (duplicate), B-C: 0.80 (not duplicate), A-C: 0.90 (duplicate)
        similarity_matrix = np.array(
            [
                [1.0, 0.95, 0.90],
                [0.95, 1.0, 0.80],
                [0.90, 0.80, 1.0],
            ]
        )

        unit_ids = ["unit_A", "unit_B", "unit_C"]

        pairs = detector.get_duplicate_pairs(similarity_matrix, unit_ids)

        # Should find 2 pairs: A-B (0.95), A-C (0.90)
        assert len(pairs) == 2

        # Check sorting (descending by similarity)
        assert pairs[0].similarity == pytest.approx(0.95)
        assert pairs[1].similarity == pytest.approx(0.90)

        # Check pair details
        assert pairs[0].unit_id_1 == "unit_A"
        assert pairs[0].unit_id_2 == "unit_B"

        assert pairs[1].unit_id_1 == "unit_A"
        assert pairs[1].unit_id_2 == "unit_C"

    def test_get_duplicate_pairs_with_threshold_override(self):
        """Test duplicate pair detection with threshold override."""
        detector = CodeDuplicateDetector(threshold=0.85)

        similarity_matrix = np.array(
            [
                [1.0, 0.95, 0.90],
                [0.95, 1.0, 0.80],
                [0.90, 0.80, 1.0],
            ]
        )

        unit_ids = ["unit_A", "unit_B", "unit_C"]

        # Override with higher threshold
        pairs = detector.get_duplicate_pairs(
            similarity_matrix, unit_ids, threshold=0.92
        )

        # Should find only 1 pair: A-B (0.95)
        assert len(pairs) == 1
        assert pairs[0].similarity == pytest.approx(0.95)

    def test_get_duplicate_pairs_no_duplicates(self):
        """Test duplicate pair detection when no pairs exceed threshold."""
        detector = CodeDuplicateDetector(threshold=0.95)

        similarity_matrix = np.array(
            [
                [1.0, 0.80, 0.75],
                [0.80, 1.0, 0.70],
                [0.75, 0.70, 1.0],
            ]
        )

        unit_ids = ["unit_A", "unit_B", "unit_C"]

        pairs = detector.get_duplicate_pairs(similarity_matrix, unit_ids)

        # Should find no pairs
        assert len(pairs) == 0

    def test_get_duplicate_pairs_validates_dimensions(self):
        """Test duplicate pair detection validates matrix dimensions."""
        detector = CodeDuplicateDetector()

        similarity_matrix = np.array(
            [
                [1.0, 0.90],
                [0.90, 1.0],
            ]
        )

        unit_ids = ["unit_A", "unit_B", "unit_C"]  # Mismatch: 3 IDs, 2x2 matrix

        with pytest.raises(ValueError, match="Matrix dimensions .* don't match"):
            detector.get_duplicate_pairs(similarity_matrix, unit_ids)

    def test_cluster_duplicates_basic(self):
        """Test duplicate clustering with transitive closure."""
        detector = CodeDuplicateDetector(threshold=0.85)

        # Create similarity matrix with transitive closure:
        # A-B: 0.90, B-C: 0.88, C-D: 0.92 → All connected
        # E: isolated (no connections)
        similarity_matrix = np.array(
            [
                [1.0, 0.90, 0.70, 0.65, 0.50],  # A
                [0.90, 1.0, 0.88, 0.70, 0.55],  # B
                [0.70, 0.88, 1.0, 0.92, 0.60],  # C
                [0.65, 0.70, 0.92, 1.0, 0.58],  # D
                [0.50, 0.55, 0.60, 0.58, 1.0],  # E (isolated)
            ]
        )

        unit_ids = ["unit_A", "unit_B", "unit_C", "unit_D", "unit_E"]

        clusters = detector.cluster_duplicates(similarity_matrix, unit_ids)

        # Should find 1 cluster: {A, B, C, D}
        # E is filtered out (singleton)
        assert len(clusters) == 1

        cluster = clusters[0]
        assert cluster.size == 4
        assert set(cluster.unit_ids) == {"unit_A", "unit_B", "unit_C", "unit_D"}

        # Check average similarity
        # Pairs: A-B (0.90), B-C (0.88), C-D (0.92), A-C (0.70), B-D (0.70), A-D (0.65)
        # Average: (0.90 + 0.88 + 0.92 + 0.70 + 0.70 + 0.65) / 6 = 0.7917
        assert cluster.avg_similarity == pytest.approx(0.7917, abs=0.01)

    def test_cluster_duplicates_multiple_clusters(self):
        """Test duplicate clustering with multiple separate clusters."""
        detector = CodeDuplicateDetector(threshold=0.85)

        # Create two separate clusters: {A, B} and {C, D}
        similarity_matrix = np.array(
            [
                [1.0, 0.90, 0.50, 0.45],  # A
                [0.90, 1.0, 0.55, 0.50],  # B
                [0.50, 0.55, 1.0, 0.88],  # C
                [0.45, 0.50, 0.88, 1.0],  # D
            ]
        )

        unit_ids = ["unit_A", "unit_B", "unit_C", "unit_D"]

        clusters = detector.cluster_duplicates(similarity_matrix, unit_ids)

        # Should find 2 clusters
        assert len(clusters) == 2

        # Check cluster sizes (sorted by size descending)
        assert all(c.size == 2 for c in clusters)

        # Check cluster members
        cluster_sets = [set(c.unit_ids) for c in clusters]
        assert {"unit_A", "unit_B"} in cluster_sets
        assert {"unit_C", "unit_D"} in cluster_sets

    def test_cluster_duplicates_filters_singletons(self):
        """Test duplicate clustering filters out singleton clusters."""
        detector = CodeDuplicateDetector(threshold=0.95)

        # No pairs exceed threshold
        similarity_matrix = np.array(
            [
                [1.0, 0.80, 0.75],
                [0.80, 1.0, 0.70],
                [0.75, 0.70, 1.0],
            ]
        )

        unit_ids = ["unit_A", "unit_B", "unit_C"]

        clusters = detector.cluster_duplicates(similarity_matrix, unit_ids)

        # Should find no clusters (all units are singletons)
        assert len(clusters) == 0

    def test_cluster_duplicates_with_threshold_override(self):
        """Test duplicate clustering with threshold override."""
        detector = CodeDuplicateDetector(threshold=0.75)

        similarity_matrix = np.array(
            [
                [1.0, 0.90, 0.85],
                [0.90, 1.0, 0.80],
                [0.85, 0.80, 1.0],
            ]
        )

        unit_ids = ["unit_A", "unit_B", "unit_C"]

        # With high threshold, should find one cluster
        clusters = detector.cluster_duplicates(
            similarity_matrix, unit_ids, threshold=0.78
        )

        assert len(clusters) == 1
        assert set(clusters[0].unit_ids) == {"unit_A", "unit_B", "unit_C"}

        # With very high threshold, should find no clusters
        clusters_high = detector.cluster_duplicates(
            similarity_matrix, unit_ids, threshold=0.95
        )
        assert len(clusters_high) == 0

    def test_cluster_duplicates_validates_dimensions(self):
        """Test duplicate clustering validates matrix dimensions."""
        detector = CodeDuplicateDetector()

        similarity_matrix = np.array(
            [
                [1.0, 0.90],
                [0.90, 1.0],
            ]
        )

        unit_ids = ["unit_A", "unit_B", "unit_C"]  # Mismatch

        with pytest.raises(ValueError, match="Matrix dimensions .* don't match"):
            detector.cluster_duplicates(similarity_matrix, unit_ids)


class TestDuplicatePair:
    """Test suite for DuplicatePair dataclass."""

    def test_duplicate_pair_initialization(self):
        """Test DuplicatePair initializes correctly."""
        pair = DuplicatePair(unit_id_1="unit_A", unit_id_2="unit_B", similarity=0.95)

        assert pair.unit_id_1 == "unit_A"
        assert pair.unit_id_2 == "unit_B"
        assert pair.similarity == 0.95

    def test_duplicate_pair_validates_similarity(self):
        """Test DuplicatePair validates similarity range."""
        with pytest.raises(ValueError, match="Similarity must be in"):
            DuplicatePair(unit_id_1="unit_A", unit_id_2="unit_B", similarity=1.5)

        with pytest.raises(ValueError, match="Similarity must be in"):
            DuplicatePair(unit_id_1="unit_A", unit_id_2="unit_B", similarity=-0.1)


class TestDuplicateCluster:
    """Test suite for DuplicateCluster dataclass."""

    def test_duplicate_cluster_initialization(self):
        """Test DuplicateCluster initializes correctly."""
        cluster = DuplicateCluster(
            unit_ids=["unit_A", "unit_B", "unit_C"], avg_similarity=0.92, size=3
        )

        assert cluster.unit_ids == ["unit_A", "unit_B", "unit_C"]
        assert cluster.avg_similarity == 0.92
        assert cluster.size == 3

    def test_duplicate_cluster_validates_size(self):
        """Test DuplicateCluster validates size matches unit_ids length."""
        with pytest.raises(ValueError, match="Cluster size .* does not match"):
            DuplicateCluster(
                unit_ids=["unit_A", "unit_B"],
                avg_similarity=0.90,
                size=3,  # Mismatch: 2 unit_ids, size=3
            )


class TestEdgeCases:
    """Test suite for edge cases and boundary conditions."""

    def test_single_unit_similarity_matrix(self):
        """Test similarity matrix with single unit."""
        detector = CodeDuplicateDetector()

        embeddings = np.array([[1.0, 2.0, 3.0]])

        similarity_matrix = detector.calculate_similarity_matrix(embeddings)

        assert similarity_matrix.shape == (1, 1)
        assert similarity_matrix[0, 0] == pytest.approx(1.0)

    def test_single_unit_no_pairs(self):
        """Test duplicate pairs with single unit returns empty list."""
        detector = CodeDuplicateDetector()

        similarity_matrix = np.array([[1.0]])
        unit_ids = ["unit_A"]

        pairs = detector.get_duplicate_pairs(similarity_matrix, unit_ids)

        assert len(pairs) == 0

    def test_single_unit_no_clusters(self):
        """Test duplicate clustering with single unit returns empty list."""
        detector = CodeDuplicateDetector()

        similarity_matrix = np.array([[1.0]])
        unit_ids = ["unit_A"]

        clusters = detector.cluster_duplicates(similarity_matrix, unit_ids)

        assert len(clusters) == 0  # Singleton filtered out

    def test_zero_embeddings_handled(self):
        """Test similarity matrix handles zero embeddings."""
        detector = CodeDuplicateDetector()

        # Include zero embedding
        embeddings = np.array(
            [
                [1.0, 0.0, 0.0],
                [0.0, 0.0, 0.0],  # Zero embedding
                [0.0, 1.0, 0.0],
            ]
        )

        similarity_matrix = detector.calculate_similarity_matrix(embeddings)

        # Should not raise error (division by zero handled)
        assert similarity_matrix.shape == (3, 3)
        assert np.all(np.isfinite(similarity_matrix))

    def test_threshold_boundary_conditions(self):
        """Test threshold boundary conditions (exact equality)."""
        detector = CodeDuplicateDetector(threshold=0.85)

        # Create pairs at exact threshold boundary
        similarity_matrix = np.array(
            [
                [1.0, 0.85, 0.849],  # 0.85 included, 0.849 excluded
                [0.85, 1.0, 0.851],  # 0.851 included
                [0.849, 0.851, 1.0],
            ]
        )

        unit_ids = ["unit_A", "unit_B", "unit_C"]

        pairs = detector.get_duplicate_pairs(similarity_matrix, unit_ids)

        # Should find 2 pairs: A-B (0.85), B-C (0.851)
        assert len(pairs) == 2
        assert pairs[0].similarity == pytest.approx(0.851)
        assert pairs[1].similarity == pytest.approx(0.85)
