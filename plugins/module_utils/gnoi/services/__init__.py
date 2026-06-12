# -*- coding: utf-8 -*-

# Copyright 2025 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""gNOI service handlers.

Importing this package registers every handler with the registry as a side
effect, so the module layer only needs ``import ...gnoi.services``.
"""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

from . import cert  # noqa: F401
from . import os    # noqa: F401
from . import reset  # noqa: F401
