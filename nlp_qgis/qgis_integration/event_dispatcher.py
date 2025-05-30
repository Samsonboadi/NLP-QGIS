# qgis_integration/event_dispatcher.py
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from qgis.PyQt.QtCore import QObject, pyqtSignal, pyqtSlot, QDateTime, Qt
from qgis.core import QgsProject, QgsMapLayer, QgsWkbTypes, QgsProcessingException
import logging
import traceback

# Import QGIS processing
try:
    from qgis.core import QgsProcessing
    from qgis import processing
    PROCESSING_AVAILABLE = True
except ImportError:
    PROCESSING_AVAILABLE = False
    logging.warning("QGIS processing not available")

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
        self.logger = logging.getLogger('NLPGISPlugin.EventDispatcher')
        
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
        self.logger.info(f"Registered handler for command type: {command_type}")
        
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
        
        # Emit signal for command received
        self.command_interpreted.emit(command)
        
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
                
                # Emit success signal
                command_id = f"{operation}_{QDateTime.currentDateTime().toString()}"
                self.command_executed.emit(command_id, True, f"Successfully executed {operation} operation.")
                
                return True, f"Successfully executed {operation} operation."
                
            except Exception as e:
                error_msg = f"Error executing {operation}: {str(e)}"
                self.logger.error(error_msg)
                self.logger.error(traceback.format_exc())
                
                # Record failure
                self.operation_history.append({
                    'type': 'nlp_command',
                    'operation': operation,
                    'command': command,
                    'success': False,
                    'error': str(e),
                    'timestamp': QDateTime.currentDateTime().toString(Qt.ISODate)
                })
                
                # Emit failure signal
                command_id = f"{operation}_{QDateTime.currentDateTime().toString()}"
                self.command_executed.emit(command_id, False, error_msg)
                
                return False, error_msg
        else:
            error_msg = f"No handler registered for operation: {operation}"
            self.logger.warning(error_msg)
            return False, error_msg
            
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
            try:
                layers.append({
                    'id': layer_id,
                    'name': layer.name(),
                    'type': self._get_layer_type(layer),
                    'visible': self.iface.layerTreeView().isLayerVisible(layer) if self.iface.layerTreeView() else True
                })
            except Exception as e:
                self.logger.warning(f"Error getting layer info for {layer_id}: {str(e)}")
        
        # Get current canvas extent
        try:
            canvas = self.iface.mapCanvas()
            extent = canvas.extent()
            
            extent_dict = {
                'xmin': extent.xMinimum(),
                'ymin': extent.yMinimum(),
                'xmax': extent.xMaximum(),
                'ymax': extent.yMaximum()
            }
            scale = canvas.scale()
        except Exception as e:
            self.logger.warning(f"Error getting canvas info: {str(e)}")
            extent_dict = {'xmin': 0, 'ymin': 0, 'xmax': 1, 'ymax': 1}
            scale = 1
        
        # Gather context information
        context = {
            'active_layers': layers,
            'selected_layer': self.iface.activeLayer().name() if self.iface.activeLayer() else None,
            'crs': project.crs().authid() if project.crs().isValid() else 'EPSG:4326',
            'extent': extent_dict,
            'scale': scale
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
        try:
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
        except Exception as e:
            self.logger.warning(f"Error determining layer type: {str(e)}")
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
        if not PROCESSING_AVAILABLE:
            return False, "QGIS processing framework not available", None
            
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
            self.logger.error(f"Error in {operation}: {str(e)}")
            self.logger.error(traceback.format_exc())
            return False, f"Error in {operation}: {str(e)}", None
            
    def _execute_buffer_operation(self, input_layer, distance, **kwargs):
        """Execute buffer operation using QGIS processing."""
        try:
            # Get the actual layer object
            layer = self._get_layer_by_name(input_layer)
            if not layer:
                return False, f"Layer '{input_layer}' not found", None
                
            # Prepare parameters
            params = {
                'INPUT': layer,
                'DISTANCE': distance,
                'SEGMENTS': kwargs.get('segments', 5),
                'END_CAP_STYLE': kwargs.get('end_cap_style', 0),
                'JOIN_STYLE': kwargs.get('join_style', 0),
                'MITER_LIMIT': kwargs.get('miter_limit', 2),
                'DISSOLVE': kwargs.get('dissolve', False),
                'OUTPUT': 'TEMPORARY_OUTPUT'
            }
            
            # Execute the processing algorithm
            result = processing.run("native:buffer", params)
            
            # Add result layer to map
            if 'OUTPUT' in result:
                output_layer = result['OUTPUT']
                output_layer.setName(f"{input_layer}_buffer_{distance}m")
                QgsProject.instance().addMapLayer(output_layer)
                
                return True, f"Buffer created successfully for {input_layer}", output_layer
            else:
                return False, "Buffer operation failed - no output generated", None
                
        except QgsProcessingException as e:
            return False, f"Processing error: {str(e)}", None
        except Exception as e:
            return False, f"Unexpected error in buffer operation: {str(e)}", None
        
    def _execute_clip_operation(self, input_layer, overlay_layer, **kwargs):
        """Execute clip operation using QGIS processing."""
        try:
            # Get the actual layer objects
            input_lyr = self._get_layer_by_name(input_layer)
            overlay_lyr = self._get_layer_by_name(overlay_layer)
            
            if not input_lyr:
                return False, f"Input layer '{input_layer}' not found", None
            if not overlay_lyr:
                return False, f"Overlay layer '{overlay_layer}' not found", None
                
            # Prepare parameters
            params = {
                'INPUT': input_lyr,
                'OVERLAY': overlay_lyr,
                'OUTPUT': 'TEMPORARY_OUTPUT'
            }
            
            # Execute the processing algorithm
            result = processing.run("native:clip", params)
            
            # Add result layer to map
            if 'OUTPUT' in result:
                output_layer = result['OUTPUT']
                output_layer.setName(f"{input_layer}_clipped_by_{overlay_layer}")
                QgsProject.instance().addMapLayer(output_layer)
                
                return True, f"Clip operation completed successfully", output_layer
            else:
                return False, "Clip operation failed - no output generated", None
                
        except QgsProcessingException as e:
            return False, f"Processing error: {str(e)}", None
        except Exception as e:
            return False, f"Unexpected error in clip operation: {str(e)}", None
        
    def _execute_select_operation(self, input_layer, expression, **kwargs):
        """Execute selection operation."""
        try:
            # Get the actual layer object
            layer = self._get_layer_by_name(input_layer)
            if not layer:
                return False, f"Layer '{input_layer}' not found", None
                
            # Perform selection
            layer.selectByExpression(expression)
            selected_count = layer.selectedFeatureCount()
            
            return True, f"Selected {selected_count} features from {input_layer}", selected_count
            
        except Exception as e:
            return False, f"Selection error: {str(e)}", None
        
    def _execute_intersection_operation(self, input_layer, overlay_layer, **kwargs):
        """Execute intersection operation using QGIS processing."""
        try:
            # Get the actual layer objects
            input_lyr = self._get_layer_by_name(input_layer)
            overlay_lyr = self._get_layer_by_name(overlay_layer)
            
            if not input_lyr:
                return False, f"Input layer '{input_layer}' not found", None
            if not overlay_lyr:
                return False, f"Overlay layer '{overlay_layer}' not found", None
                
            # Prepare parameters
            params = {
                'INPUT': input_lyr,
                'OVERLAY': overlay_lyr,
                'INPUT_FIELDS': kwargs.get('input_fields', []),
                'OVERLAY_FIELDS': kwargs.get('overlay_fields', []),
                'OUTPUT': 'TEMPORARY_OUTPUT'
            }
            
            # Execute the processing algorithm
            result = processing.run("native:intersection", params)
            
            # Add result layer to map
            if 'OUTPUT' in result:
                output_layer = result['OUTPUT']
                output_layer.setName(f"{input_layer}_intersect_{overlay_layer}")
                QgsProject.instance().addMapLayer(output_layer)
                
                return True, f"Intersection operation completed successfully", output_layer
            else:
                return False, "Intersection operation failed - no output generated", None
                
        except QgsProcessingException as e:
            return False, f"Processing error: {str(e)}", None
        except Exception as e:
            return False, f"Unexpected error in intersection operation: {str(e)}", None
    
    def _get_layer_by_name(self, layer_name: str):
        """
        Get a layer by name from the current project.
        
        Args:
            layer_name: Name of the layer to find
            
        Returns:
            QgsMapLayer or None if not found
        """
        project = QgsProject.instance()
        
        # Try exact match first
        for layer in project.mapLayers().values():
            if layer.name() == layer_name:
                return layer
                
        # Try case-insensitive match
        for layer in project.mapLayers().values():
            if layer.name().lower() == layer_name.lower():
                return layer
                
        # Try partial match
        for layer in project.mapLayers().values():
            if layer_name.lower() in layer.name().lower():
                return layer
                
        return None
        
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
        except Exception as e:
            # Connections might already be removed
            self.logger.warning(f"Error disconnecting signals: {str(e)}")
        
        # Clear handler registrations
        self.command_handlers.clear()
        self.operation_history.clear()