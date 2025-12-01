"""File-based locking mechanism for backup operations."""

import asyncio
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime, UTC
import os

logger = logging.getLogger(__name__)


class FileLock:
    """
    File-based lock for preventing concurrent backup cleanup operations.

    This lock ensures that only one cleanup operation (either from the scheduler
    or from the CLI) can run at a time to prevent race conditions.
    """

    def __init__(self, lock_file: Path, timeout: float = 300.0):
        """
        Initialize file lock.

        Args:
            lock_file: Path to lock file
            timeout: Maximum time to wait for lock (seconds)
        """
        self.lock_file = lock_file
        self.timeout = timeout
        self._lock_acquired = False

    async def acquire(self) -> bool:
        """
        Acquire the lock.

        Returns:
            True if lock was acquired, False if timeout
        """
        start_time = datetime.now(UTC)

        while True:
            try:
                # Try to create lock file exclusively
                # O_CREAT | O_EXCL ensures atomic creation
                fd = os.open(
                    self.lock_file,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                    0o644
                )

                # Write timestamp and PID to lock file
                lock_info = f"{datetime.now(UTC).isoformat()}\nPID: {os.getpid()}\n"
                os.write(fd, lock_info.encode())
                os.close(fd)

                self._lock_acquired = True
                logger.debug(f"Acquired lock: {self.lock_file}")
                return True

            except FileExistsError:
                # Lock file already exists, another process has the lock
                elapsed = (datetime.now(UTC) - start_time).total_seconds()

                if elapsed >= self.timeout:
                    logger.warning(
                        f"Failed to acquire lock after {elapsed:.1f}s timeout: {self.lock_file}"
                    )
                    return False

                # Check if lock file is stale (older than timeout)
                try:
                    stat = self.lock_file.stat()
                    lock_age = datetime.now(UTC).timestamp() - stat.st_mtime

                    if lock_age > self.timeout:
                        logger.warning(
                            f"Removing stale lock file (age: {lock_age:.1f}s): {self.lock_file}"
                        )
                        self.lock_file.unlink(missing_ok=True)
                        continue

                except FileNotFoundError:
                    # Lock was released between check and stat
                    continue

                # Wait before retrying
                await asyncio.sleep(1.0)

    async def release(self):
        """Release the lock."""
        if not self._lock_acquired:
            return

        try:
            self.lock_file.unlink(missing_ok=True)
            self._lock_acquired = False
            logger.debug(f"Released lock: {self.lock_file}")
        except Exception as e:
            logger.error(f"Error releasing lock {self.lock_file}: {e}")

    async def __aenter__(self):
        """Async context manager entry."""
        acquired = await self.acquire()
        if not acquired:
            raise TimeoutError(f"Failed to acquire lock: {self.lock_file}")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.release()
        return False
