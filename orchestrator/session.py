"""Session state management and logging."""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


class SessionState:
    """Manages session state and saves logs for analysis."""
    
    def __init__(self, log_dir: str):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.session_id = None
        self.start_time = None
        self.interactions = []
        self.interventions_log = []
    
    def start(self):
        """Start a new session."""
        self.session_id = str(uuid.uuid4())[:8]
        self.start_time = datetime.now()
        print(f"📝 Session ID: {self.session_id}")
    
    async def log_interaction(
        self,
        user_inputs: List[Dict],
        agent_outputs: List[Dict],
        interventions: Dict
    ):
        """Log an interaction with any interventions."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "user_inputs": user_inputs,
            "agent_outputs": agent_outputs,
            "interventions": interventions
        }
        
        self.interactions.append(entry)
        
        if interventions.get("warnings") or interventions.get("kill_agent"):
            self.interventions_log.append(entry)
    
    async def save(self):
        """Save session to disk."""
        if not self.session_id:
            return
        
        session_data = {
            "session_id": self.session_id,
            "start_time": self.start_time.isoformat(),
            "end_time": datetime.now().isoformat(),
            "total_interactions": len(self.interactions),
            "total_interventions": len(self.interventions_log),
            "interactions": self.interactions,
            "interventions": self.interventions_log
        }
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"marionette_{self.session_id}_{timestamp}.json"
        filepath = self.log_dir / filename
        
        with open(filepath, 'w') as f:
            json.dump(session_data, f, indent=2)
        
        self.log_path = filepath
    
    def get_summary(self) -> Dict:
        """Get session summary statistics."""
        return {
            "session_id": self.session_id,
            "duration": str(datetime.now() - self.start_time) if self.start_time else "N/A",
            "interactions": len(self.interactions),
            "interventions": len(self.interventions_log)
        }
