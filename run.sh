#!/bin/bash
cd "$(dirname "$0")"
# Activate the virtual environment
source .venv/bin/activate
# Add python directory to PYTHONPATH for imports
export PYTHONPATH="$PWD/python:$PYTHONPATH"
# Pass all arguments to the new CLI
python python/main.py "$@"
