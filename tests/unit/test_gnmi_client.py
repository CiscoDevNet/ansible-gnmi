"""
Unit tests for Cisco IOS XE gNMI Client

Tests the GnmiClient class with mocked gRPC connections
"""

import pytest
import json
from unittest.mock import Mock, MagicMock, patch, mock_open
from ansible_collections.cisco.iosxe_gnmi.plugins.module_utils.gnmi_client import (
    GnmiClient,
    GnmiClientError,
    GnmiConnectionError,
    GnmiAuthenticationError,
    GnmiOperationError,
    GnmiResult
)


class TestGnmiClient:
    """Test suite for GnmiClient class"""

    def test_client_initialization(self):
        """Test basic client initialization"""
        client = GnmiClient(
            host='192.168.1.1',
            port=9339,
            username='admin',
            password='cisco',
            encoding='json_ietf'
        )

        assert client.host == '192.168.1.1'
        assert client.port == 9339
        assert client.username == 'admin'
        assert client.password == 'cisco'
        assert client.encoding == 4  # json_ietf encoding value

    def test_invalid_encoding(self):
        """Test that invalid encoding raises error"""
        with pytest.raises(GnmiClientError) as exc_info:
            GnmiClient(
                host='192.168.1.1',
                username='admin',
                password='cisco',
                encoding='bytes'  # NOT supported on Cisco IOS XE
            )

        assert 'Invalid encoding' in str(exc_info.value)
        assert 'bytes' in str(exc_info.value).lower()

    def test_ascii_encoding_not_supported(self):
        """Test that ASCII encoding is not supported"""
        with pytest.raises(GnmiClientError) as exc_info:
            GnmiClient(
                host='192.168.1.1',
                username='admin',
                password='cisco',
                encoding='ascii'  # NOT supported on Cisco IOS XE
            )

        assert 'NOT supported' in str(exc_info.value)

    def test_valid_encodings(self):
        """Test all valid encodings for Cisco IOS XE"""
        valid_encodings = ['json', 'json_ietf', 'proto']

        for encoding in valid_encodings:
            client = GnmiClient(
                host='192.168.1.1',
                username='admin',
                password='cisco',
                encoding=encoding
            )
            assert client.encoding in [0, 2, 4]

    def test_default_port(self):
        """Test default port is 9339 (secure)"""
        client = GnmiClient(
            host='192.168.1.1',
            username='admin',
            password='cisco'
        )
        assert client.port == 9339

    def test_build_path_simple(self):
        """Test building simple gNMI path"""
        client = GnmiClient(
            host='192.168.1.1',
            username='admin',
            password='cisco'
        )

        path_str = '/interfaces/interface'
        path_obj = client._build_path(path_str)

        assert len(path_obj.elem) == 2
        assert path_obj.elem[0].name == 'interfaces'
        assert path_obj.elem[1].name == 'interface'

    def test_build_path_with_keys(self):
        """Test building gNMI path with keys"""
        client = GnmiClient(
            host='192.168.1.1',
            username='admin',
            password='cisco'
        )

        path_str = '/interfaces/interface[name=GigabitEthernet1]/config'
        path_obj = client._build_path(path_str)

        assert len(path_obj.elem) == 3
        assert path_obj.elem[1].name == 'interface'
        assert path_obj.elem[1].key['name'] == 'GigabitEthernet1'
        assert path_obj.elem[2].name == 'config'

    @patch('ansible_collections.cisco.iosxe_gnmi.plugins.module_utils.gnmi_client.grpc')
    @patch('ansible_collections.cisco.iosxe_gnmi.plugins.module_utils.gnmi_client.gnmi_pb2_grpc')
    def test_connection_success(self, mock_grpc_gnmi, mock_grpc):
        """Test successful gRPC connection"""
        mock_channel = MagicMock()
        mock_stub = MagicMock()
        mock_grpc.secure_channel.return_value = mock_channel
        mock_grpc_gnmi.gNMIStub.return_value = mock_stub

        client = GnmiClient(
            host='192.168.1.1',
            username='admin',
            password='cisco'
        )
        client.connect()

        assert client.channel is not None
        assert client.stub is not None
        mock_grpc.secure_channel.assert_called_once()

    @patch('ansible_collections.cisco.iosxe_gnmi.plugins.module_utils.gnmi_client.grpc')
    def test_get_with_proto_encoding_fails(self, mock_grpc):
        """Test that GET with PROTO encoding raises error"""
        client = GnmiClient(
            host='192.168.1.1',
            username='admin',
            password='cisco',
            encoding='proto'
        )

        with pytest.raises(GnmiOperationError) as exc_info:
            client.get(paths=['/interfaces/interface'])

        assert 'PROTO encoding is NOT supported for GET' in str(exc_info.value)

    @patch('ansible_collections.cisco.iosxe_gnmi.plugins.module_utils.gnmi_client.grpc')
    def test_set_with_proto_encoding_fails(self, mock_grpc):
        """Test that SET with PROTO encoding raises error"""
        client = GnmiClient(
            host='192.168.1.1',
            username='admin',
            password='cisco',
            encoding='proto'
        )

        with pytest.raises(GnmiOperationError) as exc_info:
            client.set(update=[('/test/path', 'value')])

        assert 'PROTO encoding is NOT supported for SET' in str(exc_info.value)

    def test_datatype_conversion(self):
        """Test datatype string to value conversion"""
        client = GnmiClient(
            host='192.168.1.1',
            username='admin',
            password='cisco'
        )

        assert client._get_datatype('all') == 0
        assert client._get_datatype('config') == 1
        assert client._get_datatype('state') == 2
        assert client._get_datatype('operational') == 3

    def test_invalid_datatype(self):
        """Test invalid datatype raises error"""
        client = GnmiClient(
            host='192.168.1.1',
            username='admin',
            password='cisco'
        )

        with pytest.raises(GnmiClientError):
            client._get_datatype('invalid')

    def test_context_manager(self):
        """Test client as context manager"""
        with patch('ansible_collections.cisco.iosxe_gnmi.plugins.module_utils.gnmi_client.grpc'):
            client = GnmiClient(
                host='192.168.1.1',
                username='admin',
                password='cisco'
            )

            with client as c:
                assert c is not None
                assert isinstance(c, GnmiClient)

    def test_build_typed_value_string(self):
        """Test building TypedValue from string"""
        client = GnmiClient(
            host='192.168.1.1',
            username='admin',
            password='cisco'
        )

        typed_value = client._build_typed_value("test string")
        assert typed_value.string_val == "test string"

    def test_build_typed_value_integer(self):
        """Test building TypedValue from integer"""
        client = GnmiClient(
            host='192.168.1.1',
            username='admin',
            password='cisco'
        )

        typed_value = client._build_typed_value(42)
        assert typed_value.int_val == 42

    def test_build_typed_value_boolean(self):
        """Test building TypedValue from boolean"""
        client = GnmiClient(
            host='192.168.1.1',
            username='admin',
            password='cisco'
        )

        typed_value = client._build_typed_value(True)
        assert typed_value.bool_val is True

    def test_build_typed_value_dict(self):
        """Test building TypedValue from dictionary"""
        client = GnmiClient(
            host='192.168.1.1',
            username='admin',
            password='cisco',
            encoding='json_ietf'
        )

        data = {'key': 'value', 'number': 42}
        typed_value = client._build_typed_value(data)

        # Should be JSON encoded
        assert typed_value.json_ietf_val is not None

    def test_path_to_string_simple(self):
        """Test converting path object to string"""
        client = GnmiClient(
            host='192.168.1.1',
            username='admin',
            password='cisco'
        )

        # First build a path, then convert back to string
        path_obj = client._build_path('/interfaces/interface')
        path_str = client._path_to_string(path_obj)

        assert path_str == '/interfaces/interface'

    def test_path_to_string_with_keys(self):
        """Test converting path with keys to string"""
        client = GnmiClient(
            host='192.168.1.1',
            username='admin',
            password='cisco'
        )

        path_obj = client._build_path('/interfaces/interface[name=GigabitEthernet1]')
        path_str = client._path_to_string(path_obj)

        assert '/interfaces/interface' in path_str
        assert 'name=GigabitEthernet1' in path_str


