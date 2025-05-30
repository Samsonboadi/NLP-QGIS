# qgis_integration/__init__.py
from .async_processor import AsyncTaskManager
from .memory_manager import MemoryManager
from .event_dispatcher import GISEventDispatcher

class QGISIntegration:
    """Main integration class for connecting NLP with QGIS."""
    
    def __init__(self, iface):
        """
        Initialize QGIS integration components.
        
        Args:
            iface: QGIS interface instance
        """
        self.iface = iface
        
        # Initialize components
        self.async_manager = AsyncTaskManager()
        self.memory_manager = MemoryManager()
        self.event_dispatcher = GISEventDispatcher(iface)
        
        # Register standard GIS operations
        self._register_operation_handlers()
        
    def _register_operation_handlers(self):
        """Register handlers for common GIS operations."""
        # Register buffer operation
        self.event_dispatcher.register_command_handler(
            'buffer', 
            lambda cmd: self._handle_buffer_command(cmd)
        )
        
        # Register clip operation
        self.event_dispatcher.register_command_handler(
            'clip',
            lambda cmd: self._handle_clip_command(cmd)
        )
        
        # Register select operation
        self.event_dispatcher.register_command_handler(
            'select',
            lambda cmd: self._handle_select_command(cmd)
        )
        
        # Register intersect operation
        self.event_dispatcher.register_command_handler(
            'intersect',
            lambda cmd: self._handle_intersect_command(cmd)
        )
        
    def _handle_buffer_command(self, command):
        """Handle buffer command execution."""
        # Extract parameters from the command
        input_layer = command.get('input_layer')
        distance = command.get('parameters', {}).get('distance')
        
        if not input_layer:
            raise ValueError("No input layer specified for buffer operation")
        
        if not distance:
            raise ValueError("No distance specified for buffer operation")
            
        # Execute the buffer operation
        success, message, result = self.event_dispatcher.execute_gis_operation(
            'buffer',
            input_layer=input_layer,
            distance=distance
        )
        
        if not success:
            raise RuntimeError(message)
            
        return result
        
    def _handle_clip_command(self, command):
        """Handle clip command execution."""
        # Extract parameters from the command
        input_layer = command.get('input_layer')
        overlay_layer = command.get('secondary_layer')
        
        if not input_layer:
            raise ValueError("No input layer specified for clip operation")
        
        if not overlay_layer:
            raise ValueError("No overlay layer specified for clip operation")
            
        # Execute the clip operation
        success, message, result = self.event_dispatcher.execute_gis_operation(
            'clip',
            input_layer=input_layer,
            overlay_layer=overlay_layer
        )
        
        if not success:
            raise RuntimeError(message)
            
        return result
        
    def _handle_select_command(self, command):
        """Handle select command execution."""
        # This would extract selection criteria and execute selection
        pass
        
    def _handle_intersect_command(self, command):
        """Handle intersection command execution."""
        # This would extract intersection parameters and execute
        pass
    
    def process_nlp_command(self, nlp_result):
        """
        Process the result from NLP engine and execute GIS operations.
        
        Args:
            nlp_result: Parsed command from NLP engine
            
        Returns:
            Tuple of (success, message)
        """
        # Dispatch the command through the event dispatcher
        return self.event_dispatcher.dispatch_command(nlp_result)
    
    def submit_nlp_task(self, nlp_engine, command_text):
        """
        Submit an NLP processing task to run asynchronously.
        
        Args:
            nlp_engine: The NLP engine to use
            command_text: The command text to process
            
        Returns:
            task_id: ID for tracking the task
        """
        # Get current GIS context
        context = self.event_dispatcher.get_current_context()
        
        # Create a function that will run in the background
        def process_nlp():
            try:
                # Attempt to get from cache first
                cached_result = self.memory_manager.get_cached_data(f"cmd_{command_text}")
                if cached_result:
                    return cached_result
                
                # Process with current context
                result = nlp_engine.process_command(
                    command_text,
                    active_layers=[layer['name'] for layer in context['active_layers']],
                    current_crs=context['crs']
                )
                
                # Cache the result
                self.memory_manager.cache_data(f"cmd_{command_text}", result)
                
                return result
            except Exception as e:
                # Re-raise to be caught by the async manager
                raise RuntimeError(f"NLP processing error: {str(e)}")
        
        # Submit the task for background processing
        return self.async_manager.submit_task(process_nlp)
    
    def cleanup(self):
        """Clean up resources when the plugin is unloaded."""
        # Clean up components
        self.async_manager.cleanup()
        self.memory_manager.cleanup()
        self.event_dispatcher.cleanup()