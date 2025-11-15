"""Monitoring modules using Gemini models for pattern detection."""

from typing import List, Dict
from collections import Counter
from .gemini_client import GeminiClient


class DebugLoopMonitor:
    """
    Detects when agent is stuck in repetitive error patterns.
    Uses Gemini Flash for real-time pattern matching.
    """
    
    def __init__(self, flash_client: GeminiClient, window: int = 5):
        self.flash = flash_client
        self.window = window
        self.detections = 0
    
    async def check(self, error_history: List[Dict]) -> Dict:
        """Check if recent errors form a repetitive loop."""
        if len(error_history) < self.window:
            return {"in_loop": False}
        
        recent_errors = error_history[-self.window:]
        
        # Quick heuristic check first (exact matches)
        error_texts = [e["error"][:200] for e in recent_errors]
        if len(set(error_texts)) == 1:
            self.detections += 1
            return {
                "in_loop": True,
                "pattern": "Identical errors repeated",
                "count": self.window
            }
        
        # Use Flash for semantic similarity check
        prompt = f"""Analyze these recent errors for repetitive patterns:

{chr(10).join(f"{i+1}. {e['error'][:300]}" for i, e in enumerate(recent_errors))}

Are these errors indicating the agent is stuck in a debug loop?
Consider:
- Similar error messages
- Same failed approach repeated
- No progress between attempts

Respond with JSON:
{{
    "in_loop": true/false,
    "pattern": "description of the loop pattern if detected",
    "confidence": 0-100
}}"""
        
        result = await self.flash.generate_json(prompt)
        
        if result.get("in_loop") and result.get("confidence", 0) > 70:
            self.detections += 1
            return {
                "in_loop": True,
                "pattern": result.get("pattern", "Repetitive error pattern"),
                "confidence": result.get("confidence")
            }
        
        return {"in_loop": False}
    
    def get_stats(self) -> Dict:
        return {"total_detections": self.detections}


class ContextDriftMonitor:
    """
    Detects when agent strays from user's original goal.
    Uses Gemini Pro for deep semantic understanding.
    """
    
    def __init__(self, pro_client: GeminiClient, threshold: float = 0.7):
        self.pro = pro_client
        self.threshold = threshold
        self.initial_goal = None
        self.drift_events = 0
    
    async def learn_initial_goal(self, early_prompts: List[str]) -> None:
        """Extract and understand user's core goal from initial prompts."""
        prompt = f"""Analyze these initial user prompts to extract their core goal:

{chr(10).join(f"{i+1}. {p}" for i, p in enumerate(early_prompts))}

What is the user trying to build/achieve? Be concise but capture the essence.

Respond with JSON:
{{
    "goal": "concise description of the core goal",
    "key_requirements": ["req1", "req2", ...],
    "technical_stack": "identified technologies if any"
}}"""
        
        result = await self.pro.generate_json(prompt)
        self.initial_goal = result
    
    async def check(self, recent_actions: List[str]) -> Dict:
        """Check if recent actions have drifted from initial goal."""
        if not self.initial_goal or not recent_actions:
            return {"drifted": False}
        
        prompt = f"""Compare the initial goal with recent agent actions:

INITIAL GOAL:
{self.initial_goal.get('goal', 'Unknown')}
Key requirements: {', '.join(self.initial_goal.get('key_requirements', []))}

RECENT ACTIONS (last 20):
{chr(10).join(f"- {a[:200]}" for a in recent_actions[-20:])}

Has the agent drifted from the core goal? Consider:
- Are recent actions aligned with the goal?
- Is the agent solving the right problem?
- Has scope crept significantly?

Respond with JSON:
{{
    "drifted": true/false,
    "distance": 0.0-1.0,
    "current_trajectory": "what agent seems to be working on now",
    "recommendation": "how to get back on track if drifted"
}}"""
        
        result = await self.pro.generate_json(prompt)
        
        if result.get("distance", 0) > self.threshold:
            self.drift_events += 1
            return {
                "drifted": True,
                "initial_goal": self.initial_goal.get("goal"),
                "current_trajectory": result.get("current_trajectory"),
                "distance": result.get("distance"),
                "recommendation": result.get("recommendation")
            }
        
        return {"drifted": False}
    
    def get_stats(self) -> Dict:
        return {
            "drift_events": self.drift_events,
            "has_learned_goal": self.initial_goal is not None
        }


class SycophancyDetector:
    """
    Detects when agent is being overly agreeable without critical thinking.
    Uses Gemini Flash for pattern matching.
    """
    
    SYCOPHANCY_PATTERNS = [
        "you're absolutely right",
        "great idea",
        "perfect",
        "excellent point",
        "that's a fantastic",
        "i completely agree",
        "you're correct",
        "brilliant",
        "exactly what we need"
    ]
    
    def __init__(self, flash_client: GeminiClient, threshold: int = 3):
        self.flash = flash_client
        self.threshold = threshold
        self.detections = 0
    
    async def check(self, agent_output: str) -> Dict:
        """Check if agent response shows sycophantic behavior."""
        output_lower = agent_output.lower()
        
        # Quick pattern match
        matches = sum(1 for pattern in self.SYCOPHANCY_PATTERNS if pattern in output_lower)
        
        if matches >= self.threshold:
            self.detections += 1
            return {
                "detected": True,
                "reason": f"Excessive agreement patterns ({matches} found)",
                "confidence": min(100, matches * 30)
            }
        
        # Deeper analysis for subtle sycophancy
        if len(agent_output) > 100:
            prompt = f"""Analyze this agent response for sycophantic behavior:

"{agent_output[:500]}"

Is the agent being overly agreeable without offering critical analysis or alternatives?

Respond with JSON:
{{
    "sycophantic": true/false,
    "reason": "explanation if true",
    "confidence": 0-100
}}"""
            
            result = await self.flash.generate_json(prompt)
            
            if result.get("sycophantic") and result.get("confidence", 0) > 70:
                self.detections += 1
                return {
                    "detected": True,
                    "reason": result.get("reason"),
                    "confidence": result.get("confidence")
                }
        
        return {"detected": False}
    
    def get_stats(self) -> Dict:
        return {"total_detections": self.detections}


class PromptQualityAnalyzer:
    """
    Analyzes user prompts for clarity and completeness.
    Uses Gemini Pro for deep understanding.
    """
    
    def __init__(self, pro_client: GeminiClient):
        self.pro = pro_client
    
    async def analyze(self, user_prompt: str) -> Dict:
        """Analyze prompt quality and suggest improvements if needed."""
        prompt = f"""Rate this coding prompt for quality:

"{user_prompt}"

Evaluate:
1. Specificity (0-10): Are requirements clear and specific?
2. Completeness (0-10): Is all necessary context provided?
3. Ambiguity (0-10): How much is left to interpretation? (lower is better)

A good prompt scores 6+ on specificity and completeness, and below 5 on ambiguity.

Respond with JSON:
{{
    "specificity": 0-10,
    "completeness": 0-10,
    "ambiguity": 0-10,
    "approved": true/false,
    "feedback": "constructive feedback if not approved",
    "suggestions": ["specific improvement 1", "improvement 2"]
}}"""
        
        result = await self.pro.generate_json(prompt)
        
        # Set approval based on thresholds
        approved = (
            result.get("specificity", 0) >= 6 and
            result.get("completeness", 0) >= 6 and
            result.get("ambiguity", 10) <= 5
        )
        
        result["approved"] = approved
        return result
