#!/usr/bin/env python3
"""
Example: Integrating Marionette with Gemini CLI
This shows how to wrap Gemini CLI with Marionette supervision.
Gemini CLI runs in YOLO mode to actually execute and create files.
"""

import asyncio
import sys
import os
from pathlib import Path

from orchestrator.marionette import Marionette
from orchestrator.config import Config


class GeminiCLIWrapper:
    """Wraps Gemini CLI with Marionette supervision."""

    def __init__(self, marionette: Marionette):
        self.marionette = marionette
        self.gemini_process = None

    async def start(self):
        """Start Marionette and Gemini CLI."""
        print("🎭 Starting Marionette supervision with Gemini CLI...\n")
        await self.marionette.start()
        print("✅ Marionette ready\n")

    async def send_prompt(self, user_input: str):
        """Send user input through Marionette then to Gemini CLI."""
        # Check prompt quality
        check = await self.marionette.process_user_input(user_input)

        if not check["approved"]:
            print("\n⚠️  PROMPT REJECTED BY MARIONETTE\n")
            print(f"   {check['feedback']}\n")
            if check.get('suggestions'):
                print("   Suggestions:")
                for suggestion in check.get('suggestions', []):
                    print(f"   • {suggestion}")
            print()
            return False

        # Send to Gemini CLI in YOLO mode (auto-approve all actions)
        print("\n🤖 Gemini CLI is working...\n")

        try:
            # Run gemini CLI with the prompt in YOLO mode
            process = await asyncio.create_subprocess_exec(
                "gemini",
                "--yolo",  # Auto-approve all tool calls
                "--prompt", user_input,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=os.getcwd()
            )

            # Read output line by line
            full_output = []

            async def read_stream(stream, prefix=""):
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    text = line.decode().strip()
                    if text:
                        print(f"   {text}")
                        full_output.append(text)

            # Read both stdout and stderr
            await asyncio.gather(
                read_stream(process.stdout),
                read_stream(process.stderr)
            )

            # Wait for process to complete
            await process.wait()

            print()  # Add spacing

            # Process through Marionette
            output_text = "\n".join(full_output)
            if output_text:
                interventions = await self.marionette.process_agent_output(output_text)

                # Check for warnings
                if interventions.get("warnings"):
                    print("⚠️  MARIONETTE WARNINGS:\n")
                    for warning in interventions.get("warnings", []):
                        print(f"   {warning}\n")

                # Check for suggestions
                if interventions.get("suggestions"):
                    print("💡 MARIONETTE SUGGESTIONS:\n")
                    for suggestion in interventions.get("suggestions", []):
                        print(f"   • {suggestion}\n")

                # Check if we should kill the agent
                if interventions.get("kill_agent"):
                    print("🛑 MARIONETTE WOULD KILL AGENT (but process already completed)\n")

        except FileNotFoundError:
            print("❌ Gemini CLI not found. Make sure it's installed:\n")
            print("   npm install -g @google/gemini-cli\n")
            return False
        except Exception as e:
            print(f"❌ Error: {e}\n")
            return False

        return True

    async def interactive_loop(self):
        """Run interactive session with supervision."""
        # Print cute puppet art
        print("\n" + "═" * 70)
        print("""
    ╭─────────╮
    │  ╭───╮  │     🎭 Marionette + Gemini CLI Interactive Session
    │  │ ◠ ◠│  │
    │  │  ▽ │  │     Gemini CLI with real-time supervision
    │  ╰───╯  │
    ╰─────────╯
        """)
        print("═" * 70)
        print("\n✨ Gemini CLI will ACTUALLY create files and run commands")
        print("✨ Marionette watches for loops, drift, and sycophancy\n")
        print("Commands:")
        print("  /exit    Exit the session")
        print("  /status  Show Marionette statistics")
        print("  /help    Show this help message")
        print("\n" + "─" * 70 + "\n")

        while True:
            try:
                user_input = input("👤 You: ").strip()

                if user_input == "/exit":
                    print("\n👋 Goodbye!\n")
                    break

                if user_input == "/status":
                    status = self.marionette.get_status()
                    print("\n📊 MARIONETTE STATUS\n")
                    print(f"   Session ID:     {status['session_id']}")
                    print(f"   User Inputs:    {status['user_inputs']}")
                    print(f"   Agent Outputs:  {status['agent_outputs']}")
                    print()
                    continue

                if user_input == "/help":
                    print("\n📖 HELP\n")
                    print("   Commands:")
                    print("   /exit    Exit the session")
                    print("   /status  Show Marionette statistics")
                    print("   /help    Show this help message")
                    print()
                    continue

                if user_input:
                    await self.send_prompt(user_input)

            except KeyboardInterrupt:
                print("\n\n👋 Interrupted. Goodbye!\n")
                break
            except EOFError:
                print("\n\n👋 EOF received. Goodbye!\n")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}\n")

        # Cleanup
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
