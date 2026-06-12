#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright 2025 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: gnoi
short_description: Perform OpenConfig gNOI operations on a Cisco device
description:
  - Generic module for OpenConfig gNOI (gRPC Network Operations Interface)
    operations.
  - Uses a service/operation dispatch model so a single module covers all
    supported gNOI services.
  - The initial release implements the gNOI services supported by Cisco
    IOS XE - Certificate Management (C(cert)), OS Installation (C(os)), and
    Factory Reset (C(factory_reset)).
  - Reuses the same gRPC transport and authentication model as the
    M(cisco.gnmi.info) / M(cisco.gnmi.config) modules. On IOS XE, gNOI is
    served on the same gRPC endpoint as gNMI (default port 9339).
version_added: "4.1.0"
author:
  - "Cisco Systems (@cisco)"
options:
  host:
    description: Hostname or IP address of the target device.
    type: str
    required: true
  port:
    description: gRPC service port (gNOI shares the gNMI port on IOS XE).
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
    description: Path to client certificate for mutual TLS.
    type: path
  client_key:
    description: Path to client private key for mutual TLS.
    type: path
  tls_server_name:
    description:
      - Override the TLS server name presented in the TLS handshake. Maps to
        the gRPC option C(grpc.ssl_target_name_override).
    type: str
  tls_skip_verify:
    description:
      - Establish a TLS (encrypted) channel but do not verify the device
        certificate against a known CA. When set and no I(ca_cert) is
        provided, the module fetches the certificate the device presents and
        trusts it for the session (Trust-On-First-Use), equivalent to
        C(gnmic --skip-verify).
      - Use this to connect to the secure gNOI/gNMI port (default 9339) with a
        self-signed device certificate without managing a CA file. The channel
        is encrypted but the server identity is not authenticated, so only use
        it on trusted networks.
      - Ignored when I(insecure=true) (plaintext) or when I(ca_cert) is set
        (explicit CA pin takes precedence).
    type: bool
    default: false
  max_message_length:
    description:
      - Maximum inbound/outbound gRPC message size in bytes. Defaults to
        gRPC's 4 MB.
    type: int
  channel_options:
    description:
      - Optional dict of additional gRPC channel options merged into the
        channel configuration (e.g. C(grpc.keepalive_time_ms)).
    type: dict
  platform:
    description:
      - Target platform hint. Used to validate that the requested service and
        operation are supported. Use C(auto) to attempt the operation
        regardless and let the device decide.
    type: str
    choices: [auto, iosxe, iosxr, nxos]
    default: auto
  service:
    description: The gNOI service to invoke.
    type: str
    required: true
    choices: [cert, os, factory_reset]
  operation:
    description:
      - The operation to perform within the chosen I(service).
      - "C(cert): install, rotate, revoke, get, can_generate_csr."
      - "C(os): install, activate, verify."
      - "C(factory_reset): start."
    type: str
    required: true
  confirm:
    description:
      - Must be set to C(true) to run destructive or service-affecting
        operations (C(os/activate), C(factory_reset/start)). The module fails
        safely if confirmation is required but absent.
    type: bool
    default: false
  chunk_size:
    description:
      - Streaming chunk size in bytes used when transferring an OS image
        (C(os/install)).
    type: int
    default: 1048576
  args:
    description:
      - Operation-specific parameters. Only the keys relevant to the chosen
        I(service)/I(operation) are used.
    type: dict
    suboptions:
      certificate_id:
        description: Certificate identifier (cert install/rotate).
        type: str
      certificate_ids:
        description: List of certificate identifiers (cert revoke).
        type: list
        elements: str
      certificate:
        description: PEM-encoded certificate (cert install/rotate).
        type: str
      private_key:
        description: PEM-encoded private key (cert install/rotate).
        type: str
      ca_certificate:
        description: PEM-encoded CA certificate bundle (cert install/rotate).
        type: str
      key_size:
        description: RSA key size in bits (cert can_generate_csr).
        type: int
        default: 2048
      image_path:
        description: Local path to the OS image to stream (os install).
        type: path
      version:
        description:
          - OS version string (os install/activate/verify).
          - Optional for C(os/install) and C(os/activate). When omitted and
            C(image_path) is given, the module derives the canonical version
            (C(CW_FULL_VERSION)) from the image header, so you normally only
            need to supply C(image_path).
        type: str
      no_reboot:
        description:
          - When C(true), os/activate sets the next-boot version without
            immediately rebooting.
        type: bool
        default: false
      standby_supervisor:
        description: Target the standby supervisor (os install/activate).
        type: bool
        default: false
      zero_fill:
        description:
          - Zero-fill persistent storage during factory reset.
          - Some IOS XE builds (for example 26.01.01a) only accept a factory
            reset when this is C(true) and reject C(false) with
            C(INVALID_ARGUMENT).
        type: bool
        default: false
      factory_os:
        description:
          - Request factory OS rollback during factory reset. Not supported on
            IOS XE.
        type: bool
        default: false
      retain_certs:
        description: Retain certificates across a factory reset where supported.
        type: bool
        default: false
