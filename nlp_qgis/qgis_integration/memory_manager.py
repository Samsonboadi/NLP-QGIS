# qgis_integration/memory_manager.py
import gc
import os
import psutil
import time
import logging
from typing import Dict, List, Optional, Set, Tuple, Any
import weakref

class MemoryManager:
    """
    Memory management system for preventing excessive memory usage.
    
    This class monitors and manages memory consumption to prevent
    crashes and performance degradation in QGIS during NLP processing.
    """
    
    def __init__(self, warning_threshold_mb: int = 1000, critical_threshold_mb: int = 1500):
        """
        Initialize the memory manager.
        
        Args:
            warning_threshold_mb: Memory threshold for warning (in MB)
            critical_threshold_mb: Memory threshold for critical actions (in MB)
        """
        self.warning_threshold = warning_threshold_mb * 1024 * 1024  # Convert to bytes
        self.critical_threshold = critical_threshold_mb * 1024 * 1024  # Convert to bytes
        
        # Initialize cache tracking
        self.caches = {}  # name -> (size estimate, last_accessed, data)
        self.cache_access_history = {}  # name -> [list of access timestamps]
        
        # Setup logging
        self.logger = logging.getLogger("NLPGISPlugin.MemoryManager")
        
        # Cache for tracking objects
        self._tracked_objects = weakref.WeakValueDictionary()
        
    def get_current_memory_usage(self) -> int:
        """
        Get the current memory usage of the process in bytes.
        
        Returns:
            Current memory usage in bytes
        """
        process = psutil.Process(os.getpid())
        return process.memory_info().rss
        
    def get_memory_status(self) -> Dict[str, Any]:
        """
        Get detailed memory status information.
        
        Returns:
            Dictionary with memory stats
        """
        current_usage = self.get_current_memory_usage()
        return {
            'current_usage_bytes': current_usage,
            'current_usage_mb': current_usage / (1024 * 1024),
            'warning_threshold_mb': self.warning_threshold / (1024 * 1024),
            'critical_threshold_mb': self.critical_threshold / (1024 * 1024),
            'status': self._get_status_level(current_usage),
            'cache_count': len(self.caches),
            'total_cache_size_estimate_mb': sum(size for size, _, _ in self.caches.values()) / (1024 * 1024)
        }
        
    def _get_status_level(self, usage: int) -> str:
        """
        Get the current memory status level.
        
        Args:
            usage: Current memory usage in bytes
            
        Returns:
            Status level: 'normal', 'warning', or 'critical'
        """
        if usage >= self.critical_threshold:
            return 'critical'
        elif usage >= self.warning_threshold:
            return 'warning'
        else:
            return 'normal'
            
    def is_memory_critical(self) -> bool:
        """
        Check if memory usage is at a critical level.
        
        Returns:
            True if memory usage is critical, False otherwise
        """
        return self.get_current_memory_usage() >= self.critical_threshold
        
    def is_memory_warning(self) -> bool:
        """
        Check if memory usage is at a warning level.
        
        Returns:
            True if memory usage is at warning level, False otherwise
        """
        return self.get_current_memory_usage() >= self.warning_threshold
        
    def cache_data(self, name: str, data: Any, size_estimate: Optional[int] = None) -> bool:
        """
        Cache data with memory-aware caching policy.
        
        Args:
            name: Unique name for the cached data
            data: The data to cache
            size_estimate: Estimated size in bytes (optional)
            
        Returns:
            True if data was cached, False if rejected due to memory constraints
        """
        # Update access history
        now = time.time()
        if name not in self.cache_access_history:
            self.cache_access_history[name] = []
        self.cache_access_history[name].append(now)
        
        # Trim history to last 10 accesses
        if len(self.cache_access_history[name]) > 10:
            self.cache_access_history[name] = self.cache_access_history[name][-10:]
        
        # Check if we're already at critical memory levels
        if self.is_memory_critical():
            self.free_memory(aggressive=True)
            if self.is_memory_critical():  # Still critical after cleanup
                return False
        
        # Guess the size if not provided
        if size_estimate is None:
            # This is a very rough estimate
            size_estimate = sys.getsizeof(data)
            if hasattr(data, '__len__'):
                try:
                    # Adjust for container objects
                    size_estimate += len(data) * 8  # Rough approximation
                except:
                    pass
        
        # Cache the data with metadata
        self.caches[name] = (size_estimate, now, data)
        
        # If we hit warning threshold after caching, do some cleanup
        if self.is_memory_warning():
            self.free_memory(aggressive=False)
            
        return True
        
    def get_cached_data(self, name: str) -> Optional[Any]:
        """
        Retrieve cached data.
        
        Args:
            name: Name of the cached data
            
        Returns:
            The cached data or None if not found
        """
        if name in self.caches:
            size, _, data = self.caches[name]
            # Update the access time
            self.caches[name] = (size, time.time(), data)
            # Also update access history
            if name not in self.cache_access_history:
                self.cache_access_history[name] = []
            self.cache_access_history[name].append(time.time())
            return data
        return None
        
    def clear_cache(self, name: Optional[str] = None):
        """
        Clear specific cache or all caches.
        
        Args:
            name: Name of cache to clear, or None for all
        """
        if name is not None:
            if name in self.caches:
                del self.caches[name]
                if name in self.cache_access_history:
                    del self.cache_access_history[name]
        else:
            self.caches.clear()
            self.cache_access_history.clear()
            
    def free_memory(self, aggressive: bool = False) -> int:
        """
        Free memory by clearing caches and forcing garbage collection.
        
        Args:
            aggressive: If True, use more aggressive memory freeing techniques
            
        Returns:
            Estimated amount of memory freed in bytes
        """
        memory_before = self.get_current_memory_usage()
        freed_estimate = 0
        
        # First approach: Clear least recently used caches
        if self.caches:
            # Sort caches by access time
            sorted_caches = sorted(
                self.caches.items(),
                key=lambda x: x[1][1]  # Sort by last access time
            )
            
            # Clear either the oldest 25% or 50% depending on aggressiveness
            clear_count = max(1, len(sorted_caches) // (2 if aggressive else 4))
            for i in range(clear_count):
                name, (size, _, _) = sorted_caches[i]
                self.clear_cache(name)
                freed_estimate += size
        
        # Run garbage collection
        gc.collect()
        
        # Calculate actual memory freed
        memory_after = self.get_current_memory_usage()
        memory_freed = max(0, memory_before - memory_after)
        
        self.logger.info(
            f"Memory freed: {memory_freed / (1024*1024):.2f} MB "
            f"(Estimate: {freed_estimate / (1024*1024):.2f} MB)"
        )
        
        return memory_freed
        
    def track_object(self, obj: Any, name: Optional[str] = None) -> str:
        """
        Track an object to ensure proper cleanup.
        
        Args:
            obj: Object to track
            name: Optional name for the object
            
        Returns:
            A unique identifier for the tracked object
        """
        if name is None:
            name = f"obj_{id(obj)}_{time.time()}"
            
        self._tracked_objects[name] = obj
        return name
        
    def cleanup(self):
        """Perform cleanup when the plugin is unloaded."""
        # Clear all caches
        self.clear_cache()
        
        # Clear tracked objects
        self._tracked_objects.clear()
        
        # Force garbage collection
        gc.collect()