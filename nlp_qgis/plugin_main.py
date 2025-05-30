# plugin_main.py

# Apply Python path fix before any other imports
import os
import sys

# Ensure user site-packages don't interfere
os.environ['PYTHONNOUSERSITE'] = '1'
try:
    import site
    site.ENABLE_USER_SITE = False
    user_site = site.getusersitepackages()
    if user_site in sys.path:
        sys.path.remove(user_site)
except:
    pass

# Now proceed with normal imports
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt, QTimer, QThread, pyqtSignal
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import (QAction, QDockWidget, QVBoxLayout, QWidget, QTextEdit, 
                                QPushButton, QLineEdit, QProgressBar, QLabel, QMessageBox, 
                                QHBoxLayout, QComboBox, QCheckBox, QTabWidget, QListWidget,
                                QSplitter, QGroupBox, QSpinBox)
from qgis.core import QgsProject, Qgis, QgsMessageLog

import traceback
import time
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, Optional, List

# Import our components with better error handling
try:
    from .nlp_engine import NLPEngine
    NLP_ENGINE_AVAILABLE = True
except ImportError as e:
    NLP_ENGINE_AVAILABLE = False
    NLP_ENGINE_ERROR = str(e)

try:
    from .qgis_integration import QGISIntegration
    QGIS_INTEGRATION_AVAILABLE = True
except ImportError as e:
    QGIS_INTEGRATION_AVAILABLE = False
    QGIS_INTEGRATION_ERROR = str(e)

try:
    from .error_system import ErrorSystem
    ERROR_SYSTEM_AVAILABLE = True
except ImportError as e:
    ERROR_SYSTEM_AVAILABLE = False
    ERROR_SYSTEM_ERROR = str(e)

try:
    from .query_engine import QueryEngine
    QUERY_ENGINE_AVAILABLE = True
except ImportError as e:
    QUERY_ENGINE_AVAILABLE = False
    QUERY_ENGINE_ERROR = str(e)

try:
    from .testing import TestingFramework
    TESTING_FRAMEWORK_AVAILABLE = True
except ImportError as e:
    TESTING_FRAMEWORK_AVAILABLE = False
    TESTING_FRAMEWORK_ERROR = str(e)

class NLPProcessingThread(QThread):
    """Separate thread for NLP processing to avoid blocking UI."""
    
    processing_finished = pyqtSignal(str, dict)
    processing_failed = pyqtSignal(str, str)
    progress_updated = pyqtSignal(int, str)
    
    def __init__(self, query_engine, command_text, context):
        super().__init__()
        self.query_engine = query_engine
        self.command_text = command_text
        self.context = context
        
    def run(self):
        """Run NLP processing in separate thread."""
        try:
            self.progress_updated.emit(10, "Initializing NLP processing...")
            
            if not self.query_engine:
                raise Exception("Query engine not available")
                
            self.progress_updated.emit(30, "Parsing natural language...")
            processed_query = self.query_engine.process_query(self.command_text, self.context)
            
            self.progress_updated.emit(70, "Validating query...")
            time.sleep(0.5)  # Brief pause for UI feedback
            
            self.progress_updated.emit(100, "Processing complete")
            self.processing_finished.emit(self.command_text, processed_query)
            
        except Exception as e:
            error_msg = f"NLP processing failed: {str(e)}"
            self.processing_failed.emit(self.command_text, error_msg)

