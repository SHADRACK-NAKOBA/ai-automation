#!/bin/bash
# ============================================================
# setup.sh — One-time project setup script
# ============================================================
# Run this ONCE when you first clone the repo.
# It sets up your Python environment and creates needed directories.
#
# USAGE:
#   chmod +x scripts/setup.sh
#   ./scripts/setup.sh
# ============================================================

set -e  # Exit on any error

echo ""
echo "============================================================"
echo "  AI AUTOMATION PLATFORM — Environment Setup"
echo "============================================================"
echo ""

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "  Python version: $PYTHON_VERSION"
MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
if [ "$MAJOR" -lt 3 ] || ([ "$MAJOR" -eq 3 ] && [ "$MINOR" -lt 9 ]); then
    echo "  ❌ Python 3.9+ required. Please upgrade Python."
    exit 1
fi
echo "  ✅ Python version OK"

# Create virtual environment
if [ ! -d "venv" ]; then
    echo ""
    echo "  Creating virtual environment..."
    python3 -m venv venv
    echo "  ✅ Virtual environment created"
else
    echo "  ✅ Virtual environment already exists"
fi

# Activate and install
echo ""
echo "  Installing dependencies..."
source venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
echo "  ✅ Dependencies installed"

# Create data directories
echo ""
echo "  Creating data directories..."
mkdir -p data/synthetic data/logs
echo "  ✅ Directories created"

# Copy .env if not exists
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo ""
    echo "  ✅ Created .env from .env.example"
    echo ""
    echo "  ┌─────────────────────────────────────────────────────┐"
    echo "  │  ACTION REQUIRED: Edit your .env file               │"
    echo "  │                                                     │"
    echo "  │  1. Open .env in your editor                        │"
    echo "  │  2. Add your ANTHROPIC_API_KEY                      │"
    echo "  │  3. Add your SNOW_BASE_URL + SNOW_USERNAME +        │"
    echo "  │     SNOW_PASSWORD (from your PDI)                   │"
    echo "  │  4. Keep DRY_RUN=true until you're confident        │"
    echo "  └─────────────────────────────────────────────────────┘"
else
    echo "  ✅ .env already exists"
fi

# Seed synthetic data
echo ""
echo "  Seeding synthetic data..."
python tools/seed_data.py
echo "  ✅ Synthetic data ready"

echo ""
echo "============================================================"
echo "  Setup complete!"
echo ""
echo "  Next steps:"
echo "  1. Edit .env with your API keys (see note above)"
echo "  2. source venv/bin/activate"
echo "  3. python tools/test_connections.py"
echo "  4. python agents/ticket_classifier.py"
echo "============================================================"
echo ""
