#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright 2025 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: config
short_description: Manage Cisco device configuration via gNMI Set
description:
  - Performs gNMI SET requests (Update, Replace, Delete) against Cisco devices
    (IOS-XE, IOS-XR, NX-OS).
  - Any combination of I(update), I(replace) and I(delete) supplied in a single
    task is sent in one SetRequest, so the device applies them as a single
    atomic transaction.
  - Supports C(check_mode), C(diff) and optional pre-change C(backup).
version_added: "4.0.0"
author:
  - "Cisco Systems (@cisco)"
options:
  host:
    description: Hostname or IP address of the target device.
    type: str
    required: true
  port:
    description: gNMI service port.
    type: int
    default: 9339
  username:
    description:
      - Username for password-based authentication. Required unless I(token) is set.
    type: str
  password:
    description:
      - Password for password-based authentication. Required when I(username) is set.
    type: str
  token:
    description:
      - Bearer token for token-based authentication. Sent as the
        C(authorization) gRPC metadata header. Mutually exclusive with
        I(username)/I(password).
    type: str
  update:
    description:
      - Merge-style updates to apply. Each item is a dict with
        C(path), C(value) and optional C(origin).
    type: list
    elements: dict
    suboptions:
      path:
        description: gNMI path to update.
        type: str
        required: true
      value:
        description: Value to write at C(path).
        type: raw
        required: true
      origin:
        description:
          - Per-item origin override. May also be encoded directly into
            C(path) using the C(origin:/path) form.
        type: str
  replace:
    description:
      - Replace-style writes (subtree fully overwritten). Each item is a
        dict with C(path), C(value) and optional C(origin).
    type: list
    elements: dict
    suboptions:
      path:
        description: gNMI path to replace.
        type: str
        required: true
      value:
        description: Value that replaces the subtree at C(path).
        type: raw
        required: true
      origin:
        description: Per-item origin override.
        type: str
  delete:
    description:
      - Paths to delete. Each item may be a plain string path or a dict
        C({path, origin}).
    type: list
    elements: raw
  backup:
    description:
      - Back up the current config (for the affected paths) before
        applying the change.
      - This is an Ansible convenience implemented by the module, not a gNMI
        protocol feature. The module performs a gNMI GET (C(datatype=config))
        on the affected paths and writes the result as a timestamped JSON file
        on the Ansible controller (the machine running the playbook), named
        C(<host>_<YYYYMMDD_HHMMSS>.json). The path is returned as
        C(backup_file). It is not a device-side checkpoint/rollback.
      - Skipped automatically in C(check_mode).
    type: bool
    default: false
  backup_path:
    description:
      - Directory on the Ansible controller in which to write backups. Must
        not contain C(..).
    type: path
    default: ./backups
  encoding:
    description: Encoding used for SET payloads.
    type: str
    choices: [json, json_ietf, proto, bytes, ascii]
    default: json_ietf
  origin:
    description:
      - Default origin for gNMI paths (e.g. C(openconfig), C(rfc7951)).
      - Individual items may override this via their own C(origin) key or
        via the C(origin:/path) form in the path string.
    type: str
  timeout:
    description: gRPC operation timeout in seconds.
    type: int
    default: 30
  insecure:
    description: Use an insecure gRPC channel (no TLS). Not recommended in production.
    type: bool
    default: false
  ca_cert:
    description: Path to CA certificate for TLS verification.
    type: path
  client_cert:
    description: Path to client certificate for mTLS.
    type: path
  client_key:
    description: Path to client private key for mTLS.
    type: path
  tls_server_name:
    description:
      - Override the TLS server name presented in the TLS handshake.
        Maps to gRPC option C(grpc.ssl_target_name_override).
    type: str
  tls_skip_verify:
    description:
      - Establish a TLS (encrypted) channel but do not verify the device
        certificate against a CA. When set and no I(ca_cert) is provided, the
        certificate the device presents is fetched and trusted for the session
        (Trust-On-First-Use), equivalent to C(gnmic --skip-verify).
      - The channel is encrypted but the server identity is not authenticated,
        so use it only on trusted networks. Ignored when I(insecure=true) or
        when I(ca_cert) is set.
    type: bool
    default: false
  max_message_length:
    description:
      - Maximum inbound gRPC message size in bytes. Defaults to gRPC's
        4 MB. Raise this for very large SetRequests.
    type: int
  channel_options:
    description:
      - Optional dict of additional gRPC channel options merged into the
        channel configuration.
    type: dict
  platform:
    description: Target platform hint used to apply per-platform quirks.
    type: str
    choices: [auto, iosxe, iosxr, nxos]
    default: auto
