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
- **gNOI** – Certificate Management, OS Installation, and Factory Reset
  (gRPC Network Operations Interface) via the `cisco.gnmi.gnoi` module
- **Check mode** and **diff mode** for safe, auditable changes
- **Configuration backup** before SET operations (saved as JSON on the Ansible controller)
- **Platform profiles** – optional vendor-specific validation (e.g. encoding
  restrictions on Cisco IOS XE)
- **TLS / mutual TLS** with automatic certificate CN override, plus a
  `tls_skip_verify` (Trust-On-First-Use) mode for self-signed certificates

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

### Platform hint + native YANG model (Cisco IOS XE)

This is still a GET, but it shows two IOS XE-specific options the basic GET
example above does not: setting `platform: iosxe` to turn on platform profile
validation (enforces the secure port, blocks unsupported encodings, applies
subscribe restrictions), and querying a Cisco native model path, which
requires `origin: rfc7951`.

```yaml
- name: GET the IOS XE native hostname with platform validation
  cisco.gnmi.info:
    host: "{{ inventory_hostname }}"
    port: 9339
    username: "{{ gnmi_user }}"
    password: "{{ gnmi_password }}"
    platform: iosxe                       # enable IOS XE profile validation
    paths:
      - /Cisco-IOS-XE-native:native/hostname
    origin: rfc7951                        # required for Cisco native models
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

### Connecting over TLS

The secure gRPC port (default `9339`) always uses TLS. Pick the mode that
matches how your device's certificate is set up:

| Goal | What to set | Notes |
|---|---|---|
| Verify the device against a known CA (recommended) | `ca_cert: /path/to/ca.pem` | Strongest option; pins the trusted CA |
| Mutual TLS (client certificate) | `client_cert:` + `client_key:` (plus `ca_cert:`) | Device authenticates the client too |
| Connect to a self-signed cert without a CA file | `tls_skip_verify: true` | Encrypted channel, trusts the cert on first connect (TOFU). Like `gnmic --skip-verify` |
| No TLS at all (lab only) | `insecure: true` | Plaintext; only works on the insecure port (e.g. `50052`) |

`tls_skip_verify` is the easy way to talk to a device that presents a
self-signed certificate (as IOS XE does by default) without exporting and
managing its CA. The channel is **encrypted**, but the server identity is
**not** verified, so it is vulnerable to man-in-the-middle attacks — use it
only on trusted networks. A warning is emitted on every run.

```yaml
- name: GET hostname over TLS without managing a CA file (skip-verify / TOFU)
  cisco.gnmi.info:
    host: "{{ inventory_hostname }}"
    port: 9339
    username: "{{ gnmi_user }}"
    password: "{{ gnmi_password }}"
    platform: iosxe
    tls_skip_verify: true           # encrypted, trusts the device cert on first use
    origin: openconfig
    paths:
      - /system/config/hostname
```

Precedence: `insecure` (plaintext) wins if set; otherwise an explicit
`ca_cert` pin takes priority over `tls_skip_verify`. The same option works on
every module in the collection (`info`, `config`, `subscribe`,
`capabilities`, and `gnoi`).

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
| `backup` | bool | `false` | Save affected paths to a JSON file on the controller before changing (Ansible feature, not gNMI) |
| `backup_path` | path | `./backups` | Backup directory on the controller |
| `timeout` | int | 30 | RPC timeout in seconds |
| `insecure` | bool | `false` | Use a plaintext channel (no TLS). Only works on the device's insecure port (e.g. `50052`) |
| `tls_skip_verify` | bool | `false` | TLS-encrypted channel that trusts the device's certificate on first connect (TOFU) without a CA file. Like `gnmic --skip-verify` |
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

## gNOI Operations (cisco.gnmi.gnoi)

The `cisco.gnmi.gnoi` module performs OpenConfig **gNOI** (gRPC Network
Operations Interface) operations using a single generic module with a
`service` / `operation` dispatch model. The initial release implements the
gNOI services supported by **Cisco IOS XE**:

| Service          | Operations                                               | Notes |
|------------------|----------------------------------------------------------|-------|
| `cert`           | `install`, `rotate`, `revoke`, `get`, `can_generate_csr` | Certificate Management (IOS XE 17.3.1+) |
| `os`             | `install`, `activate`, `verify`                          | OS Installation (IOS XE 17.5.1+) |
| `factory_reset`  | `start`                                                  | Factory Reset (IOS XE 17.7.1+) |

gNOI reuses the same gRPC transport and authentication as the gNMI modules.
On IOS XE, gNOI is served on the same gRPC endpoint as gNMI (default port
`9339`).

### Prerequisites (Cisco IOS XE)

- gRPC / gNMI enabled and reachable (the gNOI services share this endpoint).
- TLS (or mutual TLS) configured. Certificate Management and Factory Reset
  generally require a provisioned (signed, non-self-signed) certificate;
  `factory_reset/start` returns `FAILED_PRECONDITION` otherwise.
- Feature availability depends on the IOS XE version (see the table above).

### Safety, check mode, and idempotency

- **Destructive operations** (`os/activate`, `factory_reset/start`) require
  `confirm: true`. Without it, the module fails safely without contacting the
  device.
- **Check mode** skips mutating RPCs (reported as `changed`); read-only
  operations (`cert/get`, `os/verify`, `cert/can_generate_csr`) still run.
- **Idempotency**: `os/activate` and `os/install` short-circuit when the
  requested version is already running.
- **gRPC errors** are normalised to `grpc_code` (e.g. `UNIMPLEMENTED`,
  `FAILED_PRECONDITION`) and `grpc_message`.
- Secrets (`args.private_key`, `password`, `token`) are `no_log` and never
  appear in results.

### Examples

```yaml
# Verify the running OS version (read-only)
- name: Verify active image
  cisco.gnmi.gnoi:
    host: "{{ inventory_hostname }}"
    username: "{{ ansible_user }}"
    password: "{{ ansible_password }}"
    platform: iosxe
    service: os
    operation: verify
  register: image

