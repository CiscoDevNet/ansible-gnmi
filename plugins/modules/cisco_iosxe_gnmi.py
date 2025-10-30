#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2025, John Cohoe <jcohoe@cisco.com>
# Apache License 2.0 (see LICENSE or http://www.apache.org/licenses/LICENSE-2.0)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: cisco_iosxe_gnmi
short_description: Manage Cisco IOS XE devices using gNMI
version_added: "1.0.0"
description:
  - This module provides an interface to interact with Cisco IOS XE devices using gNMI (gRPC Network Management Interface).
  - Supports GET, SET, and Subscribe operations per Cisco IOS XE gNMI specification.
  - Provides feature parity with Ansible NETCONF/RESTCONF modules.
  - Supports idempotency, check mode, diff mode, and configuration backup.
  - Implements Cisco IOS XE specific requirements and restrictions.
  - See CISCO_GNMI_CAVEATS.md for complete documentation of Cisco IOS XE requirements.
author:
  - John Cohoe (@jcohoe)
notes:
  - This module requires the grpcio, grpcio-tools, and protobuf Python packages.
  - Install with C(pip install grpcio grpcio-tools protobuf).
  - gNMI must be enabled on the target Cisco IOS XE device.
  - Supports check mode for safe testing of changes.
  - Diff mode shows configuration differences before and after changes.
  - "IMPORTANT: BYTES and ASCII encodings are NOT supported on Cisco IOS XE."
  - "IMPORTANT: PROTO encoding only works with Subscribe RPC (not GET/SET)."
  - "Configuration changes automatically persist to startup-config (IOS XE 17.3.1+)."
  - "JSON_IETF encoding is RECOMMENDED for Cisco IOS XE devices."
  - "Default secure port is 9339, insecure port is 50052."
  - See https://www.cisco.com/c/en/us/td/docs/ios-xml/ios/prog/configuration/1718/b-1718-programmability-cg/gnmi.html
requirements:
  - grpcio >= 1.50.0
  - grpcio-tools >= 1.50.0
  - protobuf >= 4.21.0
  - cisco-gnmi >= 1.0.0 (or gnmi-proto)
  - Cisco IOS XE 16.8.1a or later for basic gNMI support
  - Cisco IOS XE 17.11.1 or later for PROTO encoding (Subscribe only)
  - Cisco IOS XE 17.3.1 or later for automatic configuration persistence
options:
  host:
    description:
      - Hostname or IP address of the target device.
    required: true
    type: str
  port:
    description:
      - gNMI port number.
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
      - Operation to perform.
    choices: ['get', 'set', 'subscribe']
    default: 'get'
    type: str
  paths:
    description:
      - List of gNMI paths for the operation.
      - For GET operation, these are the paths to retrieve.
      - For SET operation with state=present, these are the paths to update/replace.
      - For SET operation with state=absent, these are the paths to delete.
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
      - "RECOMMENDED: Use json_ietf for Cisco IOS XE (RFC 7951 compliant)."
      - "WARNING: BYTES and ASCII are NOT supported on Cisco IOS XE."
      - "WARNING: PROTO encoding ONLY works with Subscribe operations (not GET/SET)."
      - PROTO encoding requires IOS XE Dublin 17.11.1 or later.
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
      - Can be a single value or a list of path-value pairs.
      - If a list, each element should be a dict with 'path' and 'value' keys.
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
      - Backup is saved in the backup_path directory.
    default: false
    type: bool
  backup_path:
    description:
      - Path where backups will be stored.
    default: './backups'
    type: str
  timeout:
    description:
      - Connection timeout in seconds.
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
    type: str
  client_cert:
    description:
      - Path to client certificate file for mutual TLS.
    type: str
  client_key:
    description:
      - Path to client private key file for mutual TLS.
    type: str
  subscriptions:
    description:
      - List of subscription configurations for Subscribe operations.
      - Each subscription should have 'path', 'mode', and optionally 'sample_interval'.
    type: list
    elements: dict
    suboptions:
      path:
        description: gNMI path to subscribe to
        type: str
        required: true
      mode:
        description: Subscription mode
        type: str
        choices: ['target_defined', 'sample', 'on_change']
        default: 'target_defined'
      sample_interval:
        description: Sample interval in seconds (for sample mode)
        type: int
        default: 10
  subscribe_mode:
    description:
      - Mode for Subscribe operation.
      - C(stream) for continuous streaming.
      - C(once) for a single snapshot.
      - C(poll) for poll-based updates.
    choices: ['stream', 'once', 'poll']
    default: 'once'
    type: str
  subscribe_duration:
    description:
      - Duration in seconds to collect subscription updates.
      - Only applies to stream mode.
      - Set to 0 for infinite duration (must be manually stopped).
    default: 60
    type: int
  origin:
    description:
      - Origin value for gNMI paths (vendor-specific identifier).
      - Use C(rfc7951) for Cisco native YANG models (Cisco-IOS-XE-*).
      - Use C(openconfig) or leave empty for OpenConfig models.
      - Use C(rfc7951) for IETF models (ietf-*).
      - Use C(rfc7951) for SNMP MIBs accessible via gNMI.
    type: str
