# QGIS NLP Plugin - Installation and Setup Guide

## 📋 Prerequisites

### Required Software
- QGIS 3.0 or higher
- Python 3.6 or higher
- PyQt5 (usually comes with QGIS)

### Optional Dependencies (for enhanced features)
```bash
# Install NLP libraries for advanced features
pip install spacy>=3.0.0
pip install torch>=1.8.0
pip install transformers>=4.5.0
pip install nltk>=3.6.0

# Download spaCy English model
python -m spacy download en_core_web_sm
```

## 🚀 Installation Steps

### 1. Download the Plugin
Place all plugin files in your QGIS plugins directory:

**Windows:**
```
C:\Users\[username]\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\nlp_qgis\
```

**macOS:**
```
~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/nlp_qgis/
```

**Linux:**
```
~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/nlp_qgis/
```

### 2. File Structure
Ensure your plugin directory has this structure:
```
nlp_qgis/
├── __init__.py
├── plugin_main.py
├── metadata.txt
├── requirements.txt
├── icon.png
├── resources.qrc
├── nlp_engine/
│   ├── __init__.py (complete version)
│   ├── ner_model.py
│   ├── context_parser.py
│   └── model_trainer.py
├── qgis_integration/
│   ├── __init__.py
│   ├── event_dispatcher.py (fixed version)
│   ├── async_processor.py
│   └── memory_manager.py
├── error_system/
│   ├── __init__.py
│   ├── error_logger.py
│   ├── transaction_log.py
│   ├── event_interceptor.py
│   └── prevention.py
├── query_engine/
│   ├── __init__.py
│   ├── query_parser.py
│   ├── parameter_resolver.py
│   └── query_optimizer.py (complete version)
└── testing/
    ├── __init__.py
    ├── test_suite.py
    ├── state_preserver.py
    └── platform_adapter.py
```

### 3. Enable the Plugin
1. Open QGIS
2. Go to **Plugins** → **Manage and Install Plugins**
3. Click **Installed** tab
4. Find "NLP GIS Assistant" and check the box to enable it

## ⚙️ Configuration

### Basic Setup
1. **First Launch**: The plugin will initialize with fallback components if advanced NLP libraries aren't available
2. **Check Status**: Open the plugin dock widget to see initialization status
3. **Settings Tab**: Configure performance and NLP settings

### Advanced Setup (with NLP libraries)
If you installed the optional dependencies:

1. **Verify Installation**: 
   ```python
   # In QGIS Python console
   import spacy
   import torch
   print("Advanced NLP features available!")
   ```

2. **Model Training** (optional):
   - Use the Testing tab to train custom models
   - Provide domain-specific training data
   - Monitor training progress

## 🧪 Testing the Installation

### Quick Test Commands
Try these commands to verify the plugin works:

```
Basic Commands:
- "Buffer the roads layer by 500 meters"
- "Select buildings where area > 1000"
- "Find intersection of rivers and boundaries"

Advanced Commands:
- "Create a 2km buffer around hospitals and select residential areas within it"
- "Find all buildings that are within 500m of rivers and have area > 1000"
```

### Test Suite
1. Open the plugin dock widget
2. Go to **Testing & Recovery** tab
3. Click **Run All Tests**
4. Check results for any issues

## 🛠️ Troubleshooting

### Common Issues

**1. Plugin doesn't appear in menu**
- Check file permissions
- Verify `__init__.py` contains `classFactory` function
- Check QGIS Python console for errors

**2. Import errors**
```python
# Check in QGIS Python console
import sys
print(sys.path)

# Add plugin path if needed
sys.path.append('/path/to/nlp_qgis')
```

**3. NLP features not working**
```bash
# Install missing dependencies
pip install spacy torch transformers
python -m spacy download en_core_web_sm
```

**4. Memory issues with large datasets**
- Adjust max features in Settings tab
- Enable query optimizations
- Use smaller buffer distances

### Debug Mode
Enable debug logging by adding to QGIS Python console:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 📚 Usage Examples

### Basic Operations

**Buffer Operations:**
```
"Buffer roads by 100 meters"
"Create a 500m buffer around the hospital layer"
"Make a 2 kilometer buffer for all buildings"
```

**Selection Operations:**
```
"Select buildings where area > 1000"
"Find roads where type equals 'highway'"
"Show all polygons with population > 5000"
```

**Spatial Operations:**
```
"Find intersection of roads and flood zones"
"Clip buildings with city boundaries"
"Get all features within 1km of rivers"
```

### Advanced Operations

**Complex Queries:**
```
"Buffer hospitals by 500m, then select residential areas within the buffer"
"Find buildings that intersect with flood zones and have area > 500"
"Select roads within 200m of schools where speed_limit > 50"
```

**Analysis Commands:**
```
"Calculate total area of all forest patches"
"Count buildings in each administrative district"
"Find average elevation of selected parcels"
```

## 🔧 Performance Tuning

### Settings Configuration

**Performance Settings:**
- **Max Features**: Limit processing for large datasets (default: 10,000)
- **Enable Optimizations**: Use query optimization (recommended: ON)
- **Error Prevention**: Enable proactive error detection (recommended: ON)

**NLP Settings:**
- **Confidence Threshold**: Minimum confidence for execution (default: 60%)
- **Cache Size**: Number of cached queries (default: 100)

### Memory Management
Monitor memory usage in the **Monitoring** tab:
- Track processing times
- Monitor success rates
- View error patterns
- Check cache statistics

## 🛡️ Error Recovery

### State Management
- **Save State**: Create manual save points before complex operations
- **Recovery Points**: Automatic snapshots during operations
- **Emergency Rollback**: Restore to last known good state

### Error Prevention
The plugin includes proactive error detection:
- **Risk Assessment**: Warns about potentially problematic operations
- **Resource Monitoring**: Prevents memory-intensive operations
- **Input Validation**: Checks parameters before execution

## 📊 Monitoring and Analytics

### Performance Metrics
Track plugin performance:
- Commands processed
- Success/failure rates
- Average processing times
- Error patterns

### Error Analysis
Monitor and analyze:
- Error frequency by operation type
- Common failure patterns
- Performance bottlenecks
- Resource usage trends

## 🔄 Updates and Maintenance

### Regular Maintenance
1. **Clear Cache**: Periodically clear query cache
2. **Update Models**: Retrain NLP models with new data
3. **Check Logs**: Review error logs for patterns
4. **Performance Review**: Monitor processing times

### Plugin Updates
1. **Backup Settings**: Save current configuration
2. **Export Recovery Points**: Preserve important states
3. **Update Files**: Replace plugin files
4. **Restore Configuration**: Reapply settings

## 📞 Support and WBSO Compliance

### WBSO Documentation
This plugin implements all technical requirements from the WBSO submission:

- ✅ **Block 1**: NLP Integration (120 hours)
- ✅ **Block 2**: Plugin Architecture (140 hours)  
- ✅ **Block 3**: Error Detection (140 hours)
- ✅ **Block 4**: Query Translation (120 hours)
- ✅ **Block 5**: Testing Framework (30 hours)

### Technical Support
For technical issues:
1. Check the **Monitoring** tab for error details
2. Review logs in the error system
3. Use the **Testing & Recovery** tab for diagnostics
4. Consult the WBSO implementation documentation

### Research and Development
This plugin represents cutting-edge research in:
- Natural Language Processing for GIS
- AI-driven spatial analysis
- Error prediction and prevention
- Cross-platform GIS automation

The implementation provides a foundation for future research and commercial applications in the geospatial industry.
