# How to Get Telegram API ID and API Hash

This guide will walk you through getting your Telegram API credentials step by step.

## Step-by-Step Instructions

### Step 1: Visit Telegram's API Development Portal

1. Open your web browser
2. Go to: **https://my.telegram.org**
3. You should see a page asking you to log in

### Step 2: Log In with Your Phone Number

1. Enter your **phone number** (with country code)
   - Example: `+1234567890` (for US)
   - Example: `+919876543210` (for India)
   - Example: `+447123456789` (for UK)
2. Click **"Next"** or press Enter
3. You'll receive a **verification code** on your Telegram app
4. Enter the verification code on the website
5. If you have **2FA (Two-Factor Authentication)** enabled, enter your password

### Step 3: Access API Development Tools

1. After logging in, you'll see a dashboard
2. Look for a section called **"API development tools"** or click on it
3. You might see a link that says something like:
   - "API development tools"
   - "Create new application"
   - Or it might be in a menu

### Step 4: Create an Application (If Needed)

1. If you haven't created an application before, you'll see a form:
   - **App title**: Enter any name (e.g., "My Scraper Bot", "Telegram Scraper")
   - **Short name**: Enter a short identifier (e.g., "scraper", "mybot")
   - **Platform**: Usually "Desktop" or "Other"
   - **Description**: Optional - you can leave it blank or add a description
2. Click **"Create application"** or **"Submit"**

### Step 5: Get Your Credentials

After creating the application, you'll see a page with your credentials:

- **api_id**: A number (e.g., `12345678`)
- **api_hash**: A long string of letters and numbers (e.g., `abcdef1234567890abcdef1234567890`)

**⚠️ Important:**
- Keep these credentials **SECRET** - don't share them publicly
- Don't commit them to version control (GitHub, etc.)
- You can use the same credentials for multiple projects

## Visual Guide

```
┌─────────────────────────────────────────┐
│  my.telegram.org                         │
├─────────────────────────────────────────┤
│  Phone number: +1234567890              │
│  [Next]                                  │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│  Enter verification code:               │
│  [12345]                                 │
│  [Submit]                                │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│  API development tools                   │
│  ┌───────────────────────────────────┐  │
│  │ App title: My Scraper Bot         │  │
│  │ Short name: scraper               │  │
│  │ Platform: Desktop                 │  │
│  │ [Create application]               │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│  Your API credentials:                  │
│                                          │
│  api_id: 12345678                       │
│  api_hash: abcdef1234567890...          │
│                                          │
│  ✅ Copy these values!                   │
└─────────────────────────────────────────┘
```

## Common Issues and Solutions

### Issue: "Phone number invalid"
- **Solution**: Make sure you include the country code with `+` sign
- Example: Use `+1234567890` not `1234567890`

### Issue: "Verification code not received"
- **Solution**: 
  - Check your Telegram app (mobile or desktop)
  - The code usually appears in a popup or notification
  - Wait a few seconds - sometimes there's a delay
  - Try requesting a new code

### Issue: "Can't find API development tools"
- **Solution**: 
  - Make sure you're logged in successfully
  - Look for a menu or navigation bar
  - The link might be called "API development tools", "Create application", or similar
  - Try this direct link: https://my.telegram.org/apps

### Issue: "Already have an application"
- **Solution**: 
  - If you've created an application before, you'll see your existing credentials
  - You can use the same `api_id` and `api_hash` for this project
  - You don't need to create a new one

## Using Your Credentials

Once you have your `api_id` and `api_hash`, you can use them in two ways:

### Method 1: Environment Variables (Recommended)

**Windows PowerShell:**
```powershell
$env:TELEGRAM_API_ID="12345678"
$env:TELEGRAM_API_HASH="abcdef1234567890abcdef1234567890"
```

**Windows CMD:**
```cmd
set TELEGRAM_API_ID=12345678
set TELEGRAM_API_HASH=abcdef1234567890abcdef1234567890
```

**Linux/Mac:**
```bash
export TELEGRAM_API_ID=12345678
export TELEGRAM_API_HASH=abcdef1234567890abcdef1234567890
```

### Method 2: Edit the Script

Edit `scrapper.py` and replace the values:
```python
api_id = int(os.getenv("TELEGRAM_API_ID", "12345678"))  # Your API ID
api_hash = os.getenv("TELEGRAM_API_HASH", "abcdef1234567890...")  # Your API Hash
```

## Security Reminders

🔒 **Keep your credentials safe:**
- Never share your `api_hash` publicly
- Don't commit credentials to Git repositories
- Use environment variables instead of hardcoding
- The `.gitignore` file is already set up to exclude session files

## Need Help?

If you're still having trouble:
1. Make sure you're using the correct phone number
2. Check that you have internet connection
3. Try using a different browser
4. Clear browser cache and try again
5. Make sure JavaScript is enabled in your browser

## Quick Reference

- **Website**: https://my.telegram.org
- **Direct API Tools Link**: https://my.telegram.org/apps
- **What you need**: Phone number, Telegram app (for verification code)
- **What you get**: `api_id` (number) and `api_hash` (string)

