"""Intervention engine for guiding agent out of stuck states."""

from typing import List, Dict
from .gemini_client import GeminiClient
from .config import Config


class InterventionEngine:
    """
    Uses Gemini Pro to analyze stuck states and suggest pivots.
    Leverages grounding for researching solutions.
    """
    
    def __init__(self, pro_client: GeminiClient, config: Config):
        self.pro = pro_client
        self.config = config
        self.interventions_made = 0
    
    async def analyze_and_pivot(
        self,
        session_history: List[Dict],
        error_sequence: List[Dict],
        use_grounding: bool = True
    ) -> str:
        """
        Deep analysis of stuck state with grounded solution search.
        
        Returns:
            Actionable pivot suggestion for the agent
        """
        self.interventions_made += 1
        
        # Build context
        recent_context = "\n".join([
            f"[{msg.get('timestamp', 'N/A')}] {msg.get('content', '')[:300]}"
            for msg in session_history[-10:]
        ])
        
        error_context = "\n".join([
            f"Error {i+1}: {err.get('error', '')[:300]}"
            for i, err in enumerate(error_sequence[-5:])
        ])
        
        prompt = f"""You are analyzing a coding agent stuck in a debug loop.

RECENT SESSION CONTEXT:
{recent_context}

ERROR SEQUENCE (repeating pattern):
{error_context}

Tasks:
1. Identify the root cause of the loop
2. Determine what the agent has tried that failed
3. Suggest a completely different approach (not just tweaks)
4. If needed, search for similar solved problems

Provide:
{{
    "root_cause": "why the agent is stuck",
    "failed_approaches": ["what has been tried"],
    "pivot_strategy": "fundamentally different approach to try",
    "specific_actions": ["step 1", "step 2", ...],
    "confidence": 0-100
}}

Respond with JSON only."""
        
        system_instruction = """You are a senior debugging expert analyzing why coding agents get stuck.
You excel at identifying root causes and suggesting pivots that break patterns.
Always think: "What haven't they tried yet?"
When using grounding, search for: "how to solve [specific error]" or "alternative approaches to [problem]"."""
        
        result = await self.pro.generate_json(
            prompt,
            system_instruction=system_instruction,
            grounding=use_grounding
        )
        
        # Format as actionable suggestion
        pivot_msg = f"""
🔄 MARIONETTE INTERVENTION #{self.interventions_made}

ROOT CAUSE: {result.get('root_cause', 'Unknown')}

FAILED APPROACHES:
{chr(10).join(f"  ✗ {a}" for a in result.get('failed_approaches', []))}

PIVOT STRATEGY: {result.get('pivot_strategy', 'Try a different approach')}

RECOMMENDED ACTIONS:
{chr(10).join(f"  {i+1}. {a}" for i, a in enumerate(result.get('specific_actions', [])))}

Confidence: {result.get('confidence', 0)}%
"""
        
        return pivot_msg
    
    async def suggest_alternative_approach(
        self,
        current_approach: str,
        problem: str
    ) -> List[str]:
        """Generate alternative approaches to a problem."""
        prompt = f"""Given this problem and current approach:

PROBLEM: {problem}

CURRENT APPROACH: {current_approach}

Generate 3 completely different approaches. Think outside the box.

Respond with JSON:
{{
    "alternatives": [
        {{"name": "approach name", "description": "how it works", "tradeoffs": "pros/cons"}},
        ...
    ]
}}"""
        
        result = await self.pro.generate_json(
            prompt,
            grounding=self.config.enable_grounding
        )
        
        return result.get("alternatives", [])
    
    async def force_critical_thinking(self, agent_response: str) -> str:
        """Generate a prompt to inject critical thinking into agent's process."""
        prompt = f"""The agent gave this response:

"{agent_response[:500]}"

Generate a follow-up prompt that forces the agent to:
1. List 3 potential problems with their approach
2. Consider what could go wrong
3. Suggest one alternative

Respond with just the prompt text (no JSON)."""
        
        return await self.pro.generate(prompt, temperature=0.8)
    
    def get_stats(self) -> Dict:
        return {"total_interventions": self.interventions_made}
