#!/bin/bash

echo "🔧 Setting up SignalSynth environment..."

# Create virtual environment
python -m venv venv
source venv/bin/activate || source venv/Scripts/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo "📦 Installing dependencies from requirements.txt..."
pip install -r requirements.txt

# Show installed packages
echo "✅ Installed packages:"
pip freeze

echo ""
echo "🎯 To activate this environment in the future:"
echo "   source venv/bin/activate  (Mac/Linux)"
echo "   .\\venv\\Scripts\\activate (Windows PowerShell)"
