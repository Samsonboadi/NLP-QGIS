# error_system/transaction_log.py
import os
import json
import pickle
import time
import hashlib
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, Set
import logging

class TransactionLogger:
    """
    Transaction logging system that records user actions for potential rollbacks.
    
    This class maintains a log of operations that can be used to undo changes
    in case of errors, similar to a database transaction system.
    """
    
    def __init__(self, log_dir: Optional[str] = None, max_stored_states: int = 10):
        """
        Initialize the transaction logger.
        
        Args:
            log_dir: Directory to store transaction logs and state snapshots
            max_stored_states: Maximum number of state snapshots to keep
        """
        # Set up logging directory
        if log_dir is None:
            # Default to user's home directory
            home_dir = os.path.expanduser("~")
            log_dir = os.path.join(home_dir, ".qgis_nlp_transactions")
            
        # Ensure directory exists
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        self.log_dir = log_dir
        self.max_stored_states = max_stored_states
        
        # Set up log file paths
        self.transaction_log_file = os.path.join(log_dir, "transaction_log.json")
        self.state_dir = os.path.join(log_dir, "states")
        
        # Ensure state directory exists
        if not os.path.exists(self.state_dir):
            os.makedirs(self.state_dir)
            
        # Initialize transaction log
        self.transactions = self._load_transaction_log()
        
        # Set up logger
        self.logger = logging.getLogger('NLPGISPlugin.TransactionLogger')
        
    def _load_transaction_log(self) -> List[Dict[str, Any]]:
        """
        Load the transaction log from file.
        
        Returns:
            List of transaction records
        """
        if os.path.exists(self.transaction_log_file):
            try:
                with open(self.transaction_log_file, 'r') as f:
                    return json.load(f)
            except:
                # File exists but is not valid JSON
                backup_file = f"{self.transaction_log_file}.bak.{int(time.time())}"
                try:
                    os.rename(self.transaction_log_file, backup_file)
                except:
                    pass
                return []
        else:
            return []
            
    def _save_transaction_log(self):
        """Save the transaction log to file."""
        try:
            with open(self.transaction_log_file, 'w') as f:
                json.dump(self.transactions, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save transaction log: {str(e)}")
            
    def _get_state_snapshot_path(self, state_id: str) -> str:
        """
        Get the path to a state snapshot file.
        
        Args:
            state_id: ID of the state snapshot
            
        Returns:
            File path for the state snapshot
        """
        return os.path.join(self.state_dir, f"state_{state_id}.pickle")
        
    def _cleanup_old_states(self):
        """
        Clean up old state snapshots, keeping only the most recent ones.
        """
        # Get all state snapshots
        state_transactions = [t for t in self.transactions if t.get('has_state_snapshot', False)]
        
        # Sort by timestamp (newest first)
        state_transactions.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        # Keep only the newest max_stored_states
        states_to_keep = state_transactions[:self.max_stored_states]
        states_to_remove = state_transactions[self.max_stored_states:]
        
        # Remove old state files
        for transaction in states_to_remove:
            state_id = transaction.get('state_id')
            if state_id:
                state_path = self._get_state_snapshot_path(state_id)
                if os.path.exists(state_path):
                    try:
                        os.remove(state_path)
                        self.logger.info(f"Removed old state snapshot: {state_id}")
                    except Exception as e:
                        self.logger.error(f"Failed to remove old state snapshot {state_id}: {str(e)}")
                        
                # Update transaction record to indicate state no longer available
                transaction['has_state_snapshot'] = False
                
        # Save updated transaction log
        self._save_transaction_log()
        
    def log_operation(self, operation_type: str, parameters: Dict[str, Any], 
                     result: Optional[Any] = None, 
                     save_state: bool = False,
                     state_data: Optional[Dict[str, Any]] = None) -> str:
        """
        Log an operation in the transaction log.
        
        Args:
            operation_type: Type of operation performed
            parameters: Parameters of the operation
            result: Optional result of the operation
            save_state: Whether to save a state snapshot
            state_data: Optional state data to save (if save_state is True)
            
        Returns:
            Transaction ID for the logged operation
        """
        # Create transaction ID (timestamp-based)
        transaction_id = f"tx_{int(time.time())}_{hashlib.md5(operation_type.encode()).hexdigest()[:8]}"
        
        # Create transaction record
        transaction = {
            'transaction_id': transaction_id,
            'timestamp': datetime.now().isoformat(),
            'operation_type': operation_type,
            'parameters': parameters,
            'has_result': result is not None,
            'has_state_snapshot': False,
            'state_id': None
        }
        
        # Save result if provided
        if result is not None:
            try:
                # Try to make it JSON serializable
                json.dumps(result)
                transaction['result'] = result
            except:
                # If not JSON serializable, just note that result exists
                transaction['result'] = "Result exists but is not JSON serializable"
                
        # Save state snapshot if requested
        if save_state and state_data is not None:
            state_id = f"state_{transaction_id}"
            state_path = self._get_state_snapshot_path(state_id)
            
            try:
                with open(state_path, 'wb') as f:
                    pickle.dump(state_data, f)
                    
                transaction['has_state_snapshot'] = True
                transaction['state_id'] = state_id
                
                self.logger.info(f"Saved state snapshot for transaction {transaction_id}")
                
                # Clean up old states if we've exceeded our limit
                self._cleanup_old_states()
                
            except Exception as e:
                self.logger.error(f"Failed to save state snapshot: {str(e)}")
                
        # Add to transaction log
        self.transactions.append(transaction)
        
        # Save updated log
        self._save_transaction_log()
        
        return transaction_id
        
    def get_state_snapshot(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a state snapshot for a transaction.
        
        Args:
            transaction_id: ID of the transaction
            
        Returns:
            State snapshot data or None if not available
        """
        # Find transaction
        transaction = None
        for tx in self.transactions:
            if tx.get('transaction_id') == transaction_id:
                transaction = tx
                break
                
        if not transaction:
            self.logger.warning(f"Transaction {transaction_id} not found")
            return None
            
        # Check if transaction has a state snapshot
        if not transaction.get('has_state_snapshot', False):
            self.logger.warning(f"Transaction {transaction_id} has no state snapshot")
            return None
            
        # Get state ID
        state_id = transaction.get('state_id')
        if not state_id:
            self.logger.warning(f"Transaction {transaction_id} has no state ID")
            return None
            
        # Load state snapshot
        state_path = self._get_state_snapshot_path(state_id)
        if not os.path.exists(state_path):
            self.logger.warning(f"State snapshot file not found: {state_path}")
            # Update transaction to indicate state no longer available
            transaction['has_state_snapshot'] = False
            self._save_transaction_log()
            return None
            
        try:
            with open(state_path, 'rb') as f:
                state_data = pickle.load(f)
            return state_data
        except Exception as e:
            self.logger.error(f"Failed to load state snapshot: {str(e)}")
            return None
            
    def get_recent_operations(self, count: int = 10) -> List[Dict[str, Any]]:
        """
        Get the most recent operations from the transaction log.
        
        Args:
            count: Maximum number of operations to return
            
        Returns:
            List of the most recent transaction records
        """
        return self.transactions[-count:]
        
    def find_operations_by_type(self, operation_type: str) -> List[Dict[str, Any]]:
        """
        Find operations of a specific type.
        
        Args:
            operation_type: Type of operations to find
            
        Returns:
            List of matching transaction records
        """
        return [t for t in self.transactions if t.get('operation_type') == operation_type]
        
    def get_latest_state_snapshot(self) -> Optional[Tuple[str, Dict[str, Any]]]:
        """
        Get the latest available state snapshot.
        
        Returns:
            Tuple of (transaction_id, state_data) or None if no snapshots available
        """
        # Find transactions with state snapshots
        state_transactions = [t for t in self.transactions if t.get('has_state_snapshot', False)]
        
        if not state_transactions:
            return None
            
        # Sort by timestamp (newest first)
        state_transactions.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        # Try each one until we find a valid state
        for transaction in state_transactions:
            state_data = self.get_state_snapshot(transaction['transaction_id'])
            if state_data:
                return (transaction['transaction_id'], state_data)
                
        return None
        
    def rollback_to_transaction(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the state to roll back to a specific transaction.
        
        Args:
            transaction_id: ID of the transaction to roll back to
            
        Returns:
            State data to restore, or None if not available
        """
        return self.get_state_snapshot(transaction_id)
        
    def cleanup(self):
        """Perform cleanup when plugin is unloaded."""
        # Save transaction log
        self._save_transaction_log()