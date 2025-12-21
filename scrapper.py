"""
Telegram Bot to fetch all messages from a group without affecting view counts.
Uses Pyrogram (MTProto) with a user account to read messages without marking them as read.
"""

import asyncio
from pyrogram import Client
from pyrogram.types import Message
from pyrogram import filters
import json
from datetime import datetime
from typing import List, Optional, Callable
import os


class TelegramGroupScraper:
    def __init__(self, api_id: int, api_hash: str, session_name: str = "scraper_session"):
        """
        Initialize the Telegram scraper.
        
        Args:
            api_id: Your Telegram API ID (get from https://my.telegram.org)
            api_hash: Your Telegram API Hash
            session_name: Name for the session file
        """
        self.api_id = api_id
        self.api_hash = api_hash
        self.session_name = session_name
        self.client = Client(
            session_name,
            api_id=api_id,
            api_hash=api_hash
        )
    
    async def get_all_messages(
        self,
        chat_id: str,
        limit: Optional[int] = None,
        offset_id: int = 0
    ) -> List[Message]:
        """
        Get all messages from a group without affecting view counts.
        
        Args:
            chat_id: Username or ID of the group/channel
            limit: Maximum number of messages to fetch (None = all)
            offset_id: Message ID to start from (0 = start from latest)
        
        Returns:
            List of Message objects
        """
        messages = []
        
        async with self.client:
            # Verify we can access the chat
            try:
                chat = await self.client.get_chat(chat_id)
                print(f"Accessing chat: {chat.title or chat.first_name}")
            except Exception as e:
                print(f"Error accessing chat: {e}")
                return messages
            
            # Get messages using get_chat_history which doesn't mark as read
            # when used with appropriate parameters
            print(f"Fetching messages from {chat_id}...")
            
            try:
                # Use get_chat_history to fetch messages without marking as read
                async for message in self.client.get_chat_history(
                    chat_id=chat_id,
                    limit=limit,
                    offset_id=offset_id
                ):
                    messages.append(message)
                    
                    # Progress indicator
                    if len(messages) % 100 == 0:
                        print(f"Fetched {len(messages)} messages...")
                    
                    if limit and len(messages) >= limit:
                        break
                        
            except Exception as e:
                print(f"Error fetching messages: {e}")
        
        print(f"Total messages fetched: {len(messages)}")
        return messages
    
    def format_message(self, message: Message) -> dict:
        """
        Format a message object into a dictionary.
        
        Args:
            message: Pyrogram Message object
        
        Returns:
            Dictionary with message data
        """
        return {
            "message_id": message.id,
            "date": message.date.isoformat() if message.date else None,
            "text": message.text or message.caption or "",
            "from_user": {
                "id": message.from_user.id if message.from_user else None,
                "username": message.from_user.username if message.from_user else None,
                "first_name": message.from_user.first_name if message.from_user else None,
                "last_name": message.from_user.last_name if message.from_user else None,
            } if message.from_user else None,
            "media_type": message.media.name if message.media else None,
            "views": message.views if hasattr(message, 'views') else None,
            "forward_from": {
                "id": message.forward_from.id if message.forward_from else None,
                "username": message.forward_from.username if message.forward_from else None,
            } if message.forward_from else None,
            "reply_to_message_id": message.reply_to_message_id if message.reply_to_message_id else None,
        }
    
    async def save_messages_to_json(
        self,
        chat_id: str,
        output_file: str = "messages.json",
        limit: Optional[int] = None
    ):
        """
        Fetch all messages and save them to a JSON file.
        
        Args:
            chat_id: Username or ID of the group/channel
            output_file: Path to output JSON file
            limit: Maximum number of messages to fetch
        """
        messages = await self.get_all_messages(chat_id, limit=limit)
        
        formatted_messages = [self.format_message(msg) for msg in messages]
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(formatted_messages, f, indent=2, ensure_ascii=False)
        
        print(f"Messages saved to {output_file}")
        return formatted_messages
    
    async def print_messages_summary(
        self,
        chat_id: str,
        limit: Optional[int] = None
    ):
        """
        Print a summary of messages from a group.
        
        Args:
            chat_id: Username or ID of the group/channel
            limit: Maximum number of messages to fetch
        """
        messages = await self.get_all_messages(chat_id, limit=limit)
        
        print(f"\n=== Messages Summary ===")
        print(f"Total messages: {len(messages)}")
        
        if messages:
            print(f"Oldest message: {messages[-1].date}")
            print(f"Newest message: {messages[0].date}")
            
            # Count messages by type
            text_count = sum(1 for msg in messages if msg.text or msg.caption)
            media_count = sum(1 for msg in messages if msg.media)
            print(f"Text messages: {text_count}")
            print(f"Media messages: {media_count}")
            
            # Show first few messages
            print(f"\n=== Sample Messages ===")
            for i, msg in enumerate(messages[:5], 1):
                sender = msg.from_user.username or msg.from_user.first_name if msg.from_user else "Unknown"
                text_preview = (msg.text or msg.caption or "")[:50] if (msg.text or msg.caption) else "[Media]"
                print(f"{i}. [{msg.date}] {sender}: {text_preview}...")
    
    async def listen_realtime(
        self,
        chat_id: str,
        output_file: Optional[str] = None,
        print_messages: bool = True,
        callback: Optional[Callable] = None
    ):
        """
        Listen for new messages in real-time without affecting view counts.
        
        Args:
            chat_id: Username or ID of the group/channel to monitor
            output_file: Optional JSON file to append messages to
            print_messages: Whether to print messages as they arrive
            callback: Optional callback function to process each message
        """
        # Store chat_id for the handler
        self.monitored_chat_id = chat_id
        self.output_file = output_file
        self.print_messages = print_messages
        self.message_callback = callback
        self.message_count = 0
        
        async with self.client:
            # Verify we can access the chat
            try:
                chat = await self.client.get_chat(chat_id)
                chat_title = chat.title or chat.first_name or str(chat_id)
                print(f"✅ Monitoring chat: {chat_title}")
                print(f"📡 Listening for new messages... (Press Ctrl+C to stop)")
                print("-" * 60)
            except Exception as e:
                print(f"❌ Error accessing chat: {e}")
                return
            
            # Set up message handler
            @self.client.on_message(filters.chat(chat_id))
            async def handle_message(client: Client, message: Message):
                """Handle incoming messages without marking as read"""
                self.message_count += 1
                
                # Format the message
                formatted_msg = self.format_message(message)
                
                # Print message if enabled
                if self.print_messages:
                    sender = message.from_user.username or message.from_user.first_name if message.from_user else "Unknown"
                    text_preview = (message.text or message.caption or "")[:100] if (message.text or message.caption) else "[Media]"
                    timestamp = message.date.strftime("%Y-%m-%d %H:%M:%S") if message.date else "Unknown"
                    
                    print(f"\n[{timestamp}] {sender}:")
                    print(f"  {text_preview}")
                    if message.media:
                        print(f"  📎 Media: {message.media.name}")
                    print(f"  Message ID: {message.id} | Total received: {self.message_count}")
                    print("-" * 60)
                
                # Save to file if specified
                if self.output_file:
                    await self._append_message_to_file(formatted_msg, self.output_file)
                
                # Call custom callback if provided
                if self.message_callback:
                    await self.message_callback(message, formatted_msg)
            
            # Keep the client running
            # Use a loop that runs until KeyboardInterrupt
            try:
                while True:
                    await asyncio.sleep(1)  # Sleep to avoid busy waiting
            except KeyboardInterrupt:
                print(f"\n\n🛑 Stopped listening. Total messages received: {self.message_count}")
    
    async def _append_message_to_file(self, message_dict: dict, file_path: str):
        """
        Append a message to a JSON file.
        Maintains a list structure by reading, appending, and writing back.
        """
        try:
            # Read existing messages if file exists
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    try:
                        messages = json.load(f)
                    except json.JSONDecodeError:
                        messages = []
            else:
                messages = []
            
            # Append new message
            messages.append(message_dict)
            
            # Write back to file
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(messages, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            print(f"⚠️  Error saving message to file: {e}")


async def main():
    """
    Main function to run the scraper.
    Configure your API credentials here or use environment variables.
    """
    # Get API credentials
    # You can set these as environment variables or hardcode them
    import os
    
    api_id = int(os.getenv("TELEGRAM_API_ID", "REMOVED"))  # Replace with your API ID
    api_hash = os.getenv("TELEGRAM_API_HASH", "REMOVED")  # Replace with your API Hash
    
    if api_id == 0 or not api_hash:
        print("ERROR: Please set TELEGRAM_API_ID and TELEGRAM_API_HASH")
        print("Get them from: https://my.telegram.org")
        print("\nYou can either:")
        print("1. Set environment variables: TELEGRAM_API_ID and TELEGRAM_API_HASH")
        print("2. Edit this script and replace the values above")
        return
    
    # Initialize scraper
    scraper = TelegramGroupScraper(api_id=api_id, api_hash=api_hash)
    
    # Example usage:
    # Replace with your group username or ID
    chat_id = input("Enter group username or ID (e.g., @mygroup or -1001234567890): ").strip()
    
    if not chat_id:
        print("No chat ID provided. Exiting.")
        return
    
    # Choose action
    print("\nWhat would you like to do?")
    print("1. Print messages summary (historical)")
    print("2. Save all messages to JSON file (historical)")
    print("3. Both (historical)")
    print("4. Listen for new messages in real-time")
    print("5. Listen and save to file in real-time")
    
    choice = input("Enter choice (1/2/3/4/5): ").strip()
    
    if choice == "1":
        limit = input("Enter message limit (press Enter for all): ").strip()
        limit = int(limit) if limit else None
        await scraper.print_messages_summary(chat_id, limit=limit)
    
    elif choice == "2":
        limit = input("Enter message limit (press Enter for all): ").strip()
        limit = int(limit) if limit else None
        output_file = input("Enter output filename (default: messages.json): ").strip() or "messages.json"
        # Ensure .json extension if not provided
        if not output_file.endswith('.json'):
            output_file += '.json'
        await scraper.save_messages_to_json(chat_id, output_file, limit=limit)
    
    elif choice == "3":
        limit = input("Enter message limit (press Enter for all): ").strip()
        limit = int(limit) if limit else None
        await scraper.print_messages_summary(chat_id, limit=limit)
        output_file = input("Enter output filename (default: messages.json): ").strip() or "messages.json"
        # Ensure .json extension if not provided
        if not output_file.endswith('.json'):
            output_file += '.json'
        await scraper.save_messages_to_json(chat_id, output_file, limit=limit)
    
    elif choice == "4":
        print("\n📡 Starting real-time listener...")
        print("Messages will be printed as they arrive.")
        print("Press Ctrl+C to stop.\n")
        await scraper.listen_realtime(chat_id, print_messages=True)
    
    elif choice == "5":
        output_file = input("Enter output filename (default: messages_realtime.json): ").strip() or "messages_realtime.json"
        # Ensure .json extension if not provided
        if not output_file.endswith('.json'):
            output_file += '.json'
        print(f"\n📡 Starting real-time listener...")
        print(f"Messages will be saved to: {output_file}")
        print("Press Ctrl+C to stop.\n")
        await scraper.listen_realtime(chat_id, output_file=output_file, print_messages=True)
    
    else:
        print("Invalid choice.")


if __name__ == "__main__":
    asyncio.run(main())
