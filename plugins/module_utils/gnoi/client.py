# -*- coding: utf-8 -*-

# Copyright 2025 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""gNOI client transport for Cisco network devices.

This client reuses the same gRPC transport and authentication model as the
collection's gNMI client (:mod:`...gnmi_client`): plaintext, TLS, or mutual
TLS channels, an optional ``tls_server_name`` override, configurable message
size limits, and username/password or bearer-token metadata.

On Cisco IOS XE, gNOI is served on the same gRPC endpoint as gNMI (default
port 9339), so the connection arguments are identical.

The gNOI specification is a suite of microservices. This client binds the
service stubs that Cisco IOS XE supports today:

    - gnoi.certificate.CertificateManagement  (cert.proto)
    - gnoi.os.OS                               (os.proto)
    - gnoi.factory_reset.FactoryReset          (factory_reset.proto)
"""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

import logging
import socket
import ssl

import grpc

try:
    from cryptography import x509
    from cryptography.hazmat.backends import default_backend
    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False

try:
    from .protos import (
        cert_pb2_grpc,
        os_pb2_grpc,
        factory_reset_pb2_grpc,
    )
    HAS_GNOI = True
    GNOI_IMPORT_ERROR = None
except ImportError as exc:  # pragma: no cover - exercised only without stubs
    HAS_GNOI = False
    GNOI_IMPORT_ERROR = str(exc)
    cert_pb2_grpc = None
    os_pb2_grpc = None
    factory_reset_pb2_grpc = None


logger = logging.getLogger(__name__)


class GnoiClientError(Exception):
    """Base exception for gNOI client errors."""


class GnoiConnectionError(GnoiClientError):
    """Connection or TLS setup failed."""


class GnoiAuthenticationError(GnoiClientError):
    """Authentication-related failure."""


class GnoiOperationError(GnoiClientError):
    """A gNOI RPC failed.

    ``grpc_code`` and ``grpc_message`` carry the normalised gRPC status so the
    module layer can surface them in a consistent Ansible result.
    """

    def __init__(self, message, grpc_code=None, grpc_message=None):
        super(GnoiOperationError, self).__init__(message)
        self.grpc_code = grpc_code
        self.grpc_message = grpc_message


def rpc_error_to_operation_error(exc, service, operation):
    """Translate a ``grpc.RpcError`` into a :class:`GnoiOperationError`.

    Keeps the normalised gRPC status code (e.g. ``UNIMPLEMENTED``) and the
    server-supplied details so callers can return a consistent result.
    """
    code = None
    details = None
    try:
        code = exc.code().name if exc.code() is not None else None
    except Exception:  # pragma: no cover - defensive
        code = None
    try:
        details = exc.details()
    except Exception:  # pragma: no cover - defensive
        details = None

    message = "gNOI {0}/{1} failed".format(service, operation)
    if code:
        message += " ({0})".format(code)
    if details:
        message += ": {0}".format(details)
    return GnoiOperationError(message, grpc_code=code, grpc_message=details)


class GnoiClient:
    """gNOI client that exposes the IOS XE-supported service stubs.

    The transport configuration mirrors the collection's gNMI client so that
    the same connection arguments work for both gNMI and gNOI.
    """

    def __init__(self,
                 host,
                 port=9339,
                 username=None,
                 password=None,
                 token=None,
                 timeout=30,
                 insecure=False,
                 ca_cert=None,
                 client_cert=None,
                 client_key=None,
                 tls_server_name=None,
                 tls_skip_verify=False,
                 max_message_length=None,
                 channel_options=None,
                 warn_callback=None):
        if not HAS_GNOI:
            raise GnoiClientError(
                "gNOI libraries are not available. Install with "
                "'pip install grpcio protobuf'. Import error: {0}".format(GNOI_IMPORT_ERROR)
            )

        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.token = token
        self.timeout = timeout
        self.insecure = insecure
        self.ca_cert = ca_cert
        self.client_cert = client_cert
        self.client_key = client_key
        self.tls_server_name = tls_server_name
        self.tls_skip_verify = tls_skip_verify
        self.max_message_length = max_message_length
        self.channel_options = channel_options or {}
        self._warn = warn_callback or logger.warning

        self.channel = None
        self._metadata = None
        self.cert_stub = None
        self.os_stub = None
        self.reset_stub = None

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def connect(self):
        """Establish the gRPC channel and instantiate the gNOI stubs."""
        try:
            target = "{0}:{1}".format(self.host, self.port)
            extra_options = self._build_channel_options()

            if self.insecure:
                # Plaintext channel for lab/test environments only.
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
                    except Exception as cn_exc:
                        logger.debug("Could not extract CN from CA cert: %s", cn_exc)

                self.channel = grpc.secure_channel(
                    target, credentials,
                    options=options if options else None,
                )

            self.cert_stub = cert_pb2_grpc.CertificateManagementStub(self.channel)
            self.os_stub = os_pb2_grpc.OSStub(self.channel)
            self.reset_stub = factory_reset_pb2_grpc.FactoryResetStub(self.channel)
            self._metadata = self._build_metadata()

        except GnoiConnectionError:
            raise
        except Exception as exc:
            raise GnoiConnectionError(
                "Failed to connect to {0}:{1}: {2}".format(self.host, self.port, exc))

    def disconnect(self):
        """Close the gRPC channel."""
        if self.channel:
            self.channel.close()
            self.channel = None
            self.cert_stub = None
            self.os_stub = None
            self.reset_stub = None

    @property
    def metadata(self):
        """gRPC metadata (auth headers) to attach to every RPC."""
        return self._metadata

    # ------------------------------------------------------------------
    # Helpers (mirror the gNMI client's transport behaviour)
    # ------------------------------------------------------------------

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

        Bearer token takes precedence; otherwise fall back to the
        ``username``/``password`` headers expected by Cisco gNMI/gNOI servers.
        """
        if self.token:
            return [('authorization', 'Bearer {0}'.format(self.token))]
        if self.username and self.password:
            return [('username', self.username), ('password', self.password)]
        return None

    @staticmethod
    def _read_cert_file(path, label):
        """Read a PEM file, raising GnoiConnectionError with clear context."""
        try:
            with open(path, 'rb') as handle:
                return handle.read()
        except FileNotFoundError:
            raise GnoiConnectionError(
                "{0} file not found: {1}".format(label, path))
        except PermissionError:
            raise GnoiConnectionError(
                "{0} file not readable (permission denied): {1}".format(label, path))
        except OSError as exc:
            raise GnoiConnectionError(
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
            raise GnoiConnectionError(
                "tls_skip_verify: failed to fetch certificate from "
                "{0}:{1}: {2}".format(self.host, self.port, exc))

        if not der_cert:
            raise GnoiConnectionError(
                "tls_skip_verify: server {0}:{1} did not present a "
                "certificate.".format(self.host, self.port))

        return ssl.DER_cert_to_PEM_cert(der_cert).encode('ascii')
