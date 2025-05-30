# query_engine/query_optimizer.py
import time
import logging
from typing import Dict, List, Any, Optional, Tuple, Union

class QueryOptimizer:
    """
    Optimizer for GIS queries to improve performance.
    
    This class analyzes and optimizes spatial queries to minimize
    processing time and resource usage, especially for large datasets.
    """
    
    def __init__(self, project=None):
        """
        Initialize the query optimizer.
        
        Args:
            project: Optional QGIS project instance
        """
        self.project = project
        
        # Set up logger
        self.logger = logging.getLogger('NLPGISPlugin.QueryOptimizer')
        
        # Optimization flags
        self.use_spatial_index = True
        self.use_attribute_index = True
        self.limit_features = False
        self.max_features = 10000
        
        # Performance thresholds
        self.large_dataset_threshold = 50000  # features
        self.memory_limit_mb = 512
        self.processing_timeout_seconds = 300
        
    def set_project(self, project):
        """
        Set the QGIS project instance.
        
        Args:
            project: QGIS project instance
        """
        self.project = project
        
    def get_layer_statistics(self, layer_name: str) -> Dict[str, Any]:
        """
        Get statistics for a layer to inform optimization decisions.
        
        Args:
            layer_name: Name of the layer
            
        Returns:
            Dictionary with layer statistics
        """
        if not self.project:
            return {}
            
        # Find the layer by name
        layer = None
        for lyr in self.project.mapLayers().values():
            if lyr.name() == layer_name:
                layer = lyr
                break
                
        if not layer:
            self.logger.warning(f"Layer '{layer_name}' not found")
            return {}
            
        # Collect statistics
        stats = {
            'feature_count': 0,
            'has_spatial_index': False,
            'geometry_type': None,
            'field_count': 0,
            'estimated_size_mb': 0,
            'extent_area': 0,
            'is_large_dataset': False
        }
        
        try:
            # Get feature count
            feature_count = layer.featureCount()
            stats['feature_count'] = feature_count
            stats['is_large_dataset'] = feature_count > self.large_dataset_threshold
            
            # Check if layer has spatial index
            if hasattr(layer, 'hasSpatialIndex'):
                stats['has_spatial_index'] = layer.hasSpatialIndex()
                
            # Get geometry type
            if hasattr(layer, 'geometryType'):
                stats['geometry_type'] = layer.geometryType()
                
            # Count fields
            if hasattr(layer, 'fields'):
                stats['field_count'] = len(layer.fields())
                
            # Calculate extent area
            if hasattr(layer, 'extent'):
                extent = layer.extent()
                stats['extent_area'] = extent.width() * extent.height()
                
            # Estimate size (very rough heuristic)
            avg_feature_size_bytes = 100  # Base size
            if stats['field_count'] > 0:
                avg_feature_size_bytes += stats['field_count'] * 20
                
            if stats['geometry_type'] == 2:  # Polygon
                avg_feature_size_bytes += 500
            elif stats['geometry_type'] == 1:  # Line
                avg_feature_size_bytes += 200
                
            stats['estimated_size_mb'] = (feature_count * avg_feature_size_bytes) / (1024 * 1024)
            
        except Exception as e:
            self.logger.error(f"Error calculating layer statistics: {str(e)}")
        
        return stats
        
    def optimize_query(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """
        Optimize a GIS query for better performance.
        
        Args:
            query: Query dictionary
            
        Returns:
            Optimized query dictionary
        """
        # Make a copy to avoid modifying the original
        optimized = query.copy()
        
        # Get operation type
        operation = optimized.get('operation')
        
        # Get layer statistics
        input_layer = optimized.get('input_layer')
        input_stats = self.get_layer_statistics(input_layer) if input_layer else {}
        
        secondary_layer = optimized.get('secondary_layer')
        secondary_stats = self.get_layer_statistics(secondary_layer) if secondary_layer else {}
        
        # Apply operation-specific optimizations
        if operation == 'buffer':
            optimized = self._optimize_buffer_query(optimized, input_stats)
        elif operation in ['clip', 'intersection', 'union']:
            optimized = self._optimize_overlay_query(optimized, input_stats, secondary_stats)
        elif operation == 'select':
            optimized = self._optimize_select_query(optimized, input_stats)
            
        # Add general optimization flags
        if 'optimizations' not in optimized:
            optimized['optimizations'] = {}
            
        optimized['optimizations']['use_spatial_index'] = (
            self.use_spatial_index and 
            input_stats.get('has_spatial_index', False)
        )
        
        # Check if we need to limit features due to large datasets
        large_dataset = (
            input_stats.get('feature_count', 0) > self.max_features or
            input_stats.get('estimated_size_mb', 0) > self.memory_limit_mb
        )
        
        if large_dataset and self.limit_features:
            optimized['optimizations']['limit_features'] = True
            optimized['optimizations']['max_features'] = self.max_features
            optimized['optimizations']['reason'] = 'Large dataset detected'
            
        # Add processing hints
        optimized['optimizations']['estimated_processing_time'] = self._estimate_processing_time(
            operation, input_stats, secondary_stats
        )
        
        return optimized
        
    def _optimize_buffer_query(self, query: Dict[str, Any], layer_stats: Dict[str, Any]) -> Dict[str, Any]:
        """
        Optimize a buffer query.
        
        Args:
            query: Buffer query
            layer_stats: Statistics for the layer
            
        Returns:
            Optimized query
        """
        optimized = query.copy()
        params = optimized.get('parameters', {}).copy()
        
        # For large datasets, adjust segmentation
        if layer_stats.get('feature_count', 0) > 10000:
            # Reduce segments for better performance
            if 'segments' not in params or params['segments'] > 5:
                params['segments'] = 5
                
            # Recommend dissolve=False for large datasets
            if params.get('dissolve', False):
                params['dissolve'] = False
                
            # Add optimization notes
            if 'optimizations' not in optimized:
                optimized['optimizations'] = {}
                
            optimized['optimizations']['reduced_segments'] = True
            optimized['optimizations']['disable_dissolve'] = True
            optimized['optimizations']['reason'] = 'Large dataset optimization'
            
        # For very small buffers, we can reduce segments further
        distance = params.get('distance', 0)
        if distance < 10:  # Less than 10 meters
            params['segments'] = min(params.get('segments', 8), 4)
            if 'optimizations' not in optimized:
                optimized['optimizations'] = {}
            optimized['optimizations']['reduced_segments_small_buffer'] = True
            
        # Update parameters
        optimized['parameters'] = params
        
        return optimized
        
    def _optimize_overlay_query(self, query: Dict[str, Any], input_stats: Dict[str, Any], 
                              overlay_stats: Dict[str, Any]) -> Dict[str, Any]:
        """
        Optimize an overlay query (clip, intersection, union).
        
        Args:
            query: Overlay query
            input_stats: Statistics for input layer
            overlay_stats: Statistics for overlay layer
            
        Returns:
            Optimized query
        """
        optimized = query.copy()
        operation = optimized.get('operation')
        
        # Optimize based on relative sizes of input and overlay
        input_count = input_stats.get('feature_count', 0)
        overlay_count = overlay_stats.get('feature_count', 0)
        
        # Initialize optimizations dict
        if 'optimizations' not in optimized:
            optimized['optimizations'] = {}
        
        # For union operations with large datasets
        if operation == 'union' and (input_count > 5000 or overlay_count > 5000):
            # Suggest alternative algorithm for large unions
            optimized['optimizations']['algorithm'] = 'native:union'
            optimized['optimizations']['memory_efficient'] = True
            optimized['optimizations']['reason'] = 'Large dataset union optimization'
            
        # For intersection with very different sized inputs
        if operation == 'intersection' and min(input_count, overlay_count) > 0:
            ratio = max(input_count, overlay_count) / min(input_count, overlay_count)
            
            if ratio > 10:  # Big difference in sizes
                # Suggest processing smaller layer first
                if input_count > overlay_count:
                    optimized['optimizations']['swap_inputs'] = True
                    optimized['optimizations']['reason'] = 'Size difference optimization'
                    
        # For clip operations, check if overlay is much larger than input
        if operation == 'clip':
            if overlay_count > input_count * 5:
                optimized['optimizations']['spatial_index_critical'] = True
                optimized['optimizations']['reason'] = 'Large overlay layer optimization'
                
        # Memory usage estimation
        total_features = input_count + overlay_count
        if total_features > 100000:
            optimized['optimizations']['high_memory_operation'] = True
            optimized['optimizations']['suggested_batch_size'] = 10000
            
        return optimized
        
    def _optimize_select_query(self, query: Dict[str, Any], layer_stats: Dict[str, Any]) -> Dict[str, Any]:
        """
        Optimize a select query.
        
        Args:
            query: Select query
            layer_stats: Statistics for the layer
            
        Returns:
            Optimized query
        """
        optimized = query.copy()
        params = optimized.get('parameters', {}).copy()
        
        # Initialize optimizations dict
        if 'optimizations' not in optimized:
            optimized['optimizations'] = {}
            
        # For large datasets, suggest using spatial index
        if layer_stats.get('feature_count', 0) > 10000:
            optimized['optimizations']['use_spatial_index'] = True
            
            # If expression involves geometry, suggest spatial filtering first
            expression = params.get('expression', '')
            if any(keyword in expression.lower() for keyword in ['intersects', 'contains', 'within', 'distance']):
                optimized['optimizations']['spatial_first'] = True
                optimized['optimizations']['reason'] = 'Spatial query on large dataset'
                
        # Analyze expression complexity
        expression = params.get('expression', '')
        if expression:
            # Count operators and functions
            operator_count = sum(expression.count(op) for op in ['AND', 'OR', '>', '<', '=', 'LIKE'])
            if operator_count > 5:
                optimized['optimizations']['complex_expression'] = True
                optimized['optimizations']['reason'] = 'Complex expression detected'
                
        return optimized
        
    def _estimate_processing_time(self, operation: str, input_stats: Dict[str, Any], 
                                secondary_stats: Dict[str, Any] = None) -> str:
        """
        Estimate processing time for an operation.
        
        Args:
            operation: Operation type
            input_stats: Input layer statistics
            secondary_stats: Secondary layer statistics (if applicable)
            
        Returns:
            Estimated processing time as string
        """
        input_count = input_stats.get('feature_count', 0)
        secondary_count = secondary_stats.get('feature_count', 0) if secondary_stats else 0
        
        # Simple heuristic based on feature counts and operation type
        if operation == 'buffer':
            if input_count < 1000:
                return "< 5 seconds"
            elif input_count < 10000:
                return "5-30 seconds"
            else:
                return "30+ seconds"
                
        elif operation in ['clip', 'intersection']:
            total_complexity = input_count * (secondary_count / 1000 + 1)
            if total_complexity < 10000:
                return "< 10 seconds"
            elif total_complexity < 100000:
                return "10-60 seconds"
            else:
                return "1+ minutes"
                
        elif operation == 'select':
            if input_count < 5000:
                return "< 2 seconds"
            elif input_count < 50000:
                return "2-10 seconds"
            else:
                return "10+ seconds"
                
        else:
            return "Unknown"
            
    def optimize_query_sequence(self, queries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Optimize a sequence of queries for better overall performance.
        
        Args:
            queries: List of query dictionaries
            
        Returns:
            Optimized sequence of queries
        """
        if not queries:
            return queries
            
        optimized_sequence = []
        
        # Group queries by operation type for potential batching
        operation_groups = {}
        for i, query in enumerate(queries):
            operation = query.get('operation', 'unknown')
            if operation not in operation_groups:
                operation_groups[operation] = []
            operation_groups[operation].append((i, query))
            
        # Reorder for optimal execution
        # 1. Selection operations first (reduce dataset size)
        # 2. Simple geometric operations
        # 3. Complex overlay operations last
        
        operation_priority = {
            'select': 1,
            'buffer': 2,
            'clip': 3,
            'intersection': 4,
            'union': 5
        }
        
        # Sort operations by priority
        sorted_operations = sorted(operation_groups.keys(), 
                                 key=lambda x: operation_priority.get(x, 99))
        
        # Rebuild sequence
        for operation in sorted_operations:
            for original_index, query in operation_groups[operation]:
                optimized_query = self.optimize_query(query)
                optimized_query['original_sequence_index'] = original_index
                optimized_sequence.append(optimized_query)
                
        return optimized_sequence
        
    def add_warnings_for_expensive_queries(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add warnings for potentially expensive operations.
        
        Args:
            query: Query dictionary
            
        Returns:
            Query with warnings added
        """
        warned_query = query.copy()
        
        # Initialize warnings list
        if 'warnings' not in warned_query:
            warned_query['warnings'] = []
            
        operation = query.get('operation')
        input_layer = query.get('input_layer')
        
        # Get layer statistics
        if input_layer:
            stats = self.get_layer_statistics(input_layer)
            
            # Warning for large datasets
            if stats.get('feature_count', 0) > self.large_dataset_threshold:
                warned_query['warnings'].append({
                    'type': 'performance',
                    'message': f"Large dataset detected ({stats['feature_count']} features). "
                             f"Operation may take several minutes.",
                    'severity': 'warning'
                })
                
            # Warning for very large buffers
            if operation == 'buffer':
                distance = query.get('parameters', {}).get('distance', 0)
                extent_area = stats.get('extent_area', 0)
                
                if distance > 0 and extent_area > 0:
                    buffer_area_ratio = (3.14159 * distance * distance) / extent_area
                    if buffer_area_ratio > 0.5:  # Buffer area > 50% of layer extent
                        warned_query['warnings'].append({
                            'type': 'geometry',
                            'message': "Buffer distance is very large relative to layer extent. "
                                     "This may create overlapping geometries.",
                            'severity': 'warning'
                        })
                        
            # Warning for memory-intensive operations
            estimated_memory = stats.get('estimated_size_mb', 0)
            if operation in ['union', 'intersection'] and estimated_memory > self.memory_limit_mb:
                warned_query['warnings'].append({
                    'type': 'memory',
                    'message': f"Operation may require significant memory ({estimated_memory:.1f} MB). "
                             f"Consider processing in smaller batches.",
                    'severity': 'warning'
                })
                
        return warned_query
        
    def get_optimization_suggestions(self, query: Dict[str, Any]) -> List[str]:
        """
        Get optimization suggestions for a query.
        
        Args:
            query: Query dictionary
            
        Returns:
            List of optimization suggestions
        """
        suggestions = []
        
        operation = query.get('operation')
        input_layer = query.get('input_layer')
        
        if input_layer:
            stats = self.get_layer_statistics(input_layer)
            
            # Suggest spatial indexing
            if not stats.get('has_spatial_index', False) and stats.get('feature_count', 0) > 1000:
                suggestions.append("Consider creating a spatial index on the input layer for better performance")
                
            # Suggest data preprocessing
            if stats.get('feature_count', 0) > self.large_dataset_threshold:
                suggestions.append("For large datasets, consider filtering data first to reduce processing time")
                
            # Operation-specific suggestions
            if operation == 'buffer':
                distance = query.get('parameters', {}).get('distance', 0)
                if distance > 1000:  # > 1km
                    suggestions.append("Large buffer distances may benefit from lower segment counts")
                    
            elif operation in ['clip', 'intersection', 'union']:
                secondary_layer = query.get('secondary_layer')
                if secondary_layer:
                    secondary_stats = self.get_layer_statistics(secondary_layer)
                    if (stats.get('feature_count', 0) > 10000 and 
                        secondary_stats.get('feature_count', 0) > 10000):
                        suggestions.append("Both layers are large - consider spatial filtering before overlay operations")
                        
        return suggestions