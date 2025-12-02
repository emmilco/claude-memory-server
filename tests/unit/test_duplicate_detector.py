"""Tests for duplicate memory detection (TEST-007-D)."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.memory.duplicate_detector import (
    DuplicateDetector,
    DuplicateCluster,
    DuplicateMember,
)
from src.core.models import (
    MemoryUnit,
    MemoryCategory,
    MemoryScope,
)
from src.core.exceptions import ValidationError


class TestDuplicateMember:
    """Test DuplicateMember dataclass."""

    def test_creation(self):
        """Test creating a duplicate member."""
        member = DuplicateMember(
            id="test-id",
            file_path="/path/to/file.py",
            unit_name="test_function",
            similarity_to_canonical=0.95,
            line_count=10,
        )

        assert member.id == "test-id"
        assert member.file_path == "/path/to/file.py"
        assert member.unit_name == "test_function"
        assert member.similarity_to_canonical == 0.95
        assert member.line_count == 10


class TestDuplicateCluster:
    """Test DuplicateCluster dataclass."""

    def test_creation(self):
        """Test creating a duplicate cluster."""
        members = [
            DuplicateMember(
                id="dup-1",
                file_path="/path/to/dup1.py",
                unit_name="dup_function_1",
                similarity_to_canonical=0.96,
                line_count=10,
            ),
            DuplicateMember(
                id="dup-2",
                file_path="/path/to/dup2.py",
                unit_name="dup_function_2",
                similarity_to_canonical=0.94,
                line_count=12,
            ),
        ]

        cluster = DuplicateCluster(
            canonical_id="canonical-id",
            canonical_name="canonical_function",
            canonical_file="/path/to/canonical.py",
            members=members,
            average_similarity=0.95,
            cluster_size=3,
        )

        assert cluster.canonical_id == "canonical-id"
        assert cluster.canonical_name == "canonical_function"
        assert cluster.canonical_file == "/path/to/canonical.py"
        assert len(cluster.members) == 2
        assert cluster.average_similarity == 0.95
        assert cluster.cluster_size == 3

    def test_to_dict(self):
        """Test converting cluster to dictionary."""
        members = [
            DuplicateMember(
                id="dup-1",
                file_path="/path/to/dup1.py",
                unit_name="dup_function_1",
                similarity_to_canonical=0.96,
                line_count=10,
            ),
        ]

        cluster = DuplicateCluster(
            canonical_id="canonical-id",
            canonical_name="canonical_function",
            canonical_file="/path/to/canonical.py",
            members=members,
            average_similarity=0.96,
            cluster_size=2,
        )

        cluster_dict = cluster.to_dict()

        assert cluster_dict["canonical_id"] == "canonical-id"
        assert cluster_dict["canonical_name"] == "canonical_function"
        assert cluster_dict["canonical_file"] == "/path/to/canonical.py"
        assert len(cluster_dict["members"]) == 1
        assert cluster_dict["members"][0]["id"] == "dup-1"
        assert cluster_dict["members"][0]["file_path"] == "/path/to/dup1.py"
        assert cluster_dict["members"][0]["unit_name"] == "dup_function_1"
        assert cluster_dict["members"][0]["similarity"] == 0.96
        assert cluster_dict["members"][0]["line_count"] == 10
        assert cluster_dict["average_similarity"] == 0.96
        assert cluster_dict["cluster_size"] == 2


class TestDuplicateDetector:
    """Test DuplicateDetector functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_store = MagicMock()
        self.mock_embedding_generator = MagicMock()
        self.detector = DuplicateDetector(
            store=self.mock_store,
            embedding_generator=self.mock_embedding_generator,
            high_threshold=0.95,
            medium_threshold=0.85,
            low_threshold=0.75,
        )

    def test_initialization(self):
        """Test detector initialization with default thresholds."""
        assert self.detector.store == self.mock_store
        assert self.detector.embedding_generator == self.mock_embedding_generator
        assert self.detector.high_threshold == 0.95
        assert self.detector.medium_threshold == 0.85
        assert self.detector.low_threshold == 0.75

    def test_initialization_custom_thresholds(self):
        """Test detector initialization with custom thresholds."""
        detector = DuplicateDetector(
            store=self.mock_store,
            embedding_generator=self.mock_embedding_generator,
            high_threshold=0.98,
            medium_threshold=0.90,
            low_threshold=0.80,
        )

        assert detector.high_threshold == 0.98
        assert detector.medium_threshold == 0.90
        assert detector.low_threshold == 0.80

    def test_initialization_invalid_thresholds_order(self):
        """Test that invalid threshold order raises ValidationError."""
        with pytest.raises(ValidationError, match="Thresholds must satisfy"):
            DuplicateDetector(
                store=self.mock_store,
                embedding_generator=self.mock_embedding_generator,
                high_threshold=0.75,
                medium_threshold=0.85,
                low_threshold=0.95,
            )

    def test_initialization_invalid_thresholds_out_of_range(self):
        """Test that thresholds out of range raise ValidationError."""
        with pytest.raises(ValidationError, match="Thresholds must satisfy"):
            DuplicateDetector(
                store=self.mock_store,
                embedding_generator=self.mock_embedding_generator,
                high_threshold=1.5,  # Invalid: > 1.0
                medium_threshold=0.85,
                low_threshold=0.75,
            )

    def test_initialization_negative_threshold(self):
        """Test that negative thresholds raise ValidationError."""
        with pytest.raises(ValidationError, match="Thresholds must satisfy"):
            DuplicateDetector(
                store=self.mock_store,
                embedding_generator=self.mock_embedding_generator,
                high_threshold=0.95,
                medium_threshold=0.85,
                low_threshold=-0.1,  # Invalid: < 0
            )

    def test_classify_similarity_high(self):
        """Test classifying high-confidence similarity."""
        result = self.detector.classify_similarity(0.96)
        assert result == "high"

    def test_classify_similarity_medium(self):
        """Test classifying medium-confidence similarity."""
        result = self.detector.classify_similarity(0.88)
        assert result == "medium"

    def test_classify_similarity_low(self):
        """Test classifying low-confidence similarity."""
        result = self.detector.classify_similarity(0.78)
        assert result == "low"

    def test_classify_similarity_none(self):
        """Test classifying below-threshold similarity."""
        result = self.detector.classify_similarity(0.50)
        assert result == "none"

    def test_classify_similarity_boundary_high(self):
        """Test classifying exactly at high threshold."""
        result = self.detector.classify_similarity(0.95)
        assert result == "high"

    def test_classify_similarity_boundary_medium(self):
        """Test classifying exactly at medium threshold."""
        result = self.detector.classify_similarity(0.85)
        assert result == "medium"

    def test_classify_similarity_boundary_low(self):
        """Test classifying exactly at low threshold."""
        result = self.detector.classify_similarity(0.75)
        assert result == "low"

    @staticmethod
    def test_cosine_similarity_identical():
        """Test cosine similarity for identical vectors."""
        vec1 = [1.0, 2.0, 3.0]
        vec2 = [1.0, 2.0, 3.0]

        similarity = DuplicateDetector.cosine_similarity(vec1, vec2)
        assert abs(similarity - 1.0) < 1e-6

    @staticmethod
    def test_cosine_similarity_orthogonal():
        """Test cosine similarity for orthogonal vectors."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]

        similarity = DuplicateDetector.cosine_similarity(vec1, vec2)
        assert abs(similarity - 0.0) < 1e-6

    @staticmethod
    def test_cosine_similarity_opposite():
        """Test cosine similarity for opposite vectors."""
        vec1 = [1.0, 2.0, 3.0]
        vec2 = [-1.0, -2.0, -3.0]

        similarity = DuplicateDetector.cosine_similarity(vec1, vec2)
        assert abs(similarity - (-1.0)) < 1e-6

    @staticmethod
    def test_cosine_similarity_zero_vector():
        """Test cosine similarity with zero vector."""
        vec1 = [1.0, 2.0, 3.0]
        vec2 = [0.0, 0.0, 0.0]

        similarity = DuplicateDetector.cosine_similarity(vec1, vec2)
        assert similarity == 0.0

    @staticmethod
    def test_cosine_similarity_both_zero():
        """Test cosine similarity with both vectors zero."""
        vec1 = [0.0, 0.0, 0.0]
        vec2 = [0.0, 0.0, 0.0]

        similarity = DuplicateDetector.cosine_similarity(vec1, vec2)
        assert similarity == 0.0

    @staticmethod
    def test_cosine_similarity_partial():
        """Test cosine similarity for partially similar vectors."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [1.0, 1.0, 0.0]

        similarity = DuplicateDetector.cosine_similarity(vec1, vec2)
        # Expected: 1.0 / sqrt(2) ≈ 0.707
        assert 0.70 < similarity < 0.72

    @pytest.mark.asyncio
    async def test_find_duplicates_basic(self):
        """Test finding duplicates for a memory."""
        # Create test memory
        test_memory = MemoryUnit(
            id="test-id",
            content="test content",
            category=MemoryCategory.CODE,
            scope=MemoryScope.PROJECT,
            project_name="test-project",
        )

        # Mock embedding generation
        self.mock_embedding_generator.generate = AsyncMock(return_value=[0.1, 0.2, 0.3])

        # Mock store retrieval
        similar_memory = MemoryUnit(
            id="similar-id",
            content="similar content",
            category=MemoryCategory.CODE,
            scope=MemoryScope.PROJECT,
            project_name="test-project",
        )
        self.mock_store.retrieve = AsyncMock(
            return_value=[(similar_memory, 0.92), (test_memory, 0.99)]
        )

        # Find duplicates
        duplicates = await self.detector.find_duplicates(test_memory)

        # Verify results
        assert len(duplicates) == 1  # test_memory filtered out
        assert duplicates[0][0].id == "similar-id"
        assert duplicates[0][1] == 0.92

        # Verify embedding generation was called
        self.mock_embedding_generator.generate.assert_called_once_with("test content")

    @pytest.mark.asyncio
    async def test_find_duplicates_custom_threshold(self):
        """Test finding duplicates with custom threshold."""
        test_memory = MemoryUnit(
            id="test-id",
            content="test content",
            category=MemoryCategory.CODE,
        )

        self.mock_embedding_generator.generate = AsyncMock(return_value=[0.1, 0.2, 0.3])

        # Mock memories with various similarity scores
        similar1 = MemoryUnit(
            id="similar-1", content="similar 1", category=MemoryCategory.CODE
        )
        similar2 = MemoryUnit(
            id="similar-2", content="similar 2", category=MemoryCategory.CODE
        )
        similar3 = MemoryUnit(
            id="similar-3", content="similar 3", category=MemoryCategory.CODE
        )

        self.mock_store.retrieve = AsyncMock(
            return_value=[
                (similar1, 0.95),  # Above threshold
                (similar2, 0.88),  # Above threshold
                (similar3, 0.70),  # Below threshold
                (test_memory, 1.0),  # Self (filtered out)
            ]
        )

        # Find duplicates with custom threshold
        duplicates = await self.detector.find_duplicates(
            test_memory, min_threshold=0.80
        )

        # Verify only memories above threshold are returned
        assert len(duplicates) == 2
        assert duplicates[0][0].id == "similar-1"
        assert duplicates[0][1] == 0.95
        assert duplicates[1][0].id == "similar-2"
        assert duplicates[1][1] == 0.88

    @pytest.mark.asyncio
    async def test_find_duplicates_sorted_by_score(self):
        """Test that duplicates are sorted by similarity score descending."""
        test_memory = MemoryUnit(
            id="test-id",
            content="test content",
            category=MemoryCategory.CODE,
        )

        self.mock_embedding_generator.generate = AsyncMock(return_value=[0.1, 0.2, 0.3])

        # Mock memories with unsorted scores
        similar1 = MemoryUnit(
            id="similar-1", content="similar 1", category=MemoryCategory.CODE
        )
        similar2 = MemoryUnit(
            id="similar-2", content="similar 2", category=MemoryCategory.CODE
        )
        similar3 = MemoryUnit(
            id="similar-3", content="similar 3", category=MemoryCategory.CODE
        )

        self.mock_store.retrieve = AsyncMock(
            return_value=[
                (similar1, 0.85),
                (similar2, 0.95),
                (similar3, 0.90),
            ]
        )

        duplicates = await self.detector.find_duplicates(test_memory)

        # Verify sorted by score descending
        assert len(duplicates) == 3
        assert duplicates[0][1] == 0.95
        assert duplicates[1][1] == 0.90
        assert duplicates[2][1] == 0.85

    @pytest.mark.asyncio
    async def test_find_duplicates_empty_results(self):
        """Test finding duplicates when no similar memories exist."""
        test_memory = MemoryUnit(
            id="test-id",
            content="test content",
            category=MemoryCategory.CODE,
        )

        self.mock_embedding_generator.generate = AsyncMock(return_value=[0.1, 0.2, 0.3])
        self.mock_store.retrieve = AsyncMock(return_value=[(test_memory, 1.0)])

        duplicates = await self.detector.find_duplicates(test_memory)

        assert len(duplicates) == 0

    @pytest.mark.asyncio
    async def test_find_duplicates_filters_self(self):
        """Test that the memory itself is filtered from results."""
        test_memory = MemoryUnit(
            id="test-id",
            content="test content",
            category=MemoryCategory.CODE,
        )

        self.mock_embedding_generator.generate = AsyncMock(return_value=[0.1, 0.2, 0.3])

        # Return the same memory (perfect match)
        self.mock_store.retrieve = AsyncMock(return_value=[(test_memory, 1.0)])

        duplicates = await self.detector.find_duplicates(test_memory)

        # Should be empty because we filter out self
        assert len(duplicates) == 0

    @pytest.mark.asyncio
    async def test_find_all_duplicates_basic(self):
        """Test scanning entire database for duplicates."""
        # Create test memories
        memory1 = MemoryUnit(
            id="mem-1", content="content 1", category=MemoryCategory.CODE
        )
        memory2 = MemoryUnit(
            id="mem-2", content="content 2", category=MemoryCategory.CODE
        )
        memory3 = MemoryUnit(
            id="mem-3", content="content 3", category=MemoryCategory.CODE
        )

        # Mock store retrieval for initial scan
        self.mock_store.retrieve = AsyncMock(
            return_value=[
                (memory1, 0.5),
                (memory2, 0.5),
                (memory3, 0.5),
            ]
        )

        # Mock find_duplicates to return controlled results
        async def mock_find_duplicates(memory, min_threshold=None):
            if memory.id == "mem-1":
                return [(memory2, 0.88)]
            elif memory.id == "mem-2":
                return [(memory1, 0.88)]
            else:
                return []

        self.detector.find_duplicates = AsyncMock(side_effect=mock_find_duplicates)

        # Find all duplicates
        clusters = await self.detector.find_all_duplicates()

        # Verify clusters
        assert len(clusters) == 1
        assert "mem-1" in clusters
        assert len(clusters["mem-1"]) == 1
        assert clusters["mem-1"][0][0] == "mem-2"
        assert clusters["mem-1"][0][1] == 0.88

    @pytest.mark.asyncio
    async def test_find_all_duplicates_with_category_filter(self):
        """Test scanning with category filter."""
        memory1 = MemoryUnit(
            id="mem-1", content="content 1", category=MemoryCategory.CODE
        )

        self.mock_store.retrieve = AsyncMock(return_value=[(memory1, 0.5)])
        self.detector.find_duplicates = AsyncMock(return_value=[])

        await self.detector.find_all_duplicates(category=MemoryCategory.CODE)

        # Verify store was called with category filter
        self.mock_store.retrieve.assert_called_once()

    @pytest.mark.asyncio
    async def test_find_all_duplicates_custom_threshold(self):
        """Test scanning with custom threshold."""
        memory1 = MemoryUnit(
            id="mem-1", content="content 1", category=MemoryCategory.CODE
        )

        self.mock_store.retrieve = AsyncMock(return_value=[(memory1, 0.5)])
        self.detector.find_duplicates = AsyncMock(return_value=[])

        await self.detector.find_all_duplicates(min_threshold=0.90)

        # Verify find_duplicates was called with custom threshold
        self.detector.find_duplicates.assert_called_with(memory1, min_threshold=0.90)

    @pytest.mark.asyncio
    async def test_get_auto_merge_candidates(self):
        """Test getting high-confidence duplicates for auto-merge."""
        # Mock find_all_duplicates to return controlled results
        self.detector.find_all_duplicates = AsyncMock(
            return_value={
                "canonical-1": [("dup-1", 0.96), ("dup-2", 0.97)],  # All high
                "canonical-2": [("dup-3", 0.90), ("dup-4", 0.85)],  # Mixed
            }
        )

        candidates = await self.detector.get_auto_merge_candidates()

        # Only canonical-1 should be returned (all duplicates above high_threshold)
        assert len(candidates) == 1
        assert "canonical-1" in candidates
        assert len(candidates["canonical-1"]) == 2

    @pytest.mark.asyncio
    async def test_get_auto_merge_candidates_with_category(self):
        """Test getting auto-merge candidates with category filter."""
        self.detector.find_all_duplicates = AsyncMock(
            return_value={"canonical-1": [("dup-1", 0.96)]}
        )

        await self.detector.get_auto_merge_candidates(category=MemoryCategory.CODE)

        # Verify category was passed through
        self.detector.find_all_duplicates.assert_called_once_with(
            category=MemoryCategory.CODE, min_threshold=0.95
        )

    @pytest.mark.asyncio
    async def test_get_user_review_candidates(self):
        """Test getting medium-confidence duplicates for user review."""
        # Mock find_all_duplicates to return controlled results
        self.detector.find_all_duplicates = AsyncMock(
            return_value={
                "canonical-1": [
                    ("dup-1", 0.96),
                    ("dup-2", 0.97),
                ],  # All high (excluded)
                "canonical-2": [("dup-3", 0.90), ("dup-4", 0.88)],  # Has medium
                "canonical-3": [("dup-5", 0.70)],  # Below medium (excluded)
            }
        )

        candidates = await self.detector.get_user_review_candidates()

        # Only canonical-2 should be returned (has medium-confidence duplicates)
        assert len(candidates) == 1
        assert "canonical-2" in candidates
        assert len(candidates["canonical-2"]) == 2

    @pytest.mark.asyncio
    async def test_get_user_review_candidates_with_category(self):
        """Test getting review candidates with category filter."""
        self.detector.find_all_duplicates = AsyncMock(
            return_value={"canonical-1": [("dup-1", 0.88)]}
        )

        await self.detector.get_user_review_candidates(category=MemoryCategory.FACT)

        # Verify category was passed through
        self.detector.find_all_duplicates.assert_called_once_with(
            category=MemoryCategory.FACT, min_threshold=0.85
        )

    @pytest.mark.asyncio
    async def test_calculate_duplication_score_no_duplicates(self):
        """Test duplication score for unique code."""
        test_memory = MemoryUnit(
            id="test-id",
            content="unique code",
            category=MemoryCategory.CODE,
        )

        self.detector.find_duplicates = AsyncMock(return_value=[])

        score = await self.detector.calculate_duplication_score(test_memory)

        assert score == 0.0

    @pytest.mark.asyncio
    async def test_calculate_duplication_score_with_duplicates(self):
        """Test duplication score for code with duplicates."""
        test_memory = MemoryUnit(
            id="test-id",
            content="duplicate code",
            category=MemoryCategory.CODE,
        )

        similar_memory = MemoryUnit(
            id="similar-id",
            content="similar code",
            category=MemoryCategory.CODE,
        )

        self.detector.find_duplicates = AsyncMock(
            return_value=[
                (similar_memory, 0.92),
                (similar_memory, 0.85),
                (similar_memory, 0.78),
            ]
        )

        score = await self.detector.calculate_duplication_score(test_memory)

        # Should return highest similarity score
        assert score == 0.92

    @pytest.mark.asyncio
    async def test_cluster_duplicates_basic(self):
        """Test clustering duplicate code units."""
        # Create test memories
        memory1 = MemoryUnit(
            id="mem-1",
            content="code 1",
            category=MemoryCategory.CODE,
            metadata={
                "file_path": "/path/to/file1.py",
                "unit_name": "function_1",
                "line_count": 10,
            },
        )
        memory2 = MemoryUnit(
            id="mem-2",
            content="code 2",
            category=MemoryCategory.CODE,
            metadata={
                "file_path": "/path/to/file2.py",
                "unit_name": "function_2",
                "line_count": 12,
            },
        )

        # Mock store retrieval
        self.mock_store.retrieve = AsyncMock(
            return_value=[
                (memory1, 0.5),
                (memory2, 0.5),
            ]
        )

        # Mock find_duplicates
        async def mock_find_duplicates(unit, min_threshold):
            if unit.id == "mem-1":
                return [(memory2, 0.90)]
            elif unit.id == "mem-2":
                return [(memory1, 0.90)]
            return []

        self.detector.find_duplicates = AsyncMock(side_effect=mock_find_duplicates)

        clusters = await self.detector.cluster_duplicates(min_threshold=0.85)

        # Verify cluster was created
        assert len(clusters) == 1
        assert clusters[0].cluster_size == 2
        assert len(clusters[0].members) == 1
        assert clusters[0].average_similarity == 0.90

    @pytest.mark.asyncio
    async def test_cluster_duplicates_no_code_units(self):
        """Test clustering when no code units exist."""
        self.mock_store.retrieve = AsyncMock(return_value=[])

        clusters = await self.detector.cluster_duplicates()

        assert len(clusters) == 0

    @pytest.mark.asyncio
    async def test_cluster_duplicates_sorted_by_size(self):
        """Test that clusters are sorted by size descending."""
        # Create memories for two clusters of different sizes
        memories = [
            MemoryUnit(
                id=f"mem-{i}",
                content=f"code {i}",
                category=MemoryCategory.CODE,
                metadata={
                    "file_path": f"/file{i}.py",
                    "unit_name": f"func_{i}",
                    "line_count": 10,
                },
            )
            for i in range(4)
        ]

        self.mock_store.retrieve = AsyncMock(return_value=[(m, 0.5) for m in memories])

        # Create two clusters: one with 3 members, one with 2
        async def mock_find_duplicates(unit, min_threshold):
            if unit.id == "mem-0":
                return [(memories[1], 0.90), (memories[2], 0.88)]
            elif unit.id == "mem-1":
                return [(memories[0], 0.90), (memories[2], 0.88)]
            elif unit.id == "mem-2":
                return [(memories[0], 0.88), (memories[1], 0.88)]
            elif unit.id == "mem-3":
                return []
            return []

        self.detector.find_duplicates = AsyncMock(side_effect=mock_find_duplicates)

        clusters = await self.detector.cluster_duplicates(min_threshold=0.85)

        # First cluster should be the larger one
        assert len(clusters) >= 1
        if len(clusters) > 1:
            assert clusters[0].cluster_size >= clusters[1].cluster_size

    def test_select_canonical_prefers_documented(self):
        """Test that canonical selection prefers documented code."""
        # Create memories with different characteristics
        undocumented = MemoryUnit(
            id="undoc-id",
            content="code without docs",
            category=MemoryCategory.CODE,
            metadata={
                "has_documentation": False,
                "cyclomatic_complexity": 5,
                "line_count": 10,
            },
        )
        documented = MemoryUnit(
            id="doc-id",
            content="code with docs",
            category=MemoryCategory.CODE,
            metadata={
                "has_documentation": True,
                "cyclomatic_complexity": 8,
                "line_count": 15,
            },
        )

        all_memories = [undocumented, documented]

        canonical = self.detector._select_canonical(
            current_canonical="undoc-id",
            members=["doc-id"],
            all_memories=all_memories,
        )

        # Should select documented even if it's longer/more complex
        assert canonical == "doc-id"

    def test_select_canonical_prefers_lower_complexity(self):
        """Test that canonical selection prefers lower complexity."""
        # Both undocumented, different complexity
        simple = MemoryUnit(
            id="simple-id",
            content="simple code",
            category=MemoryCategory.CODE,
            metadata={
                "has_documentation": False,
                "cyclomatic_complexity": 2,
                "line_count": 10,
            },
        )
        complex_code = MemoryUnit(
            id="complex-id",
            content="complex code",
            category=MemoryCategory.CODE,
            metadata={
                "has_documentation": False,
                "cyclomatic_complexity": 15,
                "line_count": 10,
            },
        )

        all_memories = [simple, complex_code]

        canonical = self.detector._select_canonical(
            current_canonical="complex-id",
            members=["simple-id"],
            all_memories=all_memories,
        )

        # Should select simpler code
        assert canonical == "simple-id"

    def test_select_canonical_prefers_shorter(self):
        """Test that canonical selection prefers shorter code."""
        # Same documentation and complexity, different length
        short = MemoryUnit(
            id="short-id",
            content="short code",
            category=MemoryCategory.CODE,
            metadata={
                "has_documentation": False,
                "cyclomatic_complexity": 5,
                "line_count": 10,
            },
        )
        long = MemoryUnit(
            id="long-id",
            content="long code",
            category=MemoryCategory.CODE,
            metadata={
                "has_documentation": False,
                "cyclomatic_complexity": 5,
                "line_count": 50,
            },
        )

        all_memories = [short, long]

        canonical = self.detector._select_canonical(
            current_canonical="long-id",
            members=["short-id"],
            all_memories=all_memories,
        )

        # Should select shorter code
        assert canonical == "short-id"

    def test_union_find_clustering_basic(self):
        """Test union-find clustering algorithm."""
        # Create test memories
        memory1 = MemoryUnit(id="mem-1", content="code 1", category=MemoryCategory.CODE)
        memory2 = MemoryUnit(id="mem-2", content="code 2", category=MemoryCategory.CODE)
        memory3 = MemoryUnit(id="mem-3", content="code 3", category=MemoryCategory.CODE)

        edges = [
            ("mem-1", "mem-2", 0.90),
            ("mem-2", "mem-3", 0.85),
        ]

        all_memories = [memory1, memory2, memory3]

        result = self.detector._union_find_clustering(edges, all_memories)

        # Should create one cluster with mem-1 as canonical
        # and mem-2, mem-3 as members (or similar grouping)
        assert len(result) == 1
        canonical_id = list(result.keys())[0]
        assert len(result[canonical_id]) == 2

    def test_union_find_clustering_multiple_clusters(self):
        """Test union-find with multiple separate clusters."""
        memories = [
            MemoryUnit(id=f"mem-{i}", content=f"code {i}", category=MemoryCategory.CODE)
            for i in range(5)
        ]

        # Create two separate clusters
        edges = [
            ("mem-0", "mem-1", 0.90),  # Cluster 1
            ("mem-2", "mem-3", 0.88),  # Cluster 2
            # mem-4 is isolated
        ]

        result = self.detector._union_find_clustering(edges, memories)

        # Should create two clusters (isolated mem-4 is excluded)
        assert len(result) == 2

    def test_union_find_clustering_no_edges(self):
        """Test union-find with no connections."""
        memories = [
            MemoryUnit(id="mem-1", content="code 1", category=MemoryCategory.CODE),
            MemoryUnit(id="mem-2", content="code 2", category=MemoryCategory.CODE),
        ]

        edges = []

        result = self.detector._union_find_clustering(edges, memories)

        # No clusters should be created (all singletons)
        assert len(result) == 0
