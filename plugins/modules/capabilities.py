#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright 2025 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: capabilities
short_description: Retrieve gNMI capabilities (supported models, encodings, version) from a Cisco device
description:
  - Performs a gNMI Capabilities RPC against Cisco devices (IOS-XE, IOS-XR, NX-OS).
  - Returns the gNMI protocol version, supported encodings and the list of
    supported YANG models reported by the target.
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
  encoding:
    description: Encoding to advertise on the channel (does not affect the
      Capabilities RPC itself, which carries no data payload).
    type: str
    choices: [json, json_ietf, proto, bytes, ascii]
    default: json_ietf
  origin:
    description: Unused for Capabilities; accepted for argument-spec symmetry
      with the other cisco.gnmi modules.
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
      - Override the TLS server name presented in the TLS handshake
        (gRPC option C(grpc.ssl_target_name_override)).
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
'''

EXAMPLES = r'''
- name: Discover gNMI capabilities of a device
  cisco.gnmi.capabilities:
    host: "{{ ansible_host }}"
    username: "{{ gnmi_username }}"
    password: "{{ gnmi_password }}"
  register: caps

- name: Show the gNMI protocol version
  ansible.builtin.debug:
    var: caps.data.gnmi_version

- name: Assert openconfig-interfaces is supported
  ansible.builtin.assert:
    that:
      - "'openconfig-interfaces' in (caps.data.supported_models | map(attribute='name') | list)"

- name: Discover capabilities over TLS without a CA file (skip-verify / TOFU)
  cisco.gnmi.capabilities:
    host: "{{ ansible_host }}"
    port: 9339
    username: "{{ gnmi_username }}"
    password: "{{ gnmi_password }}"
    platform: iosxe
    tls_skip_verify: true
  register: caps
'''

RETURN = r'''
data:
  description: Capabilities reported by the target.
  returned: success
  type: dict
  contains:
    gnmi_version:
      description: gNMI protocol version string reported by the device.
      type: str
    supported_encodings:
      description: List of encoding names the device supports (e.g. C(JSON_IETF), C(PROTO)).
      type: list
      elements: str
    supported_models:
      description: List of YANG models the device supports.
      type: list
      elements: dict
      contains:
        name:
          description: YANG module name.
          type: str
        organization:
          description: Organisation that publishes the module.
          type: str
        version:
          description: Module revision / version string.
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
    required_one_of, required_together = connection_required_constraints()
    module = AnsibleModule(
        argument_spec=connection_argument_spec(),
        supports_check_mode=True,
        required_one_of=required_one_of,
        required_together=required_together,
    )

    fail_if_gnmi_client_missing(module)

    gnmi_module = GnmiModule(module)
    result = gnmi_module.run(operation='capabilities')
    module.exit_json(**result)


if __name__ == '__main__':
    main()
