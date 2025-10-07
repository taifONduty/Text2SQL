#!/bin/bash
# Quick start script for Text2SQL Analytics System

set -e

echo "======================================================================"
echo "  Text2SQL Analytics System - Quick Setup"
echo "======================================================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "  Found Python $python_version"

# Create virtual environment
echo ""
echo "${YELLOW}Step 1: Creating virtual environment...${NC}"
python3 -m venv venv
source venv/bin/activate

echo "${GREEN}✓ Virtual environment created${NC}"

# Install dependencies
echo ""
echo "${YELLOW}Step 2: Installing dependencies...${NC}"
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

echo "${GREEN}✓ Dependencies installed${NC}"

# Check for .env file
echo ""
echo "${YELLOW}Step 3: Checking environment configuration...${NC}"

if [ ! -f .env ]; then
    echo "  Creating .env from template..."
    cp env.example .env
    echo "${YELLOW}  ⚠ Please edit .env and add your credentials:${NC}"
    echo "    - GEMINI_API_KEY (get from https://ai.google.dev/)"
    echo "    - DB_ADMIN_PASSWORD (your PostgreSQL password)"
    echo ""
    echo "  Then run this script again or continue manually with:"
    echo "    python scripts/setup_database.py"
    exit 0
fi

echo "${GREEN}✓ .env file found${NC}"

# Verify setup
echo ""
echo "${YELLOW}Step 4: Verifying setup...${NC}"
python scripts/verify_setup.py

echo ""
echo "======================================================================"
echo "${GREEN}  Setup Complete!${NC}"
echo "======================================================================"
echo ""
echo "Next steps:"
echo "  1. Download data: python scripts/download_northwind.py"
echo "  2. Setup database: python scripts/setup_database.py"
echo "  3. Run tests: make test"
echo "  4. Try interactive mode: python -m src.cli"
echo ""
echo "Documentation:"
echo "  • Quick start: QUICKSTART.md"
echo "  • Full docs: README.md"
echo "  • Setup checklist: SETUP_CHECKLIST.md"
echo ""

