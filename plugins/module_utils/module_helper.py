# -*- coding: utf-8 -*-

# Copyright 2025 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Shared helper used by the cisco.gnmi modules.

The split modules (``info``, ``config``, ``subscribe``) all share the same
connection setup, error mapping, backup/diff helpers and operation
implementations. Putting that logic here keeps each module file small and
focused on its argument spec and dispatch.
"""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

import json
import os
import traceback
from datetime import datetime

from ansible.module_utils.basic import missing_required_lib

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
    GnmiClient = None

    # Distinct stub classes so that the ``except`` chain in ``GnmiModule.run``
    # is well-typed for both runtime and static analysis (pylint flags
    # duplicate-except / bad-except-order if we just alias them all to
    # ``Exception``).
    class GnmiClientError(Exception):
        pass

    class GnmiConnectionError(GnmiClientError):
        pass

    class GnmiAuthenticationError(GnmiClientError):
        pass

    class GnmiOperationError(GnmiClientError):
        pass


# ---------------------------------------------------------------------------
# Shared argument-spec fragments
# ---------------------------------------------------------------------------

def connection_argument_spec():
    """Argument spec entries shared by every gNMI module.

    Either ``username`` + ``password`` *or* ``token`` must be supplied;
    this is enforced at module level via ``required_one_of`` /
    ``required_together`` in each module's ``AnsibleModule`` call.
    """
    return dict(
        host=dict(type='str', required=True),
        port=dict(type='int', default=9339),
        username=dict(type='str'),
        password=dict(type='str', no_log=True),
        token=dict(type='str', no_log=True),
        encoding=dict(
            type='str', default='json_ietf',
            choices=['json', 'json_ietf', 'proto', 'bytes', 'ascii'],
        ),
        timeout=dict(type='int', default=30),
        insecure=dict(type='bool', default=False),
        ca_cert=dict(type='path'),
        client_cert=dict(type='path'),
        client_key=dict(type='path'),
        tls_server_name=dict(type='str'),
        max_message_length=dict(type='int'),
        channel_options=dict(type='dict'),
        platform=dict(
            type='str', default='auto',
            choices=['auto', 'iosxe', 'iosxr', 'nxos'],
        ),
        origin=dict(type='str'),
    )


def connection_required_constraints():
    """``required_one_of`` / ``required_together`` snippets for AnsibleModule.

    Returns a tuple ``(required_one_of, required_together)`` so each
    module can extend its own constraints.
    """
    required_one_of = [('username', 'token')]
    required_together = [('username', 'password')]
    return required_one_of, required_together


# ---------------------------------------------------------------------------
# Main helper class
# ---------------------------------------------------------------------------

class GnmiModule:
    """Wraps an AnsibleModule and exposes one method per gNMI RPC.

    Each cisco.gnmi.* module instantiates this class and invokes the
    appropriate ``execute_*`` method. Calling ``run(operation)`` handles
    client lifecycle and error translation in one shot.
    """

    def __init__(self, module):
        self.module = module
        self.client = None
        self.result = {
            'changed': False,
            'msg': '',
            'data': {},
        }

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def _create_client(self):
        return GnmiClient(
            host=self.module.params['host'],
            port=self.module.params['port'],
            username=self.module.params.get('username'),
            password=self.module.params.get('password'),
            token=self.module.params.get('token'),
            encoding=self.module.params['encoding'],
            timeout=self.module.params['timeout'],
            insecure=self.module.params['insecure'],
            ca_cert=self.module.params.get('ca_cert'),
            client_cert=self.module.params.get('client_cert'),
            client_key=self.module.params.get('client_key'),
            tls_server_name=self.module.params.get('tls_server_name'),
            max_message_length=self.module.params.get('max_message_length'),
            channel_options=self.module.params.get('channel_options'),
            platform=self.module.params.get('platform', 'auto'),
            warn_callback=self.module.warn,
        )

    # ------------------------------------------------------------------
    # Backup
    # ------------------------------------------------------------------

    def _validate_backup_path(self, backup_path):
        """Reject obviously-traversal-y backup paths.

        ``backup_path`` is user-supplied via Ansible task parameters and is
        eventually passed to ``os.makedirs`` / ``open``. To make traversal
        attempts explicit (rather than silently writing outside the intended
        directory), reject any component containing ``..``.
        """
        if backup_path is None or backup_path == '':
            self.module.fail_json(msg="'backup_path' must not be empty when backup=true")

        normalized = backup_path.replace('\\', '/')
        parts = [p for p in normalized.split('/') if p not in ('', '.')]
        if any(p == '..' for p in parts):
            self.module.fail_json(
                msg="'backup_path' must not contain '..' path components: {0}".format(backup_path))

        return backup_path

    def _create_backup(self, paths):
        if not self.module.params.get('backup'):
            return None
        # Honor check_mode: never write files when running with --check.
        if self.module.check_mode:
            return None

        backup_dir = self._validate_backup_path(self.module.params['backup_path'])
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
        try:
            result = self.client.get(paths=paths, datatype='config')
            if result.success:
                return result.data
            return {}
        except Exception:
            return {}

    # ------------------------------------------------------------------
    # CAPABILITIES (cisco.gnmi.capabilities)
    # ------------------------------------------------------------------

    def execute_capabilities(self):
        result = self.client.capabilities()
        if result.success:
            self.result['data'] = result.data
            self.result['msg'] = 'Capabilities retrieved successfully'
        else:
            self.module.fail_json(msg=result.error)

    # ------------------------------------------------------------------
    # GET (cisco.gnmi.info)
    # ------------------------------------------------------------------

    def execute_get(self):
        paths = self.module.params.get('paths')
        if not paths:
            self.module.fail_json(msg="'paths' is required for GET operation")

        datatype = self.module.params['datatype']
        origin = self.module.params.get('origin')
        prefix = self.module.params.get('prefix')

        result = self.client.get(
            paths=paths, datatype=datatype, origin=origin, prefix=prefix,
        )

        if result.success:
            self.result['data'] = result.data
            self.result['msg'] = 'Data retrieved successfully'
        else:
            self.module.fail_json(msg=result.error)

    # ------------------------------------------------------------------
    # SET (cisco.gnmi.config)
    # ------------------------------------------------------------------

    def execute_set(self):
        """Atomic Set: combine update / replace / delete in one transaction.

        Each of ``update``, ``replace``, ``delete`` is an optional list.
        At least one must be non-empty (validated by ``required_one_of``
        in the module's AnsibleModule call).

        * ``update`` / ``replace`` items: dict ``{path, value, origin?}``.
        * ``delete`` items: string path *or* dict ``{path, origin?}``.

        All three lists are sent in a single SetRequest so the device
        applies them as one atomic transaction.
        """
        origin = self.module.params.get('origin')
        update_param = self.module.params.get('update') or []
        replace_param = self.module.params.get('replace') or []
        delete_param = self.module.params.get('delete') or []

        update_ops = self._normalise_set_items(update_param, 'update', require_value=True)
        replace_ops = self._normalise_set_items(replace_param, 'replace', require_value=True)
        delete_ops = self._normalise_delete_items(delete_param)

        # Aggregate every path referenced for backup / diff purposes.
        all_paths = (
            [p for p, _v in update_ops]
            + [p for p, _v in replace_ops]
            + list(delete_ops)
        )

        backup_file = self._create_backup(all_paths) if all_paths else None
        if backup_file:
            self.result['backup_file'] = backup_file

        before_config = {}
        if self.module._diff and all_paths:
            before_config = self._get_current_config(all_paths)

        if self.module.check_mode:
            self.result['changed'] = True
            self.result['msg'] = 'Check mode: changes would be applied'
            if self.module._diff:
                self.result['diff'] = {
                    'before': before_config,
                    'after': 'Changes would be applied',
                }
            return

        result = self.client.set(
            update=update_ops or None,
            replace=replace_ops or None,
            delete=list(delete_ops) or None,
            origin=origin,
        )

        if result.success:
            self.result['changed'] = result.changed
            self.result['data'] = result.data
            self.result['msg'] = 'Configuration updated successfully'

            if self.module._diff and all_paths:
                after_config = self._get_current_config(all_paths)
                self.result['diff'] = {
                    'before': before_config,
                    'after': after_config,
                }
        else:
            self.module.fail_json(msg=result.error)

    # ------------------------------------------------------------------
    # SET helpers
    # ------------------------------------------------------------------

    def _normalise_set_items(self, items, label, require_value):
        """Validate and unpack update/replace items into ``(path, value)`` tuples.

        Accepts a list of dicts ``{path, value, origin?}``. The optional
        per-item ``origin`` is encoded into the path string as
        ``"<origin>:<path>"`` so gnmi_client._build_path can recognise it.
        """
        result = []
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                self.module.fail_json(
                    msg="'{0}' item {1} must be a dict, got {2}".format(
                        label, index, type(item).__name__))
            path = item.get('path')
            value = item.get('value')
            item_origin = item.get('origin')
            if not path:
                self.module.fail_json(
                    msg="'{0}' item {1} is missing 'path'".format(label, index))
            if require_value and value is None:
                self.module.fail_json(
                    msg="'{0}' item {1} is missing 'value'".format(label, index))
            path = self._apply_item_origin(path, item_origin)
            result.append((path, value))
        return result

    def _normalise_delete_items(self, items):
        """Validate and unpack delete items into a list of path strings.

        Each item may be a plain string path or a dict ``{path, origin?}``.
        """
        result = []
        for index, item in enumerate(items):
            if isinstance(item, str):
                result.append(item)
            elif isinstance(item, dict):
                path = item.get('path')
                if not path:
                    self.module.fail_json(
                        msg="'delete' item {0} is missing 'path'".format(index))
                result.append(self._apply_item_origin(path, item.get('origin')))
            else:
                self.module.fail_json(
                    msg="'delete' item {0} must be a string or dict, got {1}".format(
                        index, type(item).__name__))
        return result

    @staticmethod
    def _apply_item_origin(path, item_origin):
        """Encode a per-item origin onto *path* using the ``origin:/path`` form.

        Skipped when the path already carries an origin prefix.
        """
        if not item_origin:
            return path
        # If the user already supplied "foo:/..." form, trust it.
        if ':/' in path:
            first = path.split(':/', 1)[0]
            if first and '/' not in first and '[' not in first:
                return path
        if not path.startswith('/'):
            path = '/' + path
        return '{0}:{1}'.format(item_origin, path)

    # ------------------------------------------------------------------
    # SUBSCRIBE (cisco.gnmi.subscribe)
    # ------------------------------------------------------------------

    def execute_subscribe(self):
        subscriptions_param = self.module.params.get('subscriptions')
        if not subscriptions_param:
            self.module.fail_json(msg="'subscriptions' is required for subscribe operation")

        origin = self.module.params.get('origin')
        subscribe_mode = self.module.params.get('subscribe_mode', 'once')
        subscribe_duration = self.module.params.get('subscribe_duration', 60)

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
            duration=subscribe_duration,
        )

        if result.success:
            self.result['updates'] = result.data.get('updates', [])
            self.result['msg'] = 'Subscription completed successfully'
        else:
            self.module.fail_json(msg=result.error)

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def run(self, operation):
        """Connect, dispatch to the named operation, and clean up.

        ``operation`` is one of ``'get'``, ``'set'``, ``'subscribe'`` —
        chosen by the calling module (cisco.gnmi.info, .config, .subscribe).
        """
        try:
            self.client = self._create_client()
            self.client.connect()

            if operation == 'get':
                self.execute_get()
            elif operation == 'set':
                self.execute_set()
            elif operation == 'subscribe':
                self.execute_subscribe()
            elif operation == 'capabilities':
                self.execute_capabilities()
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


def fail_if_gnmi_client_missing(module):
    """Convenience: fail the module if the gNMI client dependencies are absent."""
    if not HAS_GNMI_CLIENT:
        module.fail_json(
            msg=missing_required_lib('gnmi_client (grpcio, protobuf)'),
            exception=GNMI_CLIENT_IMPORT_ERROR,
        )
