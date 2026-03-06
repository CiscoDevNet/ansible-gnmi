#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright: (c) 2025, Jeremy Cohoe <jcohoe@cisco.com>
# Apache License 2.0 (see LICENSE or http://www.apache.org/licenses/LICENSE-2.0)

"""
Vendor-Neutral gNMI Client Implementation

This module implements a gNMI (gRPC Network Management Interface) client
that works with any gNMI-capable network device, including but not limited to:

    - Cisco IOS XE (default port 9339)
    - Cisco IOS XR (default port 57400)
    - Cisco NX-OS (default port 50051)
    - Nokia SR OS (default port 57400)
    - Arista EOS (default port 6030)
    - Juniper Junos (default port 32767)
    - Any OpenConfig gNMI compliant device

gNMI Specification Reference:
    https://github.com/openconfig/reference/blob/master/rpc/gnmi/gnmi-specification.md

Platform-specific notes are documented in PLATFORM_NOTES.md.
"""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

import grpc
import json
import logging
from collections import namedtuple

try:
    # Import from local generated proto files
    from . import gnmi_pb2, gnmi_pb2_grpc
    HAS_GNMI = True
    GNMI_IMPORT_ERROR = None
except ImportError as e:
    HAS_GNMI = False
    GNMI_IMPORT_ERROR = str(e)
    # Create minimal dummy classes to prevent import errors
    class gnmi_pb2:  # noqa: E303
        """Dummy gnmi_pb2 when proto files are not available."""
        class Path:
            pass

        class PathElem:
            pass

        class TypedValue:
            pass

        class GetRequest:
            pass

        class GetResponse:
            pass

        class SetRequest:
            pass

        class SetResponse:
            pass

        class Update:
            pass

        class SubscribeRequest:
            pass

        class SubscriptionList:
            pass

        class Subscription:
            pass

        class Encoding:
            JSON = 0
            BYTES = 1
            PROTO = 2
            ASCII = 3
            JSON_IETF = 4

        class DataType:
            ALL = 0
            CONFIG = 1
            STATE = 2
            OPERATIONAL = 3

    class gnmi_pb2_grpc:  # noqa: E303
        """Dummy gnmi_pb2_grpc when proto files are not available."""
        class gNMIStub:
            pass


logger = logging.getLogger(__name__)


class GnmiClientError(Exception):
    """Base exception for gNMI client errors."""
    pass


class GnmiConnectionError(GnmiClientError):
    """Exception for connection-related errors."""
    pass


class GnmiAuthenticationError(GnmiClientError):
    """Exception for authentication-related errors."""
    pass


class GnmiOperationError(GnmiClientError):
    """Exception for gNMI operation errors."""
    pass


GnmiResult = namedtuple('GnmiResult', ['success', 'data', 'error', 'changed'])


# Platform-specific defaults and known restrictions.
# When platform='auto' (default), no restrictions are enforced.
PLATFORM_PROFILES = {
    'iosxe': {
        'default_port': 9339,
        'insecure_port': 50052,
        'recommended_encoding': 'json_ietf',
        'blocked_encodings_get': ['proto'],
        'blocked_encodings_set': ['proto'],
        # IOS XE only supports STREAM for the SubscriptionList mode.
        'subscribe_list_modes': ['stream'],
        # IOS XE only supports ON_CHANGE and SAMPLE (not TARGET_DEFINED).
        'subscribe_modes': ['on_change', 'sample'],
        'gnmi_version': '0.4.0',
        'notes': 'PROTO encoding only works with Subscribe RPC on Cisco IOS XE. '
                 'SetRequest operations are atomic (all-or-nothing rollback). '
                 'Configuration changes via gNMI SetRequest persist across reboots '
                 '(from IOS XE 17.3.1). '
                 'sync_response support requires IOS XE 17.14.1 or later.',
    },
    'iosxr': {
        'default_port': 57400,
        'recommended_encoding': 'json_ietf',
        'blocked_encodings_get': [],
        'blocked_encodings_set': [],
        'subscribe_list_modes': [],
        'subscribe_modes': [],
        'notes': '',
    },
    'nxos': {
        'default_port': 50051,
        'recommended_encoding': 'json_ietf',
        'blocked_encodings_get': [],
        'blocked_encodings_set': [],
        'subscribe_list_modes': [],
        'subscribe_modes': [],
        'notes': '',
    },
    'nokia_sros': {
        'default_port': 57400,
        'recommended_encoding': 'json_ietf',
        'blocked_encodings_get': [],
        'blocked_encodings_set': [],
        'subscribe_list_modes': [],
        'subscribe_modes': [],
        'notes': '',
    },
    'arista_eos': {
        'default_port': 6030,
        'recommended_encoding': 'json',
        'blocked_encodings_get': [],
        'blocked_encodings_set': [],
        'subscribe_list_modes': [],
        'subscribe_modes': [],
        'notes': '',
    },
}


