# nlp_engine/model_trainer.py
import os
import sys
import logging
from typing import List, Dict, Any, Optional

# Fix DLL loading issues before importing heavy libraries
def fix_dll_loading():
    """Fix DLL loading issues for PyTorch and related libraries in QGIS."""
    try:
        # Get QGIS Python directory
        python_dir = os.path.dirname(sys.executable)
        
        # Add DLL directories for Windows
        if os.name == 'nt' and hasattr(os, 'add_dll_directory'):
            dll_dirs = [
                python_dir,
                os.path.join(python_dir, 'Library', 'bin'),
                os.path.join(python_dir, 'DLLs'),
                os.path.join(python_dir, 'Scripts')
            ]
            
            for dll_dir in dll_dirs:
                if os.path.exists(dll_dir):
                    try:
                        os.add_dll_directory(dll_dir)
                    except (OSError, FileNotFoundError):
                        pass
        
        # Set environment variables
        current_path = os.environ.get('PATH', '')
        if python_dir not in current_path:
            os.environ['PATH'] = python_dir + os.pathsep + current_path
            
        # Fix specific library paths
        for site_packages in sys.path:
            if 'site-packages' in site_packages:
                torch_lib = os.path.join(site_packages, 'torch', 'lib')
                if os.path.exists(torch_lib) and hasattr(os, 'add_dll_directory'):
                    try:
                        os.add_dll_directory(torch_lib)
                    except (OSError, FileNotFoundError):
                        pass
                break
                
    except Exception as e:
        # If fixing fails, log but don't crash
        logging.warning(f"Could not fix DLL paths: {e}")

# Apply DLL fix before importing heavy libraries
fix_dll_loading()

# Now try to import with better error handling
def safe_import_with_retry(module_name, package=None, retry_count=3):
    """Safely import modules with retry logic for DLL issues."""
    for attempt in range(retry_count):
        try:
            if package:
                return __import__(module_name, fromlist=[package])
            else:
                return __import__(module_name)
        except ImportError as e:
            if "DLL load failed" in str(e) and attempt < retry_count - 1:
                # Try to fix path issues and retry
                fix_dll_loading()
                continue
            else:
                # Final attempt failed or different error
                raise e

# Try importing with DLL fixes
try:
    torch = safe_import_with_retry('torch')
    TORCH_AVAILABLE = True
except ImportError as e:
    TORCH_AVAILABLE = False
    torch = None
    logging.warning(f"PyTorch not available: {e}")

try:
    # Import transformers components individually to isolate issues
    transformers = safe_import_with_retry('transformers')
    AutoTokenizer = transformers.AutoTokenizer
    AutoModelForTokenClassification = transformers.AutoModelForTokenClassification
    TrainingArguments = transformers.TrainingArguments
    Trainer = transformers.Trainer
    TRANSFORMERS_AVAILABLE = True
except ImportError as e:
    TRANSFORMERS_AVAILABLE = False
    logging.warning(f"Transformers not available: {e}")
    
    # Create safe dummy classes
    class AutoTokenizer:
        @staticmethod
        def from_pretrained(*args, **kwargs):
            raise ImportError("Transformers library not available")
    
    class AutoModelForTokenClassification:
        @staticmethod
        def from_pretrained(*args, **kwargs):
            raise ImportError("Transformers library not available")
            
    class TrainingArguments:
        def __init__(self, *args, **kwargs):
            raise ImportError("Transformers library not available")
            
    class Trainer:
        def __init__(self, *args, **kwargs):
            raise ImportError("Transformers library not available")

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    np = None

# Handle datasets import (often the source of pyarrow DLL issues)
try:
    # Try to import datasets with specific error handling for pyarrow
    datasets = safe_import_with_retry('datasets')
    Dataset = datasets.Dataset
    DATASETS_AVAILABLE = True
except ImportError as e:
    DATASETS_AVAILABLE = False
    logging.warning(f"Datasets library not available: {e}")
    
    class Dataset:
        @staticmethod
        def from_list(*args, **kwargs):
            raise ImportError("Datasets library not available")

