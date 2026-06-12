#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2025 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""
gNMI Client Implementation for Cisco Network Devices

This module implements a gNMI (gRPC Network Management Interface) client
for Cisco network devices:

    - Cisco IOS XE (default port 9339)
    - Cisco IOS XR (default port 57400)
    - Cisco NX-OS (default port 50051)

gNMI Specification Reference:
    https://github.com/openconfig/reference/blob/master/rpc/gnmi/gnmi-specification.md

Platform-specific notes are documented in PLATFORM_NOTES.md.
"""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

import grpc
import json
import logging
import socket
import ssl
from collections import namedtuple

try:
    from cryptography import x509
    from cryptography.hazmat.backends import default_backend
    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False

try:
    # Import from local generated proto files
    from . import gnmi_pb2, gnmi_pb2_grpc
    HAS_GNMI = True
    GNMI_IMPORT_ERROR = None
except ImportError as e:
    HAS_GNMI = False
    GNMI_IMPORT_ERROR = str(e)

    # Create minimal dummy classes to prevent import errors
    class gnmi_pb2:
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

        class CapabilityRequest:
            pass

        class CapabilityResponse:
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
        'bytes': 1,
        'proto': 2,
        'ascii': 3,
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
                 token=None,
                 encoding='json_ietf',
                 timeout=30,
                 insecure=False,
                 ca_cert=None,
                 client_cert=None,
                 client_key=None,
                 platform='auto',
                 tls_server_name=None,
                 tls_skip_verify=False,
                 max_message_length=None,
                 channel_options=None,
                 warn_callback=None):
        """
        Initialise gNMI client.

        Args:
            host: Target device hostname or IP.
            port: gNMI port number.
            username: Authentication username (sent as gRPC metadata).
            password: Authentication password (sent as gRPC metadata).
            token: Bearer token; sent as ``authorization: Bearer <token>``
                metadata. When set, takes precedence over username/password.
            encoding: Data encoding - one of ``json_ietf`` (default), ``json``,
                ``proto``, ``bytes``, ``ascii``.
            timeout: Connection / RPC timeout in seconds.
            insecure: When *True*, use a plaintext gRPC channel (no TLS).
                Only works against the device's insecure port.
            ca_cert: Path to CA certificate file.
            client_cert: Path to client certificate for mutual TLS.
            client_key: Path to client private key for mutual TLS.
            platform: Optional platform hint (`auto`, `iosxe`, `iosxr`, `nxos`).
                       `auto` applies no restrictions.
            tls_server_name: Override the TLS server name presented during
                handshake (``grpc.ssl_target_name_override``). Useful when the
                cert SAN/CN doesn't match the connect address.
            tls_skip_verify: When *True* and no ``ca_cert`` is given, establish
                a TLS (encrypted) channel but trust whatever certificate the
                device presents (Trust-On-First-Use), without verifying it
                against a CA. Equivalent to ``gnmic --skip-verify``. The channel
                is encrypted but the server identity is not authenticated.
            max_message_length: Maximum inbound gRPC message size in bytes.
                Defaults to gRPC's 4 MB; raise for devices that return very
                large GetResponses (e.g. full-tree dumps).
            channel_options: Optional dict of additional gRPC channel options
                merged into the channel construction (e.g.
                ``{'grpc.keepalive_time_ms': 30000}``).
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
        self.token = token
        self.encoding = self._resolve_encoding(encoding)
        self.encoding_name = encoding.lower() if isinstance(encoding, str) else encoding
        self.timeout = timeout
        self.insecure = insecure
        self.ca_cert = ca_cert
        self.client_cert = client_cert
        self.client_key = client_key
        self.platform = platform.lower() if platform else 'auto'
        self.tls_server_name = tls_server_name
        self.tls_skip_verify = tls_skip_verify
        self.max_message_length = max_message_length
        self.channel_options = channel_options or {}
        self._warn = warn_callback or logger.warning

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
                        "is not supported on {plat} and will be sent to the "
                        "device as-is; the device is expected to reject it.  "
                        "Supported modes: {allowed}.".format(
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
            extra_options = self._build_channel_options()

            if self.insecure:
                # Plaintext gRPC channel - no TLS, no certificate verification.
                # Used for lab/test environments where the gNMI server is
                # configured without TLS. Do NOT use in production.
                self.channel = grpc.insecure_channel(
                    target,
                    options=extra_options if extra_options else None,
                )
            else:
                ca_cert_data = self._read_cert_file(self.ca_cert, 'ca_cert') if self.ca_cert else None
                client_cert_data = None
                client_key_data = None

                # Trust-On-First-Use: when no CA is pinned and the caller has
                # opted in to tls_skip_verify, fetch the certificate the server
                # presents and trust it for this session. The channel is still
                # encrypted; the server identity is simply not verified against
                # a known CA (equivalent to gnmic's --skip-verify).
                if ca_cert_data is None and self.tls_skip_verify:
                    ca_cert_data = self._fetch_server_certificate()
                    self._warn(
                        "tls_skip_verify is enabled: trusting the certificate "
                        "presented by {0}:{1} without CA verification (TOFU). "
                        "The channel is encrypted but the server identity is "
                        "NOT validated.".format(self.host, self.port))

                if self.client_cert and self.client_key:
                    client_cert_data = self._read_cert_file(self.client_cert, 'client_cert')
                    client_key_data = self._read_cert_file(self.client_key, 'client_key')

                credentials = grpc.ssl_channel_credentials(
                    root_certificates=ca_cert_data,
                    private_key=client_key_data,
                    certificate_chain=client_cert_data,
                )

                options = list(extra_options)

                # Explicit override wins over CA-cert CN auto-detection.
                if self.tls_server_name:
                    options.append(('grpc.ssl_target_name_override', self.tls_server_name))
                elif ca_cert_data and HAS_CRYPTOGRAPHY:
                    try:
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
            self._metadata = self._build_metadata()

        except GnmiConnectionError:
            # Already a well-formed error from _read_cert_file or similar;
            # re-raise without wrapping so the user sees the specific cause.
            raise
        except Exception as exc:
            raise GnmiConnectionError(
                "Failed to connect to {0}:{1}: {2}".format(self.host, self.port, exc))

    def _build_channel_options(self):
        """Merge ``max_message_length`` + ``channel_options`` into a tuple list."""
        opts = []
        if self.max_message_length:
            opts.append(('grpc.max_receive_message_length', int(self.max_message_length)))
            opts.append(('grpc.max_send_message_length', int(self.max_message_length)))
        for key, value in self.channel_options.items():
            opts.append((key, value))
        return opts

    def _build_metadata(self):
        """Construct the gRPC metadata sent with every RPC.

        Bearer token takes precedence; otherwise fall back to the legacy
        ``username``/``password`` headers expected by Cisco gNMI servers.
        """
        if self.token:
            return [('authorization', 'Bearer {0}'.format(self.token))]
        if self.username and self.password:
            return [('username', self.username), ('password', self.password)]
        return None

    @staticmethod
    def _read_cert_file(path, label):
        """Read a PEM file, raising GnmiConnectionError with clear context on failure."""
        try:
            with open(path, 'rb') as fh:
                return fh.read()
        except FileNotFoundError:
            raise GnmiConnectionError(
                "{0} file not found: {1}".format(label, path))
        except PermissionError:
            raise GnmiConnectionError(
                "{0} file not readable (permission denied): {1}".format(label, path))
        except OSError as exc:
            raise GnmiConnectionError(
                "Failed to read {0} file '{1}': {2}".format(label, path, exc))

    def _fetch_server_certificate(self):
        """Fetch the server's leaf certificate without verification (TOFU).

        Opens a throwaway TLS connection with verification disabled, reads the
        certificate the server presents, and returns it as PEM bytes so it can
        be used as the root of trust for the real gRPC channel. This provides
        the same practical behaviour as gnmic's ``--skip-verify`` (the channel
        is encrypted, but the server identity is not checked against a known
        CA) while staying within what Python's gRPC stack allows.
        """
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        try:
            with socket.create_connection(
                    (self.host, int(self.port)), timeout=self.timeout) as sock:
                with context.wrap_socket(sock, server_hostname=None) as tls_sock:
                    der_cert = tls_sock.getpeercert(binary_form=True)
        except (OSError, ssl.SSLError) as exc:
            raise GnmiConnectionError(
                "tls_skip_verify: failed to fetch certificate from "
                "{0}:{1}: {2}".format(self.host, self.port, exc))

        if not der_cert:
            raise GnmiConnectionError(
                "tls_skip_verify: server {0}:{1} did not present a "
                "certificate.".format(self.host, self.port))

        return ssl.DER_cert_to_PEM_cert(der_cert).encode('ascii')

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

        The *origin* parameter takes precedence.  If not provided, two
        forms of in-path origin are recognised:

          1. ``ORIGIN:/path/...`` — explicit ``origin:`` prefix at the
             start of the string (gnmic / pygnmi convention). The
             ``ORIGIN:`` prefix is stripped and used as the path's
             ``origin`` field.
          2. Auto-detection from well-known YANG namespace prefixes in
             the first path element (e.g. ``Cisco-IOS-XE-*``,
             ``openconfig-*``).

        Args:
            path: Path string, e.g. ``/interfaces/interface[name=Gi1]/config``
                or ``openconfig:/interfaces`` or ``native:/Cisco-IOS-XE-native``.
            origin: Explicit origin (``rfc7951``, ``openconfig``, ...).
                Overrides any in-path origin prefix.

        Returns:
            `gnmi_pb2.Path`
        """
        path_elements = []
        extracted_origin = None

        # Form 1: explicit ``origin:/path`` prefix. Only match short
        # identifier-like origin names followed by ``:/`` to avoid
        # eating YANG namespace prefixes like ``openconfig-interfaces:``.
        prefix_origin = self._split_origin_prefix(path)
        if prefix_origin is not None:
            extracted_origin, path = prefix_origin

        if path.startswith('/'):
            path = path[1:]

        # Form 2: auto-detect origin from a YANG namespace prefix on the
        # first element (only when no explicit origin was given anywhere).
        if extracted_origin is None:
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

    @staticmethod
    def _split_origin_prefix(path):
        """Detect a leading ``ORIGIN:/`` prefix in *path*.

        Returns a ``(origin, remaining_path)`` tuple if found, else None.
        Only identifier-shaped origins (letters/digits/underscore/dash)
        immediately followed by ``:/`` are recognised so that YANG
        namespace prefixes (``openconfig-interfaces:interfaces``) are
        left untouched.
        """
        # Look for ``foo:/`` at the very start, where ``foo`` is a single
        # token containing no slashes or brackets.
        idx = path.find(':/')
        if idx <= 0:
            return None
        candidate = path[:idx]
        if '/' in candidate or '[' in candidate:
            return None
        if not all(c.isalnum() or c in ('-', '_') for c in candidate):
            return None
        return candidate, path[idx + 1:]

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
    # CAPABILITIES
    # ------------------------------------------------------------------

    def capabilities(self):
        """
        Execute a gNMI Capabilities RPC.

        Returns:
            `GnmiResult` whose ``data`` is a dict::

                {
                    'gnmi_version': str,
                    'supported_encodings': [str, ...],   # e.g. ['JSON_IETF', 'PROTO']
                    'supported_models': [
                        {'name': str, 'organization': str, 'version': str},
                        ...
                    ],
                }
        """
        if not self.stub:
            self.connect()

        try:
            request = gnmi_pb2.CapabilityRequest()
            response = self.stub.Capabilities(
                request, metadata=self._metadata, timeout=self.timeout)

            # Map encoding enum ints back to their string names so callers
            # don't have to know about the protobuf enum.
            encoding_names = {
                v: k for k, v in vars(gnmi_pb2.Encoding).items()
                if isinstance(v, int) and not k.startswith('_')
            }
            supported_encodings = [
                encoding_names.get(e, str(e)) for e in response.supported_encodings
            ]

            supported_models = [
                {
                    'name': m.name,
                    'organization': m.organization,
                    'version': m.version,
                }
                for m in response.supported_models
            ]

            data = {
                'gnmi_version': response.gNMI_version,
                'supported_encodings': supported_encodings,
                'supported_models': supported_models,
            }
            return GnmiResult(success=True, data=data, error=None, changed=False)

        except grpc.RpcError as exc:
            msg = "gNMI Capabilities failed: {0}: {1}".format(exc.code(), exc.details())
            return GnmiResult(success=False, data=None, error=msg, changed=False)
        except Exception as exc:
            msg = "gNMI Capabilities failed: {0}".format(exc)
            return GnmiResult(success=False, data=None, error=msg, changed=False)

    # ------------------------------------------------------------------
    # GET
    # ------------------------------------------------------------------

    def get(self, paths, datatype='all', encoding=None, origin=None, prefix=None):
        """
        Execute a gNMI Get RPC.

        Args:
            paths: List of path strings.
            datatype: One of `all`, `config`, `state`, `operational`.
            encoding: Override the client-level encoding for this request.
            origin: Origin to set on every path (e.g. `rfc7951`).
            prefix: Optional path string used as the request ``prefix``.
                Each entry in *paths* is then resolved relative to this
                prefix, which can dramatically reduce on-the-wire size
                when fetching many siblings under a common parent.

        Returns:
            `GnmiResult`
        """
        if not self.stub:
            self.connect()

        self._check_encoding_for_op('get')

        try:
            path_objects = [self._build_path(p, origin=origin) for p in paths]

            request_kwargs = dict(
                path=path_objects,
                type=self._get_datatype(datatype),
                encoding=encoding if encoding is not None else self.encoding,
            )
            if prefix:
                request_kwargs['prefix'] = self._build_path(prefix, origin=origin)

            request = gnmi_pb2.GetRequest(**request_kwargs)

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
                  origin=None, callback=None, duration=None):
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
            duration: Maximum duration in seconds for stream subscriptions.
                      Defaults to ``None`` (no timeout for ``once``/``poll``,
                      uses value as gRPC deadline for ``stream``).

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

            # Use duration as the gRPC deadline for stream subscriptions.
            # For 'once' and 'poll' modes the server signals completion, so
            # a deadline is not strictly necessary but still honoured if set.
            timeout = duration if duration else None

            responses = self.stub.Subscribe(
                iter([request]), metadata=self._metadata, timeout=timeout)

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
