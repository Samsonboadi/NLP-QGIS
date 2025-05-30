# testing/test_suite.py
import unittest
import os
import logging
import time
import random
import json
from typing import Dict, List, Any, Optional, Tuple, Callable

class NLPGISTestSuite:
    """
    Specialized test suite for AI-driven GIS functionality with probabilistic evaluation.
    
    This test suite handles the unique challenges of testing AI-driven systems
    where outputs can vary but still be correct, requiring probabilistic rather
    than deterministic evaluation criteria.
    """
    
    def __init__(self, nlp_engine=None, query_engine=None, error_system=None):
        """
        Initialize the test suite.
        
        Args:
            nlp_engine: NLP engine instance
            query_engine: Query engine instance
            error_system: Error system instance
        """
        self.nlp_engine = nlp_engine
        self.query_engine = query_engine
        self.error_system = error_system
        
        # Set up logger
        self.logger = logging.getLogger('NLPGISPlugin.TestSuite')
        
        # Test cases
        self.test_cases = []
        self.results = {}
        
        # Add default test cases
        self._add_default_test_cases()
        
    def _add_default_test_cases(self):
        """Add default test cases for common operations."""
        # Buffer test cases
        self.add_test_case(
            'buffer_simple',
            'Buffer the roads layer by 100 meters',
            {
                'operation': 'buffer',
                'input_layer': 'roads',
                'parameters': {
                    'distance': lambda x: 90 <= x <= 110  # Accept values between 90-110
                }
            }
        )
        
        self.add_test_case(
            'buffer_with_units',
            'Create a 2 kilometer buffer around hospitals',
            {
                'operation': 'buffer',
                'input_layer': 'hospitals',
                'parameters': {
                    'distance': lambda x: 1900 <= x <= 2100  # ~2km in meters
                }
            }
        )
        
        # Clip test cases
        self.add_test_case(
            'clip_simple',
            'Clip roads with city boundaries',
            {
                'operation': 'clip',
                'input_layer': 'roads',
                'secondary_layer': 'city boundaries'
            }
        )
        
        # Select test cases
        self.add_test_case(
            'select_simple',
            'Select buildings where area > 1000',
            {
                'operation': 'select',
                'input_layer': 'buildings',
                'parameters': {
                    'expression': lambda x: 'area' in x.lower() and '>' in x and '1000' in x
                }
            }
        )
        
        # Intersection test cases
        self.add_test_case(
            'intersection_simple',
            'Find the intersection of roads and flood zones',
            {
                'operation': 'intersection',
                'input_layer': 'roads',
                'secondary_layer': 'flood zones'
            }
        )
        
    def add_test_case(self, test_id: str, query: str, expected_result: Dict[str, Any]):
        """
        Add a test case to the suite.
        
        Args:
            test_id: Unique identifier for the test
            query: Natural language query to test
            expected_result: Expected result dictionary (can contain callable validators)
        """
        self.test_cases.append({
            'test_id': test_id,
            'query': query,
            'expected_result': expected_result
        })
        
    def run_tests(self, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Run all test cases.
        
        Args:
            context: Optional context information for queries
            
        Returns:
            Dictionary with test results
        """
        start_time = time.time()
        self.results = {
            'total_tests': len(self.test_cases),
            'passed': 0,
            'failed': 0,
            'errors': 0,
            'test_details': {},
            'duration': 0
        }
        
        for test_case in self.test_cases:
            test_id = test_case['test_id']
            query = test_case['query']
            expected = test_case['expected_result']
            
            self.logger.info(f"Running test: {test_id}")
            
            try:
                # Process the query
                result = self.query_engine.process_query(query, context)
                
                # Validate the result
                validation = self._validate_result(result, expected)
                
                # Store test details
                self.results['test_details'][test_id] = {
                    'query': query,
                    'result': result,
                    'validation': validation,
                    'passed': validation['overall_result']
                }
                
                # Update counts
                if validation['overall_result']:
                    self.results['passed'] += 1
                else:
                    self.results['failed'] += 1
                    
            except Exception as e:
                # Handle test errors
                self.logger.error(f"Error in test {test_id}: {str(e)}")
                self.results['errors'] += 1
                self.results['test_details'][test_id] = {
                    'query': query,
                    'error': str(e),
                    'passed': False
                }
                
        # Calculate duration
        self.results['duration'] = time.time() - start_time
        
        return self.results
        
    def _validate_result(self, result: Dict[str, Any], expected: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate a result against expected values with probabilistic criteria.
        
        Args:
            result: Actual result
            expected: Expected result template
            
        Returns:
            Validation results
        """
        validation = {
            'overall_result': True,
            'field_results': {}
        }
        
        # Check each expected field
        for field, expected_value in expected.items():
            # Get actual value
            actual_value = result.get(field)
            
            # Validate based on the type of expected_value
            if callable(expected_value):
                # It's a validator function
                field_result = expected_value(actual_value)
                validation['field_results'][field] = {
                    'expected': 'callable validator',
                    'actual': actual_value,
                    'passed': field_result
                }
                
                # Update overall result
                validation['overall_result'] = validation['overall_result'] and field_result
                
            elif isinstance(expected_value, dict) and isinstance(actual_value, dict):
                # Recursively validate nested dictionaries
                nested_validation = self._validate_result(actual_value, expected_value)
                validation['field_results'][field] = nested_validation
                
                # Update overall result
                validation['overall_result'] = validation['overall_result'] and nested_validation['overall_result']
                
            else:
                # Direct comparison
                field_result = actual_value == expected_value
                validation['field_results'][field] = {
                    'expected': expected_value,
                    'actual': actual_value,
                    'passed': field_result
                }
                
                # Update overall result
                validation['overall_result'] = validation['overall_result'] and field_result
                
        return validation
        
    def generate_test_report(self, output_file: Optional[str] = None) -> str:
        """
        Generate a human-readable test report.
        
        Args:
            output_file: Optional file to write report to
            
        Returns:
            Report text
        """
        if not self.results:
            return "No tests have been run yet."
            
        # Generate report
        report = "NLP GIS Test Suite Report\n"
        report += "========================\n\n"
        
        # Summary
        report += f"Tests: {self.results['total_tests']}\n"
        report += f"Passed: {self.results['passed']}\n"
        report += f"Failed: {self.results['failed']}\n"
        report += f"Errors: {self.results['errors']}\n"
        report += f"Duration: {self.results['duration']:.2f} seconds\n\n"
        
        # Test details
        report += "Test Details:\n"
        report += "-------------\n\n"
        
        for test_id, details in self.results['test_details'].items():
            report += f"Test: {test_id}\n"
            report += f"Query: {details['query']}\n"
            report += f"Result: {'PASS' if details.get('passed', False) else 'FAIL'}\n"
            
            if 'error' in details:
                report += f"Error: {details['error']}\n"
            elif 'validation' in details:
                validation = details['validation']
                report += "Validation:\n"
                
                for field, field_result in validation['field_results'].items():
                    if isinstance(field_result, dict) and 'passed' in field_result:
                        report += f"  - {field}: {'PASS' if field_result['passed'] else 'FAIL'}\n"
                        
                        if not field_result['passed'] and 'actual' in field_result and 'expected' in field_result:
                            report += f"    Expected: {field_result['expected']}\n"
                            report += f"    Actual: {field_result['actual']}\n"
                    else:
                        report += f"  - {field}: {field_result}\n"
                        
            report += "\n"
            
        # Write to file if requested
        if output_file:
            try:
                with open(output_file, 'w') as f:
                    f.write(report)
            except Exception as e:
                self.logger.error(f"Failed to write report to {output_file}: {str(e)}")
                
        return report
        
    def run_stress_test(self, query_templates: List[str], iterations: int = 100, 
                       context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Run a stress test with many variations of queries.
        
        Args:
            query_templates: List of query templates to use
            iterations: Number of test iterations
            context: Optional context information
            
        Returns:
            Stress test results
        """
        start_time = time.time()
        
        results = {
            'total_queries': iterations,
            'successful_queries': 0,
            'failed_queries': 0,
            'errors': 0,
            'avg_processing_time': 0,
            'duration': 0
        }
        
        processing_times = []
        
        for i in range(iterations):
            # Select a random template
            template = random.choice(query_templates)
            
            # Create a variation if template contains placeholders
            query = self._create_query_variation(template)
            
            try:
                # Time the query processing
                query_start = time.time()
                result = self.query_engine.process_query(query, context)
                query_time = time.time() - query_start
                
                # Store processing time
                processing_times.append(query_time)
                
                # Check if query was successful
                if result.get('operation') != 'unknown' and result.get('confidence', 0) > 0.5:
                    results['successful_queries'] += 1
                else:
                    results['failed_queries'] += 1
                    
            except Exception as e:
                self.logger.error(f"Error in stress test query: {str(e)}")
                results['errors'] += 1
                
        # Calculate statistics
        if processing_times:
            results['avg_processing_time'] = sum(processing_times) / len(processing_times)
            results['min_processing_time'] = min(processing_times)
            results['max_processing_time'] = max(processing_times)
            
        results['duration'] = time.time() - start_time
        
        return results
        
    def _create_query_variation(self, template: str) -> str:
        """
        Create a variation of a query template.
        
        Args:
            template: Query template with optional placeholders
            
        Returns:
            Concrete query with placeholders replaced
        """
        # Example placeholder replacements
        replacements = {
            '{LAYER}': ['roads', 'buildings', 'rivers', 'parcels', 'city boundaries'],
            '{DISTANCE}': ['100 meters', '500 meters', '1 kilometer', '2 miles', '50 feet'],
            '{ATTRIBUTE}': ['area', 'length', 'population', 'name', 'category'],
            '{OPERATOR}': ['>', '<', '=', '>=', '<='],
            '{VALUE}': ['1000', '500', '100', '10000', '250']
        }
        
        # Replace all placeholders
        query = template
        for placeholder, options in replacements.items():
            if placeholder in query:
                replacement = random.choice(options)
                query = query.replace(placeholder, replacement)
                
        return query
        
    def run_cross_platform_tests(self, platforms: List[str]) -> Dict[str, Any]:
        """
        Simulate cross-platform testing.
        
        Args:
            platforms: List of platforms to simulate
            
        Returns:
            Cross-platform test results
        """
        # This would normally use actual different environments
        # For now, we'll simulate platform differences
        
        results = {
            'platforms': {},
            'overall_result': True
        }
        
        for platform in platforms:
            self.logger.info(f"Running tests for platform: {platform}")
            
            # Apply platform-specific context
            context = self._get_platform_context(platform)
            
            # Run tests with this context
            platform_results = self.run_tests(context)
            
            # Store results for this platform
            results['platforms'][platform] = {
                'passed': platform_results['passed'],
                'failed': platform_results['failed'],
                'errors': platform_results['errors']
            }
            
            # Update overall result
            if platform_results['failed'] > 0 or platform_results['errors'] > 0:
                results['overall_result'] = False
                
        return results
        
    def _get_platform_context(self, platform: str) -> Dict[str, Any]:
        """
        Get context information specific to a platform.
        
        Args:
            platform: Platform name
            
        Returns:
            Platform-specific context
        """
        # Simulate platform differences
        if platform.lower() == 'windows':
            return {
                'os': 'windows',
                'path_separator': '\\',
                'qgis_version': '3.22',
                'layer_naming': 'case_insensitive'
            }
        elif platform.lower() == 'macos':
            return {
                'os': 'macos',
                'path_separator': '/',
                'qgis_version': '3.22',
                'layer_naming': 'case_sensitive'
            }
        elif platform.lower() == 'linux':
            return {
                'os': 'linux',
                'path_separator': '/',
                'qgis_version': '3.22',
                'layer_naming': 'case_sensitive'
            }
        else:
            return {'os': 'unknown'}