'''

EXAMPLES = r'''
# Get interface configuration
- name: Get all interface configurations
  cisco.iosxe_gnmi.cisco_iosxe_gnmi:
    host: 192.168.1.1
    port: 9339
    username: admin
    password: cisco123
    operation: get
    paths:
      - /interfaces/interface
    datatype: config
    encoding: json_ietf
  register: result

# Get specific interface
- name: Get GigabitEthernet1 configuration
  cisco.iosxe_gnmi.cisco_iosxe_gnmi:
    host: 192.168.1.1
    username: admin
    password: cisco123
    operation: get
    paths:
      - /interfaces/interface[name=GigabitEthernet1]

# Set interface description
- name: Configure interface description
  cisco.iosxe_gnmi.cisco_iosxe_gnmi:
    host: 192.168.1.1
    username: admin
    password: cisco123
    operation: set
    state: present
    config:
      - path: /interfaces/interface[name=GigabitEthernet1]/config/description
        value: "Uplink to Core"

# Set multiple configurations
- name: Configure multiple interfaces
  cisco.iosxe_gnmi.cisco_iosxe_gnmi:
    host: 192.168.1.1
    username: admin
    password: cisco123
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
  cisco.iosxe_gnmi.cisco_iosxe_gnmi:
    host: 192.168.1.1
    username: admin
    password: cisco123
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
  cisco.iosxe_gnmi.cisco_iosxe_gnmi:
    host: 192.168.1.1
    username: admin
    password: cisco123
    operation: set
    state: absent
    paths:
      - /interfaces/interface[name=GigabitEthernet1]/config/description

# Using TLS certificates
- name: Get configuration with TLS
  cisco.iosxe_gnmi.cisco_iosxe_gnmi:
    host: 192.168.1.1
    username: admin
    password: cisco123
    operation: get
    paths:
      - /system/config
    ca_cert: /path/to/ca.pem
    client_cert: /path/to/client.pem
    client_key: /path/to/client-key.pem
'''

RETURN = r'''
data:
  description: Data returned from the gNMI operation
  returned: success
  type: dict
  sample:
    "/interfaces/interface[name=GigabitEthernet1]/config/description": "Uplink to Core"
    "/interfaces/interface[name=GigabitEthernet1]/config/enabled": true
changed:
  description: Whether the operation made changes
  returned: always
  type: bool
  sample: true
diff:
  description: Configuration differences (before and after)
  returned: when diff mode is enabled
  type: dict
  sample:
    before:
      description: "Old description"
    after:
      description: "New description"
backup_file:
  description: Path to the backup file created
  returned: when backup=true
  type: str
  sample: "./backups/192.168.1.1_20250129_120000.json"
updates:
  description: List of subscription updates received
  returned: when operation=subscribe
  type: list
  sample:
    - timestamp: 1706529600000000000
      path: "/interfaces/interface[name=GigabitEthernet1]/state/counters"
      value:
        in-octets: 1234567
        out-octets: 7654321
