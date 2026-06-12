#!/usr/bin/env bash
#
# Copyright 2025 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0
#
# Regenerate the vendored gNOI Python gRPC stubs from the .proto sources in
# this directory.
#
# The generated *_pb2.py / *_pb2_grpc.py files are committed to the repository
# so that end users never need protoc or grpcio-tools installed. Only run this
# script when the vendored .proto definitions change.
#
# Requirements:
#   pip install grpcio-tools
#
# Usage:
#   ./regenerate.sh
#
set -euo pipefail

PROTO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PROTOS=(
  types.proto
  cert.proto
  os.proto
  factory_reset.proto
)

echo "Generating gNOI stubs in ${PROTO_DIR}"

python -m grpc_tools.protoc \
  -I "${PROTO_DIR}" \
  --python_out="${PROTO_DIR}" \
  --grpc_python_out="${PROTO_DIR}" \
  "${PROTOS[@]/#/${PROTO_DIR}/}"

# protoc emits top-level absolute imports (e.g. `import types_pb2`). Rewrite
# them to package-relative imports (`from . import types_pb2`) so the stubs
# import correctly when this directory is used as a Python package.
for generated in "${PROTO_DIR}"/*_pb2.py "${PROTO_DIR}"/*_pb2_grpc.py; do
  [ -e "${generated}" ] || continue
  # Match lines like: import cert_pb2 as cert__pb2
  perl -0pi -e 's/^import (\w+_pb2)( as |\n)/from . import $1$2/mg' "${generated}"
done

echo "Done. Generated files:"
ls -1 "${PROTO_DIR}"/*_pb2.py "${PROTO_DIR}"/*_pb2_grpc.py
