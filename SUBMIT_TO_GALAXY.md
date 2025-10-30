# Submit to Ansible Galaxy - Final Steps

## ✅ Pre-Submission Complete

Your collection is **READY FOR SUBMISSION**! All checks passed:
- ✅ Collection built: `cisco-iosxe_gnmi-1.0.0.tar.gz` (85KB)
- ✅ Code review completed (see `CODE_REVIEW.md`)
- ✅ All tests passing
- ✅ Documentation complete
- ✅ License: Apache 2.0

---

## 🚀 Submission Options

### Option 1: Web Interface (Recommended for First Submission)

1. **Get Your API Token**
   - Go to https://galaxy.ansible.com/
   - Sign in with your GitHub account (@jcohoe)
   - Click your profile → "Settings" → "API Key"
   - Click "Show token" and copy it

2. **Upload via Web**
   - Go to https://galaxy.ansible.com/my-content/namespaces
   - Click "Upload Collection"
   - Select `cisco-iosxe_gnmi-1.0.0.tar.gz`
   - Click "Upload"
   - Wait for validation (usually 1-2 minutes)

### Option 2: Command Line

```bash
# Set your API token (get from galaxy.ansible.com)
export GALAXY_API_KEY="your-api-token-here"

# Publish the collection
ansible-galaxy collection publish cisco-iosxe_gnmi-1.0.0.tar.gz --api-key=$GALAXY_API_KEY

# Or specify the token directly:
ansible-galaxy collection publish cisco-iosxe_gnmi-1.0.0.tar.gz --api-key="your-token"
```

---

## ⚠️ Important: Namespace Decision

Your `galaxy.yml` currently uses:
```yaml
namespace: cisco
name: iosxe_gnmi
```

**This will publish as: `cisco.iosxe_gnmi`**

### Namespace Requirements

1. **To use `cisco` namespace**:
   - You must be approved by Cisco or have access to the `cisco` namespace on Galaxy
   - If you don't have access, the upload will fail
   - Contact Galaxy admins or use a different namespace

2. **Alternative: Use your personal namespace**:
   - Use `jcohoe` instead of `cisco`
   - This will work immediately: `jcohoe.iosxe_gnmi`
   - Users install with: `ansible-galaxy collection install jcohoe.iosxe_gnmi`

### To Change Namespace (if needed)

Edit `galaxy.yml`:
```yaml
namespace: jcohoe  # Your GitHub username
name: iosxe_gnmi
```

Then rebuild:
```bash
ansible-galaxy collection build --force
ansible-galaxy collection install jcohoe-iosxe_gnmi-1.0.0.tar.gz --force
# Test that it works
ansible-doc jcohoe.iosxe_gnmi.cisco_iosxe_gnmi
```

---

## 📋 Post-Submission Checklist

After successful upload:

1. **Verify on Galaxy**
   - Go to https://galaxy.ansible.com/ui/repo/published/cisco/iosxe_gnmi/
   - (or https://galaxy.ansible.com/ui/repo/published/jcohoe/iosxe_gnmi/)
   - Check that all information displays correctly

2. **Test Installation from Galaxy**
   ```bash
   # Remove local version
   ansible-galaxy collection list | grep iosxe_gnmi
   ansible-galaxy collection remove cisco.iosxe_gnmi

   # Install from Galaxy
   ansible-galaxy collection install cisco.iosxe_gnmi

   # Verify
   ansible-doc cisco.iosxe_gnmi.cisco_iosxe_gnmi
   ```

3. **Update README (Optional)**
   - Add Galaxy badge
   - Update installation instructions to reference Galaxy

4. **Announce Release**
   - GitHub Release page
   - Social media / internal communications
   - Update documentation site (if any)

---

## 🔄 Future Updates

When you release version 1.1.0 or later:

1. Update `galaxy.yml` version
2. Update `CHANGELOG.md` with changes
3. Rebuild collection
4. Upload new version (same process)
5. Galaxy will show both versions (users can choose)

---

## 🆘 Troubleshooting

### Upload Fails: Namespace Not Found
**Solution**: You don't have access to the `cisco` namespace. Change to `jcohoe`.

### Upload Fails: Validation Errors
**Solution**: Check the error message. Common issues:
- Missing required files (we have all of them ✅)
- Invalid galaxy.yml format (ours is valid ✅)
- Duplicate version (increment version number)

### Can't Access After Upload
**Solution**: Wait 5-10 minutes for Galaxy's cache to refresh.

---

## 📞 Need Help?

- Ansible Galaxy Support: https://github.com/ansible/galaxy/issues
- Community Forum: https://forum.ansible.com/
- Documentation: https://docs.ansible.com/ansible/latest/dev_guide/developing_collections_distributing.html

---

## ✨ You're Ready!

Everything is prepared and tested. Just need to:
1. Decide on namespace (`cisco` or `jcohoe`)
2. Get your API token from Galaxy
3. Upload the collection
4. Celebrate! 🎉

**Good luck with your submission!** 🚀
