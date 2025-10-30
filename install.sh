#!/bin/bash
# Installation script for Cisco IOS XE gNMI Ansible Collection

set -e

echo "======================================"
echo "Cisco IOS XE gNMI Collection Installer"
echo "======================================"
echo ""

# Check Python version
echo "Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "Found Python $PYTHON_VERSION"

PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 8 ]); then
    echo "ERROR: Python 3.8 or higher is required"
    echo "Current version: $PYTHON_VERSION"
    exit 1
fi

echo "✓ Python version OK"
echo ""

# Check if virtual environment should be created
read -p "Create virtual environment? (recommended) [Y/n] " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
    echo ""

    echo "Activating virtual environment..."
    source venv/bin/activate
    echo "✓ Virtual environment activated"
    echo ""
fi

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip setuptools wheel
echo "✓ pip upgraded"
echo ""

# Install dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt
echo "✓ Dependencies installed"
echo ""

# Install collection
echo "Installing Ansible collection..."
ansible-galaxy collection install . --force
echo "✓ Collection installed"
echo ""

# Verify installation
echo "Verifying installation..."
if ansible-doc cisco.iosxe_gnmi.cisco_iosxe_gnmi &>/dev/null; then
    echo "✓ Installation verified successfully"
else
    echo "⚠ Warning: Could not verify installation"
fi
echo ""

echo "======================================"
echo "Installation Complete!"
echo "======================================"
echo ""
echo "Next steps:"
echo "1. Enable gNMI on your Cisco IOS XE device"
echo "2. Update examples/inventory.ini with your device details"
echo "3. Run example playbooks:"
echo "   ansible-playbook -i examples/inventory.ini examples/get_operations.yml"
echo ""
echo "Documentation:"
echo "- README.md - Complete documentation"
echo "- CISCO_GNMI_CAVEATS.md - Cisco-specific requirements"
echo "- examples/ - Example playbooks"
echo ""
echo "For help: ansible-doc cisco.iosxe_gnmi.cisco_iosxe_gnmi"
echo ""
