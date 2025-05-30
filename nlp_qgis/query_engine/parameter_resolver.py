# query_engine/parameter_resolver.py
from typing import Dict, List, Any, Optional, Tuple
import logging
import re

class ParameterResolver:
    """
    Resolver for missing parameters in GIS operations.
    
    This class handles the inference of missing parameters based on
    context, defaults, and heuristics.
    """
    
    def __init__(self):
        """Initialize the parameter resolver."""
        # Set up logger
        self.logger = logging.getLogger('NLPGISPlugin.ParameterResolver')
        
        # Parameter defaults for different operations
        self.parameter_defaults = {
            'buffer': {
                'distance': 100,  # Default 100 meters
                'segments': 5,
                'end_cap_style': 0,  # Round
                'join_style': 0,     # Round
                'miter_limit': 2,
                'dissolve': False
            },
            'clip': {},
            'intersection': {
                'input_fields': [],  # Empty means all fields
                'overlay_fields': []
            },
            'union': {},
            'select': {}
        }
        
        # Parameter translation dictionaries (for mapping natural language to technical parameters)
        self.parameter_translations = {
            'buffer_cap_style': {
                'round': 0,
                'flat': 1,
                'square': 2
            },
            'buffer_join_style': {
                'round': 0,
                'miter': 1,
                'bevel': 2
            }
        }
        
    def resolve_parameters(self, operation_type: str, parsed_params: Dict[str, Any], 
                          context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Resolve and complete parameters for a GIS operation.
        
        Args:
            operation_type: Type of GIS operation
            parsed_params: Parameters extracted from NLP
            context: Optional context information
            
        Returns:
            Complete parameter dictionary for the operation
        """
        # Start with defaults for this operation type
        defaults = self.parameter_defaults.get(operation_type, {})
        resolved_params = defaults.copy()
        
        # Update with parsed parameters
        resolved_params.update(parsed_params)
        
        # Apply operation-specific parameter resolution
        resolver_method = getattr(self, f"_resolve_{operation_type}_params", None)
        if resolver_method:
            resolved_params = resolver_method(resolved_params, context)
            
        return resolved_params
        
    def _resolve_buffer_params(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Resolve buffer operation parameters.
        
        Args:
            params: Current parameters
            context: Optional context information
            
        Returns:
            Resolved parameters
        """
        # If distance not specified, infer from context
        if 'distance' not in params and context:
            # Try to infer based on map scale
            if 'scale' in context:
                scale = context['scale']
                
                # Heuristic: use larger buffers for smaller scales (zoomed out)
                if scale > 1000000:  # Very zoomed out (e.g., country level)
                    params['distance'] = 5000  # 5km
                elif scale > 100000:  # City level
                    params['distance'] = 1000  # 1km
                elif scale > 10000:   # Neighborhood level
                    params['distance'] = 200   # 200m
                elif scale > 1000:    # Block level
                    params['distance'] = 50    # 50m
                else:                 # Building level
                    params['distance'] = 10    # 10m
                    
            # Another approach: use % of current extent
            elif 'extent' in context:
                extent = context['extent']
                width = extent.get('xmax', 0) - extent.get('xmin', 0)
                height = extent.get('ymax', 0) - extent.get('ymin', 0)
                avg_dimension = (width + height) / 2
                params['distance'] = avg_dimension * 0.01  # 1% of view dimension
                
        # Resolve style parameters from natural language descriptions
        if 'cap_style' in params and isinstance(params['cap_style'], str):
            cap_style_str = params['cap_style'].lower()
            params['end_cap_style'] = self.parameter_translations['buffer_cap_style'].get(
                cap_style_str, params.get('end_cap_style', 0)
            )
            
        if 'join_style' in params and isinstance(params['join_style'], str):
            join_style_str = params['join_style'].lower()
            params['join_style'] = self.parameter_translations['buffer_join_style'].get(
                join_style_str, params.get('join_style', 0)
            )
            
        return params
        
    def _resolve_select_params(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Resolve select operation parameters.
        
        Args:
            params: Current parameters
            context: Optional context information
            
        Returns:
            Resolved parameters
        """
        # Convert natural language expressions to SQL-like expressions
        if 'expression' in params and isinstance(params['expression'], str):
            expression = params['expression']
            
            # Replace natural language operators with SQL operators
            replacements = [
                (r'\bis equal to\b', '='),
                (r'\bequals\b', '='),
                (r'\bis\b', '='),
                (r'\bgreater than\b', '>'),
                (r'\bless than\b', '<'),
                (r'\bgreater than or equal to\b', '>='),
                (r'\bless than or equal to\b', '<='),
                (r'\bnot equal to\b', '!='),
                (r'\bdoes not equal\b', '!='),
                (r'\bcontains\b', 'LIKE'),
                (r'\bstarts with\b', 'LIKE'),
                (r'\bends with\b', 'LIKE')
            ]
            
            for pattern, replacement in replacements:
                expression = re.sub(pattern, replacement, expression, flags=re.IGNORECASE)
                
            # Handle LIKE operator patterns
            if ' LIKE ' in expression:
                # Add wildcards for LIKE patterns
                expression = re.sub(r'(\w+)\s+LIKE\s+(\w+)', r'\1 LIKE "%\2%"', expression)
                expression = re.sub(r'(\w+)\s+starts with\s+(\w+)', r'\1 LIKE "\2%"', expression)
                expression = re.sub(r'(\w+)\s+ends with\s+(\w+)', r'\1 LIKE "%\2"', expression)
                
            params['expression'] = expression
            
        return params
        
    def resolve_spatial_parameters(self, spatial_relation: str, params: Dict[str, Any], 
                                  context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Resolve parameters for spatial relationship queries.
        
        Args:
            spatial_relation: Type of spatial relationship (within, contains, etc.)
            params: Current parameters
            context: Optional context information
            
        Returns:
            Resolved parameters for the spatial operation
        """
        resolved_params = params.copy()
        
        if spatial_relation.lower() in ['within', 'inside']:
            # If distance specified, it's a "within distance" query
            if 'distance' in params:
                distance = params['distance']
                resolved_params['operation'] = 'within_distance'
                resolved_params['distance'] = distance
            else:
                # Otherwise it's a simple contains/within
                resolved_params['operation'] = 'within'
                
        elif spatial_relation.lower() in ['contains', 'cover']:
            resolved_params['operation'] = 'contains'
            
        elif spatial_relation.lower() in ['intersects', 'overlaps', 'crosses']:
            resolved_params['operation'] = 'intersects'
            
        elif spatial_relation.lower() in ['near', 'close to', 'nearby']:
            # Default distance if not specified
            if 'distance' not in params:
                # Try to infer from context
                if context and 'scale' in context:
                    scale = context['scale']
                    if scale > 100000:
                        distance = 1000  # 1km for city-level
                    elif scale > 10000:
                        distance = 200   # 200m for neighborhood
                    else:
                        distance = 50    # 50m for local
                else:
                    distance = 100      # Default 100m
                    
                resolved_params['distance'] = distance
                
            resolved_params['operation'] = 'within_distance'
            
        elif spatial_relation.lower() in ['touches', 'adjacent to']:
            resolved_params['operation'] = 'touches'
            
        return resolved_params
        
    def extract_parameters_from_text(self, text: str, operation_type: str) -> Dict[str, Any]:
        """
        Extract operation-specific parameters from natural language text.
        
        Args:
            text: Natural language text
            operation_type: Type of operation
            
        Returns:
            Dictionary of extracted parameters
        """
        params = {}
        
        # Extract distance values with units
        distance_pattern = r'(\d+\.?\d*)\s*(meter|meters|m|kilometer|kilometers|km|feet|foot|ft|mile|miles|mi)'
        distance_matches = re.findall(distance_pattern, text, re.IGNORECASE)
        
        if distance_matches:
            value, unit = distance_matches[0]
            distance = float(value)
            
            # Convert to meters
            if unit.lower() in ['kilometer', 'kilometers', 'km']:
                distance *= 1000
            elif unit.lower() in ['feet', 'foot', 'ft']:
                distance *= 0.3048
            elif unit.lower() in ['mile', 'miles', 'mi']:
                distance *= 1609.34
                
            params['distance'] = distance
            params['unit'] = 'meters'  # Standardize to meters
            
        # Extract buffer style parameters
        if operation_type == 'buffer':
            # Look for cap style
            cap_pattern = r'(?:with|using)\s+(\w+)\s+caps?'
            cap_match = re.search(cap_pattern, text, re.IGNORECASE)
            if cap_match:
                params['cap_style'] = cap_match.group(1).lower()
                
            # Look for join style
            join_pattern = r'(?:with|using)\s+(\w+)\s+joins?'
            join_match = re.search(join_pattern, text, re.IGNORECASE)
            if join_match:
                params['join_style'] = join_match.group(1).lower()
                
            # Look for segments
            segments_pattern = r'(\d+)\s+segments'
            segments_match = re.search(segments_pattern, text, re.IGNORECASE)
            if segments_match:
                params['segments'] = int(segments_match.group(1))
                
            # Look for dissolve flag
            if re.search(r'\bdissolve\b', text, re.IGNORECASE):
                params['dissolve'] = True
                
        return params