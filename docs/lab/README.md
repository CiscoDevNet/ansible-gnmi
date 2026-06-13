# Cisco gNMI / gNOI Lab

A hands-on lab for exercising every function of the
[`cisco.gnmi`](https://galaxy.ansible.com/ui/repo/published/cisco/gnmi/docs/)
Ansible collection — GET, SET, Subscribe, and the gNOI services (certificate
management, OS upgrade, factory reset) — against three Cisco IOS XE devices over
TLS using Trust-On-First-Use (`tls_skip_verify`).

> **Follow [LAB_GUIDE.md](LAB_GUIDE.md)** for the step-by-step walkthrough.
> This README is just the map.

## Quick start

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
ansible-galaxy collection install -r requirements.yml

# Validate connectivity to all three devices (read-only):
ansible-playbook playbooks/00_capabilities.yml
# or: make smoke
```

## Playbooks

| Playbook | RPC / service | Notes |
|----------|---------------|-------|
| [playbooks/00_capabilities.yml](playbooks/00_capabilities.yml) | Capabilities | Connectivity + TLS check; writes `models/<host>_models.txt` |
| [playbooks/01_get.yml](playbooks/01_get.yml) | gNMI GET | Read-only |
| [playbooks/02_set.yml](playbooks/02_set.yml) | gNMI SET | Reversible; backup + diff + idempotency |
| [playbooks/03_subscribe.yml](playbooks/03_subscribe.yml) | gNMI Subscribe | once / stream-sample / on_change |
| [playbooks/04_gnoi_cert.yml](playbooks/04_gnoi_cert.yml) | gNOI cert mgmt | Read-only by default |
| [playbooks/05_gnoi_os_upgrade.yml](playbooks/05_gnoi_os_upgrade.yml) | gNOI OS | Staged; `activate` reboots |
| [playbooks/06_gnoi_factory_reset.yml](playbooks/06_gnoi_factory_reset.yml) | gNOI factory reset | Destructive; double-gated |

## Layout

```
ansible.cfg                          # inventory + output settings
inventory/inventory.ini              # the 3 devices (10.1.1.5/.15/.55)
inventory/group_vars/gnmi_devices.yml# credentials, port, platform, TLS (TOFU)
playbooks/                           # 00..06
LAB_GUIDE.md                         # the walkthrough
Makefile                             # convenience targets (make help)
```

## Make targets

Run `make help` to list them. Highlights:

- `make smoke` — capabilities → GET → Subscribe across all devices (safe).
- `make caps` / `make get` / `make set` / `make subscribe` — individual RPCs.
- `make lint` — yamllint + ansible-lint (uses an isolated `.lintenv`).

## Credentials

Lab credentials (`admin` / `Cisco123`) live in plaintext in
[inventory/group_vars/gnmi_devices.yml](inventory/group_vars/gnmi_devices.yml)
for simplicity. Change them there.
