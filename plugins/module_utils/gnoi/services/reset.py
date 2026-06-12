# -*- coding: utf-8 -*-

# Copyright 2025 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Factory Reset service handlers (factory_reset.proto).

Implements the gNOI ``gnoi.factory_reset.FactoryReset`` RPC supported by Cisco
IOS XE:

    - start -> Start

The Start RPC wipes device state and reboots into the factory-default
condition while preserving the current OS image. It is only accepted when the
device is in a provisioned state (a signed, non-self-signed certificate is in
use); otherwise the device returns ``FAILED_PRECONDITION``.
"""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

import grpc

from ..client import GnoiOperationError, rpc_error_to_operation_error
from ..protos import factory_reset_pb2
from ..registry import register


@register('factory_reset', 'start', mutating=True, destructive=True,
          description='Factory reset the device (wipes state and reboots).')
def start(request):
    """Trigger a factory reset.

    Destructive: requires ``confirm: true``. On IOS XE, ``factory_os`` rollback
    is not supported and will be rejected by the device; ``zero_fill`` support
    is platform dependent.
    """
    zero_fill = bool(request.args.get('zero_fill', False))
    factory_os = bool(request.args.get('factory_os', False))
    retain_certs = bool(request.args.get('retain_certs', False))

    start_request = factory_reset_pb2.StartRequest(
        factory_os=factory_os,
        zero_fill=zero_fill,
        retain_certs=retain_certs,
    )

    try:
        response = request.client.reset_stub.Start(
            start_request,
            metadata=request.client.metadata,
            timeout=request.timeout,
        )
    except grpc.RpcError as exc:
        raise rpc_error_to_operation_error(exc, 'factory_reset', 'start')

    which = response.WhichOneof('response')
    if which == 'reset_error':
        error = response.reset_error
        reasons = []
        if error.factory_os_unsupported:
            reasons.append('factory_os_unsupported')
        if error.zero_fill_unsupported:
            reasons.append('zero_fill_unsupported')
        if error.other:
            reasons.append('other')
        detail = error.detail or ', '.join(reasons) or 'unknown error'
        raise GnoiOperationError(
            "gNOI factory_reset/start failed: {0}".format(detail),
            grpc_message=detail)

    return {
        'changed': True,
        'msg': "Factory reset started (device rebooting to factory defaults).",
        'response': {
            'zero_fill': zero_fill,
            'factory_os': factory_os,
            'retain_certs': retain_certs,
            'reset_state': 'started',
        },
    }
