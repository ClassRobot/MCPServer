"""Runtime output directory LRU pruner.

Keeps a bounded set of generated files (PNG renders, PDF pages, Markdown outputs)
so that long-running deployments never exhaust disk space.

The algorithm mirrors SearchCacheStore.prune():
  1. Stat every file in the target directory.
  2. Remove files whose mtime is older than ``max_age_sec``.
  3. If the surviving count still exceeds ``max_entries``, sort by mtime descending
     (most-recent first) and delete the tail.

All I/O is synchronous and designed to run inside ``asyncio.to_thread``.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def prune_output_dir(
    directory: Path,
    *,
    max_entries: int,
    max_age_sec: float,
    glob_pattern: str = "*",
) -> int:
    """Remove stale or excess files from *directory* and return the number deleted.

    Args:
        directory: Target directory to prune. Does nothing if it does not exist.
        max_entries: Maximum number of files to keep after pruning.
        max_age_sec: Files older than this many seconds are unconditionally removed.
        glob_pattern: Glob pattern used to select candidate files (default: all files).

    Returns:
        Number of files that were deleted.
    """
    if not directory.exists():
        return 0

    try:
        candidate_files = [p for p in directory.glob(glob_pattern) if p.is_file()]
    except OSError:
        return 0

    import time

    now_ts = time.time()
    deleted = 0
    surviving: list[tuple[float, Path]] = []

    for path in candidate_files:
        try:
            mtime = path.stat().st_mtime
            if now_ts - mtime > max_age_sec:
                path.unlink(missing_ok=True)
                deleted += 1
            else:
                surviving.append((mtime, path))
        except OSError:
            continue

    # Evict the oldest entries if still over the cap.
    if len(surviving) > max_entries:
        surviving.sort(key=lambda item: item[0], reverse=True)  # newest first
        for _, extra_path in surviving[max_entries:]:
            try:
                extra_path.unlink(missing_ok=True)
                deleted += 1
            except OSError:
                continue

    if deleted:
        logger.debug(
            "Pruned output directory",
            extra={
                "mcp_event": "cleanup.prune",
                "mcp_fields": {
                    "directory": str(directory),
                    "deleted": deleted,
                    "max_entries": max_entries,
                    "max_age_sec": max_age_sec,
                },
            },
        )

    return deleted
