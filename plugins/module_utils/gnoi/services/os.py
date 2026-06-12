# -*- coding: utf-8 -*-

# Copyright 2025 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""OS Installation service handlers (os.proto).

Implements the gNOI ``gnoi.os.OS`` RPCs supported by Cisco IOS XE:

    - install   -> Install (client-side image streaming)
    - activate  -> Activate (sets next-boot version and reboots)
    - verify    -> Verify (running OS version)

Only the standards-based client-side streaming workflow is implemented: the
image bytes are streamed directly to the device over the Install RPC. Image
URI / HTTP / SCP / TFTP distribution mechanisms are intentionally not
supported.
"""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

# stdlib import; ``absolute_import`` ensures this is the standard library os
# module, not this package module (which is also named ``os``).
import os
import re
import threading
import time

import grpc

from ..client import GnoiOperationError, rpc_error_to_operation_error
from ..protos import os_pb2
from ..registry import register


# Install error types that mean "the requested image is already the running
# package" - treated as idempotent success rather than a failure.
_ALREADY_RUNNING = 'INSTALL_RUN_PACKAGE'


def _install_error_name(error_type):
    """Return the symbolic name for an ``InstallError.Type`` value."""
    try:
        return os_pb2.InstallError.Type.Name(error_type)
    except ValueError:  # pragma: no cover - defensive
        return str(error_type)


def _activate_error_name(error_type):
    """Return the symbolic name for an ``ActivateError.Type`` value."""
    try:
        return os_pb2.ActivateError.Type.Name(error_type)
    except ValueError:  # pragma: no cover - defensive
        return str(error_type)


# IOS XE ``.bin`` images embed a metadata block near the start of the file,
# e.g. ``CW_FULL_VERSION=$17.18.03a.0.5540.1776935325..IOSXE$``. The value
# between the dollar signs is the canonical install/activate version; the
# trailing ``..<PLATFORM>`` tag is not part of the version Verify reports.
_CW_FULL_VERSION_RE = re.compile(r'CW_FULL_VERSION=\$([^$]+)\$')
_PLATFORM_SUFFIX_RE = re.compile(r'\.\.[A-Za-z0-9_]+$')
# Number of header bytes to scan for the version marker.
_IMAGE_HEADER_BYTES = 8192


def _extract_image_version(image_path):
    """Extract the canonical CW_FULL_VERSION from an IOS XE image header.

    IOS XE ``.bin`` images embed a metadata block near the start of the file
    containing ``CW_FULL_VERSION=$<version>..<platform>$``. The ``<version>``
    portion (e.g. ``17.18.03a.0.5540.1776935325``) is exactly the value that
    gNOI Install and Activate expect and that Verify reports.

    Returns the extracted version string, or raises ``GnoiOperationError`` if
    the marker cannot be found.
    """
    try:
        with open(image_path, 'rb') as image:
            header = image.read(_IMAGE_HEADER_BYTES)
    except OSError as exc:
        raise GnoiOperationError(
            "gNOI: could not read image header from {0}: {1}".format(
                image_path, exc))

    # latin-1 maps every byte to a character, so binary content never raises.
    text = header.decode('latin-1', 'ignore')
    match = _CW_FULL_VERSION_RE.search(text)
    if not match:
        raise GnoiOperationError(
            "gNOI: could not extract CW_FULL_VERSION from image '{0}'. "
            "Provide args.version explicitly.".format(image_path))

    return _PLATFORM_SUFFIX_RE.sub('', match.group(1).strip())


@register('os', 'install', mutating=True, destructive=False,
          description='Stream and install an OS image (client-side streaming).')
def install(request):
    """Stream an OS image to the device and validate it.

    Implements the OpenConfig OS Install sequence:
    TransferRequest -> TransferReady -> transfer_content* -> TransferEnd ->
    Validated. The image is read from ``args.image_path`` and streamed in
    ``chunk_size`` byte chunks.
    """
    image_path = request.args.get('image_path')
    version = request.args.get('version')
    if not image_path:
        raise GnoiOperationError("gNOI os/install requires args.image_path.")
    if not os.path.isfile(image_path):
        raise GnoiOperationError(
            "gNOI os/install: image file not found: {0}".format(image_path))
    # If the caller did not supply a version, derive the canonical
    # CW_FULL_VERSION from the image header so install and activate use the
    # exact value the device expects.
    version_source = 'provided'
    if not version:
        version = _extract_image_version(image_path)
        version_source = 'image_header'

    package_size = os.path.getsize(image_path)
    chunk_size = int(request.chunk_size or 1048576)
    standby_supervisor = bool(request.args.get('standby_supervisor', False))

    ready_event = threading.Event()
    send_state = {'bytes_sent': 0, 'error': None, 'ended': False}

    def request_iterator():
        # 1. Announce the transfer.
        yield os_pb2.InstallRequest(
            transfer_request=os_pb2.TransferRequest(
                version=version,
                package_size=package_size,
                standby_supervisor=standby_supervisor,
            )
        )
        # 2. Wait for the device to signal it is ready to receive content.
        if not ready_event.wait(timeout=request.timeout):
            send_state['error'] = "Timed out waiting for TransferReady."
            return
        # 3. Stream the image content.
        try:
            with open(image_path, 'rb') as image:
                while True:
                    chunk = image.read(chunk_size)
                    if not chunk:
                        break
                    send_state['bytes_sent'] += len(chunk)
                    yield os_pb2.InstallRequest(transfer_content=chunk)
        except OSError as exc:
            send_state['error'] = "Failed to read image: {0}".format(exc)
            return
        # 4. Signal end of transfer. Mark the transfer complete so the
        # response handler can distinguish a fully-streamed image from one
        # that was interrupted mid-flight.
        send_state['ended'] = True
        yield os_pb2.InstallRequest(transfer_end=os_pb2.TransferEnd())

    start = time.time()
    validated = None
    last_progress = 0
    try:
        responses = request.client.os_stub.Install(
            request_iterator(),
            metadata=request.client.metadata,
            timeout=request.timeout,
        )
        for response in responses:
            which = response.WhichOneof('response')
            if which == 'transfer_ready':
                ready_event.set()
            elif which == 'transfer_progress':
                last_progress = response.transfer_progress.bytes_received
            elif which == 'validated':
                validated = response.validated
            elif which == 'install_error':
                error_name = _install_error_name(response.install_error.type)
                detail = response.install_error.detail
                if error_name == _ALREADY_RUNNING:
                    # Image already running: idempotent no-op.
                    return {
                        'changed': False,
                        'msg': "gNOI os/install: full version '{0}' is "
                               "already running.".format(version),
                        'response': {
                            'version': version,
                            'requested_version': version,
                            'version_source': version_source,
                            'install_state': 'already_running',
                        },
                    }
                raise GnoiOperationError(
                    "gNOI os/install failed: {0}: {1}".format(error_name, detail),
                    grpc_code=error_name, grpc_message=detail)
    except grpc.RpcError as exc:
        # Some IOS XE builds finish staging the image to flash but never emit
        # a terminal Validated response, so the Install RPC blocks until the
        # gRPC deadline (DEADLINE_EXCEEDED) or the stream is closed
        # (CANCELLED). If the client already streamed the entire image
        # (transfer_end sent and every byte delivered), the image is staged on
        # the device even though validation was never confirmed. Treat that as
        # a successful transfer rather than a hard failure so the workflow can
        # proceed to activate.
        code = exc.code()
        transfer_complete = (
            send_state['ended']
            and send_state['bytes_sent'] == package_size
        )
        recoverable = code in (
            grpc.StatusCode.DEADLINE_EXCEEDED,
            grpc.StatusCode.CANCELLED,
        )
        if transfer_complete and recoverable:
            duration = round(time.time() - start, 1)
            request.warn(
                "gNOI os/install: the device did not send a terminal "
                "Validated response (stream ended with {0}); reporting "
                "success because the full image was transferred. Confirm "
                "staging with 'show install summary' before activating."
                .format(code.name)
            )
            return {
                'changed': True,
                'msg': "gNOI os/install: image '{0}' fully transferred "
                       "({1} bytes); device did not emit a terminal "
                       "Validated ({2}). Image is staged. Full version: "
                       "{3}.".format(
                           image_path, package_size, code.name, version),
                'response': {
                    'image_path': image_path,
                    'version': version,
                    'requested_version': version,
                    'version_source': version_source,
                    'description': '',
                    'bytes_transferred': send_state['bytes_sent'],
                    'bytes_acknowledged': last_progress,
                    'transfer_state': 'completed',
                    'install_state': 'transferred',
                    'validated': False,
                    'duration_seconds': duration,
                },
            }
        raise rpc_error_to_operation_error(exc, 'os', 'install')
    finally:
        # Ensure the sender thread is never left blocked on the ready event.
        ready_event.set()

    if send_state['error']:
        raise GnoiOperationError(
            "gNOI os/install: {0}".format(send_state['error']))

    duration = round(time.time() - start, 1)
    validated_version = validated.version if validated else version
    bytes_transferred = send_state['bytes_sent']

    # Idempotency: if the device validated the version without ever requesting
    # the image content (no TransferReady, so nothing was streamed), the image
    # was already present. Report no change. Observed on IOS XE when the
    # requested version matches the running/installed image.
    if validated is not None and bytes_transferred == 0:
        return {
            'changed': False,
            'msg': "gNOI os/install: full version '{0}' is already present; "
                   "no transfer needed.".format(validated_version),
            'response': {
                'image_path': image_path,
                'version': validated_version,
                'requested_version': version,
                'version_source': version_source,
                'description': validated.description,
                'bytes_transferred': 0,
                'bytes_acknowledged': last_progress,
                'transfer_state': 'skipped',
                'install_state': 'already_present',
                'duration_seconds': duration,
            },
        }

    return {
        'changed': True,
        'msg': "gNOI os/install: image '{0}' transferred and validated. "
               "Full version: {1}.".format(image_path, validated_version),
        'response': {
            'image_path': image_path,
            'version': validated_version,
            'requested_version': version,
            'version_source': version_source,
            'description': validated.description if validated else '',
            'bytes_transferred': bytes_transferred,
            'bytes_acknowledged': last_progress,
            'transfer_state': 'completed',
            'install_state': 'validated' if validated else 'transferred',
            'validated': validated is not None,
            'duration_seconds': duration,
        },
    }


@register('os', 'activate', mutating=True, destructive=True,
          description='Activate an installed OS version (reboots the device).')
def activate(request):
    """Activate an installed OS version.

    Sets the requested version as the next-boot version and (unless
    ``no_reboot`` is set) reboots the device. Destructive: requires
    ``confirm: true``.

    Idempotency: the running version is checked via Verify first; if it
    already matches the requested version, no activation is performed.
    """
    version = request.args.get('version')
    image_path = request.args.get('image_path')
    # Allow deriving the version from the image file, mirroring os/install, so
    # a single image_path can drive the whole install -> activate workflow.
    version_source = 'provided'
    if not version:
        if image_path:
            if not os.path.isfile(image_path):
                raise GnoiOperationError(
                    "gNOI os/activate: image file not found: {0}".format(
                        image_path))
            version = _extract_image_version(image_path)
            version_source = 'image_header'
        else:
            raise GnoiOperationError(
                "gNOI os/activate requires args.version (or args.image_path "
                "to derive it).")

    no_reboot = bool(request.args.get('no_reboot', False))
    standby_supervisor = bool(request.args.get('standby_supervisor', False))

    # Idempotency: skip activation if the requested version is already running.
    try:
        verify_response = request.client.os_stub.Verify(
            os_pb2.VerifyRequest(),
            metadata=request.client.metadata,
            timeout=request.timeout,
        )
        if verify_response.version == version:
            return {
                'changed': False,
                'msg': "gNOI os/activate: full version '{0}' is already "
                       "active.".format(version),
                'response': {
                    'version': version,
                    'version_source': version_source,
                    'activation_state': 'already_active',
                },
            }
    except grpc.RpcError:
        # Verify may be unavailable; proceed with activation.
        request.warn(
            "Could not verify running version before activate; proceeding.")

    activate_request = os_pb2.ActivateRequest(
        version=version,
        no_reboot=no_reboot,
        standby_supervisor=standby_supervisor,
    )

    try:
        response = request.client.os_stub.Activate(
            activate_request,
            metadata=request.client.metadata,
            timeout=request.timeout,
        )
    except grpc.RpcError as exc:
        raise rpc_error_to_operation_error(exc, 'os', 'activate')

    which = response.WhichOneof('response')
    if which == 'activate_error':
        error_name = _activate_error_name(response.activate_error.type)
        detail = response.activate_error.detail
        raise GnoiOperationError(
            "gNOI os/activate failed: {0}: {1}".format(error_name, detail),
            grpc_code=error_name, grpc_message=detail)

    return {
        'changed': True,
        'msg': "gNOI os/activate: full version '{0}' activated{1}.".format(
            version, '' if no_reboot else ' (device rebooting)'),
        'response': {
            'version': version,
            'version_source': version_source,
            'no_reboot': no_reboot,
            'activation_state': 'activated',
        },
    }


@register('os', 'verify', mutating=False, destructive=False,
          description='Verify the running OS version.')
def verify(request):
    """Verify the running OS version. Read-only (``changed: false``)."""
    try:
        response = request.client.os_stub.Verify(
            os_pb2.VerifyRequest(),
            metadata=request.client.metadata,
            timeout=request.timeout,
        )
    except grpc.RpcError as exc:
        raise rpc_error_to_operation_error(exc, 'os', 'verify')

    result_response = {
        'version': response.version,
        'activation_fail_message': response.activation_fail_message,
        'individual_supervisor_install': bool(response.individual_supervisor_install),
    }

    requested = request.args.get('version')
    matches = None
    if requested is not None:
        matches = (response.version == requested)
        result_response['matches_requested'] = matches

    return {
        'changed': False,
        'msg': "Running version: {0}".format(response.version),
        'response': result_response,
    }