class TestGnmiResult:
    """Test GnmiResult namedtuple"""

    def test_gnmi_result_success(self):
        """Test creating successful result"""
        result = GnmiResult(
            success=True,
            data={'key': 'value'},
            error=None,
            changed=True
        )

        assert result.success is True
        assert result.data == {'key': 'value'}
        assert result.error is None
        assert result.changed is True

    def test_gnmi_result_failure(self):
        """Test creating failure result"""
        result = GnmiResult(
            success=False,
            data=None,
            error='Connection failed',
            changed=False
        )

        assert result.success is False
        assert result.data is None
        assert result.error == 'Connection failed'
        assert result.changed is False


class TestGnmiClientValidation:
    """Test Cisco IOS XE specific validation"""

    def test_validate_encoding_json_ietf(self):
        """Test JSON_IETF encoding is recommended"""
        client = GnmiClient(
            host='192.168.1.1',
            username='admin',
            password='cisco',
            encoding='json_ietf'
        )
        assert client.encoding == 4

    def test_insecure_mode_warning(self):
        """Test that insecure mode works but is not recommended"""
        client = GnmiClient(
            host='192.168.1.1',
            username='admin',
            password='cisco',
            insecure=True
        )
        assert client.insecure is True

    def test_custom_port(self):
        """Test custom port configuration"""
        client = GnmiClient(
            host='192.168.1.1',
            username='admin',
            password='cisco',
            port=50052  # Insecure port
        )
        assert client.port == 50052

    def test_timeout_configuration(self):
        """Test timeout configuration"""
        client = GnmiClient(
            host='192.168.1.1',
            username='admin',
            password='cisco',
            timeout=60
        )
        assert client.timeout == 60


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
