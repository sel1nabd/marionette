#!/usr/bin/env python3
"""
Marionette wrapper for Claude Code CLI using tmux + tee architecture.

Architecture:
1. Launch Claude Code in tmux session
2. Stream output to log file via tee
3. Monitor log file for issues (drift, sycophancy, debug loops)
4. Send keystrokes via tmux send-keys (Ctrl-C, Esc, prompts)
5. Validate user prompts before injection
"""

import asyncio
import subprocess
import tempfile
from pathlib import Path
import os
import sys
import time
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestrator.marionette import Marionette
from orchestrator.config import Config


class ClaudeCodeWrapper:
    """
    Wraps Claude Code CLI in tmux with full supervision.

    Features:
    - Deterministic keystroke injection via tmux send-keys
    - Real-time output monitoring via tee log file
    - Prompt validation before sending to Claude
    - Detection and intervention (Ctrl-C to stop, Esc to break loops)
    """

    def __init__(self, marionette: Marionette):
        self.marionette = marionette
        self.session_name = f"marionette_claude_{os.getpid()}"
        self.log_file = Path(tempfile.mktemp(suffix=".log", prefix="claude_output_"))
        self.running = False
        self.last_log_position = 0

        # Intervention state
        self.loop_detected = False
        self.drift_detected = False

    async def start(self):
        """Launch Claude Code in tmux and start monitoring."""
        print("🎭 Marionette - Claude Code Supervisor")
        print("=" * 60)
        print(f"📋 Session: {self.session_name}")
        print(f"📝 Log file: {self.log_file}")
        print(f"🔧 Working directory: {os.getcwd()}")
        print("=" * 60)
        print()

        # Create tmux session with Claude Code
        self._launch_claude_in_tmux()

        self.running = True

        # Start monitoring tasks
        monitor_task = asyncio.create_task(self._monitor_output())
        interaction_task = asyncio.create_task(self._user_interaction_loop())

        try:
            await asyncio.gather(monitor_task, interaction_task)
        except KeyboardInterrupt:
            print("\n\n🛑 Shutting down Marionette...")
            await self.cleanup()

    def _launch_claude_in_tmux(self):
        """Launch Claude Code CLI inside a tmux session with tee logging."""

        # Kill existing session if it exists
        subprocess.run(
            ["tmux", "kill-session", "-t", self.session_name],
            capture_output=True
        )

        # Create new tmux session with persistent bash first
        # This ensures the session stays alive and stdin remains open
        try:
            # Step 1: Create tmux session with bash
            result = subprocess.run([
                "tmux", "new-session", "-d", "-s", self.session_name,
                "-x", "120", "-y", "40",
                "bash"
            ], capture_output=True, text=True)

            if result.returncode != 0:
                print(f"❌ Failed to create tmux session: {result.stderr}")
                return

            # Step 2: Set up logging pipe and launch Claude
            # We need to keep Claude interactive, so we use process substitution
            # to tee output while maintaining the interactive session
            # Using --dangerously-skip-permissions to avoid permission prompts
            subprocess.run([
                "tmux", "send-keys", "-t", self.session_name,
                f"script -q {self.log_file} claude --dangerously-skip-permissions", "C-m"
            ], check=False)

            # Give Claude time to start
            time.sleep(1)

            # Verify session exists
            check = subprocess.run(
                ["tmux", "list-sessions"],
                capture_output=True,
                text=True
            )

            if self.session_name in check.stdout:
                print(f"✅ Claude Code launched in tmux session: {self.session_name}")
                print(f"   View session: tmux attach -t {self.session_name}")
                print()
            else:
                print(f"⚠️  Session created but not found in list.")
                print()

        except Exception as e:
            print(f"❌ Error launching tmux: {e}")

    async def _monitor_output(self):
        """Monitor Claude Code output log file for issues."""
        import re
        output_buffer = []
        last_analysis_time = datetime.now()
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        seen_lines = set()  # Deduplicate repeated lines

        while self.running:
            try:
                if self.log_file.exists():
                    file_size = self.log_file.stat().st_size

                    if file_size > self.last_log_position:
                        with open(self.log_file, 'r', encoding='utf-8', errors='ignore') as f:
                            f.seek(self.last_log_position)
                            new_content = f.read()

                            if new_content.strip():
                                # Strip ANSI escape codes
                                clean_content = ansi_escape.sub('', new_content)
                                lines = clean_content.strip().split('\n')

                                for line in lines:
                                    stripped = line.strip()

                                    # Skip if we've seen this exact line recently
                                    if stripped in seen_lines:
                                        continue

                                    # Aggressive filtering for UI noise
                                    skip_patterns = [
                                        '────────', '? for shortcuts', 'Thinking off', 'ctrl-g to edit',
                                        '/ide for VS Code', '╭───', '╰───', '│', 'Mulling', 'Creating',
                                        'Blanching', 'Harmonizing', '(esc to interrupt', 'running stop hook',
                                        '> Try', '> hi', '> ', '[G', '⎿  Tip:', '⎿  Next:',
                                        'Use /statusline', 'Create HTML structure',
                                        'Create file', 'Write(', 'Read(', 'Edit(',
                                        '⏵⏵', 'shift+'  # Permission toggles and shortcuts
                                    ]

                                    # Loading spinners (NOT including ⏺ which is Claude's response marker)
                                    spinner_chars = ['✢', '✳', '✶', '✻', '✽', '·']

                                    if any(skip in stripped for skip in skip_patterns):
                                        continue

                                    if any(char in stripped and len(stripped) < 50 for char in spinner_chars):
                                        continue

                                    # Special handling for ⏺ (Claude's response marker)
                                    if stripped.startswith('⏺'):
                                        response_text = stripped[1:].strip()
                                        if response_text and len(response_text) > 10:
                                            print(f"🤖 {response_text}")
                                            output_buffer.append(response_text)
                                            seen_lines.add(response_text)
                                        continue

                                    # Skip short lines that start with > (prompt echo)
                                    if stripped.startswith('>') and len(stripped) < 100:
                                        continue

                                    # Only show substantial, meaningful lines
                                    if len(stripped) > 20 and not stripped.startswith('>'):
                                        # Avoid duplicate prints
                                        if stripped not in seen_lines:
                                            print(f"🤖 {stripped}")
                                            output_buffer.append(stripped)
                                            seen_lines.add(stripped)

                                            # Keep seen_lines from growing forever
                                            if len(seen_lines) > 100:
                                                seen_lines.clear()

                        self.last_log_position = file_size

                        # Analyze accumulated output every 8 seconds for faster detection
                        now = datetime.now()
                        if (now - last_analysis_time).seconds >= 8 and len(output_buffer) > 3:
                            # Analyze if we have meaningful content
                            await self._analyze_output('\n'.join(output_buffer))
                            output_buffer = []
                            last_analysis_time = now

                await asyncio.sleep(0.5)

            except Exception as e:
                print(f"⚠️  Monitor error: {e}")
                await asyncio.sleep(1)

    async def _analyze_output(self, output: str):
        """Analyze Claude's output for issues and intervene if needed."""
        try:
            # Check for debug loops
            loop_result = await self.marionette.debug_loop_monitor.check(
                [{"error": output}]  # Pass as error history format
            )

            if loop_result.get('detected'):
                print("\n" + "=" * 60)
                print("🔴 DEBUG LOOP DETECTED!")
                print(f"   Reason: {loop_result.get('reason', 'unknown')}")
                print("   → Sending Esc Esc to break loop...")
                print("=" * 60 + "\n")

                self.loop_detected = True
                self._send_escape_sequence()

            # Check for context drift (if we have learned the initial goal)
            if self.marionette.context_drift_monitor.initial_goal:
                drift_result = await self.marionette.context_drift_monitor.check(
                    recent_actions=[output]
                )

                if drift_result.get('drifted'):
                    print("\n" + "=" * 60)
                    print("⚠️  CONTEXT DRIFT DETECTED!")
                    print(f"   Reason: {drift_result.get('reason', 'unknown')}")
                    print("   → Intervening: Going back to previous prompt and adding drift warning...")
                    print("=" * 60 + "\n")
                    self.drift_detected = True
                    await self._intervene_context_drift()

            # Check for sycophancy
            sycophancy_result = await self.marionette.sycophancy_detector.check(
                output
            )

            if sycophancy_result.get('detected'):
                print("\n" + "=" * 60)
                print("⚠️  SYCOPHANCY DETECTED!")
                print(f"   Reason: {sycophancy_result.get('reason', 'unknown')}")
                print("   → Intervening: Going back to previous prompt and adding critical thinking reminder...")
                print("=" * 60 + "\n")
                await self._intervene_sycophancy()

        except Exception as e:
            print(f"⚠️  Analysis error: {e}")

    async def _user_interaction_loop(self):
        """Handle user input with validation before sending to Claude."""
        print("💬 Type your prompts below (validated by Marionette before sending)")
        print("   Commands: /stop = Ctrl-C, /escape = Esc Esc, /quit = exit\n")

        while self.running:
            try:
                # Get user input in a non-blocking way
                user_prompt = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: input("You: ").strip()
                )

                if not user_prompt:
                    continue

                # Handle special commands
                if user_prompt == "/quit":
                    print("👋 Exiting Marionette...")
                    self.running = False
                    break

                elif user_prompt == "/stop":
                    print("🛑 Sending Ctrl-C to Claude Code...")
                    self._send_ctrl_c()
                    continue

                elif user_prompt == "/escape":
                    print("⎋ Sending Esc Esc to Claude Code...")
                    self._send_escape_sequence()
                    continue

                # Validate prompt quality
                print("🔍 Validating prompt...")
                quality_result = await self.marionette.prompt_quality.analyze(
                    user_prompt
                )

                if not quality_result.get('approved', True):
                    print("\n" + "=" * 60)
                    print("❌ PROMPT QUALITY INSUFFICIENT")
                    print(f"   Specificity: {quality_result.get('specificity', 0)}/10")
                    print(f"   Completeness: {quality_result.get('completeness', 0)}/10")
                    print(f"   Ambiguity: {quality_result.get('ambiguity', 10)}/10")

                    if quality_result.get('suggestions'):
                        print("\n   💡 Suggestions:")
                        for suggestion in quality_result['suggestions']:
                            print(f"      • {suggestion}")

                    print("=" * 60 + "\n")
                    print("Please rephrase your prompt with more detail.\n")
                    continue

                # Learn project context from early prompts
                if len(user_prompt) > 50:
                    await self.marionette.context_drift_monitor.learn_initial_goal([user_prompt])

                # Send to Claude Code via tmux
                print("✅ Prompt approved, sending to Claude Code...\n")
                self._send_text(user_prompt)

            except EOFError:
                # Handle Ctrl-D
                self.running = False
                break
            except Exception as e:
                print(f"❌ Error: {e}")

    def _send_text(self, text: str):
        """Send text to Claude Code via tmux send-keys."""
        # Check if session exists
        check = subprocess.run(
            ["tmux", "list-sessions"],
            capture_output=True,
            text=True
        )

        if check.returncode != 0 or self.session_name not in check.stdout:
            print(f"⚠️  tmux session '{self.session_name}' not found. Recreating...")
            self._launch_claude_in_tmux()

        # Escape special characters for tmux
        escaped_text = text.replace('"', '\\"')

        # Send the text (no Enter yet - Claude Code needs text input first)
        result = subprocess.run([
            "tmux", "send-keys", "-t", self.session_name,
            "-l",  # Literal mode - don't interpret keys
            text
        ], capture_output=True, text=True)

        if result.returncode != 0:
            print(f"❌ Failed to send text to tmux: {result.stderr}")
            return

        # Now send Enter twice with a small delay to submit
        # First Enter completes the input, second Enter submits the prompt
        subprocess.run([
            "tmux", "send-keys", "-t", self.session_name,
            "C-m"
        ], check=False)

        time.sleep(0.2)  # Small delay to let Claude process the first Enter

        subprocess.run([
            "tmux", "send-keys", "-t", self.session_name,
            "C-m"
        ], check=False)

    def _send_ctrl_c(self):
        """Send Ctrl-C to Claude Code to interrupt current operation."""
        subprocess.run([
            "tmux", "send-keys", "-t", self.session_name,
            "C-c"
        ], check=False)

    def _send_escape_sequence(self):
        """Send Esc Esc to Claude Code to break loops."""
        subprocess.run([
            "tmux", "send-keys", "-t", self.session_name,
            "Escape", "Escape"
        ], check=False)

    async def _intervene_context_drift(self):
        """Intervene when context drift is detected by going back and adding a warning."""
        print("🔄 Intervention: Pausing Claude, going back to previous prompt, adding context drift warning...")

        # Step 1: Press Esc to pause
        subprocess.run([
            "tmux", "send-keys", "-t", self.session_name,
            "Escape"
        ], check=False)
        time.sleep(1)

        # Step 2: Double Esc with delay
        subprocess.run([
            "tmux", "send-keys", "-t", self.session_name,
            "Escape"
        ], check=False)
        time.sleep(0.2)
        subprocess.run([
            "tmux", "send-keys", "-t", self.session_name,
            "Escape"
        ], check=False)

        # Step 3: Press arrow up to get previous prompt
        subprocess.run([
            "tmux", "send-keys", "-t", self.session_name,
            "Up"
        ], check=False)

        # Step 4: Press Enter
        subprocess.run([
            "tmux", "send-keys", "-t", self.session_name,
            "C-m"
        ], check=False)
        time.sleep(0.5)

        # Step 5: Press Enter again
        subprocess.run([
            "tmux", "send-keys", "-t", self.session_name,
            "C-m"
        ], check=False)
        time.sleep(0.5)

        # Step 6: Write the context drift warning
        warning_text = "Be aware of context drift at the end. Revise your main goal, state at the TOP, then revise your course of action. Ensure it aligns"
        subprocess.run([
            "tmux", "send-keys", "-t", self.session_name,
            "-l",
            warning_text
        ], check=False)

        # Step 7: Press Enter to send
        subprocess.run([
            "tmux", "send-keys", "-t", self.session_name,
            "C-m"
        ], check=False)
        time.sleep(0.2)
        subprocess.run([
            "tmux", "send-keys", "-t", self.session_name,
            "C-m"
        ], check=False)

        print("✅ Context drift intervention complete")

    async def _intervene_sycophancy(self):
        """Intervene when sycophancy is detected by going back and adding a critical thinking reminder."""
        print("🔄 Intervention: Pausing Claude, going back to previous prompt, adding critical thinking reminder...")

        # Step 1: Press Esc to pause
        subprocess.run([
            "tmux", "send-keys", "-t", self.session_name,
            "Escape"
        ], check=False)
        time.sleep(1)

        # Step 2: Double Esc with delay
        subprocess.run([
            "tmux", "send-keys", "-t", self.session_name,
            "Escape"
        ], check=False)
        time.sleep(0.2)
        subprocess.run([
            "tmux", "send-keys", "-t", self.session_name,
            "Escape"
        ], check=False)

        # Step 3: Press arrow up to get previous prompt
        subprocess.run([
            "tmux", "send-keys", "-t", self.session_name,
            "Up"
        ], check=False)

        # Step 4: Press Enter
        subprocess.run([
            "tmux", "send-keys", "-t", self.session_name,
            "C-m"
        ], check=False)
        time.sleep(0.5)

        # Step 5: Press Enter again
        subprocess.run([
            "tmux", "send-keys", "-t", self.session_name,
            "C-m"
        ], check=False)
        time.sleep(0.5)

        # Step 6: Write the sycophancy warning
        warning_text = "Be critical. Don't be sycophantic. Feel free to agree or disagree."
        subprocess.run([
            "tmux", "send-keys", "-t", self.session_name,
            "-l",
            warning_text
        ], check=False)

        # Step 7: Press Enter to send
        subprocess.run([
            "tmux", "send-keys", "-t", self.session_name,
            "C-m"
        ], check=False)
        time.sleep(0.2)
        subprocess.run([
            "tmux", "send-keys", "-t", self.session_name,
            "C-m"
        ], check=False)

        print("✅ Sycophancy intervention complete")

    async def cleanup(self):
        """Clean up tmux session and log file."""
        self.running = False

        # Kill tmux session
        subprocess.run([
            "tmux", "kill-session", "-t", self.session_name
        ], capture_output=True)

        print(f"🧹 Cleaned up session: {self.session_name}")

        # Optionally keep log file
        if self.log_file.exists():
            print(f"📝 Log file saved: {self.log_file}")


async def main():
    """Main entry point."""
    # Initialize Marionette
    config = Config.from_env()
    marionette = Marionette(config)
    await marionette.start()

    # Create wrapper and start
    wrapper = ClaudeCodeWrapper(marionette)
    await wrapper.start()


if __name__ == "__main__":
    asyncio.run(main())
