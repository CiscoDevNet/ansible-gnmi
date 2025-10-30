#!/bin/bash
# Verification script for Cisco IOS XE gNMI Ansible Collection

echo "=============================================="
echo "Cisco IOS XE gNMI Collection - Verification"
echo "=============================================="
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Counters
PASS=0
FAIL=0
WARN=0

# Check function
check() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✓${NC} $2"
        ((PASS++))
    else
        echo -e "${RED}✗${NC} $2"
        ((FAIL++))
    fi
}

warn() {
    echo -e "${YELLOW}⚠${NC} $1"
    ((WARN++))
}

echo "Checking Python environment..."
python3 --version > /dev/null 2>&1
check $? "Python 3 installed"

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
python3 -c 'import sys; exit(0 if sys.version_info >= (3, 8) else 1)' 2>/dev/null
check $? "Python version >= 3.8 (found $PYTHON_VERSION)"

echo ""
echo "Checking Python dependencies..."
python3 -c 'import grpc' 2>/dev/null
check $? "grpcio installed"

python3 -c 'import google.protobuf' 2>/dev/null
check $? "protobuf installed"

python3 -c 'import cryptography' 2>/dev/null
check $? "cryptography installed"

python3 -c 'import ansible' 2>/dev/null
check $? "ansible-core installed"

echo ""
echo "Checking Ansible installation..."
ansible --version > /dev/null 2>&1
check $? "Ansible CLI available"

ansible-galaxy collection list | grep -q iosxe_gnmi 2>/dev/null
if [ $? -eq 0 ]; then
    check 0 "Collection installed in galaxy"
else
    warn "Collection not installed via ansible-galaxy (may be in development)"
fi

echo ""
echo "Checking core files..."
[ -f "plugins/modules/cisco_iosxe_gnmi.py" ]
check $? "Module file exists"

[ -f "plugins/module_utils/gnmi_client.py" ]
check $? "Module utility exists"

[ -f "galaxy.yml" ]
check $? "Galaxy metadata exists"

[ -f "requirements.txt" ]
check $? "Requirements file exists"

echo ""
echo "Checking documentation..."
[ -f "README.md" ]
check $? "README.md exists"

[ -f "QUICKSTART.md" ]
check $? "QUICKSTART.md exists"

[ -f "CISCO_GNMI_CAVEATS.md" ]
check $? "CISCO_GNMI_CAVEATS.md exists"

[ -f "CONTRIBUTING.md" ]
check $? "CONTRIBUTING.md exists"

[ -f "CHANGELOG.md" ]
check $? "CHANGELOG.md exists"

echo ""
echo "Checking examples..."
[ -f "examples/get_operations.yml" ]
check $? "GET examples exist"

[ -f "examples/set_operations.yml" ]
check $? "SET examples exist"

[ -f "examples/subscribe_operations.yml" ]
check $? "Subscribe examples exist"

[ -f "examples/inventory.ini" ]
check $? "Inventory example exists"

echo ""
echo "Checking tests..."
[ -f "tests/unit/test_gnmi_client.py" ]
check $? "Client unit tests exist"

[ -f "tests/unit/test_cisco_iosxe_gnmi.py" ]
check $? "Module unit tests exist"

[ -f "pytest.ini" ]
check $? "Pytest config exists"

echo ""
echo "Checking development tools..."
[ -f "Makefile" ]
check $? "Makefile exists"

[ -f "install.sh" ]
check $? "Install script exists"

[ -x "install.sh" ]
check $? "Install script is executable"

echo ""
echo "Verifying module documentation..."
ansible-doc cisco.iosxe_gnmi.cisco_iosxe_gnmi > /dev/null 2>&1
if [ $? -eq 0 ]; then
    check 0 "Module documentation accessible"
else
    warn "Module documentation not accessible (may need to install collection first)"
fi

echo ""
echo "Running syntax checks..."
python3 -m py_compile plugins/modules/cisco_iosxe_gnmi.py 2>/dev/null
check $? "Module syntax valid"

python3 -m py_compile plugins/module_utils/gnmi_client.py 2>/dev/null
check $? "Client syntax valid"

echo ""
echo "Checking test dependencies..."
if [ -f "tests/requirements.txt" ]; then
    check 0 "Test requirements file exists"

    python3 -c 'import pytest' 2>/dev/null
    if [ $? -eq 0 ]; then
        check 0 "pytest installed"
    else
        warn "pytest not installed (run: pip install -r tests/requirements.txt)"
    fi
else
    warn "Test requirements file missing"
fi

echo ""
echo "=============================================="
echo "Verification Summary"
echo "=============================================="
echo -e "${GREEN}Passed:${NC}  $PASS"
echo -e "${RED}Failed:${NC}  $FAIL"
echo -e "${YELLOW}Warnings:${NC} $WARN"
echo ""

if [ $FAIL -eq 0 ]; then
    echo -e "${GREEN}✓ All critical checks passed!${NC}"
    echo ""
    echo "Project is ready for use."
    echo ""
    echo "Next steps:"
    echo "1. Review README.md for usage instructions"
    echo "2. Configure your device in examples/inventory.ini"
    echo "3. Run example playbooks"
    echo ""
    exit 0
else
    echo -e "${RED}✗ Some checks failed.${NC}"
    echo ""
    echo "Please install missing dependencies:"
    echo "  pip install -r requirements.txt"
    echo "  ansible-galaxy collection install . --force"
    echo ""
    exit 1
fi
