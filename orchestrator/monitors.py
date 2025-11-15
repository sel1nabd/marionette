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
        prompt = f"""You are evaluating whether a user prompt is good enough for a coding AI assistant.

USER PROMPT: "{user_prompt}"

IMPORTANT RULES:
1. **Casual conversation is ALWAYS approved** - greetings, questions, clarifications
2. **Only reject vague BUILD/IMPLEMENT requests** - when user wants code but gives almost no detail
3. **Reasonable prompts should pass** - don't be pedantic about minor missing details

EXAMPLES:

✅ APPROVE THESE (casual conversation):
- "hi", "hello", "hey"
- "who are you?", "what can you do?"
- "thanks", "ok", "got it"

❌ REJECT THESE (too vague for building):
- "make a website" (no details at all)
- "fix my code" (what code? what's wrong?)
- "build an app" (what kind? what features?)

❌ REJECT THESE (has some detail but still not enough):
- "wanna build a html+css dog website, two pages, first page contains title called 'Dog Paws Cleaner', and a big image of a dog underneath that which i'll upload myself. That's it. Second page, is a contact form, username, email, that's it."
  → Has tech stack and pages, but missing: layout details, styling/colors, what happens with form, image sizing. Needs more detail!

- "create a todo app with react"
  → What features? What should todos have? How do they persist? Needs specifics.

✅ APPROVE THESE (reasonable build requests with sufficient detail):
- "build a html+css dog website, two pages, first page has title 'Dog Paws Cleaner' and a big dog image that takes full width. Second page is contact form with username and email fields. White and brown colors, black text, frontend only, no backend."
  → Has tech stack, pages described, layout hints (full width), color scheme, clarified frontend only. Good enough!

- "create a python script that reads a CSV file and prints the first 5 rows"
  → Clear language, clear task, clear output. Good enough!

❌ REJECT THESE (extremely vague build requests):
- "make a website for my business"
  → What kind of business? What content? What pages? Way too vague.

- "i need a form"
  → What fields? What should it do? What tech? Too vague.

Evaluate the prompt:
- If it's casual conversation → ALWAYS approve
- If it's a build request → check if it has basic details (tech, what to build, rough idea of how)
- Don't nitpick about fonts, exact layouts, or minor styling details

Rate 0-10:
1. Specificity: Is the core request clear?
2. Completeness: Are basic requirements provided?
3. Ambiguity: How unclear is it? (lower = clearer)

Respond with JSON:
{{
    "specificity": 0-10,
    "completeness": 0-10,
    "ambiguity": 0-10,
    "approved": true/false,
    "feedback": "constructive feedback if not approved",
    "suggestions": ["improvement 1", "improvement 2"]
}}"""
        
        result = await self.pro.generate_json(prompt)

        # Trust the AI's judgment - only override if it didn't provide approval field
        if "approved" not in result:
            # Fallback: Set approval based on thresholds
            approved = (
                result.get("specificity", 0) >= 4 and
                result.get("completeness", 0) >= 4 and
                result.get("ambiguity", 10) <= 7
            )
            result["approved"] = approved

        return result
