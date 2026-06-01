# Changelog

All notable changes to this collection will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this collection adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.0.2] - 2026-06-01

### Changed

- **CI workflow actions are now SHA-pinned.** `actions/checkout` and
  `actions/setup-python` in `.github/workflows/ci.yml` are pinned to full
  commit SHAs with version comments, matching the publish workflow and
  reducing supply-chain risk.
- **Hoisted `cryptography` imports to module top** in
  `plugins/module_utils/gnmi_client.py`, gated by `HAS_CRYPTOGRAPHY`. The
  CN-extraction code now skips gracefully when `cryptography` is not
  installed instead of relying on a deferred import inside `connect()`.
- **Clarified subscribe-mode warning text.** When a per-subscription mode
  is not in a platform's supported list, the warning now says the mode
  will be sent to the device which is expected to reject it, instead of
  the misleading "Defaulting may cause unexpected behaviour" (the code
  does not default the mode).

### Fixed

- **Better error messages for certificate file failures.** Missing,
  unreadable, or otherwise inaccessible `ca_cert` / `client_cert` /
  `client_key` files now raise `GnmiConnectionError` with the specific
  file path and cause (e.g. "ca_cert file not found: /path/to/ca.pem")
  instead of being wrapped in a generic "Failed to connect" message.

## [3.0.1] - 2026-06-01

### Fixed

- **Insecure mode now actually disables TLS.** `insecure: true` previously
  built a `secure_channel` with default SSL credentials and an empty
  `GRPC_DEFAULT_SSL_ROOTS_FILE_PATH`, which still attempted certificate
  verification and silently mutated the process environment. It now creates
  a true plaintext `grpc.insecure_channel`, matching user expectations and
  the gNMI convention for non-TLS deployments
  (`plugins/module_utils/gnmi_client.py`).
- **Backup files are no longer written in check mode.** `_create_backup()`
  was invoked before the `check_mode` guard in `execute_set()`, so running
  a playbook with `--check` would create real backup files on disk. The
  helper now short-circuits when `check_mode` is set
  (`plugins/modules/gnmi.py`).
- **Removed misleading `failed: False` key from the module result dict.**
  Ansible signals failure via `fail_json()`, not via a `failed` key in the
  returned data, so the key was always `False` and could confuse consumers
  of the result (`plugins/modules/gnmi.py`).

## [3.0.0] - 2026-06-01

### Breaking Changes

- **Removed `nokia_sros` and `arista_eos` from the `platform` argument's
  `choices`** in `plugins/modules/gnmi.py`. Modules that pass either value
  will now fail argument validation. Both profiles were placeholder stubs
  with no real restrictions (only a default port hint) and are removed so
  the collection's surface area matches its tested platform support.
- **Removed `nokia_sros` and `arista_eos` entries from `PLATFORM_PROFILES`**
  in `plugins/module_utils/gnmi_client.py`.

### Added

- **README: "Using with Other gNMI Implementations" section.** Documents
  how to use the collection against any OpenConfig gNMI-compliant device by
  leaving `platform: auto` and configuring `port`, `encoding`, TLS, and
  `origin` explicitly.

### Removed

- Sanity ignores `validate-modules:doc-choices-do-not-match-spec` and
  `validate-modules:doc-default-does-not-match-spec` for
  `plugins/modules/gnmi.py` are no longer needed and have been dropped
  from `tests/sanity/ignore-2.15..2.18.txt`.

## [2.0.3] - 2026-06-01

### Changed
- **Documentation scoped to Cisco platforms.** README, `galaxy.yml`
  description, `CONTRIBUTING.md`, and the module DOCUMENTATION block now
  describe support for Cisco IOS XE, IOS XR, and NX-OS only. Internal
  comments referring to other vendors were trimmed.
- The `platform` argument's documented `choices` are now
  `['auto', 'iosxe', 'iosxr', 'nxos']`.

### Unchanged (intentional)
- The `argument_spec` for `platform` still accepts `nokia_sros` and
  `arista_eos`, and `PLATFORM_PROFILES` in `gnmi_client.py` still contains
  those entries. This avoids a breaking change for any user already passing
  those values; they are simply no longer advertised.
- `tests/sanity/ignore-2.15..2.18.txt` add
  `validate-modules:doc-choices-do-not-match-spec` and
  `validate-modules:doc-default-does-not-match-spec` for `plugins/modules/gnmi.py`
  to account for the intentional documentation/spec divergence above.

## [2.0.2] - 2026-06-01

### Fixed
- **`galaxy.yml`** – removed `license_file: LICENSE` which conflicted with
  `license: [Apache-2.0]`. Galaxy now rejects collections that declare both
  keys, which blocked the 2.0.1 publish.

### Changed
- **`.github/workflows/galaxy-publish.yml`** – bumped
  `actions/checkout` from v4.1.5 to v5.0.1 to run on Node.js 24 ahead of
  the GitHub Actions Node 20 deprecation.

## [2.0.1] - 2025-03-06

### Fixed
- **SNMP MIB test playbook** – corrected gNMI path from `/IF-MIB:IF-MIB` to
  `/IF-MIB:IF-MIB/ifTable`, added explicit `encoding: json_ietf` and
  increased timeout to 60 seconds.
- **`subscribe_duration` parameter** – was declared in `argument_spec` but
  never passed to the client; now wired through as the gRPC deadline for
  Subscribe RPCs.
- **`pytest.ini`** – changed `[tool:pytest]` header to `[pytest]` so pytest
  discovers configuration correctly; extracted coverage settings to
  `.coveragerc`.
- **`tests/requirements.txt`** – comment lines were missing `#` prefix,
  causing pip parse errors.
- **Missing `plugins/modules/__init__.py`** – added empty init file for
  proper Python package recognition.
- **`.gitignore` overly broad patterns** – `*token*`, `*secret*`,
  `*password*` replaced with specific file-extension patterns to avoid
  accidentally ignoring legitimate source files.

### Changed
- **`galaxy.yml`** – bumped version to 2.0.1; added explicit
  `license: [Apache-2.0]`; removed `requirements.txt` from `build_ignore`
  so `meta/execution-environment.yml` can reference it in built artifacts.
- **`test_inventory.ini`** – added `[iosxe_devices:children]` group (four
  playbooks target `hosts: iosxe_devices`) and set `gnmi_platform=iosxe`.

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
