# -*- coding: utf-8 -*-

# Copyright 2025 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Dispatch logic and the request context passed to gNOI service handlers."""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

from .registry import get_operation, known_operations, known_services, platform_supports


class GnoiRequest:
    """Everything a service handler needs to perform one gNOI operation.

    Attributes:
        client: A connected :class:`...gnoi.client.GnoiClient`.
        service: Requested service name.
        operation: Requested operation name.
        args: The user-supplied ``args`` dict (operation-specific parameters).
        params: The full Ansible module ``params`` (for connection-level
            settings such as ``timeout``).
        check_mode: Whether the module is running with ``--check``.
        timeout: RPC timeout in seconds.
        chunk_size: Streaming chunk size in bytes (used by OS install).
        warn: Callable accepting a single string to emit a warning.
    """

    def __init__(self, client, service, operation, args, params,
                 check_mode=False, timeout=None, chunk_size=None, warn=None):
        self.client = client
        self.service = service
        self.operation = operation
        self.args = args or {}
        self.params = params or {}
        self.check_mode = check_mode
        self.timeout = timeout
        self.chunk_size = chunk_size
        self.warn = warn or (lambda _msg: None)


class DispatchError(Exception):
    """Raised for invalid dispatch input (unknown service/operation, missing
    confirmation, or unsupported platform). The module layer turns this into a
    clean ``fail_json``."""


def dispatch(request, platform='auto', confirm=False):
    """Validate and execute a gNOI operation.

    Performs, in order:
        1. service/operation existence check against the registry,
        2. platform capability check,
        3. destructive-operation confirmation gating,
        4. check-mode short-circuit for mutating operations,
        5. handler execution.

    Returns a result dict with at least ``changed`` and ``msg``. Raises
    :class:`DispatchError` for invalid input; handler RPC failures surface as
    :class:`...gnoi.client.GnoiOperationError`.
    """
    spec = get_operation(request.service, request.operation)
    if spec is None:
        services = ', '.join(known_services())
        if request.service not in known_services():
            raise DispatchError(
                "Unknown service '{0}'. Known services: {1}.".format(
                    request.service, services))
        operations = ', '.join(known_operations(request.service))
        raise DispatchError(
            "Unknown operation '{0}' for service '{1}'. "
            "Known operations: {2}.".format(
                request.operation, request.service, operations))

    if not platform_supports(platform, request.service, request.operation):
        raise DispatchError(
            "Platform '{0}' does not support gNOI {1}/{2}. "
            "Set platform: auto to attempt the operation anyway and let the "
            "device decide.".format(platform, request.service, request.operation))

    if spec.destructive and not confirm:
        raise DispatchError(
            "Operation {0}/{1} is destructive and requires confirm: true.".format(
                request.service, request.operation))

    if request.check_mode and spec.mutating:
        return {
            'changed': True,
            'skipped_rpc': True,
            'service': request.service,
            'operation': request.operation,
            'msg': "Check mode: RPC was not executed.",
        }

    result = spec.handler(request)

    # Normalise the handler result and stamp service/operation for context.
    result.setdefault('changed', False)
    result.setdefault('msg', '')
    result['service'] = request.service
    result['operation'] = request.operation
    return result
