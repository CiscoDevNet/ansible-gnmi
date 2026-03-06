# Changelog

All notable changes to this collection will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this collection adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2025-01-29

### Breaking Changes
- Renamed namespace from `jeremycohoe.iosxe_gnmi` to `cisco.gnmi`.
- Renamed module from `cisco_iosxe_gnmi` to `gnmi`.
- Removed `ascii` and `bytes` from encoding choices (never supported by gNMI spec).
- PROTO encoding on IOS XE now raises `GnmiOperationError` only when
  `platform: iosxe` is explicitly set; otherwise proceeds normally.

### Added
- **Subscribe RPC support** – `operation: subscribe` with `stream`, `once`, and
  `poll` modes.
- **`platform` parameter** – optional vendor hint (`auto`, `iosxe`, `iosxr`,
  `nxos`, `nokia_sros`, `arista_eos`) to enable platform-specific validation.
- **Platform profiles** – built-in default ports and encoding restrictions per
  vendor.
- **`origin` parameter** – explicit gNMI path origin for SET operations (was
  missing in v1).
- **`warn_callback`** – client emits platform warnings through Ansible's
  `module.warn()`.
- Auto-detection of path origin for Cisco IOS XR and NX-OS namespace prefixes.
- Context manager support (`with GnmiClient(...) as c:`).
- CI workflow (GitHub Actions) for sanity and unit tests.
- `meta/execution-environment.yml` for Ansible EE builds.
- Plugin routing in `meta/runtime.yml` — old module name redirects to `gnmi`.
- Comprehensive unit tests for both client and module.

### Fixed
- **Duplicate `run()` method** in the Ansible module (first was an empty stub).
- **`argument_spec` mismatch** – `operation` choices now include `subscribe`;
  encoding choices match DOCUMENTATION block.
- **`origin` not passed to SET** – `execute_set()` now forwards `origin` to
  `client.set()`.
- **Bare `except:` clause** in `connect()` replaced with `except Exception`.
- **Global env mutation** – `os.environ['GRPC_DEFAULT_SSL_ROOTS_FILE_PATH']`
  is only set in insecure mode.
- Hardcoded passwords removed from EXAMPLES block (use Jinja2 variables).
- Real device IPs removed from `test_inventory.ini`.

### Changed
- `gnmi_client.py` rewritten as vendor-neutral with platform profiles.
- Class renamed from `CiscoIosXeGnmi` to `GnmiModule`.
- `_build_path()` origin auto-detection generalised beyond Cisco IOS XE.
- All error messages no longer reference "Cisco IOS XE" specifically.
- `requirements.txt` simplified (removed upper-bound caps).
- `README.md` rewritten for multi-vendor audience.

## [1.0.4] - 2025-01-28

### Added
- Initial public release as `jeremycohoe.iosxe_gnmi`.
- GET and SET operations for Cisco IOS XE.
- TLS and insecure connection modes.
- Check mode and diff mode.
- Configuration backup.
