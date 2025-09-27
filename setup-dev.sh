#!/bin/bash
# Script to set up the development environment for the project.
# call this script from the project root directory, with ./setup-dev.sh
# Exit immediately if a command exits with a non-zero status.
set -e

echo "Starting project development environment setup..."

# Check if a virtual environment exists. If not, create one.
if [ ! -d ".venv" ]; then
    echo "Creating a new virtual environment in .venv..."
    python3 -m venv .venv
else
    echo "Virtual environment already exists. Skipping creation."
fi

# Activate the virtual environment to install dependencies
echo "Activating virtual environment to install dependencies..."
source .venv/bin/activate

# Upgrade pip and install/update dependencies from pyproject.toml in editable mode.
echo "Installing/updating dependencies from pyproject.toml..."
pip install --upgrade pip
pip install -e .

echo "Setup is complete. Now you're ready to start coding! ✨"
echo ""

# --- Interactive VS Code Prompt ---
read -p "Do you want to open this project in VS Code now? (y/n) " -n 1 -r
echo "" # Move to a new line
if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Start VS Code in the current directory
    code .
else
    # activate_venv:
    source .venv/bin/activate
    # Instructions to manually activate the venv:
    echo "If not done, to activate your development environment, run this command in your terminal:"
    echo "source .venv/bin/activate"
fi
