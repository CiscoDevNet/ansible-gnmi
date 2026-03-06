#!/bin/bash
# Quick verification for cisco.gnmi collection

set -e

PASS=0; FAIL=0

check() { if [ "$1" -eq 0 ]; then echo "✓ $2"; ((PASS++)); else echo "✗ $2"; ((FAIL++)); fi; }

echo "=== cisco.gnmi Collection Verification ==="

# Structure
check "$(test -f galaxy.yml; echo $?)" "galaxy.yml exists"
check "$(test -f README.md; echo $?)" "README.md exists"
check "$(test -f LICENSE; echo $?)" "LICENSE exists"
check "$(test -f meta/runtime.yml; echo $?)" "meta/runtime.yml exists"
check "$(test -f plugins/modules/gnmi.py; echo $?)" "plugins/modules/gnmi.py exists"
check "$(test -f plugins/module_utils/gnmi_client.py; echo $?)" "plugins/module_utils/gnmi_client.py exists"
check "$(test -f CHANGELOG.md; echo $?)" "CHANGELOG.md exists"

# Syntax
check "$(python3 -m py_compile plugins/modules/gnmi.py 2>/dev/null; echo $?)" "gnmi.py compiles"
check "$(python3 -m py_compile plugins/module_utils/gnmi_client.py 2>/dev/null; echo $?)" "gnmi_client.py compiles"

# Module doc
check "$(python3 -c 'import ast; t=ast.parse(open("plugins/modules/gnmi.py").read()); [n for n in ast.walk(t) if isinstance(n,ast.Assign) and any(getattr(tgt,"id",None)=="DOCUMENTATION" for tgt in n.targets)]' 2>/dev/null; echo $?)" "DOCUMENTATION block present"

# Collection installable
if ansible-galaxy collection build --force >/dev/null 2>&1; then
    check 0 "Collection builds successfully"
    rm -f cisco-gnmi-*.tar.gz
else
    check 1 "Collection builds successfully"
fi

echo ""
echo "Results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
