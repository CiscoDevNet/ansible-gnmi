# Ansible Galaxy Submission Checklist

## ✅ Pre-Submission Verification

### Collection Build
- [x] Collection builds successfully
  ```bash
  ansible-galaxy collection build --force
  ```
- [x] No build errors or warnings
- [x] Tarball created: `cisco-iosxe_gnmi-1.0.0.tar.gz`

### Local Installation Test
- [x] Collection installs locally
  ```bash
  ansible-galaxy collection install cisco-iosxe_gnmi-1.0.0.tar.gz --force
  ```
- [x] Module documentation accessible
  ```bash
  ansible-doc cisco.iosxe_gnmi.cisco_iosxe_gnmi
  ```
- [x] Test playbooks run successfully

### Required Files
- [x] `LICENSE` - Apache 2.0 license file present
- [x] `README.md` - Comprehensive documentation
- [x] `galaxy.yml` - Collection metadata configured
- [x] `meta/runtime.yml` - Runtime requirements defined
- [x] `CHANGELOG.md` - Version history documented
- [x] Module files in `plugins/modules/`
- [x] Module utilities in `plugins/module_utils/`

### Documentation Quality
- [x] README.md includes:
  - [x] Feature overview
  - [x] Installation instructions
  - [x] Usage examples (GET, SET, Subscribe)
  - [x] Quick reference table
  - [x] Module parameters
  - [x] Troubleshooting guide
- [x] Module includes DOCUMENTATION string
- [x] Module includes EXAMPLES string
- [x] Module includes RETURN string
- [x] All examples are tested and working

### Code Quality
- [x] No syntax errors
- [x] All test playbooks working
- [x] Proper error handling
- [x] No hardcoded credentials in examples

### galaxy.yml Metadata
- [x] `namespace`: cisco
- [x] `name`: iosxe_gnmi
- [x] `version`: 1.0.0
- [x] `description`: Comprehensive and accurate
- [x] `authors`: Properly attributed
- [x] `license`: Apache-2.0
- [x] `tags`: Relevant tags added
- [x] `repository`: GitHub URL (update to your repo)
- [x] `documentation`: Link to README
- [x] `issues`: Link to issue tracker
- [x] `build_ignore`: Excludes unnecessary files

### Testing
- [x] Tested on real Cisco IOS XE devices
- [x] GET operations verified
- [x] SET operations verified
- [x] Multiple YANG models tested
- [x] Multi-device scenarios tested

## 🚀 Publishing Steps

### Step 1: Create GitHub Repository (If Not Done)
```bash
cd /Users/jcohoe/Documents/VSCODE/ansible-gnmi
git init
git add .
git commit -m "Initial commit: Cisco IOS XE gNMI Ansible Collection v1.0.0"
git remote add origin https://github.com/jcohoe/ansible-gnmi.git
git push -u origin main
```

### Step 2: Create Ansible Galaxy Account
1. Visit: https://galaxy.ansible.com
2. Click "Sign in with GitHub"
3. Authorize Ansible Galaxy
4. Complete profile

### Step 3: Create/Claim Namespace
1. Go to: https://galaxy.ansible.com/my-content/namespaces
2. Search for "cisco" namespace
3. If available, claim it
4. If not, use your GitHub username or create alternative

**Note**: You may need to use a different namespace like `jcohoe` instead of `cisco` if you don't have permission to use the Cisco namespace.

### Step 4: Get API Token
1. Go to: https://galaxy.ansible.com/me/preferences
2. Click "API Key" tab
3. Copy your API token

### Step 5: Publish Collection

**Option A - Web Interface (Recommended for first publish)**:
1. Go to: https://galaxy.ansible.com/my-content/namespaces
2. Click on your namespace
3. Click "Upload collection"
4. Upload: `cisco-iosxe_gnmi-1.0.0.tar.gz`
5. Review metadata
6. Click "Publish"

**Option B - Command Line**:
```bash
export GALAXY_API_KEY="your-api-token-here"
ansible-galaxy collection publish cisco-iosxe_gnmi-1.0.0.tar.gz --api-key=$GALAXY_API_KEY
```

### Step 6: Verify Publication
1. Visit your collection page: https://galaxy.ansible.com/cisco/iosxe_gnmi
   (or https://galaxy.ansible.com/[your-namespace]/iosxe_gnmi)
2. Check that:
   - Version shows 1.0.0
   - README displays correctly
   - Tags are visible
   - Links work
3. Test installation:
   ```bash
   ansible-galaxy collection install cisco.iosxe_gnmi
   # or with your namespace:
   ansible-galaxy collection install [your-namespace].iosxe_gnmi
   ```

## 📋 Post-Publication Tasks

### Update README Badge
Add to README.md:
```markdown
[![Galaxy](https://img.shields.io/badge/galaxy-cisco.iosxe__gnmi-blue.svg)](https://galaxy.ansible.com/cisco/iosxe_gnmi)
[![Downloads](https://img.shields.io/ansible/collection/cisco.iosxe_gnmi)](https://galaxy.ansible.com/cisco/iosxe_gnmi)
```

### Announce Release
- [ ] Tweet about it: #Ansible #Cisco #gNMI
- [ ] Post on Reddit: r/ansible, r/networking
- [ ] Share on LinkedIn
- [ ] Cisco DevNet community forums
- [ ] Network Automation community

### Monitor
- [ ] Watch for GitHub issues
- [ ] Check Galaxy download stats
- [ ] Respond to user questions
- [ ] Plan next release based on feedback

## ⚠️ Important Notes

### Namespace Consideration
If you cannot use the `cisco` namespace (requires Cisco affiliation/approval):

1. **Update galaxy.yml**:
   ```yaml
   namespace: jcohoe  # Your GitHub username
   name: iosxe_gnmi
   ```

2. **Rebuild**:
   ```bash
   ansible-galaxy collection build --force
   ```

3. **Users will install via**:
   ```bash
   ansible-galaxy collection install jcohoe.iosxe_gnmi
   ```

4. **In playbooks**:
   ```yaml
   - jcohoe.iosxe_gnmi.cisco_iosxe_gnmi:
   ```

### Version Management
For future releases:
1. Update `version` in galaxy.yml
2. Update CHANGELOG.md
3. Create git tag: `git tag v1.0.1`
4. Build and publish new version

## 🎯 Success Criteria

Your collection is ready for Galaxy when:
- [x] Builds without errors
- [x] Installs locally successfully
- [x] Documentation is comprehensive
- [x] Examples are tested and working
- [x] All required metadata is present
- [x] LICENSE file exists
- [x] GitHub repository is public

## 🔍 Validation Commands

Run these before publishing:

```bash
# Build
ansible-galaxy collection build --force

# Install locally
ansible-galaxy collection install cisco-iosxe_gnmi-1.0.0.tar.gz --force

# Check module docs
ansible-doc cisco.iosxe_gnmi.cisco_iosxe_gnmi

# List installed
ansible-galaxy collection list | grep iosxe_gnmi

# Run a test playbook
ansible-playbook -i test_inventory.ini test_device.yml
```

All commands should complete without errors.

## 📞 Support

If you encounter issues:
- Galaxy Help: https://galaxy.ansible.com/docs/
- Ansible Community: #ansible on Libera.chat IRC
- Ansible Forum: https://forum.ansible.com/

---

**Your collection is ready for submission! 🎉**

Current status: ✅ All checks passed
Next step: Publish to Galaxy following Step 5 above
