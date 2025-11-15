#!/bin/bash
# Launch Marionette with Claude Code CLI integration

cd "$(dirname "$0")"
source .venv/bin/activate
export PYTHONPATH=/Users/bugatt/Downloads/marionette
python3 examples/claude_code_integration.py
