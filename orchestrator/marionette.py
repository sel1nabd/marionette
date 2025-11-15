"""Core Marionette orchestrator - dual Gemini model supervision."""

import asyncio
import json
from datetime import datetime
from typing import List, Dict, Optional, AsyncIterator
from collections import deque

from .config import Config
from .gemini_client import GeminiClient
from .monitors import (
    DebugLoopMonitor,
    ContextDriftMonitor,
    SycophancyDetector,
    PromptQualityAnalyzer
)
from .interventions import InterventionEngine
from .session import SessionState


class Marionette:
    """
    Orchestrator that watches user and coding agent using Gemini models.
    
    Architecture:
    - Gemini Flash: Real-time log monitoring, pattern detection (fast reflexes)
    - Gemini Pro: Deep goal analysis, context reconstruction (strategic judgment)
    """
    
    def __init__(self, config: Config):
        self.config = config
        self.config.validate()
        
        # Dual Gemini models
        self.flash = GeminiClient(config.gemini_api_key, config.flash_model)
        self.pro = GeminiClient(config.gemini_api_key, config.pro_model)
        
        # Monitors (use Flash for real-time detection)
        self.debug_loop_monitor = DebugLoopMonitor(
            self.flash, 
            window=config.debug_loop_window
        )
        self.context_drift_monitor = ContextDriftMonitor(
            self.pro,  # Uses Pro for deep semantic analysis
            threshold=config.context_drift_threshold
        )
        self.sycophancy_detector = SycophancyDetector(
            self.flash,
            threshold=config.sycophancy_threshold
        )
        self.prompt_quality = PromptQualityAnalyzer(self.pro)
        
        # Intervention engine
        self.intervention = InterventionEngine(self.pro, config)
        
        # Session state
        self.session = SessionState(config.log_dir)
        
        # Event queues
        self.user_inputs: deque = deque(maxlen=100)
        self.agent_outputs: deque = deque(maxlen=100)
        self.error_history: deque = deque(maxlen=50)
        
        self._running = False
    
    async def start(self):
        """Start the orchestrator monitoring."""
        self._running = True
        self.session.start()
        
        # Start background monitoring tasks
        asyncio.create_task(self._monitor_loop())
    
    async def shutdown(self):
        """Graceful shutdown."""
        self._running = False
        await self.session.save()
        print("📊 Session saved to:", self.session.log_path)
    
    async def process_user_input(self, user_input: str) -> Dict:
        """
        Process user input through quality checks before sending to agent.
        
        Returns:
            Dict with 'approved' bool and optional 'feedback' for improvement
        """
        self.user_inputs.append({
            "timestamp": datetime.now().isoformat(),
            "content": user_input
        })
        
        # Check prompt quality if enabled
        if self.config.force_prompt_quality:
            quality_check = await self.prompt_quality.analyze(user_input)
            
            if not quality_check["approved"]:
                return {
                    "approved": False,
                    "feedback": quality_check["feedback"],
                    "suggestions": quality_check["suggestions"]
                }
        
        # Check for goal initialization (first 5 prompts)
        if len(self.user_inputs) <= 5:
            await self.context_drift_monitor.learn_initial_goal(
                [msg["content"] for msg in self.user_inputs]
            )
        
        return {"approved": True}
    
    async def process_agent_output(self, agent_output: str, is_error: bool = False) -> Dict:
        """
        Process agent output through monitoring checks.
        
        Returns:
            Dict with intervention decisions
        """
        self.agent_outputs.append({
            "timestamp": datetime.now().isoformat(),
            "content": agent_output,
            "is_error": is_error
        })
        
        interventions = {
            "kill_agent": False,
            "warnings": [],
            "suggestions": []
        }
        
        # Check for sycophancy
        sycophancy_result = await self.sycophancy_detector.check(agent_output)
        if sycophancy_result["detected"]:
            interventions["warnings"].append(
                f"⚠️ SYCOPHANCY DETECTED: {sycophancy_result['reason']}"
            )
            interventions["suggestions"].append(
                "Forcing agent to consider alternatives..."
            )
        
        # Track errors for debug loop detection
        if is_error:
            self.error_history.append({
                "timestamp": datetime.now().isoformat(),
                "error": agent_output
            })
            
            loop_check = await self.debug_loop_monitor.check(
                list(self.error_history)
            )
            
            if loop_check["in_loop"]:
                interventions["warnings"].append(
                    f"🔄 DEBUG LOOP DETECTED: {loop_check['pattern']}"
                )
                
                if self.config.auto_kill_loops:
                    interventions["kill_agent"] = True
                    
                    # Use Pro for deep analysis and solution search
                    solution = await self.intervention.analyze_and_pivot(
                        session_history=list(self.user_inputs) + list(self.agent_outputs),
                        error_sequence=list(self.error_history),
                        use_grounding=self.config.enable_grounding
                    )
                    
                    interventions["suggestions"].append(solution)
        
        # Log to session
        await self.session.log_interaction(
            user_inputs=list(self.user_inputs)[-1:],
            agent_outputs=list(self.agent_outputs)[-1:],
            interventions=interventions
        )
        
        return interventions
    
    async def _monitor_loop(self):
        """Background monitoring task for context drift detection."""
        while self._running:
            await asyncio.sleep(10)  # Check every 10 seconds
            
            if len(self.user_inputs) < 5:
                continue  # Need enough data first
            
            # Check for context drift
            drift_check = await self.context_drift_monitor.check(
                recent_actions=[msg["content"] for msg in list(self.agent_outputs)[-20:]]
            )
            
            if drift_check["drifted"]:
                print(f"\n⚠️ CONTEXT DRIFT WARNING:")
                print(f"   Initial goal: {drift_check['initial_goal']}")
                print(f"   Current trajectory: {drift_check['current_trajectory']}")
                print(f"   Distance: {drift_check['distance']:.2f}")
                print(f"   Recommendation: {drift_check['recommendation']}\n")
    
    def get_status(self) -> Dict:
        """Get current orchestrator status."""
        return {
            "session_id": self.session.session_id,
            "user_inputs": len(self.user_inputs),
            "agent_outputs": len(self.agent_outputs),
            "errors_tracked": len(self.error_history),
            "monitors": {
                "debug_loops": self.debug_loop_monitor.get_stats(),
                "context_drift": self.context_drift_monitor.get_stats(),
                "sycophancy": self.sycophancy_detector.get_stats()
            }
        }