class GnmiClient:
    """
    Vendor-neutral gNMI client.

    Provides methods for GET, SET, and Subscribe operations over gRPC.
    Works with any gNMI-capable network device.  When `platform` is set
    to a known vendor (e.g. `iosxe`), platform-specific restrictions are
    enforced as errors; otherwise they are emitted as warnings only.
    """

    ENCODING_MAP = {
        'json': 0,
        'proto': 2,
        'json_ietf': 4,
    }

    DATATYPE_MAP = {
        'all': 0,
        'config': 1,
        'state': 2,
        'operational': 3,
    }

    def __init__(self,
                 host,
                 port=9339,
                 username=None,
                 password=None,
                 encoding='json_ietf',
                 timeout=30,
                 insecure=False,
                 ca_cert=None,
                 client_cert=None,
                 client_key=None,
                 platform='auto',
                 warn_callback=None):
        """
        Initialise gNMI client.

        Args:
            host: Target device hostname or IP.
            port: gNMI port number.
            username: Authentication username (sent as gRPC metadata).
            password: Authentication password (sent as gRPC metadata).
            encoding: Data encoding - `json_ietf` (default), `json`, or `proto`.
            timeout: Connection / RPC timeout in seconds.
            insecure: When *True*, skip TLS certificate validation.
            ca_cert: Path to CA certificate file.
            client_cert: Path to client certificate for mutual TLS.
            client_key: Path to client private key for mutual TLS.
            platform: Optional platform hint (`auto`, `iosxe`, `iosxr`, `nxos`,
                       `nokia_sros`, `arista_eos`).  `auto` applies no restrictions.
            warn_callback: Callable that accepts a single string message, used to
                           emit warnings (e.g. `module.warn`).
        """
        if not HAS_GNMI:
            raise GnmiClientError(
                "gNMI libraries are not available.  Install with "
                "'pip install grpcio grpcio-tools protobuf'.  "
                "Import error: {0}".format(GNMI_IMPORT_ERROR)
            )

        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.encoding = self._resolve_encoding(encoding)
        self.encoding_name = encoding.lower() if isinstance(encoding, str) else encoding
        self.timeout = timeout
        self.insecure = insecure
        self.ca_cert = ca_cert
        self.client_cert = client_cert
        self.client_key = client_key
        self.platform = platform.lower() if platform else 'auto'
        self._warn = warn_callback or (lambda msg: logger.warning(msg))

        self.channel = None
        self.stub = None
        self._metadata = None

        self._validate_config()

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    def _validate_config(self):
        """Validate client configuration and emit warnings for unusual settings."""
        if self.port and (self.port < 1 or self.port > 65535):
            raise GnmiClientError("Invalid port number: {0}".format(self.port))

        profile = PLATFORM_PROFILES.get(self.platform)
        if profile:
            if self.port == profile['default_port'] and self.insecure:
                insecure_port = profile.get('insecure_port')
                hint = ''
                if insecure_port:
                    hint = '  The default insecure port for {0} is {1}.'.format(
                        self.platform, insecure_port)
                self._warn(
                    "Port {0} is the default *secure* port for {1}; "
                    "using insecure=true may be unintentional.{2}".format(
                        self.port, self.platform, hint))

    def _resolve_encoding(self, encoding):
        """Convert encoding string to gNMI numeric value."""
        if isinstance(encoding, int):
            return encoding
        name = encoding.lower()
        if name not in self.ENCODING_MAP:
            raise GnmiClientError(
                "Invalid encoding: '{0}'.  Supported encodings: {1}.".format(
                    encoding, list(self.ENCODING_MAP.keys())))
        return self.ENCODING_MAP[name]

    def _check_encoding_for_op(self, operation):
        """
        Warn or raise if the current encoding is blocked for *operation*
        on the configured *platform*.

        Args:
            operation: `'get'` or `'set'`.
        """
        profile = PLATFORM_PROFILES.get(self.platform)
        if not profile:
            return  # no restrictions for 'auto' / unknown platforms

        key = 'blocked_encodings_{0}'.format(operation)
        blocked = profile.get(key, [])
        if self.encoding_name in blocked:
            msg = (
                "PROTO encoding is not supported for {op} operations on {plat}.  "
                "{notes}  Consider using JSON_IETF or JSON instead.".format(
                    op=operation.upper(), plat=self.platform,
                    notes=profile.get('notes', '')))
            # When platform is explicitly set, raise
            raise GnmiOperationError(msg)

    def _check_subscribe_restrictions(self, mode, subscriptions):
        """
        Warn or raise when subscribe parameters violate platform restrictions.

        IOS XE only supports STREAM as the SubscriptionList mode and only
        ON_CHANGE and SAMPLE as the per-subscription SubscriptionMode.

        Args:
            mode: SubscriptionList mode string (``stream``, ``once``, ``poll``).
            subscriptions: List of ``(path, sub_mode, sample_interval)`` tuples.
        """
        profile = PLATFORM_PROFILES.get(self.platform)
        if not profile:
            return  # no restrictions for 'auto' / unknown platforms

        # --- SubscriptionList mode ----------------------------------
        allowed_list_modes = profile.get('subscribe_list_modes', [])
        if allowed_list_modes and mode.lower() not in allowed_list_modes:
            msg = (
                "Subscribe list mode '{mode}' is not supported on {plat}.  "
                "Supported modes: {allowed}.  {notes}".format(
                    mode=mode, plat=self.platform,
                    allowed=', '.join(allowed_list_modes),
                    notes=profile.get('notes', '')))
            # poll is definitively unsupported; once may work on 17.14.1+
            if mode.lower() == 'poll':
                raise GnmiOperationError(msg)
            else:
                self._warn(msg)

        # --- Per-subscription mode -----------------------------------
        allowed_sub_modes = profile.get('subscribe_modes', [])
        if allowed_sub_modes:
            for path, sub_mode, _interval in subscriptions:
                if sub_mode.lower() not in allowed_sub_modes:
                    msg = (
                        "Subscription mode '{sub_mode}' for path '{path}' "
                        "is not supported on {plat}.  "
                        "Supported modes: {allowed}.  "
                        "Defaulting may cause unexpected behaviour.".format(
                            sub_mode=sub_mode, path=path,
                            plat=self.platform,
                            allowed=', '.join(allowed_sub_modes)))
                    self._warn(msg)

    def _get_datatype(self, datatype):
        """Convert datatype string to gNMI numeric value."""
        name = datatype.lower()
        if name not in self.DATATYPE_MAP:
            raise GnmiClientError(
                "Invalid datatype: '{0}'.  Valid options: {1}".format(
                    datatype, list(self.DATATYPE_MAP.keys())))
        return self.DATATYPE_MAP[name]

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def connect(self):
        """Establish gRPC channel and instantiate the gNMI stub."""
        try:
            target = "{0}:{1}".format(self.host, self.port)

            if self.insecure:
                import os
                os.environ['GRPC_DEFAULT_SSL_ROOTS_FILE_PATH'] = ''
                credentials = grpc.ssl_channel_credentials()
                self.channel = grpc.secure_channel(
                    target,
                    credentials,
                    options=[
                        ('grpc.ssl_target_name_override', self.host),
                    ]
                )
            else:
                ca_cert_data = None
                client_cert_data = None
                client_key_data = None

                if self.ca_cert:
                    with open(self.ca_cert, 'rb') as fh:
                        ca_cert_data = fh.read()

                if self.client_cert and self.client_key:
                    with open(self.client_cert, 'rb') as fh:
                        client_cert_data = fh.read()
                    with open(self.client_key, 'rb') as fh:
                        client_key_data = fh.read()

                credentials = grpc.ssl_channel_credentials(
                    root_certificates=ca_cert_data,
                    private_key=client_key_data,
                    certificate_chain=client_cert_data,
                )

                options = []
                if ca_cert_data:
                    try:
                        from cryptography import x509
                        from cryptography.hazmat.backends import default_backend
                        cert = x509.load_pem_x509_certificate(ca_cert_data, default_backend())
                        for attr in cert.subject:
                            if attr.oid == x509.oid.NameOID.COMMON_NAME:
                                options.append(('grpc.ssl_target_name_override', attr.value))
                                break
                    except Exception as exc:
                        logger.debug("Could not extract CN from CA cert: %s", exc)

                self.channel = grpc.secure_channel(
                    target, credentials,
                    options=options if options else None,
                )

            self.stub = gnmi_pb2_grpc.gNMIStub(self.channel)

            if self.username and self.password:
                self._metadata = [
                    ('username', self.username),
                    ('password', self.password),
                ]

        except Exception as exc:
            raise GnmiConnectionError(
                "Failed to connect to {0}:{1}: {2}".format(self.host, self.port, exc))

    def disconnect(self):
        """Close the gRPC channel."""
        if self.channel:
            self.channel.close()
            self.channel = None
            self.stub = None

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    def _build_path(self, path, origin=None):
        """
        Build a `gnmi_pb2.Path` from a string.

        The *origin* parameter takes precedence.  If not provided, the
        method auto-detects an origin from well-known namespace prefixes
        found in the first path element (e.g. `Cisco-IOS-XE-*`,
        `Cisco-IOS-XR-*`, `openconfig-*`).

        Args:
            path: Path string, e.g. `/interfaces/interface[name=Gi1]/config`.
            origin: Explicit origin (`rfc7951`, `openconfig`, etc.).

        Returns:
            `gnmi_pb2.Path`
        """
        path_elements = []
        extracted_origin = None

        if path.startswith('/'):
            path = path[1:]

        # Auto-detect origin from namespace prefix in the first path element
        first_elem = path.split('/')[0] if '/' in path else path
        if ':' in first_elem and '[' not in first_elem.split(':')[0]:
            prefix_part = first_elem.split(':')[0]
            if prefix_part.startswith(('Cisco-IOS-XE-', 'Cisco-IOS-XR-',
                                       'Cisco-IOS-', 'Cisco-NX-OS-')):
                extracted_origin = 'rfc7951'
            elif prefix_part.startswith('openconfig'):
                extracted_origin = 'openconfig'
            elif prefix_part.startswith(('ietf-', 'IF-MIB', 'RFC')):
                extracted_origin = 'rfc7951'

        for element in path.split('/'):
            if not element:
                continue

            if '[' in element and ']' in element:
                name_part = element[:element.index('[')]
                keys_part = element[element.index('['):].strip('[]')

                keys = {}
                for kv in keys_part.split(']['):
                    if '=' in kv:
                        k, v = kv.split('=', 1)
                        keys[k] = v

                path_elements.append(gnmi_pb2.PathElem(name=name_part, key=keys))
            else:
                path_elements.append(gnmi_pb2.PathElem(name=element))

        final_origin = origin if origin is not None else (extracted_origin or '')
        return gnmi_pb2.Path(elem=path_elements, origin=final_origin)

    def _path_to_string(self, path):
        """Convert a `gnmi_pb2.Path` back to a human-readable string."""
        parts = []
        for elem in path.elem:
            if elem.key:
                keys = ','.join(["{0}={1}".format(k, v) for k, v in elem.key.items()])
                parts.append("{0}[{1}]".format(elem.name, keys))
            else:
                parts.append(elem.name)
        return '/' + '/'.join(parts)

    # ------------------------------------------------------------------
    # TypedValue helpers
    # ------------------------------------------------------------------

    def _build_typed_value(self, value):
        """Build a `gnmi_pb2.TypedValue` from a Python object."""
        typed_value = gnmi_pb2.TypedValue()

        if isinstance(value, dict) or isinstance(value, list):
            json_str = json.dumps(value)
            if self.encoding == self.ENCODING_MAP.get('json_ietf', 4):
                typed_value.json_ietf_val = json_str.encode('utf-8')
            else:
                typed_value.json_val = json_str.encode('utf-8')
        elif isinstance(value, bool):
            # bool check MUST come before int (bool is subclass of int)
            typed_value.bool_val = value
        elif isinstance(value, int):
            typed_value.int_val = value
        elif isinstance(value, float):
            typed_value.float_val = value
        elif isinstance(value, bytes):
            typed_value.bytes_val = value
        elif isinstance(value, str):
            typed_value.string_val = value
        else:
            typed_value.string_val = str(value)

        return typed_value

    def _parse_typed_value(self, typed_value):
        """Parse a `gnmi_pb2.TypedValue` into a Python object."""
        if typed_value.HasField('json_ietf_val'):
            return json.loads(typed_value.json_ietf_val)
        elif typed_value.HasField('json_val'):
            return json.loads(typed_value.json_val)
        elif typed_value.HasField('string_val'):
            return typed_value.string_val
        elif typed_value.HasField('int_val'):
            return typed_value.int_val
        elif typed_value.HasField('uint_val'):
            return typed_value.uint_val
        elif typed_value.HasField('bool_val'):
            return typed_value.bool_val
        elif typed_value.HasField('bytes_val'):
            return typed_value.bytes_val
        elif typed_value.HasField('float_val'):
            return typed_value.float_val
        elif typed_value.HasField('decimal_val'):
            return typed_value.decimal_val
        elif typed_value.HasField('leaflist_val'):
            return [self._parse_typed_value(v) for v in typed_value.leaflist_val.element]
        elif typed_value.HasField('any_val'):
            return typed_value.any_val
        return None

    # ------------------------------------------------------------------
    # GET
    # ------------------------------------------------------------------

    def get(self, paths, datatype='all', encoding=None, origin=None):
        """
        Execute a gNMI Get RPC.

        Args:
            paths: List of path strings.
            datatype: One of `all`, `config`, `state`, `operational`.
            encoding: Override the client-level encoding for this request.
            origin: Origin to set on every path (e.g. `rfc7951`).

        Returns:
            `GnmiResult`
        """
        if not self.stub:
            self.connect()

        self._check_encoding_for_op('get')

        try:
            path_objects = [self._build_path(p, origin=origin) for p in paths]

            request = gnmi_pb2.GetRequest(
                path=path_objects,
                type=self._get_datatype(datatype),
                encoding=encoding if encoding is not None else self.encoding,
            )

            response = self.stub.Get(request, metadata=self._metadata, timeout=self.timeout)
            result_data = self._parse_get_response(response)

            return GnmiResult(success=True, data=result_data, error=None, changed=False)

        except grpc.RpcError as exc:
            msg = "gNMI Get failed: {0}: {1}".format(exc.code(), exc.details())
            return GnmiResult(success=False, data=None, error=msg, changed=False)
        except GnmiOperationError:
            raise
        except Exception as exc:
            msg = "gNMI Get failed: {0}".format(exc)
            return GnmiResult(success=False, data=None, error=msg, changed=False)

    def _parse_get_response(self, response):
        """Parse a `GetResponse` into a dictionary keyed by path string."""
        result = {}
        for notification in response.notification:
            for update in notification.update:
                path_str = self._path_to_string(update.path)
                result[path_str] = self._parse_typed_value(update.val)
        return result

    # ------------------------------------------------------------------
    # SET
    # ------------------------------------------------------------------

    def set(self, delete=None, replace=None, update=None, origin=None):
        """
        Execute a gNMI Set RPC.

        Args:
            delete: List of path strings to delete.
            replace: List of `(path, value)` tuples for replace operations.
            update: List of `(path, value)` tuples for update (merge) operations.
            origin: Origin to set on every path (e.g. `rfc7951`).

        Returns:
            `GnmiResult`
        """
        if not self.stub:
            self.connect()

        self._check_encoding_for_op('set')

        try:
            request = gnmi_pb2.SetRequest()

            if delete:
                for path in delete:
                    request.delete.append(self._build_path(path, origin=origin))

            if replace:
                for path, value in replace:
                    update_msg = gnmi_pb2.Update(
                        path=self._build_path(path, origin=origin),
                        val=self._build_typed_value(value),
                    )
                    request.replace.append(update_msg)

            if update:
                for path, value in update:
                    update_msg = gnmi_pb2.Update(
                        path=self._build_path(path, origin=origin),
                        val=self._build_typed_value(value),
                    )
                    request.update.append(update_msg)

            response = self.stub.Set(request, metadata=self._metadata, timeout=self.timeout)
            result_data = self._parse_set_response(response)

            return GnmiResult(success=True, data=result_data, error=None, changed=True)

        except grpc.RpcError as exc:
            msg = "gNMI Set failed: {0}: {1}".format(exc.code(), exc.details())
            return GnmiResult(success=False, data=None, error=msg, changed=False)
        except GnmiOperationError:
            raise
        except Exception as exc:
            msg = "gNMI Set failed: {0}".format(exc)
            return GnmiResult(success=False, data=None, error=msg, changed=False)

    def _parse_set_response(self, response):
        """Parse a `SetResponse` into a dictionary."""
        result = {
            'timestamp': response.timestamp,
            'results': [],
        }
        for update_result in response.response:
            result['results'].append({
                'path': self._path_to_string(update_result.path),
                'op': update_result.op,
            })
        return result

    # ------------------------------------------------------------------
    # SUBSCRIBE
    # ------------------------------------------------------------------

    def subscribe(self, subscriptions, mode='stream', encoding=None,
                  origin=None, callback=None):
        """
        Execute a gNMI Subscribe RPC.

        Args:
            subscriptions: List of `(path, sub_mode, sample_interval)` tuples.
                           `sub_mode`: `target_defined`, `sample`, `on_change`.
                           `sample_interval`: seconds (converted to nanoseconds).
            mode: `stream`, `once`, or `poll`.
            encoding: Override the client-level encoding.
            origin: Origin to set on every path.
            callback: Optional callable invoked for each notification update.

        Returns:
            `GnmiResult`
        """
        if not self.stub:
            self.connect()

        self._check_subscribe_restrictions(mode, subscriptions)

        try:
            sub_list = []
            for path, sub_mode, sample_interval in subscriptions:
                subscription = gnmi_pb2.Subscription(
                    path=self._build_path(path, origin=origin),
                    mode=self._get_subscription_mode(sub_mode),
                    sample_interval=sample_interval * 1000000000,
                )
                sub_list.append(subscription)

            subscription_list = gnmi_pb2.SubscriptionList(
                subscription=sub_list,
                mode=self._get_subscribe_mode(mode),
                encoding=encoding if encoding is not None else self.encoding,
            )

            request = gnmi_pb2.SubscribeRequest(subscribe=subscription_list)
            responses = self.stub.Subscribe(
                iter([request]), metadata=self._metadata, timeout=None)

            updates = []
            for response in responses:
                if response.HasField('update'):
                    update_data = self._parse_notification(response.update)
                    updates.append(update_data)
                    if callback:
                        callback(update_data)

                if response.HasField('sync_response') and mode == 'once':
                    break

            return GnmiResult(
                success=True, data={'updates': updates}, error=None, changed=False)

        except grpc.RpcError as exc:
            msg = "gNMI Subscribe failed: {0}: {1}".format(exc.code(), exc.details())
            return GnmiResult(success=False, data=None, error=msg, changed=False)
        except Exception as exc:
            msg = "gNMI Subscribe failed: {0}".format(exc)
            return GnmiResult(success=False, data=None, error=msg, changed=False)

    @staticmethod
    def _get_subscribe_mode(mode):
        return {'stream': 0, 'once': 1, 'poll': 2}.get(mode.lower(), 0)

    @staticmethod
    def _get_subscription_mode(mode):
        return {'target_defined': 0, 'on_change': 1, 'sample': 2}.get(mode.lower(), 0)

    def _parse_notification(self, notification):
        """Parse a `Notification` protobuf message."""
        result = {
            'timestamp': notification.timestamp,
            'prefix': self._path_to_string(notification.prefix) if notification.prefix else '',
            'updates': [],
        }
        for upd in notification.update:
            result['updates'].append({
                'path': self._path_to_string(upd.path),
                'value': self._parse_typed_value(upd.val),
            })
        for dlt in notification.delete:
            result['updates'].append({
                'path': self._path_to_string(dlt),
                'deleted': True,
            })
        return result

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
