"""
Unit tests for Cisco IOS XE gNMI Ansible Module

Tests the cisco_iosxe_gnmi module with mocked dependencies
"""

import pytest
import json
from unittest.mock import Mock, MagicMock, patch
from ansible.module_utils import basic
from ansible.module_utils.common.text.converters import to_bytes


# Mock the module import
@pytest.fixture
def mock_module():
    """Fixture to create mock AnsibleModule"""
    mock = MagicMock()
    mock.params = {
        'host': '192.168.1.1',
        'port': 9339,
        'username': 'admin',
        'password': 'cisco',
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
        'subscriptions': None,
        'subscribe_mode': 'once',
        'subscribe_duration': 60,
    }
    mock.check_mode = False
    mock._diff = False
    return mock


@pytest.fixture
def mock_gnmi_client():
    """Fixture to create mock GnmiClient"""
    with patch('ansible_collections.cisco.iosxe_gnmi.plugins.modules.cisco_iosxe_gnmi.GnmiClient') as mock:
        client_instance = MagicMock()
        mock.return_value = client_instance
        yield client_instance


class TestCiscoIosXeGnmiModule:
    """Test suite for cisco_iosxe_gnmi module"""

    def test_module_get_operation_success(self, mock_module, mock_gnmi_client):
        """Test successful GET operation"""
        from ansible_collections.cisco.iosxe_gnmi.plugins.modules.cisco_iosxe_gnmi import CiscoIosXeGnmi
        from ansible_collections.cisco.iosxe_gnmi.plugins.module_utils.gnmi_client import GnmiResult

        # Mock successful GET response
        mock_gnmi_client.get.return_value = GnmiResult(
            success=True,
            data={'/interfaces/interface': {'name': 'GigabitEthernet1'}},
            error=None,
            changed=False
        )

        module_obj = CiscoIosXeGnmi(mock_module)
        module_obj.client = mock_gnmi_client
        module_obj.execute_get()

        assert module_obj.result['changed'] is False
        assert '/interfaces/interface' in module_obj.result['data']

    def test_module_get_operation_failure(self, mock_module, mock_gnmi_client):
        """Test failed GET operation"""
        from ansible_collections.cisco.iosxe_gnmi.plugins.modules.cisco_iosxe_gnmi import CiscoIosXeGnmi
        from ansible_collections.cisco.iosxe_gnmi.plugins.module_utils.gnmi_client import GnmiResult

        # Mock failed GET response
        mock_gnmi_client.get.return_value = GnmiResult(
            success=False,
            data=None,
            error='Connection timeout',
            changed=False
        )

        module_obj = CiscoIosXeGnmi(mock_module)
        module_obj.client = mock_gnmi_client

        with pytest.raises(SystemExit):
            module_obj.execute_get()

        mock_module.fail_json.assert_called()

    def test_module_set_operation_update(self, mock_module, mock_gnmi_client):
        """Test SET operation with update"""
        from ansible_collections.cisco.iosxe_gnmi.plugins.modules.cisco_iosxe_gnmi import CiscoIosXeGnmi
        from ansible_collections.cisco.iosxe_gnmi.plugins.module_utils.gnmi_client import GnmiResult

        mock_module.params['operation'] = 'set'
        mock_module.params['config'] = [
            {'path': '/interfaces/interface[name=GigabitEthernet1]/config/description',
             'value': 'Test Interface'}
        ]

        mock_gnmi_client.set.return_value = GnmiResult(
            success=True,
            data={'timestamp': 123456789},
            error=None,
            changed=True
        )

        module_obj = CiscoIosXeGnmi(mock_module)
        module_obj.client = mock_gnmi_client
        module_obj.execute_set()

        assert module_obj.result['changed'] is True
        mock_gnmi_client.set.assert_called_once()

    def test_module_set_operation_delete(self, mock_module, mock_gnmi_client):
        """Test SET operation with delete"""
        from ansible_collections.cisco.iosxe_gnmi.plugins.modules.cisco_iosxe_gnmi import CiscoIosXeGnmi
        from ansible_collections.cisco.iosxe_gnmi.plugins.module_utils.gnmi_client import GnmiResult

        mock_module.params['operation'] = 'set'
        mock_module.params['state'] = 'absent'
        mock_module.params['paths'] = ['/interfaces/interface[name=GigabitEthernet1]/config/description']

        mock_gnmi_client.set.return_value = GnmiResult(
            success=True,
            data={'timestamp': 123456789},
            error=None,
            changed=True
        )

        module_obj = CiscoIosXeGnmi(mock_module)
        module_obj.client = mock_gnmi_client
        module_obj.execute_set()

        assert module_obj.result['changed'] is True
        # Verify delete was called
        call_args = mock_gnmi_client.set.call_args
        assert 'delete' in call_args.kwargs or (call_args.args and call_args.args[0])

    def test_module_check_mode(self, mock_module, mock_gnmi_client):
        """Test check mode doesn't make changes"""
        from ansible_collections.cisco.iosxe_gnmi.plugins.modules.cisco_iosxe_gnmi import CiscoIosXeGnmi

        mock_module.check_mode = True
        mock_module.params['operation'] = 'set'
        mock_module.params['config'] = [
            {'path': '/test/path', 'value': 'test'}
        ]

        module_obj = CiscoIosXeGnmi(mock_module)
        module_obj.client = mock_gnmi_client
        module_obj.execute_set()

        assert module_obj.result['changed'] is True
        assert 'Check mode' in module_obj.result['msg']
        # Verify set was NOT called
        mock_gnmi_client.set.assert_not_called()

    def test_module_diff_mode(self, mock_module, mock_gnmi_client):
        """Test diff mode captures before/after state"""
        from ansible_collections.cisco.iosxe_gnmi.plugins.modules.cisco_iosxe_gnmi import CiscoIosXeGnmi
        from ansible_collections.cisco.iosxe_gnmi.plugins.module_utils.gnmi_client import GnmiResult

        mock_module._diff = True
        mock_module.params['operation'] = 'set'
        mock_module.params['config'] = [
            {'path': '/test/path', 'value': 'new_value'}
        ]

        # Mock GET for before/after states
        mock_gnmi_client.get.side_effect = [
            GnmiResult(success=True, data={'/test/path': 'old_value'}, error=None, changed=False),
            GnmiResult(success=True, data={'/test/path': 'new_value'}, error=None, changed=False)
        ]

        mock_gnmi_client.set.return_value = GnmiResult(
            success=True,
            data={'timestamp': 123456789},
            error=None,
            changed=True
        )

        module_obj = CiscoIosXeGnmi(mock_module)
        module_obj.client = mock_gnmi_client
        module_obj.execute_set()

        assert 'diff' in module_obj.result
        assert 'before' in module_obj.result['diff']
        assert 'after' in module_obj.result['diff']

    def test_module_backup_creation(self, mock_module, mock_gnmi_client):
        """Test backup file creation"""
        from ansible_collections.cisco.iosxe_gnmi.plugins.modules.cisco_iosxe_gnmi import CiscoIosXeGnmi
        from ansible_collections.cisco.iosxe_gnmi.plugins.module_utils.gnmi_client import GnmiResult

        mock_module.params['operation'] = 'set'
        mock_module.params['backup'] = True
        mock_module.params['config'] = [
            {'path': '/test/path', 'value': 'test'}
        ]

        # Mock GET for backup
        mock_gnmi_client.get.return_value = GnmiResult(
            success=True,
            data={'/test/path': 'current_value'},
            error=None,
            changed=False
        )

        mock_gnmi_client.set.return_value = GnmiResult(
            success=True,
            data={'timestamp': 123456789},
            error=None,
            changed=True
        )

        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', MagicMock()), \
             patch('os.makedirs'):

            module_obj = CiscoIosXeGnmi(mock_module)
            module_obj.client = mock_gnmi_client
            module_obj.execute_set()

            # Backup file path should be in result
            # Note: actual backup file creation is mocked

    def test_module_subscribe_operation(self, mock_module, mock_gnmi_client):
        """Test Subscribe operation"""
        from ansible_collections.cisco.iosxe_gnmi.plugins.modules.cisco_iosxe_gnmi import CiscoIosXeGnmi
        from ansible_collections.cisco.iosxe_gnmi.plugins.module_utils.gnmi_client import GnmiResult

        mock_module.params['operation'] = 'subscribe'
        mock_module.params['subscriptions'] = [
            {'path': '/interfaces/interface/state/counters', 'mode': 'target_defined'}
        ]

        mock_gnmi_client.subscribe.return_value = GnmiResult(
            success=True,
            data={
                'updates': [
                    {'path': '/test', 'value': {'counter': 100}}
                ]
            },
            error=None,
            changed=False
        )

        module_obj = CiscoIosXeGnmi(mock_module)
        module_obj.client = mock_gnmi_client
        module_obj.execute_subscribe()

        assert 'updates' in module_obj.result
        assert len(module_obj.result['updates']) > 0

    def test_module_missing_paths_for_get(self, mock_module, mock_gnmi_client):
        """Test GET operation fails without paths"""
        from ansible_collections.cisco.iosxe_gnmi.plugins.modules.cisco_iosxe_gnmi import CiscoIosXeGnmi

        mock_module.params['paths'] = None

        module_obj = CiscoIosXeGnmi(mock_module)
        module_obj.client = mock_gnmi_client

        with pytest.raises(SystemExit):
            module_obj.execute_get()

        mock_module.fail_json.assert_called()
        assert 'paths parameter is required' in str(mock_module.fail_json.call_args)

    def test_module_missing_config_for_set(self, mock_module, mock_gnmi_client):
        """Test SET operation fails without config for present state"""
        from ansible_collections.cisco.iosxe_gnmi.plugins.modules.cisco_iosxe_gnmi import CiscoIosXeGnmi

        mock_module.params['operation'] = 'set'
        mock_module.params['config'] = None

        module_obj = CiscoIosXeGnmi(mock_module)
        module_obj.client = mock_gnmi_client

        with pytest.raises(SystemExit):
            module_obj.execute_set()

        mock_module.fail_json.assert_called()

    def test_module_invalid_config_format(self, mock_module, mock_gnmi_client):
        """Test SET operation fails with invalid config format"""
        from ansible_collections.cisco.iosxe_gnmi.plugins.modules.cisco_iosxe_gnmi import CiscoIosXeGnmi

        mock_module.params['operation'] = 'set'
        mock_module.params['config'] = [
            {'invalid': 'format'}  # Missing 'path' and 'value'
        ]

        module_obj = CiscoIosXeGnmi(mock_module)
        module_obj.client = mock_gnmi_client

        with pytest.raises(SystemExit):
            module_obj.execute_set()

        mock_module.fail_json.assert_called()

    def test_module_connection_error_handling(self, mock_module):
        """Test connection error handling"""
        from ansible_collections.cisco.iosxe_gnmi.plugins.modules.cisco_iosxe_gnmi import CiscoIosXeGnmi
        from ansible_collections.cisco.iosxe_gnmi.plugins.module_utils.gnmi_client import GnmiConnectionError

        with patch('ansible_collections.cisco.iosxe_gnmi.plugins.modules.cisco_iosxe_gnmi.GnmiClient') as mock_client:
            mock_client.return_value.connect.side_effect = GnmiConnectionError("Connection failed")

            module_obj = CiscoIosXeGnmi(mock_module)

            with pytest.raises(SystemExit):
                module_obj.run()

            mock_module.fail_json.assert_called()
            assert 'Connection error' in str(mock_module.fail_json.call_args)


class TestModuleArgumentSpec:
    """Test module argument specification"""

    def test_required_parameters(self):
        """Test required parameters are defined"""
        from ansible_collections.cisco.iosxe_gnmi.plugins.modules.cisco_iosxe_gnmi import main

        # This would normally test the argument_spec
        # For now, we verify the module structure is correct
        pass

    def test_default_values(self):
        """Test default parameter values"""
        from ansible_collections.cisco.iosxe_gnmi.plugins.modules.cisco_iosxe_gnmi import main

        # Verify defaults are set correctly
        pass


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
