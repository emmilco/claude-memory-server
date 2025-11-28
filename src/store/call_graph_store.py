"""Qdrant storage for call graph data."""

import logging
from typing import List, Dict, Any, Optional, Set
from uuid import uuid4
from datetime import datetime, UTC

from qdrant_client import QdrantClient
from qdrant_client.models import (
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    MatchAny,
    SearchParams,
    Distance,
    VectorParams,
    OptimizersConfigDiff,
    HnswConfigDiff,
)

from src.config import ServerConfig
from src.core.exceptions import StorageError, MemoryNotFoundError
from src.graph.call_graph import CallGraph, CallSite, FunctionNode, InterfaceImplementation

logger = logging.getLogger(__name__)


class QdrantCallGraphStore:
    """
    Qdrant storage backend for call graph data.

    Uses a separate collection 'code_call_graph' to store function nodes,
    call sites, and implementation relationships.

    Collection Schema:
    - id: Function qualified name (e.g., "MyClass.method")
    - vector: Dummy vector [0.0] * 384 (not used for semantic search)
    - payload:
        - function_node: FunctionNode attributes
        - calls_to: List of callee function names (forward index)
        - called_by: List of caller function names (reverse index)
        - call_sites: List of CallSite objects
        - implementations: List of InterfaceImplementation objects (if function is interface)
        - project_name: Project identifier
        - indexed_at: Timestamp
    """

    def __init__(self, config: Optional[ServerConfig] = None):
        """
        Initialize call graph store.

        Args:
            config: Server configuration. If None, uses global config.
        """
        if config is None:
            from src.config import get_config
            config = get_config()

        self.config = config
        self.collection_name = "code_call_graph"
        # Dummy vector size must match embedding model for collection compatibility
        model_dims = {
            "all-MiniLM-L6-v2": 384,
            "all-MiniLM-L12-v2": 384,
            "all-mpnet-base-v2": 768,
        }
        self.vector_size = model_dims.get(config.embedding_model, 768)
        self.client: Optional[QdrantClient] = None

    async def initialize(self) -> None:
        """Initialize Qdrant connection and ensure collection exists."""
        try:
            # Connect to Qdrant
            self.client = QdrantClient(
                url=self.config.qdrant_url,
                api_key=self.config.qdrant_api_key,
                timeout=30.0,
            )

            # Test connection
            self.client.get_collections()

            # Ensure collection exists
            if not self._collection_exists():
                self._create_collection()

            logger.info(f"Call graph store initialized: {self.collection_name}")

        except Exception as e:
            raise StorageError(f"Failed to initialize call graph store: {e}") from e

    def _collection_exists(self) -> bool:
        """Check if call graph collection exists."""
        try:
            collections = self.client.get_collections().collections
            return any(c.name == self.collection_name for c in collections)
        except Exception as e:
            logger.error(f"Failed to check collection existence: {e}")
            return False

    def _create_collection(self) -> None:
        """Create call graph collection with optimized settings."""
        try:
            logger.info(f"Creating call graph collection: {self.collection_name}")

            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.vector_size,
                    distance=Distance.COSINE,
                ),
                optimizers_config=OptimizersConfigDiff(
                    indexing_threshold=5000,
                ),
                hnsw_config=HnswConfigDiff(
                    m=16,
                    ef_construct=100,
                    full_scan_threshold=1000,
                ),
            )

            logger.info(f"Collection {self.collection_name} created successfully")

        except Exception as e:
            raise StorageError(f"Failed to create call graph collection: {e}") from e

    async def store_function_node(
        self,
        node: FunctionNode,
        project_name: str,
        calls_to: Optional[List[str]] = None,
        called_by: Optional[List[str]] = None,
    ) -> str:
        """
        Store a function node in the call graph.

        Args:
            node: Function node to store
            project_name: Project identifier
            calls_to: List of callee function names
            called_by: List of caller function names

        Returns:
            UUID string used as point ID
        """
        if self.client is None:
            await self.initialize()

        try:
            # Generate UUID for point ID
            point_id = str(uuid4())

            # Build payload (includes qualified_name for lookups)
            payload = {
                "function_node": {
                    "name": node.name,
                    "qualified_name": node.qualified_name,
                    "file_path": node.file_path,
                    "language": node.language,
                    "start_line": node.start_line,
                    "end_line": node.end_line,
                    "is_exported": node.is_exported,
                    "is_async": node.is_async,
                    "parameters": node.parameters,
                    "return_type": node.return_type,
                },
                "calls_to": calls_to or [],
                "called_by": called_by or [],
                "call_sites": [],  # Stored separately via store_call_sites
                "implementations": [],  # Stored separately via store_implementations
                "project_name": project_name,
                "qualified_name": node.qualified_name,  # For filtering/lookup
                "indexed_at": datetime.now(UTC).isoformat(),
            }

            # Create point with dummy vector
            point = PointStruct(
                id=point_id,
                vector=[0.0] * self.vector_size,
                payload=payload,
            )

            # Upsert to Qdrant
            self.client.upsert(
                collection_name=self.collection_name,
                points=[point],
            )

            logger.debug(f"Stored function node: {node.qualified_name} (ID: {point_id})")
            return point_id

        except Exception as e:
            raise StorageError(f"Failed to store function node: {e}") from e

    async def store_call_sites(
        self,
        function_name: str,
        call_sites: List[CallSite],
        project_name: str,
    ) -> None:
        """
        Store call sites for a function.

        Args:
            function_name: Function qualified name
            call_sites: List of call sites to store
            project_name: Project identifier
        """
        if self.client is None:
            await self.initialize()

        try:
            # Find existing point by qualified_name
            results = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key="qualified_name",
                            match=MatchValue(value=function_name),
                        ),
                        FieldCondition(
                            key="project_name",
                            match=MatchValue(value=project_name),
                        ),
                    ]
                ),
                limit=1,
                with_payload=True,
                with_vectors=False,
            )

            points, _ = results

            if not points:
                raise MemoryNotFoundError(f"Function not found: {function_name}")

            # Update call_sites in payload
            point = points[0]
            payload = point.payload
            payload["call_sites"] = [
                {
                    "caller_function": cs.caller_function,
                    "caller_file": cs.caller_file,
                    "caller_line": cs.caller_line,
                    "callee_function": cs.callee_function,
                    "callee_file": cs.callee_file,
                    "call_type": cs.call_type,
                }
                for cs in call_sites
            ]

            # Upsert updated point
            updated_point = PointStruct(
                id=point.id,
                vector=[0.0] * self.vector_size,
                payload=payload,
            )

            self.client.upsert(
                collection_name=self.collection_name,
                points=[updated_point],
            )

            logger.debug(f"Stored {len(call_sites)} call sites for {function_name}")

        except MemoryNotFoundError:
            raise
        except Exception as e:
            raise StorageError(f"Failed to store call sites: {e}") from e

    async def store_implementations(
        self,
        interface_name: str,
        implementations: List[InterfaceImplementation],
        project_name: str,
    ) -> None:
        """
        Store interface implementations.

        Args:
            interface_name: Interface/trait/ABC name
            implementations: List of implementations
            project_name: Project identifier
        """
        if self.client is None:
            await self.initialize()

        try:
            # Check if interface node exists
            results = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key="qualified_name",
                            match=MatchValue(value=interface_name),
                        ),
                        FieldCondition(
                            key="project_name",
                            match=MatchValue(value=project_name),
                        ),
                    ]
                ),
                limit=1,
                with_payload=True,
                with_vectors=False,
            )

            points, _ = results

            if points:
                # Update existing point
                point = points[0]
                payload = point.payload
                payload["implementations"] = [
                    {
                        "interface_name": impl.interface_name,
                        "implementation_name": impl.implementation_name,
                        "file_path": impl.file_path,
                        "language": impl.language,
                        "methods": impl.methods,
                    }
                    for impl in implementations
                ]

                updated_point = PointStruct(
                    id=point.id,
                    vector=[0.0] * self.vector_size,
                    payload=payload,
                )
            else:
                # Create new point for interface
                payload = {
                    "function_node": {
                        "name": interface_name,
                        "qualified_name": interface_name,
                        "file_path": "",
                        "language": implementations[0].language if implementations else "unknown",
                        "start_line": 0,
                        "end_line": 0,
                        "is_exported": True,
                        "is_async": False,
                        "parameters": [],
                        "return_type": None,
                    },
                    "calls_to": [],
                    "called_by": [],
                    "call_sites": [],
                    "implementations": [
                        {
                            "interface_name": impl.interface_name,
                            "implementation_name": impl.implementation_name,
                            "file_path": impl.file_path,
                            "language": impl.language,
                            "methods": impl.methods,
                        }
                        for impl in implementations
                    ],
                    "project_name": project_name,
                    "qualified_name": interface_name,
                    "indexed_at": datetime.now(UTC).isoformat(),
                }

                updated_point = PointStruct(
                    id=str(uuid4()),
                    vector=[0.0] * self.vector_size,
                    payload=payload,
                )

            self.client.upsert(
                collection_name=self.collection_name,
                points=[updated_point],
            )

            logger.debug(f"Stored {len(implementations)} implementations for {interface_name}")

        except Exception as e:
            raise StorageError(f"Failed to store implementations: {e}") from e

    async def load_call_graph(self, project_name: str) -> CallGraph:
        """
        Load entire call graph for a project.

        Args:
            project_name: Project identifier

        Returns:
            CallGraph instance populated with all nodes and edges
        """
        if self.client is None:
            await self.initialize()

        try:
            graph = CallGraph()

            # Scroll through all points for this project
            offset = None
            batch_size = 100

            while True:
                results = self.client.scroll(
                    collection_name=self.collection_name,
                    scroll_filter=Filter(
                        must=[
                            FieldCondition(
                                key="project_name",
                                match=MatchValue(value=project_name),
                            )
                        ]
                    ),
                    limit=batch_size,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False,
                )

                points, offset = results

                if not points:
                    break

                for point in points:
                    payload = point.payload

                    # Add function node
                    fn_data = payload["function_node"]
                    node = FunctionNode(
                        name=fn_data["name"],
                        qualified_name=fn_data["qualified_name"],
                        file_path=fn_data["file_path"],
                        language=fn_data["language"],
                        start_line=fn_data["start_line"],
                        end_line=fn_data["end_line"],
                        is_exported=fn_data["is_exported"],
                        is_async=fn_data["is_async"],
                        parameters=fn_data["parameters"],
                        return_type=fn_data.get("return_type"),
                    )
                    graph.add_function(node)

                    # Add call sites
                    for cs_data in payload.get("call_sites", []):
                        call_site = CallSite(
                            caller_function=cs_data["caller_function"],
                            caller_file=cs_data["caller_file"],
                            caller_line=cs_data["caller_line"],
                            callee_function=cs_data["callee_function"],
                            callee_file=cs_data.get("callee_file"),
                            call_type=cs_data["call_type"],
                        )
                        graph.add_call(call_site)

                    # Add implementations
                    for impl_data in payload.get("implementations", []):
                        impl = InterfaceImplementation(
                            interface_name=impl_data["interface_name"],
                            implementation_name=impl_data["implementation_name"],
                            file_path=impl_data["file_path"],
                            language=impl_data["language"],
                            methods=impl_data["methods"],
                        )
                        graph.add_implementation(impl)

                if offset is None:
                    break

            logger.info(f"Loaded call graph for {project_name}: {len(graph.nodes)} nodes, {len(graph.calls)} calls")
            return graph

        except Exception as e:
            raise StorageError(f"Failed to load call graph: {e}") from e

    async def find_function_by_name(
        self,
        function_name: str,
        project_name: str,
    ) -> Optional[FunctionNode]:
        """
        Find a function by name in the call graph.

        Args:
            function_name: Function qualified name
            project_name: Project identifier

        Returns:
            FunctionNode if found, None otherwise
        """
        if self.client is None:
            await self.initialize()

        try:
            results = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key="qualified_name",
                            match=MatchValue(value=function_name),
                        ),
                        FieldCondition(
                            key="project_name",
                            match=MatchValue(value=project_name),
                        ),
                    ]
                ),
                limit=1,
                with_payload=True,
                with_vectors=False,
            )

            points, _ = results

            if not points:
                return None

            fn_data = points[0].payload["function_node"]
            return FunctionNode(
                name=fn_data["name"],
                qualified_name=fn_data["qualified_name"],
                file_path=fn_data["file_path"],
                language=fn_data["language"],
                start_line=fn_data["start_line"],
                end_line=fn_data["end_line"],
                is_exported=fn_data["is_exported"],
                is_async=fn_data["is_async"],
                parameters=fn_data["parameters"],
                return_type=fn_data.get("return_type"),
            )

        except Exception as e:
            logger.error(f"Error finding function {function_name}: {e}")
            return None

    async def get_call_sites_for_caller(
        self,
        caller_function: str,
        project_name: str,
    ) -> List[CallSite]:
        """
        Get all call sites from a specific caller function.

        Args:
            caller_function: Caller function name
            project_name: Project identifier

        Returns:
            List of CallSite objects
        """
        if self.client is None:
            await self.initialize()

        try:
            results = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key="qualified_name",
                            match=MatchValue(value=caller_function),
                        ),
                        FieldCondition(
                            key="project_name",
                            match=MatchValue(value=project_name),
                        ),
                    ]
                ),
                limit=1,
                with_payload=True,
                with_vectors=False,
            )

            points, _ = results

            if not points:
                return []

            call_sites_data = points[0].payload.get("call_sites", [])
            return [
                CallSite(
                    caller_function=cs["caller_function"],
                    caller_file=cs["caller_file"],
                    caller_line=cs["caller_line"],
                    callee_function=cs["callee_function"],
                    callee_file=cs.get("callee_file"),
                    call_type=cs["call_type"],
                )
                for cs in call_sites_data
            ]

        except Exception as e:
            logger.error(f"Error getting call sites for {caller_function}: {e}")
            return []

    async def get_implementations(
        self,
        interface_name: str,
        project_name: Optional[str] = None,
    ) -> List[InterfaceImplementation]:
        """
        Get all implementations of an interface.

        Args:
            interface_name: Interface name
            project_name: Optional project filter

        Returns:
            List of InterfaceImplementation objects
        """
        if self.client is None:
            await self.initialize()

        try:
            # Build filter conditions
            conditions = [
                FieldCondition(
                    key="qualified_name",
                    match=MatchValue(value=interface_name),
                )
            ]

            if project_name:
                conditions.append(
                    FieldCondition(
                        key="project_name",
                        match=MatchValue(value=project_name),
                    )
                )

            results = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=Filter(must=conditions),
                limit=1,
                with_payload=True,
                with_vectors=False,
            )

            points, _ = results

            if not points:
                return []

            impl_data_list = points[0].payload.get("implementations", [])
            return [
                InterfaceImplementation(
                    interface_name=impl["interface_name"],
                    implementation_name=impl["implementation_name"],
                    file_path=impl["file_path"],
                    language=impl["language"],
                    methods=impl["methods"],
                )
                for impl in impl_data_list
            ]

        except Exception as e:
            logger.error(f"Error getting implementations for {interface_name}: {e}")
            return []

    async def delete_project_call_graph(self, project_name: str) -> int:
        """
        Delete all call graph data for a project.

        Args:
            project_name: Project identifier

        Returns:
            Number of points deleted
        """
        if self.client is None:
            await self.initialize()

        try:
            # Delete points matching project_name
            result = self.client.delete(
                collection_name=self.collection_name,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="project_name",
                            match=MatchValue(value=project_name),
                        )
                    ]
                ),
            )

            count = result.operation_id if hasattr(result, "operation_id") else 0
            logger.info(f"Deleted {count} call graph points for project {project_name}")
            return count

        except Exception as e:
            raise StorageError(f"Failed to delete project call graph: {e}") from e
