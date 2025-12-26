"""
Parser script to extract trading signals from Telegram messages using Gemini LLM.
Uses scrapper.py to fetch messages and sends them to Gemini for signal extraction.
"""

import asyncio
import json
import csv
import os
from typing import Optional, Dict, Any
from datetime import datetime
from google import genai
from scrapper import TelegramGroupScraper


class SignalParser:
    def __init__(self, gemini_api_key: str):
        """
        Initialize the Signal Parser with Gemini API.
        
        Args:
            gemini_api_key: Your Google Gemini API key
        """
        self.client = genai.Client(api_key=gemini_api_key)
        
        # System prompt with clear output format instructions
        self.system_prompt = """You are a trading signal parser. Your task is to analyze Telegram messages and determine if they contain trading signals.

SAMPLE SIGNAL MESSAGE FORMAT:
#IDOLUSDT.P | SHORT 🔴

Entry: 0.02731 (CMP) 

TP 1 → 0.02701
TP 2 → 0.026627
TP 3 → 0.026218
TP 4 → 0.025671
TP 5 → Extended Targets

Stop Loss: 0.028266 ☠️

Risk it like a pro, not a gambler.
CBW Radar | © Cruzebow Premium™

RULES:
1. If the message is a trading signal (contains coin name, entry price, stop loss, and at least one TP), set "is_signal" to true and fill the "signal" object.
2. If the message is NOT a signal, set "is_signal" to false and set "signal" to null.
3. Extract coin name (e.g., "IDOLUSDT.P", "BTCUSDT", etc.)
4. Extract entry price (may be marked as "CMP" or "Current Market Price")
5. Extract stop loss price
6. Extract take profit prices (TP 1, TP 2, TP 3, TP 4) - fill them if present, otherwise set to null
7. If there are more than 4 TPs, only extract the first 4
8. Numbers should be extracted as floats (e.g., 0.02731, not "0.02731")
9. Extract trade side as "LONG" or "SHORT".
10. If side cannot be determined, set it to null.

OUTPUT FORMAT (you must return ONLY valid JSON in this exact format):
{
  "is_signal": true/false,
  "signal": {
    "coin_name": "IDOLUSDT.P" or null,
    "entry_price": 0.02731 or null,
    "side": "LONG" or "SHORT" or null,
    "stop_loss": 0.028266 or null,
    "tp1": 0.02701 or null,
    "tp2": 0.026627 or null,
    "tp3": 0.026218 or null,
    "tp4": 0.025671 or null
  }
}

If is_signal is false, set signal to null:
{
  "is_signal": false,
  "signal": null
}

Return ONLY the JSON object, no additional text, explanation, or markdown formatting.
"""
    
    def parse_message(self, message_text: str) -> Dict[str, Any]:
        """
        Parse a message using Gemini to extract signal information.
        
        Args:
            message_text: The text content of the Telegram message
            
        Returns:
            Dictionary with is_signal flag and signal data
        """
        if not message_text or not message_text.strip():
            return {
                "is_signal": False,
                "signal": None
            }
        
        try:
            # Create the full prompt
            full_prompt = f"{self.system_prompt}\n\nMESSAGE TO ANALYZE:\n{message_text}\n\nReturn the JSON response:"
            
            # Call Gemini API
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=full_prompt
            )
            
            # Get response text
            response_text = response.text.strip()
            
            # Remove markdown code blocks if present
            if response_text.startswith("```"):
                # Remove ```json or ``` at start and ``` at end
                lines = response_text.split('\n')
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines[-1].strip() == "```":
                    lines = lines[:-1]
                response_text = '\n'.join(lines).strip()
            
            # Parse JSON
            json_data = json.loads(response_text)
            
            # Validate basic structure
            if not isinstance(json_data, dict) or "is_signal" not in json_data:
                raise ValueError("Invalid response structure")
            
            # Ensure proper format
            result = {
                "is_signal": bool(json_data.get("is_signal", False)),
                "signal": None
            }
            
            # If it's a signal, validate and extract signal data
            if result["is_signal"] and json_data.get("signal"):
                signal_data = json_data["signal"]
                result["signal"] = {
                    "coin_name": signal_data.get("coin_name"),
                    "side": signal_data.get("side"),
                    "entry_price": self._to_float(signal_data.get("entry_price")),
                    "stop_loss": self._to_float(signal_data.get("stop_loss")),
                    "tp1": self._to_float(signal_data.get("tp1")),
                    "tp2": self._to_float(signal_data.get("tp2")),
                    "tp3": self._to_float(signal_data.get("tp3")),
                    "tp4": self._to_float(signal_data.get("tp4")),
                }
            
            return result
            
        except json.JSONDecodeError as e:
            print(f"⚠️  JSON parsing error: {e}")
            if 'response_text' in locals():
                print(f"Response text: {response_text[:200]}...")
            return {
                "is_signal": False,
                "signal": None
            }
        except Exception as e:
            print(f"⚠️  Error parsing message: {e}")
            print(f"Error type: {type(e).__name__}")
            return {
                "is_signal": False,
                "signal": None
            }
    
    def _to_float(self, value) -> Optional[float]:
        """Convert value to float or None."""
        if value is None or value == "":
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return None
        return None
    
    def save_to_csv(self, results: list, output_file: str = "parsed_signals.csv"):
        """
        Save parsed results to a CSV file.
        
        Args:
            results: List of dictionaries with message and parsed signal data
            output_file: Path to output CSV file
        """
        if not results:
            print("No results to save.")
            return
        
        # Define CSV columns
        fieldnames = [
            "message_id",
            "date",
            "message_text",
            "is_signal",
            "coin_name",
            "side",
            "entry_price",
            "stop_loss",
            "tp1",
            "tp2",
            "tp3",
            "tp4"
        ]
        
        # Write to CSV
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for result in results:
                row = {
                    "message_id": result.get("message_id", ""),
                    "date": result.get("date", ""),
                    "message_text": result.get("message_text", ""),
                    "is_signal": result.get("is_signal", False),
                    "coin_name": "",
                    "side": "",
                    "entry_price": "",
                    "stop_loss": "",
                    "tp1": "",
                    "tp2": "",
                    "tp3": "",
                    "tp4": ""
                }
                
                # Fill signal data if present
                signal = result.get("signal")
                if signal:
                    row["coin_name"] = signal.get("coin_name", "") or ""
                    row["entry_price"] = signal.get("entry_price", "") or ""
                    row["side"] = signal.get("side", "") or ""
                    row["stop_loss"] = signal.get("stop_loss", "") or ""
                    row["tp1"] = signal.get("tp1", "") or ""
                    row["tp2"] = signal.get("tp2", "") or ""
                    row["tp3"] = signal.get("tp3", "") or ""
                    row["tp4"] = signal.get("tp4", "") or ""
                
                writer.writerow(row)
        
        print(f"✅ Saved {len(results)} results to {output_file}")