# Stream and install an OS image (client-side streaming)
- name: Install IOS XE image
  cisco.gnmi.gnoi:
    host: "{{ inventory_hostname }}"
    username: "{{ ansible_user }}"
    password: "{{ ansible_password }}"
    platform: iosxe
    service: os
    operation: install
    chunk_size: 1048576        # tune transfer chunk size (bytes)
    args:
      image_path: /images/cat9k_iosxe.17.18.01a.SPA.bin
      version: 17.18.01a

# Activate an installed image (reboots the device — destructive)
- name: Activate image
  cisco.gnmi.gnoi:
    host: "{{ inventory_hostname }}"
    username: "{{ ansible_user }}"
    password: "{{ ansible_password }}"
    platform: iosxe
    service: os
    operation: activate
    confirm: true              # required for destructive operations
    args:
      version: 17.18.01a

# Install a certificate (provide signed material directly)
- name: Install gRPC server certificate
  cisco.gnmi.gnoi:
    host: "{{ inventory_hostname }}"
    username: "{{ ansible_user }}"
    password: "{{ ansible_password }}"
    platform: iosxe
    service: cert
    operation: install
    args:
      certificate_id: grpc-server
      certificate: "{{ lookup('file', 'certs/device.pem') }}"
      private_key: "{{ lookup('file', 'certs/device.key') }}"
      ca_certificate: "{{ lookup('file', 'certs/ca.pem') }}"
```

A full runnable example playbook is provided at
[examples/gnoi_operations.yml](examples/gnoi_operations.yml).

### OS upgrade — Quick Start

The OS service splits an upgrade into independent steps, so you decide exactly
when the device reboots:

1. **verify** – read the running version (read-only)
2. **install** – stream the image to the device and stage it (**no reboot**)
3. **activate** – boot into the staged image and commit it (**reboots**)
4. **verify** – confirm the new version after the device comes back

A ready-to-run, two-stage playbook is provided at
[examples/gnoi_os_upgrade.yml](examples/gnoi_os_upgrade.yml). Set `image_path`
(and the connection vars) at the top, then run the two stages:

```bash
# Stage 1: verify the current version, then stream + stage the image (no reboot)
ansible-playbook examples/gnoi_os_upgrade.yml -i inventory.ini

# Stage 2: activate the staged image and REBOOT into it
ansible-playbook examples/gnoi_os_upgrade.yml -i inventory.ini -e do_activate=true
```

After Stage 2 the device reboots; once it is reachable again, re-run Stage 1
(or just the `verify` task) to confirm the new running version.

Key points that keep this simple:

- **No `version` needed.** When you omit `args.version`, the module reads the
  canonical `CW_FULL_VERSION` embedded in the `.bin` image header and uses that
  exact value for both `install` and `activate`. Pass `args.image_path` to
  `activate` so it can derive the same version you staged.
- **No CLI `install commit`.** On IOS XE, `os/activate` commits the image as
  part of the activate-and-reboot — there is no separate commit step.
- **The image is streamed from the controller.** `image_path` points at the
  `.bin` on the machine running Ansible; it does not need to be pre-copied to
  the device.
- **Self-signed certificates.** Set `tls_skip_verify: true` to trust the
  device certificate on first use (the channel is still encrypted). For
  production, pin a CA with `ca_cert` instead.
- **`install` reports success even if the device withholds the final
  validation.** Some IOS XE builds stage the image but do not send a terminal
  `Validated` message; as long as the whole image was transferred, the module
  reports the image as staged (`install_state: transferred`,
  `validated: false`) with a warning, instead of failing.

## Vendor-Agnostic Usage

The `platform` parameter only ships profiles for Cisco IOS XE, IOS XR, and
NX-OS. The underlying client speaks standard
[OpenConfig gNMI](https://github.com/openconfig/reference/blob/master/rpc/gnmi/gnmi-specification.md),
so it works with any compliant device from any vendor when you configure the
connection explicitly. Leave `platform` at its default (`auto`) to disable all
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
    insecure: false                   # true = plaintext, no TLS (insecure port only)
    tls_skip_verify: false            # true = TLS but trust the device cert on first use (no ca_cert needed)
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
| TLS | `ca_cert` / `client_cert` / `client_key` / `tls_skip_verify` / `insecure` | Per your device's certificate setup |
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
