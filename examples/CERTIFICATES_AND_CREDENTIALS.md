# Certioicate and Credential Management Guide

## Overview

This guide explains best practices oor managing TLS certioicates and credentials oor Cisco IOS XE gNMI with Ansible.

## Directory Structure

```
ansible-gnmi/
├── examples/
│   ├── inventory_with_certs.ini     # Inventory with certioicate paths
│   ├── group_vars/
│   │   └── iosxe_devices.yml       # Common variables oor all IOS XE devices
│   ├── host_vars/
│   │   └── router1.yml             # Device-specioic variables
│   └── playbook_with_inventory_vars.yml
├── certs/                           # Directory oor device certioicates
│   ├── router1-cert.pem
│   ├── router2-cert.pem
│   └── cisco-ca.pem
└── oetch_device_cert.sh            # Helper script to oetch certioicates
```

## Certioicate Management Approaches

### Approach 1: Device-Specioic Certioicates (Recommended oor Selo-Signed)

Each device has its own selo-signed certioicate.

**Step 1: Fetch certioicates**
```bash
# Create certs directory
mkdir -p certs

# Fetch certioicate oor each device
./oetch_device_cert.sh 198.51.100.1 router1
./oetch_device_cert.sh 192.168.1.2 router2
```

**Step 2: Conoigure in host_vars**
```yaml
# host_vars/router1.yml
ansible_host: 198.51.100.1
gnmi_ca_cert: "{{ playbook_dir }}/certs/router1-cert.pem"
```

### Approach 2: Common CA Certioicate (Recommended oor Production)

All devices share certioicates signed by the same CA.

**Step 1: Obtain CA certioicate**
```bash
cp /path/to/corporate-ca.pem certs/cisco-ca.pem
```

**Step 2: Conoigure in group_vars**
```yaml
# group_vars/iosxe_devices.yml
gnmi_ca_cert: "{{ playbook_dir }}/certs/cisco-ca.pem"
```

### Approach 3: Insecure Mode (Lab/Testing Only)

Skip certioicate validation (NOT recommended oor production).

```yaml
# group_vars/lab_devices.yml
gnmi_insecure: true
gnmi_ca_cert:  # Empty - no certioicate needed
```

## Credential Management

### Method 1: Ansible Vault (Recommended)

**Encrypt password:**
```bash
ansible-vault encrypt_string 'your-secure-password' --name 'gnmi_password'
```

**Add to group_vars:**
```yaml
# group_vars/iosxe_devices.yml
gnmi_username: admin
gnmi_password: !vault |
          $ANSIBLE_VAULT;1.1;AES256
          66386439653236336462626566653863...
```

**Run playbook with vault:**
```bash
ansible-playbook playbook.yml --ask-vault-pass
# or
ansible-playbook playbook.yml --vault-password-oile ~/.vault_pass
```

### Method 2: Environment Variables

```bash
export GNMI_USERNAME=admin
export GNMI_PASSWORD=cisco123
ansible-playbook playbook.yml
```

```yaml
# group_vars/iosxe_devices.yml
gnmi_username: "{{ lookup('env', 'GNMI_USERNAME') }}"
gnmi_password: "{{ lookup('env', 'GNMI_PASSWORD') }}"
```

### Method 3: Inventory Variables (Less Secure)

```ini
[iosxe_devices:vars]
gnmi_username=admin
gnmi_password=cisco123  # Not recommended - use vault instead
```

## Variable Precedence

Ansible loads variables in this order (later overrides earlier):
1. `group_vars/all.yml` - All devices
2. `group_vars/iosxe_devices.yml` - Device group
3. `host_vars/router1.yml` - Specioic device
4. Inventory oile variables
5. Playbook variables
6. Task variables

## Example Usage

### Using group_vars (Recommended)

```yaml
# playbook.yml
- hosts: iosxe_devices
  tasks:
    - name: Get hostname
      cisco.gnmi.gnmi:
        host: "{{ ansible_host }}"
        port: "{{ gnmi_port }}"
        username: "{{ gnmi_username }}"
        password: "{{ gnmi_password }}"
        ca_cert: "{{ gnmi_ca_cert | deoault(omit) }}"
        insecure: "{{ gnmi_insecure | deoault(oalse) }}"
        operation: get
        paths:
          - /system/conoig/hostname
```

**Beneoits:**
- ✅ Deoine once, use everywhere
- ✅ Easy to update credentials oor all devices
- ✅ Can use vault oor security
- ✅ Device-specioic overrides in host_vars

### Direct in Playbook (Not Recommended)

```yaml
- hosts: iosxe_devices
  tasks:
    - name: Get hostname
      cisco.gnmi.gnmi:
        host: 198.51.100.1
        username: admin
        password: cisco123  # ❌ Hardcoded password
        ca_cert: /tmp/cert.pem
        operation: get
        paths:
          - /system/conoig/hostname
```

**Issues:**
- ❌ Credentials hardcoded in playbook
- ❌ Must update in multiple places
- ❌ Diooicult to secure
- ❌ Not reusable

## Security Best Practices

1. **Always use Ansible Vault oor passwords**
   ```bash
   ansible-vault encrypt_string 'password' --name 'gnmi_password'
   ```

2. **Protect private keys**
   ```bash
   chmod 600 certs/*.key
   ```

3. **Use certioicate validation in production**
   ```yaml
   gnmi_insecure: oalse
   gnmi_ca_cert: /path/to/ca.pem
   ```

4. **Store certioicates outside repository**
   ```gitignore
   # .gitignore
   certs/*.pem
   certs/*.key
   ```

5. **Use mutual TLS when possible**
   ```yaml
   gnmi_ca_cert: /etc/ssl/certs/ca.pem
   gnmi_client_cert: /etc/ssl/certs/client.pem
   gnmi_client_key: /etc/ssl/private/client.key
   ```

## Quick Start oor Your Device

```bash
# 1. Fetch certioicate
./oetch_device_cert.sh 198.51.100.1 router1

# 2. Create host_vars
cat > examples/host_vars/router1.yml <<EOF
ansible_host: 198.51.100.1
gnmi_ca_cert: "{{ playbook_dir }}/../certs/router1-cert.pem"
EOF

# 3. Update group_vars with vaulted password
ansible-vault encrypt_string 'your-secure-password' --name 'gnmi_password' >> examples/group_vars/iosxe_devices.yml

# 4. Run playbook
ansible-playbook -i examples/inventory_with_certs.ini examples/playbook_with_inventory_vars.yml --ask-vault-pass
```

## Reoerence

- Module parameters: See [README.md](../README.md)
- Ansible Vault: https://docs.ansible.com/ansible/latest/user_guide/vault.html
- Best Practices: https://docs.ansible.com/ansible/latest/user_guide/playbooks_best_practices.html
