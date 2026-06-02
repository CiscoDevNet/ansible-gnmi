# Cisco gNMI Ansible Collection

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://www.apache.org/licenses/LICENSE-2.0)
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://www.python.org/)
[![Ansible](https://img.shields.io/badge/Ansible-2.15%2B-red)](https://www.ansible.com/)

An Ansible collection for managing Cisco network devices using gNMI
(gRPC Network Management Interface). Supports **Cisco IOS XE, IOS XR, and
NX-OS**.

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
  cisco.gnmi.info:
    host: "{{ inventory_hostname }}"
    port: 9339
    username: "{{ gnmi_user }}"
    password: "{{ gnmi_password }}"
    paths:
      - /interfaces/interface
    encoding: json_ietf
  register: result
```

### SET – configure interface description

```yaml
- name: Set interface description
  cisco.gnmi.config:
    host: "{{ inventory_hostname }}"
    username: "{{ gnmi_user }}"
    password: "{{ gnmi_password }}"
    update:
      - path: /interfaces/interface[name=GigabitEthernet1]/config/description
        value: "Uplink to Core"
```

### Subscribe – one-shot counter snapshot

```yaml
- name: Get counter snapshot
  cisco.gnmi.subscribe:
    host: "{{ inventory_hostname }}"
    username: "{{ gnmi_user }}"
    password: "{{ gnmi_password }}"
    subscribe_mode: once
    subscriptions:
      - path: /interfaces/interface[name=GigabitEthernet1]/state/counters
        mode: sample
        sample_interval: 10
```

### Platform hint (Cisco IOS XE)

```yaml
- name: IOS XE with platform-specific validation
  cisco.gnmi.info:
    host: "{{ inventory_hostname }}"
    port: 9339
    username: "{{ gnmi_user }}"
    password: "{{ gnmi_password }}"
    platform: iosxe
    paths:
      - /Cisco-IOS-XE-native:native/hostname
    origin: rfc7951
```

### IOS XE Subscribe (stream mode, on_change)

```yaml
- name: Stream on-change interface updates from IOS XE
  cisco.gnmi.subscribe:
    host: "{{ inventory_hostname }}"
    port: 9339
    username: "{{ gnmi_user }}"
    password: "{{ gnmi_password }}"
    platform: iosxe
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
| `platform` | str | `auto` | `auto`, `iosxe`, `iosxr`, `nxos` |
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

## Using with Other gNMI Implementations

The `platform` parameter only ships profiles for Cisco IOS XE, IOS XR, and
NX-OS. The underlying client speaks standard
[OpenConfig gNMI](https://github.com/openconfig/reference/blob/master/rpc/gnmi/gnmi-specification.md),
so it works with any compliant device when you configure the connection
explicitly. Leave `platform` at its default (`auto`) to disable all
platform-specific validation, then set the standard parameters yourself:

```yaml
- name: GET on a non-Cisco gNMI device
  cisco.gnmi.info:
    host: "{{ inventory_hostname }}"
    port: 57400                       # set the vendor's gNMI port
    username: "{{ ansible_user }}"
    password: "{{ ansible_password }}"
    paths:
      - /interfaces/interface
    encoding: json_ietf               # json | json_ietf | proto
    datatype: all                     # all | config | state | operational
    timeout: 30
    # TLS options
    insecure: false                   # true = skip server cert verification
    ca_cert: /path/to/ca.pem          # trust this CA
    client_cert: /path/to/client.pem  # mutual TLS (required together with key)
    client_key:  /path/to/client.key
    # platform defaults to 'auto' - no platform restrictions enforced
```

Reference for vendor-specific defaults you may want to set:

| Setting | What to configure | Typical values |
|---|---|---|
| Port | `port:` | Vendor-documented gNMI port (e.g. 57400, 6030, 32767) |
| Encoding | `encoding:` | `json_ietf` (most common), `json`, or `proto` if your device supports it |
| TLS | `ca_cert` / `client_cert` / `client_key` / `insecure` | Per your device's certificate setup |
| Path origin | `origin:` | e.g. `openconfig`, `rfc7951`, or vendor-specific origins |
| Subscribe | `subscribe_mode`, `subscriptions[].mode` | `stream`/`once`/`poll`; `sample`/`on_change`/`target_defined` |

If you find your device needs platform-specific guard rails similar to the
IOS XE profile, open an issue or a pull request at
<https://github.com/CiscoDevNet/ansible-gnmi>.

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
