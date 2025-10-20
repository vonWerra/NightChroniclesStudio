# src/cache.py
# -*- coding: utf-8 -*-
"""Cache manager for storing intermediate results."""

import hashlib
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, Optional
import shutil

from src.logger import setup_logging

logger = setup_logging(__name__)


class CacheManager:
    """Manages caching of generation results."""

    def __init__(
        self,
        cache_dir: Path,
        enabled: bool = True,
        ttl_hours: int = 24
    ):
        self.cache_dir = Path(cache_dir)
        self.enabled = enabled
        self.ttl = timedelta(hours=ttl_hours)

        if enabled:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Cache initialized at {self.cache_dir}")

            # Clean old cache entries on init
            self._cleanup_old_entries()

    def _get_cache_path(self, key: str) -> Path:
        """Get cache file path for a key."""
        # Create hash of the key for filename
        key_hash = hashlib.sha256(key.encode()).hexdigest()[:16]
        return self.cache_dir / f"{key_hash}.cache"

    def _get_metadata_path(self, key: str) -> Path:
        """Get metadata file path for a key."""
        key_hash = hashlib.sha256(key.encode()).hexdigest()[:16]
        return self.cache_dir / f"{key_hash}.meta"

    def get(self, key: str) -> Optional[Any]:
        """Get cached value if exists and not expired."""
        if not self.enabled:
            return None

        cache_path = self._get_cache_path(key)
        meta_path = self._get_metadata_path(key)

        if not cache_path.exists() or not meta_path.exists():
            logger.debug(f"Cache miss for key: {key}")
            return None

        try:
            # Check metadata for expiry
            with meta_path.open('r', encoding='utf-8') as f:
                metadata = json.load(f)

            cached_time = datetime.fromisoformat(metadata['timestamp'])
            if datetime.now() - cached_time > self.ttl:
                logger.debug(f"Cache expired for key: {key}")
                self._remove_cache_files(key)
                return None

            # Load cached data (JSON instead of pickle for security)
            with cache_path.open('r', encoding='utf-8') as f:
                data = json.load(f)

            # Verify hash integrity
            data_str = json.dumps(data, sort_keys=True)
            computed_hash = hashlib.sha256(data_str.encode()).hexdigest()
            stored_hash = metadata.get('data_hash', '')

            if computed_hash != stored_hash:
                logger.warning(f"Cache integrity check failed for key: {key}")
                self._remove_cache_files(key)
                return None

            logger.debug(f"Cache hit for key: {key}")
            return data

        except Exception as e:
            logger.warning(f"Error reading cache for {key}: {e}")
            self._remove_cache_files(key)
            return None

    def set(self, key: str, value: Any) -> None:
        """Set cache value."""
        if not self.enabled:
            return

        cache_path = self._get_cache_path(key)
        meta_path = self._get_metadata_path(key)

        try:
            # Save data as JSON (safer than pickle)
            with cache_path.open('w', encoding='utf-8') as f:
                json.dump(value, f, ensure_ascii=False, indent=2)

            # Compute hash for integrity check
            data_str = json.dumps(value, sort_keys=True)
            data_hash = hashlib.sha256(data_str.encode()).hexdigest()

            # Save metadata
            metadata = {
                'key': key,
                'timestamp': datetime.now().isoformat(),
                'ttl_hours': self.ttl.total_seconds() / 3600,
                'data_hash': data_hash
            }
            with meta_path.open('w', encoding='utf-8') as f:
                json.dump(metadata, f)

            logger.debug(f"Cached value for key: {key}")

        except Exception as e:
            logger.error(f"Error caching value for {key}: {e}")
            self._remove_cache_files(key)

    def _remove_cache_files(self, key: str) -> None:
        """Remove cache files for a key."""
        cache_path = self._get_cache_path(key)
        meta_path = self._get_metadata_path(key)

        for path in [cache_path, meta_path]:
            if path.exists():
                try:
                    path.unlink()
                except Exception as e:
                    logger.warning(f"Could not remove {path}: {e}")

    def _cleanup_old_entries(self) -> None:
        """Remove expired cache entries."""
        if not self.enabled or not self.cache_dir.exists():
            return

        removed = 0
        for meta_file in self.cache_dir.glob("*.meta"):
            try:
                with meta_file.open('r', encoding='utf-8') as f:
                    metadata = json.load(f)

                cached_time = datetime.fromisoformat(metadata['timestamp'])
                if datetime.now() - cached_time > self.ttl:
                    # Remove both cache and meta files
                    cache_file = meta_file.with_suffix('.cache')
                    for path in [meta_file, cache_file]:
                        if path.exists():
                            path.unlink()
                    removed += 1

            except Exception as e:
                logger.debug(f"Error checking {meta_file}: {e}")

        if removed > 0:
            logger.info(f"Cleaned up {removed} expired cache entries")

    def clear(self) -> None:
        """Clear all cache."""
        if not self.enabled or not self.cache_dir.exists():
            return

        try:
            shutil.rmtree(self.cache_dir)
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            logger.info("Cache cleared")
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")

    def get_stats(self) -> dict:
        """Get cache statistics."""
        if not self.enabled or not self.cache_dir.exists():
            return {
                'enabled': self.enabled,
                'total_entries': 0,
                'total_size_mb': 0,
                'expired_entries': 0
            }

        total_entries = 0
        expired_entries = 0
        total_size = 0

        for meta_file in self.cache_dir.glob("*.meta"):
            try:
                total_entries += 1

                with meta_file.open('r', encoding='utf-8') as f:
                    metadata = json.load(f)

                cached_time = datetime.fromisoformat(metadata['timestamp'])
                if datetime.now() - cached_time > self.ttl:
                    expired_entries += 1

                # Add sizes
                cache_file = meta_file.with_suffix('.cache')
                if cache_file.exists():
                    total_size += cache_file.stat().st_size
                total_size += meta_file.stat().st_size

            except Exception:
                pass

        return {
            'enabled': self.enabled,
            'total_entries': total_entries,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'expired_entries': expired_entries
        }
