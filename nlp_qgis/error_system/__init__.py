# error_system/__init__.py
from .event_interceptor import EventInterceptor
from .error_logger import StructuredErrorLogger
from .transaction_log import TransactionLogger
from .prevention import ProactiveErrorPrevention

class ErrorSystem:
    """Main error handling system that integrates all error components."""
    
    def __init__(self, iface, log_dir=None):
        """
        Initialize the error system.
        
        Args:
            iface: QGIS interface
            log_dir: Directory for logs and transaction data
        """
        self.iface = iface
        
        # Initialize components
        self.error_logger = StructuredErrorLogger(log_dir)
        self.transaction_logger = TransactionLogger(log_dir)
        self.event_interceptor = EventInterceptor(iface)
        self.prevention = ProactiveErrorPrevention(self.error_logger, self.transaction_logger)
        
        # Connect event signals
        self._connect_signals()
        
    def _connect_signals(self):
        """Connect internal signals between components."""
        # Connect event interceptor to error logger
        self.event_interceptor.potential_error_detected.connect(self._on_potential_error)
        
    def _on_potential_error(self, error_type, event_data):
        """Handle potential error detected by event interceptor."""
        # Log the potential error
        self.error_logger.log_error(
            error_type,
            event_data.get('description', 'Potential error detected'),
            context={
                'event_type': event_data.get('event_type'),
                'event_data': event_data.get('event_data'),
                'risk_level': event_data.get('risk_level'),
                'is_potential': True
            }
        )
        
    def log_operation(self, operation_type, parameters, result=None, save_state=False, state_data=None):
        """
        Log an operation in the transaction log.
        
        Args:
            operation_type: Type of operation
            parameters: Operation parameters
            result: Optional result of the operation
            save_state: Whether to save a state snapshot
            state_data: Optional state data to save
            
        Returns:
            Transaction ID
        """
        # Check for risks before logging
        risks = self.prevention.check_operation_risks(operation_type, parameters)
        
        # Log the operation
        tx_id = self.transaction_logger.log_operation(
            operation_type,
            parameters,
            result,
            save_state,
            state_data
        )
        
        # Log as action in error logger for correlation
        self.error_logger.log_action(
            operation_type,
            {
                'parameters': parameters,
                'transaction_id': tx_id,
                'risks_detected': risks
            }
        )
        
        return tx_id
        
    def log_error(self, error_type, error_message, error_traceback=None, context=None):
        """
        Log an error with the error logger.
        
        Args:
            error_type: Type of error
            error_message: Error message
            error_traceback: Optional traceback
            context: Optional context dictionary
        """
        # Add recent transactions to context if not provided
        if context is None:
            context = {}
            
        if 'recent_transactions' not in context:
            recent_ops = self.transaction_logger.get_recent_operations(5)
            context['recent_transactions'] = recent_ops
            
        # Log the error
        self.error_logger.log_error(
            error_type,
            error_message,
            error_traceback,
            context
        )
        
    def validate_nlp_command(self, nlp_result):
        """
        Validate an NLP command before execution.
        
        Args:
            nlp_result: Result from NLP engine
            
        Returns:
            Tuple of (is_valid, issues, suggestions)
        """
        # Validate using prevention system
        issues = self.prevention.validate_nlp_command(nlp_result)
        
        # Get suggestions if there are issues
        suggestions = []
        if issues:
            suggestions = self.prevention.get_alternative_suggestions(nlp_result, issues)
            
        # Check if execution should be prevented
        should_prevent = self.prevention.should_prevent_execution(issues)
        
        return (not should_prevent, issues, suggestions)
        
    def capture_state(self, state_provider_func):
        """
        Capture the current state using a provided function.
        
        Args:
            state_provider_func: Function that returns the current state
            
        Returns:
            Transaction ID for the state snapshot
        """
        try:
            # Get state data
            state_data = state_provider_func()
            
            # Log with state
            return self.transaction_logger.log_operation(
                'state_snapshot',
                {},
                None,
                True,
                state_data
            )
        except Exception as e:
            self.log_error(
                'state_capture_error',
                f"Failed to capture state: {str(e)}",
                traceback.format_exc()
            )
            return None
            
    def rollback_to_last_state(self):
        """
        Roll back to the last known good state.
        
        Returns:
            Tuple of (success, state_data or error_message)
        """
        try:
            # Get latest state
            latest_state = self.transaction_logger.get_latest_state_snapshot()
            
            if not latest_state:
                return (False, "No state snapshots available for rollback")
                
            tx_id, state_data = latest_state
            
            # Log the rollback
            self.log_operation(
                'rollback',
                {'target_transaction': tx_id},
                None,
                False,
                None
            )
            
            return (True, state_data)
            
        except Exception as e:
            self.log_error(
                'rollback_error',
                f"Failed to roll back: {str(e)}",
                traceback.format_exc()
            )
            return (False, f"Error during rollback: {str(e)}")
            
    def get_error_statistics(self):
        """
        Get error statistics.
        
        Returns:
            Dictionary with error statistics
        """
        return self.error_logger.get_error_statistics()
        
    def cleanup(self):
        """Perform cleanup when the plugin is unloaded."""
        # Clean up components
        self.error_logger.cleanup()
        self.transaction_logger.cleanup()
        self.event_interceptor.cleanup()
        self.prevention.cleanup()