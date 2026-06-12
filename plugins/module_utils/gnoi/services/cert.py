# -*- coding: utf-8 -*-

# Copyright 2025 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Certificate Management service handlers (cert.proto).

Implements the gNOI ``gnoi.certificate.CertificateManagement`` RPCs that Cisco
IOS XE supports:

    - install            -> Install (LoadCertificate flow)
    - rotate             -> Rotate (LoadCertificate + Finalize flow)
    - revoke             -> RevokeCertificates
    - get                -> GetCertificates
    - can_generate_csr   -> CanGenerateCSR

The ``install`` and ``rotate`` flows used here load an externally generated
certificate, key pair, and (optionally) CA bundle. The GenerateCSR-on-device
flow is intentionally not exposed by this module; callers provide the signed
certificate material directly.
"""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

import queue

import grpc

from ..client import GnoiOperationError, rpc_error_to_operation_error
from ..protos import cert_pb2
from ..registry import register


# Sensitive arg keys that must never appear in module results.
_SECRET_KEYS = ('private_key',)


def _to_bytes(value):
    """Return PEM/text material as bytes for protobuf ``bytes`` fields."""
    if value is None:
        return None
    if isinstance(value, bytes):
        return value
    return value.encode('utf-8')


def _build_certificate(pem):
    """Build an X.509 :class:`Certificate` message from PEM text/bytes."""
    return cert_pb2.Certificate(
        type=cert_pb2.CT_X509,
        certificate=_to_bytes(pem),
    )


def _require(args, key, service, operation):
    """Return ``args[key]`` or raise a clear :class:`GnoiOperationError`."""
    value = args.get(key)
    if value is None or value == '':
        raise GnoiOperationError(
            "gNOI {0}/{1} requires args.{2}.".format(service, operation, key))
    return value


def _build_load_request(args, service, operation):
    """Build a :class:`LoadCertificateRequest` from user args."""
    certificate_id = _require(args, 'certificate_id', service, operation)
    certificate = _require(args, 'certificate', service, operation)
    private_key = _require(args, 'private_key', service, operation)

    load = cert_pb2.LoadCertificateRequest(
        certificate=_build_certificate(certificate),
        key_pair=cert_pb2.KeyPair(private_key=_to_bytes(private_key)),
        certificate_id=certificate_id,
    )

    ca_certificate = args.get('ca_certificate')
    if ca_certificate:
        load.ca_certificates.append(_build_certificate(ca_certificate))

    return load


@register('cert', 'install', mutating=True, destructive=False,
          description='Install a certificate (LoadCertificate flow).')
def install(request):
    """Install a new certificate on the device.

    Uses the Install bidirectional stream to load an externally generated
    certificate, key pair, and optional CA bundle. Fails if a certificate with
    the same ``certificate_id`` already exists.
    """
    load = _build_load_request(request.args, 'cert', 'install')
    install_request = cert_pb2.InstallCertificateRequest(load_certificate=load)

    def request_iterator():
        yield install_request

    try:
        responses = request.client.cert_stub.Install(
            request_iterator(),
            metadata=request.client.metadata,
            timeout=request.timeout,
        )
        # Drain the response stream; a load_certificate response signals success.
        for _response in responses:
            pass
    except grpc.RpcError as exc:
        raise rpc_error_to_operation_error(exc, 'cert', 'install')

    return {
        'changed': True,
        'msg': "Certificate '{0}' installed.".format(request.args['certificate_id']),
        'response': {'certificate_id': request.args['certificate_id']},
    }


@register('cert', 'rotate', mutating=True, destructive=False,
          description='Rotate (renew) an existing certificate.')
def rotate(request):
    """Rotate an existing certificate.

    Loads the new certificate material, then sends a Finalize message to commit
    the rotation. The certificate with ``certificate_id`` must already exist.

    Note: this handler does not open an independent connection to test the new
    certificate between load and finalize. Verify device reachability after a
    rotation as a separate step.
    """
    load = _build_load_request(request.args, 'cert', 'rotate')
    load_msg = cert_pb2.RotateCertificateRequest(load_certificate=load)
    finalize_msg = cert_pb2.RotateCertificateRequest(
        finalize_rotation=cert_pb2.FinalizeRequest())

    send_queue = queue.Queue()

    def request_iterator():
        while True:
            item = send_queue.get()
            if item is None:
                return
            yield item

    # Send the load request first; wait for its response before finalizing.
    send_queue.put(load_msg)
    try:
        responses = request.client.cert_stub.Rotate(
            request_iterator(),
            metadata=request.client.metadata,
            timeout=request.timeout,
        )
        # Block for the load response, then finalize and close the stream.
        next(responses)
        send_queue.put(finalize_msg)
        send_queue.put(None)
        for _response in responses:
            pass
    except StopIteration:
        send_queue.put(None)
    except grpc.RpcError as exc:
        send_queue.put(None)
        raise rpc_error_to_operation_error(exc, 'cert', 'rotate')

    return {
        'changed': True,
        'msg': "Certificate '{0}' rotated.".format(request.args['certificate_id']),
        'response': {'certificate_id': request.args['certificate_id']},
    }


@register('cert', 'revoke', mutating=True, destructive=False,
          description='Revoke one or more certificates by ID.')
def revoke(request):
    """Revoke one or more certificates by certificate ID."""
    ids = request.args.get('certificate_ids')
    if not ids:
        single = request.args.get('certificate_id')
        ids = [single] if single else []
    if not ids:
        raise GnoiOperationError(
            "gNOI cert/revoke requires args.certificate_ids (list) or "
            "args.certificate_id.")

    revoke_request = cert_pb2.RevokeCertificatesRequest(certificate_id=list(ids))

    try:
        response = request.client.cert_stub.RevokeCertificates(
            revoke_request,
            metadata=request.client.metadata,
            timeout=request.timeout,
        )
    except grpc.RpcError as exc:
        raise rpc_error_to_operation_error(exc, 'cert', 'revoke')

    revoked = list(response.revoked_certificate_id)
    errors = [
        {'certificate_id': err.certificate_id, 'error_message': err.error_message}
        for err in response.certificate_revocation_error
    ]

    return {
        'changed': bool(revoked),
        'msg': "Revoked {0} certificate(s).".format(len(revoked)),
        'response': {'revoked_certificate_id': revoked, 'errors': errors},
    }


@register('cert', 'get', mutating=False, destructive=False,
          description='List installed certificates.')
def get(request):
    """List installed certificates. Read-only (``changed: false``)."""
    try:
        response = request.client.cert_stub.GetCertificates(
            cert_pb2.GetCertificatesRequest(),
            metadata=request.client.metadata,
            timeout=request.timeout,
        )
    except grpc.RpcError as exc:
        raise rpc_error_to_operation_error(exc, 'cert', 'get')

    certificates = []
    for info in response.certificate_info:
        certificate_pem = None
        if info.certificate and info.certificate.certificate:
            certificate_pem = info.certificate.certificate.decode('utf-8', errors='replace')
        certificates.append({
            'certificate_id': info.certificate_id,
            'modification_time': info.modification_time,
            'certificate': certificate_pem,
        })

    return {
        'changed': False,
        'msg': "Found {0} certificate(s).".format(len(certificates)),
        'response': {'certificates': certificates},
    }


@register('cert', 'can_generate_csr', mutating=False, destructive=False,
          description='Query whether the device can generate a CSR.')
def can_generate_csr(request):
    """Query whether the device can generate a CSR. Read-only."""
    key_size = request.args.get('key_size', 2048)
    csr_request = cert_pb2.CanGenerateCSRRequest(
        key_type=cert_pb2.KT_RSA,
        certificate_type=cert_pb2.CT_X509,
        key_size=int(key_size),
    )

    try:
        response = request.client.cert_stub.CanGenerateCSR(
            csr_request,
            metadata=request.client.metadata,
            timeout=request.timeout,
        )
    except grpc.RpcError as exc:
        raise rpc_error_to_operation_error(exc, 'cert', 'can_generate_csr')

    return {
        'changed': False,
        'msg': "can_generate={0}".format(response.can_generate),
        'response': {'can_generate': bool(response.can_generate)},
    }
