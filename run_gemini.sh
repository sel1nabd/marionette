#!/bin/bash
# Launch Marionette with Gemini CLI integration

cd "$(dirname "$0")"
source .venv/bin/activate
export PYTHONPATH=/Users/bugatt/Downloads/marionette
python3 examples/gemini_cli_integration.py
