# Copyright 2025 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the cisco.gnmi modules.

Exercises ``GnmiModule`` (in ``plugins/module_utils/module_helper.py``),
which is the shared core used by:

  * cisco.gnmi.info       (operation='get')
  * cisco.gnmi.config     (operation='set')
  * cisco.gnmi.subscribe  (operation='subscribe')
"""

import pytest
from unittest.mock import MagicMock, patch


MODULE_HELPER = (
    'ansible_collections.cisco.gnmi.plugins.module_utils.module_helper'
)


def _make_mock_module(**overrides):
    params = {
        'host': '10.0.0.1',
        'port': 9339,
        'username': 'admin',
        'password': 'secret',
        'token': None,
        'encoding': 'json_ietf',
        'timeout': 30,
        'insecure': False,
        'ca_cert': None,
        'client_cert': None,
        'client_key': None,
        'tls_server_name': None,
        'tls_skip_verify': False,
        'max_message_length': None,
        'channel_options': None,
        'platform': 'auto',
        'origin': None,
        # info-only
        'paths': ['/interfaces/interface'],
        'prefix': None,
        'datatype': 'all',
        # config-only (new 4.0 schema: update/replace/delete lists)
        'update': None,
        'replace': None,
        'delete': None,
        'backup': False,
        'backup_path': './backups',
        # subscribe-only
        'subscriptions': None,
        'subscribe_mode': 'once',
        'subscribe_duration': 60,
    }
    params.update(overrides)

    mock = MagicMock()
    mock.params = params
    mock.check_mode = False
    mock._diff = False
    mock.fail_json.side_effect = SystemExit(1)
    return mock


@pytest.fixture
def mock_module():
    return _make_mock_module()


@pytest.fixture
def mock_gnmi_client():
    with patch(MODULE_HELPER + '.GnmiClient') as mock:
        client_instance = MagicMock()
        mock.return_value = client_instance
        yield client_instance


# ---------------------------------------------------------------------------
# GET (cisco.gnmi.info)
# ---------------------------------------------------------------------------

class TestGet:
    def test_get_success(self, mock_module, mock_gnmi_client):
        from ansible_collections.cisco.gnmi.plugins.module_utils.module_helper import GnmiModule
        from ansible_collections.cisco.gnmi.plugins.module_utils.gnmi_client import GnmiResult

        mock_gnmi_client.get.return_value = GnmiResult(
            success=True,
            data={'/interfaces/interface': {'name': 'Gi1'}},
            error=None, changed=False,
        )

        mod = GnmiModule(mock_module)
        mod.client = mock_gnmi_client
        mod.execute_get()

        assert mod.result['data'] == {'/interfaces/interface': {'name': 'Gi1'}}
        assert mod.result['msg'] == 'Data retrieved successfully'

    def test_get_failure(self, mock_module, mock_gnmi_client):
        from ansible_collections.cisco.gnmi.plugins.module_utils.module_helper import GnmiModule
        from ansible_collections.cisco.gnmi.plugins.module_utils.gnmi_client import GnmiResult

        mock_gnmi_client.get.return_value = GnmiResult(
            success=False, data=None, error='Timeout', changed=False,
        )

        mod = GnmiModule(mock_module)
        mod.client = mock_gnmi_client

        with pytest.raises(SystemExit):
            mod.execute_get()
        mock_module.fail_json.assert_called()

    def test_get_no_paths_fails(self, mock_module, mock_gnmi_client):
        from ansible_collections.cisco.gnmi.plugins.module_utils.module_helper import GnmiModule

        mock_module.params['paths'] = None
        mod = GnmiModule(mock_module)
        mod.client = mock_gnmi_client

        with pytest.raises(SystemExit):
            mod.execute_get()
        mock_module.fail_json.assert_called()

    def test_get_prefix_passed_through(self, mock_module, mock_gnmi_client):
        from ansible_collections.cisco.gnmi.plugins.module_utils.module_helper import GnmiModule
        from ansible_collections.cisco.gnmi.plugins.module_utils.gnmi_client import GnmiResult

        mock_module.params['prefix'] = '/interfaces'
        mock_module.params['paths'] = ['interface[name=Gi1]', 'interface[name=Gi2]']

        mock_gnmi_client.get.return_value = GnmiResult(
            success=True, data={}, error=None, changed=False,
        )

        mod = GnmiModule(mock_module)
        mod.client = mock_gnmi_client
        mod.execute_get()

        kwargs = mock_gnmi_client.get.call_args.kwargs
        assert kwargs['prefix'] == '/interfaces'
        assert kwargs['paths'] == ['interface[name=Gi1]', 'interface[name=Gi2]']


# ---------------------------------------------------------------------------
# SET (cisco.gnmi.config)
# ---------------------------------------------------------------------------

class TestSet:
    def test_set_update(self, mock_module, mock_gnmi_client):
        from ansible_collections.cisco.gnmi.plugins.module_utils.module_helper import GnmiModule
        from ansible_collections.cisco.gnmi.plugins.module_utils.gnmi_client import GnmiResult

        mock_module.params['update'] = [
            {'path': '/interfaces/interface[name=Gi1]/config/description',
             'value': 'Uplink',
             'origin': None}
        ]

        mock_gnmi_client.set.return_value = GnmiResult(
            success=True, data={'timestamp': 1}, error=None, changed=True,
        )

        mod = GnmiModule(mock_module)
        mod.client = mock_gnmi_client
        mod.execute_set()

        assert mod.result['changed'] is True
        mock_gnmi_client.set.assert_called_once()
        call_kwargs = mock_gnmi_client.set.call_args.kwargs
        assert call_kwargs['update'] == [
            ('/interfaces/interface[name=Gi1]/config/description', 'Uplink')
        ]
        assert call_kwargs['replace'] is None
        assert call_kwargs['delete'] is None

    def test_set_replace(self, mock_module, mock_gnmi_client):
        from ansible_collections.cisco.gnmi.plugins.module_utils.module_helper import GnmiModule
        from ansible_collections.cisco.gnmi.plugins.module_utils.gnmi_client import GnmiResult

        mock_module.params['replace'] = [
            {'path': '/system/config', 'value': {'hostname': 'r1'}, 'origin': None}
        ]
        mock_gnmi_client.set.return_value = GnmiResult(
            success=True, data={'timestamp': 1}, error=None, changed=True,
        )

        mod = GnmiModule(mock_module)
        mod.client = mock_gnmi_client
        mod.execute_set()

        assert mod.result['changed'] is True
        call_kwargs = mock_gnmi_client.set.call_args.kwargs
        assert call_kwargs['replace'] == [('/system/config', {'hostname': 'r1'})]

    def test_set_delete_strings(self, mock_module, mock_gnmi_client):
        from ansible_collections.cisco.gnmi.plugins.module_utils.module_helper import GnmiModule
        from ansible_collections.cisco.gnmi.plugins.module_utils.gnmi_client import GnmiResult

        mock_module.params['delete'] = ['/test/path', '/another/path']

        mock_gnmi_client.set.return_value = GnmiResult(
            success=True, data={'timestamp': 1}, error=None, changed=True,
        )

        mod = GnmiModule(mock_module)
        mod.client = mock_gnmi_client
        mod.execute_set()

        assert mod.result['changed'] is True
        call_kwargs = mock_gnmi_client.set.call_args.kwargs
        assert call_kwargs['delete'] == ['/test/path', '/another/path']

    def test_set_delete_dict_form_with_origin(self, mock_module, mock_gnmi_client):
        from ansible_collections.cisco.gnmi.plugins.module_utils.module_helper import GnmiModule
        from ansible_collections.cisco.gnmi.plugins.module_utils.gnmi_client import GnmiResult

        mock_module.params['delete'] = [
            {'path': '/old/path', 'origin': 'native'},
        ]
        mock_gnmi_client.set.return_value = GnmiResult(
            success=True, data={}, error=None, changed=True,
        )

        mod = GnmiModule(mock_module)
        mod.client = mock_gnmi_client
        mod.execute_set()

        call_kwargs = mock_gnmi_client.set.call_args.kwargs
        # Per-item origin is encoded into the path string
        assert call_kwargs['delete'] == ['native:/old/path']

    def test_set_atomic_mixed(self, mock_module, mock_gnmi_client):
        """update + replace + delete in one task -> single set() call."""
        from ansible_collections.cisco.gnmi.plugins.module_utils.module_helper import GnmiModule
        from ansible_collections.cisco.gnmi.plugins.module_utils.gnmi_client import GnmiResult

        mock_module.params['update'] = [
            {'path': '/a', 'value': 'v1', 'origin': None},
        ]
        mock_module.params['replace'] = [
            {'path': '/b', 'value': 'v2', 'origin': None},
        ]
        mock_module.params['delete'] = ['/c']
        mock_gnmi_client.set.return_value = GnmiResult(
            success=True, data={}, error=None, changed=True,
        )

        mod = GnmiModule(mock_module)
        mod.client = mock_gnmi_client
        mod.execute_set()

        # One call carrying all three operations.
        assert mock_gnmi_client.set.call_count == 1
        kwargs = mock_gnmi_client.set.call_args.kwargs
        assert kwargs['update'] == [('/a', 'v1')]
        assert kwargs['replace'] == [('/b', 'v2')]
        assert kwargs['delete'] == ['/c']

    def test_set_check_mode(self, mock_module, mock_gnmi_client):
        from ansible_collections.cisco.gnmi.plugins.module_utils.module_helper import GnmiModule

        mock_module.check_mode = True
        mock_module.params['update'] = [
            {'path': '/test', 'value': 'v', 'origin': None}
        ]

        mod = GnmiModule(mock_module)
        mod.client = mock_gnmi_client
        mod.execute_set()

        assert mod.result['changed'] is True
        assert 'Check mode' in mod.result['msg']
        mock_gnmi_client.set.assert_not_called()

    def test_set_diff_mode(self, mock_module, mock_gnmi_client):
        from ansible_collections.cisco.gnmi.plugins.module_utils.module_helper import GnmiModule
        from ansible_collections.cisco.gnmi.plugins.module_utils.gnmi_client import GnmiResult

        mock_module._diff = True
        mock_module.params['update'] = [
            {'path': '/t', 'value': 'new', 'origin': None}
        ]

        mock_gnmi_client.get.side_effect = [
            GnmiResult(success=True, data={'/t': 'old'}, error=None, changed=False),
            GnmiResult(success=True, data={'/t': 'new'}, error=None, changed=False),
        ]
        mock_gnmi_client.set.return_value = GnmiResult(
            success=True, data={'timestamp': 1}, error=None, changed=True,
        )

        mod = GnmiModule(mock_module)
        mod.client = mock_gnmi_client
        mod.execute_set()

        assert 'diff' in mod.result
        assert 'before' in mod.result['diff']
        assert 'after' in mod.result['diff']

    def test_set_invalid_update_item_missing_value(self, mock_module, mock_gnmi_client):
        from ansible_collections.cisco.gnmi.plugins.module_utils.module_helper import GnmiModule

        mock_module.params['update'] = [{'path': '/x', 'value': None, 'origin': None}]
        mod = GnmiModule(mock_module)
        mod.client = mock_gnmi_client

        with pytest.raises(SystemExit):
            mod.execute_set()
        mock_module.fail_json.assert_called()

    def test_set_invalid_delete_item_type(self, mock_module, mock_gnmi_client):
        from ansible_collections.cisco.gnmi.plugins.module_utils.module_helper import GnmiModule

        mock_module.params['delete'] = [123]
        mod = GnmiModule(mock_module)
        mod.client = mock_gnmi_client

        with pytest.raises(SystemExit):
            mod.execute_set()
        mock_module.fail_json.assert_called()


# ---------------------------------------------------------------------------
# SUBSCRIBE (cisco.gnmi.subscribe)
# ---------------------------------------------------------------------------

class TestSubscribe:
    def test_subscribe_once(self, mock_module, mock_gnmi_client):
        from ansible_collections.cisco.gnmi.plugins.module_utils.module_helper import GnmiModule
        from ansible_collections.cisco.gnmi.plugins.module_utils.gnmi_client import GnmiResult

        mock_module.params['subscriptions'] = [
            {'path': '/interfaces/interface/state/counters',
             'mode': 'target_defined', 'sample_interval': 10}
        ]

        mock_gnmi_client.subscribe.return_value = GnmiResult(
            success=True,
            data={'updates': [{'path': '/test', 'value': {'counter': 100}}]},
            error=None, changed=False,
        )

        mod = GnmiModule(mock_module)
        mod.client = mock_gnmi_client
        mod.execute_subscribe()

        assert 'updates' in mod.result
        assert len(mod.result['updates']) == 1

    def test_subscribe_no_subscriptions_fails(self, mock_module, mock_gnmi_client):
        from ansible_collections.cisco.gnmi.plugins.module_utils.module_helper import GnmiModule

        mock_module.params['subscriptions'] = None
        mod = GnmiModule(mock_module)
        mod.client = mock_gnmi_client

        with pytest.raises(SystemExit):
            mod.execute_subscribe()
        mock_module.fail_json.assert_called()


# ---------------------------------------------------------------------------
# CAPABILITIES (cisco.gnmi.capabilities)
# ---------------------------------------------------------------------------

class TestCapabilities:
    def test_capabilities_success(self, mock_module, mock_gnmi_client):
        from ansible_collections.cisco.gnmi.plugins.module_utils.module_helper import GnmiModule
        from ansible_collections.cisco.gnmi.plugins.module_utils.gnmi_client import GnmiResult

        mock_gnmi_client.capabilities.return_value = GnmiResult(
            success=True,
            data={
                'gnmi_version': '0.7.0',
                'supported_encodings': ['JSON_IETF', 'PROTO'],
                'supported_models': [
                    {'name': 'openconfig-interfaces',
                     'organization': 'OpenConfig', 'version': '2.0.0'},
                ],
            },
            error=None, changed=False,
        )

        mod = GnmiModule(mock_module)
        mod.client = mock_gnmi_client
        mod.execute_capabilities()

        assert mod.result['data']['gnmi_version'] == '0.7.0'
        assert 'JSON_IETF' in mod.result['data']['supported_encodings']
        assert mod.result['msg'] == 'Capabilities retrieved successfully'

    def test_capabilities_failure(self, mock_module, mock_gnmi_client):
        from ansible_collections.cisco.gnmi.plugins.module_utils.module_helper import GnmiModule
        from ansible_collections.cisco.gnmi.plugins.module_utils.gnmi_client import GnmiResult

        mock_gnmi_client.capabilities.return_value = GnmiResult(
            success=False, data=None, error='unavailable', changed=False,
        )

        mod = GnmiModule(mock_module)
        mod.client = mock_gnmi_client

        with pytest.raises(SystemExit):
            mod.execute_capabilities()
        mock_module.fail_json.assert_called()


# ---------------------------------------------------------------------------
# Dispatch / error handling
# ---------------------------------------------------------------------------

class TestRun:
    def test_connection_error(self, mock_module):
        from ansible_collections.cisco.gnmi.plugins.module_utils.module_helper import GnmiModule
        from ansible_collections.cisco.gnmi.plugins.module_utils.gnmi_client import GnmiConnectionError

        with patch(MODULE_HELPER + '.GnmiClient') as mc:
            mc.return_value.connect.side_effect = GnmiConnectionError('refused')

            mod = GnmiModule(mock_module)
            with pytest.raises(SystemExit):
                mod.run(operation='get')

            mock_module.fail_json.assert_called()
            assert 'Connection error' in str(mock_module.fail_json.call_args)

    def test_unknown_operation_fails(self, mock_module, mock_gnmi_client):
        from ansible_collections.cisco.gnmi.plugins.module_utils.module_helper import GnmiModule

        mod = GnmiModule(mock_module)
        with pytest.raises(SystemExit):
            mod.run(operation='bogus')
        mock_module.fail_json.assert_called()


# ---------------------------------------------------------------------------
# Result shape / backup behaviour
# ---------------------------------------------------------------------------

class TestResultShape:
    def test_result_has_no_failed_key(self, mock_module):
        from ansible_collections.cisco.gnmi.plugins.module_utils.module_helper import GnmiModule

        mod = GnmiModule(mock_module)
        assert 'failed' not in mod.result
        assert mod.result['changed'] is False
        assert mod.result['msg'] == ''
        assert mod.result['data'] == {}


class TestBackup:
    def test_backup_skipped_in_check_mode(self, mock_module, mock_gnmi_client, tmp_path):
        from ansible_collections.cisco.gnmi.plugins.module_utils.module_helper import GnmiModule
        from ansible_collections.cisco.gnmi.plugins.module_utils.gnmi_client import GnmiResult

        mock_module.check_mode = True
        mock_module.params['backup'] = True
        mock_module.params['backup_path'] = str(tmp_path)

        mock_gnmi_client.get.return_value = GnmiResult(
            success=True, data={'/x': 'y'}, error=None, changed=False,
        )

        mod = GnmiModule(mock_module)
        mod.client = mock_gnmi_client

        result = mod._create_backup(['/x'])

        assert result is None
        mock_gnmi_client.get.assert_not_called()
        assert list(tmp_path.iterdir()) == []

    def test_backup_writes_file_when_not_check_mode(self, mock_module, mock_gnmi_client, tmp_path):
        from ansible_collections.cisco.gnmi.plugins.module_utils.module_helper import GnmiModule
        from ansible_collections.cisco.gnmi.plugins.module_utils.gnmi_client import GnmiResult

        mock_module.params['backup'] = True
        mock_module.params['backup_path'] = str(tmp_path)

        mock_gnmi_client.get.return_value = GnmiResult(
            success=True, data={'/x': 'y'}, error=None, changed=False,
        )

        mod = GnmiModule(mock_module)
        mod.client = mock_gnmi_client

        backup_file = mod._create_backup(['/x'])

        assert backup_file is not None
        assert str(tmp_path) in backup_file
        files = list(tmp_path.iterdir())
        assert len(files) == 1

    def test_backup_path_rejects_traversal(self, mock_module, mock_gnmi_client):
        from ansible_collections.cisco.gnmi.plugins.module_utils.module_helper import GnmiModule

        mock_module.params['backup'] = True
        mock_module.params['backup_path'] = '/var/lib/../../etc'

        mod = GnmiModule(mock_module)
        mod.client = mock_gnmi_client

        with pytest.raises(SystemExit):
            mod._create_backup(['/x'])

        mock_module.fail_json.assert_called()
        assert '..' in str(mock_module.fail_json.call_args)

    def test_backup_path_rejects_empty(self, mock_module, mock_gnmi_client):
        from ansible_collections.cisco.gnmi.plugins.module_utils.module_helper import GnmiModule

        mock_module.params['backup'] = True
        mock_module.params['backup_path'] = ''

        mod = GnmiModule(mock_module)
        mod.client = mock_gnmi_client

        with pytest.raises(SystemExit):
            mod._create_backup(['/x'])
        mock_module.fail_json.assert_called()

    def test_backup_path_accepts_relative(self, mock_module, mock_gnmi_client, tmp_path, monkeypatch):
        from ansible_collections.cisco.gnmi.plugins.module_utils.module_helper import GnmiModule

        monkeypatch.chdir(tmp_path)
        mock_module.params['backup'] = True
        mock_module.params['backup_path'] = 'backups'

        mod = GnmiModule(mock_module)
        assert mod._validate_backup_path('backups') == 'backups'
        assert mod._validate_backup_path('./backups/today') == './backups/today'
        assert mod._validate_backup_path('/tmp/backups') == '/tmp/backups'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
