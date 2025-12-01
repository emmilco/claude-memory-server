"""File-based locking mechanism for backup operations."""

import asyncio
import logging
from pathlib import Path
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
        self._lock_pid = None  # Track PID to verify ownership

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
                # Convert Path to str for os.open compatibility
                fd = os.open(
                    str(self.lock_file),
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                    0o644
                )

                # Write timestamp and PID to lock file
                # Use try/finally to ensure fd is closed even if write fails
                try:
                    current_pid = os.getpid()
                    lock_info = f"{datetime.now(UTC).isoformat()}\nPID: {current_pid}\n"
                    os.write(fd, lock_info.encode())
                finally:
                    os.close(fd)

                self._lock_acquired = True
                self._lock_pid = current_pid
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
                        # Lock is stale - attempt to remove it
                        # This is safe because we only remove files older than timeout
                        try:
                            self.lock_file.unlink(missing_ok=True)
                            logger.warning(
                                f"Removed stale lock file (age: {lock_age:.1f}s): {self.lock_file}"
                            )
                            # Continue to next iteration to try acquiring the lock
                            continue
                        except OSError:
                            # Lock file was already deleted by another process, retry
                            continue

                except FileNotFoundError:
                    # Lock was released between check and stat, retry
                    continue

                # Wait before retrying
                await asyncio.sleep(1.0)

    async def release(self):
        """Release the lock."""
        if not self._lock_acquired:
            return

        try:
            # Only remove lock file if we still own it (same PID)
            # This prevents accidentally removing another process's lock
            # if we timed out and another process acquired it
            if self._lock_pid == os.getpid():
                self.lock_file.unlink(missing_ok=True)
                logger.debug(f"Released lock: {self.lock_file}")
            else:
                logger.warning(
                    f"Lock PID mismatch - not releasing lock. "
                    f"Expected {self._lock_pid}, current {os.getpid()}"
                )

            self._lock_acquired = False
            self._lock_pid = None
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
