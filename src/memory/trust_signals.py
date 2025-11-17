"""Trust signal generation for search results (FEAT-034 Phase 4)."""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, UTC

from src.core.models import MemoryUnit, TrustSignals, MemoryCategory
from src.store.base import MemoryStore

logger = logging.getLogger(__name__)


class TrustSignalGenerator:
    """
    Generate trust signals and explanations for search results.

    Provides:
    - "Why this result?" explanations
    - Trust score calculations
    - Confidence level interpretations
    - Provenance summaries
    """

    def __init__(self, store: MemoryStore):
        """
        Initialize the trust signal generator.

        Args:
            store: Memory store for accessing relationships and metadata
        """
        self.store = store
        logger.info("TrustSignalGenerator initialized")

    async def explain_result(
        self,
        memory: MemoryUnit,
        query: str,
        score: float,
        rank: int,
        include_relationships: bool = True
    ) -> TrustSignals:
        """
        Generate 'Why this result?' explanation.

        Explanation includes:
        - Semantic match quality
        - Project context match
        - Access frequency
        - Verification status
        - Related memories count

        Args:
            memory: Memory that matched
            query: Original query
            score: Similarity score
            rank: Result rank
            include_relationships: Whether to include relationship counts

        Returns:
            TrustSignals object with explanations
        """
        try:
            # Calculate overall trust score
            trust_score = await self.calculate_trust_score(memory)

            # Generate explanation points
            why_shown = []

            # 1. Semantic match quality
            if score >= 0.9:
                why_shown.append(f"Exact semantic match to your query ({score:.2f})")
            elif score >= 0.8:
                why_shown.append(f"Strong semantic match ({score:.2f})")
            elif score >= 0.7:
                why_shown.append(f"Good semantic match ({score:.2f})")
            else:
                why_shown.append(f"Related to your query ({score:.2f})")

            # 2. Project context
            if memory.project_name:
                why_shown.append(f"From current project: {memory.project_name}")
            elif memory.scope.value == "global":
                why_shown.append("Global memory (applies everywhere)")

            # 3. Access frequency
            access_count = memory.metadata.get("access_count", 0)
            if access_count > 20:
                why_shown.append(f"Frequently accessed ({access_count} times) HIGH CONFIDENCE")
            elif access_count > 10:
                why_shown.append(f"Well-used memory ({access_count} accesses)")
            elif access_count > 5:
                why_shown.append(f"Accessed {access_count} times previously")

            # 4. Verification status
            if memory.provenance.verified:
                days_since_verified = 0
                if memory.provenance.last_confirmed:
                    days_since_verified = (datetime.now(UTC) - memory.provenance.last_confirmed).days

                if days_since_verified == 0:
                    why_shown.append("You verified this today")
                elif days_since_verified < 7:
                    why_shown.append(f"You verified this {days_since_verified} days ago")
                elif days_since_verified < 30:
                    why_shown.append(f"You verified this {days_since_verified} days ago")
                else:
                    why_shown.append("You verified this (some time ago)")

            # 5. Category information
            if memory.category == MemoryCategory.PREFERENCE:
                why_shown.append("This is a personal preference")
            elif memory.category == MemoryCategory.FACT:
                why_shown.append("Factual information")

            # 6. Relationship information (if requested)
            if include_relationships:
                try:
                    relationships = await self.store.get_relationships(memory.id)
                    if relationships:
                        related_count = len([r for r in relationships if r.get("relationship_type") == "related"])
                        if related_count > 0:
                            why_shown.append(f"Related to {related_count} other memories")
                except Exception as e:
                    logger.debug(f"Could not fetch relationships: {e}")

            # 7. Provenance source
            source_quality = self._get_source_quality_label(memory.provenance.source.value)
            why_shown.append(f"Source: {source_quality}")

            # Generate provenance summary
            provenance_summary = {
                "source": memory.provenance.source.value,
                "created_by": memory.provenance.created_by,
                "confidence": memory.provenance.confidence,
                "verified": memory.provenance.verified,
                "age_days": (datetime.now(UTC) - memory.created_at).days
            }

            # Check for contradictions
            contradiction_detected = False
            try:
                relationships = await self.store.get_relationships(memory.id)
                contradiction_detected = any(
                    r.get("relationship_type") == "contradicts"
                    for r in relationships
                )
            except Exception:
                pass

            # Get confidence level
            confidence_level = self.generate_confidence_explanation(trust_score)

            # Format last verified
            last_verified = None
            if memory.provenance.last_confirmed:
                days_ago = (datetime.now(UTC) - memory.provenance.last_confirmed).days
                if days_ago == 0:
                    last_verified = "today"
                elif days_ago == 1:
                    last_verified = "yesterday"
                elif days_ago < 7:
                    last_verified = f"{days_ago} days ago"
                elif days_ago < 30:
                    weeks = days_ago // 7
                    last_verified = f"{weeks} week{'s' if weeks > 1 else ''} ago"
                else:
                    months = days_ago // 30
                    last_verified = f"{months} month{'s' if months > 1 else ''} ago"

            # Get related count
            related_count = 0
            try:
                relationships = await self.store.get_relationships(memory.id)
                related_count = len(relationships)
            except Exception:
                pass

            return TrustSignals(
                why_shown=why_shown,
                trust_score=trust_score,
                confidence_level=confidence_level,
                last_verified=last_verified,
                provenance_summary=provenance_summary,
                related_count=related_count,
                contradiction_detected=contradiction_detected
            )

        except Exception as e:
            logger.error(f"Error explaining result: {e}")
            # Return minimal trust signals on error
            return TrustSignals(
                why_shown=[f"Matched with score {score:.2f}"],
                trust_score=0.5,
                confidence_level="fair",
                provenance_summary={}
            )

    async def calculate_trust_score(
        self,
        memory: MemoryUnit
    ) -> float:
        """
        Calculate overall trust score (0-1).

        Factors:
        - Provenance source reliability (30%)
        - Verification status (25%)
        - Access frequency (20%)
        - Age and recency (15%)
        - Contradiction status (10%)

        Args:
            memory: Memory to score

        Returns:
            Trust score (0-1)
        """
        try:
            # 1. Provenance source reliability (30%)
            source_score = memory.provenance.confidence * 0.3

            # 2. Verification status (25%)
            verification_score = 0.25 if memory.provenance.verified else 0.1

            # 3. Access frequency (20%)
            access_count = memory.metadata.get("access_count", 0)
            if access_count >= 20:
                access_score = 0.2
            elif access_count >= 10:
                access_score = 0.15
            elif access_count >= 5:
                access_score = 0.1
            else:
                access_score = 0.05

            # 4. Age and recency (15%)
            age_days = (datetime.now(UTC) - memory.created_at).days
            if age_days < 30:
                age_score = 0.15  # Recent
            elif age_days < 90:
                age_score = 0.12  # Medium
            elif age_days < 180:
                age_score = 0.08  # Older
            else:
                age_score = 0.05  # Old

            # Last confirmed bonus
            if memory.provenance.last_confirmed:
                days_since_confirmed = (datetime.now(UTC) - memory.provenance.last_confirmed).days
                if days_since_confirmed < 30:
                    age_score = min(0.15, age_score + 0.05)

            # 5. Contradiction status (10%)
            contradiction_penalty = 0.0
            try:
                relationships = await self.store.get_relationships(memory.id)
                has_contradictions = any(
                    r.get("relationship_type") == "contradicts"
                    for r in relationships
                )
                contradiction_score = 0.0 if has_contradictions else 0.1
            except Exception:
                contradiction_score = 0.05  # Neutral if we can't check

            # Calculate total
            trust_score = source_score + verification_score + access_score + age_score + contradiction_score

            # Ensure bounds
            trust_score = max(0.0, min(1.0, trust_score))

            return trust_score

        except Exception as e:
            logger.error(f"Error calculating trust score: {e}")
            return 0.5  # Default to medium trust

    def generate_confidence_explanation(
        self,
        confidence: float
    ) -> str:
        """
        Convert confidence score to human-readable explanation.

        Args:
            confidence: Confidence score (0-1)

        Returns:
            Human-readable confidence level
        """
        if confidence >= 0.8:
            return "excellent"
        elif confidence >= 0.65:
            return "good"
        elif confidence >= 0.5:
            return "fair"
        else:
            return "poor"

    def _get_source_quality_label(self, source: str) -> str:
        """
        Get human-readable label for provenance source.

        Args:
            source: Provenance source value

        Returns:
            Human-readable label
        """
        labels = {
            "user_explicit": "you stated this directly",
            "claude_inferred": "inferred from conversation",
            "documentation": "from code documentation",
            "code_indexed": "from code analysis",
            "auto_classified": "automatically classified",
            "imported": "imported data",
            "legacy": "legacy data"
        }
        return labels.get(source, source)

    async def generate_batch_trust_signals(
        self,
        results: List[tuple[MemoryUnit, float]],
        query: str
    ) -> List[tuple[MemoryUnit, float, TrustSignals]]:
        """
        Generate trust signals for a batch of search results.

        Args:
            results: List of (memory, score) tuples from search
            query: Original query

        Returns:
            List of (memory, score, trust_signals) tuples
        """
        enhanced_results = []

        for rank, (memory, score) in enumerate(results, 1):
            try:
                trust_signals = await self.explain_result(
                    memory=memory,
                    query=query,
                    score=score,
                    rank=rank,
                    include_relationships=True
                )
                enhanced_results.append((memory, score, trust_signals))
            except Exception as e:
                logger.error(f"Error generating trust signals for memory {memory.id}: {e}")
                # Include without trust signals on error
                enhanced_results.append((memory, score, None))

        return enhanced_results
