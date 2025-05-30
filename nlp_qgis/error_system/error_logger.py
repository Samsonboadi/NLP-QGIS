# error_system/error_logger.py
import logging
import os
import json
import time
import traceback
from datetime import datetime
from typing import Dict, List, Any, Optional
import statistics

class StructuredErrorLogger:
    """
    Enhanced error logging system that captures detailed error information.
    
    This logger creates structured records of errors with context information
    to help identify patterns and correlations between user actions and errors.
    """
    
    def __init__(self, log_dir: Optional[str] = None):
        """
        Initialize the error logger.
        
        Args:
            log_dir: Directory to save log files, or None for default location
        """
        # Set up logging directory
        if log_dir is None:
            # Default to user's home directory
            home_dir = os.path.expanduser("~")
            log_dir = os.path.join(home_dir, ".qgis_nlp_logs")
            
        # Ensure directory exists
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        self.log_dir = log_dir
        
        # Set up log file paths
        self.error_log_file = os.path.join(log_dir, "error_log.json")
        self.stats_file = os.path.join(log_dir, "error_stats.json")
        
        # Initialize error records
        self.error_records = self._load_existing_records()
        
        # Set up Python logger
        self.logger = logging.getLogger('NLPGISPlugin.ErrorLogger')
        file_handler = logging.FileHandler(os.path.join(log_dir, "nlp_gis.log"))
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        self.logger.setLevel(logging.INFO)
        
    def _load_existing_records(self) -> List[Dict[str, Any]]:
        """
        Load existing error records from file.
        
        Returns:
            List of error record dictionaries
        """
        if os.path.exists(self.error_log_file):
            try:
                with open(self.error_log_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                # File exists but is not valid JSON or other error
                self.logger.warning(f"Could not read existing error log: {self.error_log_file}")
                # Backup the problematic file
                backup_file = f"{self.error_log_file}.bak.{int(time.time())}"
                try:
                    os.rename(self.error_log_file, backup_file)
                    self.logger.info(f"Backed up problematic log file to {backup_file}")
                except:
                    pass
                return []
        else:
            return []
            
    def _save_records(self):
        """Save error records to file."""
        try:
            with open(self.error_log_file, 'w') as f:
                json.dump(self.error_records, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save error records: {str(e)}")
            
    def _update_stats(self):
        """Update error statistics file."""
        if not self.error_records:
            return
            
        try:
            # Group errors by type
            error_types = {}
            for record in self.error_records:
                error_type = record.get('error_type', 'unknown')
                if error_type not in error_types:
                    error_types[error_type] = []
                error_types[error_type].append(record)
                
            # Calculate statistics for each error type
            stats = {
                'total_errors': len(self.error_records),
                'error_types': {},
                'last_updated': datetime.now().isoformat()
            }
            
            for error_type, records in error_types.items():
                # Calculate when these errors occur (time since last action)
                times_since_last_action = [
                    r.get('time_since_last_action', 0) for r in records
                    if 'time_since_last_action' in r
                ]
                
                if times_since_last_action:
                    avg_time = statistics.mean(times_since_last_action)
                    median_time = statistics.median(times_since_last_action)
                else:
                    avg_time = None
                    median_time = None
                    
                # Count occurrences of preceding operations
                preceding_ops = {}
                for record in records:
                    if 'preceding_operation' in record:
                        op = record['preceding_operation']
                        preceding_ops[op] = preceding_ops.get(op, 0) + 1
                        
                # Most common preceding operation
                most_common_op = None
                max_count = 0
                for op, count in preceding_ops.items():
                    if count > max_count:
                        max_count = count
                        most_common_op = op
                        
                # Store stats for this error type
                stats['error_types'][error_type] = {
                    'count': len(records),
                    'percentage': (len(records) / len(self.error_records)) * 100,
                    'avg_time_since_last_action': avg_time,
                    'median_time_since_last_action': median_time,
                    'most_common_preceding_operation': most_common_op,
                    'preceding_operations': preceding_ops
                }
                
            # Save statistics
            with open(self.stats_file, 'w') as f:
                json.dump(stats, f, indent=2)
                
        except Exception as e:
            self.logger.error(f"Failed to update error statistics: {str(e)}")
            
    def log_error(self, error_type: str, error_message: str, 
                  error_traceback: Optional[str] = None,
                  context: Optional[Dict[str, Any]] = None):
        """
        Log an error with detailed contextual information.
        
        Args:
            error_type: Type or category of the error
            error_message: Error message
            error_traceback: Optional traceback text
            context: Optional dictionary with contextual information
        """
        # Create error record
        record = {
            'timestamp': datetime.now().isoformat(),
            'error_type': error_type,
            'error_message': error_message,
            'traceback': error_traceback or traceback.format_exc() if traceback.format_exc() != 'NoneType: None\n' else None
        }
        
        # Add context if provided
        if context:
            record.update(context)
            
        # Add to records
        self.error_records.append(record)
        
        # Log to standard logger as well
        self.logger.error(f"{error_type}: {error_message}")
        
        # Save updated records
        self._save_records()
        
        # Update statistics
        self._update_stats()
        
    def log_action(self, action_type: str, details: Dict[str, Any]):
        """
        Log a user action for correlation with errors.
        
        Args:
            action_type: Type of action performed
            details: Details about the action
        """
        # Create action record (not an error, but related for correlation)
        record = {
            'timestamp': datetime.now().isoformat(),
            'action_type': action_type,
            'details': details,
            'is_action': True  # Flag to distinguish from errors
        }
        
        # Add to records (we keep actions and errors in the same timeline)
        self.error_records.append(record)
        
        # Log to standard logger as well
        self.logger.info(f"Action: {action_type}")
        
        # Save updated records
        self._save_records()
        
    def get_errors_by_type(self, error_type: str) -> List[Dict[str, Any]]:
        """
        Get all errors of a specific type.
        
        Args:
            error_type: Type of errors to retrieve
            
        Returns:
            List of error records matching the type
        """
        return [r for r in self.error_records 
                if 'error_type' in r and r['error_type'] == error_type]
                
    def get_recent_errors(self, count: int = 10) -> List[Dict[str, Any]]:
        """
        Get the most recent errors.
        
        Args:
            count: Maximum number of errors to return
            
        Returns:
            List of the most recent error records
        """
        # Filter to only include error records (not actions)
        errors = [r for r in self.error_records if 'is_action' not in r]
        return errors[-count:]
        
    def get_error_statistics(self) -> Dict[str, Any]:
        """
        Get error statistics.
        
        Returns:
            Dictionary with error statistics
        """
        if os.path.exists(self.stats_file):
            try:
                with open(self.stats_file, 'r') as f:
                    return json.load(f)
            except:
                # If stats file is corrupted, just return basic stats
                return {'total_errors': len([r for r in self.error_records if 'is_action' not in r])}
        else:
            return {'total_errors': len([r for r in self.error_records if 'is_action' not in r])}
            
    def analyze_errors(self) -> Dict[str, Any]:
        """
        Perform deeper analysis of error patterns.
        
        Returns:
            Dictionary with analysis results
        """
        # This would implement more sophisticated analysis
        # For now, return a simplified analysis
        
        if not self.error_records:
            return {'status': 'No errors recorded yet'}
            
        # Filter to only include error records (not actions)
        errors = [r for r in self.error_records if 'is_action' not in r]
        
        # Group by error type
        error_types = {}
        for error in errors:
            error_type = error.get('error_type', 'unknown')
            if error_type not in error_types:
                error_types[error_type] = []
            error_types[error_type].append(error)
            
        # Find most common error type
        most_common_type = max(error_types.items(), key=lambda x: len(x[1]), default=('unknown', []))
        
        # Look for temporal patterns (time of day)
        hour_distribution = [0] * 24
        for error in errors:
            timestamp = error.get('timestamp')
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp)
                    hour_distribution[dt.hour] += 1
                except:
                    pass
                    
        # Find peak hour for errors
        peak_hour = hour_distribution.index(max(hour_distribution))
        
        return {
            'total_errors': len(errors),
            'unique_error_types': len(error_types),
            'most_common_error_type': {
                'type': most_common_type[0],
                'count': len(most_common_type[1]),
                'percentage': (len(most_common_type[1]) / len(errors)) * 100 if errors else 0
            },
            'temporal_patterns': {
                'peak_hour': peak_hour,
                'hour_distribution': hour_distribution
            }
        }
        
    def cleanup(self):
        """Perform cleanup when plugin is unloaded."""
        # Save any pending records
        self._save_records()
        
        # Update statistics
        self._update_stats()