async def parse_messages_from_chat(
    chat_id: str,
    gemini_api_key: str,
    telegram_api_id: int,
    telegram_api_hash: str,
    limit: Optional[int] = None,
    output_file: str = "parsed_signals.csv"
):
    """
    Fetch messages from a Telegram chat and parse them for trading signals.
    
    Args:
        chat_id: Telegram group/channel username or ID
        gemini_api_key: Google Gemini API key
        telegram_api_id: Telegram API ID
        telegram_api_hash: Telegram API Hash
        limit: Maximum number of messages to process (None = all)
        output_file: Output CSV file path
    """
    # Initialize scraper
    scraper = TelegramGroupScraper(
        api_id=telegram_api_id,
        api_hash=telegram_api_hash
    )
    
    # Initialize parser
    parser = SignalParser(gemini_api_key)
    
    print(f"📥 Fetching messages from {chat_id}...")
    messages = await scraper.get_all_messages(chat_id, limit=limit)
    
    if not messages:
        print("❌ No messages found.")
        return
    
    print(f"📊 Processing {len(messages)} messages with Gemini...")
    
    results = []
    for i, message in enumerate(messages, 1):
        # Get message text
        message_text = message.text or message.caption or ""
        
        if not message_text:
            # Skip messages without text
            continue
        
        # Parse message
        print(f"Processing message {i}/{len(messages)}: {message.id}")
        parsed_result = parser.parse_message(message_text)
        
        # Combine message metadata with parsed result
        result = {
            "message_id": message.id,
            "date": message.date.isoformat() if message.date else "",
            "message_text": message_text,
            **parsed_result
        }
        
        results.append(result)
        
        # Progress indicator
        if i % 10 == 0:
            print(f"  Processed {i}/{len(messages)} messages...")
    
    # Save to CSV
    parser.save_to_csv(results, output_file)
    
    # Print summary
    signal_count = sum(1 for r in results if r.get("is_signal", False))
    print(f"\n📈 Summary:")
    print(f"  Total messages processed: {len(results)}")
    print(f"  Signals found: {signal_count}")
    print(f"  Normal messages: {len(results) - signal_count}")


