# testing/state_preserver.py
import os
import pickle
import json
import time
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

class StatePreservationSystem:
    """
    State preservation system that saves critical information for recovery after crashes.
    
    This system creates snapshots of the plugin state at critical points
    to enable recovery if crashes or errors occur.
    """
    
    def __init__(self, save_dir: Optional[str] = None):
        """
        Initialize the state preserver.
        
        Args:
            save_dir: Directory to save state snapshots
        """
        # Set up save directory
        if save_dir is None:
            # Default to user's home directory
            home_dir = os.path.expanduser("~")
            save_dir = os.path.join(home_dir, ".qgis_nlp_states")
            
        # Ensure directory exists
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
            
        self.save_dir = save_dir
        
        # Set up logger
        self.logger = logging.getLogger('NLPGISPlugin.StatePreserver')
        
        # State tracking
        self.current_state_id = None
        self.state_history = []
        self.max_states = 10  # Maximum number of states to keep
        
    def save_state(self, state_data: Dict[str, Any], state_type: str = 'manual') -> str:
        """
        Save the current state.
        
        Args:
            state_data: Dictionary with state data
            state_type: Type of state snapshot
            
        Returns:
            State ID
        """
        # Create state ID
        timestamp = int(time.time())
        state_id = f"state_{timestamp}_{state_type}"
        
        # Add metadata
        state_with_meta = {
            'state_id': state_id,
            'timestamp': timestamp,
            'datetime': datetime.now().isoformat(),
            'type': state_type,
            'data': state_data
        }
        
        # Save to file
        file_path = os.path.join(self.save_dir, f"{state_id}.pickle")
        try:
            with open(file_path, 'wb') as f:
                pickle.dump(state_with_meta, f)
                
            # Save summary to JSON (without the actual data)
            summary = state_with_meta.copy()
            del summary['data']
            
            summary_path = os.path.join(self.save_dir, "state_history.json")
            
            # Load existing history
            history = []
            if os.path.exists(summary_path):
                try:
                    with open(summary_path, 'r') as f:
                        history = json.load(f)
                except:
                    history = []
                    
            # Add new state
            history.append(summary)
            
            # Save updated history
            with open(summary_path, 'w') as f:
                json.dump(history, f, indent=2)
                
            # Update current state
            self.current_state_id = state_id
            self.state_history = history
            
            # Clean up old states
            self._cleanup_old_states()
            
            self.logger.info(f"State saved: {state_id}")
            
            return state_id
            
        except Exception as e:
            self.logger.error(f"Failed to save state: {str(e)}")
            return None
            
    def load_state(self, state_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Load a state snapshot.
        
        Args:
            state_id: ID of state to load, or None for most recent
            
        Returns:
            State data dictionary or None if not found
        """
        # If no state ID specified, get the most recent
        if state_id is None:
            if not self.state_history:
                # Load history from file
                summary_path = os.path.join(self.save_dir, "state_history.json")
                if os.path.exists(summary_path):
                    try:
                        with open(summary_path, 'r') as f:
                            self.state_history = json.load(f)
                    except:
                        self.state_history = []
                        
            if self.state_history:
                # Sort by timestamp (newest first)
                sorted_history = sorted(
                    self.state_history,
                    key=lambda x: x.get('timestamp', 0),
                    reverse=True
                )
                
                state_id = sorted_history[0].get('state_id')
            else:
                self.logger.warning("No state history available")
                return None
                
        # Load the state file
        file_path = os.path.join(self.save_dir, f"{state_id}.pickle")
        if not os.path.exists(file_path):
            self.logger.warning(f"State file not found: {file_path}")
            return None
            
        try:
            with open(file_path, 'rb') as f:
                state = pickle.load(f)
                
            # Update current state
            self.current_state_id = state_id
            
            self.logger.info(f"State loaded: {state_id}")
            
            # Return just the data portion
            return state.get('data')
            
        except Exception as e:
            self.logger.error(f"Failed to load state: {str(e)}")
            return None
            
    def get_state_history(self) -> List[Dict[str, Any]]:
        """
        Get the history of saved states.
        
        Returns:
            List of state metadata dictionaries
        """
        # Ensure we have the latest history
        summary_path = os.path.join(self.save_dir, "state_history.json")
        if os.path.exists(summary_path):
            try:
                with open(summary_path, 'r') as f:
                    self.state_history = json.load(f)
            except:
                # If file exists but can't be read
                if not self.state_history:
                    self.state_history = []
                    
        # Sort by timestamp (newest first)
        sorted_history = sorted(
            self.state_history,
            key=lambda x: x.get('timestamp', 0),
            reverse=True
        )
        
        return sorted_history
        
    def delete_state(self, state_id: str) -> bool:
        """
        Delete a state snapshot.
        
        Args:
            state_id: ID of state to delete
            
        Returns:
            True if deleted successfully, False otherwise
        """
        file_path = os.path.join(self.save_dir, f"{state_id}.pickle")
        if not os.path.exists(file_path):
            self.logger.warning(f"State file not found: {file_path}")
            return False
            
        try:
            # Delete the file
            os.remove(file_path)
            
            # Update history
            summary_path = os.path.join(self.save_dir, "state_history.json")
            if os.path.exists(summary_path):
                try:
                    with open(summary_path, 'r') as f:
                        history = json.load(f)
                        
                    # Remove this state
                    history = [s for s in history if s.get('state_id') != state_id]
                    
                    # Save updated history
                    with open(summary_path, 'w') as f:
                        json.dump(history, f, indent=2)
                        
                    self.state_history = history
                    
                except:
                    pass
                    
            self.logger.info(f"State deleted: {state_id}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to delete state: {str(e)}")
            return False
            
    def _cleanup_old_states(self):
        """Clean up old state snapshots, keeping only the most recent ones."""
        # Get all states
        history = self.get_state_history()
        
        # Keep only the newest max_states
        if len(history) > self.max_states:
            states_to_remove = history[self.max_states:]
            
            for state in states_to_remove:
                state_id = state.get('state_id')
                if state_id:
                    self.delete_state(state_id)
                    
    def auto_save_state(self, state_data: Dict[str, Any]) -> str:
        """
        Automatically save state at regular intervals.
        
        Args:
            state_data: Dictionary with state data
            
        Returns:
            State ID
        """
        # This would be called periodically
        return self.save_state(state_data, state_type='auto')
        
    def create_recovery_point(self, state_data: Dict[str, Any], description: str = '') -> str:
        """
        Create a named recovery point.
        
        Args:
            state_data: Dictionary with state data
            description: Optional description of the recovery point
            
        Returns:
            State ID
        """
        # Add description to state data
        state_data['recovery_description'] = description
        
        return self.save_state(state_data, state_type='recovery')
        
    def cleanup(self):
        """Perform cleanup when plugin is unloaded."""
        # Nothing specific to do
        pass