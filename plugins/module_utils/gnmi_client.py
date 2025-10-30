#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright: (c) 2025, John Cohoe <jcohoe@cisco.com>
# Apache License 2.0 (see LICENSE or http://www.apache.org/licenses/LICENSE-2.0)

"""
Cisco IOS XE gNMI Client Implementation

This module implements a gNMI (gRPC Network Management Interface) client
specifically designed for Cisco IOS XE devices with full compliance to
Cisco's gNMI configuration requirements and restrictions.

Official Reference:
    Cisco Programmability Configuration Guide, IOS XE 17.18.x - gNMI Protocol
    https://www.cisco.com/c/en/us/td/docs/ios-xml/ios/prog/configuration/1718/b-1718-programmability-cg/gnmi.html

Key Cisco IOS XE Restrictions:
    - BYTES and ASCII encodings are NOT supported
    - PROTO encoding ONLY works with Subscribe RPC (not GET/SET)
    - JSON_IETF (RFC 7951) is the RECOMMENDED encoding
    - Default secure port: 9339, insecure port: 50052
    - Configuration changes automatically persist (IOS XE 17.3.1+)
    - SetRequest operations are atomic (all or nothing)
    - YANG namespace prefixes required for augmented elements

Platform Support:
    - Cisco IOS XE 16.8.1a+ for basic gNMI (GET/SET)
    - Cisco IOS XE 17.11.1+ for PROTO encoding (Subscribe only)
    - Cisco IOS XE 17.3.1+ for automatic config persistence

For complete documentation of Cisco IOS XE caveats and requirements,
see CISCO_GNMI_CAVEATS.md in the repository root.
"""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

import grpc
import json
import ssl
from typing import Dict, List, Optional, Any, Tuple
from collections import namedtuple

try:
    # Import from local generated proto files
    from . import gnmi_pb2, gnmi_pb2_grpc
    HAS_GNMI = True
    GNMI_IMPORT_ERROR = None
except ImportError as e:
    HAS_GNMI = False
    GNMI_IMPORT_ERROR = str(e)
    # Create dummy classes to prevent errors
    class gnmi_pb2:
        class Path:
            pass
        class PathElem:
            pass
        class GetRequest:
            pass
        class GetResponse:
            pass
        class SetRequest:
            pass
        class SetResponse:
            pass
        class SubscribeRequest:
            pass
        class SubscriptionList:
            pass
        class Subscription:
            pass
        class Encoding:
            JSON_IETF = 4
            PROTO = 2
            JSON = 0
        class DataType:
            ALL = 0
            CONFIG = 1
            STATE = 2
            OPERATIONAL = 3

    class gnmi_pb2_grpc:
        class gNMIStub:
            pass


class GnmiClientError(Exception):
    """Base exception for gNMI client errors"""
    pass


class GnmiConnectionError(GnmiClientError):
    """Exception for connection related errors"""
    pass


class GnmiAuthenticationError(GnmiClientError):
    """Exception for authentication related errors"""
    pass


class GnmiOperationError(GnmiClientError):
    """Exception for operation related errors"""
    pass


GnmiResult = namedtuple('GnmiResult', ['success', 'data', 'error', 'changed'])


