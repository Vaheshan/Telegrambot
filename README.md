# Telegram Group Message Scraper

A Telegram bot that fetches all messages from a group without affecting view counts. This tool uses Pyrogram (MTProto API) with a user account to read messages without marking them as read.

## Features

- ✅ Fetch all messages from Telegram groups/channels
- ✅ **Real-time message listening** - Get messages as they arrive
- ✅ Does NOT affect view counts (messages remain unread)
- ✅ Export messages to JSON format (historical or real-time)
- ✅ View message summaries and statistics
- ✅ Support for both groups and channels
- ✅ Preserves message metadata (sender, date, media type, etc.)

## Prerequisites

1. **Python 3.7+** installed on your system
2. **Telegram API Credentials**:
   - Go to https://my.telegram.org
   - Log in with your phone number
   - Go to "API development tools"
   - Create an application (if you haven't already)
   - Copy your `api_id` and `api_hash`
   - 📖 **Detailed guide**: See [API_SETUP_GUIDE.md](API_SETUP_GUIDE.md) for step-by-step instructions

## Installation

1. Clone or download this repository

2. Install required dependencies:
```bash
pip install -r requirements.txt
```

## Configuration

You have two options to set your API credentials:

### Option 1: Environment Variables (Recommended)
```bash
# Windows PowerShell
$env:TELEGRAM_API_ID="your_api_id"
$env:TELEGRAM_API_HASH="your_api_hash"

# Windows CMD
set TELEGRAM_API_ID=your_api_id
set TELEGRAM_API_HASH=your_api_hash

# Linux/Mac
export TELEGRAM_API_ID=your_api_id
export TELEGRAM_API_HASH=your_api_hash
```

### Option 2: Edit the Script
Edit `scrapper.py` and replace the default values in the `main()` function:
```python
api_id = int(os.getenv("TELEGRAM_API_ID", "YOUR_API_ID"))
api_hash = os.getenv("TELEGRAM_API_HASH", "YOUR_API_HASH")
```

## Usage

1. Run the script:
```bash
python scrapper.py
```

2. On first run, you'll be asked to:
   - Enter your phone number (with country code, e.g., +1234567890)
   - Enter the verification code sent to your Telegram
   - Enter your 2FA password (if enabled)

3. Enter the group/channel identifier:
   - For public groups: Use username (e.g., `@mygroup`)
   - For private groups: Use the group ID (e.g., `-1001234567890`)
   - You can find group IDs using Telegram clients or bots

4. Choose an action:
   - **1**: Print messages summary (historical - quick overview)
   - **2**: Save all messages to JSON file (historical)
   - **3**: Both (historical - summary + save to file)
   - **4**: Listen for new messages in real-time (prints to console)
   - **5**: Listen and save to file in real-time (prints + saves to JSON)

5. For options 1-3: Optionally specify a message limit (press Enter for all messages)
   - For options 4-5: The bot will run continuously until you press Ctrl+C

## How It Works

This tool uses **Pyrogram**, which is a Python wrapper for Telegram's MTProto API. Unlike the Bot API, MTProto allows you to:
- Use a user account (not a bot)
- Read messages without marking them as read
- Access full message history
- Listen for messages in real-time

**Historical Messages:**
The `get_chat_history()` method is used to fetch messages without affecting view counts, as it doesn't trigger the "read" status that would normally update view counts.

**Real-time Messages:**
The `listen_realtime()` method uses Pyrogram's message handlers to listen for new messages as they arrive. Messages are captured without marking them as read, preserving view counts. The bot runs continuously until stopped with Ctrl+C.

## Output Format

Messages are saved in JSON format with the following structure:
```json
[
  {
    "message_id": 123,
    "date": "2024-01-01T12:00:00",
    "text": "Message content",
    "from_user": {
      "id": 123456789,
      "username": "username",
      "first_name": "First",
      "last_name": "Last"
    },
    "media_type": null,
    "views": 100,
    "forward_from": null,
    "reply_to_message_id": null
  }
]
```

## Important Notes

⚠️ **Privacy & Legal Considerations:**
- Only use this tool on groups you have permission to access
- Respect privacy and terms of service
- Don't use this for scraping private conversations without consent
- Be aware of data protection regulations in your jurisdiction

⚠️ **Rate Limits:**
- Telegram has rate limits on API calls
- For very large groups, fetching all messages may take time
- Consider using the limit parameter for testing

⚠️ **Session Files:**
- A session file (`scraper_session.session`) will be created after first login
- Keep this file secure - it contains your authentication
- Don't share or commit this file to version control

⚠️ **Real-time Listening:**
- The bot must stay running to receive messages
- Messages are captured as they arrive, not retroactively
- Use Ctrl+C to stop the listener gracefully
- Real-time messages are appended to the JSON file (if saving is enabled)

## Troubleshooting

**"Error accessing chat"**
- Make sure you're a member of the group/channel
- Verify the chat ID/username is correct
- For private groups, you need to be a member

**"Auth key not found"**
- Delete the session file and run again
- Make sure you have internet connection during authentication

**"FloodWaitError"**
- You're hitting Telegram's rate limits
- Wait for the specified time or reduce the number of requests

## License

This project is provided as-is for educational purposes. Use responsibly and in accordance with Telegram's Terms of Service.

