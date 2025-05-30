# nlp_engine/context_parser.py
from typing import Dict, Any, List, Optional
import re

class GISContextParser:
    """Context-aware parser for GIS natural language commands."""
    
    def __init__(self, active_layers=None, current_crs=None):
        """Initialize the context parser.
        
        Args:
            active_layers: List of currently loaded layers
            current_crs: Current coordinate reference system
        """
        self.active_layers = active_layers or []
        self.current_crs = current_crs
        
        # Common GIS operations dictionary mapping natural language to GIS operations
        self.operation_mappings = {
            # Geometric operations
            "buffer": ["buffer", "create buffer", "make buffer", "buffering"],
            "intersect": ["intersect", "intersection", "overlapping", "overlap", "overlaps with"],
            "clip": ["clip", "cut", "extract", "trim"],
            "merge": ["merge", "combine", "join", "dissolve"],
            "union": ["union", "unite", "combine"],
            "split": ["split", "divide", "separate"],
            
            # Selection operations
            "select": ["select", "choose", "pick", "filter", "find", "get"],
            "query": ["query", "search", "find", "where"],
            
            # Analysis operations  
            "proximity": ["near", "close to", "within", "distance", "proximity"],
            "density": ["density", "concentration", "hotspot", "cluster"],
            "statistics": ["statistics", "calculate", "compute", "stats", "mean", "average", "sum"]
        }
        
        # Common spatial relationship terms
        self.spatial_relationships = [
            "near", "close to", "far from", "adjacent to", "within", "contains",
            "inside", "outside", "intersects", "overlaps", "crosses", "touches"
        ]
        
    def update_context(self, active_layers: List[str], current_crs: Optional[str] = None):
        """Update the context with current GIS state.
        
        Args:
            active_layers: List of currently loaded layers
            current_crs: Current coordinate reference system
        """
        self.active_layers = active_layers
        if current_crs:
            self.current_crs = current_crs
            
    def identify_operation(self, text: str) -> str:
        """Identify the most likely GIS operation from text.
        
        Args:
            text: Natural language command text
            
        Returns:
            The identified operation name or "unknown"
        """
        text = text.lower()
        
        for operation, phrases in self.operation_mappings.items():
            for phrase in phrases:
                if phrase in text:
                    return operation
                    
        return "unknown"
    
    def identify_layers(self, text: str) -> List[str]:
        """Identify potential layer names mentioned in the text.
        
        Args:
            text: Natural language command text
            
        Returns:
            List of potential layer names
        """
        identified_layers = []
        
        # First check for exact matches with active layers
        for layer in self.active_layers:
            if layer.lower() in text.lower():
                identified_layers.append(layer)
                
        # If no exact matches, look for partial matches
        if not identified_layers:
            for layer in self.active_layers:
                # Create tokens from layer name (e.g., "road_network" -> ["road", "network"])
                layer_tokens = re.split(r'[_\s-]', layer.lower())
                
                for token in layer_tokens:
                    if len(token) > 3 and token in text.lower():
                        identified_layers.append(layer)
                        break
        
        return identified_layers
    
    def extract_numeric_parameters(self, text: str) -> Dict[str, float]:
        """Extract numeric parameters like distances from text.
        
        Args:
            text: Natural language command text
            
        Returns:
            Dictionary of parameter types and values
        """
        parameters = {}
        
        # Match patterns like "500 meters", "2.5 km", etc.
        distance_pattern = r'(\d+\.?\d*)\s*(meter|meters|m|kilometer|kilometers|km|feet|foot|ft|mile|miles|mi)'
        matches = re.findall(distance_pattern, text, re.IGNORECASE)
        
        if matches:
            value, unit = matches[0]
            value = float(value)
            
            # Convert to meters for consistency
            if unit.lower() in ['kilometer', 'kilometers', 'km']:
                value *= 1000
            elif unit.lower() in ['feet', 'foot', 'ft']:
                value *= 0.3048
            elif unit.lower() in ['mile', 'miles', 'mi']:
                value *= 1609.34
                
            parameters['distance'] = value
            
        # Could add more parameter types here
            
        return parameters
    
    def identify_spatial_relationship(self, text: str) -> Optional[str]:
        """Identify spatial relationship terms in text.
        
        Args:
            text: Natural language command text
            
        Returns:
            Identified spatial relationship or None
        """
        text = text.lower()
        
        for relation in self.spatial_relationships:
            if relation in text:
                return relation
                
        return None
    
    def parse_command(self, text: str) -> Dict[str, Any]:
        """Parse a natural language command into structured GIS operation.
        
        Args:
            text: Natural language command
            
        Returns:
            Dictionary with operation details
        """
        result = {
            "operation": self.identify_operation(text),
            "layers": self.identify_layers(text),
            "parameters": self.extract_numeric_parameters(text),
            "spatial_relationship": self.identify_spatial_relationship(text),
            "original_text": text
        }
        
        # Try to determine input and output layers
        if result["layers"]:
            # Heuristic: First mentioned layer is often the input
            result["input_layer"] = result["layers"][0]
            
            # If there are multiple layers, second is often output or secondary input
            if len(result["layers"]) > 1:
                result["secondary_layer"] = result["layers"][1]
        
        return result