class GISLanguageModelTrainer:
    """
    Robust fine-tuning framework for language models with DLL conflict handling.
    
    This implementation includes specific fixes for Windows DLL loading issues
    that commonly occur when using PyTorch/Transformers in QGIS environment.
    """
    
    def __init__(self, model_name: str = "distilbert-base-uncased"):
        """Initialize the trainer with robust error handling."""
        self.logger = logging.getLogger('NLPGISPlugin.ModelTrainer')
        
        self.model_name = model_name
        self.tokenizer = None
        self.model = None
        
        # Check availability
        self.transformers_available = TRANSFORMERS_AVAILABLE
        self.torch_available = TORCH_AVAILABLE
        self.numpy_available = NUMPY_AVAILABLE
        self.datasets_available = DATASETS_AVAILABLE
        
        # Log status
        self.logger.info(f"Model trainer initialized - PyTorch: {self.torch_available}, "
                        f"Transformers: {self.transformers_available}, "
                        f"Datasets: {self.datasets_available}")
        
        # Try to initialize tokenizer if possible
        if self.transformers_available:
            self._safe_init_tokenizer()
    
    def _safe_init_tokenizer(self):
        """Safely initialize tokenizer with error handling."""
        try:
            self.logger.info("Attempting to initialize tokenizer...")
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.logger.info(f"Tokenizer initialized successfully for {self.model_name}")
        except Exception as e:
            self.logger.error(f"Failed to initialize tokenizer: {e}")
            self.transformers_available = False
            
    def diagnose_environment(self) -> Dict[str, Any]:
        """Diagnose the current environment for troubleshooting."""
        diagnosis = {
            'python_executable': sys.executable,
            'python_version': sys.version,
            'python_path': sys.path[:3],  # First 3 entries
            'dll_search_paths': [],
            'environment_variables': {
                'PATH': os.environ.get('PATH', '')[:200] + '...',  # Truncated
                'PYTHONPATH': os.environ.get('PYTHONPATH', 'Not set')
            },
            'library_locations': {}
        }
        
        # Check DLL search paths (Windows only)
        if hasattr(os, 'add_dll_directory'):
            try:
                # Can't easily list all DLL directories, but we can check common ones
                common_dirs = [
                    os.path.dirname(sys.executable),
                    os.path.join(os.path.dirname(sys.executable), 'Library', 'bin'),
                    os.path.join(os.path.dirname(sys.executable), 'DLLs')
                ]
                diagnosis['dll_search_paths'] = [d for d in common_dirs if os.path.exists(d)]
            except:
                pass
        
        # Find library locations
        for lib_name in ['torch', 'transformers', 'datasets']:
            try:
                lib = __import__(lib_name)
                diagnosis['library_locations'][lib_name] = getattr(lib, '__file__', 'Unknown')
            except ImportError:
                diagnosis['library_locations'][lib_name] = 'Not installed'
        
        return diagnosis
    
    def is_training_available(self) -> bool:
        """Check if model training is available."""
        return self.transformers_available and self.torch_available
    
    def get_detailed_status(self) -> Dict[str, Any]:
        """Get detailed status including troubleshooting information."""
        status = {
            'libraries': {
                'torch': self.torch_available,
                'transformers': self.transformers_available,
                'numpy': self.numpy_available,
                'datasets': self.datasets_available
            },
            'training_available': self.is_training_available(),
            'tokenizer_initialized': self.tokenizer is not None,
            'model_loaded': self.model is not None
        }
        
        if not self.is_training_available():
            status['recommendations'] = self._get_installation_recommendations()
            
        return status
    
    def _get_installation_recommendations(self) -> List[str]:
        """Get installation recommendations based on current status."""
        recommendations = []
        
        if not self.torch_available:
            recommendations.append(
                "Install PyTorch in QGIS Python environment: "
                "Use QGIS's pip to install torch (CPU version recommended)"
            )
        
        if not self.transformers_available:
            recommendations.append(
                "Install Transformers: pip install transformers in QGIS Python environment"
            )
            
        if not self.datasets_available:
            recommendations.append(
                "Install Datasets: pip install datasets (may require fixing pyarrow DLL conflicts)"
            )
        
        recommendations.append(
            "Alternative: Use conda environment and add to QGIS Python path"
        )
        
        return recommendations
    
    def install_in_qgis_environment(self) -> bool:
        """Attempt to install required packages in QGIS environment."""
        try:
            import subprocess
            
            # Get QGIS Python executable
            python_exe = sys.executable
            
            # Install packages
            packages = ['torch', 'transformers', 'datasets', 'spacy']
            
            for package in packages:
                self.logger.info(f"Installing {package}...")
                result = subprocess.run([
                    python_exe, '-m', 'pip', 'install', package
                ], capture_output=True, text=True)
                
                if result.returncode != 0:
                    self.logger.error(f"Failed to install {package}: {result.stderr}")
                    return False
                else:
                    self.logger.info(f"Successfully installed {package}")
            
            # Try to download spaCy model
            self.logger.info("Downloading spaCy model...")
            result = subprocess.run([
                python_exe, '-m', 'spacy', 'download', 'en_core_web_sm'
            ], capture_output=True, text=True)
            
            if result.returncode != 0:
                self.logger.warning(f"Failed to download spaCy model: {result.stderr}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Installation failed: {e}")
            return False
    
    def prepare_training_data(self, examples: List[Dict[str, Any]]) -> Optional[Any]:
        """Prepare training data with error handling."""
        if not self.is_training_available():
            self.logger.warning("Training not available - missing dependencies")
            return None
        
        try:
            if self.datasets_available:
                # Use full datasets functionality
                features = []
                for example in examples:
                    if not self.tokenizer:
                        self.logger.error("Tokenizer not available")
                        return None
                        
                    tokens = self.tokenizer(
                        example["text"],
                        padding="max_length",
                        truncation=True,
                        max_length=128,
                        return_tensors="pt"
                    )
                    
                    item = {key: val.squeeze().tolist() for key, val in tokens.items()}
                    if "labels" in example:
                        item["labels"] = example["labels"]
                    
                    features.append(item)
                
                return Dataset.from_list(features)
            else:
                # Fallback to simple list format
                return self._prepare_simple_data(examples)
                
        except Exception as e:
            self.logger.error(f"Error preparing training data: {e}")
            return None
    
    def _prepare_simple_data(self, examples: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Simple data preparation without datasets library."""
        if not self.tokenizer:
            return []
        
        features = []
        for example in examples:
            try:
                tokens = self.tokenizer.encode(
                    example.get("text", ""), 
                    max_length=128, 
                    truncation=True
                )
                
                feature = {
                    "input_ids": tokens,
                    "text": example.get("text", "")
                }
                
                if "labels" in example:
                    feature["labels"] = example["labels"]
                
                features.append(feature)
            except Exception as e:
                self.logger.error(f"Error processing example: {e}")
                continue
        
        return features
    
    def create_synthetic_training_data(self) -> List[Dict[str, Any]]:
        """Create synthetic training data for GIS NLP."""
        return [
            {"text": "Buffer the rivers layer by 500 meters", "labels": [0] * 10},
            {"text": "Select buildings within 1 km of hospital", "labels": [0] * 10},
            {"text": "Find intersection of roads and flood zones", "labels": [0] * 10},
            {"text": "Calculate area of forest patches", "labels": [0] * 8},
            {"text": "Create heatmap of crime incidents", "labels": [0] * 8},
            {"text": "Clip parcels with city boundaries", "labels": [0] * 8},
            {"text": "Show elevation above 1000 feet", "labels": [0] * 8},
            {"text": "Find nearest hospital to each school", "labels": [0] * 9}
        ]
    
    def test_basic_functionality(self) -> Dict[str, Any]:
        """Test basic functionality to verify installation."""
        results = {
            'tokenizer_test': False,
            'model_loading_test': False,
            'data_preparation_test': False,
            'errors': []
        }
        
        try:
            # Test tokenizer
            if self.tokenizer:
                test_text = "Buffer roads by 500 meters"
                tokens = self.tokenizer.encode(test_text)
                if tokens:
                    results['tokenizer_test'] = True
        except Exception as e:
            results['errors'].append(f"Tokenizer test failed: {e}")
        
        try:
            # Test data preparation
            test_data = [{"text": "Test command", "labels": [0, 1, 0]}]
            prepared = self.prepare_training_data(test_data)
            if prepared:
                results['data_preparation_test'] = True
        except Exception as e:
            results['errors'].append(f"Data preparation test failed: {e}")
        
        return results