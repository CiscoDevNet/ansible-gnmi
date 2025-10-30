# Ansible Integration Guide

This document outlines the paths to integrate the Cisco IOS XE gNMI collection into the broader Ansible ecosystem.

## Integration Options

### 1. Ansible Galaxy (Immediate Availability)

**Best for:** Quick distribution and user adoption

#### Steps to Publish

1. **Prepare the Collection**
   ```bash
   # Update galaxy.yml with proper metadata
   vim galaxy.yml

   # Build the collection
   ansible-galaxy collection build
   ```

2. **Create Ansible Galaxy Account**
   - Visit https://galaxy.ansible.com
   - Sign in with GitHub
   - Create namespace (e.g., 'cisco' or your username)

3. **Publish to Galaxy**
   ```bash
   # Upload the tar.gz file through web interface or API
   ansible-galaxy collection publish cisco-iosxe_gnmi-1.0.0.tar.gz --api-key=<your-key>
   ```

4. **Users Install Via**
   ```bash
   ansible-galaxy collection install cisco.iosxe_gnmi
   ```

**Advantages:**
- ✅ Fast deployment
- ✅ Full control over releases
- ✅ Easy for users to find and install
- ✅ Automatic versioning and dependency management

**Requirements:**
- GitHub repository (for source code)
- Ansible Galaxy account
- Proper galaxy.yml metadata
- Documentation (README, examples)

---

### 2. Contribute to cisco.ios Collection

**Best for:** Integration with existing Cisco modules

**Repository:** https://github.com/ansible-collections/cisco.ios

#### Steps to Contribute

1. **Fork and Clone**
   ```bash
   git clone https://github.com/YOUR_USERNAME/cisco.ios.git
   cd cisco.ios
   ```

2. **Add Your Module**
   ```bash
   # Copy your module
   cp /path/to/cisco_iosxe_gnmi.py plugins/modules/
   cp /path/to/gnmi_client.py plugins/module_utils/
   ```

3. **Add Tests**
   ```bash
   # Add unit tests
   cp tests/unit/test_*.py tests/unit/modules/network/ios/

   # Add integration tests
   mkdir tests/integration/targets/ios_gnmi
   cp -r your_tests/* tests/integration/targets/ios_gnmi/
   ```

4. **Update Documentation**
   - Add module documentation to docs/
   - Update CHANGELOG.rst
   - Add examples to README

5. **Submit Pull Request**
   ```bash
   git checkout -b feature/add-gnmi-support
   git add .
   git commit -m "Add gNMI support for Cisco IOS XE"
   git push origin feature/add-gnmi-support
   ```

6. **Community Review Process**
   - Respond to reviewer feedback
   - Make requested changes
   - Wait for approval from maintainers
   - Merge (can take weeks to months)

**Advantages:**
- ✅ Part of official Cisco collection
- ✅ Included in default Ansible installations (if collection is bundled)
- ✅ Community maintenance and support
- ✅ Better discoverability

**Challenges:**
- ❌ Longer review process
- ❌ Must meet collection standards
- ❌ Less control over releases
- ❌ Dependency on maintainers

---

### 3. Ansible Community Collections

**Best for:** Broader networking community adoption

**Options:**
- **community.network** - Networking modules
- **community.general** - General-purpose modules

**Repository:** https://github.com/ansible-collections/community.network

#### Steps to Contribute

Similar to cisco.ios contribution, but with these differences:

1. **Follow Community Guidelines**
   - Review CONTRIBUTING.md
   - Follow module naming conventions
   - Ensure cross-platform compatibility

2. **Module Placement**
   ```bash
   # For community.network
   plugins/modules/network/gnmi/cisco_iosxe_gnmi.py
   ```

3. **Documentation Requirements**
   - More stringent documentation standards
   - Must include examples for multiple platforms
   - Integration test requirements

**Advantages:**
- ✅ Wider audience
- ✅ Multi-vendor support potential
- ✅ Active community

**Challenges:**
- ❌ Stricter review process
- ❌ Broader compatibility requirements
- ❌ May need to generalize beyond Cisco

---

### 4. Official Cisco Partnership

**Best for:** Enterprise support and long-term maintenance

#### Steps to Partner with Cisco

1. **Contact Cisco DevNet**
   - Email: devnetsupport@cisco.com
   - DevNet forums: https://developer.cisco.com/site/networking/

2. **Propose Collection**
   - Present use cases and benefits
   - Demonstrate community need
   - Show technical implementation

3. **Collaborate on Standards**
   - Align with Cisco's Ansible strategy
   - Follow Cisco's coding standards
   - Integrate with existing Cisco collections

4. **Official Release**
   - Cisco publishes as `cisco.iosxe_gnmi`
   - Available through Automation Hub
   - Enterprise support included

**Advantages:**
- ✅ Official Cisco support
- ✅ Enterprise credibility
- ✅ Professional maintenance
- ✅ Integration with Cisco ecosystem

**Challenges:**
- ❌ Longer timeline
- ❌ Corporate approval process
- ❌ Must meet enterprise standards
- ❌ Less individual control

---

## Recommended Approach: Multi-Phase Strategy

### Phase 1: Ansible Galaxy (Months 1-2)
1. Publish to Galaxy immediately
2. Build user base and gather feedback
3. Fix bugs and add features based on usage

