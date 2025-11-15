#!/usr/bin/env python3
"""
Example: Integrating Marionette with Gemini CLI
Plan-Then-Execute pattern: Validate prompts upfront, then let Gemini run freely.
Monitor output and intervene only on critical issues.
"""

import asyncio
import sys
import os
import pty
import select
from pathlib import Path

from orchestrator.marionette import Marionette
from orchestrator.config import Config


class GeminiCLIWrapper:
    """
    Hybrid supervision:
    - ACTIVE on input: Block bad prompts before reaching Gemini
    - PASSIVE on output: Monitor and warn, only kill on critical issues
    """

    def __init__(self, marionette: Marionette):
        self.marionette = marionette
        self.gemini_process = None
        self.master_fd = None
        self.pending_input_buffer = []
        self.agent_output_buffer = []
        self.waiting_for_approval = False

    async def start(self):
        """Start both Marionette and Gemini CLI."""
        print("🎭 Starting Marionette supervision layer...\n")
        await self.marionette.start()

        print("═" * 70)
        print("""
    ╭─────────╮
    │  ╭───╮  │     🎭 Marionette + Gemini CLI
    │  │ ◠ ◠│  │
    │  │  ▽ │  │     Active Input Validation + Passive Monitoring
    │  ╰───╯  │
    ╰─────────╯
        """)
        print("═" * 70)
        print("\n✨ ACTIVE: Validates prompts before reaching Gemini")
        print("✨ PASSIVE: Monitors output, intervenes on critical issues")
        print("✨ Press Ctrl+D to exit\n")
        print("─" * 70 + "\n")

        # Start Gemini CLI in YOLO mode
        print("🚀 Starting Gemini CLI in YOLO mode...\n")

        try:
            # Start gemini CLI with pty for full interactive support
            master, slave = pty.openpty()
            self.master_fd = master

            self.gemini_process = await asyncio.create_subprocess_exec(
                "gemini",
                "--yolo",
                stdin=slave,
                stdout=slave,
                stderr=slave,
                cwd=os.getcwd()
            )

            os.close(slave)

            # Start monitoring tasks
            asyncio.create_task(self._monitor_output())
            asyncio.create_task(self._handle_input())

            # Wait for process to exit
            await self.gemini_process.wait()

            os.close(master)

        except FileNotFoundError:
            print("❌ Gemini CLI not found. Install it:\n")
            print("   npm install -g @google/gemini-cli\n")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Error: {e}\n")
            sys.exit(1)

    async def _handle_input(self):
        """
        ACTIVE VALIDATION:
        Intercept user input, validate with Marionette BEFORE sending to Gemini.
        """
        input_line_buffer = []

        while True:
            try:
                # Read from stdin
                ready, _, _ = select.select([sys.stdin], [], [], 0.1)
                if ready:
                    data = os.read(sys.stdin.fileno(), 1024)
                    if not data:
                        break

                    text = data.decode('utf-8', errors='ignore')

                    # If not waiting for approval, forward everything immediately
                    if not self.waiting_for_approval:
                        # Accumulate until we see a newline
                        for char in text:
                            if char in ['\n', '\r']:
                                # Got a complete line
                                user_input = ''.join(input_line_buffer).strip()

                                # Check if this looks like a command/prompt (not just navigation)
                                if user_input and not user_input.startswith(('y', 'n', 'q')):
                                    # Validate BEFORE sending
                                    self.waiting_for_approval = True
                                    approved = await self._validate_prompt(user_input)
                                    self.waiting_for_approval = False

                                    if not approved:
                                        # Blocked! User needs to try again
                                        input_line_buffer = []
                                        continue

                                # Approved or non-command input - send to Gemini
                                os.write(self.master_fd, ''.join(input_line_buffer).encode() + char.encode())
                                input_line_buffer = []
                            else:
                                input_line_buffer.append(char)
                                # Echo character immediately for responsiveness
                                os.write(self.master_fd, char.encode())
                    else:
                        # Waiting for approval, buffer input
                        self.pending_input_buffer.append(text)

                await asyncio.sleep(0.01)

            except Exception as e:
                print(f"Input error: {e}")
                break

    async def _validate_prompt(self, user_input: str) -> bool:
        """
        ACTIVE VALIDATION:
        Check prompt quality BEFORE it reaches Gemini.
        Returns True if approved, False if rejected.
        """
        try:
            # Restore terminal for proper output during validation
            import termios
            import tty
            old_settings = termios.tcgetattr(sys.stdin)
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

            print("\n🔍 Marionette validating prompt...", end='', flush=True)

            check = await self.marionette.process_user_input(user_input)

            if not check["approved"]:
                print(" ❌ REJECTED\n")
                print("⚠️  PROMPT QUALITY ISSUE\n")
                print(f"   {check['feedback']}\n")
                if check.get('suggestions'):
                    print("   💡 Suggestions:")
                    for suggestion in check.get('suggestions', []):
                        print(f"      • {suggestion}")
                print("\n   Please improve your prompt and try again.\n")

                # Reset to raw mode
                tty.setraw(sys.stdin.fileno())
                return False
            else:
                print(" ✅ APPROVED\n")

                # Reset to raw mode
                tty.setraw(sys.stdin.fileno())
                return True

        except Exception as e:
            print(f"Validation error: {e}")
            return True  # On error, let it through

    async def _monitor_output(self):
        """
        PASSIVE MONITORING:
        Watch Gemini's output, only intervene on critical issues.
        """
        output_buffer = []

        while True:
            try:
                ready, _, _ = select.select([self.master_fd], [], [], 0.1)
                if ready:
                    data = os.read(self.master_fd, 1024)
                    if not data:
                        break

                    # Forward to stdout immediately (transparent)
                    os.write(sys.stdout.fileno(), data)
                    sys.stdout.flush()

                    # Accumulate for Marionette analysis
                    text = data.decode('utf-8', errors='ignore')
                    output_buffer.append(text)

                    # Analyze periodically
                    if len(output_buffer) > 20:
                        await self._analyze_output(''.join(output_buffer))
                        output_buffer = []

                await asyncio.sleep(0.01)

            except Exception as e:
                break

    async def _analyze_output(self, agent_output: str):
        """
        ACTIVE ANALYSIS:
        Check for issues and INTERVENE by interrupting and correcting Gemini.
        """
        try:
            interventions = await self.marionette.process_agent_output(agent_output)

            # Check for context drift
            if any("context drift" in w.lower() for w in interventions.get("warnings", [])):
                await self._interrupt_and_correct("context_drift", interventions)

            # Check for sycophancy
            if any("sycophancy" in w.lower() or "overly agreeable" in w.lower() for w in interventions.get("warnings", [])):
                await self._interrupt_and_correct("sycophancy", interventions)

            # CRITICAL: Kill agent on debug loop
            if interventions.get("kill_agent"):
                import termios
                old_settings = termios.tcgetattr(sys.stdin)
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

                print("\n🛑 MARIONETTE KILLING AGENT - DEBUG LOOP DETECTED!")
                print("   Agent is stuck in a repetitive error pattern\n")

                if interventions.get("suggestions"):
                    print("   💡 Try this instead:")
                    for suggestion in interventions.get("suggestions", []):
                        print(f"      • {suggestion}")
                    print()

                if self.gemini_process:
                    self.gemini_process.kill()

                import tty
                tty.setraw(sys.stdin.fileno())

        except Exception as e:
            pass  # Silent fail on monitoring errors

    async def _interrupt_and_correct(self, issue_type: str, interventions: dict):
        """
        ACTIVE INTERVENTION:
        Send Ctrl+C to interrupt Gemini, then inject corrective prompt.
        """
        try:
            import termios
            import tty
            old_settings = termios.tcgetattr(sys.stdin)
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

            print("\n⚠️  MARIONETTE INTERVENING - INTERRUPTING GEMINI")
            print(f"   Detected: {issue_type.replace('_', ' ').title()}")

            # Send Ctrl+C to interrupt current operation
            print("   Sending Ctrl+C...", flush=True)
            os.write(self.master_fd, b'\x03')  # Ctrl+C is ASCII 0x03
            await asyncio.sleep(0.5)  # Wait for interruption to register

            # Build corrective prompt based on issue type
            if issue_type == "context_drift":
                # Get initial goal from Marionette
                status = self.marionette.get_status()
                initial_goal = getattr(self.marionette, 'initial_goal', None)

                correction = "\n\n⚠️ CORRECTION: You are drifting from the original goal. "
                if initial_goal:
                    correction += f"Remember, our initial plan was: {initial_goal}. "
                correction += "Please refocus on the original requirements.\n"

            elif issue_type == "sycophancy":
                correction = "\n\n⚠️ CORRECTION: Be critical and provide rational judgment. Do not attempt to please the user. You are encouraged to genuinely agree AND disagree when appropriate. Provide honest technical assessment.\n"

            else:
                correction = "\n\n⚠️ CORRECTION: Please reconsider your approach.\n"

            print(f"   Injecting correction...\n")
            print(f"   {correction.strip()}\n")

            # Send the correction to Gemini
            os.write(self.master_fd, correction.encode())
            os.write(self.master_fd, b'\n')

            await asyncio.sleep(0.3)

            # Reset to raw mode
            tty.setraw(sys.stdin.fileno())

        except Exception as e:
            print(f"   Intervention error: {e}")
            import tty
            tty.setraw(sys.stdin.fileno())


async def main():
    """Run Gemini CLI with hybrid Marionette supervision."""
    config = Config.from_env()
    marionette = Marionette(config)

    wrapper = GeminiCLIWrapper(marionette)

    try:
        await wrapper.start()
    except KeyboardInterrupt:
        print("\n\n👋 Exiting...\n")
    finally:
        await marionette.shutdown()


if __name__ == "__main__":
    # Set terminal to raw mode for proper interactive experience
    import termios
    import tty

    old_settings = termios.tcgetattr(sys.stdin)
    try:
        tty.setraw(sys.stdin.fileno())
        asyncio.run(main())
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
