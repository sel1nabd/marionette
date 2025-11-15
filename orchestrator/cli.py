"""CLI interface for Marionette orchestrator."""

import asyncio
from typing import Optional
from .marionette import Marionette


class CLI:
    """Interactive CLI for Marionette-supervised coding sessions."""
    
    def __init__(self, marionette: Marionette):
        self.marionette = marionette
        self.agent_process: Optional[asyncio.subprocess.Process] = None
    
    async def run(self):
        """Main CLI loop."""
        await self.marionette.start()
        
        print("\n🎭 Marionette is now watching your coding session")
        print("Commands:")
        print("  /status  - Show orchestrator status")
        print("  /stats   - Show detection statistics")
        print("  /kill    - Kill agent process")
        print("  /exit    - Exit Marionette")
        print("=" * 60)
        
        while True:
            try:
                user_input = input("\n👤 You: ").strip()
                
                if not user_input:
                    continue
                
                # Handle commands
                if user_input.startswith("/"):
                    await self._handle_command(user_input)
                    continue
                
                # Process user input through Marionette
                check = await self.marionette.process_user_input(user_input)
                
                if not check["approved"]:
                    print("\n⚠️ PROMPT QUALITY CHECK FAILED")
                    print(f"Feedback: {check['feedback']}")
                    print("\nSuggestions:")
                    for i, suggestion in enumerate(check.get('suggestions', []), 1):
                        print(f"  {i}. {suggestion}")
                    
                    retry = input("\nWould you like to rephrase? (y/n): ").lower()
                    if retry == 'y':
                        continue
                
                # In real usage, this would send to actual coding agent
                # For demo, we simulate agent response
                print("\n🤖 Agent: [Processing your request...]")
                
                # Simulate getting agent output
                agent_output = await self._simulate_agent_response(user_input)
                
                print(f"🤖 Agent: {agent_output}")
                
                # Process agent output through Marionette
                interventions = await self.marionette.process_agent_output(
                    agent_output,
                    is_error="error" in agent_output.lower()
                )
                
                # Display any interventions
                if interventions.get("warnings"):
                    print("\n⚠️ MARIONETTE WARNINGS:")
                    for warning in interventions["warnings"]:
                        print(f"  {warning}")
                
                if interventions.get("suggestions"):
                    print("\n💡 MARIONETTE SUGGESTIONS:")
                    for suggestion in interventions["suggestions"]:
                        print(f"  {suggestion}")
                
                if interventions.get("kill_agent"):
                    print("\n🛑 AGENT KILLED - Debug loop detected")
            
            except KeyboardInterrupt:
                print("\n\n👋 Use /exit to quit properly")
            except Exception as e:
                print(f"\n❌ Error: {e}")
    
    async def _handle_command(self, command: str):
        """Handle CLI commands."""
        cmd = command.lower()
        
        if cmd == "/status":
            status = self.marionette.get_status()
            print("\n📊 MARIONETTE STATUS")
            print(f"Session ID: {status['session_id']}")
            print(f"User inputs: {status['user_inputs']}")
            print(f"Agent outputs: {status['agent_outputs']}")
            print(f"Errors tracked: {status['errors_tracked']}")
        
        elif cmd == "/stats":
            status = self.marionette.get_status()
            print("\n📈 DETECTION STATISTICS")
            for monitor, stats in status['monitors'].items():
                print(f"\n{monitor.upper()}:")
                for key, value in stats.items():
                    print(f"  {key}: {value}")
        
        elif cmd == "/kill":
            if self.agent_process:
                self.agent_process.kill()
                print("🛑 Agent process killed")
            else:
                print("⚠️ No agent process running")
        
        elif cmd == "/exit":
            print("\n👋 Shutting down Marionette...")
            await self.marionette.shutdown()
            exit(0)
        
        else:
            print(f"❌ Unknown command: {command}")
    
    async def _simulate_agent_response(self, user_input: str) -> str:
        """
        Simulate agent response for demo purposes.
        In production, this would interface with actual coding agent.
        """
        # Simulate different response types for testing
        if "error" in user_input.lower():
            return "Error: File not found. Retrying with different path..."
        elif "great" in user_input.lower() or "perfect" in user_input.lower():
            return "You're absolutely right! That's a perfect approach. I'll implement exactly that."
        else:
            return f"I understand you want to: {user_input}. Let me implement that for you."


class AgentInterface:
    """
    Interface to actual coding agents (Claude Code, Aider, etc.)
    Replace the simulator above with real agent communication.
    """
    
    def __init__(self, agent_type: str = "claude-code"):
        self.agent_type = agent_type
        self.process = None
    
    async def start(self):
        """Start the coding agent process."""
        # Example: subprocess to run claude-code or aider
        # self.process = await asyncio.create_subprocess_exec(
        #     "claude-code",
        #     stdin=asyncio.subprocess.PIPE,
        #     stdout=asyncio.subprocess.PIPE,
        #     stderr=asyncio.subprocess.PIPE
        # )
        pass
    
    async def send_prompt(self, prompt: str) -> str:
        """Send prompt to agent and get response."""
        # Real implementation would communicate with agent
        pass
    
    async def kill(self):
        """Kill agent process."""
        if self.process:
            self.process.kill()
            await self.process.wait()
