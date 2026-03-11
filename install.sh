#!/bin/bash
# Copyright 2025 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

# Installation script for cisco.gnmi Ansible Collection

set -e

echo "======================================"
echo "cisco.gnmi Collection Installer"
echo "======================================"
echo ""

# Check Python version
echo "Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || { [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 9 ]; }; then
    echo "ERROR: Python 3.9 or higher is required (found $PYTHON_VERSION)"
    exit 1
fi
echo "✓ Python $PYTHON_VERSION"

# Install dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Build and install collection
echo "Building collection..."
ansible-galaxy collection build --force
echo "Installing collection..."
ansible-galaxy collection install cisco-gnmi-*.tar.gz --force

echo ""
echo "✓ Installation complete"
echo "  ansible-doc cisco.gnmi.gnmi"
