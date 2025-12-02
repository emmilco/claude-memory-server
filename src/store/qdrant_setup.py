"""Qdrant collection setup and initialization."""

import logging
import time
from typing import Optional
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    OptimizersConfigDiff,
    HnswConfigDiff,
    ScalarQuantization,
    ScalarQuantizationConfig,
    ScalarType,
    QuantizationSearchParams,
    PayloadSchemaType,
)
from src.config import ServerConfig
from src.core.exceptions import QdrantConnectionError, StorageError
from src.store.connection_pool import QdrantConnectionPool

logger = logging.getLogger(__name__)


class QdrantSetup:
    """Manages Qdrant collection initialization and configuration."""

    def __init__(self, config: Optional[ServerConfig] = None, use_pool: bool = True):
        """
        Initialize Qdrant setup manager.

        Args:
            config: Server configuration. If None, uses global config.
            use_pool: If True, create connection pool. If False, use single client (legacy mode).
        """
        if config is None:
            from src.config import get_config
            config = get_config()

        self.config = config
        self.collection_name = config.qdrant_collection_name
        # Vector size based on embedding model
        model_dims = {
            "all-MiniLM-L6-v2": 384,
            "all-MiniLM-L12-v2": 384,
            "all-mpnet-base-v2": 768,
        }
        self.vector_size = model_dims.get(config.embedding_model, 768)
        self.use_pool = use_pool
        self.client: Optional[QdrantClient] = None
        self.pool: Optional[QdrantConnectionPool] = None

    def connect(self) -> QdrantClient:
        """
        Connect to Qdrant server with retry logic.

        Returns:
            QdrantClient: Connected Qdrant client.

        Raises:
            QdrantConnectionError: If connection fails after retries.
        """
        max_retries = 3
        base_delay = 0.5  # seconds

        for attempt in range(max_retries):
            try:
                self.client = QdrantClient(
                    url=self.config.qdrant_url,
                    api_key=self.config.qdrant_api_key,
                    timeout=30.0,  # Increased from 10.0 for parallel tests
                )
                # Test connection
                self.client.get_collections()
                logger.info(f"Connected to Qdrant at {self.config.qdrant_url}")
                return self.client
            except Exception as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(
                        f"Qdrant connection attempt {attempt + 1}/{max_retries} failed: {e}. "
                        f"Retrying in {delay}s..."
                    )
                    time.sleep(delay)
                else:
                    # Final attempt failed
                    raise QdrantConnectionError(
                        url=self.config.qdrant_url,
                        reason=str(e)
                    )

    async def create_pool(
        self,
        min_size: Optional[int] = None,
        max_size: Optional[int] = None,
        timeout: Optional[float] = None,
        recycle: Optional[int] = None,
        enable_health_checks: bool = True,
        enable_monitoring: bool = False,
    ) -> QdrantConnectionPool:
        """
        Create and initialize a connection pool.

        Args:
            min_size: Minimum pool size (uses config if None)
            max_size: Maximum pool size (uses config if None)
            timeout: Acquire timeout (uses config if None)
            recycle: Connection recycle time (uses config if None)
            enable_health_checks: Enable health checking
            enable_monitoring: Enable background monitoring

        Returns:
            QdrantConnectionPool: Initialized connection pool

        Raises:
            QdrantConnectionError: If pool creation fails
        """
        # Use config defaults if not provided
        min_size = min_size or getattr(self.config, 'qdrant_pool_min_size', 1)
        max_size = max_size or getattr(self.config, 'qdrant_pool_size', 5)
        timeout = timeout or getattr(self.config, 'qdrant_pool_timeout', 10.0)
        recycle = recycle or getattr(self.config, 'qdrant_pool_recycle', 3600)

        logger.info(
            f"Creating connection pool: min={min_size}, max={max_size}, "
            f"timeout={timeout}s, recycle={recycle}s"
        )

        self.pool = QdrantConnectionPool(
            config=self.config,
            min_size=min_size,
            max_size=max_size,
            timeout=timeout,
            recycle=recycle,
            enable_health_checks=enable_health_checks,
            enable_monitoring=enable_monitoring,
        )

        await self.pool.initialize()
        logger.info("Connection pool initialized successfully")
        return self.pool

    def collection_exists(self) -> bool:
        """
        Check if the memory collection exists.

        Returns:
            bool: True if collection exists, False otherwise.
        """
        if self.client is None:
            self.connect()

        try:
            collections = self.client.get_collections().collections
            return any(c.name == self.collection_name for c in collections)
        except Exception as e:
            logger.error(f"Failed to check collection existence: {e}", exc_info=True)
            return False

    def create_collection(self, recreate: bool = False) -> None:
        """
        Create the memory collection with optimized settings.

        Args:
            recreate: If True, delete existing collection first.

        Raises:
            StorageError: If collection creation fails.
        """
        if self.client is None:
            self.connect()

        try:
            # Delete existing collection if recreate=True
            if recreate and self.collection_exists():
                logger.info(f"Deleting existing collection: {self.collection_name}")
                self.client.delete_collection(self.collection_name)

            # Skip if collection already exists
            if self.collection_exists():
                logger.info(f"Collection {self.collection_name} already exists")
                return

            logger.info(f"Creating collection: {self.collection_name}")

            # Create collection with optimized HNSW parameters
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.vector_size,
                    distance=Distance.COSINE,
                ),
                optimizers_config=OptimizersConfigDiff(
                    indexing_threshold=10000,  # Start indexing after 10k vectors
                ),
                hnsw_config=HnswConfigDiff(
                    m=16,  # Number of connections per element
                    ef_construct=200,  # Construction time accuracy
                    full_scan_threshold=2000,  # Use full scan for small collections
                ),
                quantization_config=ScalarQuantization(
                    scalar=ScalarQuantizationConfig(
                        type=ScalarType.INT8,  # 75% memory savings
                        quantile=0.99,
                        always_ram=True,
                    )
                ),
            )

            logger.info(f"Collection {self.collection_name} created successfully")

        except Exception as e:
            raise StorageError(f"Failed to create collection: {e}") from e

    def create_payload_indices(self) -> None:
        """
        Create payload indices for efficient filtering.

        Creates indices for:
        - category (keyword)
        - context_level (keyword)
        - scope (keyword)
        - project_name (keyword)
        - importance (float)
        - tags (keyword list)
        """
        if self.client is None:
            self.connect()

        try:
            # Create keyword indices for filtering
            fields_to_index = [
                ("category", PayloadSchemaType.KEYWORD),
                ("context_level", PayloadSchemaType.KEYWORD),
                ("scope", PayloadSchemaType.KEYWORD),
                ("project_name", PayloadSchemaType.KEYWORD),
                ("importance", PayloadSchemaType.FLOAT),
                ("tags", PayloadSchemaType.KEYWORD),
            ]

            for field_name, schema_type in fields_to_index:
                try:
                    self.client.create_payload_index(
                        collection_name=self.collection_name,
                        field_name=field_name,
                        field_schema=schema_type,
                    )
                    logger.info(f"Created payload index for: {field_name}")
                except Exception as e:
                    # Index might already exist, that's okay
                    logger.debug(f"Index creation for {field_name} failed (may already exist): {e}")

        except Exception as e:
            logger.warning(f"Failed to create some payload indices: {e}")

    def ensure_collection_exists(self) -> None:
        """
        Ensure the collection exists and is properly configured.

        This is the main entry point for initialization.
        """
        if self.client is None:
            self.connect()

        if not self.collection_exists():
            self.create_collection()
            self.create_payload_indices()
        else:
            logger.info(f"Collection {self.collection_name} already configured")

    def get_collection_info(self) -> dict:
        """
        Get information about the collection.

        Returns:
            dict: Collection information including vector count, config, etc.
        """
        if self.client is None:
            self.connect()

        try:
            collection_info = self.client.get_collection(self.collection_name)
            return {
                "name": self.collection_name,
                "vectors_count": collection_info.vectors_count,
                "points_count": collection_info.points_count,
                "status": collection_info.status,
                "optimizer_status": collection_info.optimizer_status,
            }
        except Exception as e:
            logger.error(f"Failed to get collection info: {e}", exc_info=True)
            return {}

    def health_check(self) -> bool:
        """
        Check if Qdrant is healthy and accessible.

        Returns:
            bool: True if healthy, False otherwise.
        """
        try:
            if self.client is None:
                self.connect()

            # Try to list collections as a health check
            self.client.get_collections()
            return True
        except Exception as e:
            logger.error(f"Qdrant health check failed: {e}", exc_info=True)
            return False
