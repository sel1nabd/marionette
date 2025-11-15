#!/usr/bin/env python3
"""
Example: Integrating Marionette with Claude Code
This shows how to wrap an existing CLI coding agent with Marionette supervision.
"""

import asyncio
import subprocess
import sys
from pathlib import Path

from orchestrator.marionette import Marionette
from orchestrator.config import Config


class ClaudeCodeWrapper:
    """Wraps Claude Code with Marionette supervision."""
    
    def __init__(self, marionette: Marionette):
        self.marionette = marionette
        self.claude_process = None
    
    async def start(self):
        """Start Claude Code process with supervision."""
        print("🎭 Starting Claude Code with Marionette supervision...")
        
        # Start Marionette
        await self.marionette.start()
        
        # Start Claude Code as subprocess
        # Note: This is a conceptual example - actual implementation depends on
        # how your CLI agent accepts input/output
        
        try:
            self.claude_process = await asyncio.create_subprocess_exec(
                "claude-code",  # or "aider", etc.
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Start monitoring tasks
            asyncio.create_task(self._monitor_stdout())
            asyncio.create_task(self._monitor_stderr())
            
        except FileNotFoundError:
            print("❌ claude-code not found. Install it first:")
            print("   pip install claude-code")
            sys.exit(1)
    
    async def send_prompt(self, user_input: str):
        """Send user input through Marionette then to Claude Code."""
        # Check prompt quality
        check = await self.marionette.process_user_input(user_input)
        
        if not check["approved"]:
            print("\n⚠️ PROMPT REJECTED BY MARIONETTE")
            print(f"Feedback: {check['feedback']}")
            for suggestion in check.get('suggestions', []):
                print(f"  • {suggestion}")
            return False
        
        # Send to Claude Code
        self.claude_process.stdin.write(f"{user_input}\n".encode())
        await self.claude_process.stdin.drain()
        return True
    
    async def _monitor_stdout(self):
        """Monitor Claude Code output and send through Marionette."""
        async for line in self.claude_process.stdout:
            output = line.decode().strip()
            print(f"🤖 Claude: {output}")
            
            # Process through Marionette
            interventions = await self.marionette.process_agent_output(output)
            
            if interventions.get("kill_agent"):
                print("\n🛑 MARIONETTE KILLED AGENT - Debug loop detected")
                self.claude_process.kill()
                
                for suggestion in interventions.get("suggestions", []):
                    print(suggestion)
    
    async def _monitor_stderr(self):
        """Monitor errors from Claude Code."""
        async for line in self.claude_process.stderr:
            error = line.decode().strip()
            print(f"❌ Error: {error}")
            
            # Process as error
            await self.marionette.process_agent_output(error, is_error=True)
    
    async def interactive_loop(self):
        """Run interactive session with supervision."""
        while True:
            try:
                user_input = input("\n👤 You: ").strip()
                
                if user_input == "/exit":
                    break
                
                if user_input == "/status":
                    status = self.marionette.get_status()
                    print(f"\n📊 Session: {status['session_id']}")
                    print(f"Interactions: {status['user_inputs']}")
                    continue
                
                await self.send_prompt(user_input)
                
            except KeyboardInterrupt:
                break
        
        # Cleanup
        if self.claude_process:
            self.claude_process.kill()
        await self.marionette.shutdown()


async def main():
    """Run Claude Code with Marionette supervision."""
    config = Config.from_env()
    marionette = Marionette(config)
    
    wrapper = ClaudeCodeWrapper(marionette)
    await wrapper.start()
    await wrapper.interactive_loop()


if __name__ == "__main__":
    asyncio.run(main())
