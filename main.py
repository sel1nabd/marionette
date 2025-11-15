#!/usr/bin/env python3
"""
Marionette - LLM Orchestration Layer for CLI Coding Agents
Watches user and agent, guides both using Gemini models for metacognitive supervision.
"""

import asyncio
import sys
from pathlib import Path

from orchestrator.marionette import Marionette
from orchestrator.config import Config
from orchestrator.cli import CLI


async def main():
    """Main entry point for Marionette orchestrator."""
    config = Config.from_env()
    
    # Initialize orchestrator
    marionette = Marionette(config)
    
    # Initialize CLI interface
    cli = CLI(marionette)
    
    print("🎭 Marionette Orchestrator v1.0")
    print("Watching your coding agent with Gemini-powered supervision")
    print("=" * 60)
    
    try:
        await cli.run()
    except KeyboardInterrupt:
        print("\n\n👋 Marionette shutting down...")
        await marionette.shutdown()
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        await marionette.shutdown()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
