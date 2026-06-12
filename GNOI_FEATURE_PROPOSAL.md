# Feature Request: Add OpenConfig gNOI Support to the Ansible gNMI Collection

## Objective

Extend the Ansible gNMI collection with a new generic `gnoi` module that supports OpenConfig gNOI operations.

The initial implementation should focus on Cisco IOS XE while being architected to support NX-OS and IOS XR gNOI services in the future without requiring redesign.

The goal is to create a reusable framework for gNOI services, not a collection of one-off IOS XE-specific modules.

---

# Scope

Implement a new generic module:

```yaml
cisco.gnmi.gnoi:
  service: os
  operation: install
```

Do not create separate modules per service.

The module should use a service/operation dispatch model internally.

---

# Initial IOS XE MVP

Implement all IOS XE-supported gNOI operations for:

- `cert.proto`
- `os.proto`
- `factory_reset.proto`

Certificate support should include all IOS XE-supported `cert.proto` RPCs.

Do not invent synthetic operations that do not map to actual supported RPCs.

OS support should include the standard OpenConfig gNOI workflow for:

- install
- activate
- verify/status

where supported by IOS XE.

Factory reset support should implement the supported reset workflow exposed by IOS XE.

---

# Architecture

Create a reusable gNOI framework using a registry/handler model.

Suggested structure:

```text
plugins/modules/
  gnoi.py

plugins/module_utils/
  gnoi/
    registry.py
    client.py
    services/
      cert.py
      os.py
      reset.py
      system.py
      file.py
      interface.py
      bgp.py
      healthz.py

  protos/
    gnoi/...
```

The registry should map:

- service
- operation
- protobuf service/stub
- handler implementation

so additional gNOI services can be added later without architectural changes.

---

# Transport and Authentication

Reuse the existing gNMI transport and authentication model already present in the collection.

Support existing mechanisms including:

- username/password
- TLS
- mTLS
- existing connection arguments

Do not introduce a separate connection model.

---

# Proto Handling

Vendor the OpenConfig gNOI proto definitions.

Generate Python gRPC stubs during build and ship the generated stubs with the collection.

End users must not be required to install proto files or generate stubs themselves.

---

# OS Workflow

Implement only the standards-based OpenConfig gNOI OS workflow.

The Ansible/gNOI client should stream the image directly to the device over the gNOI OS Install RPC.

Example flow:

```text
Ansible client
  -> gNOI OS Install RPC
  -> stream image bytes
  -> device validates image
  -> activate
  -> verify/status
```

Do not implement:

- image URI workflows
- HTTP pull workflows
- SCP workflows
- TFTP workflows
- pre-stage abstractions
- alternate image distribution mechanisms

These are intentionally out of scope.

The implementation should align with the OpenConfig gNOI OS specification and use client-side image streaming only.

---

# IOS XE Example Usage

## OS Install

```yaml
- name: Install IOS XE image using gNOI
  cisco.gnmi.gnoi:
    host: "{{ inventory_hostname }}"
    username: "{{ ansible_user }}"
    password: "{{ ansible_password }}"
    platform: iosxe
    service: os
    operation: install
    confirm: true
    args:
      image_path: /images/cat9k_iosxe.17.18.01a.SPA.bin
      version: 17.18.01a
```

## OS Activate

```yaml
- name: Activate IOS XE image
  cisco.gnmi.gnoi:
    host: "{{ inventory_hostname }}"
    username: "{{ ansible_user }}"
    password: "{{ ansible_password }}"
    platform: iosxe
    service: os
    operation: activate
    confirm: true
    args:
      version: 17.18.01a
```

## OS Verify

```yaml
- name: Verify active image
  cisco.gnmi.gnoi:
    host: "{{ inventory_hostname }}"
    username: "{{ ansible_user }}"
    password: "{{ ansible_password }}"
    platform: iosxe
    service: os
    operation: verify
    args:
      version: 17.18.01a
```

## Certificate Install

```yaml
- name: Install certificate
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

## Certificate Rotate

```yaml
- name: Rotate certificate
  cisco.gnmi.gnoi:
    host: "{{ inventory_hostname }}"
    username: "{{ ansible_user }}"
    password: "{{ ansible_password }}"
    platform: iosxe
    service: cert
    operation: rotate
    args:
      certificate_id: grpc-server
      certificate: "{{ lookup('file', 'certs/new-device.pem') }}"
      private_key: "{{ lookup('file', 'certs/new-device.key') }}"
      ca_certificate: "{{ lookup('file', 'certs/new-ca.pem') }}"
