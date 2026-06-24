#!/bin/bash
# scripts/test.sh
# Runs the full test suite with coverage.
#
# USAGE:
#   ./scripts/test.sh

set -e
cd "$(dirname "$0")/.."

if [ -f "venv/Scripts/activate" ]; then
    source venv/Scripts/activate
elif [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

export PYTHONIOENCODING=utf-8
export PYTHONPATH=$(pwd)

echo "Running test suite..."
pytest tests/ --cov=agents --cov=shared --cov-report=term-missing -v