"""Documentation ingestion system for markdown files."""

import re
from pathlib import Path
from typing import List, Dict, Optional
import glob
import hashlib

from .database import MemoryDatabase, compute_file_hash
from .embeddings import EmbeddingGenerator


class DocumentationIngester:
    """Handles ingestion of markdown documentation into the vector database."""

    def __init__(self, db: MemoryDatabase, embedder: EmbeddingGenerator):
        self.db = db
        self.embedder = embedder

    def scan_directory(
        self,
        path: str,
        patterns: List[str],
        recursive: bool = True
    ) -> List[str]:
        """
        Find all markdown files matching patterns.

        Args:
            path: Directory to scan
            patterns: List of glob patterns (e.g., ["*.md", "docs/**/*.md"])
            recursive: Scan subdirectories

        Returns:
            List of file paths
        """
        found_files = []
        base_path = Path(path).resolve()

        for pattern in patterns:
            if recursive and '**' not in pattern:
                pattern = f"**/{pattern}"

            matches = base_path.glob(pattern)
            for match in matches:
                if match.is_file():
                    found_files.append(str(match))

        # Deduplicate and sort
        return sorted(list(set(found_files)))

    def chunk_markdown(
        self,
        content: str,
        max_size: int = 1000
    ) -> List[Dict]:
        """
        Chunk markdown by headers and paragraphs.

        Strategy:
        1. Split on H2 headers (##)
        2. If section > max_size, split on paragraphs
        3. Preserve code blocks intact
        4. Include heading context in each chunk

        Args:
            content: Markdown content
            max_size: Maximum chunk size in characters

        Returns:
            List of chunks with metadata:
            [{"content": "...", "heading": "Installation", "index": 0}, ...]
        """
        chunks = []

        # Split on headers (## or #)
        header_pattern = r'^(#{1,6})\s+(.+)$'
        lines = content.split('\n')

        current_heading = "Introduction"
        current_content = []
        current_level = 0

        for line in lines:
            header_match = re.match(header_pattern, line)

            if header_match:
                # Save previous section
                if current_content:
                    section_text = '\n'.join(current_content).strip()
                    if section_text:
                        chunks.extend(
                            self._split_large_section(
                                section_text,
                                current_heading,
                                max_size
                            )
                        )

                # Start new section
                level = len(header_match.group(1))
                current_heading = header_match.group(2).strip()
                current_level = level
                current_content = []
            else:
                current_content.append(line)

        # Don't forget the last section
        if current_content:
            section_text = '\n'.join(current_content).strip()
            if section_text:
                chunks.extend(
                    self._split_large_section(
                        section_text,
                        current_heading,
                        max_size
                    )
                )

        # Add index to each chunk
        for i, chunk in enumerate(chunks):
            chunk['index'] = i

        return chunks

    def _split_large_section(
        self,
        content: str,
        heading: str,
        max_size: int
    ) -> List[Dict]:
        """Split a large section into smaller chunks."""
        if len(content) <= max_size:
            return [{
                "content": f"{heading}: {content}",
                "heading": heading
            }]

        chunks = []
        paragraphs = content.split('\n\n')
        current_chunk = ""

        for para in paragraphs:
            # Check if adding this paragraph exceeds max_size
            if len(current_chunk) + len(para) + 2 > max_size:
                if current_chunk.strip():
                    chunks.append({
                        "content": f"{heading}: {current_chunk.strip()}",
                        "heading": heading
                    })
                current_chunk = para
            else:
                if current_chunk:
                    current_chunk += "\n\n" + para
                else:
                    current_chunk = para

        # Don't forget the last chunk
        if current_chunk.strip():
            chunks.append({
                "content": f"{heading}: {current_chunk.strip()}",
                "heading": heading
            })

        return chunks

    def ingest_file(
        self,
        file_path: str,
        project_name: str,
        force: bool = False
    ) -> int:
        """
        Ingest a single markdown file.

        Args:
            file_path: Path to markdown file
            project_name: Name of the project
            force: Force re-ingestion even if unchanged

        Returns:
            Number of chunks created
        """
        file_path = str(Path(file_path).resolve())

        # Compute file hash
        file_hash = compute_file_hash(file_path)

        # Check if file changed
        if not force and not self.db.check_doc_changed(project_name, file_path, file_hash):
            return 0  # File unchanged, skip

        # Read file content
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except FileNotFoundError:
            raise FileNotFoundError(f"File not found: {file_path}")
        except UnicodeDecodeError as e:
            raise ValueError(f"File encoding error in {file_path}: {e}")
        except Exception as e:
            raise Exception(f"Failed to read {file_path}: {e}")

        # Chunk the markdown
        chunks = self.chunk_markdown(content)

        if not chunks:
            return 0

        # Generate embeddings and store
        chunk_ids = []
        for chunk in chunks:
            # Generate embedding
            embedding = self.embedder.generate(chunk['content'])

            # Extract tags from content
            tags = self._extract_tags(chunk['content'])

            # Store in database
            chunk_id = self.db.store_documentation(
                content=chunk['content'],
                project_name=project_name,
                source_file=file_path,
                heading=chunk['heading'],
                embedding=embedding,
                tags=tags
            )
            chunk_ids.append(chunk_id)

        # Mark file as ingested
        self.db.mark_doc_ingested(
            project_name=project_name,
            file_path=file_path,
            file_hash=file_hash,
            chunk_count=len(chunks)
        )

        return len(chunks)

    def ingest_directory(
        self,
        path: str,
        project_name: str,
        patterns: Optional[List[str]] = None,
        recursive: bool = True,
        force: bool = False
    ) -> Dict:
        """
        Ingest all matching markdown files in a directory.

        Args:
            path: Directory to scan
            project_name: Name of the project
            patterns: Glob patterns (default: ["*.md", "README.md", "docs/**/*.md"])
            recursive: Scan subdirectories
            force: Force re-ingestion of all files

        Returns:
            Statistics about ingestion:
            {
                "files_processed": 10,
                "total_chunks": 45,
                "skipped": 2,
                "errors": ["error1", ...]
            }
        """
        if patterns is None:
            patterns = ["*.md", "README.md", "docs/**/*.md"]

        # Find all matching files
        files = self.scan_directory(path, patterns, recursive)

        stats = {
            "files_processed": 0,
            "total_chunks": 0,
            "skipped": 0,
            "errors": []
        }

        for file_path in files:
            try:
                chunks_created = self.ingest_file(file_path, project_name, force)

                if chunks_created > 0:
                    stats["files_processed"] += 1
                    stats["total_chunks"] += chunks_created
                else:
                    stats["skipped"] += 1

            except Exception as e:
                stats["errors"].append(f"{file_path}: {str(e)}")

        return stats

    def _extract_tags(self, content: str) -> List[str]:
        """Extract relevant tags/keywords from content."""
        # Common technical terms
        tech_terms = [
            'python', 'javascript', 'typescript', 'react', 'node', 'django',
            'postgres', 'mysql', 'mongodb', 'redis', 'docker', 'kubernetes',
            'api', 'rest', 'graphql', 'auth', 'authentication', 'database',
            'frontend', 'backend', 'testing', 'deployment', 'production',
            'install', 'configuration', 'setup', 'tutorial', 'guide',
            'reference', 'example', 'usage'
        ]

        content_lower = content.lower()
        tags = [term for term in tech_terms if term in content_lower]

        return tags[:5]  # Limit to 5 tags