```

## Factory Reset

```yaml
- name: Factory reset device
  cisco.gnmi.gnoi:
    host: "{{ inventory_hostname }}"
    username: "{{ ansible_user }}"
    password: "{{ ansible_password }}"
    platform: iosxe
    service: factory_reset
    operation: start
    confirm: true
    args:
      zero_fill: false
```

These examples define the intended user experience. Exact parameter names may be adjusted if needed.

---

# Safety Requirements

Destructive operations must require explicit confirmation.

Example:

```yaml
confirm: true
```

Operations requiring confirmation:

- factory reset
- reboot-triggering OS activation
- future reboot operations
- future destructive system operations

Fail safely when confirmation is absent.

Example:

```yaml
failed: true
msg: "Operation factory_reset/start is destructive and requires confirm: true."
```

---

# Idempotency

The module should make a best effort to avoid unnecessary changes.

Recommended behavior:

- `os verify` → `changed: false`
- `cert get/list` → `changed: false`
- `os activate` → `changed: false` if requested version already active
- `os install` → `changed: false` if image/version already validated or installed
- `cert install/rotate` → `changed: true` when operation accepted
- `factory_reset start` → `changed: true` when operation accepted

If the device does not expose enough information to determine state safely, document the limitation and return `changed: true` when the RPC is accepted.

---

# Check Mode

Support Ansible check mode where practical.

Read-only operations may execute normally:

- verify
- certificate retrieval operations

Mutating operations must not execute:

- OS install
- OS activate
- certificate install
- certificate rotate
- factory reset

Example result:

```yaml
changed: true
skipped_rpc: true
msg: "Check mode: RPC was not executed."
```

The implementation must never stream an image, rotate a certificate, activate software, or start a reset while running in check mode.

---

# Streaming Controls

Because OS images may be large, expose configurable transfer controls.

Suggested parameters:

```yaml
timeout: 3600
chunk_size: 1048576
```

Also consider exposing:

```yaml
grpc_max_send_message_length
grpc_max_receive_message_length
```

Use reasonable defaults.

---

# Progress and Result Reporting

Return useful operation details without flooding output.

Example:

```yaml
changed: true
service: os
operation: install
platform: iosxe
response:
  image_path: /images/cat9k_iosxe.bin
  version: 17.18.01a
  bytes_transferred: 1234567890
  transfer_state: completed
  install_state: validated
  duration_seconds: 842
```

If progress updates are available during transfer, consume them internally and return a final summary.

---

# Platform Capability Model

Create a capability registry for:

- iosxe
- nxos
- iosxr

Only IOS XE requires complete implementation in the initial MVP.

However, the framework should support future NX-OS and IOS XR gNOI handlers without architectural changes.

---

# Error Handling

Normalize gRPC errors into consistent Ansible results.

Example:

```yaml
failed: true
grpc_code: UNIMPLEMENTED
grpc_message: ...
service: cert
operation: rotate
```

Handle common gRPC status codes including:

- UNIMPLEMENTED
- UNAVAILABLE
- FAILED_PRECONDITION
- INVALID_ARGUMENT
- PERMISSION_DENIED

---

# Security Requirements

Ensure sensitive values are never logged or returned.

Examples:

- private keys
- certificate signing material
- authentication metadata
- TLS secrets

Use `no_log` appropriately.

---

# Documentation

Document:

- IOS XE prerequisites
- gNMI/gNOI enablement
- TLS and mTLS configuration
- certificate workflow requirements
- OS install workflow
- activate/verify workflow
- factory reset workflow
- common gRPC errors
- check mode behavior
- timeout/chunk-size tuning guidance

---

# Testing

Add unit tests for:

- service dispatch
- operation dispatch
- argument validation
- proto interactions
- gRPC error translation
- no_log handling

Add integration tests for:

- certificate operations
- OS image streaming
- OS activate
- OS verify
- factory reset

Destructive integration tests must be gated and disabled by default.

---

# Non-Goals

The following are explicitly out of scope:

- gNSI Certz
- separate gNSI module work
- image URI workflows
- HTTP/SCP/TFTP image pulls
- image repository orchestration
- pre-stage image abstractions
- non-standard software distribution mechanisms

The focus is implementing standards-based OpenConfig gNOI support, starting with IOS XE, while creating an extensible framework for future NX-OS and IOS XR support.P
