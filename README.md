# Cisco IOS XE gNMI Ansible Collection

[![License](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)
[![Ansible](https://img.shields.io/badge/Ansible-2.12%2B-red)](https://www.ansible.com/)

A comprehensive Ansible collection for managing Cisco IOS XE devices using gNMI (gRPC Network Management Interface) protocol, providing feature parity with Ansible NETCONF/RESTCONF modules.

**Official Cisco Documentation:** [Cisco IOS XE Programmability Configuration Guide - gNMI Protocol](https://www.cisco.com/c/en/us/td/docs/ios-xml/ios/prog/configuration/1718/b-1718-programmability-cg/gnmi.html)

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Usage Examples](#usage-examples)
- [Module Documentation](#module-documentation)
- [Cisco IOS XE Caveats](#cisco-ios-xe-caveats)
- [Development](#development)
- [Testing](#testing)
- [Contributing](#contributing)
- [License](#license)

## Features

✅ **Complete gNMI Operations**
- GET: Retrieve configuration and operational state
- SET: Update, replace, and delete configurations

✅ **Ansible Best Practices**
- Idempotency support
- Check mode (dry-run)
- Diff mode (before/after comparison)
- Configuration backup
- Comprehensive error handling

✅ **Cisco IOS XE Optimized**
- Full compliance with Cisco gNMI implementation
- JSON_IETF encoding (RFC 7951) recommended
- Automatic configuration persistence (IOS XE 17.3.1+)
- Proper handling of encoding restrictions

✅ **Production Ready**
- TLS/certificate validation
- Connection pooling
- Timeout management
- Extensive logging
- Unit and integration tests

## Requirements

### Platform Support

- **Cisco IOS XE 16.8.1a+** for basic gNMI (GET/SET operations)
- **Cisco IOS XE 17.3.1+** for automatic config persistence
- **Cisco IOS XE 17.11.1+** for PROTO encoding (Subscribe only)

### Software Requirements

- **Python 3.8+**
- **Ansible Core 2.12+**

### Python Dependencies

```bash
grpcio >= 1.50.0
grpcio-tools >= 1.50.0
protobuf >= 4.21.0
cisco-gnmi >= 1.0.0
cryptography >= 38.0.0
```

## Installation

### Step 1: Install Python Dependencies

```bash
pip install -r requirements.txt
```

### Step 2: Install Ansible Collection

#### From Git Repository

```bash
ansible-galaxy collection install git+https://github.com/yourusername/ansible-gnmi.git
```

#### From Local Directory

```bash
ansible-galaxy collection install /path/to/ansible-gnmi
```

### Step 3: Enable gNMI on Cisco IOS XE Device

```cisco
configure terminal
!
! Required: Enable internal service for self-signed certificates
service internal
!
! Enable gNMI server
gnxi
 gnxi secure-allow-self-signed-trustpoint
 gnxi secure-password-auth
 gnxi secure-server
!
! Configure user authentication
username admin privilege 15 secret EN-TME-Cisco123
!
! Optional: Configure custom certificates for production
! crypto pki trustpoint ...
! crypto pki certificate ...
!
end
write memory
```

**Note:** The `service internal` command is required to allow self-signed certificates. For production deployments, use proper PKI certificates.

### Step 4: Verify Installation

```bash
ansible-doc cisco.iosxe_gnmi.cisco_iosxe_gnmi
```

## Quick Start

### Basic GET Operation

```yaml
---
- name: Get interface configuration
  hosts: iosxe_devices
  tasks:
    - name: Retrieve GigabitEthernet1 config
      cisco.iosxe_gnmi.cisco_iosxe_gnmi:
        host: 192.168.1.1
        username: admin
        password: cisco123
        operation: get
        paths:
          - /interfaces/interface[name=GigabitEthernet1]
      register: result

    - name: Display configuration
      debug:
        var: result.data
```

### Basic SET Operation

```yaml
---
- name: Configure interface
  hosts: iosxe_devices
  tasks:
    - name: Set interface description
      cisco.iosxe_gnmi.cisco_iosxe_gnmi:
        host: 192.168.1.1
        username: admin
        password: cisco123
        operation: set
        state: present
        config:
          - path: /interfaces/interface[name=GigabitEthernet1]/config/description
            value: "Managed by Ansible"
```

### Basic Subscribe Operation

```yaml
---
- name: Subscribe to interface statistics
  hosts: iosxe_devices
  tasks:
    - name: Get interface counters
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

## Configuration

### Inventory Setup

Create an inventory file (`inventory.ini`):

```ini
[iosxe_devices]
router1 ansible_host=192.168.1.1
router2 ansible_host=192.168.1.2

[iosxe_devices:vars]
ansible_connection=local
ansible_python_interpreter=/usr/bin/python3
gnmi_port=9339
gnmi_username=admin
gnmi_password=cisco123
gnmi_encoding=json_ietf
```

### Using Ansible Vault for Secrets

```bash
# Create encrypted vars file
ansible-vault create group_vars/iosxe_devices/vault.yml

# Add credentials
gnmi_username: admin
gnmi_password: secure_password
```

Use in playbook:
```yaml
password: "{{ gnmi_password }}"
```

### TLS Certificate Configuration

```yaml
- name: Secure connection with certificates
  cisco.iosxe_gnmi.cisco_iosxe_gnmi:
    host: 192.168.1.1
    username: admin
    password: cisco123
    operation: get
    paths: [/system/config]
    ca_cert: /path/to/ca.pem
    client_cert: /path/to/client.pem
    client_key: /path/to/client-key.pem
```

## Usage Examples

### Quick Reference

| Use Case | Model Type | Origin | Path Example | Playbook |
|----------|------------|--------|--------------|----------|
| Get hostname | OpenConfig | - | `/system/config/hostname` | test_device.yml |
| Get hostname | Cisco Native | rfc7951 | `/Cisco-IOS-XE-native:native/hostname` | test_set_hostname_native.yml |
| Get memory | Cisco Native | rfc7951 | `/Cisco-IOS-XE-memory-oper:memory-statistics` | test_memory.yml |
| Get NTP | OpenConfig | - | `/system/ntp` | test_ntp_config.yml |
| Get environment | Cisco Native | rfc7951 | `/Cisco-IOS-XE-environment-oper:environment-sensors` | test_environmental_sensors.yml |
| Get SNMP MIB | SNMP | rfc7951 | `/IF-MIB:IF-MIB` | test_snmp_mib.yml |
| Get IETF interfaces | IETF | rfc7951 | `/ietf-interfaces:interfaces` | test_ietf_interfaces.yml |
| Set hostname | OpenConfig | - | `/system/config/hostname` | test_set_hostname.yml |
| Set hostname | Cisco Native | rfc7951 | `/Cisco-IOS-XE-native:native/hostname` | test_set_hostname_native.yml |

### GET Operations

#### OpenConfig - Get System Hostname

```yaml
- name: Get hostname using OpenConfig
  cisco.iosxe_gnmi.cisco_iosxe_gnmi:
    host: "{{ ansible_host }}"
    port: 9339
    username: "{{ gnmi_username }}"
    password: "{{ gnmi_password }}"
    ca_cert: "{{ gnmi_ca_cert }}"
    operation: get
    encoding: JSON_IETF
    paths:
      - /system/config/hostname
    datatype: config
  register: hostname_result

- debug:
    msg: "Device hostname: {{ hostname_result.data['/system/config/hostname'] }}"
```

#### OpenConfig - Get All Interfaces

```yaml
- name: Get all interfaces
  cisco.iosxe_gnmi.cisco_iosxe_gnmi:
    host: "{{ ansible_host }}"
    username: "{{ gnmi_username }}"
    password: "{{ gnmi_password }}"
    operation: get
    paths:
      - /interfaces/interface
    datatype: config
    encoding: json_ietf
  register: interfaces
```

#### OpenConfig - Get NTP Configuration

```yaml
- name: Get NTP configuration (OpenConfig model)
  cisco.iosxe_gnmi.cisco_iosxe_gnmi:
    host: "{{ ansible_host }}"
    port: 9339
    username: "{{ gnmi_username }}"
    password: "{{ gnmi_password }}"
    ca_cert: "{{ gnmi_ca_cert }}"
    operation: get
    encoding: JSON_IETF
    paths:
      - /system/ntp
    datatype: all
  register: ntp_config
```

#### Cisco Native - Get Memory Statistics

```yaml
- name: Get memory statistics using Cisco native YANG
  cisco.iosxe_gnmi.cisco_iosxe_gnmi:
    host: "{{ ansible_host }}"
    port: 9339
    username: "{{ gnmi_username }}"
    password: "{{ gnmi_password }}"
    ca_cert: "{{ gnmi_ca_cert }}"
    operation: get
    encoding: JSON_IETF
    origin: rfc7951
    paths:
      - /Cisco-IOS-XE-memory-oper:memory-statistics/memory-statistic
    datatype: state
  register: memory_stats

- name: Display memory usage percentage
  debug:
    msg: "Memory usage: {{ (memory_stats.data['/Cisco-IOS-XE-memory-oper:memory-statistics']['memory-statistic'][0]['used-memory'] / memory_stats.data['/Cisco-IOS-XE-memory-oper:memory-statistics']['memory-statistic'][0]['total-memory'] * 100) | round(1) }}%"
```

#### Cisco Native - Get Environmental Sensors

```yaml
- name: Get environmental sensor data
  cisco.iosxe_gnmi.cisco_iosxe_gnmi:
    host: "{{ ansible_host }}"
    port: 9339
    username: "{{ gnmi_username }}"
    password: "{{ gnmi_password }}"
    ca_cert: "{{ gnmi_ca_cert }}"
    operation: get
    encoding: JSON_IETF
    origin: rfc7951
    paths:
      - /Cisco-IOS-XE-environment-oper:environment-sensors
    datatype: state
  register: env_sensors

- name: Display temperature sensors
  debug:
    msg: "Sensor: {{ item.name }}, Location: {{ item.location }}, Current: {{ item['current-reading'] }}°C"
  loop: "{{ env_sensors.data['/Cisco-IOS-XE-environment-oper:environment-sensors']['environment-sensor'] }}"
  when: item.sensor == "iomd"
```

#### SNMP MIB - Get IF-MIB Data

```yaml
- name: Get IF-MIB data (RFC 7951 origin)
  cisco.iosxe_gnmi.cisco_iosxe_gnmi:
    host: "{{ ansible_host }}"
    port: 9339
    username: "{{ gnmi_username }}"
    password: "{{ gnmi_password }}"
    ca_cert: "{{ gnmi_ca_cert }}"
    operation: get
    encoding: JSON_IETF
    origin: rfc7951
    paths:
      - /IF-MIB:IF-MIB
    datatype: state
  register: if_mib_result

- name: Display interface count
  debug:
    msg: "Total interfaces: {{ if_mib_result.data['/IF-MIB:IF-MIB']['interfaces']['ifNumber'] }}"
```

#### IETF - Get Standard Interfaces

```yaml
- name: Get IETF interfaces (RFC 7951 origin)
  cisco.iosxe_gnmi.cisco_iosxe_gnmi:
    host: "{{ ansible_host }}"
    port: 9339
    username: "{{ gnmi_username }}"
    password: "{{ gnmi_password }}"
    ca_cert: "{{ gnmi_ca_cert }}"
    operation: get
    encoding: JSON_IETF
    origin: rfc7951
    paths:
      - /ietf-interfaces:interfaces
    datatype: all
  register: ietf_interfaces

- name: Display interface summary
  debug:
    msg: "Found {{ ietf_interfaces.data['/ietf-interfaces:interfaces']['interface'] | length }} interfaces"
```

### SET Operations

#### OpenConfig - Update Hostname

```yaml
- name: Set hostname using OpenConfig
  cisco.iosxe_gnmi.cisco_iosxe_gnmi:
    host: "{{ ansible_host }}"
    port: 9339
    username: "{{ gnmi_username }}"
    password: "{{ gnmi_password }}"
    ca_cert: "{{ gnmi_ca_cert }}"
    operation: set
    encoding: JSON_IETF
    datatype: config
    origin: openconfig
    config:
      - path: "/system/config/hostname"
        value: "router-new-name"
  register: set_result
```

#### Cisco Native - Update Hostname (RFC 7951)

```yaml
- name: Set hostname using Cisco native YANG
  cisco.iosxe_gnmi.cisco_iosxe_gnmi:
    host: "{{ ansible_host }}"
    port: 9339
    username: "{{ gnmi_username }}"
    password: "{{ gnmi_password }}"
    ca_cert: "{{ gnmi_ca_cert }}"
    operation: set
    encoding: JSON_IETF
    origin: rfc7951
    config:
      - path: "/Cisco-IOS-XE-native:native/hostname"
        value: "set-by-gnmi"
  register: set_result
```

#### Update Configuration (Merge)

```yaml
- name: Update interface settings
  cisco.iosxe_gnmi.cisco_iosxe_gnmi:
    host: "{{ inventory_hostname }}"
    username: "{{ gnmi_username }}"
    password: "{{ gnmi_password }}"
    operation: set
    state: present
    config:
      - path: /interfaces/interface[name=GigabitEthernet1]/config/description
        value: "Uplink to Core"
      - path: /interfaces/interface[name=GigabitEthernet1]/config/enabled
        value: true
      - path: /interfaces/interface[name=GigabitEthernet1]/config/mtu
        value: 1500
```

#### Replace Configuration

```yaml
- name: Replace interface configuration
  cisco.iosxe_gnmi.cisco_iosxe_gnmi:
    host: "{{ inventory_hostname }}"
    username: "{{ gnmi_username }}"
    password: "{{ gnmi_password }}"
    operation: set
    state: present
    replace: true
    config:
      - path: /interfaces/interface[name=GigabitEthernet1]/config
        value:
          name: GigabitEthernet1
          description: "Production Link"
          enabled: true
          mtu: 9000
```

#### Delete Configuration

```yaml
- name: Remove interface description
  cisco.iosxe_gnmi.cisco_iosxe_gnmi:
    host: "{{ inventory_hostname }}"
    username: "{{ gnmi_username }}"
    password: "{{ gnmi_password }}"
    operation: set
    state: absent
    paths:
      - /interfaces/interface[name=GigabitEthernet1]/config/description
```

### Advanced Features

#### Multi-Device Management

```yaml
---
# Inventory file: inventory.ini
[iosxe_devices]
router1 ansible_host=10.85.134.65
router2 ansible_host=jcohoe-c9300-2.cisco.com

[iosxe_devices:vars]
gnmi_port=9339
gnmi_username=admin
gnmi_password=Cisco123
gnmi_encoding=JSON_IETF

# Host-specific variables: host_vars/router1.yml
gnmi_ca_cert: /tmp/device_cert.pem

# Host-specific variables: host_vars/router2.yml
gnmi_ca_cert: ./certs/router2-cert.pem
```

```yaml
---
# Playbook: multi_device_get.yml
- name: Get NTP Configuration from Multiple Devices
  hosts: iosxe_devices
  gather_facts: false

  tasks:
    - name: Get NTP configuration
      cisco.iosxe_gnmi.cisco_iosxe_gnmi:
        host: "{{ ansible_host }}"
        port: "{{ gnmi_port }}"
        username: "{{ gnmi_username }}"
        password: "{{ gnmi_password }}"
        ca_cert: "{{ gnmi_ca_cert }}"
        operation: get
        encoding: "{{ gnmi_encoding }}"
        paths:
          - /system/ntp
        datatype: all
      register: ntp_config

    - name: Display NTP servers
      debug:
        msg: "{{ inventory_hostname }}: NTP servers configured"
```

#### Check Mode (Dry Run)

```yaml
- name: Test configuration changes
  cisco.iosxe_gnmi.cisco_iosxe_gnmi:
    host: "{{ inventory_hostname }}"
    username: "{{ gnmi_username }}"
    password: "{{ gnmi_password }}"
    operation: set
    state: present
    config:
      - path: /interfaces/interface[name=GigabitEthernet1]/config/mtu
        value: 9000
  check_mode: yes
```

#### Diff Mode (Show Changes)

```yaml
- name: Configure with diff
  cisco.iosxe_gnmi.cisco_iosxe_gnmi:
    host: "{{ inventory_hostname }}"
    username: "{{ gnmi_username }}"
    password: "{{ gnmi_password }}"
    operation: set
    state: present
    config:
      - path: /interfaces/interface[name=GigabitEthernet1]/config/description
        value: "New Description"
  diff: yes
  register: result

- debug:
    var: result.diff
```

#### Configuration Backup

```yaml
- name: Change config with backup
  cisco.iosxe_gnmi.cisco_iosxe_gnmi:
    host: "{{ inventory_hostname }}"
    username: "{{ gnmi_username }}"
    password: "{{ gnmi_password }}"
    operation: set
    state: present
    backup: yes
    backup_path: ./backups
    config:
      - path: /system/config/hostname
        value: "ROUTER-01"
  register: result

- debug:
    msg: "Backup saved to {{ result.backup_file }}"
```

### Subscribe Operations

#### One-time Subscription

```yaml
- name: Get snapshot of statistics
  cisco.iosxe_gnmi.cisco_iosxe_gnmi:
    host: "{{ inventory_hostname }}"
    username: "{{ gnmi_username }}"
    password: "{{ gnmi_password }}"
    operation: subscribe
    subscribe_mode: once
    subscriptions:
      - path: /interfaces/interface/state/counters
        mode: target_defined
```

#### Sample-based Subscription

```yaml
- name: Sample interface counters
  cisco.iosxe_gnmi.cisco_iosxe_gnmi:
    host: "{{ inventory_hostname }}"
    username: "{{ gnmi_username }}"
    password: "{{ gnmi_password }}"
    operation: subscribe
    subscribe_mode: once
    subscriptions:
      - path: /interfaces/interface[name=GigabitEthernet1]/state/counters
        mode: sample
        sample_interval: 10
```

#### On-change Subscription

```yaml
- name: Monitor configuration changes
  cisco.iosxe_gnmi.cisco_iosxe_gnmi:
    host: "{{ inventory_hostname }}"
    username: "{{ gnmi_username }}"
    password: "{{ gnmi_password }}"
    operation: subscribe
    subscribe_mode: once
    subscriptions:
      - path: /interfaces/interface/config
        mode: on_change
```

## Module Documentation

### Parameters

| Parameter | Type | Required | Default | Choices | Description |
|-----------|------|----------|---------|---------|-------------|
| `host` | str | yes | - | - | Device hostname or IP address |
| `port` | int | no | 9339 | - | gNMI port (9339 secure, 50052 insecure) |
| `username` | str | yes | - | - | Authentication username |
| `password` | str | yes | - | - | Authentication password |
| `operation` | str | no | get | get, set, subscribe | Operation to perform |
| `paths` | list | conditional | - | - | List of gNMI paths |
| `datatype` | str | no | all | all, config, state, operational | Data type for GET |
| `encoding` | str | no | json_ietf | json, json_ietf, proto | Data encoding format |
| `state` | str | no | present | present, absent | Desired state for SET |
| `config` | raw | conditional | - | - | Configuration data for SET |
| `replace` | bool | no | false | - | Use replace instead of update |
| `backup` | bool | no | false | - | Create backup before changes |
| `backup_path` | str | no | ./backups | - | Backup directory path |
| `timeout` | int | no | 30 | - | Connection timeout in seconds |
| `insecure` | bool | no | false | - | Skip TLS verification (not recommended) |
| `ca_cert` | str | no | - | - | Path to CA certificate |
| `client_cert` | str | no | - | - | Path to client certificate |
| `client_key` | str | no | - | - | Path to client private key |
| `subscriptions` | list | conditional | - | - | Subscription configurations |
| `subscribe_mode` | str | no | once | stream, once, poll | Subscribe operation mode |
| `subscribe_duration` | int | no | 60 | - | Stream duration in seconds |

### Return Values

| Key | Type | Description |
|-----|------|-------------|
| `data` | dict | Data returned from gNMI operation |
| `changed` | bool | Whether configuration changed |
| `diff` | dict | Before/after differences (if diff mode enabled) |
| `backup_file` | str | Path to backup file (if backup enabled) |
| `updates` | list | Subscription updates (for subscribe operation) |
| `failed` | bool | Whether operation failed |
| `msg` | str | Status message |

## Cisco IOS XE Caveats

**Important limitations and requirements specific to Cisco IOS XE gNMI implementation:**

### Encoding Support

✅ **Supported Encodings:**
- `JSON` (0) - Standard JSON encoding
- `JSON_IETF` (4) - **RECOMMENDED** - RFC 7951 compliant
- `PROTO` (2) - Protocol Buffers (IOS XE 17.11.1+, **Subscribe ONLY**)

❌ **NOT Supported:**
- `BYTES` (1) - Not available on Cisco IOS XE
- `ASCII` (3) - Not available on Cisco IOS XE

### Operation-specific Restrictions

**GET Operations:**
- ❌ PROTO encoding NOT supported
- ✅ Use JSON_IETF or JSON encoding
- ✅ Supports all datatypes (all, config, state, operational)

**SET Operations:**
- ❌ PROTO encoding NOT supported
- ✅ Use JSON_IETF or JSON encoding
- ✅ Changes persist automatically (IOS XE 17.3.1+)
- ✅ SetRequest operates as atomic transaction

**Subscribe Operations:**
- ✅ PROTO encoding supported (IOS XE 17.11.1+)
- ✅ All encoding types supported
- ✅ Supports stream, once, and poll modes

### Configuration Persistence

- Configurations applied via SetRequest **automatically persist** to startup-config
- Available on IOS XE 17.3.1 and later
- No manual `copy running-config startup-config` required

### Default Ports

- **Secure (TLS):** 9339 (recommended)
- **Insecure:** 50052 (not recommended for production)

See [CISCO_GNMI_CAVEATS.md](CISCO_GNMI_CAVEATS.md) for complete documentation.

## Development

### Project Structure

```
ansible-gnmi/
├── plugins/
│   ├── modules/
│   │   └── cisco_iosxe_gnmi.py      # Main Ansible module
│   └── module_utils/
│       └── gnmi_client.py            # gNMI client library
├── examples/
│   ├── get_operations.yml            # GET examples
│   ├── set_operations.yml            # SET examples
│   ├── subscribe_operations.yml      # Subscribe examples
│   └── inventory.ini                 # Sample inventory
├── tests/
│   ├── unit/
│   │   ├── test_gnmi_client.py      # Client unit tests
│   │   └── test_cisco_iosxe_gnmi.py # Module unit tests
│   └── requirements.txt              # Test dependencies
├── requirements.txt                  # Python dependencies
├── galaxy.yml                        # Collection metadata
├── README.md                         # This file
├── CISCO_GNMI_CAVEATS.md           # Cisco-specific documentation
└── pytest.ini                        # Test configuration
```

### Setting Up Development Environment

```bash
# Clone repository
git clone https://github.com/yourusername/ansible-gnmi.git
cd ansible-gnmi

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r tests/requirements.txt

# Install collection in development mode
ansible-galaxy collection install . --force
```

## Testing

### Run Unit Tests

```bash
# Run all tests
pytest tests/unit/ -v

# Run with coverage
pytest tests/unit/ --cov=plugins --cov-report=html

# Run specific test file
pytest tests/unit/test_gnmi_client.py -v
```

### Run Integration Tests

```bash
# Requires real Cisco IOS XE device
export GNMI_HOST=192.168.1.1
export GNMI_USERNAME=admin
export GNMI_PASSWORD=cisco123

pytest tests/integration/ -v
```

### Lint and Code Quality

```bash
# Run pylint
pylint plugins/

# Run flake8
flake8 plugins/

# Run black formatter
black plugins/ tests/
```

## Examples

Complete examples are available in the repository:

### Test Playbooks

- **test_device.yml** - Basic device connectivity and hostname retrieval
- **test_multi_device.yml** - Multi-device NTP configuration retrieval
- **test_memory.yml** - Cisco native YANG memory statistics (single device)
- **test_memory_simple.yml** - Simplified memory statistics display
- **test_environmental_sensors.yml** - Environmental sensor data from multiple devices
- **test_ntp_config.yml** - OpenConfig NTP configuration from multiple devices
- **test_set_hostname.yml** - SET operation to change hostname (OpenConfig)
- **test_set_hostname_native.yml** - SET operation using Cisco native YANG (RFC 7951)
- **test_snmp_mib.yml** - SNMP IF-MIB retrieval via gNMI
- **test_ietf_interfaces.yml** - IETF interfaces using RFC 7951 origin

### Example Playbooks

Located in the `examples/` directory:

- **get_operations.yml** - Comprehensive GET operation examples
- **set_operations.yml** - SET operation examples with backup/diff
- **subscribe_operations.yml** - Subscribe operation examples
- **inventory.ini** - Sample inventory configuration
- **inventory_with_certs.ini** - Inventory with TLS certificate paths

### Helper Scripts

- **fetch_device_cert.sh** - Fetch SSL certificates from devices
- **install.sh** - Collection installation script
- **verify.sh** - Verify installation and dependencies

### Running Examples

```bash
# Run basic connectivity test
ansible-playbook -i test_inventory.ini test_device.yml

# Run multi-device playbook
ansible-playbook -i test_inventory.ini test_multi_device.yml

# Run with check mode (dry-run)
ansible-playbook -i test_inventory.ini test_set_hostname.yml --check

# Run with diff mode
ansible-playbook -i test_inventory.ini test_set_hostname.yml --diff

# Run examples from examples directory
cd examples/
ansible-playbook -i inventory.ini get_operations.yml
ansible-playbook -i inventory.ini set_operations.yml --check --diff
ansible-playbook -i inventory.ini subscribe_operations.yml
```

### Origin Parameter Examples

The collection supports different YANG model origins:

- **OpenConfig**: No origin parameter or `origin: openconfig`
- **Cisco Native**: `origin: rfc7951` (for Cisco-IOS-XE-* models)
- **IETF Models**: `origin: rfc7951` (for ietf-* models)
- **SNMP MIBs**: `origin: rfc7951` (for traditional MIBs via gNMI)

## Troubleshooting

### Connection Issues

**Problem:** Cannot connect to device

**Solution:**
1. Verify gNMI is enabled: `show gnmi state`
2. Check port accessibility: `telnet <ip> 9339`
3. Verify credentials
4. Check firewall rules

### TLS Certificate Errors

**Problem:** TLS verification failed

**Solution:**
- Use `insecure: true` for testing (not production)
- Install proper CA certificates
- Use `ca_cert` parameter with correct CA cert path

### Encoding Errors

**Problem:** PROTO encoding fails on GET/SET

**Solution:**
- Use `encoding: json_ietf` for GET/SET operations
- PROTO only works with Subscribe on IOS XE

### Authentication Failures

**Problem:** Authentication denied

**Solution:**
- Verify username/password
- Check user privilege level (needs level 15)
- Ensure gNMI service is running

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run existing tests
6. Submit a pull request

## License

GNU General Public License v3.0 or later

See [LICENSE](LICENSE) for full text.

## References

- [Cisco gNMI Configuration Guide](https://www.cisco.com/c/en/us/td/docs/ios-xml/ios/prog/configuration/1718/b-1718-programmability-cg/gnmi.html)
- [gNMI Specification](https://github.com/openconfig/reference/blob/master/rpc/gnmi/gnmi-specification.md)
- [OpenConfig Models](https://www.openconfig.net/)
- [RFC 7951 - JSON Encoding of YANG Data](https://tools.ietf.org/html/rfc7951)
- [Ansible Module Development](https://docs.ansible.com/ansible/latest/dev_guide/developing_modules_general.html)

## Support

For issues and questions:

- **Issues:** [GitHub Issues](https://github.com/yourusername/ansible-gnmi/issues)
- **Documentation:** See `/docs` directory
- **Cisco DevNet:** [devnetsupport@cisco.com](mailto:devnetsupport@cisco.com)

## Acknowledgments

- Cisco DevNet team for gNMI documentation
- OpenConfig community for YANG models
- Ansible community for module development guidelines
