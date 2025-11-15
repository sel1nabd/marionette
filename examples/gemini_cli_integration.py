#!/usr/bin/env python3
"""
Example: Integrating Marionette with Gemini CLI
This shows how to wrap Gemini CLI with Marionette supervision.
"""

import asyncio
import subprocess
import sys
from pathlib import Path

from orchestrator.marionette import Marionette
from orchestrator.config import Config


class GeminiCLIWrapper:
    """Wraps Gemini CLI with Marionette supervision."""

    def __init__(self, marionette: Marionette):
        self.marionette = marionette
        self.gemini_process = None

    async def start(self):
        """Start Gemini CLI process with supervision."""
        print("🎭 Starting Gemini CLI with Marionette supervision...")

        # Start Marionette
        await self.marionette.start()

        # Start Gemini CLI as subprocess
        try:
            self.gemini_process = await asyncio.create_subprocess_exec(
                "gemini",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Start monitoring tasks
            asyncio.create_task(self._monitor_stdout())
            asyncio.create_task(self._monitor_stderr())

            print("✅ Gemini CLI started with Marionette supervision")

        except FileNotFoundError:
            print("❌ gemini CLI not found. Install it first:")
            print("   npm install -g @google/generative-ai-cli")
            sys.exit(1)

    async def send_prompt(self, user_input: str):
        """Send user input through Marionette then to Gemini CLI."""
        # Check prompt quality
        check = await self.marionette.process_user_input(user_input)

        if not check["approved"]:
            print("\n⚠️ PROMPT REJECTED BY MARIONETTE")
            print(f"Feedback: {check['feedback']}")
            for suggestion in check.get('suggestions', []):
                print(f"  • {suggestion}")
            return False

        # Send to Gemini CLI
        if self.gemini_process and self.gemini_process.stdin:
            self.gemini_process.stdin.write(f"{user_input}\n".encode())
            await self.gemini_process.stdin.drain()
        return True

    async def _monitor_stdout(self):
        """Monitor Gemini CLI output and send through Marionette."""
        if not self.gemini_process or not self.gemini_process.stdout:
            return

        async for line in self.gemini_process.stdout:
            output = line.decode().strip()
            if output:  # Skip empty lines
                print(f"🤖 Gemini: {output}")

                # Process through Marionette
                interventions = await self.marionette.process_agent_output(output)

                # Check for warnings
                for warning in interventions.get("warnings", []):
                    print(f"\n⚠️ {warning}")

                # Kill agent if needed
                if interventions.get("kill_agent"):
                    print("\n🛑 MARIONETTE KILLED AGENT - Debug loop detected")
                    self.gemini_process.kill()

                    print("\n💡 Marionette's suggestions:")
                    for suggestion in interventions.get("suggestions", []):
                        print(f"  • {suggestion}")

    async def _monitor_stderr(self):
        """Monitor errors from Gemini CLI."""
        if not self.gemini_process or not self.gemini_process.stderr:
            return

        async for line in self.gemini_process.stderr:
            error = line.decode().strip()
            if error:  # Skip empty lines
                print(f"❌ Error: {error}")

                # Process as error
                await self.marionette.process_agent_output(error, is_error=True)

    async def interactive_loop(self):
        """Run interactive session with supervision."""
        print("\n" + "="*60)
        print("🎭 Marionette + Gemini CLI Interactive Session")
        print("="*60)
        print("Commands:")
        print("  /exit   - Exit the session")
        print("  /status - Show Marionette status")
        print("  /help   - Show this help")
        print("="*60 + "\n")

        while True:
            try:
                user_input = input("👤 You: ").strip()

                if user_input == "/exit":
                    print("\n👋 Exiting...")
                    break

                if user_input == "/status":
                    status = self.marionette.get_status()
                    print(f"\n📊 Marionette Status:")
                    print(f"  Session ID: {status['session_id']}")
                    print(f"  User Inputs: {status['user_inputs']}")
                    print(f"  Agent Outputs: {status['agent_outputs']}")
                    continue

                if user_input == "/help":
                    print("\nCommands:")
                    print("  /exit   - Exit the session")
                    print("  /status - Show Marionette status")
                    print("  /help   - Show this help")
                    continue

                if user_input:
                    await self.send_prompt(user_input)

            except KeyboardInterrupt:
                print("\n\n👋 Interrupted...")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")

        # Cleanup
        if self.gemini_process:
            self.gemini_process.kill()
        await self.marionette.shutdown()


async def main():
    """Run Gemini CLI with Marionette supervision."""
    config = Config.from_env()
    marionette = Marionette(config)

    wrapper = GeminiCLIWrapper(marionette)
    await wrapper.start()
    await wrapper.interactive_loop()


if __name__ == "__main__":
    asyncio.run(main())
