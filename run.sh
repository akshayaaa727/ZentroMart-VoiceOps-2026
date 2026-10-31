#!/bin/bash
set -e
cd "$(dirname "$0")"
source .venv/bin/activate
python run.py "${1:-sample_audio}"
