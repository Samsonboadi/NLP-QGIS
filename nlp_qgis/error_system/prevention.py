# error_system/prevention.py
import re
import time
import logging
from typing import Dict, List, Any, Optional, Tuple, Set, Callable

class ProactiveErrorPrevention:
    """
    Proactive error prevention system that identifies risky operations.
    
    This system analyzes operations before execution to identify those that
    are likely to cause errors based on past error patterns, input validation,
    and resource constraints.
    """
    
    def __init__(self, error_logger, transaction_logger):
        """
        Initialize the error prevention system.
        
        Args:
            error_logger: Reference to the structured error logger
            transaction_logger: Reference to the transaction logger
        """
        self.error_logger = error_logger
        self.transaction_logger = transaction_logger
        
        # Set up logger
        self.logger = logging.getLogger('NLPGISPlugin.ErrorPrevention')
        
        # Risk detection rules
        self.risk_rules = []
        
        # Initialize with default rules
        self._initialize_default_rules()
        
    def _initialize_default_rules(self):
        """Initialize default risk detection rules."""
        # Rule for large buffer distances
        self.add_risk_rule(
            'buffer_distance_too_large',
            lambda op, params: op == 'buffer' and params.get('distance', 0) > 10000,
            'Warning: Buffer distance is very large (>10km), which may cause performance issues or memory errors.',
            'buffer'
        )
        
        # Rule for complex geometries
        self.add_risk_rule(
            'complex_geometry',
            lambda op, params: 'input_layer' in params and 
                              params.get('input_layer_feature_count', 0) > 10000,
            'Warning: Operation on a layer with more than 10,000 features may be slow or cause memory issues.',
            ['clip', 'intersection', 'union', 'buffer']
        )
        
        # Rule for missing parameters
        self.add_risk_rule(
            'missing_required_parameters',
            self._check_missing_required_parameters,
            'Warning: Operation is missing required parameters.',
            '*'  # Apply to all operations
        )
        
        # Rule for operations that frequently cause errors
        self.add_risk_rule(
            'error_prone_operation',
            self._check_if_error_prone_operation,
            'Warning: This operation has frequently caused errors in the past.',
            '*'  # Apply to all operations
        )
        
    def add_risk_rule(self, rule_id: str, detection_func: Callable, 
                     message: str, applicable_ops: str or List[str]):
        """
        Add a risk detection rule.
        
        Args:
            rule_id: Unique identifier for the rule
            detection_func: Function to detect the risk condition
                           Should accept (operation_type, parameters) and return boolean
            message: Message to display when risk is detected
            applicable_ops: Operation type(s) this rule applies to
                           '*' means all operations
        """
        self.risk_rules.append({
            'rule_id': rule_id,
            'detection_func': detection_func,
            'message': message,
            'applicable_ops': applicable_ops
        })
        
    def _check_missing_required_parameters(self, operation_type: str, parameters: Dict[str, Any]) -> bool:
        """
        Check if required parameters are missing for an operation.
        
        Args:
            operation_type: Type of operation
            parameters: Operation parameters
            
        Returns:
            True if required parameters are missing, False otherwise
        """
        # Define required parameters for different operation types
        required_params = {
            'buffer': ['input_layer', 'distance'],
            'clip': ['input_layer', 'overlay_layer'],
            'intersection': ['input_layer', 'overlay_layer'],
            'select': ['input_layer', 'expression'],
            'union': ['input_layer', 'overlay_layer']
        }
        
        # Check if this operation has defined required parameters
        if operation_type in required_params:
            # Check each required parameter
            for param in required_params[operation_type]:
                if param not in parameters:
                    return True
        
        return False
        
    def _check_if_error_prone_operation(self, operation_type: str, parameters: Dict[str, Any]) -> bool:
        """
        Check if an operation is prone to errors based on historical data.
        
        Args:
            operation_type: Type of operation
            parameters: Operation parameters
            
        Returns:
            True if the operation is error-prone, False otherwise
        """
        # This would normally analyze error statistics from the error logger
        # For now, a simplified implementation
        
        # Get error statistics
        stats = self.error_logger.get_error_statistics()
        
        # Check if this operation type appears frequently in errors
        for error_type, error_stats in stats.get('error_types', {}).items():
            if operation_type == error_stats.get('most_common_preceding_operation'):
                # This operation often precedes errors
                return True
                
        return False
        
    def check_operation_risks(self, operation_type: str, parameters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Check an operation for potential risks before execution.
        
        Args:
            operation_type: Type of operation to check
            parameters: Operation parameters
            
        Returns:
            List of detected risks (empty if none detected)
        """
        detected_risks = []
        
        # Apply each applicable rule
        for rule in self.risk_rules:
            applicable_ops = rule['applicable_ops']
            
            # Check if rule applies to this operation
            if applicable_ops == '*' or operation_type in (applicable_ops if isinstance(applicable_ops, list) else [applicable_ops]):
                # Apply the detection function
                if rule['detection_func'](operation_type, parameters):
                    # Risk detected
                    detected_risks.append({
                        'rule_id': rule['rule_id'],
                        'message': rule['message'],
                        'severity': 'warning'  # Could be dynamic in a real implementation
                    })
                    
        return detected_risks
        
    def validate_nlp_command(self, nlp_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Validate an NLP command result before execution.
        
        Args:
            nlp_result: Result from NLP engine
            
        Returns:
            List of validation issues (empty if command is valid)
        """
        validation_issues = []
        
        # Check if operation type is recognized
        operation = nlp_result.get('operation')
        if not operation or operation == 'unknown':
            validation_issues.append({
                'type': 'unrecognized_operation',
                'message': 'The operation type was not recognized.',
                'severity': 'error'
            })
            return validation_issues
            
        # Check confidence level
        confidence = nlp_result.get('confidence', 0)
        if confidence < 0.6:
            validation_issues.append({
                'type': 'low_confidence',
                'message': f'Low confidence in command interpretation ({confidence:.2f}).',
                'severity': 'warning'
            })
            
        # Check for input layer
        input_layer = nlp_result.get('input_layer')
        if not input_layer:
            validation_issues.append({
                'type': 'missing_input_layer',
                'message': 'No input layer was identified in the command.',
                'severity': 'error'
            })
            
        # Check operation-specific parameters
        parameters = nlp_result.get('parameters', {})
        
        if operation == 'buffer' and 'distance' not in parameters:
            validation_issues.append({
                'type': 'missing_parameter',
                'message': 'No buffer distance specified.',
                'severity': 'error'
            })
            
        elif operation in ['clip', 'intersection', 'union'] and not nlp_result.get('secondary_layer'):
            validation_issues.append({
                'type': 'missing_secondary_layer',
                'message': f'No overlay layer specified for {operation} operation.',
                'severity': 'error'
            })
            
        elif operation == 'select' and not nlp_result.get('spatial_relationship') and not parameters.get('expression'):
            validation_issues.append({
                'type': 'missing_selection_criteria',
                'message': 'No selection criteria specified.',
                'severity': 'warning'
            })
            
        # Check for risks using the risk detection rules
        risk_params = {
            'input_layer': input_layer,
            'secondary_layer': nlp_result.get('secondary_layer'),
            **parameters
        }
        
        risks = self.check_operation_risks(operation, risk_params)
        validation_issues.extend(risks)
        
        return validation_issues
        
    def should_prevent_execution(self, issues: List[Dict[str, Any]]) -> bool:
        """
        Determine if an operation should be prevented based on validation issues.
        
        Args:
            issues: List of validation issues
            
        Returns:
            True if execution should be prevented, False otherwise
        """
        # Prevent execution if there are any errors (not just warnings)
        return any(issue['severity'] == 'error' for issue in issues)
        
    def get_alternative_suggestions(self, nlp_result: Dict[str, Any], issues: List[Dict[str, Any]]) -> List[str]:
        """
        Get suggestions for alternative commands based on validation issues.
        
        Args:
            nlp_result: Original NLP result
            issues: Validation issues
            
        Returns:
            List of suggested alternative commands
        """
        suggestions = []
        
        operation = nlp_result.get('operation', 'unknown')
        
        # Check each issue type and provide specific suggestions
        for issue in issues:
            issue_type = issue['type']
            
            if issue_type == 'missing_input_layer':
                # Suggest specifying a layer
                layers = self._get_available_layers()
                if layers:
                    layer_list = ", ".join(layers[:3])
                    suggestions.append(f"Try specifying a layer name, such as: '{operation} {layer_list}'")
                else:
                    suggestions.append("Try specifying a layer name for the operation")
                    
            elif issue_type == 'missing_secondary_layer' and operation in ['clip', 'intersection', 'union']:
                # Suggest adding a secondary layer
                layers = self._get_available_layers()
                if layers:
                    layer_list = ", ".join(layers[:3])
                    suggestions.append(f"Try specifying which layer to use with {operation}, such as: '{operation} [input] with {layer_list}'")
                else:
                    suggestions.append(f"Try specifying both input and overlay layers for the {operation} operation")
                    
            elif issue_type == 'missing_parameter' and operation == 'buffer':
                # Suggest adding a distance
                suggestions.append("Try specifying a buffer distance, such as: 'buffer by 100 meters'")
                
            elif issue_type == 'buffer_distance_too_large':
                # Suggest a smaller buffer distance
                current_distance = nlp_result.get('parameters', {}).get('distance', 0)
                suggestions.append(f"Try using a smaller buffer distance (current: {current_distance}), such as: 'buffer by 1000 meters'")
                
        return suggestions
        
    def _get_available_layers(self) -> List[str]:
        """
        Get a list of available layers in the project.
        
        Returns:
            List of layer names
        """
        # This would normally query QGIS for available layers
        # For now, return a placeholder
        return ["roads", "buildings", "rivers", "land_use"]
        
    def cleanup(self):
        """Perform cleanup when plugin is unloaded."""
        # Clear risk rules
        self.risk_rules.clear()