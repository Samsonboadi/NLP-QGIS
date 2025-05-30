# qgis_integration/event_dispatcher.py
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from qgis.PyQt.QtCore import QObject, pyqtSignal, pyqtSlot
from qgis.core import QgsProject, QgsMapLayer

class GISEventDispatcher(QObject):
    """
    Event dispatching system that links NLP results to QGIS actions.
    
    This class bridges the gap between NLP interpretation results and
    actual QGIS operations, ensuring that NLP commands are properly
    translated into QGIS framework actions.
    """
    
    # Signals for NLP events
    command_received = pyqtSignal(str)  # Raw command text
    command_interpreted = pyqtSignal(object)  # Interpreted command structure
    command_executed = pyqtSignal(str, bool, str)  # command_id, success, message
    
    def __init__(self, iface):
        """
        Initialize the event dispatcher.
        
        Args:
            iface: QGIS interface instance
        """
        super().__init__()
        self.iface = iface
        
        # Store mapping of command types to handler functions
        self.command_handlers = {}
        
        # Operations history
        self.operation_history = []
        
        # Set up project connections
        self._connect_project_signals()
        
    def _connect_project_signals(self):
        """Connect to relevant QGIS project signals."""
        project = QgsProject.instance()
        
        # Connect to layer-related signals
        project.layersAdded.connect(self._on_layers_added)
        project.layersRemoved.connect(self._on_layers_removed)
        project.layersWillBeRemoved.connect(self._on_layers_will_be_removed)
        
        # Connect to project-related signals
        project.readProject.connect(self._on_project_read)
        project.writeProject.connect(self._on_project_write)
        
    def _on_layers_added(self, layers):
        """Handle layers being added to the project."""
        layer_names = [layer.name() for layer in layers]
        self.operation_history.append({
            'type': 'layers_added',
            'layer_names': layer_names,
            'timestamp': QDateTime.currentDateTime().toString(Qt.ISODate)
        })
        
    def _on_layers_removed(self, layer_ids):
        """Handle layers being removed from the project."""
        self.operation_history.append({
            'type': 'layers_removed',
            'layer_ids': layer_ids,
            'timestamp': QDateTime.currentDateTime().toString(Qt.ISODate)
        })
        
    def _on_layers_will_be_removed(self, layer_ids):
        """Handle notification before layers are removed."""
        # Could be used for pre-removal actions if needed
        pass
        
    def _on_project_read(self):
        """Handle project being loaded."""
        self.operation_history.append({
            'type': 'project_read',
            'timestamp': QDateTime.currentDateTime().toString(Qt.ISODate)
        })
        
    def _on_project_write(self):
        """Handle project being saved."""
        self.operation_history.append({
            'type': 'project_write',
            'timestamp': QDateTime.currentDateTime().toString(Qt.ISODate)
        })
        
    def register_command_handler(self, command_type: str, handler_func: Callable):
        """
        Register a handler function for a specific command type.
        
        Args:
            command_type: Type of command (e.g., 'buffer', 'clip', etc.)
            handler_func: Function to call when this command is dispatched
        """
        self.command_handlers[command_type] = handler_func
        
    def dispatch_command(self, command: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Dispatch an interpreted command to the appropriate handler.
        
        Args:
            command: Interpreted command dictionary with operation and parameters
            
        Returns:
            Tuple of (success, message)
        """
        # Get the operation type
        operation = command.get('operation', '').lower()
        
        # Check if we have a handler for this operation
        if operation in self.command_handlers:
            try:
                # Execute the handler
                result = self.command_handlers[operation](command)
                
                # Record in operation history
                self.operation_history.append({
                    'type': 'nlp_command',
                    'operation': operation,
                    'command': command,
                    'success': True,
                    'timestamp': QDateTime.currentDateTime().toString(Qt.ISODate)
                })
                
                return True, f"Successfully executed {operation} operation."
                
            except Exception as e:
                # Record failure
                self.operation_history.append({
                    'type': 'nlp_command',
                    'operation': operation,
                    'command': command,
                    'success': False,
                    'error': str(e),
                    'timestamp': QDateTime.currentDateTime().toString(Qt.ISODate)
                })
                
                return False, f"Error executing {operation}: {str(e)}"
        else:
            return False, f"No handler registered for operation: {operation}"
            
    def get_current_context(self) -> Dict[str, Any]:
        """
        Get the current QGIS context information for command interpretation.
        
        Returns:
            Dictionary with current context information
        """
        # Get current project
        project = QgsProject.instance()
        
        # Get current layers
        layers = []
        for layer_id, layer in project.mapLayers().items():
            layers.append({
                'id': layer_id,
                'name': layer.name(),
                'type': self._get_layer_type(layer),
                'visible': self.iface.layerTreeView().isLayerVisible(layer)
            })
        
        # Get current canvas extent
        canvas = self.iface.mapCanvas()
        extent = canvas.extent()
        
        # Gather context information
        context = {
            'active_layers': layers,
            'selected_layer': self.iface.activeLayer().name() if self.iface.activeLayer() else None,
            'crs': project.crs().authid(),
            'extent': {
                'xmin': extent.xMinimum(),
                'ymin': extent.yMinimum(),
                'xmax': extent.xMaximum(),
                'ymax': extent.yMaximum()
            },
            'scale': canvas.scale()
        }
        
        return context
    
    def _get_layer_type(self, layer: QgsMapLayer) -> str:
        """
        Get a human-readable layer type.
        
        Args:
            layer: QGIS map layer
            
        Returns:
            Layer type as string
        """
        if layer.type() == QgsMapLayer.VectorLayer:
            geom_type = layer.geometryType()
            if geom_type == QgsWkbTypes.PointGeometry:
                return "point"
            elif geom_type == QgsWkbTypes.LineGeometry:
                return "line"
            elif geom_type == QgsWkbTypes.PolygonGeometry:
                return "polygon"
            else:
                return "vector"
        elif layer.type() == QgsMapLayer.RasterLayer:
            return "raster"
        else:
            return "unknown"
            
    def execute_gis_operation(self, operation: str, **params) -> Tuple[bool, str, Any]:
        """
        Execute a GIS operation with the given parameters.
        
        Args:
            operation: Operation name
            **params: Operation parameters
            
        Returns:
            Tuple of (success, message, result)
        """
        # This method would translate operations to actual QGIS processing calls
        # For now, this is a skeleton that would be expanded with actual implementations
        
        try:
            if operation == 'buffer':
                return self._execute_buffer_operation(**params)
            elif operation == 'clip':
                return self._execute_clip_operation(**params)
            elif operation == 'select':
                return self._execute_select_operation(**params)
            elif operation == 'intersection':
                return self._execute_intersection_operation(**params)
            else:
                return False, f"Operation {operation} not implemented", None
        except Exception as e:
            return False, f"Error in {operation}: {str(e)}", None
            
    def _execute_buffer_operation(self, input_layer, distance, **kwargs):
        """Execute buffer operation using QGIS processing."""
        # This would be implemented with actual QGIS processing calls
        # For example:
        # from qgis.core import processing
        # result = processing.run("native:buffer", {
        #     'INPUT': input_layer,
        #     'DISTANCE': distance,
        #     'SEGMENTS': kwargs.get('segments', 5),
        #     'END_CAP_STYLE': kwargs.get('end_cap_style', 0),
        #     'JOIN_STYLE': kwargs.get('join_style', 0),
        #     'MITER_LIMIT': kwargs.get('miter_limit', 2),
        #     'DISSOLVE': kwargs.get('dissolve', False),
        #     'OUTPUT': 'memory:'
        # })
        # return True, "Buffer created successfully", result['OUTPUT']
        
        # For now, return a placeholder
        return True, "Buffer operation simulated", "buffer_result"
        
    def _execute_clip_operation(self, input_layer, overlay_layer, **kwargs):
        """Execute clip operation using QGIS processing."""
        # This would be implemented with actual QGIS processing calls
        # For now, return a placeholder
        return True, "Clip operation simulated", "clip_result"
        
    def _execute_select_operation(self, input_layer, expression, **kwargs):
        """Execute selection operation using QGIS processing."""
        # This would be implemented with actual QGIS processing calls
        # For now, return a placeholder
        return True, "Select operation simulated", "select_result"
        
    def _execute_intersection_operation(self, input_layer, overlay_layer, **kwargs):
        """Execute intersection operation using QGIS processing."""
        # This would be implemented with actual QGIS processing calls
        # For now, return a placeholder
        return True, "Intersection operation simulated", "intersection_result"
        
    def cleanup(self):
        """Clean up resources when the plugin is unloaded."""
        # Remove connections to QGIS signals
        project = QgsProject.instance()
        
        try:
            project.layersAdded.disconnect(self._on_layers_added)
            project.layersRemoved.disconnect(self._on_layers_removed)
            project.layersWillBeRemoved.disconnect(self._on_layers_will_be_removed)
            project.readProject.disconnect(self._on_project_read)
            project.writeProject.disconnect(self._on_project_write)
        except:
            # Connections might already be removed
            pass
        
        # Clear handler registrations
        self.command_handlers.clear()