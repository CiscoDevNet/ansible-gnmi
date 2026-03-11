# AGENTS.md – cisco.gnmi Ansible Collection

## Dev environment tips

- **Python version**: Use Python 3.9+.
- **Virtual env (recommended)**:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
pip install -r requirements.txt
```

### Quick run examples

```bash
# Install the collection from source
ansible-galaxy collection build
ansible-galaxy collection install cisco-gnmi-*.tar.gz --force

# Run a gNMI GET playbook
ansible-playbook examples/playbooks/test_device.yml -i test_inventory.ini

# Run unit tests
PYTHONPATH="$HOME/.ansible/collections:$PYTHONPATH" python -m pytest tests/unit/ -v
```

## Testing instructions

- **Run unit tests**:

```bash
python -m pytest tests/unit/ -v
```

- **Run integration playbooks** (requires a gNMI-enabled device):

```bash
# Update test_inventory.ini with your device IP, credentials, and CA cert path
ansible-playbook examples/playbooks/test_device.yml -i test_inventory.ini
```

- **Test the code with the Cisco DevNet sandbox**

  Visit https://devnetsandbox.cisco.com/DevNet to book a related sandbox.

- **Latest Cisco gNMI documentation**:

  - gNMI specification: https://github.com/openconfig/gnmi
  - Cisco IOS-XE gNMI configuration guide: https://www.cisco.com/c/en/us/td/docs/ios-xml/ios/prog/configuration/1710/b_1710_programmability_cg/grpc_network_management_interface.html

## PR instructions

- **Security**: Do not commit real credentials, device IPs, or tokens. Use
  placeholders and document required env vars or files.
- **Protobuf files**: Do not hand-edit files ending in `_pb2.py` or
  `_pb2_grpc.py` — they are auto-generated from `.proto` definitions.
- **SPDX headers**: All new Python source files must include the Cisco
  copyright and SPDX license header.

## Contribution conventions

- **Backward compatibility**: Do not change existing module parameters or
  return values unless clearly improving or fixing a bug; document changes
  in CHANGELOG.md.
- **Testing**: Include unit tests for new functionality. All tests must pass
  before submitting a PR.
- **Naming**: Follow Ansible collection conventions — FQCN is `cisco.gnmi.gnmi`.
