# Cisco IOS XE gNMI Implementation - Caveats and Requirements

This document outlines the specific requirements, restrictions, and best practices for using gNMI with Cisco IOS XE devices based on the official Cisco Programmability Configuration Guide (IOS XE 17.18.x).

## Official Documentation Reference
**Source:** [Cisco Programmability Configuration Guide, IOS XE 17.18.x - gNMI Protocol](https://www.cisco.com/c/en/us/td/docs/ios-xml/ios/prog/configuration/1718/b-1718-programmability-cg/gnmi.html)

---

## 1. Encoding Support

### ✅ Supported Encodings
- **JSON_IETF** (Value: 4) - **RECOMMENDED**
  - Conforms to RFC 7951
  - Properly handles YANG namespaces
  - Default encoding for this module

- **JSON** (Value: 0) - Supported
  - Basic JSON encoding
  - Less namespace-aware than JSON_IETF

- **PROTO** (Value: 2) - **Limited Support**
  - Only supported from IOS XE Dublin 17.11.1+
  - **ONLY works with Subscribe RPC**
  - **NOT supported for GET or SET operations**
  - Provides scalar (TypedValue) values for better precision

### ❌ Unsupported Encodings
- **BYTES** (Value: 1) - NOT supported on Cisco IOS XE
- **ASCII** (Value: 3) - NOT supported on Cisco IOS XE

**Impact:** Using BYTES or ASCII encoding will result in `UNIMPLEMENTED` error from the device.

---

## 2. Port Configuration

### Default Ports
- **Secure (TLS) Mode:** Port **9339** (default)
- **Insecure Mode:** Port **50052** (default)

### Configuration
```python
# Secure mode (recommended for production)
client = GnmiClient(
    host='192.168.1.1',
    port=9339,
    insecure=False,
    ca_cert='/path/to/rootCA.pem',
    client_cert='/path/to/client.crt',
    client_key='/path/to/client.key'
)

# Insecure mode (testing only)
client = GnmiClient(
    host='192.168.1.1',
    port=50052,
    insecure=True
)
```

---

## 3. Device Configuration Requirements

### Minimum Configuration for gNMI

To enable gNMI on Cisco IOS XE devices, apply the following configuration:

```cisco
configure terminal
!
! Required: Enable internal service for self-signed certificates
service internal
!
! Enable gNMI server with secure settings
gnxi
 gnxi secure-allow-self-signed-trustpoint
 gnxi secure-password-auth
 gnxi secure-server
!
! Configure user authentication
username admin privilege 15 secret your-password-here
!
end
write memory
```

### Configuration Details

| Command | Purpose |
|---------|---------|
| `service internal` | **Required** to allow self-signed certificates |
| `gnxi secure-allow-self-signed-trustpoint` | Allow self-signed certificates for gNMI |
| `gnxi secure-password-auth` | Enable password-based authentication |
| `gnxi secure-server` | Start the gNMI server (default port 9339) |

### Port Configuration

- **Default Secure Port:** 9339 (TLS enabled)
- **Default Insecure Port:** 50052 (no TLS)

**Production Recommendation:** Always use secure port (9339) with proper PKI certificates instead of self-signed certificates.

### Production Certificate Setup (Optional)

For production deployments, configure proper PKI certificates:

```cisco
crypto pki trustpoint GNMI-TRUSTPOINT
 enrollment terminal
 subject-name CN=switch.example.com
 revocation-check none

crypto pki authenticate GNMI-TRUSTPOINT
crypto pki enroll GNMI-TRUSTPOINT

gnxi
 gnxi secure-trustpoint GNMI-TRUSTPOINT
 gnxi secure-server
```

---

## 4. Authentication

### Username/Password Authentication
- Credentials are passed as **metadata** in each RPC
- Both username and password are required
- Validated against device AAA configuration

```python
# Credentials passed as metadata
metadata = [('username', 'admin'), ('password', 'cisco123')]
```

### TLS Certificate Authentication
- Requires properly signed certificates
- CA certificate for server validation
- Optional client certificate for mutual TLS
- Certificates must be in PEM format

**Certificate Creation Example:**
```bash
# Create CA
openssl genrsa -out rootCA.key 2048
openssl req -x509 -new -nodes -key rootCA.key -sha256 -out rootCA.pem

# Create device certificate
openssl genrsa -out device.key 2048
openssl req -new -key device.key -out device.csr
openssl x509 -req -in device.csr -CA rootCA.pem -CAkey rootCA.key -out device.crt

# Create client certificate
openssl genrsa -out client.key 2048
openssl req -new -key client.key -out client.csr
openssl x509 -req -in client.csr -CA rootCA.pem -CAkey rootCA.key -out client.crt
```

---

## 5. YANG Namespace Requirements

### JSON_IETF Namespace Prefixes
When using JSON_IETF encoding, **YANG module prefixes are required** when the namespace of child elements differs from the parent.

**Example:**
```json
// CORRECT - Uses oc-vlan prefix for augmented element
{
  "openconfig-interfaces:config": {
    "oc-vlan:routed-vlan": true
  }
}

// INCORRECT - Missing prefix
{
  "openconfig-interfaces:config": {
    "routed-vlan": true  // ERROR: Namespace conflict
  }
}
```

**Common Prefixes:**
- `openconfig-interfaces` → `oc-if`
- `openconfig-vlan` → `oc-vlan`
- `Cisco-IOS-XE-native` → `ios`

---

## 5. Configuration Persistence

### Automatic Persistence (IOS XE 17.3.1+)
- **All successful SetRequest changes automatically persist** across device restarts
- Changes are automatically saved to startup-config
- No need to manually execute `write memory` or SaveConfig RPC
- **Enabled by default and cannot be disabled**

**Important:**
All changes in running-config are saved, even if modified by processes other than gNMI, when a SetRequest is issued.

---

## 6. GET Request Restrictions

### Unsupported Features
- **Operational data filtering:** Cannot filter operational data in GetRequest
- **Use models:** Schema definition models not supported in GetRequest
- **Alias:** Alternate naming in GetResponse not supported
- **Delete:** Delete field in GetResponse not supported

### Supported Features
- ✅ Path wildcards (implicit and explicit)
- ✅ Multiple paths in single request
- ✅ All data types: ALL, CONFIG, STATE, OPERATIONAL

---

## 7. SET Request Behavior

### Transaction Semantics
- **All operations in a SetRequest are atomic**
- If any operation fails, entire transaction is rolled back
- No partial application of changes

### Operations Supported
- ✅ **Delete:** Remove configuration at specified paths
- ✅ **Replace:** Overwrite configuration at path
- ✅ **Update:** Merge with existing configuration

**Example:**
```python
# All or nothing - if any fails, all roll back
result = client.set(
    delete=['/interfaces/interface[name=Gi1]/config/description'],
    update=[
        ('/interfaces/interface[name=Gi1]/config/mtu', 9000),
        ('/interfaces/interface[name=Gi1]/config/enabled', True)
    ]
)
```

---

## 8. Path Wildcards

### Implicit Wildcards
Omit key values to match all list elements:
```python
# Get all interface descriptions
path = '/interfaces/interface/config/description'
```

### Explicit Wildcards

**Asterisk (*) - Key wildcard:**
```python
# Get all interface descriptions (explicit)
path = '/interfaces/interface[name=*]/config/description'
```

**Ellipsis (...) - Multi-level wildcard:**
```python
# Get all description fields under interfaces
path = '/interfaces/.../description'
```

---

## 9. Error Handling

### Common Error Messages

**Invalid Path:**
```
StatusCode.TERMINATED: An error occurred while parsing provided xpath:
unknown tag: "invalidpath"
```

**Unsupported Encoding:**
```
StatusCode.UNIMPLEMENTED: Requested encoding "ASCII" not supported
```

**Empty Result:**
```
StatusCode.NOT_FOUND: Empty set returned for path "/interfaces/nonexistent"
```

**PROTO with GET/SET:**
```
PROTO encoding is NOT supported for GET operations on Cisco IOS XE.
PROTO encoding only works with Subscribe RPC.
Please use JSON_IETF or JSON encoding instead.
```

---

## 10. Device Configuration

### Enable gNMI on Cisco IOS XE

**Secure Mode (Recommended):**
```cisco
configure terminal
gnxi
gnxi secure-trustpoint trustpoint1
gnxi secure-server
gnxi secure-client-auth
gnxi secure-port 9339
end
```

**Insecure Mode (Testing Only):**
```cisco
configure terminal
gnxi
gnxi server
gnxi port 50052
end
```

**Verify Status:**
```cisco
show gnxi state
```

---

## 11. Platform Support

### Cisco IOS XE Version Requirements

| Feature | Minimum Version |
|---------|----------------|
| Basic gNMI (GET/SET) | IOS XE Fuji 16.8.1a |
| PROTO Encoding | IOS XE Dublin 17.11.1 |
| Config Persistence | IOS XE Amsterdam 17.3.1 |
| IPv6 Support | IOS XE Dublin 17.10.1 |
| Named Method List AAA | IOS XE Cupertino 17.9.1 |

### Supported Platforms
- Cisco Catalyst 9000 Series Switches (9200, 9300, 9400, 9500, 9600)
- Cisco ASR 900/920/1000 Series Routers
- Cisco Catalyst 8000 Series Edge Platforms
- Cisco Catalyst 9800 Wireless Controllers
- Cisco cBR-8 Converged Broadband Router
- Cisco ISR 1000/4000 Series Routers

---

## 12. Best Practices

### ✅ Recommended Practices

1. **Use JSON_IETF Encoding**
   - Most compatible with Cisco IOS XE
   - Proper namespace handling
   - RFC 7951 compliant

2. **Use Secure Mode in Production**
   - Enable TLS with proper certificates
   - Use strong passwords
   - Enable client authentication

3. **Validate Paths Before Execution**
   - Use Capabilities RPC to verify supported models
   - Test paths with GET before SET

4. **Handle Errors Gracefully**
   - Check RPC status codes
   - Parse error messages for debugging
   - Implement retry logic for transient failures

5. **Use Specific Paths**
   - Avoid overly broad wildcards
   - Request only needed data
   - Minimize response size

### ❌ Common Pitfalls

1. **Using BYTES/ASCII Encoding**
   - Will fail with UNIMPLEMENTED error

2. **Using PROTO with GET/SET**
   - PROTO only works with Subscribe RPC

3. **Missing YANG Prefixes**
   - Will cause namespace errors with JSON_IETF

4. **Assuming Partial Transactions**
   - All SetRequest operations are atomic

5. **Not Handling Certificate Validation**
   - Can cause connection failures in secure mode

---

## 13. Module Configuration Example

### Ansible Playbook with All Caveats Addressed

```yaml
---
- name: Configure Cisco IOS XE via gNMI (Best Practices)
  hosts: iosxe_devices
  gather_facts: no

  tasks:
    - name: Get interface configuration
      cisco.gnmi.gnmi:
        host: "{{ inventory_hostname }}"
        port: 9339                    # Secure port
        username: "{{ ansible_user }}"
        password: "{{ ansible_password }}"
        operation: get
        encoding: json_ietf           # RECOMMENDED encoding
        datatype: config
        paths:
          - /interfaces/interface[name=GigabitEthernet1]
        insecure: false               # Use TLS validation
        ca_cert: /path/to/rootCA.pem
        client_cert: /path/to/client.crt
        client_key: /path/to/client.key
      register: interface_config

    - name: Update interface with proper namespace
      cisco.gnmi.gnmi:
        host: "{{ inventory_hostname }}"
        port: 9339
        username: "{{ ansible_user }}"
        password: "{{ ansible_password }}"
        operation: set
        state: present
        encoding: json_ietf
        config:
          - path: /interfaces/interface[name=GigabitEthernet1]/config
            value:
              openconfig-interfaces:description: "Managed by Ansible"
              openconfig-interfaces:enabled: true
              openconfig-interfaces:mtu: 9000
        backup: true                  # Backup before change (optional)
      register: set_result

    - name: Subscribe to interface statistics (PROTO allowed here)
      cisco.gnmi.gnmi:
        host: "{{ inventory_hostname }}"
        port: 9339
        username: "{{ ansible_user }}"
        password: "{{ ansible_password }}"
        operation: subscribe
        encoding: proto               # PROTO works with Subscribe
        subscribe_mode: stream
        subscribe_duration: 60
        subscriptions:
          - path: /interfaces/interface[name=GigabitEthernet1]/state/counters
            mode: sample
            sample_interval: 10
      register: telemetry_data
```

---

## 14. Troubleshooting

### Verify gNMI is Running
```cisco
show gnxi state
```

### Check Certificate Configuration
```cisco
show crypto pki certificates
show crypto pki trustpoints
```

### Enable Debug (Use with Caution)
```cisco
debug gnxi events
debug gnxi errors
```

### Test Connectivity
```python
from gnmi import gnmi_pb2, gnmi_pb2_grpc
import grpc

# Test Capabilities RPC
channel = grpc.secure_channel('device:9339', credentials)
stub = gnmi_pb2_grpc.gNMIStub(channel)
response = stub.Capabilities(gnmi_pb2.CapabilityRequest())
print(response)
```

---

## 15. Additional Resources

- [Cisco gNMI Configuration Guide (IOS XE 17.18.x)](https://www.cisco.com/c/en/us/td/docs/ios-xml/ios/prog/configuration/1718/b-1718-programmability-cg/gnmi.html)
- [gNMI Specification (GitHub)](https://github.com/openconfig/reference/blob/master/rpc/gnmi/gnmi-specification.md)
- [gNMI Path Encoding Conventions](https://github.com/openconfig/reference/blob/master/rpc/gnmi/gnmi-path-conventions.md)
- [RFC 7951 - JSON Encoding of YANG Data](https://tools.ietf.org/html/rfc7951)
- [Cisco DevNet - IOS XE Programmability](https://developer.cisco.com/site/ios-xe/)

---

## Version History

| Date | Version | Changes |
|------|---------|---------|
| 2025-10-29 | 1.0 | Initial documentation based on IOS XE 17.18.x guide |

---

**Note:** This implementation has been validated against the official Cisco IOS XE 17.18.x Programmability Configuration Guide to ensure compliance with all documented restrictions and requirements.
