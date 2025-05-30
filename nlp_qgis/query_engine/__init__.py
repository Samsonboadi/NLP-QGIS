# query_engine/__init__.py
from .query_parser import NLPQueryParser
from .parameter_resolver import ParameterResolver
from .query_optimizer import QueryOptimizer

class QueryEngine:
    """Main query translation engine that integrates all query components."""
    
    def __init__(self, nlp_engine=None, project=None):
        """
        Initialize the query engine.
        
        Args:
            nlp_engine: Optional NLP engine instance
            project: Optional QGIS project instance
        """
        self.parser = NLPQueryParser(nlp_engine)
        self.resolver = ParameterResolver()
        self.optimizer = QueryOptimizer(project)
        
    def set_nlp_engine(self, nlp_engine):
        """
        Set the NLP engine instance.
        
        Args:
            nlp_engine: NLP engine instance
        """
        self.parser.set_nlp_engine(nlp_engine)
        
    def set_project(self, project):
        """
        Set the QGIS project instance.
        
        Args:
            project: QGIS project instance
        """
        self.optimizer.set_project(project)
        
    def process_query(self, query_text: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Process a natural language query into an optimized GIS operation.
        
        Args:
            query_text: Natural language query
            context: Optional context information
            
        Returns:
            Processed query dictionary
        """
        # Step 1: Parse the query
        parsed_query = self.parser.parse_query(query_text, context)
        
        # Step 2: Validate the parsed query
        issues = self.parser.validate_query(parsed_query)
        
        # If there are severe issues, add to result but continue processing
        if issues:
            parsed_query['validation_issues'] = issues
            
        # Step 3: Resolve parameters
        operation = parsed_query.get('operation')
        if operation and operation != 'unknown':
            parameters = parsed_query.get('parameters', {})
            resolved_parameters = self.resolver.resolve_parameters(operation, parameters, context)
            parsed_query['parameters'] = resolved_parameters
            
        # Step 4: Optimize the query
        optimized_query = self.optimizer.optimize_query(parsed_query)
        
        # Step 5: Add warnings for potentially expensive operations
        final_query = self.optimizer.add_warnings_for_expensive_queries(optimized_query)
        
        # Add the original query for reference
        final_query['original_text'] = query_text
        
        return final_query
        
    def generate_qgis_script(self, processed_query: Dict[str, Any]) -> str:
        """
        Generate a QGIS Python script from a processed query.
        
        Args:
            processed_query: Processed query dictionary
            
        Returns:
            QGIS Python script as string
        """
        return self.parser.format_as_qgis_command(processed_query)
        
    def suggest_completions(self, partial_query: Dict[str, Any]) -> List[str]:
        """
        Suggest ways to complete a partial query.
        
        Args:
            partial_query: Partially processed query
            
        Returns:
            List of completion suggestions
        """
        return self.parser.suggest_query_completion(partial_query)
        
    def batch_process_queries(self, queries: List[str], context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Process multiple queries with optimized sequencing.
        
        Args:
            queries: List of natural language queries
            context: Optional context information
            
        Returns:
            List of processed query dictionaries
        """
        # Process each query individually
        processed_queries = [self.process_query(q, context) for q in queries]
        
        # Optimize sequence
        optimized_sequence = self.optimizer.optimize_query_sequence(processed_queries)
        
        return optimized_sequence# query_engine/query_parser.py
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