requirements:
  - grpcio
  - protobuf
notes:
  - This module replaces the deprecated single-entry-point M(cisco.gnmi.gnmi) module
    (with C(operation=set)) starting in collection version 4.0.0.
  - The earlier C(state)/C(config) shorthand from pre-4.0 monolithic module is
    no longer supported. Use I(update), I(replace) and/or I(delete) directly.
'''

EXAMPLES = r'''
- name: Set interface description (Update)
  cisco.gnmi.config:
    host: "{{ ansible_host }}"
    username: "{{ gnmi_username }}"
    password: "{{ gnmi_password }}"
    update:
      - path: "/interfaces/interface[name=GigabitEthernet1]/config/description"
        value: "Uplink to core"

- name: Replace interface configuration
  cisco.gnmi.config:
    host: "{{ ansible_host }}"
    username: "{{ gnmi_username }}"
    password: "{{ gnmi_password }}"
    replace:
      - path: "/interfaces/interface[name=GigabitEthernet2]/config"
        value:
          name: "GigabitEthernet2"
          description: "Customer link"
          enabled: true

- name: Delete a configuration path
  cisco.gnmi.config:
    host: "{{ ansible_host }}"
    username: "{{ gnmi_username }}"
    password: "{{ gnmi_password }}"
    delete:
      - "/interfaces/interface[name=GigabitEthernet3]"

- name: Atomic transaction - update, replace and delete in one Set
  cisco.gnmi.config:
    host: "{{ ansible_host }}"
    username: "{{ gnmi_username }}"
    password: "{{ gnmi_password }}"
    update:
      - path: "/system/config/hostname"
        value: "edge-rtr-1"
    replace:
      - path: "/system/ntp/config"
        value:
          enabled: true
          enable-ntp-auth: false
    delete:
      - "/system/dns/servers/server[address=1.1.1.1]"

- name: Per-item origin (gnmic-style prefix on the path string)
  cisco.gnmi.config:
    host: "{{ ansible_host }}"
    username: "{{ gnmi_username }}"
    password: "{{ gnmi_password }}"
    update:
      - path: "native:/Cisco-IOS-XE-native:native/hostname"
        value: "router1"
'''

RETURN = r'''
changed:
  description: Whether the device reported a configuration change.
  returned: always
  type: bool
data:
  description: Raw response data from the gNMI SET RPC.
  returned: success
  type: dict
diff:
  description: Before/after snapshot when run with C(--diff).
  returned: when diff is requested
  type: dict
backup_file:
  description: Path to the created backup file, when C(backup=true).
  returned: when backup is created
  type: str
msg:
  description: Human-readable status message.
  returned: always
  type: str
'''

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.cisco.gnmi.plugins.module_utils.module_helper import (
    GnmiModule,
    connection_argument_spec,
    connection_required_constraints,
    fail_if_gnmi_client_missing,
)


def main():
    argument_spec = connection_argument_spec()

    set_item_spec = dict(
        path=dict(type='str', required=True),
        value=dict(type='raw', required=True),
        origin=dict(type='str'),
    )

    argument_spec.update(
        update=dict(type='list', elements='dict', options=set_item_spec),
        replace=dict(type='list', elements='dict', options=set_item_spec),
        delete=dict(type='list', elements='raw'),
        backup=dict(type='bool', default=False),
        backup_path=dict(type='path', default='./backups'),
    )

    conn_required_one_of, required_together = connection_required_constraints()
    required_one_of = conn_required_one_of + [('update', 'replace', 'delete')]

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_one_of=required_one_of,
        required_together=required_together,
    )

    fail_if_gnmi_client_missing(module)

    gnmi_module = GnmiModule(module)
    result = gnmi_module.run(operation='set')
    module.exit_json(**result)


if __name__ == '__main__':
    main()
