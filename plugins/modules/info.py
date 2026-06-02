#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright 2025 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: info
short_description: Retrieve operational and configuration data from a Cisco device using gNMI
description:
  - Performs gNMI GET requests against Cisco devices (IOS-XE, IOS-XR, NX-OS).
  - Read-only module — never reports C(changed=true).
  - This is the read counterpart to M(cisco.gnmi.config).
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
  paths:
    description:
      - List of gNMI paths to retrieve.
      - Each path may include an explicit origin prefix using the
        C(origin:/path) form (e.g. C(openconfig:/interfaces) or
        C(native:/Cisco-IOS-XE-native:native)). This per-path origin
        overrides the module-level I(origin) option for that path only.
    type: list
    elements: str
    required: true
  prefix:
    description:
      - Optional common path prefix applied to every entry in I(paths).
      - When set, the device evaluates each path relative to this prefix
        in the same SetRequest, reducing on-the-wire size for bulk reads.
    type: str
  datatype:
    description: Type of data to retrieve.
    type: str
    choices: [all, config, state, operational]
    default: all
  encoding:
    description: Encoding to request from the target.
    type: str
    choices: [json, json_ietf, proto, bytes, ascii]
    default: json_ietf
  origin:
    description:
      - Default origin for gNMI paths (e.g. C(openconfig), C(rfc7951)).
      - Individual paths may override this via the C(origin:/path) prefix.
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
      - Useful when the device certificate's SAN/CN does not match the
        address used to connect (e.g. connecting by IP to a cert issued
        for a hostname). Maps to gRPC option
        C(grpc.ssl_target_name_override).
    type: str
  max_message_length:
    description:
      - Maximum inbound gRPC message size in bytes. Defaults to gRPC's
        4 MB. Raise this for devices that return very large
        GetResponses (e.g. full-tree dumps).
    type: int
  channel_options:
    description:
      - Optional dict of additional gRPC channel options merged into the
        channel configuration (e.g. C(grpc.keepalive_time_ms)).
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
    (with C(operation=get)) starting in collection version 4.0.0.
'''

EXAMPLES = r'''
- name: Get interface configuration
  cisco.gnmi.info:
    host: "{{ ansible_host }}"
    username: "{{ gnmi_username }}"
    password: "{{ gnmi_password }}"
    paths:
      - "/interfaces/interface"
    datatype: config

- name: Get operational state for a specific interface
  cisco.gnmi.info:
    host: "{{ ansible_host }}"
    username: "{{ gnmi_username }}"
    password: "{{ gnmi_password }}"
    paths:
      - "/interfaces/interface[name=GigabitEthernet1]/state"
    datatype: state
'''

RETURN = r'''
data:
  description: The data retrieved from the device, keyed by path.
  returned: success
  type: dict
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
    argument_spec.update(
        paths=dict(type='list', elements='str', required=True),
        prefix=dict(type='str'),
        datatype=dict(
            type='str', default='all',
            choices=['all', 'config', 'state', 'operational'],
        ),
    )

    required_one_of, required_together = connection_required_constraints()

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_one_of=required_one_of,
        required_together=required_together,
    )

    fail_if_gnmi_client_missing(module)

    gnmi_module = GnmiModule(module)
    result = gnmi_module.run(operation='get')
    module.exit_json(**result)


if __name__ == '__main__':
    main()