failed:
  description: Whether the operation failed
  returned: always
  type: bool
  sample: false
msg:
  description: Status message
  returned: always
  type: str
  sample: "Configuration updated successfully"
'''

import json
import os
import traceback
from datetime import datetime
from ansible.module_utils.basic import AnsibleModule, missing_required_lib

try:
    from ansible_collections.cisco.iosxe_gnmi.plugins.module_utils.gnmi_client import (
        GnmiClient,
        GnmiClientError,
        GnmiConnectionError,
        GnmiAuthenticationError,
        GnmiOperationError
    )
    HAS_GNMI_CLIENT = True
    GNMI_CLIENT_IMPORT_ERROR = None
except ImportError:
    HAS_GNMI_CLIENT = False
    GNMI_CLIENT_IMPORT_ERROR = traceback.format_exc()


class CiscoIosXeGnmi:
    """Main class for Cisco IOS XE gNMI module"""

    def __init__(self, module):
        self.module = module
        self.client = None
        self.result = {
            'changed': False,
            'failed': False,
            'msg': '',
            'data': {}
        }

    def _create_client(self):
        """Create and return gNMI client instance"""
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
            client_key=self.module.params.get('client_key')
        )

    def _create_backup(self, paths):
        """Create backup of current configuration"""
        if not self.module.params['backup']:
            return None

        backup_dir = self.module.params['backup_path']
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = os.path.join(
            backup_dir,
            f"{self.module.params['host']}_{timestamp}.json"
        )

        try:
            # Get current configuration
            result = self.client.get(paths=paths, datatype='config')

            if result.success:
                with open(backup_file, 'w') as f:
                    json.dump(result.data, f, indent=2)
                return backup_file
            else:
                self.module.warn(f"Failed to create backup: {result.error}")
                return None

        except Exception as e:
            self.module.warn(f"Failed to create backup: {str(e)}")
            return None

    def _get_current_config(self, paths):
        """Get current configuration for diff comparison"""
        try:
            result = self.client.get(paths=paths, datatype='config')
            if result.success:
                return result.data
            return {}
        except Exception:
            return {}

    def execute_get(self):
        """Execute GET operation"""
        paths = self.module.params.get('paths')
        if not paths:
            self.module.fail_json(msg="paths parameter is required for GET operation")

        datatype = self.module.params['datatype']
        origin = self.module.params.get('origin')

        result = self.client.get(paths=paths, datatype=datatype, origin=origin)

        if result.success:
            self.result['data'] = result.data
            self.result['msg'] = 'Data retrieved successfully'
        else:
            self.result['msg'] = result.error
            self.result['failed'] = True
            self.module.fail_json(**self.result)

    def execute_set(self):
        """Execute SET operation"""
        state = self.module.params['state']
        config = self.module.params.get('config')
        paths = self.module.params.get('paths')
        replace = self.module.params['replace']

        # Determine paths for backup and diff
        backup_paths = []
        if state == 'absent' and paths:
            backup_paths = paths
        elif config:
            if isinstance(config, list):
                backup_paths = [item['path'] for item in config if 'path' in item]
            else:
                backup_paths = paths or []

        # Create backup if requested
        backup_file = None
        if backup_paths:
            backup_file = self._create_backup(backup_paths)
            if backup_file:
                self.result['backup_file'] = backup_file

        # Get current config for diff
        before_config = {}
        if self.module._diff and backup_paths:
            before_config = self._get_current_config(backup_paths)

        # Check mode - don't make actual changes
        if self.module.check_mode:
            self.result['changed'] = True
            self.result['msg'] = 'Check mode: would have made changes'
            if self.module._diff:
                self.result['diff'] = {
                    'before': before_config,
                    'after': 'Changes would be applied'
                }
            return

        # Execute the operation
        if state == 'absent':
            # Delete operation
            if not paths:
                self.module.fail_json(msg="paths parameter is required for delete operation")

            result = self.client.set(delete=paths)

        else:
            # Update or replace operation
            if not config:
                self.module.fail_json(msg="config parameter is required for present state")

            # Parse config into path-value pairs
            updates = []
            if isinstance(config, list):
                for item in config:
                    if not isinstance(item, dict) or 'path' not in item or 'value' not in item:
                        self.module.fail_json(
                            msg="Each config item must be a dict with 'path' and 'value' keys"
                        )
                    updates.append((item['path'], item['value']))
            elif isinstance(config, dict) and paths and len(paths) == 1:
                # Single path with dict value
                updates.append((paths[0], config))
            else:
                self.module.fail_json(
                    msg="config must be a list of dicts or a single dict with corresponding path"
                )

            if replace:
                result = self.client.set(replace=updates)
            else:
                result = self.client.set(update=updates)

        if result.success:
            self.result['changed'] = result.changed
            self.result['data'] = result.data
            self.result['msg'] = 'Configuration updated successfully'

            # Get after config for diff
            if self.module._diff and backup_paths:
                after_config = self._get_current_config(backup_paths)
                self.result['diff'] = {
                    'before': before_config,
                    'after': after_config
                }
        else:
            self.result['msg'] = result.error
            self.result['failed'] = True
            self.module.fail_json(**self.result)

    def run(self):
        """Main execution path"""

    def run(self):
        """Main execution method"""
        try:
            self.client = self._create_client()
            self.client.connect()

            operation = self.module.params['operation']

            if operation == 'get':
                self.execute_get()
            elif operation == 'set':
                self.execute_set()
            else:
                self.module.fail_json(msg=f"Unsupported operation: {operation}")

        except GnmiConnectionError as e:
            self.result['msg'] = f"Connection error: {str(e)}"
            self.result['failed'] = True
            self.module.fail_json(**self.result)
        except GnmiAuthenticationError as e:
            self.result['msg'] = f"Authentication error: {str(e)}"
            self.result['failed'] = True
            self.module.fail_json(**self.result)
        except GnmiOperationError as e:
            self.result['msg'] = f"Operation error: {str(e)}"
            self.result['failed'] = True
            self.module.fail_json(**self.result)
        except GnmiClientError as e:
            self.result['msg'] = f"gNMI client error: {str(e)}"
            self.result['failed'] = True
            self.module.fail_json(**self.result)
        except Exception as e:
            self.result['msg'] = f"Unexpected error: {str(e)}"
            self.result['failed'] = True
            self.result['exception'] = traceback.format_exc()
            self.module.fail_json(**self.result)
        finally:
            if self.client:
                self.client.disconnect()

        return self.result


def main():
    """Main module execution"""
    argument_spec = dict(
        host=dict(type='str', required=True),
        port=dict(type='int', default=9339),
        username=dict(type='str', required=True),
        password=dict(type='str', required=True, no_log=True),
        operation=dict(type='str', default='get', choices=['get', 'set']),
        paths=dict(type='list', elements='str'),
        datatype=dict(type='str', default='all', choices=['all', 'config', 'state', 'operational']),
        encoding=dict(type='str', default='json_ietf',
                     choices=['json', 'json_ietf', 'proto', 'ascii', 'bytes']),
        state=dict(type='str', default='present', choices=['present', 'absent']),
        config=dict(type='raw'),
        replace=dict(type='bool', default=False),
        backup=dict(type='bool', default=False),
        backup_path=dict(type='str', default='./backups'),
        timeout=dict(type='int', default=30),
        insecure=dict(type='bool', default=False),
        ca_cert=dict(type='str'),
        client_cert=dict(type='str'),
        client_key=dict(type='str'),
        origin=dict(type='str'),  # Common: 'rfc7951' (Cisco native), 'openconfig', or '' (IETF/default)
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_if=[
            ('operation', 'get', ['paths']),
        ],
    )

    # Check for required libraries
    if not HAS_GNMI_CLIENT:
        module.fail_json(
            msg=missing_required_lib('gnmi_client'),
            exception=GNMI_CLIENT_IMPORT_ERROR
        )

    # Execute module
    gnmi_module = CiscoIosXeGnmi(module)
    result = gnmi_module.run()

    module.exit_json(**result)


if __name__ == '__main__':
    main()
