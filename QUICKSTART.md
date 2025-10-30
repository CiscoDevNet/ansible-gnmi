# Quick Start Guide - Cisco IOS XE gNMI Ansible Collection

Get up and running with the Cisco IOS XE gNMI Ansible Collection in 5 minutes.

## Prerequisites

- Python 3.8 or higher
- Cisco IOS XE device with gNMI enabled
- Network connectivity to the device

## Step 1: Install Dependencies (2 minutes)

```bash
# Clone or download the collection
git clone https://github.com/yourusername/ansible-gnmi.git
cd ansible-gnmi

# Run installation script (recommended)
chmod +x install.sh
./install.sh

# OR install manually:
pip install -r requirements.txt
ansible-galaxy collection install . --force
```

## Step 2: Enable gNMI on Your Device (1 minute)

Connect to your Cisco IOS XE device and run:

```cisco
configure terminal
gnmi-yang
 server
  port 9339
 !
!
username admin privilege 15 secret cisco123
end
```

Verify gNMI is running:
```cisco
show gnmi state
```

## Step 3: Create Your First Playbook (1 minute)

Create `my_first_gnmi.yml`:

```yaml
---
- name: My First gNMI Playbook
  hosts: localhost
  gather_facts: false

  tasks:
    - name: Get device hostname
      cisco.iosxe_gnmi.cisco_iosxe_gnmi:
        host: 192.168.1.1          # Your device IP
        username: admin
        password: cisco123
        operation: get
        paths:
          - /system/config/hostname
      register: result

    - name: Display hostname
      debug:
        var: result.data
```

## Step 4: Run Your Playbook (1 minute)

```bash
ansible-playbook my_first_gnmi.yml
```

Expected output:
```json
{
  "result.data": {
    "/system/config/hostname": "Router1"
  }
}
```

## Step 5: Try More Operations

### GET Interface Configuration

```yaml
- name: Get interface details
  cisco.iosxe_gnmi.cisco_iosxe_gnmi:
    host: 192.168.1.1
    username: admin
    password: cisco123
    operation: get
    paths:
      - /interfaces/interface[name=GigabitEthernet1]
  register: interface
```

### SET Interface Description

```yaml
- name: Configure interface
  cisco.iosxe_gnmi.cisco_iosxe_gnmi:
    host: 192.168.1.1
    username: admin
    password: cisco123
    operation: set
    state: present
    config:
      - path: /interfaces/interface[name=GigabitEthernet1]/config/description
        value: "Configured via gNMI"
```

### Subscribe to Statistics

```yaml
- name: Get interface statistics
  cisco.iosxe_gnmi.cisco_iosxe_gnmi:
    host: 192.168.1.1
    username: admin
    password: cisco123
    operation: subscribe
    subscribe_mode: once
    subscriptions:
      - path: /interfaces/interface[name=GigabitEthernet1]/state/counters
        mode: target_defined
  register: stats
```

## Common Use Cases

### Use Case 1: Check Interface Status

```yaml
- name: Check all interface status
  cisco.iosxe_gnmi.cisco_iosxe_gnmi:
    host: "{{ device_ip }}"
    username: "{{ username }}"
    password: "{{ password }}"
    operation: get
    paths:
      - /interfaces/interface/state/admin-status
      - /interfaces/interface/state/oper-status
  register: status

- name: Show interfaces that are down
  debug:
    msg: "Interface down: {{ item.key }}"
  loop: "{{ status.data | dict2items }}"
  when: "'down' in item.value | string | lower"
```

### Use Case 2: Backup Before Change

```yaml
- name: Configure with backup
  cisco.iosxe_gnmi.cisco_iosxe_gnmi:
    host: "{{ device_ip }}"
    username: "{{ username }}"
    password: "{{ password }}"
    operation: set
    state: present
    backup: yes
    backup_path: ./backups
    config:
      - path: /interfaces/interface[name=GigabitEthernet1]/config/mtu
        value: 9000
```

### Use Case 3: Safe Testing with Check Mode

```yaml
- name: Test configuration change
  cisco.iosxe_gnmi.cisco_iosxe_gnmi:
    host: "{{ device_ip }}"
    username: "{{ username }}"
    password: "{{ password }}"
    operation: set
    state: present
    config:
      - path: /system/config/hostname
        value: "NEW-HOSTNAME"
  check_mode: yes  # Won't actually make changes
```

## Next Steps

1. **Explore Examples**: Check out `examples/` directory for more playbooks
2. **Read Documentation**: See README.md for complete documentation
3. **Understand Cisco Specifics**: Review CISCO_GNMI_CAVEATS.md
4. **Run Tests**: `make test` to verify your setup
5. **Secure Your Setup**: Use ansible-vault for passwords

## Troubleshooting

### Can't Connect to Device

```bash
# Test connectivity
telnet <device-ip> 9339

# Verify gNMI is enabled
show gnmi state detail
```

### Module Not Found

```bash
# Reinstall collection
ansible-galaxy collection install . --force

# Verify installation
ansible-doc cisco.iosxe_gnmi.cisco_iosxe_gnmi
```

### Authentication Failed

- Verify username/password are correct
- Check user has privilege level 15
- Confirm gNMI service is running

### TLS Errors

```yaml
# For testing, use insecure mode (not for production!)
insecure: true
```

## Tips

💡 **Use Variables**: Store credentials in `group_vars/` with ansible-vault

💡 **Check Mode**: Always test with `--check` first

💡 **Diff Mode**: Use `--diff` to see what changed

💡 **Backups**: Enable backup for production changes

💡 **Encoding**: Use `json_ietf` encoding (recommended for IOS XE)

## Quick Reference

### Module Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `host` | Yes | - | Device IP/hostname |
| `username` | Yes | - | Username |
| `password` | Yes | - | Password |
| `operation` | No | get | get/set/subscribe |
| `encoding` | No | json_ietf | json/json_ietf/proto |
| `port` | No | 9339 | gNMI port |

### Common Paths

```yaml
# System
/system/config/hostname
/system/config/domain-name

# Interfaces
/interfaces/interface[name=GigabitEthernet1]/config
/interfaces/interface[name=GigabitEthernet1]/state

# All interfaces
/interfaces/interface
```

## Getting Help

- 📖 Full documentation: `README.md`
- 🐛 Report issues: GitHub Issues
- 💬 Community: Cisco DevNet
- 📝 Module docs: `ansible-doc cisco.iosxe_gnmi.cisco_iosxe_gnmi`

## Success! 🎉

You're now ready to manage Cisco IOS XE devices with gNMI using Ansible!

For production deployments, review:
- Security best practices (TLS, vault)
- Error handling strategies
- Backup and rollback procedures
- Monitoring and logging
