#!/bin/bash
# scripts/run.sh
# Runs the Ticket Classifier. Pass --dry-run to preview without writing.
#
# USAGE:
#   ./scripts/run.sh
#   ./scripts/run.sh --dry-run

set -e
cd "$(dirname "$0")/.."

if [ -f "venv/Scripts/activate" ]; then
    source venv/Scripts/activate
elif [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

export PYTHONIOENCODING=utf-8
export PYTHONPATH=$(pwd)

if [ "$1" == "--dry-run" ]; then
    echo "DRY RUN mode — no writes to ServiceNow"
    export DRY_RUN=true
fi

python agents/ticket_classifier.py