# Cisco gNMI Ansible Collection

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://www.apache.org/licenses/LICENSE-2.0)
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://www.python.org/)
[![Ansible](https://img.shields.io/badge/Ansible-2.15%2B-red)](https://www.ansible.com/)

A vendor-neutral Ansible collection for managing network devices using gNMI
(gRPC Network Management Interface).  Works with **any gNMI-capable device**
including Cisco IOS XE, IOS XR, NX-OS, Nokia SR OS, Arista EOS, and Juniper
Junos.

## Features

- **GET** – retrieve configuration and operational state
- **SET** – update, replace, and delete configuration
- **Subscribe** – stream, once, or poll subscription RPCs
- **Check mode** and **diff mode** for safe, auditable changes
- **Configuration backup** before SET operations
- **Platform profiles** – optional vendor-specific validation (e.g. encoding
  restrictions on Cisco IOS XE)
- **TLS / mutual TLS** with automatic certificate CN override

## Requirements

| Requirement | Version |
|---|---|
| Ansible / ansible-core | >= 2.15 |
| Python | >= 3.9 |
| grpcio | >= 1.50.0 |
| grpcio-tools | >= 1.50.0 |
| protobuf | >= 4.21.0 |
| cryptography | >= 38.0.0 (for TLS) |

## Installation

### From Ansible Galaxy

```bash
ansible-galaxy collection install cisco.gnmi
```

### From source

```bash
git clone https://github.com/CiscoDevNet/ansible-gnmi.git
cd ansible-gnmi
ansible-galaxy collection build
ansible-galaxy collection install cisco-gnmi-*.tar.gz
```

### Python dependencies

```bash
pip install -r requirements.txt
```

## Quick Start

### GET – retrieve interface configuration

```yaml
- name: Get all interfaces
  cisco.gnmi.gnmi:
    host: "{{ inventory_hostname }}"
    port: 9339
    username: "{{ gnmi_user }}"
    password: "{{ gnmi_password }}"
    operation: get
    paths:
      - /interfaces/interface
    encoding: json_ietf
  register: result
```

### SET – configure interface description

```yaml
- name: Set interface description
  cisco.gnmi.gnmi:
    host: "{{ inventory_hostname }}"
    username: "{{ gnmi_user }}"
    password: "{{ gnmi_password }}"
    operation: set
    config:
      - path: /interfaces/interface[name=GigabitEthernet1]/config/description
        value: "Uplink to Core"
```

### Subscribe – one-shot counter snapshot

```yaml
- name: Get counter snapshot
  cisco.gnmi.gnmi:
    host: "{{ inventory_hostname }}"
    username: "{{ gnmi_user }}"
    password: "{{ gnmi_password }}"
    operation: subscribe
    subscribe_mode: once
    subscriptions:
      - path: /interfaces/interface[name=GigabitEthernet1]/state/counters
        mode: sample
        sample_interval: 10
```

### Platform hint (Cisco IOS XE)

```yaml
- name: IOS XE with platform-specific validation
  cisco.gnmi.gnmi:
    host: "{{ inventory_hostname }}"
    port: 9339
    username: "{{ gnmi_user }}"
    password: "{{ gnmi_password }}"
    platform: iosxe
    operation: get
    paths:
      - /Cisco-IOS-XE-native:native/hostname
    origin: rfc7951
```

### IOS XE Subscribe (stream mode, on_change)

```yaml
- name: Stream on-change interface updates from IOS XE
  cisco.gnmi.gnmi:
    host: "{{ inventory_hostname }}"
    port: 9339
    username: "{{ gnmi_user }}"
    password: "{{ gnmi_password }}"
    platform: iosxe
    operation: subscribe
    subscribe_mode: stream
    subscribe_duration: 120
    subscriptions:
      - path: /interfaces/interface/state/oper-status
        mode: on_change
  register: oper_updates
```

## Module Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `host` | str | *required* | Target device hostname or IP |
| `port` | int | 9339 | gNMI port |
| `username` | str | *required* | Authentication username |
| `password` | str | *required* | Authentication password |
| `operation` | str | `get` | `get`, `set`, or `subscribe` |
| `paths` | list | — | gNMI paths (required for GET) |
| `datatype` | str | `all` | `all`, `config`, `state`, `operational` |
| `encoding` | str | `json_ietf` | `json`, `json_ietf`, or `proto` |
| `state` | str | `present` | `present` or `absent` (SET only) |
| `config` | raw | — | List of `{path, value}` dicts (SET only) |
| `replace` | bool | `false` | Use replace instead of update |
| `backup` | bool | `false` | Backup config before changes |
| `backup_path` | path | `./backups` | Backup directory |
| `timeout` | int | 30 | RPC timeout in seconds |
| `insecure` | bool | `false` | Skip TLS verification |
| `ca_cert` | path | — | CA certificate path |
| `client_cert` | path | — | Client certificate path |
| `client_key` | path | — | Client key path |
| `platform` | str | `auto` | `auto`, `iosxe`, `iosxr`, `nxos`, `nokia_sros`, `arista_eos` |
| `origin` | str | — | gNMI path origin (`rfc7951`, `openconfig`, etc.) |
| `subscriptions` | list | — | Subscription dicts (Subscribe only) |
| `subscribe_mode` | str | `once` | `stream`, `once`, or `poll` |
| `subscribe_duration` | int | 60 | Stream duration in seconds |

## Platform Profiles

When `platform` is set to a known value, encoding, port, and subscribe restrictions are
enforced automatically:

| Platform | Secure Port | Insecure Port | Blocked Encodings (GET/SET) | Subscribe Restrictions | Notes |
|---|---|---|---|---|---|
| `auto` | 9339 | — | *none* | *none* | No restrictions |
| `iosxe` | 9339 | 50052 | `proto` | List mode: only `stream`; Sub mode: only `on_change`, `sample` | gNMI 0.4.0; PROTO only with Subscribe; atomic SET (all-or-nothing) |
| `iosxr` | 57400 | — | *none* | *none* | |
| `nxos` | 50051 | — | *none* | *none* | |
| `nokia_sros` | 57400 | — | *none* | *none* | |
| `arista_eos` | 6030 | — | *none* | *none* | |

## Development

```bash
# Install dev dependencies
pip install -r requirements.txt pytest

# Run unit tests
pytest tests/unit/ -v

# Run ansible-test sanity (requires ansible-core)
ansible-test sanity --docker default
```

## License

Apache License 2.0 – see [LICENSE](LICENSE) for details.

## Author

Jeremy Cohoe ([@jeremycohoe](https://github.com/jeremycohoe)) – Cisco Systems
