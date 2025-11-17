"""Relationship detection between memories (FEAT-034 Phase 3)."""

import logging
import re
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, UTC, timedelta

from src.core.models import MemoryUnit, MemoryRelationship, RelationshipType, MemoryCategory
from src.store.base import MemoryStore
from src.embeddings.generator import EmbeddingGenerator

logger = logging.getLogger(__name__)


class RelationshipDetector:
    """
    Detect and manage relationships between memories.

    Detects:
    - Contradictions (conflicting preferences/facts)
    - Duplicates (similar content)
    - Supporting relationships (reinforcing info)
    - Supersession (newer replaces older)
    """

    def __init__(self, store: MemoryStore, embedding_generator: Optional[EmbeddingGenerator] = None):
        """
        Initialize the relationship detector.

        Args:
            store: Memory store for reading memories
            embedding_generator: Optional embedding generator (creates one if not provided)
        """
        self.store = store
        self.embedding_generator = embedding_generator or EmbeddingGenerator()
        logger.info("RelationshipDetector initialized")

    async def detect_contradictions(
        self,
        new_memory: MemoryUnit,
        existing_memories: Optional[List[MemoryUnit]] = None
    ) -> List[MemoryRelationship]:
        """
        Detect if new memory contradicts existing ones.

        Special logic for preferences:
        - "I prefer X" vs "I prefer Y" (X != Y)
        - Framework/tool conflicts
        - Coding style conflicts

        Args:
            new_memory: Newly created memory
            existing_memories: Existing memories to check against (fetches all if None)

        Returns:
            List of contradiction relationships
        """
        try:
            # Only check for contradictions in preferences and facts
            if new_memory.category not in [MemoryCategory.PREFERENCE, MemoryCategory.FACT]:
                return []

            # Fetch existing memories if not provided
            if existing_memories is None:
                from src.core.models import SearchFilters
                filters = SearchFilters(
                    category=new_memory.category,
                    scope=new_memory.scope,
                    project_name=new_memory.project_name
                )
                results = await self.store.retrieve(
                    query_embedding=await self.embedding_generator.generate(new_memory.content),
                    filters=filters,
                    limit=50
                )
                existing_memories = [mem for mem, _ in results]

            contradictions = []

            # Check each existing memory
            for existing in existing_memories:
                if existing.id == new_memory.id:
                    continue

                # Detect contradiction
                is_contradiction, confidence, reason = await self._detect_preference_contradiction(
                    new_memory, existing
                )

                if is_contradiction:
                    relationship = MemoryRelationship(
                        source_memory_id=new_memory.id,
                        target_memory_id=existing.id,
                        relationship_type=RelationshipType.CONTRADICTS,
                        confidence=confidence,
                        detected_by="auto",
                        notes=reason
                    )
                    contradictions.append(relationship)

                    logger.info(
                        f"Detected contradiction: {new_memory.id[:8]} <-> {existing.id[:8]} "
                        f"(confidence={confidence:.2f}, reason={reason})"
                    )

            return contradictions

        except Exception as e:
            logger.error(f"Error detecting contradictions: {e}")
            return []

    async def _detect_preference_contradiction(
        self,
        memory_a: MemoryUnit,
        memory_b: MemoryUnit
    ) -> Tuple[bool, float, str]:
        """
        Detect if two preference memories contradict each other.

        Returns:
            Tuple of (is_contradiction, confidence, reason)
        """
        # Patterns for preference extraction
        preference_patterns = [
            r"(?:i\s+)?prefer\s+(\w+(?:\s+\w+)?)",
            r"(?:i\s+)?like\s+(\w+(?:\s+\w+)?)",
            r"(?:i\s+)?use\s+(\w+(?:\s+\w+)?)",
            r"always\s+use\s+(\w+(?:\s+\w+)?)",
            r"never\s+use\s+(\w+(?:\s+\w+)?)",
            r"(?:i\s+)?choose\s+(\w+(?:\s+\w+)?)",
        ]

        content_a = memory_a.content.lower()
        content_b = memory_b.content.lower()

        # Extract preferences from both memories
        prefs_a = []
        prefs_b = []

        for pattern in preference_patterns:
            prefs_a.extend(re.findall(pattern, content_a))
            prefs_b.extend(re.findall(pattern, content_b))

        if not prefs_a or not prefs_b:
            return False, 0.0, "no_preferences_found"

        # Check for conflicting frameworks/tools
        conflicts = self._check_framework_conflicts(prefs_a, prefs_b)
        if conflicts:
            # Check temporal separation
            time_gap = abs((memory_a.created_at - memory_b.created_at).days)
            if time_gap > 30:  # Significant time gap suggests preference changed
                confidence = min(0.9, 0.7 + (time_gap / 365) * 0.2)  # Higher confidence for larger gaps
                return True, confidence, f"conflicting_preferences: {conflicts}"

        # Check for explicit negation patterns
        negation_patterns = [
            (r"i\s+prefer\s+(\w+)", r"i\s+don't\s+(?:prefer|like)\s+\1"),
            (r"always\s+use\s+(\w+)", r"never\s+use\s+\1"),
        ]

        for positive_pattern, negative_pattern in negation_patterns:
            positive_match = re.search(positive_pattern, content_a)
            if positive_match:
                term = positive_match.group(1)
                if re.search(negative_pattern.replace(r"\1", term), content_b):
                    return True, 0.95, f"explicit_negation: {term}"

        return False, 0.0, "no_contradiction"

    def _check_framework_conflicts(self, prefs_a: List[str], prefs_b: List[str]) -> Optional[str]:
        """
        Check if preferences contain conflicting frameworks/tools.

        Args:
            prefs_a: Preferences from memory A
            prefs_b: Preferences from memory B

        Returns:
            Conflict description or None
        """
        # Known mutually exclusive framework groups
        framework_groups = {
            "frontend": ["react", "vue", "angular", "svelte", "solid"],
            "backend": ["express", "fastapi", "django", "flask", "nest"],
            "database": ["postgres", "mysql", "mongodb", "sqlite"],
            "testing": ["jest", "vitest", "mocha", "jasmine"],
            "bundler": ["webpack", "vite", "rollup", "parcel", "esbuild"],
            "package_manager": ["npm", "yarn", "pnpm"],
        }

        # Check each group
        for group_name, frameworks in framework_groups.items():
            found_a = [f for f in frameworks if any(f in pref for pref in prefs_a)]
            found_b = [f for f in frameworks if any(f in pref for pref in prefs_b)]

            if found_a and found_b and found_a[0] != found_b[0]:
                return f"{group_name}: {found_a[0]} vs {found_b[0]}"

        return None

    async def detect_duplicates(
        self,
        new_memory: MemoryUnit,
        similarity_threshold: float = 0.9
    ) -> List[MemoryRelationship]:
        """
        Detect duplicate/similar memories.

        Args:
            new_memory: Memory to check
            similarity_threshold: Similarity threshold for duplicates

        Returns:
            List of duplicate relationships
        """
        try:
            # Generate embedding for new memory
            embedding = await self.embedding_generator.generate(new_memory.content)

            # Search for similar memories
            from src.core.models import SearchFilters
            filters = SearchFilters(
                category=new_memory.category,
                scope=new_memory.scope,
                project_name=new_memory.project_name
            )

            similar_results = await self.store.retrieve(
                query_embedding=embedding,
                filters=filters,
                limit=20
            )

            duplicates = []

            for similar_memory, score in similar_results:
                if similar_memory.id == new_memory.id:
                    continue

                if score >= similarity_threshold:
                    relationship = MemoryRelationship(
                        source_memory_id=new_memory.id,
                        target_memory_id=similar_memory.id,
                        relationship_type=RelationshipType.DUPLICATE,
                        confidence=score,
                        detected_by="auto",
                        notes=f"Semantic similarity: {score:.3f}"
                    )
                    duplicates.append(relationship)

                    logger.debug(
                        f"Detected duplicate: {new_memory.id[:8]} <-> {similar_memory.id[:8]} "
                        f"(similarity={score:.3f})"
                    )

            return duplicates

        except Exception as e:
            logger.error(f"Error detecting duplicates: {e}")
            return []

    async def detect_support(
        self,
        memory_a: MemoryUnit,
        memory_b: MemoryUnit
    ) -> Optional[MemoryRelationship]:
        """
        Detect if memories support/reinforce each other.

        Args:
            memory_a: First memory
            memory_b: Second memory

        Returns:
            Support relationship if detected
        """
        try:
            # Check if memories are in the same category and related
            if memory_a.category != memory_b.category:
                return None

            # Calculate semantic similarity
            embedding_a = await self.embedding_generator.generate(memory_a.content)
            embedding_b = await self.embedding_generator.generate(memory_b.content)

            # Use cosine similarity
            from src.memory.duplicate_detector import DuplicateDetector
            similarity = DuplicateDetector.cosine_similarity(embedding_a, embedding_b)

            # Support if similar but not duplicate
            if 0.7 <= similarity < 0.85:
                relationship = MemoryRelationship(
                    source_memory_id=memory_a.id,
                    target_memory_id=memory_b.id,
                    relationship_type=RelationshipType.SUPPORTS,
                    confidence=similarity,
                    detected_by="auto",
                    notes=f"Supporting evidence (similarity={similarity:.3f})"
                )
                return relationship

            return None

        except Exception as e:
            logger.error(f"Error detecting support: {e}")
            return None

    async def scan_for_contradictions(
        self,
        category: Optional[MemoryCategory] = None
    ) -> List[Tuple[MemoryUnit, MemoryUnit, float]]:
        """
        Scan all memories for contradictions.

        Args:
            category: Optional category filter

        Returns:
            List of (memory_a, memory_b, confidence) tuples
        """
        try:
            # Get all memories in category
            from src.core.models import SearchFilters
            filters = SearchFilters(category=category) if category else None

            all_results = await self.store.retrieve(
                query_embedding=[0.0] * 384,  # Dummy embedding
                filters=filters,
                limit=1000
            )
            all_memories = [mem for mem, _ in all_results]

            logger.info(f"Scanning {len(all_memories)} memories for contradictions...")

            contradictions = []

            # Check each pair (n^2 complexity - optimize in production)
            for i, memory_a in enumerate(all_memories):
                for memory_b in all_memories[i+1:]:
                    # Skip if different scopes/projects
                    if memory_a.scope != memory_b.scope:
                        continue
                    if memory_a.project_name != memory_b.project_name:
                        continue

                    # Check for contradiction
                    is_contradiction, confidence, _ = await self._detect_preference_contradiction(
                        memory_a, memory_b
                    )

                    if is_contradiction:
                        contradictions.append((memory_a, memory_b, confidence))

            logger.info(f"Found {len(contradictions)} contradictions")
            return contradictions

        except Exception as e:
            logger.error(f"Error scanning for contradictions: {e}")
            return []

    async def detect_supersession(
        self,
        new_memory: MemoryUnit,
        existing_memories: Optional[List[MemoryUnit]] = None
    ) -> List[MemoryRelationship]:
        """
        Detect if new memory supersedes (replaces) older memories.

        A memory supersedes another if:
        - Very similar content (>0.9 similarity)
        - Newer creation date
        - Higher confidence or verified status

        Args:
            new_memory: New memory
            existing_memories: Existing memories to check

        Returns:
            List of supersession relationships
        """
        try:
            # Fetch existing memories if not provided
            if existing_memories is None:
                embedding = await self.embedding_generator.generate(new_memory.content)
                from src.core.models import SearchFilters
                filters = SearchFilters(
                    category=new_memory.category,
                    scope=new_memory.scope,
                    project_name=new_memory.project_name
                )
                results = await self.store.retrieve(
                    query_embedding=embedding,
                    filters=filters,
                    limit=20
                )
                existing_memories = [mem for mem, score in results if score > 0.9]

            supersessions = []

            for existing in existing_memories:
                if existing.id == new_memory.id:
                    continue

                # Check supersession criteria
                is_newer = new_memory.created_at > existing.created_at
                is_better = (
                    new_memory.provenance.confidence > existing.provenance.confidence or
                    (new_memory.provenance.verified and not existing.provenance.verified)
                )

                if is_newer and is_better:
                    # Calculate confidence in supersession
                    time_gap_days = (new_memory.created_at - existing.created_at).days
                    confidence_gap = new_memory.provenance.confidence - existing.provenance.confidence

                    supersession_confidence = min(0.95, 0.7 + confidence_gap * 0.3 + (time_gap_days / 365) * 0.1)

                    relationship = MemoryRelationship(
                        source_memory_id=new_memory.id,
                        target_memory_id=existing.id,
                        relationship_type=RelationshipType.SUPERSEDES,
                        confidence=supersession_confidence,
                        detected_by="auto",
                        notes=f"Newer and higher confidence (gap={time_gap_days}d)"
                    )
                    supersessions.append(relationship)

            return supersessions

        except Exception as e:
            logger.error(f"Error detecting supersession: {e}")
            return []
