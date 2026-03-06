#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2025, Jeremy Cohoe <jcohoe@cisco.com>
# Apache License 2.0 (see LICENSE or http://www.apache.org/licenses/LICENSE-2.0)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: gnmi
short_description: Manage network devices using gNMI (gRPC Network Management Interface)
version_added: "2.0.0"
description:
  - This module provides an interface to interact with network devices using
    gNMI (gRPC Network Management Interface).
  - Supports GET, SET, and Subscribe operations per the gNMI specification.
  - Works with any gNMI-capable device (Cisco IOS XE, IOS XR, NX-OS,
    Nokia SR OS, Arista EOS, Juniper Junos, etc.).
  - Provides idempotency, check mode, diff mode, and configuration backup.
  - Optional I(platform) parameter enables platform-specific validation and
    defaults (e.g. encoding restrictions on Cisco IOS XE).
author:
  - Jeremy Cohoe (@jeremycohoe)
notes:
  - This module requires the C(grpcio), C(grpcio-tools), and C(protobuf) Python packages.
  - Install with C(pip install grpcio grpcio-tools protobuf).
  - gNMI must be enabled on the target device.
  - Supports check mode for safe testing of changes.
  - Diff mode shows configuration differences before and after changes.
  - "JSON_IETF encoding is recommended for most network devices."
  - "PROTO encoding may not be supported by all platforms for all RPCs."
  - See U(https://github.com/openconfig/reference/blob/master/rpc/gnmi/gnmi-specification.md)
requirements:
  - grpcio >= 1.50.0
  - grpcio-tools >= 1.50.0
  - protobuf >= 4.21.0
options:
  host:
    description:
      - Hostname or IP address of the target device.
    required: true
    type: str
  port:
    description:
      - gNMI port number.
      - Common defaults vary by platform (IOS XE 9339, IOS XR 57400, NX-OS 50051).
    default: 9339
    type: int
  username:
    description:
      - Username for device authentication.
    required: true
    type: str
  password:
    description:
      - Password for device authentication.
    required: true
    type: str
    no_log: true
  operation:
    description:
      - gNMI RPC to execute.
    choices: ['get', 'set', 'subscribe']
    default: 'get'
    type: str
  paths:
    description:
      - List of gNMI paths for the operation.
      - Required for GET and Subscribe operations.
      - For SET with I(state=absent), these are the paths to delete.
    type: list
    elements: str
  datatype:
    description:
      - Type of data to retrieve (for GET operations).
    choices: ['all', 'config', 'state', 'operational']
    default: 'all'
    type: str
  encoding:
    description:
      - Data encoding format.
      - C(json_ietf) is recommended for most platforms.
      - C(proto) may have restrictions on some platforms.
    choices: ['json', 'json_ietf', 'proto']
    default: 'json_ietf'
    type: str
  state:
    description:
      - Desired state for SET operations.
      - C(present) will update or replace configuration.
      - C(absent) will delete configuration.
    choices: ['present', 'absent']
    default: 'present'
    type: str
  config:
    description:
      - Configuration data for SET operations.
      - A list of dicts, each with C(path) and C(value) keys.
      - Alternatively, a single dict used with a single path in I(paths).
    type: raw
  replace:
    description:
      - Whether to use replace instead of update for SET operations.
      - Replace will overwrite existing configuration at the path.
      - Update will merge with existing configuration.
    default: false
    type: bool
  backup:
    description:
      - Create a backup of the current configuration before making changes.
    default: false
    type: bool
  backup_path:
    description:
      - Directory where backups will be stored.
    default: './backups'
    type: path
  timeout:
    description:
      - RPC timeout in seconds.
    default: 30
    type: int
  insecure:
    description:
      - Skip TLS certificate validation.
      - Not recommended for production use.
    default: false
    type: bool
  ca_cert:
    description:
      - Path to CA certificate file for TLS verification.
    type: path
  client_cert:
    description:
      - Path to client certificate file for mutual TLS.
    type: path
  client_key:
    description:
      - Path to client private key file for mutual TLS.
    type: path
  platform:
    description:
      - Optional platform hint to enable vendor-specific validation.
      - C(auto) applies no vendor restrictions (default).
      - C(iosxe) enforces Cisco IOS XE restrictions (e.g. no PROTO for GET/SET).
      - C(iosxr) applies Cisco IOS XR defaults.
      - C(nxos) applies Cisco NX-OS defaults.
      - C(nokia_sros) applies Nokia SR OS defaults.
      - C(arista_eos) applies Arista EOS defaults.
    choices: ['auto', 'iosxe', 'iosxr', 'nxos', 'nokia_sros', 'arista_eos']
    default: 'auto'
    type: str
  subscriptions:
    description:
      - List of subscription configurations for Subscribe operations.
    type: list
    elements: dict
    suboptions:
      path:
        description: gNMI path to subscribe to.
        type: str
        required: true
      mode:
        description: Subscription mode.
        type: str
        choices: ['target_defined', 'sample', 'on_change']
        default: 'target_defined'
      sample_interval:
        description: Sample interval in seconds (for sample mode).
        type: int
        default: 10
  subscribe_mode:
    description:
      - Mode for Subscribe operation.
    choices: ['stream', 'once', 'poll']
    default: 'once'
    type: str
  subscribe_duration:
    description:
      - Duration in seconds to collect subscription updates (stream mode only).
      - Set to 0 for infinite duration.
    default: 60
    type: int
  origin:
    description:
      - Origin value for gNMI paths.
      - Use C(rfc7951) for vendor-native YANG models.
      - Use C(openconfig) for OpenConfig models.
      - Leave empty to auto-detect from path prefixes.
    type: str
'''

EXAMPLES = r'''
# Get interface configuration
- name: Get all interface configurations
  cisco.gnmi.gnmi:
    host: "{{ inventory_hostname }}"
    port: 9339
    username: "{{ gnmi_user }}"
    password: "{{ gnmi_password }}"
    operation: get
    paths:
      - /interfaces/interface
    datatype: config
    encoding: json_ietf
  register: result

# Get specific interface
- name: Get GigabitEthernet1 configuration
  cisco.gnmi.gnmi:
    host: "{{ inventory_hostname }}"
    username: "{{ gnmi_user }}"
    password: "{{ gnmi_password }}"
    operation: get
    paths:
      - /interfaces/interface[name=GigabitEthernet1]

# Set interface description
- name: Configure interface description
  cisco.gnmi.gnmi:
    host: "{{ inventory_hostname }}"
    username: "{{ gnmi_user }}"
    password: "{{ gnmi_password }}"
    operation: set
    state: present
    config:
      - path: /interfaces/interface[name=GigabitEthernet1]/config/description
        value: "Uplink to Core"

# Set multiple configurations
- name: Configure multiple interfaces
  cisco.gnmi.gnmi:
    host: "{{ inventory_hostname }}"
    username: "{{ gnmi_user }}"
    password: "{{ gnmi_password }}"
    operation: set
    state: present
    backup: true
    config:
      - path: /interfaces/interface[name=GigabitEthernet1]/config/description
        value: "Uplink to Core"
      - path: /interfaces/interface[name=GigabitEthernet1]/config/enabled
        value: true
      - path: /interfaces/interface[name=GigabitEthernet2]/config/description
        value: "Server Connection"

# Replace interface configuration
- name: Replace interface configuration
  cisco.gnmi.gnmi:
    host: "{{ inventory_hostname }}"
    username: "{{ gnmi_user }}"
    password: "{{ gnmi_password }}"
    operation: set
    state: present
    replace: true
    config:
      - path: /interfaces/interface[name=GigabitEthernet1]/config
        value:
          description: "New Configuration"
          enabled: true
          mtu: 1500

# Delete configuration
- name: Delete interface description
  cisco.gnmi.gnmi:
    host: "{{ inventory_hostname }}"
    username: "{{ gnmi_user }}"
    password: "{{ gnmi_password }}"
    operation: set
    state: absent
    paths:
      - /interfaces/interface[name=GigabitEthernet1]/config/description

# Using TLS certificates
- name: Get configuration with TLS
  cisco.gnmi.gnmi:
    host: "{{ inventory_hostname }}"
    username: "{{ gnmi_user }}"
    password: "{{ gnmi_password }}"
    operation: get
    paths:
      - /system/config
    ca_cert: /path/to/ca.pem
    client_cert: /path/to/client.pem
    client_key: /path/to/client-key.pem

# Subscribe to interface counters (once mode)
- name: Get interface counter snapshot
  cisco.gnmi.gnmi:
    host: "{{ inventory_hostname }}"
    username: "{{ gnmi_user }}"
    password: "{{ gnmi_password }}"
    operation: subscribe
    subscribe_mode: once
    subscriptions:
      - path: /interfaces/interface[name=GigabitEthernet1]/state/counters
        mode: target_defined
  register: counters

# Cisco IOS XE with platform hint (enforces encoding restrictions)
- name: Get config from IOS XE device
  cisco.gnmi.gnmi:
    host: "{{ inventory_hostname }}"
    port: 9339
    username: "{{ gnmi_user }}"
    password: "{{ gnmi_password }}"
    platform: iosxe
    operation: get
    paths:
      - /Cisco-IOS-XE-native:native/hostname
    origin: rfc7951
'''

RETURN = r'''
data:
  description: Data returned from the gNMI operation.
  returned: success
  type: dict
  sample:
    "/interfaces/interface[name=GigabitEthernet1]/config/description": "Uplink to Core"
    "/interfaces/interface[name=GigabitEthernet1]/config/enabled": true
changed:
  description: Whether the operation made changes.
  returned: always
  type: bool
  sample: true
diff:
  description: Configuration differences (before and after).
  returned: when diff mode is enabled and operation is set
  type: dict
  sample:
    before:
      description: "Old description"
    after:
      description: "New description"
backup_file:
  description: Path to the backup file created.
  returned: when backup=true
  type: str
  sample: "./backups/192.168.1.1_20250129_120000.json"
updates:
  description: List of subscription updates received.
  returned: when operation=subscribe
  type: list
  sample:
    - timestamp: 1706529600000000000
      path: "/interfaces/interface[name=GigabitEthernet1]/state/counters"
      value:
        in-octets: 1234567
        out-octets: 7654321
msg:
  description: Status message describing the result.
  returned: always
  type: str
  sample: "Data retrieved successfully"
'''

import json
import os
import traceback
from datetime import datetime
from ansible.module_utils.basic import AnsibleModule, missing_required_lib

try:
    from ansible_collections.cisco.gnmi.plugins.module_utils.gnmi_client import (
        GnmiClient,
        GnmiClientError,
        GnmiConnectionError,
        GnmiAuthenticationError,
        GnmiOperationError,
    )
    HAS_GNMI_CLIENT = True
    GNMI_CLIENT_IMPORT_ERROR = None
except ImportError:
    HAS_GNMI_CLIENT = False
    GNMI_CLIENT_IMPORT_ERROR = traceback.format_exc()


class GnmiModule:
    """Ansible module wrapper for gNMI operations."""

    def __init__(self, module):
        self.module = module
        self.client = None
        self.result = {
            'changed': False,
            'failed': False,
            'msg': '',
            'data': {},
        }

    def _create_client(self):
        """Create and return gNMI client instance."""
        return GnmiClient(
            host=self.module.params['host'],
            port=self.module.params['port'],
            username=self.module.params['username'],
            password=self.module.params['password'],
            encoding=self.module.params['encoding'],
            timeout=self.module.params['timeout'],
            insecure=self.module.params['insecure'],
            ca_cert=self.module.params.get('ca_cert'),
            client_cert=self.module.params.get('client_cert'),
            client_key=self.module.params.get('client_key'),
            platform=self.module.params.get('platform', 'auto'),
            warn_callback=self.module.warn,
        )

    def _create_backup(self, paths):
        """Create backup of current configuration before changes."""
        if not self.module.params['backup']:
            return None

        backup_dir = self.module.params['backup_path']
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = os.path.join(
            backup_dir,
            "{0}_{1}.json".format(self.module.params['host'], timestamp),
        )

        try:
            result = self.client.get(paths=paths, datatype='config')
            if result.success:
                with open(backup_file, 'w') as fh:
                    json.dump(result.data, fh, indent=2)
                return backup_file
            self.module.warn("Failed to create backup: {0}".format(result.error))
            return None
        except Exception as exc:
            self.module.warn("Failed to create backup: {0}".format(exc))
            return None

    def _get_current_config(self, paths):
        """Get current configuration for diff comparison."""
        try:
            result = self.client.get(paths=paths, datatype='config')
            if result.success:
                return result.data
            return {}
        except Exception:
            return {}

    # ------------------------------------------------------------------
    # GET
    # ------------------------------------------------------------------

    def execute_get(self):
        """Execute a gNMI Get RPC."""
        paths = self.module.params.get('paths')
        if not paths:
            self.module.fail_json(msg="'paths' is required for GET operation")

        datatype = self.module.params['datatype']
        origin = self.module.params.get('origin')

        result = self.client.get(paths=paths, datatype=datatype, origin=origin)

        if result.success:
            self.result['data'] = result.data
            self.result['msg'] = 'Data retrieved successfully'
        else:
            self.module.fail_json(msg=result.error)

    # ------------------------------------------------------------------
    # SET
    # ------------------------------------------------------------------

    def execute_set(self):
        """Execute a gNMI Set RPC."""
        state = self.module.params['state']
        config = self.module.params.get('config')
        paths = self.module.params.get('paths')
        replace = self.module.params['replace']
        origin = self.module.params.get('origin')

        # Determine paths for backup and diff
        backup_paths = []
        if state == 'absent' and paths:
            backup_paths = paths
        elif config:
            if isinstance(config, list):
                backup_paths = [item['path'] for item in config if isinstance(item, dict) and 'path' in item]
            else:
                backup_paths = paths or []

        # Create backup if requested
        backup_file = self._create_backup(backup_paths) if backup_paths else None
        if backup_file:
            self.result['backup_file'] = backup_file

        # Get current config for diff
        before_config = {}
        if self.module._diff and backup_paths:
            before_config = self._get_current_config(backup_paths)

        # Check mode - don't make actual changes
        if self.module.check_mode:
            self.result['changed'] = True
            self.result['msg'] = 'Check mode: changes would be applied'
            if self.module._diff:
                self.result['diff'] = {
                    'before': before_config,
                    'after': 'Changes would be applied',
                }
            return

        # Execute the operation
        if state == 'absent':
            if not paths:
                self.module.fail_json(msg="'paths' is required for delete (state=absent)")
            result = self.client.set(delete=paths, origin=origin)
        else:
            if not config:
                self.module.fail_json(msg="'config' is required when state=present")

            updates = []
            if isinstance(config, list):
                for item in config:
                    if not isinstance(item, dict) or 'path' not in item or 'value' not in item:
                        self.module.fail_json(
                            msg="Each config item must be a dict with 'path' and 'value' keys")
                    updates.append((item['path'], item['value']))
            elif isinstance(config, dict) and paths and len(paths) == 1:
                updates.append((paths[0], config))
            else:
                self.module.fail_json(
                    msg="config must be a list of dicts or a single dict with a corresponding path")

            if replace:
                result = self.client.set(replace=updates, origin=origin)
            else:
                result = self.client.set(update=updates, origin=origin)

        if result.success:
            self.result['changed'] = result.changed
            self.result['data'] = result.data
            self.result['msg'] = 'Configuration updated successfully'

            if self.module._diff and backup_paths:
                after_config = self._get_current_config(backup_paths)
                self.result['diff'] = {
                    'before': before_config,
                    'after': after_config,
                }
        else:
            self.module.fail_json(msg=result.error)

    # ------------------------------------------------------------------
    # SUBSCRIBE
    # ------------------------------------------------------------------

    def execute_subscribe(self):
        """Execute a gNMI Subscribe RPC."""
        subscriptions_param = self.module.params.get('subscriptions')
        if not subscriptions_param:
            self.module.fail_json(msg="'subscriptions' is required for subscribe operation")

        origin = self.module.params.get('origin')
        subscribe_mode = self.module.params.get('subscribe_mode', 'once')

        subscription_tuples = []
        for sub in subscriptions_param:
            path = sub['path']
            mode = sub.get('mode', 'target_defined')
            interval = sub.get('sample_interval', 10)
            subscription_tuples.append((path, mode, interval))

        result = self.client.subscribe(
            subscriptions=subscription_tuples,
            mode=subscribe_mode,
            origin=origin,
        )

        if result.success:
            self.result['updates'] = result.data.get('updates', [])
            self.result['msg'] = 'Subscription completed successfully'
        else:
            self.module.fail_json(msg=result.error)

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run(self):
        """Main execution method."""
        try:
            self.client = self._create_client()
            self.client.connect()

            operation = self.module.params['operation']

            if operation == 'get':
                self.execute_get()
            elif operation == 'set':
                self.execute_set()
            elif operation == 'subscribe':
                self.execute_subscribe()
            else:
                self.module.fail_json(msg="Unsupported operation: {0}".format(operation))

        except GnmiConnectionError as exc:
            self.module.fail_json(msg="Connection error: {0}".format(exc))
        except GnmiAuthenticationError as exc:
            self.module.fail_json(msg="Authentication error: {0}".format(exc))
        except GnmiOperationError as exc:
            self.module.fail_json(msg="Operation error: {0}".format(exc))
        except GnmiClientError as exc:
            self.module.fail_json(msg="gNMI client error: {0}".format(exc))
        except Exception as exc:
            self.module.fail_json(
                msg="Unexpected error: {0}".format(exc),
                exception=traceback.format_exc(),
            )
        finally:
            if self.client:
                self.client.disconnect()

        return self.result


def main():
    """Module entry point."""
    argument_spec = dict(
        host=dict(type='str', required=True),
        port=dict(type='int', default=9339),
        username=dict(type='str', required=True),
        password=dict(type='str', required=True, no_log=True),
        operation=dict(type='str', default='get', choices=['get', 'set', 'subscribe']),
        paths=dict(type='list', elements='str'),
        datatype=dict(type='str', default='all', choices=['all', 'config', 'state', 'operational']),
        encoding=dict(type='str', default='json_ietf', choices=['json', 'json_ietf', 'proto']),
        state=dict(type='str', default='present', choices=['present', 'absent']),
        config=dict(type='raw'),
        replace=dict(type='bool', default=False),
        backup=dict(type='bool', default=False),
        backup_path=dict(type='path', default='./backups'),
        timeout=dict(type='int', default=30),
        insecure=dict(type='bool', default=False),
        ca_cert=dict(type='path'),
        client_cert=dict(type='path'),
        client_key=dict(type='path'),
        platform=dict(
            type='str', default='auto',
            choices=['auto', 'iosxe', 'iosxr', 'nxos', 'nokia_sros', 'arista_eos'],
        ),
        subscriptions=dict(
            type='list', elements='dict',
            options=dict(
                path=dict(type='str', required=True),
                mode=dict(type='str', default='target_defined',
                          choices=['target_defined', 'sample', 'on_change']),
                sample_interval=dict(type='int', default=10),
            ),
        ),
        subscribe_mode=dict(type='str', default='once', choices=['stream', 'once', 'poll']),
        subscribe_duration=dict(type='int', default=60),
        origin=dict(type='str'),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_if=[
            ('operation', 'get', ['paths']),
            ('operation', 'subscribe', ['subscriptions']),
        ],
    )

    if not HAS_GNMI_CLIENT:
        module.fail_json(
            msg=missing_required_lib('gnmi_client (grpcio, protobuf)'),
            exception=GNMI_CLIENT_IMPORT_ERROR,
        )

    gnmi_module = GnmiModule(module)
    result = gnmi_module.run()

    module.exit_json(**result)


if __name__ == '__main__':
    main()
