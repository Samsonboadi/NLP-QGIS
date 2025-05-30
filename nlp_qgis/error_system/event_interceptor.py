# error_system/event_interceptor.py
from qgis.PyQt.QtCore import QObject, pyqtSignal, pyqtSlot
from qgis.gui import QgisInterface
from qgis.core import QgsApplication
import time
import json
import os
import logging
from typing import Dict, List, Any, Optional, Callable

class EventInterceptor(QObject):
    """
    Custom event interceptor that captures QGIS UI events before processing.
    
    This interceptor sits between the user interface and core QGIS functions,
    allowing monitoring, logging, and potentially preventing actions that
    could lead to errors.
    """
    
    # Signals
    event_captured = pyqtSignal(str, object)  # event_type, event_data
    potential_error_detected = pyqtSignal(str, object)  # error_type, event_data
    
    def __init__(self, iface: QgisInterface):
        """
        Initialize the event interceptor.
        
        Args:
            iface: QGIS interface instance
        """
        super().__init__()
        self.iface = iface
        
        # Initialize logger
        self.logger = logging.getLogger('NLPGISPlugin.EventInterceptor')
        
        # Event tracking
        self.events_log = []  # Track recent events
        self.max_events = 1000  # Maximum events to keep in memory
        
        # Risk detection callbacks
        self.risk_detectors = {}  # Maps event types to risk detection functions
        
        # Setup interceptors for various UI components
        self._setup_interceptors()
        
    def _setup_interceptors(self):
        """Set up interception for various QGIS UI components."""
        # Intercept map canvas events
        canvas = self.iface.mapCanvas()
        canvas.keyPressed.connect(self._on_canvas_key_pressed)
        canvas.keyReleased.connect(self._on_canvas_key_released)
        canvas.renderComplete.connect(self._on_render_complete)
        canvas.renderStarting.connect(self._on_render_starting)
        
        # Intercept layer tree events
        layer_tree = self.iface.layerTreeView()
        layer_tree.currentLayerChanged.connect(self._on_current_layer_changed)
        
        # Intercept project events
        project = QgsProject.instance()
        project.layersWillBeRemoved.connect(self._on_layers_will_be_removed)
        project.layersAdded.connect(self._on_layers_added)
        
        # Intercept processing algorithm execution
        # This is more complex as we need to monkey patch or extend processing framework
        self._setup_processing_interceptors()
        
    def _setup_processing_interceptors(self):
        """Set up interception for processing framework algorithms."""
        # This would be a more complex implementation requiring
        # monkey patching or extending QGIS processing classes
        # For now, we'll use a simplified approach just for demonstration
        
        # Get the processing registry
        registry = QgsApplication.processingRegistry()
        
        # We'd need to intercept the algorithm execution
        # This is just a placeholder for a more complex implementation
        
    def register_risk_detector(self, event_type: str, detector_func: Callable):
        """
        Register a risk detection function for a specific event type.
        
        Args:
            event_type: Type of event to monitor
            detector_func: Function to call to check for risk
                           Should return (is_risky, risk_type, risk_level, description)
        """
        self.risk_detectors[event_type] = detector_func
        
    def _check_for_risks(self, event_type: str, event_data: Dict[str, Any]):
        """
        Check if an event poses any risks.
        
        Args:
            event_type: Type of the event
            event_data: Event data dictionary
            
        Returns:
            Tuple of (is_risky, risk_type, risk_level, description) or None
        """
        if event_type in self.risk_detectors:
            detector = self.risk_detectors[event_type]
            return detector(event_data)
        return None
        
    def _log_event(self, event_type: str, event_data: Dict[str, Any]):
        """
        Log an event to the internal event log.
        
        Args:
            event_type: Type of the event
            event_data: Event data dictionary
        """
        # Create event record
        event = {
            'timestamp': time.time(),
            'type': event_type,
            'data': event_data
        }
        
        # Add to log
        self.events_log.append(event)
        
        # Trim log if needed
        if len(self.events_log) > self.max_events:
            self.events_log = self.events_log[-self.max_events:]
            
        # Emit signal
        self.event_captured.emit(event_type, event_data)
        
        # Check for risks
        risk_result = self._check_for_risks(event_type, event_data)
        if risk_result:
            is_risky, risk_type, risk_level, description = risk_result
            if is_risky:
                self.logger.warning(
                    f"Potential risk detected: {risk_type} "
                    f"(Level: {risk_level}) - {description}"
                )
                self.potential_error_detected.emit(risk_type, {
                    'event_type': event_type,
                    'event_data': event_data,
                    'risk_level': risk_level,
                    'description': description
                })
    
    # Event handlers
    def _on_canvas_key_pressed(self, event):
        """Handle key press event on map canvas."""
        self._log_event('canvas_key_pressed', {
            'key': event.key(),
            'text': event.text(),
            'modifiers': event.modifiers()
        })
        
    def _on_canvas_key_released(self, event):
        """Handle key release event on map canvas."""
        self._log_event('canvas_key_released', {
            'key': event.key(),
            'text': event.text(),
            'modifiers': event.modifiers()
        })
        
    def _on_render_complete(self):
        """Handle render complete event."""
        canvas = self.iface.mapCanvas()
        self._log_event('render_complete', {
            'scale': canvas.scale(),
            'extent': {
                'xmin': canvas.extent().xMinimum(),
                'ymin': canvas.extent().yMinimum(),
                'xmax': canvas.extent().xMaximum(),
                'ymax': canvas.extent().yMaximum()
            },
            'rotation': canvas.rotation()
        })
        
    def _on_render_starting(self):
        """Handle render starting event."""
        canvas = self.iface.mapCanvas()
        self._log_event('render_starting', {
            'scale': canvas.scale(),
            'extent': {
                'xmin': canvas.extent().xMinimum(),
                'ymin': canvas.extent().yMinimum(),
                'xmax': canvas.extent().xMaximum(),
                'ymax': canvas.extent().yMaximum()
            },
            'rotation': canvas.rotation()
        })
        
    def _on_current_layer_changed(self, layer):
        """Handle current layer changed event."""
        if layer:
            self._log_event('current_layer_changed', {
                'layer_id': layer.id(),
                'layer_name': layer.name(),
                'layer_type': layer.type()
            })
        else:
            self._log_event('current_layer_changed', {
                'layer_id': None,
                'layer_name': None,
                'layer_type': None
            })
            
    def _on_layers_will_be_removed(self, layer_ids):
        """Handle layers will be removed event."""
        layer_details = []
        for layer_id in layer_ids:
            layer = QgsProject.instance().mapLayer(layer_id)
            if layer:
                layer_details.append({
                    'layer_id': layer_id,
                    'layer_name': layer.name(),
                    'layer_type': layer.type()
                })
            else:
                layer_details.append({
                    'layer_id': layer_id,
                    'layer_name': 'Unknown',
                    'layer_type': 'Unknown'
                })
                
        self._log_event('layers_will_be_removed', {
            'layer_count': len(layer_ids),
            'layers': layer_details
        })
        
    def _on_layers_added(self, layers):
        """Handle layers added event."""
        layer_details = []
        for layer in layers:
            layer_details.append({
                'layer_id': layer.id(),
                'layer_name': layer.name(),
                'layer_type': layer.type()
            })
                
        self._log_event('layers_added', {
            'layer_count': len(layers),
            'layers': layer_details
        })
    
    def get_recent_events(self, count: int = 10, event_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get recent events from the log.
        
        Args:
            count: Maximum number of events to return
            event_type: Optional filter for event type
            
        Returns:
            List of event dictionaries
        """
        if event_type:
            filtered_events = [e for e in self.events_log if e['type'] == event_type]
            return filtered_events[-count:]
        else:
            return self.events_log[-count:]
            
    def save_events_to_file(self, filename: str):
        """
        Save event log to a file.
        
        Args:
            filename: Path to save the log
        """
        with open(filename, 'w') as f:
            json.dump(self.events_log, f, indent=2)
            
    def cleanup(self):
        """Clean up resources when the plugin is unloaded."""
        # Remove all our signal connections
        try:
            canvas = self.iface.mapCanvas()
            canvas.keyPressed.disconnect(self._on_canvas_key_pressed)
            canvas.keyReleased.disconnect(self._on_canvas_key_released)
            canvas.renderComplete.disconnect(self._on_render_complete)
            canvas.renderStarting.disconnect(self._on_render_starting)
            
            layer_tree = self.iface.layerTreeView()
            layer_tree.currentLayerChanged.disconnect(self._on_current_layer_changed)
            
            project = QgsProject.instance()
            project.layersWillBeRemoved.disconnect(self._on_layers_will_be_removed)
            project.layersAdded.disconnect(self._on_layers_added)
        except:
            # Some connections might already be removed
            pass