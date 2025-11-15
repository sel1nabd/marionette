"""Gemini API client for Flash and Pro models."""

import google.generativeai as genai
from typing import Dict, List, Optional, AsyncIterator
import json


class GeminiClient:
    """Wrapper for Gemini API with streaming and grounding support."""
    
    def __init__(self, api_key: str, model_name: str):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)
        self.model_name = model_name
    
    async def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        grounding: bool = False,
        temperature: float = 0.7
    ) -> str:
        """
        Generate a response from Gemini.
        
        Args:
            prompt: User prompt
            system_instruction: System instructions for model behavior
            grounding: Enable Google Search grounding
            temperature: Sampling temperature
        """
        config = genai.GenerationConfig(
            temperature=temperature,
            candidate_count=1
        )
        
        # Build tools list
        tools = []
        if grounding:
            try:
                from google.generativeai import grounding
                tools.append(grounding.GoogleSearchRetrieval())
            except (ImportError, AttributeError):
                # Grounding not available in this API version
                tools = []
        
        try:
            if system_instruction:
                model = genai.GenerativeModel(
                    self.model_name,
                    system_instruction=system_instruction,
                    tools=tools if tools else None
                )
            else:
                model = self.model if not tools else genai.GenerativeModel(
                    self.model_name,
                    tools=tools
                )
            
            response = model.generate_content(
                prompt,
                generation_config=config
            )
            
            return response.text
        
        except Exception as e:
            print(f"❌ Gemini API error ({self.model_name}): {e}")
            return f"Error: {str(e)}"
    
    async def generate_json(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        grounding: bool = False
    ) -> Dict:
        """
        Generate a JSON response from Gemini.
        Forces JSON output format.
        """
        json_prompt = f"{prompt}\n\nRespond ONLY with valid JSON. No markdown, no explanation."
        
        response = await self.generate(
            json_prompt,
            system_instruction=system_instruction,
            grounding=grounding,
            temperature=0.3  # Lower temp for structured output
        )
        
        # Extract JSON from response (handle markdown code blocks)
        response = response.strip()
        if response.startswith("```json"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]
        
        try:
            return json.loads(response.strip())
        except json.JSONDecodeError as e:
            print(f"⚠️ Failed to parse JSON response: {e}")
            print(f"Response was: {response}")
            return {"error": "Invalid JSON response", "raw": response}
    
    async def stream_generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None
    ) -> AsyncIterator[str]:
        """
        Stream response from Gemini (for real-time monitoring).
        """
        try:
            if system_instruction:
                model = genai.GenerativeModel(
                    self.model_name,
                    system_instruction=system_instruction
                )
            else:
                model = self.model
            
            response = model.generate_content(
                prompt,
                stream=True
            )
            
            for chunk in response:
                if chunk.text:
                    yield chunk.text
        
        except Exception as e:
            yield f"Error: {str(e)}"
    
    async def count_tokens(self, text: str) -> int:
        """Count tokens in text using Gemini's tokenizer."""
        try:
            result = self.model.count_tokens(text)
            return result.total_tokens
        except:
            # Fallback estimation
            return len(text) // 4
