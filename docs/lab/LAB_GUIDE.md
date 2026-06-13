# Cisco gNMI / gNOI Lab Guide

A follow-along lab for exercising every function of the
[`cisco.gnmi`](https://galaxy.ansible.com/ui/repo/published/cisco/gnmi/docs/)
Ansible collection (v4.1.0) against three Cisco IOS XE devices.

| Device   | Address    | Credentials       |
|----------|------------|-------------------|
| device1  | 10.1.1.5   | `admin` / `Cisco123` |
| device2  | 10.1.1.15  | `admin` / `Cisco123` |
| device3  | 10.1.1.55  | `admin` / `Cisco123` |

We connect over the **secure gRPC port 9339** and use **TOFU**
(`tls_skip_verify: true`) so we trust each device's self-signed certificate on
first connect without managing a CA file. The channel is encrypted but the
server identity is **not** verified — fine for a trusted lab, not for production.

---

## What you'll run

| Module / service          | RPC                | Playbook                          | Safe? |
|---------------------------|--------------------|-----------------------------------|-------|
| `cisco.gnmi.capabilities` | Capabilities       | `playbooks/00_capabilities.yml`   | ✅ read-only |
| `cisco.gnmi.info`         | GET                | `playbooks/01_get.yml`            | ✅ read-only |
| `cisco.gnmi.config`       | SET                | `playbooks/02_set.yml`            | ✅ reversible |
| `cisco.gnmi.subscribe`    | Subscribe          | `playbooks/03_subscribe.yml`      | ✅ read-only |
| `cisco.gnmi.gnoi` (cert)  | Certificate Mgmt   | `playbooks/04_gnoi_cert.yml`      | ✅ read-only by default |
| `cisco.gnmi.gnoi` (os)    | OS Install/Upgrade | `playbooks/05_gnoi_os_upgrade.yml`| ⚠️ reboots on activate |
| `cisco.gnmi.gnoi` (reset) | Factory Reset      | `playbooks/06_gnoi_factory_reset.yml` | 🛑 destructive |

---

## 0. One-time setup

```bash
# 1. Create and activate a Python virtual environment
python3 -m venv venv
source venv/bin/activate

# 2. Install the Python gRPC/TLS dependencies into the venv
pip install -r requirements.txt

# 3. Install the collection
ansible-galaxy collection install -r requirements.yml
#    (or: ansible-galaxy collection install cisco.gnmi)

# 4. Confirm Ansible can see the inventory
ansible-inventory --graph
```

> **Why a venv?** The modules open a gRPC channel and need `grpcio`,
> `protobuf`, and `cryptography`. The inventory's
> `ansible_python_interpreter` already points at `venv/bin/python`, so the
> modules find these deps there. `ansible-playbook` itself can stay the
> system install — only the device-side Python needs the gRPC libraries.
> If you recreate the venv under a different path, update
> `ansible_python_interpreter` in [inventory/inventory.ini](inventory/inventory.ini).

Project layout:

```
ansible.cfg                         # points at inventory, enables YAML + timing output
inventory/
  inventory.ini                     # the 3 devices
  group_vars/gnmi_devices.yml       # credentials, port, platform, TLS (TOFU) settings
playbooks/
  00_capabilities.yml ... 06_gnoi_factory_reset.yml
backups/                            # created automatically by the SET backup step
certs/                              # (optional) PEM material for cert install
models/                             # supported-model lists written by 00_capabilities
venv/                               # Python virtualenv with the gRPC/TLS deps
```

All connection settings live in
[inventory/group_vars/gnmi_devices.yml](inventory/group_vars/gnmi_devices.yml).
Each playbook pulls them in via `module_defaults`, so the per-task YAML stays
short. Change the password or switch from TOFU to a pinned CA in that one file.

> **Credentials note:** `Cisco123` is in plaintext for the lab. For anything
> real, encrypt the file: `ansible-vault encrypt inventory/group_vars/gnmi_devices.yml`.

---

## 1. Capabilities — prove the connection works

Always start here. It validates connectivity, TLS (TOFU), and auth in one shot.

```bash
ansible-playbook playbooks/00_capabilities.yml
```

**Expect:** each device returns a gNMI version, a list of supported encodings
(`json_ietf`, `json`, `proto`), and a count of advertised YANG models. You'll
also see a one-line warning that the device certificate is being trusted
without verification — that's the TOFU warning, and it's expected.

### Seeing the full list of supported models

The capabilities response includes every YANG model the device supports
(`caps.data.supported_models`, each with `name`, `organization`, `version`).
The playbook always writes the complete list, one model per line, to
`models/<host>_models.txt`:

```bash
ansible-playbook playbooks/00_capabilities.yml      # writes models/<host>_models.txt
column -t -s$'\t' models/device1_models.txt | less  # browse it (TSV: name / org / version)
wc -l models/*.txt                                  # model counts per device
```

To also dump the model names to the screen during the run, add `-e show_models=true`:

```bash
ansible-playbook playbooks/00_capabilities.yml -e show_models=true
```

If this fails, fix it before moving on:
- *connection refused* → gNMI not enabled / wrong port.
- *auth error* → username/password.
- *TLS error even with skip-verify* → you're hitting a non-TLS port; 9339 is correct for IOS XE.

---

## 2. GET — read config and state

```bash
ansible-playbook playbooks/01_get.yml
```

This retrieves, per device:
1. All interfaces (OpenConfig `/interfaces/interface`).
2. The hostname (`datatype: config`).
3. Operational counters for one interface (`datatype: operational`).
4. The IOS XE **native** hostname (`origin: rfc7951`, needed for Cisco native models).

**Expect:** JSON payloads under `*.data` (a dict keyed by path). Tasks 3 and 4 use `ignore_errors`
because interface names and native paths vary — that's intentional.

Key options demonstrated: `paths`, `datatype` (`all`/`config`/`state`/`operational`),
`encoding`, and `origin`.

---

## 3. SET — change config safely and reversibly

Dry-run first, then apply:

```bash
# See what WOULD change, with a diff, without touching the device:
ansible-playbook playbooks/02_set.yml --check --diff

# Apply for real:
ansible-playbook playbooks/02_set.yml --diff
```

[playbooks/02_set.yml](playbooks/02_set.yml) walks the full SET lifecycle:
1. GET the current interface description (so we can restore it).
2. SET a new description **with a pre-change backup** (saved as JSON under
   `./backups/<host>_<timestamp>.json` on the controller).
3. GET again to verify.
4. Re-run the identical SET to prove **idempotency** (`changed: false`).
5. DELETE the description to leave the device as we found it.

> **gNMI SET is atomic:** any combination of `update`, `replace`, and `delete`
> in one task is sent as a single transaction. On IOS XE it's all-or-nothing.

Change the target with `-e demo_interface=GigabitEthernet2` if `Gi1` isn't ideal.

---

## 4. Subscribe — streaming telemetry

```bash
ansible-playbook playbooks/03_subscribe.yml
```

Three subscription styles, all read-only:
- **once** — immediate counter snapshot, returns right away.
- **stream / sample** — periodic samples of `oper-status` for 30 s.
- **stream / on_change** — pushes only when state changes for 30 s. Flap an
  interface during this window to watch an update arrive.

> On IOS XE the platform profile restricts STREAM to `on_change` / `sample`
> modes and PROTO encoding for Subscribe — the module enforces this for you.

Tune `subscribe_duration`, `sample_interval`, and the `subscriptions[].path`
to taste.

---

## 5. gNOI Certificate Management

```bash
# Safe: list installed certs + probe CSR capability
ansible-playbook playbooks/04_gnoi_cert.yml
```

[playbooks/04_gnoi_cert.yml](playbooks/04_gnoi_cert.yml) runs the **read-only**
operations by default (`cert/get`, `cert/can_generate_csr`). The mutating
`cert/install` step only runs when you opt in:

```bash
# Put PEM material in certs/ first: <host>.pem, <host>.key, ca.pem
ansible-playbook playbooks/04_gnoi_cert.yml -e cert_do_install=true
```

> **IOS XE caveat:** `cert/install` expects the on-box **GenerateCSR** workflow.
> Pushing an externally generated cert + key directly can be rejected with
> `ABORTED`.

Available cert operations: `get`, `can_generate_csr`, `install`, `rotate`, `revoke`.

---

## 6. gNOI OS Upgrade

The upgrade is deliberately split so **you** control the reboot. Do it one
device at a time with `--limit`.

```bash
# Stage 0 — just read the running version (always safe)
ansible-playbook playbooks/05_gnoi_os_upgrade.yml --limit device1

# Stage 1 — stream + STAGE the image (NO reboot)
ansible-playbook playbooks/05_gnoi_os_upgrade.yml --limit device1 \
  -e os_image_path=/images/cat9k_iosxe.17.18.01a.SPA.bin -e do_install=true

# Stage 2 — ACTIVATE the staged image and REBOOT into it
ansible-playbook playbooks/05_gnoi_os_upgrade.yml --limit device1 \
  -e os_image_path=/images/cat9k_iosxe.17.18.01a.SPA.bin -e do_activate=true
```

After Stage 2 the device reboots; once it's back, re-run Stage 0 to confirm the
new running version.

Why this is simple:
- **No `version` needed.** Omit it and the module reads `CW_FULL_VERSION` from
  the `.bin` header and uses that for both install and activate.
- **Image streams from the controller** — `os_image_path` points at the `.bin`
  on the machine running Ansible; no pre-copy to the device.
- **No separate `install commit`.** On IOS XE, `activate` commits as part of the
  activate-and-reboot.
- **Idempotent.** `install`/`activate` short-circuit if the version is already
  present/running.

> **"System configuration has been modified" on activate?** IOS XE requires the
> running-config to be saved, and there is no save RPC in gNMI/gNOI. But IOS XE
> gNMI Configuration Persistence writes the *entire* running-config to startup
> after any successful `SetRequest`. So just make one successful SET first — e.g.
> run `playbooks/02_set.yml` (set hostname to its current value) — then retry
> `activate`.

OS operations: `verify` (read-only), `install` (stage), `activate` (reboot).

---

## 7. gNOI Factory Reset — **destructive, run last**

This **wipes the device**. It will not run unless you explicitly confirm, and it
pauses for a final Enter before issuing the RPC.

```bash
ansible-playbook playbooks/06_gnoi_factory_reset.yml \
  --limit device3 -e factory_reset_confirm=true
```

Prerequisites and gotchas:
- No special certificate is needed. Factory reset uses the same connection and
  auth as the OS service, so the TOFU / self-signed setup used throughout this
  lab is sufficient.
- Some IOS XE builds **require `zero_fill: true`** and reject `false` with
  `INVALID_ARGUMENT` — the playbook defaults it to true.
- Use `--limit` so you never reset all three at once by accident.
- Use `--limit` so you never reset all three at once by accident.

Factory reset operation: `start`.

---

## TLS reference — moving beyond TOFU

The same options work on every module (`info`, `config`, `subscribe`,
`capabilities`, `gnoi`). Set them once in
[inventory/group_vars/gnmi_devices.yml](inventory/group_vars/gnmi_devices.yml).

| Goal | What to set | Notes |
|------|-------------|-------|
| Trust self-signed cert on first use (**this lab**) | `tls_skip_verify: true` | Encrypted, identity not verified (TOFU). Like `gnmic --skip-verify`. |
| Verify against a known CA (recommended for prod) | `ca_cert: /path/ca.pem` | Strongest; pins the trusted CA. Takes precedence over `tls_skip_verify`. |
| Mutual TLS | `client_cert:` + `client_key:` (+ `ca_cert:`) | Device authenticates the client too. |
| No TLS (lab only) | `insecure: true` | Plaintext; only on the insecure port (e.g. 50052). |

**Precedence:** `insecure` wins if set; otherwise an explicit `ca_cert` pin beats
`tls_skip_verify`.

---

## Suggested run order

```
00_capabilities  →  01_get  →  02_set  →  03_subscribe  →  04_gnoi_cert
                 →  05_gnoi_os_upgrade  →  06_gnoi_factory_reset
```

Validate connectivity (00) before anything else. Keep the destructive gNOI
operations (05 activate, 06 reset) for last, and run them with `--limit` on a
single device at a time.
