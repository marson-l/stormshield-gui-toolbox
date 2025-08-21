# SSL Certificate Troubleshooting Guide

## Issue: "Certificate authority bundle not found"

This error occurs when the compiled executable cannot find the SSL certificate bundle needed for HTTPS connections to Stormshield appliances.

## Solutions Applied:

### 1. Modified SSL Client Connection
- Added proper SSL context handling
- Disabled SSL verification for self-signed certificates (common with Stormshield)
- Added fallback options for different SSL client versions

### 2. Updated PyInstaller Configuration
- Added `certifi` package to include SSL certificates
- Included necessary hidden imports
- Configured proper data file collection

### 3. Enhanced Error Handling
- More descriptive error messages for SSL issues
- Connection troubleshooting hints
- Proper authentication error detection

## Building the Application:

### Option 1: Use the build script (Recommended)
```batch
build.bat
```

### Option 2: Manual build process
```batch
# Install requirements
pip install -r requirements.txt

# Clean previous builds
rmdir /s /q dist build

# Build with spec file
pyinstaller main_gui.spec --clean --noconfirm
```

## Additional Troubleshooting:

### If you still get certificate errors:

1. **Enable console mode for debugging:**
   - Edit `main_gui.spec`
   - Change `console=False` to `console=True`
   - Rebuild the application
   - Run from command line to see detailed error messages

2. **Test SSL connection manually:**
   ```python
   from stormshield.sns.sslclient import SSLClient
   client = SSLClient(host="your_host", port=443, user="admin", password="password", sslverifyhost=False)
   ```

3. **Check Stormshield appliance settings:**
   - Ensure SSL/HTTPS is enabled
   - Check if the management port is correct (usually 443)
   - Verify firewall rules allow connections

4. **Network connectivity:**
   - Test basic connectivity: `ping your_stormshield_ip`
   - Test port connectivity: `telnet your_stormshield_ip 443`

### Alternative SSL verification options:

If the appliance uses a valid certificate, you can enable verification by modifying the connection code:
```python
self.client = SSLClient(
    host=self.host,
    port=self.port,
    user=self.user,
    password=self.password,
    sslverifyhost=True,  # Enable if using valid certificates
    sslverifypeer=True   # Enable if using valid certificates
)
```

## Environment Variables (if needed):

For additional SSL configuration, you can set these environment variables:
```batch
set REQUESTS_CA_BUNDLE=path\to\certificates
set SSL_CERT_FILE=path\to\certificates
set CURL_CA_BUNDLE=path\to\certificates
```

## Testing the Fix:

1. Run the compiled executable
2. Try connecting to your Stormshield appliance
3. If connection succeeds, the SSL certificate issue is resolved
4. Test command execution in both batch and terminal modes

## Still Having Issues?

- Check the Windows Event Viewer for application errors
- Run with console=True to see Python tracebacks
- Verify the Stormshield SNS client library version compatibility
- Consider using a different SSL client or requests library as fallback
