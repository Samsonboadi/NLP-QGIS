# testing/__init__.py
from .test_suite import NLPGISTestSuite
from .state_preserver import StatePreservationSystem
from .platform_adapter import PlatformAdapter

class TestingFramework:
    """Main testing and error recovery framework."""
    
    def __init__(self, nlp_engine=None, query_engine=None, error_system=None):
        """
        Initialize the testing framework.
        
        Args:
            nlp_engine: NLP engine instance
            query_engine: Query engine instance
            error_system: Error system instance
        """
        self.test_suite = NLPGISTestSuite(nlp_engine, query_engine, error_system)
        self.state_preserver = StatePreservationSystem()
        self.platform_adapter = PlatformAdapter()
        
    def run_tests(self, context=None):
        """
        Run the test suite.
        
        Args:
            context: Optional context information
            
        Returns:
            Test results
        """
        return self.test_suite.run_tests(context)
        
    def generate_test_report(self, output_file=None):
        """
        Generate a test report.
        
        Args:
            output_file: Optional file to write report to
            
        Returns:
            Report text
        """
        return self.test_suite.generate_test_report(output_file)
        
    def save_state(self, state_data, state_type='manual'):
        """
        Save the current state.
        
        Args:
            state_data: State data dictionary
            state_type: Type of state snapshot
            
        Returns:
            State ID
        """
        return self.state_preserver.save_state(state_data, state_type)
        
    def load_state(self, state_id=None):
        """
        Load a state.
        
        Args:
            state_id: ID of state to load, or None for most recent
            
        Returns:
            State data dictionary
        """
        return self.state_preserver.load_state(state_id)
        
    def get_platform_info(self):
        """
        Get platform information.
        
        Returns:
            Platform information dictionary
        """
        return self.platform_adapter.get_platform_info()
        
    def adapt_file_path(self, path):
        """
        Adapt a file path for the current platform.
        
        Args:
            path: File path to adapt
            
        Returns:
            Adapted file path
        """
        return self.platform_adapter.adapt_file_path(path)
        
    def create_recovery_point(self, state_data, description=''):
        """
        Create a named recovery point.
        
        Args:
            state_data: State data dictionary
            description: Optional description
            
        Returns:
            State ID
        """
        return self.state_preserver.create_recovery_point(state_data, description)
        
    def cleanup(self):
        """Perform cleanup when plugin is unloaded."""
        self.state_preserver.cleanup()