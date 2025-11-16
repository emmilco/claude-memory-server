"""Smart query routing system for memories and documentation."""

from enum import Enum
from typing import Dict, List, Optional


class QueryIntent(Enum):
    """Types of query intent for routing."""
    PERSONAL = "personal"      # User preferences, workflows
    TECHNICAL = "technical"    # Documentation, how-to
    MIXED = "mixed"           # Both personal and technical


class SmartRouter:
    """Routes queries to appropriate sources based on intent classification."""

    # Indicators for personal queries (preferences, workflows, personal facts)
    PERSONAL_INDICATORS = [
        "i prefer", "i like", "i always", "i usually", "i typically",
        "my workflow", "my style", "my preference", "my approach",
        "what do i", "do i prefer", "have i", "did i",
        "what's my", "am i using"
    ]

    # Indicators for technical queries (documentation, how-to, reference)
    TECHNICAL_INDICATORS = [
        "how does", "how do i", "how to", "how can i",
        "what is", "what are", "what's the",
        "explain", "describe", "show me", "where is", "find",
        "documentation", "docs", "readme", "reference",
        "api", "function", "class", "method", "module",
        "install", "configure", "setup", "deploy",
        "tutorial", "guide", "example", "usage"
    ]

    def __init__(self):
        """Initialize the smart router."""
        pass

    def classify_intent(self, query: str) -> QueryIntent:
        """
        Classify query intent based on indicators.

        Args:
            query: The user's query

        Returns:
            QueryIntent enum value
        """
        query_lower = query.lower()

        has_personal = any(ind in query_lower for ind in self.PERSONAL_INDICATORS)
        has_technical = any(ind in query_lower for ind in self.TECHNICAL_INDICATORS)

        if has_personal and not has_technical:
            return QueryIntent.PERSONAL
        elif has_technical and not has_personal:
            return QueryIntent.TECHNICAL
        else:
            # Default to MIXED if both or neither
            return QueryIntent.MIXED

    def route_query(
        self,
        query: str,
        db,
        embedder,
        limit: int = 10,
        project_name: Optional[str] = None
    ) -> List[Dict]:
        """
        Route query to appropriate sources and return combined results.

        Args:
            query: User's query
            db: MemoryDatabase instance
            embedder: EmbeddingGenerator instance
            limit: Maximum number of results
            project_name: Current project context

        Returns:
            Combined and ranked results from appropriate sources
        """
        intent = self.classify_intent(query)
        query_embedding = embedder.generate(query)

        if intent == QueryIntent.PERSONAL:
            # Search memories only
            results = db.retrieve_similar_memories(
                query_embedding,
                limit=limit,
                filters={'memory_type': 'memory'},
                min_importance=0.2
            )

        elif intent == QueryIntent.TECHNICAL:
            # Search documentation primarily, with some project facts
            doc_results = db.retrieve_similar_memories(
                query_embedding,
                limit=int(limit * 0.7),
                filters={'memory_type': 'documentation'},
                min_importance=0.0
            )

            # Also get project-specific factual memories
            fact_filters = {
                'memory_type': 'memory',
                'category': 'fact'
            }
            if project_name:
                fact_filters['project_name'] = project_name

            memory_results = db.retrieve_similar_memories(
                query_embedding,
                limit=int(limit * 0.3),
                filters=fact_filters,
                min_importance=0.3
            )

            # Combine with weights (docs are more important for technical queries)
            results = self._combine_results(
                doc_results,
                memory_results,
                doc_weight=0.7
            )

        else:  # MIXED
            # Balanced search across both
            doc_results = db.retrieve_similar_memories(
                query_embedding,
                limit=int(limit * 0.6),
                filters={'memory_type': 'documentation'},
                min_importance=0.0
            )

            memory_results = db.retrieve_similar_memories(
                query_embedding,
                limit=int(limit * 0.4),
                filters={'memory_type': 'memory'},
                min_importance=0.2
            )

            results = self._combine_results(
                doc_results,
                memory_results,
                doc_weight=0.6
            )

        return results[:limit]

    def _combine_results(
        self,
        doc_results: List[Dict],
        memory_results: List[Dict],
        doc_weight: float = 0.6
    ) -> List[Dict]:
        """
        Combine and re-rank results from different sources.

        Args:
            doc_results: Results from documentation search
            memory_results: Results from memory search
            doc_weight: Weight for documentation results (0.0-1.0)

        Returns:
            Combined and sorted results
        """
        # Adjust similarity scores by weight
        for doc in doc_results:
            doc['weighted_similarity'] = doc['similarity'] * doc_weight
            doc['source_type'] = 'documentation'

        for mem in memory_results:
            mem['weighted_similarity'] = mem['similarity'] * (1 - doc_weight)
            mem['source_type'] = 'memory'

        # Combine and sort by weighted similarity
        all_results = doc_results + memory_results
        all_results.sort(key=lambda x: x['weighted_similarity'], reverse=True)

        return all_results

    def format_results(self, results: List[Dict], include_source: bool = True) -> str:
        """
        Format results for display.

        Args:
            results: List of result dictionaries
            include_source: Whether to include source type/file info

        Returns:
            Formatted string
        """
        if not results:
            return "No relevant information found."

        output = []
        for i, result in enumerate(results, 1):
            # Build result entry
            entry = f"{i}. {result['content'][:200]}"
            if len(result['content']) > 200:
                entry += "..."

            if include_source:
                if result.get('source_file'):
                    entry += f"\n   Source: {result['source_file']}"
                    if result.get('heading'):
                        entry += f" ({result['heading']})"
                elif result.get('memory_type') == 'memory':
                    entry += f"\n   Type: {result['category']} memory"

                entry += f"\n   Relevance: {result['similarity']:.2f}"

            output.append(entry)

        return "\n\n".join(output)
