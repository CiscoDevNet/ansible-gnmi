# -*- coding: utf-8 -*-

# Copyright 2025 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Service/operation registry and platform capability model for gNOI.

The ``cisco.gnmi.gnoi`` module is a single generic module that dispatches to
service handlers based on ``service`` and ``operation`` parameters. This
module provides:

    - A registry mapping ``(service, operation)`` to a handler function along
      with metadata (whether the operation mutates state, whether it is
      destructive and therefore requires explicit confirmation).
    - A per-platform capability model so that additional platforms (NX-OS,
      IOS XR) can be described without changing the dispatch logic.

Handlers are registered with the :func:`register` decorator from each service
module under :mod:`...gnoi.services`.
"""

from __future__ import absolute_import, division, print_function
__metaclass__ = type


class OperationSpec:
    """Describes a single gNOI operation and how the module should treat it.

    Attributes:
        service: Service name, e.g. ``'os'``.
        operation: Operation name, e.g. ``'install'``.
        handler: Callable ``handler(request) -> dict`` implementing the RPC.
        mutating: ``True`` if the operation changes device state. Mutating
            operations are skipped in check mode.
        destructive: ``True`` if the operation is destructive or service
            affecting (e.g. reboots the device, wipes state) and therefore
            requires ``confirm: true``.
        description: Short human-readable summary.
    """

    def __init__(self, service, operation, handler,
                 mutating=True, destructive=False, description=''):
        self.service = service
        self.operation = operation
        self.handler = handler
        self.mutating = mutating
        self.destructive = destructive
        self.description = description


# (service, operation) -> OperationSpec
_REGISTRY = {}


def register(service, operation, mutating=True, destructive=False, description=''):
    """Decorator that registers a handler for ``(service, operation)``."""

    def decorator(func):
        _REGISTRY[(service, operation)] = OperationSpec(
            service=service,
            operation=operation,
            handler=func,
            mutating=mutating,
            destructive=destructive,
            description=description,
        )
        return func

    return decorator


def get_operation(service, operation):
    """Return the :class:`OperationSpec` for ``(service, operation)`` or None."""
    return _REGISTRY.get((service, operation))


def known_services():
    """Return the sorted set of registered service names."""
    return sorted({service for service, _ in _REGISTRY})


def known_operations(service):
    """Return the sorted operations registered for ``service``."""
    return sorted(op for svc, op in _REGISTRY if svc == service)


# ---------------------------------------------------------------------------
# Platform capability model
# ---------------------------------------------------------------------------
#
# Maps a platform to the services and operations it is known to support. This
# is used for pre-flight validation and documentation. The ``auto`` platform
# performs no gating: the operation is attempted and the device decides
# (returning UNIMPLEMENTED if unsupported).
#
# Only IOS XE is fully populated for the initial release. NX-OS and IOS XR are
# present as empty placeholders so future handlers can be added without
# changing the dispatch logic.

PLATFORM_CAPABILITIES = {
    'iosxe': {
        'cert': {'install', 'rotate', 'revoke', 'get', 'can_generate_csr'},
        'os': {'install', 'activate', 'verify'},
        'factory_reset': {'start'},
    },
    'nxos': {},
    'iosxr': {},
}


def platform_supports(platform, service, operation):
    """Return whether ``platform`` is known to support ``service/operation``.

    For ``auto`` (or any platform without a defined capability map) this
    returns ``True`` so the operation is attempted and the device decides.
    """
    if not platform or platform == 'auto':
        return True
    capabilities = PLATFORM_CAPABILITIES.get(platform)
    if not capabilities:
        # Unknown platform: do not gate, let the device respond.
        return True
    return operation in capabilities.get(service, set())
