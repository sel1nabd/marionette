#!/bin/bash
# Run Marionette demos

cd "$(dirname "$0")"
source .venv/bin/activate
export PYTHONPATH=/Users/bugatt/Downloads/marionette
python3 examples/demo.py
