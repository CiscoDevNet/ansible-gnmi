# -*- coding: utf-8 -*-

# Copyright 2025 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the cisco.gnmi.gnoi module and its service framework.

Exercises:
  * the registry + capability model,
  * the dispatcher (validation, confirm gating, check mode),
  * the cert / os / factory_reset service handlers (with mocked stubs),
  * gRPC error translation,
  * argument-spec no_log handling.
"""

import os
import tempfile
import threading

import grpc
import pytest

from ansible_collections.cisco.gnmi.plugins.module_utils.gnoi import services  # noqa: F401
from ansible_collections.cisco.gnmi.plugins.module_utils.gnoi.registry import (
    known_services,
    known_operations,
    get_operation,
    platform_supports,
)
from ansible_collections.cisco.gnmi.plugins.module_utils.gnoi.handler import (
    GnoiRequest,
    DispatchError,
    dispatch,
)
from ansible_collections.cisco.gnmi.plugins.module_utils.gnoi.client import (
    GnoiClient,
    GnoiOperationError,
    rpc_error_to_operation_error,
)
from ansible_collections.cisco.gnmi.plugins.module_utils.gnoi.protos import (
    cert_pb2,
    os_pb2,
    factory_reset_pb2,
)
from ansible_collections.cisco.gnmi.plugins.module_utils.gnoi.services.os import (
    _extract_image_version,
)


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------

class FakeRpcError(grpc.RpcError):
    """A grpc.RpcError with deterministic code()/details()."""

    def __init__(self, code, details):
        self._code = code
        self._details = details

    def code(self):
        return self._code

    def details(self):
        return self._details


class FakeStub:
    """Records calls and returns a preset value or raises a preset error."""

    def __init__(self):
        self.calls = []

    def _make(self, name):
        def method(request, metadata=None, timeout=None):
            self.calls.append((name, request, metadata, timeout))
            behaviour = getattr(self, '_' + name, None)
            if isinstance(behaviour, Exception):
                raise behaviour
            if callable(behaviour):
                return behaviour(request, metadata, timeout)
            return behaviour
        return method

    def __getattr__(self, name):
        # Only synthesise RPC-style attributes (capitalised).
        if name and name[0].isupper():
            return self._make(name)
        raise AttributeError(name)


class FakeClient:
    """Minimal stand-in for GnoiClient used by handlers."""

    def __init__(self):
        self.metadata = None
        self.cert_stub = FakeStub()
        self.os_stub = FakeStub()
        self.reset_stub = FakeStub()


def make_request(service, operation, args=None, check_mode=False,
                 timeout=30, chunk_size=4, client=None):
    return GnoiRequest(
        client=client or FakeClient(),
        service=service,
        operation=operation,
        args=args or {},
        params={'timeout': timeout},
        check_mode=check_mode,
        timeout=timeout,
        chunk_size=chunk_size,
        warn=lambda _m: None,
    )


# ---------------------------------------------------------------------------
# Registry & capability model
# ---------------------------------------------------------------------------

def test_registry_known_services_and_operations():
    assert known_services() == ['cert', 'factory_reset', 'os']
    assert known_operations('os') == ['activate', 'install', 'verify']
    assert 'can_generate_csr' in known_operations('cert')
    assert known_operations('factory_reset') == ['start']


def test_operation_flags():
    assert get_operation('os', 'activate').destructive is True
    assert get_operation('factory_reset', 'start').destructive is True
    assert get_operation('os', 'verify').mutating is False
    assert get_operation('cert', 'get').mutating is False
    assert get_operation('cert', 'install').mutating is True


def test_platform_supports():
    assert platform_supports('iosxe', 'os', 'install') is True
    assert platform_supports('iosxe', 'os', 'bogus') is False
    # auto and unknown/empty platforms never gate.
    assert platform_supports('auto', 'os', 'anything') is True
    assert platform_supports('nxos', 'os', 'install') is True


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

def test_dispatch_unknown_service():
    req = make_request('bogus', 'install')
    with pytest.raises(DispatchError) as exc:
        dispatch(req)
    assert 'Unknown service' in str(exc.value)


def test_dispatch_unknown_operation():
    req = make_request('os', 'bogus')
    with pytest.raises(DispatchError) as exc:
        dispatch(req)
    assert 'Unknown operation' in str(exc.value)


def test_dispatch_destructive_requires_confirm():
    req = make_request('factory_reset', 'start')
    with pytest.raises(DispatchError) as exc:
        dispatch(req, confirm=False)
    assert 'requires confirm: true' in str(exc.value)


def test_dispatch_platform_gating():
    req = make_request('os', 'install')
    # IOS XE supports os/install, so this should not raise for capability.
    # Use a non-existent operation on a known platform to trigger gating via a
    # registered-but-unsupported combination is not possible, so assert the
    # message path through platform_supports directly is covered above.
    # Here just ensure auto platform proceeds to check-mode short circuit.
    req.check_mode = True
    result = dispatch(req, platform='auto')
    assert result['skipped_rpc'] is True


def test_dispatch_check_mode_skips_mutating():
    req = make_request('os', 'install', check_mode=True)
    result = dispatch(req)
    assert result['changed'] is True
    assert result['skipped_rpc'] is True
    assert result['service'] == 'os'
    assert result['operation'] == 'install'


def test_dispatch_check_mode_allows_readonly():
    client = FakeClient()
    client.os_stub._Verify = os_pb2.VerifyResponse(version='17.18.01a')
    req = make_request('os', 'verify', check_mode=True, client=client)
    result = dispatch(req)
    # Read-only verify executes even in check mode.
    assert result['changed'] is False
    assert result['response']['version'] == '17.18.01a'


# ---------------------------------------------------------------------------
# cert service
# ---------------------------------------------------------------------------

def test_cert_install_builds_load_request_and_changes():
    client = FakeClient()
    captured = {}

    def install_behaviour(request_iter, metadata, timeout):
        captured['requests'] = list(request_iter)
        return iter([cert_pb2.InstallCertificateResponse()])

    client.cert_stub._Install = install_behaviour
    req = make_request('cert', 'install', args={
        'certificate_id': 'grpc-server',
        'certificate': 'CERTPEM',
        'private_key': 'KEYPEM',
        'ca_certificate': 'CAPEM',
    }, client=client)

    result = dispatch(req)
    assert result['changed'] is True
    sent = captured['requests'][0]
    assert sent.WhichOneof('install_request') == 'load_certificate'
    assert sent.load_certificate.certificate_id == 'grpc-server'
    assert sent.load_certificate.certificate.certificate == b'CERTPEM'
    assert sent.load_certificate.key_pair.private_key == b'KEYPEM'
    assert sent.load_certificate.ca_certificates[0].certificate == b'CAPEM'


def test_cert_install_missing_args_fails():
    req = make_request('cert', 'install', args={'certificate_id': 'x'})
    with pytest.raises(GnoiOperationError) as exc:
        dispatch(req)
    assert 'args.certificate' in str(exc.value)


def test_cert_install_does_not_leak_private_key_in_result():
    client = FakeClient()
    client.cert_stub._Install = lambda r, m, t: iter([])
    req = make_request('cert', 'install', args={
        'certificate_id': 'grpc-server',
        'certificate': 'CERTPEM',
        'private_key': 'SUPERSECRETKEY',
    }, client=client)
    result = dispatch(req)
    assert 'SUPERSECRETKEY' not in str(result)


def test_cert_revoke():
    client = FakeClient()
    client.cert_stub._RevokeCertificates = cert_pb2.RevokeCertificatesResponse(
        revoked_certificate_id=['a', 'b'])
    req = make_request('cert', 'revoke', args={'certificate_ids': ['a', 'b']},
                       client=client)
    result = dispatch(req)
    assert result['changed'] is True
    assert result['response']['revoked_certificate_id'] == ['a', 'b']


def test_cert_get_is_readonly():
    client = FakeClient()
    info = cert_pb2.CertificateInfo(
        certificate_id='grpc-server',
        certificate=cert_pb2.Certificate(
            type=cert_pb2.CT_X509, certificate=b'PEMDATA'),
        modification_time=123,
    )
    client.cert_stub._GetCertificates = cert_pb2.GetCertificatesResponse(
        certificate_info=[info])
    req = make_request('cert', 'get', client=client)
    result = dispatch(req)
    assert result['changed'] is False
    assert result['response']['certificates'][0]['certificate_id'] == 'grpc-server'
    assert result['response']['certificates'][0]['certificate'] == 'PEMDATA'


def test_cert_can_generate_csr():
    client = FakeClient()
    client.cert_stub._CanGenerateCSR = cert_pb2.CanGenerateCSRResponse(
        can_generate=True)
    req = make_request('cert', 'can_generate_csr', args={'key_size': 2048},
                       client=client)
    result = dispatch(req)
    assert result['changed'] is False
    assert result['response']['can_generate'] is True


def test_cert_rotate_sends_load_then_finalize():
    client = FakeClient()
    captured = []

    def rotate_behaviour(request_iter, metadata, timeout):
        # Drain requests in a thread (mimics grpc's sender thread) so the
        # queue-driven request generator can progress as we yield responses.
        def drain():
            for item in request_iter:
                captured.append(item)
        thread = threading.Thread(target=drain)
        thread.start()

        def responses():
            yield cert_pb2.RotateCertificateResponse()  # load response
            thread.join(timeout=5)

        return responses()

    client.cert_stub._Rotate = rotate_behaviour
    req = make_request('cert', 'rotate', args={
        'certificate_id': 'grpc-server',
        'certificate': 'CERTPEM',
        'private_key': 'KEYPEM',
    }, client=client)

    result = dispatch(req)
    assert result['changed'] is True
    kinds = [item.WhichOneof('rotate_request') for item in captured]
    assert kinds == ['load_certificate', 'finalize_rotation']


def test_cert_grpc_error_is_translated():
    client = FakeClient()
    client.cert_stub._GetCertificates = FakeRpcError(
        grpc.StatusCode.UNIMPLEMENTED, 'not supported')
    req = make_request('cert', 'get', client=client)
    with pytest.raises(GnoiOperationError) as exc:
        dispatch(req)
    assert exc.value.grpc_code == 'UNIMPLEMENTED'
    assert 'not supported' in (exc.value.grpc_message or '')


# ---------------------------------------------------------------------------
# os service
# ---------------------------------------------------------------------------

def test_os_verify_readonly():
    client = FakeClient()
    client.os_stub._Verify = os_pb2.VerifyResponse(version='17.18.01a')
    req = make_request('os', 'verify', args={'version': '17.18.01a'},
                       client=client)
    result = dispatch(req)
    assert result['changed'] is False
    assert result['response']['version'] == '17.18.01a'
    assert result['response']['matches_requested'] is True


def test_os_activate_idempotent_when_already_active():
    client = FakeClient()
    client.os_stub._Verify = os_pb2.VerifyResponse(version='17.18.01a')
    req = make_request('os', 'activate', args={'version': '17.18.01a'},
                       client=client)
    result = dispatch(req, confirm=True)
    assert result['changed'] is False
    assert result['response']['activation_state'] == 'already_active'
    # Activate RPC must not have been called.
    assert not any(c[0] == 'Activate' for c in client.os_stub.calls)


def test_os_activate_runs_and_reboots():
    client = FakeClient()
    client.os_stub._Verify = os_pb2.VerifyResponse(version='OLD')
    client.os_stub._Activate = os_pb2.ActivateResponse(
        activate_ok=os_pb2.ActivateOK())
    req = make_request('os', 'activate', args={'version': 'NEW'}, client=client)
    result = dispatch(req, confirm=True)
    assert result['changed'] is True
    assert result['response']['activation_state'] == 'activated'


def test_os_activate_error():
    client = FakeClient()
    client.os_stub._Verify = os_pb2.VerifyResponse(version='OLD')
    client.os_stub._Activate = os_pb2.ActivateResponse(
        activate_error=os_pb2.ActivateError(
            type=os_pb2.ActivateError.NON_EXISTENT_VERSION, detail='no such'))
    req = make_request('os', 'activate', args={'version': 'NEW'}, client=client)
    with pytest.raises(GnoiOperationError) as exc:
        dispatch(req, confirm=True)
    assert 'no such' in str(exc.value)


def test_os_install_streams_and_validates():
    client = FakeClient()
    captured = []

    with tempfile.NamedTemporaryFile(delete=False) as handle:
        handle.write(b'ABCDEFGHIJ')  # 10 bytes
        image_path = handle.name

    def install_behaviour(request_iter, metadata, timeout):
        def drain():
            for item in request_iter:
                captured.append(item)
        thread = threading.Thread(target=drain)
        thread.start()

        def responses():
            yield os_pb2.InstallResponse(transfer_ready=os_pb2.TransferReady())
            yield os_pb2.InstallResponse(
                transfer_progress=os_pb2.TransferProgress(bytes_received=10))
            yield os_pb2.InstallResponse(
                validated=os_pb2.Validated(version='17.18.01a'))
            thread.join(timeout=5)

        return responses()

    client.os_stub._Install = install_behaviour
    req = make_request('os', 'install', args={
        'image_path': image_path,
        'version': '17.18.01a',
    }, chunk_size=4, client=client)

    try:
        result = dispatch(req)
    finally:
        os.unlink(image_path)

    assert result['changed'] is True
    assert result['response']['version'] == '17.18.01a'
    assert result['response']['bytes_transferred'] == 10
    assert result['response']['install_state'] == 'validated'
    kinds = [item.WhichOneof('request') for item in captured]
    assert kinds[0] == 'transfer_request'
    assert kinds[-1] == 'transfer_end'
    assert kinds.count('transfer_content') == 3  # 4+4+2 bytes


def test_os_install_missing_validated_after_full_transfer_succeeds():
    # Some IOS XE builds stage the image but never send a terminal Validated,
    # so the Install RPC ends with DEADLINE_EXCEEDED. Once the full image has
    # been streamed, the handler should report a staged success rather than
    # failing, and warn that validation was not confirmed.
    client = FakeClient()
    warnings = []

    with tempfile.NamedTemporaryFile(delete=False) as handle:
        handle.write(b'ABCDEFGHIJ')  # 10 bytes
        image_path = handle.name

    def install_behaviour(request_iter, metadata, timeout):
        def drain():
            for _item in request_iter:
                pass
        thread = threading.Thread(target=drain)
        thread.start()

        def responses():
            yield os_pb2.InstallResponse(transfer_ready=os_pb2.TransferReady())
            yield os_pb2.InstallResponse(
                transfer_progress=os_pb2.TransferProgress(bytes_received=10))
            # Wait until the entire image has been streamed, then simulate the
            # device closing the stream without a Validated message.
            thread.join(timeout=5)
            raise FakeRpcError(
                grpc.StatusCode.DEADLINE_EXCEEDED, 'Deadline Exceeded')

        return responses()

    client.os_stub._Install = install_behaviour
    req = make_request('os', 'install', args={
        'image_path': image_path,
        'version': '17.18.03a.0.5540.1776935325',
    }, chunk_size=4, client=client)
    req.warn = warnings.append

    try:
        result = dispatch(req)
    finally:
        os.unlink(image_path)

    assert result['changed'] is True
    assert result['response']['install_state'] == 'transferred'
    assert result['response']['validated'] is False
    assert result['response']['bytes_transferred'] == 10
    assert result['response']['transfer_state'] == 'completed'
    assert warnings, 'expected a warning about the missing Validated response'


def test_os_install_deadline_before_full_transfer_still_fails():
    # If the stream dies before the whole image is sent, that is a genuine
    # failure and must not be reported as a staged success.
    client = FakeClient()

    with tempfile.NamedTemporaryFile(delete=False) as handle:
        handle.write(b'ABCDEFGHIJ')  # 10 bytes
        image_path = handle.name

    def install_behaviour(request_iter, metadata, timeout):
        # Never signal transfer_ready, so no content is streamed, then fail.
        def responses():
            raise FakeRpcError(
                grpc.StatusCode.DEADLINE_EXCEEDED, 'Deadline Exceeded')
            yield  # pragma: no cover - generator marker
        return responses()

    client.os_stub._Install = install_behaviour
    req = make_request('os', 'install', args={
        'image_path': image_path,
        'version': '17.18.03a.0.5540.1776935325',
    }, chunk_size=4, client=client)

    try:
        with pytest.raises(GnoiOperationError):
            dispatch(req)
    finally:
        os.unlink(image_path)


def test_extract_image_version_from_header():
    header = (b'\x00\x01CW_BEGIN=$$\n'
              b'CW_FULL_VERSION=$17.18.03a.0.5540.1776935325..IOSXE$\n'
              b'CW_END=$$\n') + b'\xff' * 1000
    with tempfile.NamedTemporaryFile(delete=False) as handle:
        handle.write(header)
        image_path = handle.name
    try:
        version = _extract_image_version(image_path)
    finally:
        os.unlink(image_path)
    assert version == '17.18.03a.0.5540.1776935325'


def test_extract_image_version_missing_marker_raises():
    with tempfile.NamedTemporaryFile(delete=False) as handle:
        handle.write(b'no version marker present in this header')
        image_path = handle.name
    try:
        with pytest.raises(GnoiOperationError):
            _extract_image_version(image_path)
    finally:
        os.unlink(image_path)


def test_os_install_derives_version_from_image_when_omitted():
    client = FakeClient()
    captured = []

    header = (b'CW_FULL_VERSION=$17.18.03a.0.5540.1776935325..IOSXE$\n'
              + b'PADDINGDATA' * 4)
    with tempfile.NamedTemporaryFile(delete=False) as handle:
        handle.write(header)
        image_path = handle.name

    def install_behaviour(request_iter, metadata, timeout):
        def drain():
            for item in request_iter:
                captured.append(item)
        thread = threading.Thread(target=drain)
        thread.start()

        def responses():
            yield os_pb2.InstallResponse(transfer_ready=os_pb2.TransferReady())
            yield os_pb2.InstallResponse(
                validated=os_pb2.Validated(
                    version='17.18.03a.0.5540.1776935325'))
            thread.join(timeout=5)

        return responses()

    client.os_stub._Install = install_behaviour
    # No 'version' supplied: it must be derived from the image header.
    req = make_request('os', 'install', args={
        'image_path': image_path,
    }, chunk_size=64, client=client)

    try:
        result = dispatch(req)
    finally:
        os.unlink(image_path)

    assert result['changed'] is True
    assert result['response']['version'] == '17.18.03a.0.5540.1776935325'
    # The derived version must be carried in the TransferRequest.
    assert captured[0].transfer_request.version == \
        '17.18.03a.0.5540.1776935325'


def test_os_install_missing_version_and_unreadable_marker_fails():
    with tempfile.NamedTemporaryFile(delete=False) as handle:
        handle.write(b'binary image without a version marker')
        image_path = handle.name
    req = make_request('os', 'install', args={'image_path': image_path})
    try:
        with pytest.raises((GnoiOperationError, DispatchError)):
            dispatch(req)
    finally:
        os.unlink(image_path)


def test_os_install_already_running_is_idempotent():
    client = FakeClient()

    with tempfile.NamedTemporaryFile(delete=False) as handle:
        handle.write(b'X')
        image_path = handle.name

    def install_behaviour(request_iter, metadata, timeout):
        def drain():
            for _ in request_iter:
                pass
        thread = threading.Thread(target=drain)
        thread.start()

        def responses():
            yield os_pb2.InstallResponse(transfer_ready=os_pb2.TransferReady())
            yield os_pb2.InstallResponse(
                install_error=os_pb2.InstallError(
                    type=os_pb2.InstallError.INSTALL_RUN_PACKAGE,
                    detail='already running'))
            thread.join(timeout=5)

        return responses()

    client.os_stub._Install = install_behaviour
    req = make_request('os', 'install', args={
        'image_path': image_path, 'version': '17.18.01a',
    }, client=client)

    try:
        result = dispatch(req)
    finally:
        os.unlink(image_path)

    assert result['changed'] is False
    assert result['response']['install_state'] == 'already_running'


def test_os_install_validated_without_transfer_is_idempotent():
    # Observed on IOS XE: when the requested version already matches the
    # installed image, the device returns Validated immediately without ever
    # sending TransferReady, so no content is streamed. Treat as no change.
    client = FakeClient()

    with tempfile.NamedTemporaryFile(delete=False) as handle:
        handle.write(b'0123456789')
        image_path = handle.name

    def install_behaviour(request_iter, metadata, timeout):
        def drain():
            for _ in request_iter:
                pass
        thread = threading.Thread(target=drain)
        thread.start()

        def responses():
            # No transfer_ready -> the client never streams content.
            yield os_pb2.InstallResponse(
                validated=os_pb2.Validated(version='26.01.01a.0.441'))
            thread.join(timeout=5)

        return responses()

    client.os_stub._Install = install_behaviour
    req = make_request('os', 'install', args={
        'image_path': image_path, 'version': '26.01.01a.0.441',
    }, client=client)

    try:
        result = dispatch(req)
    finally:
        os.unlink(image_path)

    assert result['changed'] is False
    assert result['response']['bytes_transferred'] == 0
    assert result['response']['install_state'] == 'already_present'
    assert result['response']['transfer_state'] == 'skipped'
    assert result['response']['version'] == '26.01.01a.0.441'


def test_os_install_missing_image_fails():
    req = make_request('os', 'install', args={
        'image_path': '/nonexistent/image.bin', 'version': '1.0'})
    with pytest.raises(GnoiOperationError) as exc:
        dispatch(req)
    assert 'image file not found' in str(exc.value)


# ---------------------------------------------------------------------------
# factory_reset service
# ---------------------------------------------------------------------------

def test_factory_reset_start_success():
    client = FakeClient()
    client.reset_stub._Start = factory_reset_pb2.StartResponse(
        reset_success=factory_reset_pb2.ResetSuccess())
    req = make_request('factory_reset', 'start', args={'zero_fill': False},
                       client=client)
    result = dispatch(req, confirm=True)
    assert result['changed'] is True
    assert result['response']['reset_state'] == 'started'


def test_factory_reset_error():
    client = FakeClient()
    client.reset_stub._Start = factory_reset_pb2.StartResponse(
        reset_error=factory_reset_pb2.ResetError(
            zero_fill_unsupported=True, detail='no zero fill'))
    req = make_request('factory_reset', 'start', args={'zero_fill': True},
                       client=client)
    with pytest.raises(GnoiOperationError) as exc:
        dispatch(req, confirm=True)
    assert 'no zero fill' in str(exc.value)


# ---------------------------------------------------------------------------
# Error translation
# ---------------------------------------------------------------------------

def test_rpc_error_to_operation_error():
    err = FakeRpcError(grpc.StatusCode.FAILED_PRECONDITION, 'needs cert')
    op_err = rpc_error_to_operation_error(err, 'factory_reset', 'start')
    assert op_err.grpc_code == 'FAILED_PRECONDITION'
    assert op_err.grpc_message == 'needs cert'
    assert 'factory_reset/start' in str(op_err)


# ---------------------------------------------------------------------------
# Module argument spec
# ---------------------------------------------------------------------------

def test_module_argument_spec_marks_private_key_no_log():
    from ansible_collections.cisco.gnmi.plugins.modules.gnoi import argument_spec
    spec = argument_spec()
    suboptions = spec['args']['options']
    assert suboptions['private_key']['no_log'] is True
    assert spec['password']['no_log'] is True
    assert spec['token']['no_log'] is True


def test_module_argument_spec_has_tls_skip_verify():
    from ansible_collections.cisco.gnmi.plugins.modules.gnoi import argument_spec
    spec = argument_spec()
    assert spec['tls_skip_verify']['type'] == 'bool'
    assert spec['tls_skip_verify']['default'] is False


# ---------------------------------------------------------------------------
# TLS transport / tls_skip_verify (Trust-On-First-Use)
# ---------------------------------------------------------------------------

class _FakeChannel:
    """Minimal channel that satisfies gRPC stub construction."""

    def unary_unary(self, *args, **kwargs):
        return None

    def unary_stream(self, *args, **kwargs):
        return None

    def stream_unary(self, *args, **kwargs):
        return None

    def stream_stream(self, *args, **kwargs):
        return None

    def close(self):
        pass


def _patch_secure_channel(monkeypatch):
    """Patch grpc credentials + secure_channel, returning a capture dict."""
    from ansible_collections.cisco.gnmi.plugins.module_utils.gnoi import (
        client as client_mod,
    )
    captured = {}

    def fake_ssl_creds(root_certificates=None, private_key=None,
                       certificate_chain=None):
        captured['root_certificates'] = root_certificates
        return 'CREDENTIALS'

    def fake_secure_channel(target, credentials, options=None):
        captured['target'] = target
        captured['credentials'] = credentials
        captured['options'] = options
        return _FakeChannel()

    monkeypatch.setattr(client_mod.grpc, 'ssl_channel_credentials', fake_ssl_creds)
    monkeypatch.setattr(client_mod.grpc, 'secure_channel', fake_secure_channel)
    return captured


def test_tls_skip_verify_fetches_and_trusts_server_cert(monkeypatch):
    captured = _patch_secure_channel(monkeypatch)
    monkeypatch.setattr(
        GnoiClient, '_fetch_server_certificate',
        lambda self: b'-----BEGIN CERTIFICATE-----\nTOFU\n-----END CERTIFICATE-----\n')

    client = GnoiClient(host='10.0.0.1', port=9339, username='u', password='p',
                        tls_skip_verify=True)
    client.connect()

    # The fetched (TOFU) certificate is used as the channel root of trust.
    assert captured['root_certificates'] == (
        b'-----BEGIN CERTIFICATE-----\nTOFU\n-----END CERTIFICATE-----\n')
    assert captured['target'] == '10.0.0.1:9339'


def test_ca_cert_takes_precedence_over_tls_skip_verify(monkeypatch, tmp_path):
    captured = _patch_secure_channel(monkeypatch)
    fetch_called = {'value': False}

    def fake_fetch(self):
        fetch_called['value'] = True
        return b'SHOULD_NOT_BE_USED'

    monkeypatch.setattr(GnoiClient, '_fetch_server_certificate', fake_fetch)

    ca_file = tmp_path / 'ca.pem'
    ca_file.write_bytes(b'PINNED_CA_PEM')

    client = GnoiClient(host='10.0.0.1', port=9339, ca_cert=str(ca_file),
                        tls_skip_verify=True)
    client.connect()

    assert fetch_called['value'] is False
    assert captured['root_certificates'] == b'PINNED_CA_PEM'


def test_insecure_ignores_tls_skip_verify(monkeypatch):
    from ansible_collections.cisco.gnmi.plugins.module_utils.gnoi import (
        client as client_mod,
    )
    fetch_called = {'value': False}
    monkeypatch.setattr(
        GnoiClient, '_fetch_server_certificate',
        lambda self: fetch_called.__setitem__('value', True) or b'X')
    monkeypatch.setattr(client_mod.grpc, 'insecure_channel',
                        lambda target, options=None: _FakeChannel())

    client = GnoiClient(host='10.0.0.1', port=50052, username='u', password='p',
                        insecure=True, tls_skip_verify=True)
    client.connect()

    # Plaintext channel: no TLS, so no certificate fetch.
    assert fetch_called['value'] is False


def test_fetch_server_certificate_returns_pem(monkeypatch):
    from ansible_collections.cisco.gnmi.plugins.module_utils.gnoi import (
        client as client_mod,
    )

    class _Ctx:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    class _FakeTlsSock(_Ctx):
        def getpeercert(self, binary_form=False):
            assert binary_form is True
            return b'DERBYTES'

    class _FakeSock(_Ctx):
        pass

    class _FakeSslContext:
        def __init__(self, *args, **kwargs):
            self.check_hostname = True
            self.verify_mode = None

        def wrap_socket(self, sock, server_hostname=None):
            return _FakeTlsSock()

    monkeypatch.setattr(client_mod.socket, 'create_connection',
                        lambda addr, timeout=None: _FakeSock())
    monkeypatch.setattr(client_mod.ssl, 'SSLContext', _FakeSslContext)
    monkeypatch.setattr(client_mod.ssl, 'DER_cert_to_PEM_cert',
                        lambda der: '-----BEGIN CERTIFICATE-----\nX\n-----END CERTIFICATE-----\n')

    client = GnoiClient(host='10.0.0.1', port=9339)
    pem = client._fetch_server_certificate()
    assert pem == b'-----BEGIN CERTIFICATE-----\nX\n-----END CERTIFICATE-----\n'
