"""Memory extraction, storage, and retrieval logic with project scope support."""

import json
import re
from typing import List, Dict, Optional
from datetime import datetime


class MemoryManager:
    """Manages automatic memory extraction, storage, and retrieval with project awareness."""

    # Categories of memories to extract
    CATEGORIES = {
        'preference': ['prefer', 'like', 'always', 'never', 'favorite', 'hate', 'love'],
        'fact': ['is', 'uses', 'has', 'contains', 'runs', 'deployed', 'stack'],
        'event': ['fixed', 'added', 'changed', 'updated', 'deployed', 'migrated', 'decided'],
        'workflow': ['usually', 'typically', 'often', 'script', 'command', 'process'],
    }

    def __init__(self, db, embedder, project_name: Optional[str] = None):
        """
        Initialize memory manager.

        Args:
            db: MemoryDatabase instance
            embedder: EmbeddingGenerator instance
            project_name: Current project name (from git repo)
        """
        self.db = db
        self.embedder = embedder
        self.project_name = project_name

    def extract_and_store_memories(
        self,
        user_message: str,
        assistant_message: str
    ) -> List[int]:
        """
        Extract important memories from conversation and store them.

        Args:
            user_message: What the user said
            assistant_message: What Claude responded

        Returns:
            List of memory IDs that were stored
        """
        memories = []

        # Extract from user message (preferences, facts, workflows)
        memories.extend(self._extract_from_user(user_message))

        # Extract from assistant message (facts, events)
        memories.extend(self._extract_from_assistant(assistant_message))

        # Store conversation context as a memory (recent context)
        context_summary = self._create_context_summary(user_message, assistant_message)
        if context_summary:
            memories.append({
                'content': context_summary,
                'category': 'context',
                'importance': 0.3  # Lower importance for general context
            })

        # Store all extracted memories
        memory_ids = []
        for memory in memories:
            embedding = self.embedder.generate(memory['content'])
            tags = self._extract_tags(memory['content'])

            # Determine scope: preferences/workflows are global, facts/events are project-scoped
            category = memory['category']
            if category in ['preference', 'workflow']:
                scope = 'global'
                project_name = None
            else:
                scope = 'project' if self.project_name else 'global'
                project_name = self.project_name

            memory_id = self.db.store_memory(
                content=memory['content'],
                category=category,
                memory_type='memory',  # This is a memory, not documentation
                scope=scope,
                project_name=project_name,
                embedding=embedding,
                tags=tags,
                importance=memory.get('importance', 0.5)
            )
            memory_ids.append(memory_id)

        return memory_ids

    def retrieve_relevant_memories(
        self,
        query: str,
        limit: int = 10,
        include_recent: bool = True
    ) -> str:
        """
        Retrieve relevant memories for a query and format them as context.

        Args:
            query: User's current message
            limit: Maximum number of memories to retrieve
            include_recent: Whether to include recent memories

        Returns:
            Formatted string of relevant memories to include in prompt
        """
        # Generate embedding for the query
        query_embedding = self.embedder.generate(query)

        # Get semantically similar memories (memories only, not docs)
        similar_memories = self.db.retrieve_similar_memories(
            query_embedding,
            limit=limit,
            filters={'memory_type': 'memory'},
            min_importance=0.2
        )

        # Optionally get recent memories
        recent_memories = []
        if include_recent:
            recent_memories = self.db.get_recent_memories(
                limit=3,
                hours=24,
                memory_type='memory'
            )

        # Combine and deduplicate
        all_memories = self._deduplicate_memories(similar_memories, recent_memories)

        # Format as context string
        return self._format_memories_as_context(all_memories)

    def _extract_from_user(self, message: str) -> List[Dict]:
        """Extract memories from user messages."""
        memories = []

        # Look for preference statements
        if any(word in message.lower() for word in ['prefer', 'like', 'always', 'favorite']):
            memories.append({
                'content': message,
                'category': 'preference',
                'importance': 0.8
            })

        # Look for workflow/process descriptions
        if any(word in message.lower() for word in ['usually', 'typically', 'script', 'command']):
            memories.append({
                'content': message,
                'category': 'workflow',
                'importance': 0.7
            })

        # Look for factual statements about projects
        if re.search(r'\b(using|use|has|have|is|are)\b.*\b(project|app|system|database|api)\b', message.lower()):
            memories.append({
                'content': message,
                'category': 'fact',
                'importance': 0.6
            })

        return memories

    def _extract_from_assistant(self, message: str) -> List[Dict]:
        """Extract memories from assistant messages."""
        memories = []

        # Look for event descriptions (things that were done)
        if re.search(r'\b(fixed|added|updated|implemented|created|deployed)\b', message.lower()):
            # Extract specific actions
            sentences = message.split('.')
            for sentence in sentences:
                if any(word in sentence.lower() for word in ['fixed', 'added', 'updated', 'implemented', 'created']):
                    clean_sentence = sentence.strip()
                    if len(clean_sentence) > 20:  # Skip very short sentences
                        memories.append({
                            'content': clean_sentence,
                            'category': 'event',
                            'importance': 0.7
                        })

        return memories

    def _create_context_summary(self, user_msg: str, assistant_msg: str) -> Optional[str]:
        """Create a brief summary of the conversation exchange."""
        # Only create context for substantial exchanges
        if len(user_msg) < 20 and len(assistant_msg) < 50:
            return None

        # Create a brief summary
        summary = f"User asked: {user_msg[:100]}..."
        return summary

    def _extract_tags(self, content: str) -> List[str]:
        """Extract relevant tags/keywords from content."""
        # Common technical terms to look for
        tech_terms = [
            'python', 'javascript', 'typescript', 'react', 'node', 'django',
            'postgres', 'mysql', 'mongodb', 'redis', 'docker', 'kubernetes',
            'api', 'rest', 'graphql', 'auth', 'authentication', 'database',
            'frontend', 'backend', 'testing', 'deployment', 'production'
        ]

        content_lower = content.lower()
        tags = [term for term in tech_terms if term in content_lower]

        return tags[:5]  # Limit to 5 tags

    def _deduplicate_memories(
        self,
        similar: List[Dict],
        recent: List[Dict]
    ) -> List[Dict]:
        """Remove duplicate memories, preferring higher similarity scores."""
        seen_ids = set()
        result = []

        # Add similar memories first (already sorted by similarity)
        for memory in similar:
            if memory['id'] not in seen_ids:
                seen_ids.add(memory['id'])
                result.append(memory)

        # Add recent memories if not already included
        for memory in recent:
            if memory['id'] not in seen_ids:
                seen_ids.add(memory['id'])
                memory['similarity'] = 0.0  # Mark as recent, not semantically matched
                result.append(memory)

        return result

    def _format_memories_as_context(self, memories: List[Dict]) -> str:
        """Format memories into a context string for Claude."""
        if not memories:
            return ""

        # Group by category
        by_category = {}
        for mem in memories:
            cat = mem['category']
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(mem)

        # Format each category
        sections = []

        if 'preference' in by_category:
            prefs = [m['content'] for m in by_category['preference']]
            sections.append("## Your Preferences\n" + "\n".join(f"- {p}" for p in prefs))

        if 'fact' in by_category:
            facts = [m['content'] for m in by_category['fact']]
            sections.append("## Project Facts\n" + "\n".join(f"- {f}" for f in facts))

        if 'workflow' in by_category:
            workflows = [m['content'] for m in by_category['workflow']]
            sections.append("## Your Workflows\n" + "\n".join(f"- {w}" for w in workflows))

        if 'event' in by_category:
            events = sorted(by_category['event'], key=lambda x: x.get('timestamp', ''), reverse=True)[:3]
            event_strs = [f"- {e['content']}" for e in events]
            sections.append("## Recent Events\n" + "\n".join(event_strs))

        if sections:
            return "# Relevant Context from Memory\n\n" + "\n\n".join(sections)

        return ""