class NLPGISPlugin:
    """
    Main Plugin Class with robust error handling and dependency management.
    
    This version includes fixes for Python path conflicts and graceful
    handling of missing dependencies.
    """

    def __init__(self, iface):
        """Initialize the plugin with comprehensive error handling."""
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        
        # UI elements
        self.dock_widget = None
        self.main_tabs = None
        self.command_input = None
        self.result_output = None
        self.execute_button = None
        self.progress_bar = None
        self.status_label = None
        
        # Plugin components
        self.nlp_engine = None
        self.qgis_integration = None
        self.error_system = None
        self.query_engine = None
        self.testing_framework = None
        
        # Threading
        self.thread_pool = ThreadPoolExecutor(max_workers=2)
        self.processing_thread = None
        
        # State tracking
        self.command_history = []
        self.max_history = 100
        self.session_start_time = time.time()
        
        # Component availability status
        self.component_status = {
            'nlp_engine': NLP_ENGINE_AVAILABLE,
            'qgis_integration': QGIS_INTEGRATION_AVAILABLE,
            'error_system': ERROR_SYSTEM_AVAILABLE,
            'query_engine': QUERY_ENGINE_AVAILABLE,
            'testing_framework': TESTING_FRAMEWORK_AVAILABLE
        }
        
        # Performance metrics
        self.performance_metrics = {
            'commands_processed': 0,
            'successful_commands': 0,
            'failed_commands': 0,
            'average_processing_time': 0,
            'total_processing_time': 0
        }
        
        # Setup monitoring timer
        self.monitoring_timer = QTimer()
        self.monitoring_timer.timeout.connect(self._update_performance_display)
        self.monitoring_timer.start(5000)
        
    def _check_dependencies(self) -> Dict[str, Any]:
        """Check which dependencies are available."""
        dependency_status = {}
        
        # Check Python path fix
        dependency_status['python_path_fixed'] = os.environ.get('PYTHONNOUSERSITE') == '1'
        
        # Check heavy NLP libraries
        for lib in ['torch', 'transformers', 'spacy', 'datasets']:
            try:
                __import__(lib)
                dependency_status[lib] = True
            except ImportError:
                dependency_status[lib] = False
        
        # Check component availability
        dependency_status['components'] = self.component_status.copy()
        
        return dependency_status
        
    def _init_components(self):
        """Initialize components with graceful error handling."""
        dependency_status = self._check_dependencies()
        
        try:
            # Initialize available components
            if self.component_status['error_system']:
                self.error_system = ErrorSystem(self.iface)
                
            if self.component_status['nlp_engine']:
                self.nlp_engine = NLPEngine()
                
            if self.component_status['qgis_integration']:
                self.qgis_integration = QGISIntegration(self.iface)
                
            if self.component_status['query_engine'] and self.nlp_engine:
                self.query_engine = QueryEngine(self.nlp_engine, QgsProject.instance())
                
            if self.component_status['testing_framework']:
                self.testing_framework = TestingFramework(
                    self.nlp_engine, self.query_engine, self.error_system
                )
            
            # Log successful initialization
            available_count = sum(self.component_status.values())
            total_count = len(self.component_status)
            
            QgsMessageLog.logMessage(
                f"NLP GIS Plugin: {available_count}/{total_count} components initialized",
                "NLP GIS Plugin",
                Qgis.Info
            )
            
            return True
            
        except Exception as e:
            error_msg = f"Error initializing components: {str(e)}"
            QgsMessageLog.logMessage(error_msg, "NLP GIS Plugin", Qgis.Critical)
            
            if self.status_label:
                self.status_label.setText(f"Initialization error: {str(e)}")
                
            return False
    
    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""
        # Create action
        icon_path = os.path.join(self.plugin_dir, 'icon.png')
        self.action = QAction(
            QIcon(icon_path) if os.path.exists(icon_path) else QIcon(),
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
        """Create the dock widget with dependency status."""
        self.dock_widget = QDockWidget("NLP GIS Assistant", self.iface.mainWindow())
        self.dock_widget.setObjectName("NLPGISAssistant")
        
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        
        # Create tab widget
        self.main_tabs = QTabWidget()
        main_layout.addWidget(self.main_tabs)
        
        # Create tabs
        self._create_main_interface_tab()
        self._create_status_tab()
        
        self.dock_widget.setWidget(main_widget)
        self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dock_widget)
        self.dock_widget.hide()
        
    def _create_main_interface_tab(self):
        """Create the main interface tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Status section
        status_group = QGroupBox("Status")
        status_layout = QVBoxLayout(status_group)
        
        self.status_label = QLabel("Checking dependencies...")
        status_layout.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        status_layout.addWidget(self.progress_bar)
        
        layout.addWidget(status_group)
        
        # Command input section
        input_group = QGroupBox("Natural Language Command")
        input_layout = QVBoxLayout(input_group)
        
        input_row = QHBoxLayout()
        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText("E.g., 'Buffer roads by 500 meters'")
        self.command_input.returnPressed.connect(self.process_command)
        input_row.addWidget(self.command_input)
        
        self.execute_button = QPushButton("Execute")
        self.execute_button.clicked.connect(self.process_command)
        input_row.addWidget(self.execute_button)
        
        input_layout.addLayout(input_row)
        layout.addWidget(input_group)
        
        # Results section
        results_group = QGroupBox("Results")
        results_layout = QVBoxLayout(results_group)
        
        self.result_output = QTextEdit()
        self.result_output.setReadOnly(True)
        self.result_output.setMinimumHeight(200)
        results_layout.addWidget(self.result_output)
        
        layout.addWidget(results_group)
        
        self.main_tabs.addTab(tab, "Command Interface")
        
    def _create_status_tab(self):
        """Create status tab showing dependency information."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Dependency status
        deps_group = QGroupBox("Dependencies Status")
        deps_layout = QVBoxLayout(deps_group)
        
        self.dependency_display = QTextEdit()
        self.dependency_display.setReadOnly(True)
        self.dependency_display.setMaximumHeight(200)
        deps_layout.addWidget(self.dependency_display)
        
        # Refresh button
        refresh_btn = QPushButton("Refresh Status")
        refresh_btn.clicked.connect(self._update_dependency_display)
        deps_layout.addWidget(refresh_btn)
        
        layout.addWidget(deps_group)
        
        # Component status
        components_group = QGroupBox("Component Status")
        components_layout = QVBoxLayout(components_group)
        
        self.components_display = QTextEdit()
        self.components_display.setReadOnly(True)
        components_layout.addWidget(self.components_display)
        
        layout.addWidget(components_group)
        
        self.main_tabs.addTab(tab, "Status & Diagnostics")
        
        # Initial update
        self._update_dependency_display()
        
    def _update_dependency_display(self):
        """Update the dependency status display."""
        try:
            status = self._check_dependencies()
            
            text = "Python Environment Status:\n"
            text += "=" * 30 + "\n\n"
            
            # Python path fix status
            path_fix = "✅" if status.get('python_path_fixed', False) else "❌"
            text += f"{path_fix} Python Path Fix Applied\n\n"
            
            # Library status
            text += "NLP Libraries:\n"
            for lib in ['torch', 'transformers', 'spacy', 'datasets']:
                lib_status = "✅" if status.get(lib, False) else "❌"
                text += f"{lib_status} {lib}\n"
            
            text += "\nComponent Status:\n"
            for component, available in status.get('components', {}).items():
                comp_status = "✅" if available else "❌"
                text += f"{comp_status} {component}\n"
            
            # Recommendations
            text += "\n" + "=" * 30 + "\n"
            text += "Recommendations:\n"
            
            if not status.get('python_path_fixed', False):
                text += "• Python path fix not applied - restart QGIS\n"
                
            missing_libs = [lib for lib in ['torch', 'transformers', 'spacy'] 
                          if not status.get(lib, False)]
            if missing_libs:
                text += f"• Missing libraries: {', '.join(missing_libs)}\n"
                text += "• Install using: pip install --no-user [library_name]\n"
                
            available_components = sum(status.get('components', {}).values())
            total_components = len(status.get('components', {}))
            
            if available_components == total_components:
                text += "• All components available - full functionality enabled\n"
            elif available_components > 0:
                text += "• Partial functionality available - some features may be limited\n"
            else:
                text += "• No components available - plugin may not function properly\n"
            
            self.dependency_display.setText(text)
            
            # Update component status
            comp_text = "Component Details:\n"
            comp_text += "=" * 20 + "\n\n"
            
            if not NLP_ENGINE_AVAILABLE:
                comp_text += f"❌ NLP Engine: {NLP_ENGINE_ERROR}\n\n"
            if not QGIS_INTEGRATION_AVAILABLE:
                comp_text += f"❌ QGIS Integration: {QGIS_INTEGRATION_ERROR}\n\n"
            if not ERROR_SYSTEM_AVAILABLE:
                comp_text += f"❌ Error System: {ERROR_SYSTEM_ERROR}\n\n"
            if not QUERY_ENGINE_AVAILABLE:
                comp_text += f"❌ Query Engine: {QUERY_ENGINE_ERROR}\n\n"
            if not TESTING_FRAMEWORK_AVAILABLE:
                comp_text += f"❌ Testing Framework: {TESTING_FRAMEWORK_ERROR}\n\n"
                
            if all([NLP_ENGINE_AVAILABLE, QGIS_INTEGRATION_AVAILABLE, 
                   ERROR_SYSTEM_AVAILABLE, QUERY_ENGINE_AVAILABLE, 
                   TESTING_FRAMEWORK_AVAILABLE]):
                comp_text += "✅ All components loaded successfully!"
                
            self.components_display.setText(comp_text)
            
        except Exception as e:
            self.dependency_display.setText(f"Error checking dependencies: {str(e)}")
    
    def process_command(self):
        """Process command with dependency checking."""
        command_text = self.command_input.text().strip()
        if not command_text:
            self.result_output.setText("Please enter a command.")
            return
        
        # Check if we have required components
        if not self.query_engine:
            if not self._init_components():
                self.result_output.setText(
                    "❌ Cannot process command - required components not available.\n\n"
                    "Please check the 'Status & Diagnostics' tab for more information."
                )
                return
        
        # Clear input and show processing
        self.command_input.clear()
        self.result_output.setText("Processing command...")
        self.status_label.setText("Processing command...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # Record start time
        start_time = time.time()
        
        # Add to history
        self.command_history.append({
            'timestamp': time.time(),
            'command': command_text,
            'start_time': start_time
        })
        
        # Get context
        context = None
        if (self.qgis_integration and 
            hasattr(self.qgis_integration, 'event_dispatcher') and
            self.qgis_integration.event_dispatcher):
            try:
                context = self.qgis_integration.event_dispatcher.get_current_context()
            except Exception as e:
                QgsMessageLog.logMessage(f"Error getting context: {str(e)}", "NLP GIS Plugin", Qgis.Warning)
        
        # Process using thread
        self.processing_thread = NLPProcessingThread(self.query_engine, command_text, context)
        self.processing_thread.processing_finished.connect(
            lambda cmd, result: self._on_processing_finished(cmd, result, start_time)
        )
        self.processing_thread.processing_failed.connect(
            lambda cmd, error: self._on_processing_failed(cmd, error, start_time)
        )
        self.processing_thread.progress_updated.connect(self._on_progress_updated)
        
        self.processing_thread.start()
    
    def _on_progress_updated(self, percentage: int, message: str):
        """Handle progress updates."""
        self.progress_bar.setValue(percentage)
        self.status_label.setText(message)
    
    def _on_processing_finished(self, command_text: str, processed_query: Dict[str, Any], start_time: float):
        """Handle successful processing."""
        try:
            processing_time = time.time() - start_time
            self.performance_metrics['total_processing_time'] += processing_time
            self.progress_bar.setVisible(False)
            
            # Create result message
            result_message = f"Command: {command_text}\n"
            result_message += f"Processing Time: {processing_time:.2f}s\n\n"
            
            # Check if we have QGIS integration for execution
            if self.qgis_integration:
                # Validate and execute
                if self.error_system:
                    is_valid, issues, suggestions = self.error_system.validate_nlp_command(processed_query)
                else:
                    is_valid = processed_query.get('operation') != 'unknown'
                    issues = []
                    suggestions = []
                
                if is_valid:
                    self.status_label.setText("Executing GIS operation...")
                    success, message = self.qgis_integration.process_nlp_command(processed_query)
                    
                    if success:
                        result_message += f"✅ Successfully executed: {processed_query.get('operation')}\n\n"
                        result_message += f"Operation Details:\n"
                        result_message += f"• Operation: {processed_query.get('operation')}\n"
                        
                        if processed_query.get('input_layer'):
                            result_message += f"• Input Layer: {processed_query.get('input_layer')}\n"
                        if processed_query.get('secondary_layer'):
                            result_message += f"• Overlay Layer: {processed_query.get('secondary_layer')}\n"
                        if processed_query.get('parameters'):
                            result_message += f"• Parameters:\n"
                            for key, value in processed_query.get('parameters', {}).items():
                                if not key.startswith('auto_completed'):
                                    result_message += f"  ◦ {key}: {value}\n"
                        
                        result_message += f"\nExecution Message: {message}"
                        self.performance_metrics['successful_commands'] += 1
                    else:
                        result_message += f"❌ Error executing command: {message}\n"
                        if suggestions:
                            result_message += "\nSuggestions:\n"
                            for suggestion in suggestions:
                                result_message += f"• {suggestion}\n"
                        self.performance_metrics['failed_commands'] += 1
                else:
                    result_message += "⚠️ Command validation failed:\n\n"
                    for issue in issues:
                        severity = issue.get('severity', 'error')
                        message = issue.get('message', 'Unknown issue')
                        icon = "🔴" if severity == 'error' else "🟡"
                        result_message += f"{icon} {severity.upper()}: {message}\n"
                    
                    if suggestions:
                        result_message += "\nSuggestions:\n"
                        for suggestion in suggestions:
                            result_message += f"• {suggestion}\n"
            else:
                # No QGIS integration, just show parsed result
                result_message += f"✅ Command parsed successfully:\n"
                result_message += f"• Operation: {processed_query.get('operation')}\n"
                result_message += f"• Confidence: {processed_query.get('confidence', 0):.2f}\n"
                result_message += f"• Processing Method: {processed_query.get('processing_method', 'unknown')}\n"
                result_message += "\n⚠️ QGIS integration not available - command parsed but not executed"
            
            self.status_label.setText("Command processing complete")
            
        except Exception as e:
            result_message = f"Error in result processing: {str(e)}\n\n{traceback.format_exc()}"
            
        finally:
            self.result_output.setText(result_message)
            self.performance_metrics['commands_processed'] += 1
    
    def _on_processing_failed(self, command_text: str, error_message: str, start_time: float):
        """Handle failed processing."""
        processing_time = time.time() - start_time
        self.performance_metrics['total_processing_time'] += processing_time
        self.progress_bar.setVisible(False)
        
        result_message = f"Command: {command_text}\n"
        result_message += f"Processing Time: {processing_time:.2f}s\n\n"
        result_message += f"❌ {error_message}"
        
        self.result_output.setText(result_message)
        self.status_label.setText("Command processing failed")
        
        self.performance_metrics['commands_processed'] += 1
        self.performance_metrics['failed_commands'] += 1
    
    def _update_performance_display(self):
        """Update performance metrics periodically."""
        # This could update any performance displays
        pass
    
    def run(self):
        """Show/hide the dock widget."""
        if self.dock_widget.isVisible():
            self.dock_widget.hide()
        else:
            self.dock_widget.show()
            
            # Initialize components if not done yet
            if not any(self.component_status.values()):
                self._init_components()
                
            # Update status displays
            self._update_dependency_display()
    
    def unload(self):
        """Clean up when plugin is unloaded."""
        # Stop monitoring timer
        if hasattr(self, 'monitoring_timer'):
            self.monitoring_timer.stop()
            
        # Stop any running threads
        if self.processing_thread and self.processing_thread.isRunning():
            self.processing_thread.quit()
            self.processing_thread.wait()
            
        # Shutdown thread pool
        self.thread_pool.shutdown(wait=False)
        
        # Clean up components
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
            
        # Log plugin shutdown
        QgsMessageLog.logMessage(
            "NLP GIS Plugin unloaded successfully",
            "NLP GIS Plugin",
            Qgis.Info
        )