#!/bin/bash
# fetch_device_certs.sh
# Helper script to fetch SSL certificates from Cisco IOS XE devices
# and store them for use with gNMI

set -e

CERT_DIR="${CERT_DIR:-./certs}"
PORT="${PORT:-9339}"

usage() {
    echo "Usage: $0 <device_ip> [device_name]"
    echo ""
    echo "Fetch SSL certificate from a Cisco IOS XE device for gNMI"
    echo ""
    echo "Arguments:"
    echo "  device_ip    IP address or hostname of the device"
    echo "  device_name  Optional name for the certificate file (default: device_ip)"
    echo ""
    echo "Environment variables:"
    echo "  CERT_DIR     Directory to store certificates (default: ./certs)"
    echo "  PORT         gNMI port (default: 9339)"
    echo ""
    echo "Example:"
    echo "  $0 10.85.134.65 router1"
    echo "  $0 192.168.1.1"
    exit 1
}

if [ $# -lt 1 ]; then
    usage
fi

DEVICE_IP="$1"
DEVICE_NAME="${2:-$DEVICE_IP}"
CERT_FILE="${CERT_DIR}/${DEVICE_NAME}-cert.pem"

# Create certificate directory if it doesn't exist
mkdir -p "$CERT_DIR"

echo "Fetching SSL certificate from ${DEVICE_IP}:${PORT}..."

# Fetch the certificate
if openssl s_client -connect "${DEVICE_IP}:${PORT}" -showcerts </dev/null 2>/dev/null | \
   openssl x509 -outform PEM > "$CERT_FILE"; then

    echo "✓ Certificate saved to: $CERT_FILE"

    # Display certificate information
    echo ""
    echo "Certificate details:"
    echo "-------------------"
    openssl x509 -in "$CERT_FILE" -noout -subject -issuer -dates

    echo ""
    echo "To use this certificate in your playbook:"
    echo "  ca_cert: \"$CERT_FILE\""

else
    echo "✗ Failed to fetch certificate from ${DEVICE_IP}:${PORT}"
    rm -f "$CERT_FILE"
    exit 1
fi
