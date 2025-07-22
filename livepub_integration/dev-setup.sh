#!/bin/bash

# CoastSat LivePublication Development Environment Setup Script
# This script sets up the development environment for the CoastSat LivePublication integration

set -e

echo "🚀 Setting up CoastSat LivePublication development environment..."

# Check if we're in the right directory
if [ ! -f "requirements.txt" ]; then
    echo "❌ Error: requirements.txt not found. Please run this script from the project root."
    exit 1
fi

# Check if Python virtual environment exists
if [ ! -d ".venv" ]; then
    echo "⚠️  Virtual environment not found. Please run the Python configuration first."
    exit 1
fi

# Create necessary directories
echo "📁 Creating necessary directories..."
mkdir -p livepub_integration/micropub_requests
mkdir -p livepub_integration/micropub_tmp
mkdir -p livepub_integration/shoreline_requests
mkdir -p livepub_integration/shoreline_tmp

# Check if services can be started
echo "🔍 Checking service dependencies..."

# Test if Python packages are installed
.venv/bin/python -c "import flask, flask_cors, watchdog, requests" 2>/dev/null || {
    echo "❌ Missing Python dependencies. Please install requirements.txt"
    exit 1
}

echo "✅ All dependencies are available!"

echo "📋 LivePublication development environment setup complete!"
echo ""
echo "🎯 Quick start commands:"
echo "  1. Start micropublication service: python livepub_integration/micropub_watcher.py"
echo "  2. Start shoreline publication service: python livepub_integration/shorelinepub_watcher.py"
echo "  3. Serve the web interface: python -m http.server 8000"
echo "  4. Open Jupyter Lab: jupyter lab"
echo ""
echo "📖 Web interface will be available at: http://localhost:8000"
echo "🔬 Jupyter Lab will be available at: http://localhost:8888"
echo "🌐 Micropublication service: http://localhost:8765"
echo "🗺️  Shoreline publication service: http://localhost:8766"
echo ""
echo "💡 Use VS Code tasks panel to start all services with one click!"
echo "📚 See DEV_ENVIRONMENT.md for detailed documentation!"
