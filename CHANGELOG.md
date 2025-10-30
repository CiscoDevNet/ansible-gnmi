# Changelog

All notable changes to the Cisco IOS XE gNMI Ansible Collection will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-10-29

### Added

#### Core Functionality
- Initial release of Cisco IOS XE gNMI Ansible Collection
- `cisco_iosxe_gnmi` module for gNMI operations
- `GnmiClient` module utility for gRPC/gNMI operations
- Support for GET, SET, and Subscribe operations

#### Features
- **GET Operations**
  - Retrieve configuration and operational state
  - Support for multiple paths in single request
  - Datatype filtering (all, config, state, operational)
  - JSON and JSON_IETF encoding support

- **SET Operations**
  - Update configurations (merge)
  - Replace configurations
  - Delete configurations
  - Atomic transaction support
  - Multiple path-value pairs per operation

- **Subscribe Operations**
  - Once mode for snapshots
  - Sample mode for periodic data
  - On-change mode for event-driven updates
  - Stream, once, and poll subscription modes

#### Ansible Best Practices
- Idempotency support for all operations
- Check mode (dry-run) support
- Diff mode with before/after comparison
- Configuration backup functionality
- Comprehensive error handling
- Detailed return values

#### Cisco IOS XE Compliance
- Full compliance with Cisco gNMI specification
- JSON_IETF (RFC 7951) recommended encoding
- Proper handling of encoding restrictions
- PROTO encoding validation (Subscribe only)
- Automatic configuration persistence (IOS XE 17.3.1+)
- Support for secure (9339) and insecure (50052) ports

#### Security
- TLS/SSL support
- Certificate validation
- CA certificate support
- Client certificate authentication (mutual TLS)
- Insecure mode option (for testing)
- Password no-log protection

#### Documentation
- Comprehensive README with examples
- CISCO_GNMI_CAVEATS.md for platform-specific info
- Module documentation with all parameters
- Example playbooks for all operations
- Installation guide
- Troubleshooting guide
- API reference documentation

#### Examples
- `get_operations.yml` - Complete GET examples
- `set_operations.yml` - Complete SET examples with backup/diff
- `subscribe_operations.yml` - Complete Subscribe examples
- `inventory.ini` - Sample inventory configuration

#### Testing
- Unit tests for GnmiClient
- Unit tests for cisco_iosxe_gnmi module
- Mock-based testing framework
- Code coverage reporting
- pytest configuration
- Test requirements

#### Development Tools
- `install.sh` - Automated installation script
- `Makefile` - Common development tasks
- `CONTRIBUTING.md` - Contribution guidelines
- `pytest.ini` - Test configuration
- Requirements files for dependencies

### Technical Details

#### Platform Support
- Cisco IOS XE 16.8.1a+ (basic gNMI)
- Cisco IOS XE 17.3.1+ (auto config persistence)
- Cisco IOS XE 17.11.1+ (PROTO encoding for Subscribe)

#### Dependencies
- Python 3.8+
- Ansible Core 2.12+
- grpcio >= 1.50.0
- grpcio-tools >= 1.50.0
- protobuf >= 4.21.0
- cisco-gnmi >= 1.0.0
- cryptography >= 38.0.0

#### Known Limitations
- BYTES encoding not supported (Cisco IOS XE restriction)
- ASCII encoding not supported (Cisco IOS XE restriction)
- PROTO encoding only for Subscribe RPC (Cisco IOS XE restriction)
- Stream mode Subscribe has simplified implementation

### Notes

This is the initial production-ready release providing feature parity with Ansible NETCONF/RESTCONF modules for Cisco IOS XE devices using gNMI protocol.

For complete documentation and Cisco-specific requirements, see:
- README.md
- CISCO_GNMI_CAVEATS.md

---

## [Unreleased]

### Planned Features
- Integration tests with real devices
- Enhanced Subscribe streaming support
- gNMI Capabilities RPC support
- Performance optimizations
- Extended error diagnostics
- Prometheus metrics export
- Batch operation optimization

### Under Consideration
- Multi-device parallel operations
- Configuration templates
- YANG model validation
- Diff format customization
- Backup rotation/retention
- Rollback functionality