class GnmiClient:
    """
    gNMI client for Cisco IOS XE devices

    Provides methods for GET, SET, and Subscribe operations over gRPC
    """

    # Encoding support per Cisco IOS XE gNMI documentation
    # NOTE: BYTES (1) and ASCII (3) are NOT supported on Cisco IOS XE
    # PROTO (2) supported from IOS XE Dublin 17.11.1+
    # JSON_IETF (4) is recommended for Cisco IOS XE
    ENCODING_MAP = {
        'json': 0,        # JSON encoding - supported
        # 'bytes': 1,     # NOT supported on Cisco IOS XE
        'proto': 2,       # Supported from IOS XE 17.11.1+ (Subscribe RPC only)
        # 'ascii': 3,     # NOT supported on Cisco IOS XE
        'json_ietf': 4,   # JSON IETF (RFC 7951) - RECOMMENDED
    }

    DATATYPE_MAP = {
        'all': 0,
        'config': 1,
        'state': 2,
        'operational': 3,
    }

    def __init__(self,
                 host: str,
                 port: int = 9339,
                 username: str = None,
                 password: str = None,
                 encoding: str = 'json_ietf',
                 timeout: int = 30,
                 insecure: bool = False,
                 ca_cert: str = None,
                 client_cert: str = None,
                 client_key: str = None):
        """
        Initialize gNMI client for Cisco IOS XE devices

        Args:
            host: Target device hostname or IP
            port: gNMI port (default: 9339 for secure, 50052 for insecure)
            username: Authentication username (passed as metadata)
            password: Authentication password (passed as metadata)
            encoding: Data encoding (json_ietf recommended, json, proto)
            timeout: Connection timeout in seconds
            insecure: Skip TLS certificate validation (not recommended for production)
            ca_cert: Path to CA certificate (rootCA.pem)
            client_cert: Path to client certificate for mutual TLS
            client_key: Path to client private key for mutual TLS

        Notes:
            - BYTES and ASCII encoding NOT supported on Cisco IOS XE
            - PROTO encoding only for Subscribe RPC (IOS XE 17.11.1+)
            - JSON_IETF (RFC 7951) is the recommended encoding
            - Default secure port is 9339, insecure port is 50052
            - Configuration persistence enabled by default (IOS XE 17.3.1+)
        """
        if not HAS_GNMI:
            raise GnmiClientError(
                f"gNMI libraries not available. Install with 'pip install grpcio grpcio-tools'. Error: {GNMI_IMPORT_ERROR}"
            )

        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.encoding = self._get_encoding(encoding)
        self.timeout = timeout
        self.insecure = insecure
        self.ca_cert = ca_cert
        self.client_cert = client_cert
        self.client_key = client_key

        self.channel = None
        self.stub = None
        self._metadata = None

        # Validate configuration against Cisco IOS XE restrictions
        self._validate_cisco_config()

    def _validate_cisco_config(self) -> None:
        """
        Validate configuration against Cisco IOS XE gNMI restrictions

        Raises:
            GnmiClientError: If configuration violates Cisco IOS XE restrictions
        """
        # Validate encoding is supported
        encoding_lower = self.encoding if isinstance(self.encoding, int) else str(self.encoding).lower()

        if not isinstance(self.encoding, int):
            # Check that encoding string is valid
            if encoding_lower not in self.ENCODING_MAP:
                valid_encodings = list(self.ENCODING_MAP.keys())
                raise GnmiClientError(
                    f"Invalid encoding '{self.encoding}'. "
                    f"Cisco IOS XE supports: {valid_encodings}. "
                    f"Note: BYTES and ASCII are NOT supported."
                )

        # Warn about PROTO encoding limitation
        if (isinstance(self.encoding, int) and self.encoding == 2) or encoding_lower == 'proto':
            # PROTO only supported for Subscribe RPC, not GET/SET
            pass  # Warning will be issued when GET/SET is attempted with PROTO

        # Validate port number
        if self.port and (self.port < 1 or self.port > 65535):
            raise GnmiClientError(f"Invalid port number: {self.port}")

        # Check for recommended configuration
        if self.port == 9339 and self.insecure:
            # User specified secure port with insecure mode - may be unintentional
            pass  # This is allowed but unusual

        if self.port == 50052 and not self.insecure:
            # User specified insecure port with secure mode - may be unintentional
            pass  # This is allowed but unusual

    def _get_encoding(self, encoding: str) -> int:
        """
        Convert encoding string to gNMI encoding value

        Raises:
            GnmiClientError: If encoding is not supported on Cisco IOS XE
        """
        encoding_lower = encoding.lower()
        if encoding_lower not in self.ENCODING_MAP:
            raise GnmiClientError(
                f"Invalid encoding: {encoding}. Valid options: {list(self.ENCODING_MAP.keys())}. "
                f"Note: BYTES and ASCII encodings are NOT supported on Cisco IOS XE."
            )
        return self.ENCODING_MAP[encoding_lower]

    def _get_datatype(self, datatype: str) -> int:
        """Convert datatype string to gNMI datatype value"""
        datatype_lower = datatype.lower()
        if datatype_lower not in self.DATATYPE_MAP:
            raise GnmiClientError(
                f"Invalid datatype: {datatype}. Valid options: {list(self.DATATYPE_MAP.keys())}"
            )
        return self.DATATYPE_MAP[datatype_lower]

    def connect(self) -> None:
        """Establish gRPC channel and create stub"""
        try:
            target = f"{self.host}:{self.port}"

            # Set up credentials
            if self.insecure:
                # For insecure mode with self-signed certificates (like Cisco IOS XE default)
                # Set environment variable to disable certificate verification
                import os
                os.environ['GRPC_DEFAULT_SSL_ROOTS_FILE_PATH'] = ''

                # Create SSL credentials without root certificate verification
                credentials = grpc.ssl_channel_credentials()
                self.channel = grpc.secure_channel(
                    target,
                    credentials,
                    options=[
                        ('grpc.ssl_target_name_override', self.host),
                    ]
                )
            else:
                # Load certificates
                ca_cert_data = None
                client_cert_data = None
                client_key_data = None

                if self.ca_cert:
                    with open(self.ca_cert, 'rb') as f:
                        ca_cert_data = f.read()

                if self.client_cert and self.client_key:
                    with open(self.client_cert, 'rb') as f:
                        client_cert_data = f.read()
                    with open(self.client_key, 'rb') as f:
                        client_key_data = f.read()

                credentials = grpc.ssl_channel_credentials(
                    root_certificates=ca_cert_data,
                    private_key=client_key_data,
                    certificate_chain=client_cert_data
                )

                # If using custom CA cert, we may need to override the target name
                # to match the certificate's CN instead of the IP address
                options = []
                if ca_cert_data:
                    # Extract CN from the certificate
                    try:
                        from cryptography import x509
                        from cryptography.hazmat.backends import default_backend
                        cert = x509.load_pem_x509_certificate(ca_cert_data, default_backend())
                        # Get the subject CN
                        for attr in cert.subject:
                            if attr.oid == x509.oid.NameOID.COMMON_NAME:
                                cert_cn = attr.value
                                options.append(('grpc.ssl_target_name_override', cert_cn))
                                break
                    except:
                        # If cryptography is not available, try simple regex extraction
                        import re
                        cert_text = ca_cert_data.decode('utf-8')
                        # This won't work with PEM - skip for now
                        pass

                self.channel = grpc.secure_channel(target, credentials, options=options if options else None)

            self.stub = gnmi_pb2_grpc.gNMIStub(self.channel)

            # Set up metadata for authentication
            if self.username and self.password:
                self._metadata = [
                    ('username', self.username),
                    ('password', self.password)
                ]

        except Exception as e:
            raise GnmiConnectionError(f"Failed to connect to {self.host}:{self.port}: {str(e)}")

    def disconnect(self) -> None:
        """Close gRPC channel"""
        if self.channel:
            self.channel.close()
            self.channel = None
            self.stub = None

    def _build_path(self, path: str, origin: str = None) -> 'gnmi_pb2.Path':
        """
        Build gNMI Path from string with optional origin

        Args:
            path: Path string (e.g., '/interfaces/interface[name=GigabitEthernet1]/config')
                  Can include origin prefix like 'Cisco-IOS-XE-memory-oper:memory-statistics'
            origin: Origin string (e.g., 'rfc7951' for Cisco native, 'openconfig' for OpenConfig)
                    If not provided, will be extracted from path if present

        Returns:
            gnmi_pb2.Path object with origin set appropriately

        Note:
            - Cisco native YANG models (Cisco-IOS-XE-*) should use origin='rfc7951'
            - OpenConfig models typically use origin='openconfig' or no origin
            - The origin can be specified in the path with prefix (e.g., 'Cisco-IOS-XE-memory-oper:path')
              or passed explicitly via the origin parameter
        """
        path_elements = []
        extracted_origin = None

        # Remove leading slash
        if path.startswith('/'):
            path = path[1:]

        # Check if first element has a namespace prefix (e.g., 'Cisco-IOS-XE-memory-oper:memory-statistics')
        # This indicates we should use rfc7951 origin
        first_elem = path.split('/')[0] if '/' in path else path
        if ':' in first_elem and not '[' in first_elem.split(':')[0]:
            # Has namespace prefix - extract it
            prefix_part = first_elem.split(':')[0]
            if prefix_part.startswith('Cisco-IOS-XE-') or prefix_part.startswith('Cisco-IOS-'):
                extracted_origin = 'rfc7951'
                # Keep the prefix in the element name as per Cisco requirements
            elif 'openconfig' in prefix_part.lower():
                extracted_origin = 'openconfig'
                # Keep the prefix in the element name

        # Split by '/' and process each element
        for element in path.split('/'):
            if not element:
                continue

            # Check for keys in brackets
            if '[' in element and ']' in element:
                # Extract name and keys
                name_part = element[:element.index('[')]
                keys_part = element[element.index('['):].strip('[]')

                keys = {}
                # Parse key-value pairs
                for kv in keys_part.split(']['):
                    if '=' in kv:
                        k, v = kv.split('=', 1)
                        keys[k] = v

                path_elements.append(
                    gnmi_pb2.PathElem(name=name_part, key=keys)
                )
            else:
                path_elements.append(
                    gnmi_pb2.PathElem(name=element)
                )

        # Use explicitly passed origin, or fall back to extracted origin, or empty string
        final_origin = origin if origin is not None else (extracted_origin if extracted_origin else '')

        return gnmi_pb2.Path(elem=path_elements, origin=final_origin)

    def get(self,
            paths: List[str],
            datatype: str = 'all',
            encoding: Optional[int] = None,
            origin: Optional[str] = None) -> GnmiResult:
        """
        Execute gNMI Get operation (Cisco IOS XE)

        Args:
            paths: List of paths to retrieve
            datatype: Type of data (all, config, state, operational)
            encoding: Override default encoding
            origin: Origin for gNMI paths (e.g., 'rfc7951' for Cisco native, 'openconfig')

        Returns:
            GnmiResult with success status and data

        Note:
            - PROTO encoding is NOT supported for GET RPC on Cisco IOS XE
            - Use JSON_IETF encoding for GET operations
            - Operational data filtering is not supported
            - Use models are not supported
            - For Cisco native YANG models (Cisco-IOS-XE-*), use origin='rfc7951'
            - For OpenConfig models, use origin='openconfig'
            - For IETF models, use empty string origin='' or omit (default)

        Raises:
            GnmiOperationError: If PROTO encoding is used for GET
        """
        if not self.stub:
            self.connect()

        # Validate encoding for GET operation
        encoding_to_use = encoding if encoding is not None else self.encoding
        if encoding_to_use == 2:  # PROTO encoding
            raise GnmiOperationError(
                "PROTO encoding is NOT supported for GET operations on Cisco IOS XE. "
                "PROTO encoding only works with Subscribe RPC. "
                "Please use JSON_IETF or JSON encoding instead."
            )

        try:
            # Build path objects with origin support
            path_objects = [self._build_path(p, origin=origin) for p in paths]

            # Create GetRequest
            request = gnmi_pb2.GetRequest(
                path=path_objects,
                type=self._get_datatype(datatype),
                encoding=encoding if encoding is not None else self.encoding
            )

            # Execute request
            response = self.stub.Get(request, metadata=self._metadata, timeout=self.timeout)

            # Parse response
            result_data = self._parse_get_response(response)

            return GnmiResult(
                success=True,
                data=result_data,
                error=None,
                changed=False
            )

        except grpc.RpcError as e:
            error_msg = f"gNMI Get failed: {e.code()}: {e.details()}"
            return GnmiResult(
                success=False,
                data=None,
                error=error_msg,
                changed=False
            )
        except Exception as e:
            error_msg = f"gNMI Get failed: {str(e)}"
            return GnmiResult(
                success=False,
                data=None,
                error=error_msg,
                changed=False
            )

    def _parse_get_response(self, response: 'gnmi_pb2.GetResponse') -> Dict[str, Any]:
        """Parse GetResponse into dictionary"""
        result = {}

        for notification in response.notification:
            for update in notification.update:
                path_str = self._path_to_string(update.path)
                value = self._parse_typed_value(update.val)
                result[path_str] = value

        return result

    def _path_to_string(self, path: 'gnmi_pb2.Path') -> str:
        """Convert gNMI Path to string representation"""
        parts = []
        for elem in path.elem:
            if elem.key:
                keys = ','.join([f"{k}={v}" for k, v in elem.key.items()])
                parts.append(f"{elem.name}[{keys}]")
            else:
                parts.append(elem.name)
        return '/' + '/'.join(parts)

    def _parse_typed_value(self, typed_value: Any) -> Any:
        """Parse gNMI TypedValue to Python object"""
        if typed_value.HasField('json_val'):
            return json.loads(typed_value.json_val)
        elif typed_value.HasField('json_ietf_val'):
            return json.loads(typed_value.json_ietf_val)
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
        else:
            return None

    def set(self,
            delete: Optional[List[str]] = None,
            replace: Optional[List[Tuple[str, Any]]] = None,
            update: Optional[List[Tuple[str, Any]]] = None) -> GnmiResult:
        """
        Execute gNMI Set operation (Cisco IOS XE)

        Args:
            delete: List of paths to delete
            replace: List of (path, value) tuples to replace
            update: List of (path, value) tuples to update

        Returns:
            GnmiResult with success status and data

        Note:
            - PROTO encoding is NOT supported for SET RPC on Cisco IOS XE
            - All successful SetRequest changes persist across device restarts (IOS XE 17.3.1+)
            - Configuration automatically saved to startup-config
            - JSON_IETF keys must use YANG prefix when namespace differs from parent
              Example: Use 'oc-vlan:routed-vlan' for augmented elements
            - SetRequest operates as a single transaction (all or nothing)

        Raises:
            GnmiOperationError: If PROTO encoding is used for SET
        """
        if not self.stub:
            self.connect()

        # Validate encoding for SET operation
        if self.encoding == 2:  # PROTO encoding
            raise GnmiOperationError(
                "PROTO encoding is NOT supported for SET operations on Cisco IOS XE. "
                "PROTO encoding only works with Subscribe RPC. "
                "Please use JSON_IETF or JSON encoding instead."
            )

        try:
            request = gnmi_pb2.SetRequest()

            # Add delete operations
            if delete:
                for path in delete:
                    request.delete.append(self._build_path(path))

            # Add replace operations
            if replace:
                for path, value in replace:
                    update_msg = gnmi_pb2.Update(
                        path=self._build_path(path),
                        val=self._build_typed_value(value)
                    )
                    request.replace.append(update_msg)

            # Add update operations
            if update:
                for path, value in update:
                    update_msg = gnmi_pb2.Update(
                        path=self._build_path(path),
                        val=self._build_typed_value(value)
                    )
                    request.update.append(update_msg)

            # Execute request
            response = self.stub.Set(request, metadata=self._metadata, timeout=self.timeout)

            # Parse response
            result_data = self._parse_set_response(response)

            return GnmiResult(
                success=True,
                data=result_data,
                error=None,
                changed=True
            )

        except grpc.RpcError as e:
            error_msg = f"gNMI Set failed: {e.code()}: {e.details()}"
            return GnmiResult(
                success=False,
                data=None,
                error=error_msg,
                changed=False
            )
        except Exception as e:
            error_msg = f"gNMI Set failed: {str(e)}"
            return GnmiResult(
                success=False,
                data=None,
                error=error_msg,
                changed=False
            )

    def _build_typed_value(self, value: Any) -> Any:
        """Build gNMI TypedValue from Python object"""
        typed_value = gnmi_pb2.TypedValue()

        if isinstance(value, dict) or isinstance(value, list):
            # Use JSON encoding
            json_str = json.dumps(value)
            if self.encoding == self.ENCODING_MAP['json_ietf']:
                typed_value.json_ietf_val = json_str.encode('utf-8')
            else:
                typed_value.json_val = json_str.encode('utf-8')
        elif isinstance(value, str):
            typed_value.string_val = value
        elif isinstance(value, bool):
            typed_value.bool_val = value
        elif isinstance(value, int):
            typed_value.int_val = value
        elif isinstance(value, float):
            typed_value.float_val = value
        elif isinstance(value, bytes):
            typed_value.bytes_val = value
        else:
            # Default to string representation
            typed_value.string_val = str(value)

        return typed_value

    def _parse_set_response(self, response: 'gnmi_pb2.SetResponse') -> Dict[str, Any]:
        """Parse SetResponse into dictionary"""
        result = {
            'timestamp': response.timestamp,
            'results': []
        }

        for update_result in response.response:
            result['results'].append({
                'path': self._path_to_string(update_result.path),
                'op': update_result.op,
            })

        return result

    def subscribe(self,
                  subscriptions: List[Tuple[str, str, int]],
                  mode: str = 'stream',
                  encoding: Optional[int] = None,
                  callback=None) -> GnmiResult:
        """
        Execute gNMI Subscribe operation

        Args:
            subscriptions: List of (path, mode, sample_interval) tuples
                          mode can be: 'target_defined', 'sample', 'on_change'
            mode: Subscription mode ('stream', 'once', 'poll')
            encoding: Override default encoding
            callback: Function to call for each update

        Returns:
            GnmiResult with success status
        """
        if not self.stub:
            self.connect()

        try:
            # Build subscription list
            sub_list = []
            for path, sub_mode, sample_interval in subscriptions:
                subscription = gnmi_pb2.Subscription(
                    path=self._build_path(path),
                    mode=self._get_subscription_mode(sub_mode),
                    sample_interval=sample_interval * 1000000000  # Convert to nanoseconds
                )
                sub_list.append(subscription)

            # Create SubscriptionList
            subscription_list = gnmi_pb2.SubscriptionList(
                subscription=sub_list,
                mode=self._get_subscribe_mode(mode),
                encoding=encoding if encoding is not None else self.encoding
            )

            # Create SubscribeRequest
            request = gnmi_pb2.SubscribeRequest(subscribe=subscription_list)

            # Execute streaming request
            responses = self.stub.Subscribe([request], metadata=self._metadata, timeout=None)

            updates = []
            for response in responses:
                if response.HasField('update'):
                    update_data = self._parse_notification(response.update)
                    updates.append(update_data)

                    if callback:
                        callback(update_data)

                # Stop after sync_response for 'once' mode
                if response.HasField('sync_response') and mode == 'once':
                    break

            return GnmiResult(
                success=True,
                data={'updates': updates},
                error=None,
                changed=False
            )

        except grpc.RpcError as e:
            error_msg = f"gNMI Subscribe failed: {e.code()}: {e.details()}"
            return GnmiResult(
                success=False,
                data=None,
                error=error_msg,
                changed=False
            )
        except Exception as e:
            error_msg = f"gNMI Subscribe failed: {str(e)}"
            return GnmiResult(
                success=False,
                data=None,
                error=error_msg,
                changed=False
            )

    def _get_subscribe_mode(self, mode: str) -> int:
        """Convert subscribe mode string to gNMI value"""
        modes = {
            'stream': 0,
            'once': 1,
            'poll': 2
        }
        return modes.get(mode.lower(), 0)

    def _get_subscription_mode(self, mode: str) -> int:
        """Convert subscription mode string to gNMI value"""
        modes = {
            'target_defined': 0,
            'sample': 2,
            'on_change': 1
        }
        return modes.get(mode.lower(), 0)

    def _parse_notification(self, notification: Any) -> Dict[str, Any]:
        """Parse Notification message"""
        result = {
            'timestamp': notification.timestamp,
            'prefix': self._path_to_string(notification.prefix) if notification.prefix else '',
            'updates': []
        }

        for update in notification.update:
            result['updates'].append({
                'path': self._path_to_string(update.path),
                'value': self._parse_typed_value(update.val)
            })

        for delete in notification.delete:
            result['updates'].append({
                'path': self._path_to_string(delete),
                'deleted': True
            })

        return result

    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()
