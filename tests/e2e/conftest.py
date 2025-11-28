"""E2E test fixtures and configuration."""

import pytest
import pytest_asyncio
import tempfile
import shutil
import asyncio
from pathlib import Path
from typing import AsyncGenerator, Dict, Any

from src.core.server import MemoryRAGServer
from src.config import get_config


@pytest.fixture
def clean_environment(tmp_path):
    """Provide a clean environment for E2E tests.

    Creates a temporary directory that's automatically cleaned up after the test.
    This ensures each E2E test starts with a fresh environment.
    """
    # tmp_path is already a pytest fixture that auto-cleans
    # We just expose it with a more descriptive name for E2E tests
    yield tmp_path
    # Cleanup is automatic via pytest's tmp_path


# ============================================================================
# Session-Scoped Fixtures for Read-Only Tests (TEST-029 Optimization)
# ============================================================================

@pytest.fixture(scope="session")
def session_sample_code_project(tmp_path_factory):
    """Session-scoped sample code project for reuse across read-only tests.

    This fixture creates a realistic mini-project ONCE per session,
    eliminating the need to recreate it for each test.

    The project contains:
    - Multiple Python files (auth.py, database.py, api.py, utils.py, main.py)
    - Functions, classes, and methods
    - Import statements (for dependency testing)
    - Searchable content
    """
    project_dir = tmp_path_factory.mktemp("session_sample") / "sample_project"
    project_dir.mkdir()

    # auth.py - Authentication module
    (project_dir / "auth.py").write_text('''"""Authentication and authorization module."""

import hashlib
from typing import Optional


class User:
    """User model with authentication support."""

    def __init__(self, username: str, email: str):
        self.username = username
        self.email = email
        self._password_hash = None

    def set_password(self, password: str) -> None:
        """Hash and store password using SHA-256."""
        self._password_hash = hashlib.sha256(password.encode()).hexdigest()

    def verify_password(self, password: str) -> bool:
        """Verify password matches stored hash."""
        if not self._password_hash:
            return False
        return self._password_hash == hashlib.sha256(password.encode()).hexdigest()


def authenticate(username: str, password: str) -> Optional[User]:
    """Authenticate user with username and password.

    Returns User object if credentials are valid, None otherwise.
    """
    # In real app, would query database
    user = User(username, f"{username}@example.com")
    if user.verify_password(password):
        return user
    return None
''')

    # database.py - Database module
    (project_dir / "database.py").write_text('''"""Database connection and operations."""

import sqlite3
from pathlib import Path
from typing import List, Dict, Any


class DatabaseConnection:
    """SQLite database connection manager with context support."""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.conn = None

    def connect(self) -> None:
        """Open database connection."""
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row

    def close(self) -> None:
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None

    def execute_query(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """Execute SQL query and return results."""
        if not self.conn:
            self.connect()

        cursor = self.conn.cursor()
        cursor.execute(query, params)

        # Convert rows to dictionaries
        results = []
        for row in cursor.fetchall():
            results.append(dict(row))

        return results

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


def get_connection(db_path: str) -> DatabaseConnection:
    """Factory function to create database connection."""
    return DatabaseConnection(db_path)
''')

    # api.py - API handlers
    (project_dir / "api.py").write_text('''"""HTTP API request handlers."""

from typing import Dict, Any, Optional
import json


class APIRequest:
    """Represents an incoming API request."""

    def __init__(self, method: str, path: str, body: Optional[str] = None):
        self.method = method
        self.path = path
        self.body = body

    def get_json(self) -> Dict[str, Any]:
        """Parse request body as JSON."""
        if not self.body:
            return {}
        return json.loads(self.body)


class APIResponse:
    """Represents an API response."""

    def __init__(self, status_code: int, data: Any):
        self.status_code = status_code
        self.data = data

    def to_json(self) -> str:
        """Serialize response to JSON."""
        return json.dumps({
            "status": self.status_code,
            "data": self.data
        })


def handle_request(request: APIRequest) -> APIResponse:
    """Main request handler that routes to appropriate handler."""
    if request.method == "GET":
        return handle_get(request)
    elif request.method == "POST":
        return handle_post(request)
    else:
        return APIResponse(405, {"error": "Method not allowed"})


def handle_get(request: APIRequest) -> APIResponse:
    """Handle GET requests."""
    return APIResponse(200, {"message": f"GET {request.path}"})


def handle_post(request: APIRequest) -> APIResponse:
    """Handle POST requests."""
    data = request.get_json()
    return APIResponse(201, {"message": "Created", "data": data})
''')

    # utils.py - Utility functions
    (project_dir / "utils.py").write_text('''"""Utility functions and helpers."""

from typing import List, Any
from datetime import datetime


def format_timestamp(dt: datetime) -> str:
    """Format datetime as ISO 8601 string."""
    return dt.isoformat()


def parse_timestamp(timestamp: str) -> datetime:
    """Parse ISO 8601 timestamp string to datetime."""
    return datetime.fromisoformat(timestamp)


def validate_email(email: str) -> bool:
    """Validate email address format."""
    return "@" in email and "." in email.split("@")[1]


def chunk_list(items: List[Any], chunk_size: int) -> List[List[Any]]:
    """Split list into chunks of specified size."""
    return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]


def test_helper():
    """Helper function for testing purposes."""
    return "test result"
''')

    # main.py - Entry point
    (project_dir / "main.py").write_text('''"""Main application entry point."""

from auth import authenticate, User
from database import get_connection
from api import handle_request, APIRequest


def main():
    """Application main function."""
    print("Starting application...")

    # Example usage
    user = authenticate("admin", "password123")
    if user:
        print(f"Authenticated: {user.username}")

    # Database example
    with get_connection("app.db") as db:
        results = db.execute_query("SELECT * FROM users")
        print(f"Found {len(results)} users")

    # API example
    request = APIRequest("GET", "/api/users")
    response = handle_request(request)
    print(f"Response: {response.status_code}")


if __name__ == "__main__":
    main()
''')

    return project_dir


