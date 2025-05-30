# query_engine/query_parser.py
import re
import json
from typing import Dict, List, Any, Optional, Tuple, Union
import logging

class NLPQueryParser:
    """
    NLP-driven query parser that converts natural language input into GIS scripts.
    
    This parser handles the conversion of ambiguous natural language queries
    into explicit, structured GIS operations with complete parameters.
    """
    
    def __init__(self, nlp_engine=None):
        """
        Initialize the query parser.
        
        Args:
            nlp_engine: Optional NLP engine instance
        """
        self.nlp_engine = nlp_engine
        
        # Set up logger
        self.logger = logging.getLogger('NLPGISPlugin.QueryParser')
        
        # Command patterns for simple pattern matching
        self.command_patterns = {
            'buffer': [
                r'(?:create|make)?\s*(?:a|the)?\s*buffer\s+(?:of|around|for)?\s*([\w\s]+)\s+(?:by|of|with)?\s*([\d\.]+)\s*(meter|meters|m|kilometer|kilometers|km|feet|foot|ft|mile|miles|mi)',
                r'buffer\s+(?:the|a)?\s*([\w\s]+)\s+(?:by|with)?\s*([\d\.]+)\s*(meter|meters|m|kilometer|kilometers|km|feet|foot|ft|mile|miles|mi)'
            ],
            'clip': [
                r'clip\s+(?:the|a)?\s*([\w\s]+)\s+(?:with|using|by)\s+(?:the|a)?\s*([\w\s]+)',
                r'extract\s+(?:the|a)?\s*([\w\s]+)\s+from\s+(?:the|a)?\s*([\w\s]+)'
            ],
            'intersection': [
                r'(?:find|get|compute|calculate)\s+(?:the)?\s*intersection\s+(?:of|between)?\s+(?:the|a)?\s*([\w\s]+)\s+(?:and|with)\s+(?:the|a)?\s*([\w\s]+)',
                r'intersect\s+(?:the|a)?\s*([\w\s]+)\s+(?:with|and)\s+(?:the|a)?\s*([\w\s]+)'
            ],
            'select': [
                r'select\s+(?:from|in)?\s*(?:the|a)?\s*([\w\s]+)\s+where\s+(.*)',
                r'find\s+(?:all)?\s*([\w\s]+)\s+where\s+(.*)',
                r'show\s+(?:me)?\s+(?:all)?\s*([\w\s]+)\s+(?:that|which)\s+(.*)'
            ]
        }
        
    def set_nlp_engine(self, nlp_engine):
        """
        Set the NLP engine instance.
        
        Args:
            nlp_engine: NLP engine instance
        """
        self.nlp_engine = nlp_engine
        
    def parse_query(self, query_text: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Parse a natural language query into a structured GIS operation.
        
        Args:
            query_text: Natural language query
            context: Optional context information (active layers, etc.)
            
        Returns:
            Dictionary with parsed operation details
        """
        # Use NLP engine if available
        if self.nlp_engine:
            # Get active layers from context
            active_layers = None
            current_crs = None
            if context:
                active_layers = context.get('active_layers', [])
                active_layers = [layer.get('name') for layer in active_layers] if isinstance(active_layers[0], dict) else active_layers
                current_crs = context.get('crs')
                
            # Process with NLP engine
            nlp_result = self.nlp_engine.process_command(
                query_text,
                active_layers=active_layers,
                current_crs=current_crs
            )
            
            # Enhance the result with pattern matching for specific operation types
            enhanced_result = self._enhance_with_pattern_matching(nlp_result, query_text)
            
            # Fill in missing parameters based on context
            complete_result = self._fill_missing_parameters(enhanced_result, context)
            
            return complete_result
            
        else:
            # Fall back to pattern matching only
            return self._parse_with_patterns(query_text, context)
            
    def _parse_with_patterns(self, query_text: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Parse a query using regex pattern matching as fallback.
        
        Args:
            query_text: Natural language query
            context: Optional context information
            
        Returns:
            Dictionary with parsed operation details
        """
        query_text = query_text.lower().strip()
        
        # Check each operation type
        for operation, patterns in self.command_patterns.items():
            for pattern in patterns:
                match = re.search(pattern, query_text, re.IGNORECASE)
                if match:
                    # Different operations have different parameter structures
                    if operation == 'buffer':
                        input_layer = match.group(1).strip()
                        distance = float(match.group(2))
                        unit = match.group(3).lower()
                        
                        # Convert to meters for consistency
                        if unit in ['kilometer', 'kilometers', 'km']:
                            distance *= 1000
                        elif unit in ['feet', 'foot', 'ft']:
                            distance *= 0.3048
                        elif unit in ['mile', 'miles', 'mi']:
                            distance *= 1609.34
                            
                        return {
                            'operation': 'buffer',
                            'input_layer': input_layer,
                            'parameters': {
                                'distance': distance,
                                'unit': 'meters'  # Standardized unit
                            },
                            'confidence': 0.8,
                            'original_text': query_text
                        }
                        
                    elif operation in ['clip', 'intersection']:
                        input_layer = match.group(1).strip()
                        overlay_layer = match.group(2).strip()
                        
                        return {
                            'operation': operation,
                            'input_layer': input_layer,
                            'secondary_layer': overlay_layer,
                            'parameters': {},
                            'confidence': 0.8,
                            'original_text': query_text
                        }
                        
                    elif operation == 'select':
                        input_layer = match.group(1).strip()
                        where_clause = match.group(2).strip()
                        
                        return {
                            'operation': 'select',
                            'input_layer': input_layer,
                            'parameters': {
                                'expression': where_clause
                            },
                            'confidence': 0.7,  # Lower confidence as expressions can be complex
                            'original_text': query_text
                        }
        
        # No pattern matched, return a generic result
        return {
            'operation': 'unknown',
            'input_layer': None,
            'parameters': {},
            'confidence': 0.1,
            'original_text': query_text
        }
        
    def _enhance_with_pattern_matching(self, nlp_result: Dict[str, Any], query_text: str) -> Dict[str, Any]:
        """
        Enhance NLP result with pattern matching for specific parameters.
        
        Args:
            nlp_result: Result from NLP engine
            query_text: Original query text
            
        Returns:
            Enhanced result dictionary
        """
        # If operation is already high confidence, return as is
        if nlp_result.get('confidence', 0) > 0.8:
            return nlp_result
            
        # Operation specific enhancements
        operation = nlp_result.get('operation')
        
        if operation == 'buffer':
            # Look for distance with unit pattern
            distance_pattern = r'(\d+\.?\d*)\s*(meter|meters|m|kilometer|kilometers|km|feet|foot|ft|mile|miles|mi)'
            match = re.search(distance_pattern, query_text, re.IGNORECASE)
            
            if match and 'distance' not in nlp_result.get('parameters', {}):
                distance = float(match.group(1))
                unit = match.group(2).lower()
                
                # Convert to meters for consistency
                if unit in ['kilometer', 'kilometers', 'km']:
                    distance *= 1000
                elif unit in ['feet', 'foot', 'ft']:
                    distance *= 0.3048
                elif unit in ['mile', 'miles', 'mi']:
                    distance *= 1609.34
                    
                # Update parameters
                if 'parameters' not in nlp_result:
                    nlp_result['parameters'] = {}
                    
                nlp_result['parameters']['distance'] = distance
                nlp_result['parameters']['unit'] = 'meters'
                
                # Increase confidence slightly
                nlp_result['confidence'] = min(nlp_result.get('confidence', 0) + 0.1, 1.0)
                
        elif operation in ['clip', 'intersection', 'union']:
            # Look for secondary layer if not already identified
            if not nlp_result.get('secondary_layer'):
                # Pattern like "X with Y" or "X and Y"
                secondary_pattern = r'(?:with|and|using|by|over|against)\s+(?:the|a)?\s*([\w\s]+)'
                match = re.search(secondary_pattern, query_text, re.IGNORECASE)
                
                if match:
                    secondary_layer = match.group(1).strip()
                    nlp_result['secondary_layer'] = secondary_layer
                    
                    # Increase confidence slightly
                    nlp_result['confidence'] = min(nlp_result.get('confidence', 0) + 0.1, 1.0)
                    
        elif operation == 'select':
            # Look for where clause if not already identified
            if 'expression' not in nlp_result.get('parameters', {}):
                # Pattern like "where X = Y" or "that have X > Y"
                where_pattern = r'(?:where|that|which|with)\s+([\w\s]+\s*(?:>|<|=|is|equals|contains|in)\s*[\w\s\.]+)'
                match = re.search(where_pattern, query_text, re.IGNORECASE)
                
                if match:
                    expression = match.group(1).strip()
                    
                    if 'parameters' not in nlp_result:
                        nlp_result['parameters'] = {}
                        
                    nlp_result['parameters']['expression'] = expression
                    
                    # Increase confidence slightly
                    nlp_result['confidence'] = min(nlp_result.get('confidence', 0) + 0.1, 1.0)
                    
        return nlp_result
        
    def _fill_missing_parameters(self, result: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Fill in missing parameters based on context.
        
        Args:
            result: Parsed operation result
            context: Optional context information
            
        Returns:
            Result with filled parameters
        """
        if not context:
            return result
            
        # Make a copy to avoid modifying the original
        filled_result = result.copy()
        
        # Get operation type
        operation = filled_result.get('operation')
        
        # Fill in input layer if missing
        if not filled_result.get('input_layer') and context.get('active_layers'):
            # Use the currently selected layer if available
            selected_layer = context.get('selected_layer')
            if selected_layer:
                filled_result['input_layer'] = selected_layer
                filled_result['parameters']['auto_completed_input'] = True
                
            # Otherwise use the first visible layer
            elif context.get('active_layers'):
                visible_layers = []
                if isinstance(context['active_layers'][0], dict):
                    visible_layers = [layer.get('name') for layer in context['active_layers'] 
                                    if layer.get('visible', True)]
                else:
                    visible_layers = context['active_layers']
                    
                if visible_layers:
                    filled_result['input_layer'] = visible_layers[0]
                    filled_result['parameters']['auto_completed_input'] = True
                    
        # Operation-specific parameter filling
        if operation == 'buffer' and 'distance' not in filled_result.get('parameters', {}):
            # Default buffer distance based on current map scale
            if context.get('scale'):
                scale = context.get('scale')
                # Heuristic: use 1% of the current view extent as default buffer
                if context.get('extent'):
                    extent = context.get('extent')
                    width = extent.get('xmax', 0) - extent.get('xmin', 0)
                    height = extent.get('ymax', 0) - extent.get('ymin', 0)
                    avg_dimension = (width + height) / 2
                    default_distance = avg_dimension * 0.01  # 1% of view size
                    
                    if 'parameters' not in filled_result:
                        filled_result['parameters'] = {}
                        
                    filled_result['parameters']['distance'] = default_distance
                    filled_result['parameters']['unit'] = 'meters'
                    filled_result['parameters']['auto_completed_distance'] = True
                    
        elif operation in ['clip', 'intersection', 'union'] and not filled_result.get('secondary_layer'):
            # Try to suggest a secondary layer
            if context.get('active_layers'):
                # Get all layers except the input layer
                input_layer = filled_result.get('input_layer')
                other_layers = []
                
                if isinstance(context['active_layers'][0], dict):
                    other_layers = [layer.get('name') for layer in context['active_layers'] 
                                    if layer.get('name') != input_layer]
                else:
                    other_layers = [layer for layer in context['active_layers'] if layer != input_layer]
                    
                if other_layers:
                    filled_result['secondary_layer'] = other_layers[0]
                    filled_result['parameters']['auto_completed_secondary'] = True
                    
        return filled_result
        
    def validate_query(self, parsed_query: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Validate a parsed query for completeness and correctness.
        
        Args:
            parsed_query: Parsed query dictionary
            
        Returns:
            List of validation issues (empty if valid)
        """
        issues = []
        
        # Check operation type
        operation = parsed_query.get('operation')
        if not operation or operation == 'unknown':
            issues.append({
                'severity': 'error',
                'message': 'Unknown or missing operation type.'
            })
            return issues  # Can't validate further without operation
            
        # Check input layer
        if not parsed_query.get('input_layer'):
            issues.append({
                'severity': 'error',
                'message': f'No input layer specified for {operation} operation.'
            })
            
        # Operation-specific validation
        if operation == 'buffer':
            # Check distance parameter
            if 'distance' not in parsed_query.get('parameters', {}):
                issues.append({
                    'severity': 'error',
                    'message': 'No buffer distance specified.'
                })
            elif parsed_query['parameters']['distance'] <= 0:
                issues.append({
                    'severity': 'warning',
                    'message': 'Buffer distance must be greater than zero.'
                })
            elif parsed_query['parameters']['distance'] > 10000:
                issues.append({
                    'severity': 'warning',
                    'message': 'Very large buffer distance may cause performance issues.'
                })
                
        elif operation in ['clip', 'intersection', 'union']:
            # Check overlay layer
            if not parsed_query.get('secondary_layer'):
                issues.append({
                    'severity': 'error',
                    'message': f'No overlay layer specified for {operation} operation.'
                })
                
        elif operation == 'select':
            # Check selection criteria
            if 'expression' not in parsed_query.get('parameters', {}) and not parsed_query.get('spatial_relationship'):
                issues.append({
                    'severity': 'error',
                    'message': 'No selection criteria specified.'
                })
                
        # Check confidence
        confidence = parsed_query.get('confidence', 0)
        if confidence < 0.6:
            issues.append({
                'severity': 'warning',
                'message': f'Low confidence in query interpretation ({confidence:.2f}). Please clarify the command.'
            })
            
        return issues
    
    def suggest_query_completion(self, partial_query: Dict[str, Any]) -> List[str]:
        """
        Suggest ways to complete a partial query.
        
        Args:
            partial_query: Partially parsed query
            
        Returns:
            List of completion suggestions
        """
        suggestions = []
        
        # Get operation type
        operation = partial_query.get('operation')
        
        if not operation or operation == 'unknown':
            # Suggest common operations
            suggestions.append("Try specifying an operation like 'buffer', 'clip', 'select', or 'intersection'")
            return suggestions
            
        # Operation-specific suggestions
        if operation == 'buffer':
            if not partial_query.get('input_layer'):
                suggestions.append("Specify which layer to buffer, e.g., 'buffer the roads layer'")
                
            if 'distance' not in partial_query.get('parameters', {}):
                suggestions.append("Specify a buffer distance, e.g., 'buffer by 500 meters'")
                
        elif operation in ['clip', 'intersection', 'union']:
            if not partial_query.get('input_layer'):
                suggestions.append(f"Specify the input layer for {operation}, e.g., '{operation} the roads layer'")
                
            if not partial_query.get('secondary_layer'):
                suggestions.append(f"Specify the overlay layer, e.g., '{operation} with city boundaries'")
                
        elif operation == 'select':
            if not partial_query.get('input_layer'):
                suggestions.append("Specify which layer to select from, e.g., 'select from buildings'")
                
            if 'expression' not in partial_query.get('parameters', {}):
                suggestions.append("Specify selection criteria, e.g., 'where area > 1000' or 'within 500m of rivers'")
                
        return suggestions
        
    def format_as_qgis_command(self, parsed_query: Dict[str, Any]) -> str:
        """
        Format a parsed query as a QGIS processing command.
        
        Args:
            parsed_query: Parsed query dictionary
            
        Returns:
            QGIS command string
        """
        operation = parsed_query.get('operation')
        
        if operation == 'buffer':
            input_layer = parsed_query.get('input_layer', 'input_layer')
            distance = parsed_query.get('parameters', {}).get('distance', 0)
            
            return (
                f"processing.run('native:buffer', "
                f"{{'INPUT': '{input_layer}', "
                f"'DISTANCE': {distance}, "
                f"'SEGMENTS': 5, "
                f"'END_CAP_STYLE': 0, "
                f"'JOIN_STYLE': 0, "
                f"'MITER_LIMIT': 2, "
                f"'DISSOLVE': False, "
                f"'OUTPUT': 'TEMPORARY_OUTPUT'}})"
            )
            
        elif operation == 'clip':
            input_layer = parsed_query.get('input_layer', 'input_layer')
            overlay_layer = parsed_query.get('secondary_layer', 'overlay_layer')
            
            return (
                f"processing.run('native:clip', "
                f"{{'INPUT': '{input_layer}', "
                f"'OVERLAY': '{overlay_layer}', "
                f"'OUTPUT': 'TEMPORARY_OUTPUT'}})"
            )
            
        elif operation == 'intersection':
            input_layer = parsed_query.get('input_layer', 'input_layer')
            overlay_layer = parsed_query.get('secondary_layer', 'overlay_layer')
            
            return (
                f"processing.run('native:intersection', "
                f"{{'INPUT': '{input_layer}', "
                f"'OVERLAY': '{overlay_layer}', "
                f"'INPUT_FIELDS': [], "
                f"'OVERLAY_FIELDS': [], "
                f"'OUTPUT': 'TEMPORARY_OUTPUT'}})"
            )
            
        elif operation == 'select':
            input_layer = parsed_query.get('input_layer', 'input_layer')
            expression = parsed_query.get('parameters', {}).get('expression', '')
            
            # This is simplified - real implementation would parse the expression
            return (
                f"layer = QgsProject.instance().mapLayersByName('{input_layer}')[0]\n"
                f"layer.selectByExpression(\"{expression}\")"
            )
            
        else:
            return f"# Operation '{operation}' not implemented"