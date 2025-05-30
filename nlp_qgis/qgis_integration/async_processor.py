# qgis_integration/async_processor.py
import asyncio
import concurrent.futures
import threading
import time
from typing import Any, Callable, Dict, Optional, Tuple
from qgis.PyQt.QtCore import QObject, pyqtSignal, pyqtSlot

class AsyncTaskManager(QObject):
    """
    Manages asynchronous processing of NLP tasks to prevent UI blocking.
    
    This class handles the execution of computationally intensive NLP 
    processing in a way that doesn't block the QGIS user interface.
    """
    
    # Signals to communicate task status
    task_completed = pyqtSignal(str, object)  # task_id, result
    task_failed = pyqtSignal(str, str)  # task_id, error_message
    task_progress = pyqtSignal(str, int)  # task_id, progress_percentage
    
    def __init__(self):
        """Initialize the async task manager."""
        super().__init__()
        
        # Thread pool for CPU-bound operations
        self.thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        
        # Task tracking
        self.active_tasks = {}  # task_id -> future
        self.task_metadata = {}  # task_id -> metadata dict
        
        # Create event loop for async operations
        self.loop = asyncio.new_event_loop()
        
        # Start event loop in a separate thread
        self.thread = threading.Thread(target=self._run_event_loop, daemon=True)
        self.thread.start()
        
    def _run_event_loop(self):
        """Run the asyncio event loop in a background thread."""
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()
        
    def _create_task_id(self) -> str:
        """Create a unique task ID."""
        return f"task_{int(time.time() * 1000)}"
        
    async def _run_in_thread(self, func, *args, **kwargs):
        """Run a function in the thread pool."""
        return await self.loop.run_in_executor(
            self.thread_pool, 
            lambda: func(*args, **kwargs)
        )
        
    async def _execute_task(self, task_id: str, func: Callable, *args, **kwargs):
        """Execute the task and handle results/errors."""
        try:
            # Update status
            self.task_metadata[task_id]['status'] = 'running'
            
            # Execute the function in thread pool
            result = await self._run_in_thread(func, *args, **kwargs)
            
            # Task completed successfully
            self.task_metadata[task_id]['status'] = 'completed'
            self.task_completed.emit(task_id, result)
            
        except Exception as e:
            # Task failed
            self.task_metadata[task_id]['status'] = 'failed'
            self.task_metadata[task_id]['error'] = str(e)
            self.task_failed.emit(task_id, str(e))
            
        finally:
            # Clean up
            if task_id in self.active_tasks:
                del self.active_tasks[task_id]
                
    def submit_task(self, func: Callable, *args, **kwargs) -> str:
        """
        Submit a task for asynchronous execution.
        
        Args:
            func: The function to execute
            *args, **kwargs: Arguments to pass to the function
            
        Returns:
            task_id: A unique identifier for this task
        """
        task_id = self._create_task_id()
        
        # Create task metadata
        self.task_metadata[task_id] = {
            'status': 'pending',
            'submitted_time': time.time(),
            'function': func.__name__,
        }
        
        # Create and store the task
        task = asyncio.run_coroutine_threadsafe(
            self._execute_task(task_id, func, *args, **kwargs), 
            self.loop
        )
        
        self.active_tasks[task_id] = task
        return task_id
        
    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a running task.
        
        Args:
            task_id: The ID of the task to cancel
            
        Returns:
            bool: True if the task was cancelled, False otherwise
        """
        if task_id in self.active_tasks:
            # Try to cancel the future
            cancelled = self.active_tasks[task_id].cancel()
            
            if cancelled:
                self.task_metadata[task_id]['status'] = 'cancelled'
                del self.active_tasks[task_id]
                
            return cancelled
            
        return False
        
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the status of a task.
        
        Args:
            task_id: The ID of the task
            
        Returns:
            Dict containing task metadata or None if task not found
        """
        return self.task_metadata.get(task_id)
        
    def cleanup(self):
        """Clean up resources when the plugin is unloaded."""
        # Cancel all active tasks
        for task_id in list(self.active_tasks.keys()):
            self.cancel_task(task_id)
            
        # Shutdown thread pool
        self.thread_pool.shutdown(wait=False)
        
        # Stop event loop
        self.loop.call_soon_threadsafe(self.loop.stop)
        
        # Wait for thread to finish
        if self.thread.is_alive():
            self.thread.join(timeout=1.0)