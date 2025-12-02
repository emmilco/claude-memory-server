"""Provenance tracking for memory operations (FEAT-034 Phase 2)."""

import logging
from datetime import datetime, UTC, timedelta
from typing import Dict, Any, Optional

from src.core.models import MemoryProvenance, ProvenanceSource, MemoryUnit
from src.store.base import MemoryStore
from src.config import DEFAULT_EMBEDDING_DIM

logger = logging.getLogger(__name__)


class ProvenanceTracker:
    """
    Track and manage memory provenance metadata.

    Responsible for:
    - Capturing provenance when memories are created
    - Updating access timestamps
    - Managing verification status
    - Calculating confidence scores
    """

    def __init__(self, store: MemoryStore):
        """
        Initialize the provenance tracker.

        Args:
            store: Memory store for updating provenance data
        """
        self.store = store
        logger.info("ProvenanceTracker initialized")

    async def capture_provenance(
        self, content: str, source: ProvenanceSource, context: Dict[str, Any]
    ) -> MemoryProvenance:
        """
        Capture provenance metadata for a new memory.

        Args:
            content: Memory content
            source: Source of memory creation
            context: Contextual information (conversation_id, file_context, etc.)

        Returns:
            MemoryProvenance object
        """
        try:
            # Determine created_by based on source
            created_by = self._determine_created_by(source, context)

            # Calculate initial confidence based on source
            confidence = self._calculate_source_confidence(source)

            # Extract context information
            conversation_id = context.get("conversation_id")
            file_context = context.get("file_context", [])
            notes = context.get("notes")

            provenance = MemoryProvenance(
                source=source,
                created_by=created_by,
                confidence=confidence,
                verified=False,
                conversation_id=conversation_id,
                file_context=file_context,
                notes=notes,
            )

            logger.debug(
                f"Captured provenance: source={source.value}, "
                f"confidence={confidence:.2f}, created_by={created_by}"
            )
            return provenance

        except Exception as e:
            logger.error(f"Error capturing provenance: {e}")
            # Return default provenance on error
            return MemoryProvenance()

    def _determine_created_by(
        self, source: ProvenanceSource, context: Dict[str, Any]
    ) -> str:
        """
        Determine the created_by value based on source and context.

        Args:
            source: Provenance source
            context: Additional context

        Returns:
            Created by description
        """
        if source == ProvenanceSource.USER_EXPLICIT:
            return context.get("user_id", "user_statement")
        elif source == ProvenanceSource.CLAUDE_INFERRED:
            return "claude_inference"
        elif source == ProvenanceSource.DOCUMENTATION:
            return f"documentation:{context.get('doc_type', 'unknown')}"
        elif source == ProvenanceSource.CODE_INDEXED:
            return f"code_indexer:{context.get('indexer_version', 'v1')}"
        elif source == ProvenanceSource.AUTO_CLASSIFIED:
            return "auto_classifier"
        elif source == ProvenanceSource.IMPORTED:
            return f"import:{context.get('import_source', 'unknown')}"
        else:
            return "legacy_migration"

    def _calculate_source_confidence(self, source: ProvenanceSource) -> float:
        """
        Calculate initial confidence based on source reliability.

        Args:
            source: Provenance source

        Returns:
            Confidence score (0-1)
        """
        # Source reliability mapping
        confidence_map = {
            ProvenanceSource.USER_EXPLICIT: 0.9,  # User directly stated
            ProvenanceSource.CLAUDE_INFERRED: 0.7,  # Claude inferred
            ProvenanceSource.DOCUMENTATION: 0.85,  # From documentation
            ProvenanceSource.CODE_INDEXED: 0.8,  # From code analysis
            ProvenanceSource.AUTO_CLASSIFIED: 0.6,  # Auto-classified
            ProvenanceSource.IMPORTED: 0.5,  # Imported (unknown quality)
            ProvenanceSource.LEGACY: 0.5,  # Legacy (unknown provenance)
        }
        return confidence_map.get(source, 0.5)

    async def update_access(self, memory_id: str) -> None:
        """
        Update last_accessed timestamp for a memory.

        This should be called whenever a memory is retrieved in search results.

        Args:
            memory_id: Memory ID
        """
        try:
            # Fetch the memory
            memory = await self.store.get_by_id(memory_id)
            if not memory:
                logger.warning(f"Memory not found for access update: {memory_id}")
                return

            # Update provenance
            memory.provenance.last_confirmed = (
                None  # Don't update confirmed, just accessed
            )

            # The store layer should update last_accessed automatically,
            # but we can also update it explicitly if needed
            from src.embeddings.generator import EmbeddingGenerator

            embedding_gen = EmbeddingGenerator()
            embedding = await embedding_gen.generate(memory.content)

            # Store with updated access time
            await self.store.store(
                content=memory.content,
                embedding=embedding,
                metadata={
                    "id": memory.id,
                    "category": memory.category.value,
                    "context_level": memory.context_level.value,
                    "scope": memory.scope.value,
                    "project_name": memory.project_name,
                    "importance": memory.importance,
                    "tags": memory.tags,
                    "metadata": memory.metadata,
                    "created_at": memory.created_at,
                    "last_accessed": datetime.now(UTC),
                    "provenance": memory.provenance.model_dump(),
                },
            )

            logger.debug(f"Updated access time for memory: {memory_id}")

        except Exception as e:
            logger.error(f"Error updating access time: {e}")

    async def verify_memory(
        self, memory_id: str, verified: bool, user_notes: Optional[str] = None
    ) -> bool:
        """
        Mark memory as verified by user.

        Args:
            memory_id: Memory ID
            verified: Verification status
            user_notes: Optional notes from user

        Returns:
            True if updated successfully
        """
        try:
            # Fetch the memory
            memory = await self.store.get_by_id(memory_id)
            if not memory:
                logger.warning(f"Memory not found for verification: {memory_id}")
                return False

            # Update provenance
            memory.provenance.verified = verified
            memory.provenance.last_confirmed = datetime.now(UTC)

            # Boost confidence if verified
            if verified:
                memory.provenance.confidence = min(
                    1.0, memory.provenance.confidence + 0.15
                )

            # Add notes if provided
            if user_notes:
                existing_notes = memory.provenance.notes or ""
                memory.provenance.notes = f"{existing_notes}\n[{datetime.now(UTC).isoformat()}] {user_notes}".strip()

            # Store updated memory
            from src.embeddings.generator import EmbeddingGenerator

            embedding_gen = EmbeddingGenerator()
            embedding = await embedding_gen.generate(memory.content)

            await self.store.store(
                content=memory.content,
                embedding=embedding,
                metadata={
                    "id": memory.id,
                    "category": memory.category.value,
                    "context_level": memory.context_level.value,
                    "scope": memory.scope.value,
                    "project_name": memory.project_name,
                    "importance": memory.importance,
                    "tags": memory.tags,
                    "metadata": memory.metadata,
                    "created_at": memory.created_at,
                    "provenance": memory.provenance.model_dump(),
                },
            )

            logger.info(
                f"Verified memory {memory_id}: verified={verified}, "
                f"new_confidence={memory.provenance.confidence:.2f}"
            )
            return True

        except Exception as e:
            logger.error(f"Error verifying memory: {e}")
            return False

    async def calculate_confidence(self, memory: MemoryUnit) -> float:
        """
        Calculate confidence score based on provenance factors.

        Factors:
        - Source reliability (base score)
        - Age (newer = higher confidence)
        - Verification status (verified = +0.15)
        - Access frequency (more accessed = higher confidence)
        - Last confirmation time (recently confirmed = higher)

        Args:
            memory: MemoryUnit

        Returns:
            Confidence score (0-1)
        """
        try:
            # Start with source-based confidence
            confidence = memory.provenance.confidence

            # Age factor: decay over time
            age_days = (datetime.now(UTC) - memory.created_at).days
            if age_days > 365:
                confidence *= 0.8  # 20% penalty for very old memories
            elif age_days > 180:
                confidence *= 0.9  # 10% penalty for old memories

            # Verification bonus
            if memory.provenance.verified:
                confidence = min(1.0, confidence + 0.15)

            # Last confirmation factor
            if memory.provenance.last_confirmed:
                days_since_confirmed = (
                    datetime.now(UTC) - memory.provenance.last_confirmed
                ).days
                if days_since_confirmed < 30:
                    confidence = min(1.0, confidence + 0.1)  # Recent confirmation bonus

            # Access frequency factor (if available in metadata)
            access_count = memory.metadata.get("access_count", 0)
            if access_count > 10:
                confidence = min(1.0, confidence + 0.05)  # Frequently accessed bonus

            # Ensure bounds
            confidence = max(0.0, min(1.0, confidence))

            return confidence

        except Exception as e:
            logger.error(f"Error calculating confidence: {e}")
            return memory.provenance.confidence

    async def get_low_confidence_memories(
        self, threshold: float = 0.6, limit: int = 50
    ) -> list[MemoryUnit]:
        """
        Get memories with low confidence scores for review.

        Args:
            threshold: Confidence threshold (memories below this are returned)
            limit: Maximum number of memories to return

        Returns:
            List of low-confidence memories
        """
        try:
            # Get all memories (this is simplified - in production, we'd want better filtering)
            all_memories = await self.store.retrieve(
                query_embedding=[0.0] * DEFAULT_EMBEDDING_DIM, filters=None, limit=1000
            )

            # Filter for low confidence
            low_confidence = []
            for memory, _ in all_memories:
                confidence = await self.calculate_confidence(memory)
                if confidence < threshold:
                    low_confidence.append(memory)

            # Sort by confidence ascending (lowest first)
            low_confidence.sort(key=lambda m: m.provenance.confidence)

            return low_confidence[:limit]

        except Exception as e:
            logger.error(f"Error getting low-confidence memories: {e}")
            return []

    async def get_unverified_memories(
        self, days_old: int = 90, limit: int = 50
    ) -> list[MemoryUnit]:
        """
        Get old unverified memories that need review.

        Args:
            days_old: Minimum age in days
            limit: Maximum number of memories

        Returns:
            List of unverified memories
        """
        try:
            # Get all memories
            all_memories = await self.store.retrieve(
                query_embedding=[0.0] * DEFAULT_EMBEDDING_DIM, filters=None, limit=1000
            )

            # Filter for unverified and old
            cutoff_date = datetime.now(UTC) - timedelta(days=days_old)
            unverified = []

            for memory, _ in all_memories:
                if not memory.provenance.verified and memory.created_at < cutoff_date:
                    unverified.append(memory)

            # Sort by age descending (oldest first)
            unverified.sort(key=lambda m: m.created_at)

            return unverified[:limit]

        except Exception as e:
            logger.error(f"Error getting unverified memories: {e}")
            return []
