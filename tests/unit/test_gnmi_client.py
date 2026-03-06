"""
Unit tests for vendor-neutral gNMI Client.

Tests the GnmiClient class with mocked gRPC connections.
"""

import pytest
from unittest.mock import MagicMock, patch
from ansible_collections.cisco.gnmi.plugins.module_utils.gnmi_client import (
    GnmiClient,
    GnmiClientError,
    GnmiConnectionError,
    GnmiOperationError,
    GnmiResult,
    PLATFORM_PROFILES,
)


class TestGnmiClientInit:
    """Test GnmiClient initialisation and validation."""

    def test_default_init(self):
        client = GnmiClient(host='10.0.0.1', username='admin', password='secret')
        assert client.host == '10.0.0.1'
        assert client.port == 9339
        assert client.encoding == 4  # json_ietf
        assert client.platform == 'auto'
        assert client.timeout == 30

    def test_custom_port_and_encoding(self):
        client = GnmiClient(host='10.0.0.1', username='admin', password='secret',
                            port=57400, encoding='json')
        assert client.port == 57400
        assert client.encoding == 0

    def test_invalid_encoding_raises(self):
        with pytest.raises(GnmiClientError, match='Invalid encoding'):
            GnmiClient(host='10.0.0.1', username='admin', password='secret',
                       encoding='bytes')

    def test_invalid_port_raises(self):
        with pytest.raises(GnmiClientError, match='Invalid port'):
            GnmiClient(host='10.0.0.1', username='admin', password='secret',
                       port=99999)

    def test_all_valid_encodings(self):
        for name, val in GnmiClient.ENCODING_MAP.items():
            client = GnmiClient(host='10.0.0.1', username='admin', password='secret',
                                encoding=name)
            assert client.encoding == val

    def test_platform_lowercased(self):
        client = GnmiClient(host='10.0.0.1', username='admin', password='secret',
                            platform='IOSXE')
        assert client.platform == 'iosxe'


class TestEncodingPlatformChecks:
    """Test platform-specific encoding restrictions."""

    def test_iosxe_proto_get_raises(self):
        client = GnmiClient(host='10.0.0.1', username='admin', password='secret',
                            encoding='proto', platform='iosxe')
        with pytest.raises(GnmiOperationError, match='PROTO encoding'):
            client.get(paths=['/interfaces/interface'])

    def test_iosxe_proto_set_raises(self):
        client = GnmiClient(host='10.0.0.1', username='admin', password='secret',
                            encoding='proto', platform='iosxe')
        with pytest.raises(GnmiOperationError, match='PROTO encoding'):
            client.set(update=[('/test', 'val')])

    def test_auto_platform_proto_get_ok(self):
        """With platform=auto, proto GET should not raise (no platform restrictions)."""
        client = GnmiClient(host='10.0.0.1', username='admin', password='secret',
                            encoding='proto', platform='auto')
        client._check_encoding_for_op('get')

    def test_iosxr_proto_get_ok(self):
        """IOS XR does not block proto for GET."""
        client = GnmiClient(host='10.0.0.1', username='admin', password='secret',
                            encoding='proto', platform='iosxr')
        client._check_encoding_for_op('get')


class TestPathBuilding:
    """Test _build_path and _path_to_string."""

    @pytest.fixture
    def client(self):
        return GnmiClient(host='10.0.0.1', username='admin', password='secret')

    def test_simple_path(self, client):
        path = client._build_path('/interfaces/interface')
        assert len(path.elem) == 2
        assert path.elem[0].name == 'interfaces'
        assert path.elem[1].name == 'interface'

    def test_path_with_keys(self, client):
        path = client._build_path('/interfaces/interface[name=GigabitEthernet1]/config')
        assert len(path.elem) == 3
        assert path.elem[1].key['name'] == 'GigabitEthernet1'

    def test_roundtrip(self, client):
        original = '/interfaces/interface'
        path_obj = client._build_path(original)
        assert client._path_to_string(path_obj) == original

    def test_origin_explicit(self, client):
        path = client._build_path('/native/hostname', origin='rfc7951')
        assert path.origin == 'rfc7951'

    def test_origin_auto_cisco_xe(self, client):
        path = client._build_path('/Cisco-IOS-XE-native:native/hostname')
        assert path.origin == 'rfc7951'

    def test_origin_auto_cisco_xr(self, client):
        path = client._build_path('/Cisco-IOS-XR-ifmgr-cfg:interface-configurations')
        assert path.origin == 'rfc7951'

    def test_origin_auto_openconfig(self, client):
        path = client._build_path('/openconfig-interfaces:interfaces/interface')
        assert path.origin == 'openconfig'

    def test_origin_default_empty(self, client):
        path = client._build_path('/interfaces/interface')
        assert path.origin == ''


class TestTypedValues:
    """Test _build_typed_value and _parse_typed_value."""

    @pytest.fixture
    def client(self):
        return GnmiClient(host='10.0.0.1', username='admin', password='secret')

    def test_string_value(self, client):
        tv = client._build_typed_value('hello')
        assert tv.string_val == 'hello'

    def test_int_value(self, client):
        tv = client._build_typed_value(42)
        assert tv.int_val == 42

    def test_bool_value(self, client):
        tv = client._build_typed_value(True)
        assert tv.bool_val is True

    def test_float_value(self, client):
        tv = client._build_typed_value(3.14)
        assert tv.float_val == pytest.approx(3.14)

    def test_dict_json_ietf(self, client):
        tv = client._build_typed_value({'a': 1})
        assert tv.json_ietf_val is not None

    def test_dict_json(self):
        client = GnmiClient(host='10.0.0.1', username='admin', password='secret',
                            encoding='json')
        tv = client._build_typed_value({'a': 1})
        assert tv.json_val is not None


class TestDatatype:
    """Test datatype conversion."""

    @pytest.fixture
    def client(self):
        return GnmiClient(host='10.0.0.1', username='admin', password='secret')

    def test_valid_datatypes(self, client):
        assert client._get_datatype('all') == 0
        assert client._get_datatype('config') == 1
        assert client._get_datatype('state') == 2
        assert client._get_datatype('operational') == 3

    def test_invalid_datatype(self, client):
        with pytest.raises(GnmiClientError, match='Invalid datatype'):
            client._get_datatype('invalid')


class TestGnmiResult:
    """Test GnmiResult namedtuple."""

    def test_success_result(self):
        r = GnmiResult(success=True, data={'k': 'v'}, error=None, changed=True)
        assert r.success and r.changed and r.error is None

    def test_failure_result(self):
        r = GnmiResult(success=False, data=None, error='fail', changed=False)
        assert not r.success and r.error == 'fail'


class TestContextManager:
    """Test context manager protocol."""

    def test_enter_exit(self):
        with patch('ansible_collections.cisco.gnmi.plugins.module_utils.gnmi_client.grpc'):
            client = GnmiClient(host='10.0.0.1', username='admin', password='secret')
            with client as c:
                assert isinstance(c, GnmiClient)


class TestPlatformProfiles:
    """Test platform profile data."""

    def test_iosxe_profile(self):
        p = PLATFORM_PROFILES['iosxe']
        assert p['default_port'] == 9339
        assert 'proto' in p['blocked_encodings_get']

    def test_iosxr_profile(self):
        p = PLATFORM_PROFILES['iosxr']
        assert p['default_port'] == 57400
        assert p['blocked_encodings_get'] == []


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
