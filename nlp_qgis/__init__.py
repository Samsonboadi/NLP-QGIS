# __init__.py
def classFactory(iface):
    """Load NLPGISPlugin class from plugin_main.py
    
    This function is required by QGIS and is called when the plugin is loaded.
    
    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    from .plugin_main import NLPGISPlugin
    return NLPGISPlugin(iface)