### Phase 2: Community Contribution (Months 3-6)
1. Submit PR to cisco.ios collection
2. Engage with community reviewers
3. Refine based on feedback

### Phase 3: Cisco Partnership (Months 6-12)
1. Approach Cisco with proven adoption
2. Discuss official support
3. Transition to official Cisco collection if appropriate

---

## Preparation Checklist

Before pursuing any integration path:

### Code Quality
- [ ] All tests passing (unit and integration)
- [ ] Code follows Ansible style guide
- [ ] No pylint/flake8 warnings
- [ ] Type hints where applicable
- [ ] Proper error handling

### Documentation
- [ ] Comprehensive README.md
- [ ] Module documentation (DOCUMENTATION string)
- [ ] EXAMPLES string with multiple use cases
- [ ] RETURN documentation
- [ ] CHANGELOG.md or CHANGELOG.rst
- [ ] Contributing guidelines

### Testing
- [ ] Unit tests with >80% coverage
- [ ] Integration tests for major operations
- [ ] Tested on multiple IOS XE versions
- [ ] CI/CD pipeline configured

### Legal
- [ ] Proper license (GPL v3 for Ansible compatibility)
- [ ] Copyright headers in all files
- [ ] No proprietary dependencies
- [ ] Contributor agreements if applicable

### Community
- [ ] GitHub repository with issues enabled
- [ ] Active maintenance commitment
- [ ] Community support channels
- [ ] Example playbooks and use cases

---

## Next Steps

### For Immediate Release (Galaxy)

1. **Update galaxy.yml**
   ```yaml
   namespace: cisco
   name: iosxe_gnmi
   version: 1.0.0
   readme: README.md
   authors:
     - Your Name <your.email@example.com>
   description: Cisco IOS XE gNMI management via Ansible
   license:
     - GPL-3.0-or-later
   tags:
     - cisco
     - iosxe
     - gnmi
     - networking
     - grpc
   repository: https://github.com/yourusername/ansible-gnmi
   documentation: https://github.com/yourusername/ansible-gnmi/blob/main/README.md
   homepage: https://github.com/yourusername/ansible-gnmi
   issues: https://github.com/yourusername/ansible-gnmi/issues
   ```

2. **Build Collection**
   ```bash
   ansible-galaxy collection build
   ```

3. **Test Installation**
   ```bash
   ansible-galaxy collection install cisco-iosxe_gnmi-1.0.0.tar.gz
   ```

4. **Publish**
   - Upload to Galaxy via web interface
   - Or use API: `ansible-galaxy collection publish`

### For cisco.ios Contribution

1. **Review Current Collection**
   ```bash
   git clone https://github.com/ansible-collections/cisco.ios.git
   cd cisco.ios
   # Study existing modules and structure
   ```

2. **Open Discussion Issue**
   - Create issue proposing gNMI support
   - Gauge maintainer interest
   - Discuss implementation approach

3. **Create Feature Branch**
   - Follow their contribution guidelines
   - Implement according to their standards
   - Include all required tests

---

## Resources

### Ansible Galaxy
- Documentation: https://galaxy.ansible.com/docs/
- Publishing Guide: https://docs.ansible.com/ansible/latest/dev_guide/developing_collections_distributing.html

### Collection Development
- Dev Guide: https://docs.ansible.com/ansible/latest/dev_guide/developing_collections.html
- Module Guidelines: https://docs.ansible.com/ansible/latest/dev_guide/developing_modules_best_practices.html
- Testing Guide: https://docs.ansible.com/ansible/latest/dev_guide/testing.html

### Cisco Resources
- DevNet: https://developer.cisco.com
- Cisco Ansible: https://github.com/ansible-collections/cisco.ios
- gNMI Docs: https://www.cisco.com/c/en/us/td/docs/ios-xml/ios/prog/configuration/1718/b-1718-programmability-cg/gnmi.html

### Community
- Ansible Community: https://ansible.com/community
- Network Automation: https://github.com/network-automation
- IRC: #ansible-network on Libera.chat

---

## Support and Maintenance

### Ongoing Responsibilities

Regardless of integration path chosen:

1. **Bug Fixes**
   - Respond to issues within 48 hours
   - Critical bugs fixed within 1 week
   - Regular patch releases

2. **Feature Requests**
   - Evaluate community requests
   - Prioritize based on impact
   - Document roadmap publicly

3. **Compatibility**
   - Test with new Ansible versions
   - Support multiple IOS XE versions
   - Update for gNMI spec changes

4. **Documentation**
   - Keep examples up to date
   - Add new use cases
   - Maintain changelog

5. **Community Engagement**
   - Monitor GitHub issues
   - Participate in discussions
   - Help users troubleshoot

---

## Success Metrics

Track these metrics to demonstrate value:

- **Downloads**: Galaxy download count
- **Stars**: GitHub repository stars
- **Issues**: Issue resolution rate and time
- **Contributions**: Pull requests from community
- **Adoption**: Number of organizations using
- **Documentation**: View count on docs

---

## Conclusion

**Recommended Path:**

1. **Start with Ansible Galaxy** - Get users immediately
2. **Gather feedback and iterate** - Improve based on real usage
3. **Submit to cisco.ios** - Once mature and proven
4. **Maintain both** - Galaxy for latest, cisco.ios for stability

This multi-pronged approach maximizes reach while minimizing risk.
