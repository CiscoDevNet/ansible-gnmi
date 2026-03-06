"""
Unit tests for the cisco.gnmi.gnmi Ansible module.

Tests the GnmiModule class with mocked dependencies.
"""

import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_module():
    """Fixture to create a mock AnsibleModule.

    ``fail_json`` is configured to raise ``SystemExit`` (like the real
    ``AnsibleModule``) so that test assertions using ``pytest.raises``
    work correctly.
    """
    mock = MagicMock()
    mock.params = {
        'host': '10.0.0.1',
        'port': 9339,
        'username': 'admin',
        'password': 'secret',
        'operation': 'get',
        'paths': ['/interfaces/interface'],
        'datatype': 'all',
        'encoding': 'json_ietf',
        'state': 'present',
        'config': None,
        'replace': False,
        'backup': False,
        'backup_path': './backups',
        'timeout': 30,
        'insecure': False,
        'ca_cert': None,
        'client_cert': None,
        'client_key': None,
        'platform': 'auto',
        'subscriptions': None,
        'subscribe_mode': 'once',
        'subscribe_duration': 60,
        'origin': None,
    }
    mock.check_mode = False
    mock._diff = False
    # Real AnsibleModule.fail_json raises SystemExit after printing JSON.
    mock.fail_json.side_effect = SystemExit(1)
    return mock


@pytest.fixture
def mock_gnmi_client():
    """Fixture to create a mock GnmiClient."""
    with patch('ansible_collections.cisco.gnmi.plugins.modules.gnmi.GnmiClient') as mock:
        client_instance = MagicMock()
        mock.return_value = client_instance
        yield client_instance


class TestGnmiModuleGet:
    """Test GET operations."""

    def test_get_success(self, mock_module, mock_gnmi_client):
        from ansible_collections.cisco.gnmi.plugins.modules.gnmi import GnmiModule
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
        from ansible_collections.cisco.gnmi.plugins.modules.gnmi import GnmiModule
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
        from ansible_collections.cisco.gnmi.plugins.modules.gnmi import GnmiModule

        mock_module.params['paths'] = None
        mod = GnmiModule(mock_module)
        mod.client = mock_gnmi_client

        with pytest.raises(SystemExit):
            mod.execute_get()

        mock_module.fail_json.assert_called()


class TestGnmiModuleSet:
    """Test SET operations."""

    def test_set_update(self, mock_module, mock_gnmi_client):
        from ansible_collections.cisco.gnmi.plugins.modules.gnmi import GnmiModule
        from ansible_collections.cisco.gnmi.plugins.module_utils.gnmi_client import GnmiResult

        mock_module.params['operation'] = 'set'
        mock_module.params['config'] = [
            {'path': '/interfaces/interface[name=Gi1]/config/description',
             'value': 'Uplink'}
        ]

        mock_gnmi_client.set.return_value = GnmiResult(
            success=True, data={'timestamp': 1}, error=None, changed=True,
        )

        mod = GnmiModule(mock_module)
        mod.client = mock_gnmi_client
        mod.execute_set()

        assert mod.result['changed'] is True
        mock_gnmi_client.set.assert_called_once()

    def test_set_delete(self, mock_module, mock_gnmi_client):
        from ansible_collections.cisco.gnmi.plugins.modules.gnmi import GnmiModule
        from ansible_collections.cisco.gnmi.plugins.module_utils.gnmi_client import GnmiResult

        mock_module.params['operation'] = 'set'
        mock_module.params['state'] = 'absent'
        mock_module.params['paths'] = ['/test/path']

        mock_gnmi_client.set.return_value = GnmiResult(
            success=True, data={'timestamp': 1}, error=None, changed=True,
        )

        mod = GnmiModule(mock_module)
        mod.client = mock_gnmi_client
        mod.execute_set()

        assert mod.result['changed'] is True

    def test_set_check_mode(self, mock_module, mock_gnmi_client):
        from ansible_collections.cisco.gnmi.plugins.modules.gnmi import GnmiModule

        mock_module.check_mode = True
        mock_module.params['operation'] = 'set'
        mock_module.params['config'] = [{'path': '/test', 'value': 'v'}]

        mod = GnmiModule(mock_module)
        mod.client = mock_gnmi_client
        mod.execute_set()

        assert mod.result['changed'] is True
        assert 'Check mode' in mod.result['msg']
        mock_gnmi_client.set.assert_not_called()

    def test_set_diff_mode(self, mock_module, mock_gnmi_client):
        from ansible_collections.cisco.gnmi.plugins.modules.gnmi import GnmiModule
        from ansible_collections.cisco.gnmi.plugins.module_utils.gnmi_client import GnmiResult

        mock_module._diff = True
        mock_module.params['operation'] = 'set'
        mock_module.params['config'] = [{'path': '/t', 'value': 'new'}]

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

    def test_set_missing_config_fails(self, mock_module, mock_gnmi_client):
        from ansible_collections.cisco.gnmi.plugins.modules.gnmi import GnmiModule

        mock_module.params['operation'] = 'set'
        mock_module.params['config'] = None

        mod = GnmiModule(mock_module)
        mod.client = mock_gnmi_client

        with pytest.raises(SystemExit):
            mod.execute_set()

        mock_module.fail_json.assert_called()

    def test_set_invalid_config_format(self, mock_module, mock_gnmi_client):
        from ansible_collections.cisco.gnmi.plugins.modules.gnmi import GnmiModule

        mock_module.params['operation'] = 'set'
        mock_module.params['config'] = [{'invalid': 'fmt'}]

        mod = GnmiModule(mock_module)
        mod.client = mock_gnmi_client

        with pytest.raises(SystemExit):
            mod.execute_set()

        mock_module.fail_json.assert_called()


class TestGnmiModuleSubscribe:
    """Test Subscribe operations."""

    def test_subscribe_once(self, mock_module, mock_gnmi_client):
        from ansible_collections.cisco.gnmi.plugins.modules.gnmi import GnmiModule
        from ansible_collections.cisco.gnmi.plugins.module_utils.gnmi_client import GnmiResult

        mock_module.params['operation'] = 'subscribe'
        mock_module.params['subscriptions'] = [
            {'path': '/interfaces/interface/state/counters', 'mode': 'target_defined',
             'sample_interval': 10}
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
        from ansible_collections.cisco.gnmi.plugins.modules.gnmi import GnmiModule

        mock_module.params['operation'] = 'subscribe'
        mock_module.params['subscriptions'] = None

        mod = GnmiModule(mock_module)
        mod.client = mock_gnmi_client

        with pytest.raises(SystemExit):
            mod.execute_subscribe()

        mock_module.fail_json.assert_called()


class TestGnmiModuleRun:
    """Test the run() dispatch and error handling."""

    def test_connection_error(self, mock_module):
        from ansible_collections.cisco.gnmi.plugins.modules.gnmi import GnmiModule
        from ansible_collections.cisco.gnmi.plugins.module_utils.gnmi_client import GnmiConnectionError

        with patch('ansible_collections.cisco.gnmi.plugins.modules.gnmi.GnmiClient') as mc:
            mc.return_value.connect.side_effect = GnmiConnectionError('refused')

            mod = GnmiModule(mock_module)
            with pytest.raises(SystemExit):
                mod.run()

            mock_module.fail_json.assert_called()
            assert 'Connection error' in str(mock_module.fail_json.call_args)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