requirements:
  - grpcio
  - protobuf
notes:
  - Destructive operations require C(confirm=true).
  - In check mode, mutating operations are not executed; the module reports
    C(changed=true) with C(skipped_rpc=true).
  - Sensitive values such as private keys are never returned in results.
  - On IOS XE, C(cert/install) expects the on-box GenerateCSR workflow; loading
    an externally generated certificate and private key directly may be
    rejected by the device with C(ABORTED). See CISCO_GNMI_CAVEATS.md.
  - C(os/install) is idempotent; if the requested version is already present
    the device validates without a transfer and the module reports
    C(changed=false). C(os/activate) checks the running version first and skips
    the reboot when it already matches.
  - For C(os/install) and C(os/activate) you may omit C(version) and supply
    only C(image_path); the module reads the C(CW_FULL_VERSION) marker from the
    image header and uses that exact value for the transfer and activation.
  - C(os/activate) requires the device running-config to be saved. If the
    configuration was modified out-of-band (for example via the CLI) the
    device rejects activation with "System configuration has been modified.
    Please save configuration and resubmit command." There is no save-config
    RPC in gNMI/gNOI, but IOS XE gNMI Configuration Persistence (enabled by
    default) writes the ENTIRE running-config - including changes made by
    processes other than gNMI - to the startup configuration whenever a
    successful gNMI C(SetRequest) is issued. So if activation is blocked,
    persist the configuration first by making any successful config change
    with M(cisco.gnmi.config) - for example set C(hostname) to a new value and
    then back to its original value (or simply set it to its current value) -
    and then run C(os/activate) again.
seealso:
  - module: cisco.gnmi.info
  - module: cisco.gnmi.config
  - name: Cisco IOS XE gNOI documentation
    description: Cisco IOS XE programmability configuration guide covering gNOI.
    link: https://www.cisco.com/c/en/us/td/docs/ios-xml/ios/prog/configuration/26x/26x-programmability-cg/gnoi.html
'''

EXAMPLES = r'''
- name: Install IOS XE image using gNOI
  cisco.gnmi.gnoi:
    host: "{{ inventory_hostname }}"
    username: "{{ ansible_user }}"
    password: "{{ ansible_password }}"
    platform: iosxe
    service: os
    operation: install
    args:
      # version is derived from the image header (CW_FULL_VERSION) when omitted
      image_path: /images/cat9k_iosxe.17.18.01a.SPA.bin

- name: Verify OS over TLS without managing a CA file (skip-verify / TOFU)
  cisco.gnmi.gnoi:
    host: "{{ inventory_hostname }}"
    port: 9339
    username: "{{ ansible_user }}"
    password: "{{ ansible_password }}"
    tls_skip_verify: true
    platform: iosxe
    service: os
    operation: verify

- name: Activate IOS XE image (reboots device)
  cisco.gnmi.gnoi:
    host: "{{ inventory_hostname }}"
    username: "{{ ansible_user }}"
    password: "{{ ansible_password }}"
    platform: iosxe
    service: os
    operation: activate
    confirm: true
    args:
      # version is derived from the image header (CW_FULL_VERSION) when omitted
      image_path: /images/cat9k_iosxe.17.18.01a.SPA.bin

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
      # Some IOS XE builds require zero_fill: true (a false value is rejected).
      zero_fill: true
'''

RETURN = r'''
changed:
  description: Whether the operation changed device state.
  type: bool
  returned: always
service:
  description: The gNOI service that was invoked.
  type: str
  returned: always
operation:
  description: The operation that was performed.
  type: str
  returned: always
skipped_rpc:
  description: True when a mutating RPC was skipped because of check mode.
  type: bool
  returned: when in check mode for a mutating operation
response:
  description: Operation-specific result details.
  type: dict
  returned: on success
  sample:
    version: 17.18.01a
    bytes_transferred: 1234567890
    transfer_state: completed
    install_state: validated
    duration_seconds: 842
grpc_code:
  description: Normalised gRPC status code when an RPC fails.
  type: str
  returned: on gRPC failure
grpc_message:
  description: Server-supplied detail when an RPC fails.
  type: str
  returned: on gRPC failure
msg:
  description: Human-readable result or error message.
  type: str
  returned: always
