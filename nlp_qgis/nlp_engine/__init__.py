# nlp_engine/__init__.py
import os
import logging
import pickle
import re
from typing import Dict, Any, List, Optional, Tuple
import warnings

# Suppress warnings from NLP libraries
warnings.filterwarnings("ignore", category=UserWarning)

try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    spacy = None

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    torch = None

from .ner_model import GISNamedEntityRecognizer
from .context_parser import GISContextParser
from .model_trainer import GISLanguageModelTrainer

class NLPEngine:
    """
    Main NLP Engine for GIS commands implementing WBSO Block 1 requirements.
    
    This engine addresses the technical bottlenecks:
    1. Custom Named Entity Recognition (NER) model for GIS terminology
    2. Context-sensitive interpretation of natural language
    3. Ambiguity resolution in GIS context
    4. Fine-tuning framework for language models
    """

    def __init__(self, model_path: Optional[str] = None):
        """Initialize the NLP engine components.
        
        Args:
            model_path: Optional path to pre-trained model
        """
        self.logger = logging.getLogger('NLPGISPlugin.NLPEngine')
        
        # Initialize availability flags
        self.spacy_available = SPACY_AVAILABLE
        self.torch_available = TORCH_AVAILABLE
        
        # Initialize components with fallback mechanisms
        self.ner = None
        self.context_parser = None
        self.model_trainer = None
        
        # Cache for frequent queries (WBSO Block 2 requirement)
        self.query_cache = {}
        self.max_cache_size = 100
        
        # Confidence threshold for disambiguation
        self.confidence_threshold = 0.6
        
        # GIS-specific vocabulary for fallback processing
        self.gis_vocabulary = self._initialize_gis_vocabulary()
        
        # Pattern matching rules for when NLP models aren't available
        self.fallback_patterns = self._initialize_fallback_patterns()
        
        # Initialize components
        self._initialize_components(model_path)
        
    def _initialize_components(self, model_path: Optional[str] = None):
        """
        Initialize NLP components with robust error handling.
        
        Args:
            model_path: Optional path to pre-trained model
        """
        try:
            # Initialize NER model
            if self.spacy_available:
                self.ner = GISNamedEntityRecognizer(model_path)
                self.logger.info("GIS NER model initialized successfully")
            else:
                self.logger.warning("spaCy not available - using fallback NER")
                self.ner = self._create_fallback_ner()
                
            # Initialize context parser
            self.context_parser = GISContextParser()
            self.logger.info("GIS context parser initialized")
            
            # Initialize model trainer if PyTorch is available
            if self.torch_available:
                self.model_trainer = GISLanguageModelTrainer()
                self.logger.info("Model trainer initialized")
            else:
                self.logger.warning("PyTorch not available - model training disabled")
                
        except Exception as e:
            self.logger.error(f"Error initializing NLP components: {str(e)}")
            # Initialize fallback components
            self._initialize_fallback_components()
            
    def _initialize_fallback_components(self):
        """Initialize fallback components when main NLP libraries aren't available."""
        self.logger.info("Initializing fallback NLP components")
        
        # Create simple rule-based NER
        self.ner = self._create_fallback_ner()
        
        # Context parser should work without external dependencies
        if not self.context_parser:
            self.context_parser = GISContextParser()
            
    def _create_fallback_ner(self):
        """Create a fallback NER when spaCy isn't available."""
        return FallbackNER(self.gis_vocabulary)
    
    def _initialize_gis_vocabulary(self) -> Dict[str, List[str]]:
        """
        Initialize GIS-specific vocabulary for fallback processing.
        Implements WBSO Block 1: Custom feature extraction methods
        """
        return {
            'operations': [
                'buffer', 'clip', 'intersect', 'intersection', 'union', 'merge', 'join',
                'select', 'filter', 'query', 'find', 'search', 'extract', 'dissolve',
                'split', 'overlay', 'spatial join', 'near', 'within', 'contains'
            ],
            'layer_types': [
                'roads', 'rivers', 'buildings', 'parcels', 'boundaries', 'points',
                'lines', 'polygons', 'raster', 'vector', 'shapefile', 'layer',
                'features', 'geometries', 'areas', 'zones', 'regions'
            ],
            'spatial_relationships': [
                'intersects', 'contains', 'within', 'overlaps', 'touches', 'crosses',
                'near', 'adjacent', 'inside', 'outside', 'close to', 'far from'
            ],
            'distance_units': [
                'meters', 'metres', 'm', 'kilometers', 'kilometres', 'km',
                'feet', 'foot', 'ft', 'miles', 'mile', 'mi', 'yards', 'yd'
            ],
            'attributes': [
                'area', 'length', 'perimeter', 'population', 'elevation', 'height',
                'name', 'type', 'class', 'category', 'id', 'code', 'status'
            ],
            'comparison_operators': [
                'greater than', 'less than', 'equal to', 'equals', 'is',
                'more than', 'bigger than', 'smaller than', 'above', 'below'
            ]
        }
    
    def _initialize_fallback_patterns(self) -> Dict[str, List[str]]:
        """
        Initialize pattern matching rules for fallback processing.
        Implements WBSO Block 1: Domain-specific entity classification approaches
        """
        return {
            'buffer': [
                r'(?:create|make)?\s*(?:a|the)?\s*buffer\s+(?:of|around|for)?\s*(.+?)\s+(?:by|of|with)?\s*(\d+\.?\d*)\s*(meter|metre|m|kilometer|kilometre|km|feet|foot|ft|mile|mi)',
                r'buffer\s+(?:the|a)?\s*(.+?)\s+(?:by|with)?\s*(\d+\.?\d*)\s*(meter|metre|m|kilometer|kilometre|km|feet|foot|ft|mile|mi)'
            ],
            'clip': [
                r'clip\s+(?:the|a)?\s*(.+?)\s+(?:with|using|by)\s+(?:the|a)?\s*(.+)',
                r'extract\s+(?:the|a)?\s*(.+?)\s+from\s+(?:the|a)?\s*(.+)',
                r'cut\s+(?:the|a)?\s*(.+?)\s+(?:with|using|by)\s+(?:the|a)?\s*(.+)'
            ],
            'intersection': [
                r'(?:find|get|compute|calculate)\s+(?:the)?\s*intersection\s+(?:of|between)?\s+(?:the|a)?\s*(.+?)\s+(?:and|with)\s+(?:the|a)?\s*(.+)',
                r'intersect\s+(?:the|a)?\s*(.+?)\s+(?:with|and)\s+(?:the|a)?\s*(.+)'
            ],
            'select': [
                r'select\s+(?:from|in)?\s*(?:the|a)?\s*(.+?)\s+where\s+(.+)',
                r'find\s+(?:all)?\s*(.+?)\s+where\s+(.+)',
                r'show\s+(?:me)?\s+(?:all)?\s*(.+?)\s+(?:that|which)\s+(.+)',
                r'filter\s+(?:the|a)?\s*(.+?)\s+(?:where|by)\s+(.+)'
            ],
            'union': [
                r'(?:merge|combine|union)\s+(?:the|a)?\s*(.+?)\s+(?:and|with)\s+(?:the|a)?\s*(.+)',
                r'join\s+(?:the|a)?\s*(.+?)\s+(?:and|with)\s+(?:the|a)?\s*(.+)'
            ]
        }

    def process_command(self, text: str, active_layers: Optional[List[str]] = None, 
                       current_crs: Optional[str] = None) -> Dict[str, Any]:
        """
        Process a natural language GIS command.
        
        Implements WBSO Block 1: Context-sensitive interpretation and ambiguity resolution
        
        Args:
            text: The command text
            active_layers: List of currently active layers in QGIS
            current_crs: Current coordinate reference system
            
        Returns:
            Structured interpretation of the GIS command
        """
        # Check cache first (WBSO Block 2: Performance optimization)
        cache_key = self._generate_cache_key(text, active_layers, current_crs)
        if cache_key in self.query_cache:
            self.logger.debug(f"Cache hit for query: {text[:50]}...")
            cached_result = self.query_cache[cache_key].copy()
            cached_result['from_cache'] = True
            return cached_result
        
        # Update context if provided
        if active_layers or current_crs:
            self.context_parser.update_context(active_layers, current_crs)
            
        try:
            # Primary processing with NER model
            if self.ner and hasattr(self.ner, 'extract_gis_commands'):
                entity_result = self.ner.extract_gis_commands(text)
            else:
                # Fallback entity extraction
                entity_result = self._fallback_entity_extraction(text)
                
            # Context parsing
            context_result = self.context_parser.parse_command(text)
            
            # Merge and enhance results
            merged_result = self._merge_and_enhance_results(
                entity_result, context_result, text, active_layers
            )
            
            # Apply disambiguation if confidence is low
            if merged_result.get('confidence', 0) < self.confidence_threshold:
                merged_result = self._apply_disambiguation(merged_result, text, active_layers)
                
            # Cache the result
            self._cache_result(cache_key, merged_result)
            
            return merged_result
            
        except Exception as e:
            self.logger.error(f"Error processing command '{text}': {str(e)}")
            # Return a basic error result
            return {
                "operation": "unknown",
                "input_layer": None,
                "parameters": {},
                "spatial_relationship": None,
                "confidence": 0.0,
                "original_text": text,
                "error": str(e),
                "processing_method": "error_fallback"
            }
    
    def _generate_cache_key(self, text: str, active_layers: Optional[List[str]], 
                           current_crs: Optional[str]) -> str:
        """Generate a cache key for the query."""
        # Create a normalized key
        key_parts = [
            text.lower().strip(),
            str(sorted(active_layers) if active_layers else []),
            current_crs or ""
        ]
        return "|".join(key_parts)
    
    def _cache_result(self, cache_key: str, result: Dict[str, Any]):
        """Cache a processing result."""
        # Remove from_cache flag if present
        cached_result = result.copy()
        cached_result.pop('from_cache', None)
        
        self.query_cache[cache_key] = cached_result
        
        # Limit cache size
        if len(self.query_cache) > self.max_cache_size:
            # Remove oldest entries (simple FIFO)
            oldest_keys = list(self.query_cache.keys())[:-self.max_cache_size//2]
            for key in oldest_keys:
                del self.query_cache[key]
    
    def _fallback_entity_extraction(self, text: str) -> Dict[str, Any]:
        """
        Fallback entity extraction when NER model isn't available.
        Implements WBSO Block 1: Specialized post-processing logic for GIS terminology
        """
        result = {
            "action": None,
            "primary_target": None,
            "parameters": {},
            "output": None,
            "spatial_modifiers": [],
            "confidence": 0.5,  # Lower confidence for fallback
            "processing_method": "fallback_extraction"
        }
        
        text_lower = text.lower()
        
        # Extract operation
        for operation, patterns in self.fallback_patterns.items():
            for pattern in patterns:
                match = re.search(pattern, text_lower)
                if match:
                    result["action"] = operation
                    
                    # Extract specific parameters based on operation
                    if operation == 'buffer' and len(match.groups()) >= 3:
                        result["primary_target"] = match.group(1).strip()
                        try:
                            distance = float(match.group(2))
                            unit = match.group(3).lower()
                            
                            # Convert to meters
                            if unit in ['kilometer', 'kilometre', 'km']:
                                distance *= 1000
                            elif unit in ['feet', 'foot', 'ft']:
                                distance *= 0.3048
                            elif unit in ['mile', 'mi']:
                                distance *= 1609.34
                                
                            result["parameters"]["distance"] = distance
                            result["parameters"]["unit"] = "meters"
                            result["confidence"] = 0.8
                        except ValueError:
                            pass
                            
                    elif operation in ['clip', 'intersection', 'union'] and len(match.groups()) >= 2:
                        result["primary_target"] = match.group(1).strip()
                        result["secondary_target"] = match.group(2).strip()
                        result["confidence"] = 0.75
                        
                    elif operation == 'select' and len(match.groups()) >= 2:
                        result["primary_target"] = match.group(1).strip()
                        result["parameters"]["expression"] = match.group(2).strip()
                        result["confidence"] = 0.7
                        
                    break
                    
            if result["action"]:
                break
        
        # If no pattern matched, try vocabulary-based extraction
        if not result["action"]:
            result = self._vocabulary_based_extraction(text_lower)
            
        return result
    
    def _vocabulary_based_extraction(self, text: str) -> Dict[str, Any]:
        """
        Extract information using GIS vocabulary when patterns don't match.
        """
        result = {
            "action": None,
            "primary_target": None,
            "parameters": {},
            "confidence": 0.3,  # Low confidence for vocabulary-only extraction
            "processing_method": "vocabulary_extraction"
        }
        
        # Find operations
        for operation in self.gis_vocabulary['operations']:
            if operation in text:
                result["action"] = operation
                result["confidence"] += 0.2
                break
                
        # Find layer types
        for layer_type in self.gis_vocabulary['layer_types']:
            if layer_type in text:
                if not result["primary_target"]:
                    result["primary_target"] = layer_type
                    result["confidence"] += 0.1
                break
                
        # Find spatial relationships
        for relationship in self.gis_vocabulary['spatial_relationships']:
            if relationship in text:
                result["spatial_modifiers"].append(relationship)
                result["confidence"] += 0.1
                break
                
        # Extract numeric values for distances
        number_pattern = r'(\d+\.?\d*)'
        numbers = re.findall(number_pattern, text)
        
        if numbers:
            try:
                # Assume first number is a distance
                distance = float(numbers[0])
                
                # Find associated unit
                for unit in self.gis_vocabulary['distance_units']:
                    if unit in text:
                        result["parameters"]["distance"] = distance
                        result["parameters"]["unit"] = unit
                        result["confidence"] += 0.15
                        break
            except ValueError:
                pass
                
        return result
    
    def _merge_and_enhance_results(self, entity_result: Dict[str, Any], 
                                  context_result: Dict[str, Any], 
                                  text: str, active_layers: Optional[List[str]]) -> Dict[str, Any]:
        """
        Merge results from different processing methods and enhance with context.
        Implements WBSO Block 1: Context-aware parser integration
        """
        # Start with context result as base
        merged_result = {
            "operation": context_result.get("operation", "unknown"),
            "input_layer": entity_result.get("primary_target") or context_result.get("input_layer"),
            "secondary_layer": entity_result.get("secondary_target") or context_result.get("secondary_layer"),
            "parameters": {**context_result.get("parameters", {}), **entity_result.get("parameters", {})},
            "spatial_relationship": context_result.get("spatial_relationship"),
            "confidence": max(entity_result.get("confidence", 0), context_result.get("confidence", 0)),
            "original_text": text,
            "processing_method": "merged"
        }
        
        # Use entity action if context didn't find operation
        if merged_result["operation"] == "unknown" and entity_result.get("action"):
            merged_result["operation"] = entity_result["action"]
            
        # Enhance with active layer matching
        if active_layers and merged_result["input_layer"]:
            matched_layer = self._match_layer_name(merged_result["input_layer"], active_layers)
            if matched_layer:
                merged_result["input_layer"] = matched_layer
                merged_result["confidence"] += 0.1
                
        if active_layers and merged_result.get("secondary_layer"):
            matched_layer = self._match_layer_name(merged_result["secondary_layer"], active_layers)
            if matched_layer:
                merged_result["secondary_layer"] = matched_layer
                merged_result["confidence"] += 0.05
                
        # Normalize confidence
        merged_result["confidence"] = min(merged_result["confidence"], 1.0)
        
        return merged_result
    
    def _match_layer_name(self, mentioned_name: str, active_layers: List[str]) -> Optional[str]:
        """
        Match a mentioned layer name to actual active layers.
        Implements WBSO Block 1: Ambiguity resolution in GIS context
        """
        mentioned_lower = mentioned_name.lower()
        
        # Exact match first
        for layer in active_layers:
            if layer.lower() == mentioned_lower:
                return layer
                
        # Partial match
        for layer in active_layers:
            if mentioned_lower in layer.lower() or layer.lower() in mentioned_lower:
                return layer
                
        # Token-based matching
        mentioned_tokens = mentioned_lower.split()
        for layer in active_layers:
            layer_tokens = layer.lower().replace('_', ' ').split()
            if any(token in layer_tokens for token in mentioned_tokens):
                return layer
                
        return None
    
    def _apply_disambiguation(self, result: Dict[str, Any], text: str, 
                            active_layers: Optional[List[str]]) -> Dict[str, Any]:
        """
        Apply disambiguation techniques when confidence is low.
        Implements WBSO Block 1: Ambiguity resolution
        """
        disambiguated = result.copy()
        
        # If no operation detected, try harder
        if result["operation"] == "unknown":
            # Look for action verbs
            action_words = ['create', 'make', 'find', 'get', 'show', 'calculate', 'compute']
            text_lower = text.lower()
            
            for word in action_words:
                if word in text_lower:
                    # Infer operation based on context
                    if any(gis_op in text_lower for gis_op in ['buffer', 'around']):
                        disambiguated["operation"] = "buffer"
                    elif any(gis_op in text_lower for gis_op in ['clip', 'cut', 'extract']):
                        disambiguated["operation"] = "clip"
                    elif any(gis_op in text_lower for gis_op in ['select', 'filter', 'where']):
                        disambiguated["operation"] = "select"
                    elif any(gis_op in text_lower for gis_op in ['intersect', 'intersection', 'overlap']):
                        disambiguated["operation"] = "intersection"
                    break
                    
        # If no input layer, try to infer from active layers
        if not result["input_layer"] and active_layers:
            # Use the first active layer as a guess
            disambiguated["input_layer"] = active_layers[0]
            disambiguated["parameters"]["auto_inferred_layer"] = True
            disambiguated["confidence"] += 0.1
            
        # Add disambiguation metadata
        disambiguated["disambiguation_applied"] = True
        disambiguated["original_confidence"] = result["confidence"]
        
        return disambiguated
    
    def get_suggestions(self, partial_text: str, active_layers: Optional[List[str]] = None) -> List[str]:
        """
        Get command completion suggestions.
        Implements WBSO Block 4: Query completion algorithms
        """
        suggestions = []
        text_lower = partial_text.lower()
        
        # Operation-based suggestions
        if not any(op in text_lower for op in self.gis_vocabulary['operations']):
            # Suggest operations
            if 'buff' in text_lower:
                suggestions.append("Buffer the roads layer by 500 meters")
            elif 'clip' in text_lower or 'cut' in text_lower:
                suggestions.append("Clip buildings with city boundaries")
            elif 'select' in text_lower or 'find' in text_lower:
                suggestions.append("Select buildings where area > 1000")
            elif 'intersect' in text_lower:
                suggestions.append("Find intersection of roads and flood zones")
                
        # Layer-based suggestions
        if active_layers:
            for layer in active_layers[:3]:  # Top 3 layers
                suggestions.append(f"Buffer {layer} by 100 meters")
                suggestions.append(f"Select {layer} where name is not null")
                
        # Common operation suggestions
        if len(suggestions) < 5:
            common_suggestions = [
                "Buffer the selected layer by 500 meters",
                "Find buildings within 1km of hospitals",
                "Select roads where type equals 'highway'",
                "Clip rivers with study area boundaries",
                "Calculate area of all polygons"
            ]
            suggestions.extend(common_suggestions[:5 - len(suggestions)])
            
        return suggestions
    
    def train_model(self, training_data: List[Tuple[str, Dict[str, Any]]], 
                   epochs: int = 30) -> bool:
        """
        Train the NLP model with GIS-specific data.
        Implements WBSO Block 1: Fine-tuning framework for language models
        """
        if not self.model_trainer:
            self.logger.warning("Model trainer not available - cannot train model")
            return False
            
        try:
            if self.ner and hasattr(self.ner, 'train'):
                self.ner.train(training_data, epochs)
                self.logger.info(f"Model training completed with {len(training_data)} examples")
                return True
            else:
                self.logger.warning("NER model doesn't support training")
                return False
                
        except Exception as e:
            self.logger.error(f"Error during model training: {str(e)}")
            return False
    
    def evaluate_model(self, test_data: List[Tuple[str, Dict[str, Any]]]) -> Dict[str, float]:
        """
        Evaluate model performance on test data.
        Implements WBSO Block 1: Testbed for evaluating NER accuracy
        """
        if not test_data:
            return {"error": "No test data provided"}
            
        correct_operations = 0
        correct_layers = 0
        confidence_scores = []
        
        for text, expected in test_data:
            try:
                result = self.process_command(text)
                
                # Check operation accuracy
                if result.get("operation") == expected.get("operation"):
                    correct_operations += 1
                    
                # Check layer accuracy
                if result.get("input_layer") == expected.get("input_layer"):
                    correct_layers += 1
                    
                # Collect confidence scores
                confidence_scores.append(result.get("confidence", 0))
                
            except Exception as e:
                self.logger.error(f"Error evaluating test case '{text}': {str(e)}")
                confidence_scores.append(0)
                
        total_tests = len(test_data)
        
        return {
            "operation_accuracy": correct_operations / total_tests if total_tests > 0 else 0,
            "layer_accuracy": correct_layers / total_tests if total_tests > 0 else 0,
            "average_confidence": sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0,
            "total_tests": total_tests
        }
    
    def clear_cache(self):
        """Clear the query cache."""
        self.query_cache.clear()
        self.logger.info("Query cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "cache_size": len(self.query_cache),
            "max_cache_size": self.max_cache_size,
            "cache_keys": list(self.query_cache.keys())
        }


class FallbackNER:
    """
    Fallback NER implementation when spaCy isn't available.
    Implements basic entity recognition using pattern matching.
    """
    
    def __init__(self, gis_vocabulary: Dict[str, List[str]]):
        self.vocabulary = gis_vocabulary
        
    def extract_gis_commands(self, text: str) -> Dict[str, Any]:
        """Extract GIS commands using pattern matching."""
        result = {
            "action": None,
            "primary_target": None,
            "secondary_target": None,
            "parameters": {},
            "confidence": 0.4,  # Lower confidence for fallback
            "processing_method": "fallback_ner"
        }
        
        text_lower = text.lower()
        
        # Find operations
        for operation in self.vocabulary['operations']:
            if operation in text_lower:
                result["action"] = operation
                result["confidence"] += 0.2
                break
                
        # Find layers
        for layer_type in self.vocabulary['layer_types']:
            if layer_type in text_lower:
                if not result["primary_target"]:
                    result["primary_target"] = layer_type
                elif not result["secondary_target"]:
                    result["secondary_target"] = layer_type
                result["confidence"] += 0.1
                
        # Find distances
        distance_pattern = r'(\d+\.?\d*)\s*(meter|metre|m|kilometer|kilometre|km|feet|foot|ft|mile|mi)'
        match = re.search(distance_pattern, text_lower)
        if match:
            try:
                distance = float(match.group(1))
                unit = match.group(2)
                result["parameters"]["distance"] = distance
                result["parameters"]["unit"] = unit
                result["confidence"] += 0.2
            except ValueError:
                pass
                
        return result