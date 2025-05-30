# testing/platform_adapter.py
import platform
import os
import sys
import logging
from typing import Dict, Any, Optional, List

class PlatformAdapter:
    """
    Platform-specific adaptations to ensure consistent behavior across OS.
    
    This class handles the differences between operating systems to ensure
    the plugin behaves consistently across Windows, macOS, and Linux.
    """
    
    def __init__(self):
        """Initialize the platform adapter."""
        # Set up logger
        self.logger = logging.getLogger('NLPGISPlugin.PlatformAdapter')
        
        # Detect platform
        self.os_name = platform.system().lower()
        self.os_version = platform.version()
        
        # Initialize adapters
        self._init_adapters()
        
        self.logger.info(f"Platform detected: {self.os_name} {self.os_version}")
        
    def _init_adapters(self):
        """Initialize platform-specific adapters."""
        # File path handling
        if self.os_name == 'windows':
            self.path_separator = '\\'
            self.line_ending = '\r\n'
        else:
            self.path_separator = '/'
            self.line_ending = '\n'
            
        # Platform-specific directories
        if self.os_name == 'windows':
            self.config_dir = os.path.join(os.environ.get('APPDATA', ''), 'QGIS', 'NLP_GIS')
        elif self.os_name == 'darwin':  # macOS
            self.config_dir = os.path.expanduser('~/Library/Application Support/QGIS/NLP_GIS')
        else:  # Linux and others
            self.config_dir = os.path.expanduser('~/.config/QGIS/NLP_GIS')
            
        # Ensure config directory exists
        if not os.path.exists(self.config_dir):
            try:
                os.makedirs(self.config_dir)
            except Exception as e:
                self.logger.warning(f"Could not create config directory: {str(e)}")
                
    def get_platform_info(self) -> Dict[str, Any]:
        """
        Get information about the current platform.
        
        Returns:
            Dictionary with platform information
        """
        return {
            'os_name': self.os_name,
            'os_version': self.os_version,
            'python_version': platform.python_version(),
            'path_separator': self.path_separator,
            'config_dir': self.config_dir,
            'system_encoding': sys.getfilesystemencoding()
        }
        
    def adapt_file_path(self, path: str) -> str:
        """
        Adapt a file path for the current platform.
        
        Args:
            path: File path to adapt
            
        Returns:
            Adapted file path
        """
        # Replace path separators
        if self.os_name == 'windows':
            # Convert forward slashes to backslashes
            return path.replace('/', '\\')
        else:
            # Convert backslashes to forward slashes
            return path.replace('\\', '/')
            
    def get_temp_directory(self) -> str:
        """
        Get a temporary directory suitable for the current platform.
        
        Returns:
            Path to temporary directory
        """
        import tempfile
        
        # Create a subdirectory in the system temp directory
        temp_dir = os.path.join(tempfile.gettempdir(), 'qgis_nlp')
        
        # Ensure it exists
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)
            
        return temp_dir
        
    def adapt_processing_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Adapt processing parameters for the current platform.
        
        Args:
            parameters: Processing parameters
            
        Returns:
            Adapted parameters
        """
        adapted = parameters.copy()
        
        # Adapt file paths in parameters
        for key, value in adapted.items():
            if isinstance(value, str) and ('/' in value or '\\' in value):
                # Looks like a file path
                adapted[key] = self.adapt_file_path(value)
                
        return adapted
        
    def get_platform_specific_python_path(self) -> List[str]:
        """
        Get platform-specific Python path for executing scripts.
        
        Returns:
            List of path components
        """
        if self.os_name == 'windows':
            # Windows-specific path
            return ['C:\\Program Files\\QGIS 3.0\\bin\\python.exe']
        elif self.os_name == 'darwin':
            # macOS-specific path
            return ['/Applications/QGIS.app/Contents/MacOS/bin/python3']
        else:
            # Linux and others
            return ['/usr/bin/python3']
            
    def handle_platform_specific_error(self, error_message: str) -> Optional[str]:
        """
        Handle platform-specific errors.
        
        Args:
            error_message: Error message to check
            
        Returns:
            Platform-specific fix suggestion or None
        """
        lower_message = error_message.lower()
        
        # Windows-specific errors
        if self.os_name == 'windows':
            if 'access is denied' in lower_message:
                return "This error may be due to Windows file permissions. Try running QGIS as administrator."
            elif 'path too long' in lower_message:
                return "Windows has path length limitations. Try moving your data to a location with a shorter path."
                
        # macOS-specific errors
        elif self.os_name == 'darwin':
            if 'operation not permitted' in lower_message:
                return "This error may be due to macOS permissions. Check System Preferences > Security & Privacy."
                
        # Linux-specific errors
        else:
            if 'permission denied' in lower_message:
                return "This error may be due to Linux file permissions. Check the file permissions with 'ls -l'."
                
        # No platform-specific suggestion
        return None