@pytest_asyncio.fixture(scope="session")
async def pre_indexed_server(session_sample_code_project, worker_id):
    """Session-scoped server with pre-indexed code for read-only tests.

    This fixture:
    1. Creates a MemoryRAGServer with a unique collection per worker
    2. Initializes it
    3. Indexes the sample_code_project ONCE
    4. Yields the server for read-only search tests
    5. Cleans up on session end

    IMPORTANT: Only use this fixture for tests that:
    - Only SEARCH the indexed code (don't modify)
    - Don't need a specific project name
    - Can share the indexed data with other tests

    Tests that store memories, delete data, or need project isolation
    should use the function-scoped `fresh_server` fixture instead.
    """
    import os
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams

    # Create unique collection name for this session/worker
    collection_name = f"e2e_preindexed_{worker_id}"

    # Get Qdrant client and create collection
    qdrant_url = os.getenv("CLAUDE_RAG_QDRANT_URL", "http://localhost:6333")
    qdrant_client = QdrantClient(url=qdrant_url, timeout=30.0)

    # Get vector size from config
    config = get_config()
    model_dims = {"all-MiniLM-L6-v2": 384, "all-MiniLM-L12-v2": 384, "all-mpnet-base-v2": 768}
    vector_size = model_dims.get(config.embedding_model, 768)

    # Create collection if it doesn't exist
    try:
        collections = qdrant_client.get_collections().collections
        if collection_name not in [c.name for c in collections]:
            qdrant_client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE)
            )
    except Exception:
        pass  # Collection might already exist

    # Set environment to use this collection
    os.environ["CLAUDE_RAG_QDRANT_COLLECTION_NAME"] = collection_name

    # Create and initialize server
    server = MemoryRAGServer(config=config)
    await server.initialize()

    # Index the sample code project ONCE
    await server.index_codebase(
        directory_path=str(session_sample_code_project),
        project_name="shared-test-project",
        recursive=True
    )

    yield server

    # Cleanup: close server and delete collection
    try:
        await server.close()
    except Exception:
        pass

    try:
        qdrant_client.delete_collection(collection_name=collection_name)
    except Exception:
        pass

    try:
        qdrant_client.close()
    except Exception:
        pass


@pytest_asyncio.fixture
async def fresh_server(clean_environment, unique_qdrant_collection, monkeypatch) -> AsyncGenerator[MemoryRAGServer, None]:
    """Create a fresh server instance for E2E testing.

    This fixture provides a fully initialized server with:
    - Clean Qdrant collection
    - Isolated temp directory
    - All services ready

    The server is automatically cleaned up after the test.
    """
    # Configure server to use clean environment
    config = get_config()

    # Override paths to use clean environment
    db_path = clean_environment / "test.db"
    monkeypatch.setenv("CLAUDE_RAG_SQLITE_PATH", str(db_path))

    # Create and initialize server
    server = MemoryRAGServer(config=config)
    await server.initialize()

    yield server

    # Cleanup: close server connections
    try:
        await server.close()
    except Exception:
        pass  # Ignore cleanup errors