async def parse_realtime_messages(
    chat_id: str,
    gemini_api_key: str,
    telegram_api_id: int,
    telegram_api_hash: str,
    output_file: str = "parsed_signals_realtime.csv"
):
    """
    Listen for real-time messages and parse them for trading signals.
    
    Args:
        chat_id: Telegram group/channel username or ID
        gemini_api_key: Google Gemini API key
        telegram_api_id: Telegram API ID
        telegram_api_hash: Telegram API Hash
        output_file: Output CSV file path
    """
    # Initialize parser
    parser = SignalParser(gemini_api_key)
    
    # Initialize scraper
    scraper = TelegramGroupScraper(
        api_id=telegram_api_id,
        api_hash=telegram_api_hash
    )
    
    # Store results
    results = []
    
    async def process_message(message, formatted_msg):
        """Callback to process each incoming message"""
        message_text = formatted_msg.get("text", "")
        
        if not message_text:
            return
        
        print(f"\n📨 New message received: {message.id}")
        
        # Parse message
        parsed_result = parser.parse_message(message_text)
        
        # Combine message metadata with parsed result
        result = {
            "message_id": formatted_msg.get("message_id", ""),
            "date": formatted_msg.get("date", ""),
            "message_text": message_text,
            **parsed_result
        }
        
        results.append(result)
        
        # Append to CSV immediately
        parser.save_to_csv(results, output_file)
        
        # Print signal info if found
        if parsed_result.get("is_signal"):
            signal = parsed_result.get("signal", {})
            print(f"  ✅ SIGNAL DETECTED!")
            print(f"     Coin: {signal.get('coin_name', 'N/A')}")
            print(f"     Side: {signal.get('side', 'N/A')}")
            print(f"     Entry: {signal.get('entry_price', 'N/A')}")
            print(f"     Stop Loss: {signal.get('stop_loss', 'N/A')}")
        else:
            print(f"  ℹ️  Normal message")
    
    print(f"📡 Starting real-time listener for {chat_id}...")
    print("Press Ctrl+C to stop.\n")
    
    await scraper.listen_realtime(
        chat_id=chat_id,
        output_file=None,  # We'll handle CSV ourselves
        print_messages=False,  # We'll print our own format
        callback=process_message
    )


async def main():
    """Main function to run the parser."""
    import os
    
    # Get API credentials
    gemini_api_key = os.getenv("GEMINI_API_KEY", "REMOVED")
    telegram_api_id = int(os.getenv("TELEGRAM_API_ID", "REMOVED"))
    telegram_api_hash = os.getenv("TELEGRAM_API_HASH", "REMOVED")
    
    if not gemini_api_key:
        print("❌ ERROR: Please set GEMINI_API_KEY environment variable")
        print("Get your API key from: https://makersuite.google.com/app/apikey")
        return
    
    if not telegram_api_id or not telegram_api_hash:
        print("❌ ERROR: Please set TELEGRAM_API_ID and TELEGRAM_API_HASH")
        print("Get them from: https://my.telegram.org")
        return
    
    # Get chat ID
    chat_id = "Sayan_Saba"
    if not chat_id:
        print("No chat ID provided. Exiting.")
        return
    
    # Choose mode
    print("\nWhat would you like to do?")
    print("1. Parse historical messages")
    print("2. Parse real-time messages (listen for new messages)")
    
    choice = "2"
    
    if choice == "1":
        limit_input = input("Enter message limit (press Enter for all): ").strip()
        limit = int(limit_input) if limit_input else None
        
        output_file = input("Enter output CSV filename (default: parsed_signals.csv): ").strip() or "parsed_signals.csv"
        if not output_file.endswith('.csv'):
            output_file += '.csv'
        
        await parse_messages_from_chat(
            chat_id=chat_id,
            gemini_api_key=gemini_api_key,
            telegram_api_id=telegram_api_id,
            telegram_api_hash=telegram_api_hash,
            limit=limit,
            output_file=output_file
        )
    
    elif choice == "2":
        output_file = "parsed_signals_realtime.csv"
        if not output_file.endswith('.csv'):
            output_file += '.csv'
        
        await parse_realtime_messages(
            chat_id=chat_id,
            gemini_api_key=gemini_api_key,
            telegram_api_id=telegram_api_id,
            telegram_api_hash=telegram_api_hash,
            output_file=output_file
        )
    
    else:
        print("Invalid choice.")


if __name__ == "__main__":
    asyncio.run(main())