# WordPress Authentication Setup

## Issue: Application Passwords Disabled

If you see "Application passwords have been disabled by All-In-One Security plugin", you need to enable them first.

## Solution 1: Enable in All-In-One Security Plugin

1. **Go to All-In-One Security Settings:**
   - WordPress Admin → All-In-One Security → User Login
   - Find "Application Passwords" section
   - Click "Change setting" or toggle to enable

2. **Then generate password:**
   - WordPress Admin → Users → Your Profile → Application Passwords
   - Click "Add New Application Password"
   - Name it (e.g., "Python Script" or "REST API")
   - Copy the generated password (format: `xxxx xxxx xxxx xxxx`)

## Solution 2: Alternative Authentication Methods

If you can't enable Application Passwords, you can use:

### Option A: OAuth Token (if available)
Some WordPress setups support OAuth tokens. Check with your hosting provider.

### Option B: Plugin-Based Authentication
Install a plugin like "Application Passwords" or "REST API Authentication" that provides alternative auth methods.

### Option C: Temporary Admin Access
For testing only, you could temporarily use your regular WordPress password (not recommended for production).

## Testing Connection

After setting up credentials in `config.py`:

```bash
python3 push_pages.py --test-connection
```

Expected output:
```
✓ Connection successful!
  Site: https://gravelgodcycling.com
  User: Your Name (your-username)
```

If you get an error, check:
1. Application Passwords are enabled
2. Credentials in `config.py` are correct
3. WordPress REST API is enabled (usually enabled by default)