@pytest.fixture
def sample_code_project(clean_environment):
    """Create a small sample code project for testing indexing and search.

    Creates a realistic mini-project with:
    - Multiple Python files
    - Functions, classes, and methods
    - Import statements (for dependency testing)
    - Searchable content
    """
    project_dir = clean_environment / "sample_project"
    project_dir.mkdir()

    # auth.py - Authentication module
    (project_dir / "auth.py").write_text('''"""Authentication and authorization module."""

import hashlib
from typing import Optional


class User:
    """User model with authentication support."""

    def __init__(self, username: str, email: str):
        self.username = username
        self.email = email
        self._password_hash = None

    def set_password(self, password: str) -> None:
        """Hash and store password using SHA-256."""
        self._password_hash = hashlib.sha256(password.encode()).hexdigest()

    def verify_password(self, password: str) -> bool:
        """Verify password matches stored hash."""
        if not self._password_hash:
            return False
        return self._password_hash == hashlib.sha256(password.encode()).hexdigest()


def authenticate(username: str, password: str) -> Optional[User]:
    """Authenticate user with username and password.

    Returns User object if credentials are valid, None otherwise.
    """
    # In real app, would query database
    user = User(username, f"{username}@example.com")
    if user.verify_password(password):
        return user
    return None
''')

    # database.py - Database module
    (project_dir / "database.py").write_text('''"""Database connection and operations."""

import sqlite3
from pathlib import Path
from typing import List, Dict, Any


class DatabaseConnection:
    """SQLite database connection manager with context support."""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.conn = None

    def connect(self) -> None:
        """Open database connection."""
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row

    def close(self) -> None:
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None

    def execute_query(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """Execute SQL query and return results."""
        if not self.conn:
            self.connect()

        cursor = self.conn.cursor()
        cursor.execute(query, params)

        # Convert rows to dictionaries
        results = []
        for row in cursor.fetchall():
            results.append(dict(row))

        return results

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


def get_connection(db_path: str) -> DatabaseConnection:
    """Factory function to create database connection."""
    return DatabaseConnection(db_path)
''')

    # api.py - API handlers
    (project_dir / "api.py").write_text('''"""HTTP API request handlers."""

from typing import Dict, Any, Optional
import json


class APIRequest:
    """Represents an incoming API request."""

    def __init__(self, method: str, path: str, body: Optional[str] = None):
        self.method = method
        self.path = path
        self.body = body

    def get_json(self) -> Dict[str, Any]:
        """Parse request body as JSON."""
        if not self.body:
            return {}
        return json.loads(self.body)


class APIResponse:
    """Represents an API response."""

    def __init__(self, status_code: int, data: Any):
        self.status_code = status_code
        self.data = data

    def to_json(self) -> str:
        """Serialize response to JSON."""
        return json.dumps({
            "status": self.status_code,
            "data": self.data
        })


def handle_request(request: APIRequest) -> APIResponse:
    """Main request handler that routes to appropriate handler."""
    if request.method == "GET":
        return handle_get(request)
    elif request.method == "POST":
        return handle_post(request)
    else:
        return APIResponse(405, {"error": "Method not allowed"})


def handle_get(request: APIRequest) -> APIResponse:
    """Handle GET requests."""
    return APIResponse(200, {"message": f"GET {request.path}"})


def handle_post(request: APIRequest) -> APIResponse:
    """Handle POST requests."""
    data = request.get_json()
    return APIResponse(201, {"message": "Created", "data": data})
''')

    # utils.py - Utility functions
    (project_dir / "utils.py").write_text('''"""Utility functions and helpers."""

from typing import List, Any
from datetime import datetime


def format_timestamp(dt: datetime) -> str:
    """Format datetime as ISO 8601 string."""
    return dt.isoformat()


def parse_timestamp(timestamp: str) -> datetime:
    """Parse ISO 8601 timestamp string to datetime."""
    return datetime.fromisoformat(timestamp)


def validate_email(email: str) -> bool:
    """Validate email address format."""
    return "@" in email and "." in email.split("@")[1]


def chunk_list(items: List[Any], chunk_size: int) -> List[List[Any]]:
    """Split list into chunks of specified size."""
    return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]


def test_helper():
    """Helper function for testing purposes."""
    return "test result"
''')

    # main.py - Entry point
    (project_dir / "main.py").write_text('''"""Main application entry point."""

from auth import authenticate, User
from database import get_connection
from api import handle_request, APIRequest


def main():
    """Application main function."""
    print("Starting application...")

    # Example usage
    user = authenticate("admin", "password123")
    if user:
        print(f"Authenticated: {user.username}")

    # Database example
    with get_connection("app.db") as db:
        results = db.execute_query("SELECT * FROM users")
        print(f"Found {len(results)} users")

    # API example
    request = APIRequest("GET", "/api/users")
    response = handle_request(request)
    print(f"Response: {response.status_code}")


if __name__ == "__main__":
    main()
''')

    return project_dir


@pytest.fixture
def real_embeddings(monkeypatch):
    """Disable mock embeddings for E2E tests.

    E2E tests should use real embeddings to test actual system behavior.
    This fixture undoes the mock_embeddings fixture from conftest.py.
    """
    # The mock_embeddings fixture is autouse=False in root conftest
    # So we don't need to do anything special here
    # This fixture exists mainly for documentation and explicit intent
    yield
