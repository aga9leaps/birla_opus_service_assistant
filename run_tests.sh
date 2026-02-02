#!/bin/bash
# Birla Opus Chatbot - Test Runner

set -e

echo "=============================================="
echo "    Birla Opus Chatbot - Running Tests"
echo "=============================================="

# Change to project directory
cd "$(dirname "$0")"

# Create virtual environment if not exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -q -r requirements.txt

# Run tests with coverage
echo ""
echo "Running tests..."
echo "----------------------------------------------"

pytest tests/ -v \
    --tb=short \
    --cov=src \
    --cov=config \
    --cov-report=term-missing \
    --cov-report=html:coverage_report \
    -x  # Stop on first failure

# Check exit code
if [ $? -eq 0 ]; then
    echo ""
    echo "=============================================="
    echo "    All tests passed!"
    echo "=============================================="
    echo ""
    echo "Coverage report: coverage_report/index.html"
else
    echo ""
    echo "=============================================="
    echo "    Some tests failed!"
    echo "=============================================="
    exit 1
fi
