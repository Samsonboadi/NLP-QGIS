# plugin_main.py

from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QDockWidget, QVBoxLayout, QWidget, QTextEdit, QPushButton, QLineEdit, QProgressBar, QLabel, QMessageBox
from qgis.core import QgsProject, Qgis

import os.path
import asyncio
import traceback
import time
import json

# Import our components
from .nlp_engine import NLPEngine
from .qgis_integration import QGISIntegration
from .error_system import ErrorSystem
from .query_engine import QueryEngine
from .testing import TestingFramework

class NLPGISPlugin:
    """Main Plugin Class that integrates all components."""

    def __init__(self, iface):
        """Initialize the plugin.
        
        Args:
            iface: A QGIS interface instance.
        """
        # Save reference to the QGIS interface
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        
        # Initialize asynchronous event loop for non-blocking operations
        self.loop = asyncio.get_event_loop()
        
        # Setup UI elements
        self.dock_widget = None
        self.command_input = None
        self.result_output = None
        self.execute_button = None
        self.progress_bar = None
        self.status_label = None
        
        # Plugin components - will initialize lazily
        self.nlp_engine = None
        self.qgis_integration = None
        self.error_system = None
        self.query_engine = None
        self.testing_framework = None
        
        # Command history
        self.command_history = []
        self.max_history = 100
        
        # Component initialization status
        self.initialization_status = {
            'nlp_engine': False,
            'qgis_integration': False,
            'error_system': False,
            'query_engine': False,
            'testing_framework': False
        }
        
    def _init_components(self):
        """Initialize all plugin components."""
        try:
            # Initialize in order of dependencies
            self._init_error_system()
            self._init_nlp_engine()
            self._init_qgis_integration()
            self._init_query_engine()
            self._init_testing_framework()
            
            # Set status message
            if self.status_label:
                self.status_label.setText("All components initialized successfully")
                
            return True
            
        except Exception as e:
            # Log the error
            if self.error_system:
                self.error_system.log_error(
                    'initialization_error',
                    f"Error initializing components: {str(e)}",
                    traceback.format_exc()
                )
            
            # Set status message
            if self.status_label:
                self.status_label.setText(f"Error during initialization: {str(e)}")
                
            # Show error message
            QMessageBox.critical(
                self.iface.mainWindow(),
                "Initialization Error",
                f"Failed to initialize the NLP GIS Plugin: {str(e)}\n\nPlease check the error logs for details."
            )
            
            return False
            
    def _init_nlp_engine(self):
        """Initialize the NLP engine component."""
        if not self.nlp_engine:
            self.nlp_engine = NLPEngine()
            self.initialization_status['nlp_engine'] = True
            
    def _init_qgis_integration(self):
        """Initialize the QGIS integration component."""
        if not self.qgis_integration:
            self.qgis_integration = QGISIntegration(self.iface)
            self.initialization_status['qgis_integration'] = True
            
    def _init_error_system(self):
        """Initialize the error system component."""
        if not self.error_system:
            self.error_system = ErrorSystem(self.iface)
            self.initialization_status['error_system'] = True
            
    def _init_query_engine(self):
        """Initialize the query engine component."""
        if not self.query_engine:
            # Need NLP engine first
            if not self.nlp_engine:
                self._init_nlp_engine()
                
            self.query_engine = QueryEngine(self.nlp_engine, QgsProject.instance())
            self.initialization_status['query_engine'] = True
            
    def _init_testing_framework(self):
        """Initialize the testing framework component."""
        if not self.testing_framework:
            # Need other components first
            if not self.nlp_engine:
                self._init_nlp_engine()
            if not self.query_engine:
                self._init_query_engine()
            if not self.error_system:
                self._init_error_system()
                
            self.testing_framework = TestingFramework(
                self.nlp_engine, 
                self.query_engine, 
                self.error_system
            )
            self.initialization_status['testing_framework'] = True
    
    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""
        # Create action
        icon_path = os.path.join(self.plugin_dir, 'icon.png')
        self.action = QAction(
            QIcon(icon_path),
            "NLP GIS Assistant",
            self.iface.mainWindow()
        )
        self.action.triggered.connect(self.run)
        
        # Add toolbar button and menu item
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu("NLP GIS Assistant", self.action)
        
        # Create the dock widget UI
        self._create_dock_widget()
    
    def _create_dock_widget(self):
        """Create the dock widget and its contents."""
        # Create the dock widget
        self.dock_widget = QDockWidget("NLP GIS Assistant", self.iface.mainWindow())
        self.dock_widget.setObjectName("NLPGISAssistant")
        
        # Create widget for dock
        dock_contents = QWidget()
        layout = QVBoxLayout(dock_contents)
        
        # Add status label
        self.status_label = QLabel("Initializing...")
        layout.addWidget(self.status_label)
        
        # Add command input
        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText("Enter your GIS command in natural language...")
        self.command_input.returnPressed.connect(self.process_command)
        layout.addWidget(self.command_input)
        
        # Add execute button
        self.execute_button = QPushButton("Execute")
        self.execute_button.clicked.connect(self.process_command)
        layout.addWidget(self.execute_button)
        
        # Add progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Add result output area
        self.result_output = QTextEdit()
        self.result_output.setReadOnly(True)
        layout.addWidget(self.result_output)
        
        # Set the widget as the dockable window
        self.dock_widget.setWidget(dock_contents)
        
        # Add the dockwidget to the QGIS UI
        self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dock_widget)
        self.dock_widget.hide()  # Initially hidden
    
    async def _init_components_async(self):
        """Initialize components asynchronously."""
        # Update progress in the UI
        def update_progress(value, message):
            self.progress_bar.setValue(value)
            self.status_label.setText(message)
            
        # Show progress
        self.progress_bar.setVisible(True)
        update_progress(10, "Initializing error system...")
        
        # Initialize each component with progress updates
        try:
            self._init_error_system()
            update_progress(30, "Initializing NLP engine...")
            
            self._init_nlp_engine()
            update_progress(50, "Initializing QGIS integration...")
            
            self._init_qgis_integration()
            update_progress(70, "Initializing query engine...")
            
            self._init_query_engine()
            update_progress(90, "Initializing testing framework...")
            
            self._init_testing_framework()
            update_progress(100, "Initialization complete")
            
            # Create an initial state snapshot
            if self.testing_framework:
                state_data = self._get_plugin_state()
                self.testing_framework.save_state(state_data, "initial")
                
            # Hide progress after a delay
            await asyncio.sleep(1)
            self.progress_bar.setVisible(False)
            
        except Exception as e:
            # Handle initialization error
            update_progress(0, f"Initialization error: {str(e)}")
            self.result_output.setText(f"Error initializing plugin: {str(e)}\n\n{traceback.format_exc()}")
            self.progress_bar.setVisible(False)
            
            # Log the error if error system is available
            if self.error_system:
                self.error_system.log_error(
                    'async_initialization_error',
                    f"Error in async initialization: {str(e)}",
                    traceback.format_exc()
                )
    
    def _get_plugin_state(self):
        """
        Get the current state of the plugin for saving.
        
        Returns:
            Dictionary with plugin state
        """
        state = {
            'timestamp': time.time(),
            'initialization_status': self.initialization_status.copy(),
            'command_history': self.command_history.copy(),
            'project_name': QgsProject.instance().fileName(),
            'active_layers': []
        }
        
        # Add active layers
        project = QgsProject.instance()
        for layer_id, layer in project.mapLayers().items():
            state['active_layers'].append({
                'id': layer_id,
                'name': layer.name(),
                'type': layer.type(),
                'visible': self.iface.layerTreeView().isLayerVisible(layer)
            })
            
        return state
    
    async def _process_command_async(self, command_text):
        """Process the command asynchronously.
        
        Args:
            command_text: The command text from the user.
        """
        # Make sure components are initialized
        if not all(self.initialization_status.values()):
            await self._init_components_async()
            
        # Show progress
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(10)
        self.status_label.setText("Processing command...")
        
        try:
            # Add to history
            self.command_history.append({
                'timestamp': time.time(),
                'command': command_text
            })
            
            # Trim history if needed
            if len(self.command_history) > self.max_history:
                self.command_history = self.command_history[-self.max_history:]
                
            # Get current context
            context = None
            if self.qgis_integration and self.qgis_integration.event_dispatcher:
                context = self.qgis_integration.event_dispatcher.get_current_context()
                
            # Process through query engine
            self.progress_bar.setValue(30)
            self.status_label.setText("Interpreting command...")
            
            processed_query = self.query_engine.process_query(command_text, context)
            
            # Validate the query
            self.progress_bar.setValue(50)
            self.status_label.setText("Validating command...")
            
            is_valid, issues, suggestions = self.error_system.validate_nlp_command(processed_query)
            
            # Create the result message
            result_message = f"Command: {command_text}\n\n"
            
            if is_valid:
                # Execute the command
                self.progress_bar.setValue(70)
                self.status_label.setText("Executing command...")
                
                # Log the operation to transaction log
                tx_id = self.error_system.log_operation(
                    processed_query.get('operation', 'unknown'),
                    processed_query.get('parameters', {}),
                    None,  # Result will be added later
                    True,  # Save state
                    self._get_plugin_state()
                )
                
                # Process through QGIS integration
                success, message = self.qgis_integration.process_nlp_command(processed_query)
                
                self.progress_bar.setValue(90)
                
                if success:
                    result_message += f"Successfully executed: {processed_query.get('operation')}\n\n"
                    result_message += f"Details:\n"
                    result_message += f"- Operation: {processed_query.get('operation')}\n"
                    
                    if processed_query.get('input_layer'):
                        result_message += f"- Input Layer: {processed_query.get('input_layer')}\n"
                        
                    if processed_query.get('secondary_layer'):
                        result_message += f"- Overlay Layer: {processed_query.get('secondary_layer')}\n"
                        
                    if processed_query.get('parameters'):
                        result_message += f"- Parameters:\n"
                        for key, value in processed_query.get('parameters', {}).items():
                            result_message += f"  - {key}: {value}\n"
                            
                    result_message += f"\nMessage: {message}"
                    
                else:
                    result_message += f"Error executing command: {message}\n\n"
                    
                    # Add suggestions if there was an error
                    if suggestions:
                        result_message += "Suggestions:\n"
                        for suggestion in suggestions:
                            result_message += f"- {suggestion}\n"
                            
            else:
                # Command has validation issues
                result_message += "Command could not be executed due to validation issues:\n\n"
                
                for issue in issues:
                    severity = issue.get('severity', 'error')
                    message = issue.get('message', 'Unknown issue')
                    result_message += f"- {severity.upper()}: {message}\n"
                    
                # Add suggestions
                if suggestions:
                    result_message += "\nSuggestions:\n"
                    for suggestion in suggestions:
                        result_message += f"- {suggestion}\n"
                        
            # Complete
            self.progress_bar.setValue(100)
            self.status_label.setText("Command processing complete")
            
            # Hide progress after a delay
            await asyncio.sleep(1)
            self.progress_bar.setVisible(False)
            
            return result_message
            
        except Exception as e:
            # Handle error
            self.progress_bar.setVisible(False)
            error_message = f"Error processing command: {str(e)}\n\n{traceback.format_exc()}"
            
            # Log the error
            if self.error_system:
                self.error_system.log_error(
                    'command_processing_error',
                    f"Error processing command '{command_text}': {str(e)}",
                    traceback.format_exc()
                )
                
            return error_message
    
    def process_command(self):
        """Process the command entered by the user."""
        command_text = self.command_input.text()
        if not command_text:
            self.result_output.setText("Please enter a command.")
            return
        
        # Clear input
        self.command_input.clear()
        
        # Show processing message
        self.result_output.setText("Processing command...")
        
        # Process asynchronously using the event loop to avoid blocking UI
        future = asyncio.ensure_future(self._process_command_async(command_text), loop=self.loop)
        future.add_done_callback(self._command_processed)
    
    def _command_processed(self, future):
        """Callback for when command processing is complete."""
        try:
            result = future.result()
            self.result_output.setText(result)
        except Exception as e:
            self.result_output.setText(f"Error processing command: {str(e)}")
            
            # Log the error
            if self.error_system:
                self.error_system.log_error(
                    'callback_error',
                    f"Error in command processing callback: {str(e)}",
                    traceback.format_exc()
                )
    
    def run(self):
        """Run method that performs all the real work."""
        # Show/hide the dock widget
        if self.dock_widget.isVisible():
            self.dock_widget.hide()
        else:
            self.dock_widget.show()
            
            # Initialize components if needed
            if not all(self.initialization_status.values()):
                # Initialize asynchronously to avoid blocking the UI
                future = asyncio.ensure_future(self._init_components_async(), loop=self.loop)
                
    def save_current_state(self):
        """Save the current plugin state."""
        if self.testing_framework:
            state_data = self._get_plugin_state()
            state_id = self.testing_framework.save_state(state_data)
            self.status_label.setText(f"State saved: {state_id}")
            return state_id
        return None
        
    def load_state(self, state_id=None):
        """Load a saved state."""
        if self.testing_framework:
            state_data = self.testing_framework.load_state(state_id)
            if state_data:
                self.status_label.setText(f"State loaded: {state_id}")
                # Apply state data here (would depend on what is saved)
                return True
            else:
                self.status_label.setText("Failed to load state")
        return False
        
    def run_tests(self):
        """Run the plugin test suite."""
        if not self.testing_framework:
            self._init_testing_framework()
            
        if self.testing_framework:
            # Get current context
            context = None
            if self.qgis_integration and self.qgis_integration.event_dispatcher:
                context = self.qgis_integration.event_dispatcher.get_current_context()
                
            # Run tests
            results = self.testing_framework.run_tests(context)
            
            # Show results in output
            report = self.testing_framework.generate_test_report()
            self.result_output.setText(report)
            
            # Update status
            self.status_label.setText(
                f"Tests complete: {results['passed']}/{results['total_tests']} passed"
            )
            
            return results
        else:
            self.result_output.setText("Testing framework not available")
            return None
            
    def create_recovery_point(self, description="Manual recovery point"):
        """Create a named recovery point."""
        if self.testing_framework:
            state_data = self._get_plugin_state()
            state_id = self.testing_framework.create_recovery_point(state_data, description)
            self.status_label.setText(f"Recovery point created: {state_id}")
            return state_id
        return None
        
    def rollback_to_last_state(self):
        """Roll back to the last known good state."""
        if not self.error_system:
            self._init_error_system()
            
        if self.error_system:
            success, state_data = self.error_system.rollback_to_last_state()
            
            if success and state_data:
                self.status_label.setText("Rolled back to previous state")
                # Apply state data here (would depend on what is saved)
                return True
            else:
                self.status_label.setText(f"Rollback failed: {state_data}")
        
        return False
    
    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        # Perform cleanup
        if self.qgis_integration:
            self.qgis_integration.cleanup()
            
        if self.error_system:
            self.error_system.cleanup()
            
        if self.testing_framework:
            self.testing_framework.cleanup()
        
        # Remove UI elements
        self.iface.removePluginMenu("NLP GIS Assistant", self.action)
        self.iface.removeToolBarIcon(self.action)
        
        # Clean up the dock widget
        if self.dock_widget:
            self.dock_widget.setVisible(False)
            self.dock_widget.deleteLater()