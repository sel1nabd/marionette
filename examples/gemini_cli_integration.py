#!/usr/bin/env python3
"""
Example: Integrating Marionette with Gemini CLI
Simply pastes text between terminals using AppleScript/pbcopy.
"""

import asyncio
import sys
import os
from pathlib import Path
import tempfile
import subprocess
import time

from orchestrator.marionette import Marionette
from orchestrator.config import Config


class GeminiCLIPaster:
    """
    Simple approach:
    1. Launch Gemini CLI in separate terminal
    2. When user types prompt -> validate -> paste into Gemini terminal
    3. User manually copies Gemini output -> we display it
    """

    def __init__(self, marionette: Marionette):
        self.marionette = marionette
        self.log_file = Path(tempfile.mktemp(suffix=".log"))
        self.gemini_window_id = None

    async def start(self):
        """Start Marionette and Gemini CLI in new terminal."""
        print("🎭 Starting Marionette supervision...\n")
        await self.marionette.start()

        print("═" * 70)
        print("""
    ╭─────────╮
    │  ╭───╮  │     🎭 Marionette + Gemini CLI
    │  │ ◠ ◠│  │
    │  │  ▽ │  │     Terminal pasting bridge
    │  ╰───╯  │
    ╰─────────╯
        """)
        print("═" * 70)
        print("\n✨ ACTIVE: Validates prompts before pasting to Gemini")
        print("✨ PASSIVE: Monitors what you paste back from Gemini")
        print("\nCommands:")
        print("  /exit    Exit the session")
        print("  /status  Show Marionette statistics")
        print("\n" + "─" * 70 + "\n")

        # Launch Gemini CLI in new terminal
        print("🚀 Launching Gemini CLI in new terminal...\n")

        try:
            # Create script that runs Gemini and logs output
            script_file = Path(tempfile.mktemp(suffix=".sh"))
            script_file.write_text(f'''#!/bin/bash
# Simple Gemini CLI with logging

# Create working directory if it doesn't exist
mkdir -p /Users/bugatt/Downloads/marionette/GEMINI_CLI
cd /Users/bugatt/Downloads/marionette/GEMINI_CLI

echo "🎭 Gemini CLI (Supervised by Marionette)"
echo "📁 Working directory: $(pwd)"
echo ""

# Run Gemini CLI with output logging
gemini --yolo 2>&1 | tee "{self.log_file}"
''')
            script_file.chmod(0o755)

            # macOS: use osascript to open new Terminal window
            applescript = f'''
tell application "Terminal"
    set newWindow to do script "{script_file}"
    set windowID to id of window 1
    activate
end tell
return windowID
'''
            result = subprocess.run(
                ['osascript', '-e', applescript],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                self.gemini_window_id = result.stdout.strip()
                print(f"✅ Gemini CLI launched (Window ID: {self.gemini_window_id})")
            else:
                print("✅ Gemini CLI launched")

            print(f"📝 Output log: {self.log_file}\n")

            # Wait for Gemini to start
            await asyncio.sleep(3)

            # Start log monitor
            asyncio.create_task(self._monitor_log())

            print("Ready! Type your prompts below.\n")

        except Exception as e:
            print(f"❌ Error: {e}\n")
            import traceback
            traceback.print_exc()

    async def _monitor_log(self):
        """Monitor Gemini's output log file."""
        last_size = 0
        output_buffer = []

        while True:
            try:
                if self.log_file.exists():
                    current_size = self.log_file.stat().st_size

                    if current_size > last_size:
                        with open(self.log_file, 'r') as f:
                            f.seek(last_size)
                            new_content = f.read()

                            if new_content.strip():
                                lines = new_content.strip().split('\n')
                                for line in lines:
                                    # Filter out noise
                                    if line.strip() and not any(skip in line for skip in [
                                        "YOLO mode",
                                        "Loaded cached",
                                        "🎭 Gemini CLI"
                                    ]):
                                        print(f"🤖 {line}")
                                        output_buffer.append(line)

                                # Analyze accumulated output
                                if len(output_buffer) > 10:
                                    await self._analyze_output('\n'.join(output_buffer))
                                    output_buffer = []

                        last_size = current_size

                await asyncio.sleep(0.5)

            except Exception:
                await asyncio.sleep(1)

    async def _analyze_output(self, agent_output: str):
        """Monitor for issues."""
        try:
            interventions = await self.marionette.process_agent_output(agent_output)

            # Check for context drift
            if any("context drift" in w.lower() for w in interventions.get("warnings", [])):
                print("\n⚠️  MARIONETTE: Context drift detected!")
                print("    Suggested correction to paste:")
                print("    '⚠️ You are drifting from the original goal. Please refocus.'\n")

            # Check for sycophancy
            if any("sycophancy" in w.lower() or "overly agreeable" in w.lower()
                   for w in interventions.get("warnings", [])):
                print("\n⚠️  MARIONETTE: Sycophancy detected!")
                print("    Suggested correction to paste:")
                print("    '⚠️ Be critical. You are encouraged to genuinely disagree.'\n")

            # CRITICAL: Kill on debug loop
            if interventions.get("kill_agent"):
                print("\n🛑 MARIONETTE: Debug loop detected!")
                if interventions.get("suggestions"):
                    print("    💡 Suggestions:")
                    for suggestion in interventions.get("suggestions", []):
                        print(f"       • {suggestion}")
                print("\n    Close the Gemini terminal to stop.\n")

        except Exception:
            pass

    async def _paste_to_gemini(self, text: str):
        """Paste text into Gemini CLI terminal."""
        try:
            # Put text in clipboard
            subprocess.run(['pbcopy'], input=text.encode(), check=True)

            # Activate Terminal and paste using System Events
            applescript = f'''
tell application "Terminal"
    activate
    set frontmost to true
end tell

delay 0.3

tell application "System Events"
    tell process "Terminal"
        keystroke "v" using command down
        delay 0.1
        keystroke return
    end tell
end tell
'''
            subprocess.run(['osascript', '-e', applescript], check=False)

            print("📋 Pasted to Gemini CLI\n")

        except Exception as e:
            print(f"❌ Paste failed: {e}")
            print(f"📋 Please manually paste this into Gemini terminal:\n{text}\n")

    async def interactive_loop(self):
        """Clean chatbox interface."""

        print("💡 Tip: Focus stays on this terminal. Gemini window will auto-activate when pasting.\n")

        while True:
            try:
                # Get user input (stays in this terminal, no cmd+tab interference)
                user_input = input("👤 You: ").strip()

                if user_input == "/exit":
                    print("\n👋 Goodbye! (Close the Gemini terminal manually)\n")
                    break

                if user_input == "/status":
                    status = self.marionette.get_status()
                    print(f"\n📊 Marionette Status:")
                    print(f"   Session ID:     {status['session_id']}")
                    print(f"   User Inputs:    {status['user_inputs']}")
                    print(f"   Agent Outputs:  {status['agent_outputs']}\n")
                    continue

                if not user_input:
                    continue

                # Validate prompt with Marionette
                print("🔍 Validating...", end=' ', flush=True)
                check = await self.marionette.process_user_input(user_input)

                if not check["approved"]:
                    print("❌ REJECTED\n")
                    print("⚠️  Prompt quality issue:")
                    print(f"   {check['feedback']}\n")
                    if check.get('suggestions'):
                        print("   💡 Suggestions:")
                        for suggestion in check.get('suggestions', []):
                            print(f"      • {suggestion}")
                    print()
                    continue

                print("✅ APPROVED")

                # Try to paste to Gemini
                if self.gemini_window_id:
                    await self._paste_to_gemini(user_input)
                else:
                    # Fallback: just copy to clipboard
                    subprocess.run(['pbcopy'], input=user_input.encode())
                    print("📋 Copied to clipboard - paste into Gemini terminal (Cmd+V)\n")

            except KeyboardInterrupt:
                print("\n\n👋 Interrupted. Goodbye!\n")
                break
            except EOFError:
                print("\n\n👋 EOF. Goodbye!\n")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}\n")

        # Cleanup
        await self.marionette.shutdown()


async def main():
    """Run Gemini CLI paster with Marionette supervision."""
    config = Config.from_env()
    marionette = Marionette(config)

    paster = GeminiCLIPaster(marionette)
    await paster.start()
    await paster.interactive_loop()


if __name__ == "__main__":
    asyncio.run(main())
