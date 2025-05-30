# __init__.py




import os
import sys

# Fix DLL loading issues
def fix_dll_paths():
    """Fix DLL loading paths for PyTorch and related libraries."""
    
    # Get QGIS Python path
    qgis_python = os.path.dirname(sys.executable)
    
    # Add QGIS Python paths to DLL search
    if hasattr(os, 'add_dll_directory'):  # Windows 10+
        try:
            os.add_dll_directory(qgis_python)
            os.add_dll_directory(os.path.join(qgis_python, 'Library', 'bin'))
            os.add_dll_directory(os.path.join(qgis_python, 'DLLs'))
        except (OSError, AttributeError):
            pass
    
    # Set environment variables for DLL loading
    os.environ['PATH'] = qgis_python + os.pathsep + os.environ.get('PATH', '')
    
    # Fix PyTorch DLL issues specifically
    torch_lib_path = None
    for path in sys.path:
        torch_path = os.path.join(path, 'torch', 'lib')
        if os.path.exists(torch_path):
            torch_lib_path = torch_path
            break
    
    if torch_lib_path and hasattr(os, 'add_dll_directory'):
        try:
            os.add_dll_directory(torch_lib_path)
        except (OSError, AttributeError):
            pass

# Call the fix before any other imports
fix_dll_paths()



def classFactory(iface):
    """Load NLPGISPlugin class from plugin_main.py
    
    This function is required by QGIS and is called when the plugin is loaded.
    
    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    from .plugin_main import NLPGISPlugin
    return NLPGISPlugin(iface)