'''

import traceback

from ansible.module_utils.basic import AnsibleModule, missing_required_lib

try:
    from ansible_collections.cisco.gnmi.plugins.module_utils.gnoi.client import (
        GnoiClient,
        GnoiClientError,
        GnoiConnectionError,
        GnoiAuthenticationError,
        GnoiOperationError,
    )
    from ansible_collections.cisco.gnmi.plugins.module_utils.gnoi.handler import (
        GnoiRequest,
        DispatchError,
        dispatch,
    )
    HAS_GNOI = True
    GNOI_IMPORT_ERROR = None
except ImportError:
    HAS_GNOI = False
    GNOI_IMPORT_ERROR = traceback.format_exc()

    class GnoiClientError(Exception):
        pass

    class GnoiConnectionError(GnoiClientError):
        pass

    class GnoiAuthenticationError(GnoiClientError):
        pass

    class GnoiOperationError(GnoiClientError):
        pass

    class DispatchError(Exception):
        pass


def argument_spec():
    """Build the argument spec for the gNOI module."""
    return dict(
        host=dict(type='str', required=True),
        port=dict(type='int', default=9339),
        username=dict(type='str'),
        password=dict(type='str', no_log=True),
        token=dict(type='str', no_log=True),
        timeout=dict(type='int', default=30),
        insecure=dict(type='bool', default=False),
        ca_cert=dict(type='path'),
        client_cert=dict(type='path'),
        client_key=dict(type='path'),
        tls_server_name=dict(type='str'),
        tls_skip_verify=dict(type='bool', default=False),
        max_message_length=dict(type='int'),
        channel_options=dict(type='dict'),
        platform=dict(type='str', default='auto',
                      choices=['auto', 'iosxe', 'iosxr', 'nxos']),
        service=dict(type='str', required=True,
                     choices=['cert', 'os', 'factory_reset']),
        operation=dict(type='str', required=True),
        confirm=dict(type='bool', default=False),
        chunk_size=dict(type='int', default=1048576),
        args=dict(
            type='dict',
            options=dict(
                certificate_id=dict(type='str'),
                certificate_ids=dict(type='list', elements='str'),
                certificate=dict(type='str'),
                private_key=dict(type='str', no_log=True),
                ca_certificate=dict(type='str'),
                key_size=dict(type='int', default=2048),
                image_path=dict(type='path'),
                version=dict(type='str'),
                no_reboot=dict(type='bool', default=False),
                standby_supervisor=dict(type='bool', default=False),
                zero_fill=dict(type='bool', default=False),
                factory_os=dict(type='bool', default=False),
                retain_certs=dict(type='bool', default=False),
            ),
        ),
    )


def build_client(module):
    """Instantiate a GnoiClient from module parameters."""
    return GnoiClient(
        host=module.params['host'],
        port=module.params['port'],
        username=module.params.get('username'),
        password=module.params.get('password'),
        token=module.params.get('token'),
        timeout=module.params['timeout'],
        insecure=module.params['insecure'],
        ca_cert=module.params.get('ca_cert'),
        client_cert=module.params.get('client_cert'),
        client_key=module.params.get('client_key'),
        tls_server_name=module.params.get('tls_server_name'),
        tls_skip_verify=module.params.get('tls_skip_verify'),
        max_message_length=module.params.get('max_message_length'),
        channel_options=module.params.get('channel_options'),
        warn_callback=module.warn,
    )


def main():
    module = AnsibleModule(
        argument_spec=argument_spec(),
        supports_check_mode=True,
        required_one_of=[('username', 'token')],
        required_together=[('username', 'password')],
    )

    if not HAS_GNOI:
        module.fail_json(
            msg=missing_required_lib('gNOI client (grpcio, protobuf)'),
            exception=GNOI_IMPORT_ERROR,
        )

    client = None
    try:
        client = build_client(module)
        client.connect()

        request = GnoiRequest(
            client=client,
            service=module.params['service'],
            operation=module.params['operation'],
            args=module.params.get('args') or {},
            params=module.params,
            check_mode=module.check_mode,
            timeout=module.params['timeout'],
            chunk_size=module.params['chunk_size'],
            warn=module.warn,
        )

        result = dispatch(
            request,
            platform=module.params.get('platform', 'auto'),
            confirm=module.params.get('confirm', False),
        )

    except DispatchError as exc:
        module.fail_json(msg=str(exc))
    except GnoiConnectionError as exc:
        module.fail_json(msg="Connection error: {0}".format(exc))
    except GnoiAuthenticationError as exc:
        module.fail_json(msg="Authentication error: {0}".format(exc))
    except GnoiOperationError as exc:
        failure = {'msg': "Operation error: {0}".format(exc)}
        if getattr(exc, 'grpc_code', None):
            failure['grpc_code'] = exc.grpc_code
        if getattr(exc, 'grpc_message', None):
            failure['grpc_message'] = exc.grpc_message
        module.fail_json(**failure)
    except GnoiClientError as exc:
        module.fail_json(msg="gNOI client error: {0}".format(exc))
    except Exception as exc:
        module.fail_json(
            msg="Unexpected error: {0}".format(exc),
            exception=traceback.format_exc(),
        )
    finally:
        if client:
            client.disconnect()

    module.exit_json(**result)


if __name__ == '__main__':
    main()
