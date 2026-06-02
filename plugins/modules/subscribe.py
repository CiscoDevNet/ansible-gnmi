#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright 2025 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: subscribe
short_description: Subscribe to streaming telemetry from a Cisco device via gNMI
description:
  - Performs gNMI Subscribe RPCs against Cisco devices (IOS-XE, IOS-XR, NX-OS).
  - Supports C(once), C(stream) and C(poll) subscription modes.
  - Read-only — never reports C(changed=true).
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
  subscriptions:
    description:
      - List of subscription specifications. Each entry is a dict with
        C(path), optional C(mode) (C(target_defined), C(on_change),
        C(sample)) and optional C(sample_interval) in seconds.
    type: list
    elements: dict
    required: true
    suboptions:
      path:
        description: gNMI path to subscribe to.
        type: str
        required: true
      mode:
        description: Per-subscription mode.
        type: str
        default: target_defined
        choices: [target_defined, on_change, sample]
      sample_interval:
        description: Sample interval (seconds) when C(mode=sample).
        type: int
        default: 10
  subscribe_mode:
    description: Overall subscription mode.
    type: str
    choices: [stream, once, poll]
    default: stream
  subscribe_duration:
    description: How long (seconds) to keep a C(stream) subscription open
      before returning.
    type: int
    default: 60
  encoding:
    description: Encoding to request from the target.
    type: str
    choices: [json, json_ietf, proto, bytes, ascii]
    default: json_ietf
  origin:
    description: Origin for the gNMI paths.
    type: str
  timeout:
    description: gRPC connection timeout in seconds.
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
      - Override the TLS server name presented in the TLS handshake
        (gRPC option C(grpc.ssl_target_name_override)).
    type: str
  max_message_length:
    description:
      - Maximum inbound gRPC message size in bytes. Defaults to gRPC's 4 MB.
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
    (with C(operation=subscribe)) starting in collection version 4.0.0.
'''

EXAMPLES = r'''
- name: One-shot subscribe to interface counters
  cisco.gnmi.subscribe:
    host: "{{ ansible_host }}"
    username: "{{ gnmi_username }}"
    password: "{{ gnmi_password }}"
    subscribe_mode: once
    subscriptions:
      - path: "/interfaces/interface/state/counters"

- name: Stream sampled CPU usage for 30 seconds
  cisco.gnmi.subscribe:
    host: "{{ ansible_host }}"
    username: "{{ gnmi_username }}"
    password: "{{ gnmi_password }}"
    subscribe_mode: stream
    subscribe_duration: 30
    subscriptions:
      - path: "/components/component/state/cpu"
        mode: sample
        sample_interval: 5
'''

RETURN = r'''
updates:
  description: List of telemetry updates received from the device.
  returned: success
  type: list
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
        subscriptions=dict(
            type='list', elements='dict', required=True,
            options=dict(
                path=dict(type='str', required=True),
                mode=dict(
                    type='str', default='target_defined',
                    choices=['target_defined', 'on_change', 'sample'],
                ),
                sample_interval=dict(type='int', default=10),
            ),
        ),
        subscribe_mode=dict(
            type='str', default='stream',
            choices=['stream', 'once', 'poll'],
        ),
        subscribe_duration=dict(type='int', default=60),
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
    result = gnmi_module.run(operation='subscribe')
    module.exit_json(**result)


if __name__ == '__main__':
    main()
