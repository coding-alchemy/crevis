#!/bin/bash
cd "$(dirname "$0")"
# Activate the virtual environment
source .venv/bin/activate
python python/video_generator.py
