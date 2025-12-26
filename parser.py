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
import google.generativeai as genai
from pydantic import BaseModel, Field, field_validator, ValidationError
from scrapper import TelegramGroupScraper


class Signal(BaseModel):
    """Pydantic model for trading signal data."""
    coin_name: Optional[str] = Field(None, description="Coin name (e.g., IDOLUSDT.P)")
    entry_price: Optional[float] = Field(None, description="Entry price")
    stop_loss: Optional[float] = Field(None, description="Stop loss price")
    tp1: Optional[float] = Field(None, description="Take profit 1")
    tp2: Optional[float] = Field(None, description="Take profit 2")
    tp3: Optional[float] = Field(None, description="Take profit 3")
    tp4: Optional[float] = Field(None, description="Take profit 4")
    
    @field_validator('entry_price', 'stop_loss', 'tp1', 'tp2', 'tp3', 'tp4', mode='before')
    @classmethod
    def parse_float_or_none(cls, v):
        """Convert string numbers to float, keep None as None."""
        if v is None or v == "":
            return None
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            try:
                return float(v)
            except ValueError:
                return None
        return None


class SignalResponse(BaseModel):
    """Pydantic model for the complete response from Gemini."""
    is_signal: bool = Field(description="Whether the message is a trading signal")
    signal: Optional[Signal] = Field(None, description="Signal data if is_signal is true")
    
    def model_post_init(self, __context: Any):
        """Validate that signal is None when is_signal is False."""
        if not self.is_signal and self.signal is not None:
            self.signal = None


class SignalParser:
    def __init__(self, gemini_api_key: str):
        """
        Initialize the Signal Parser with Gemini API.
        
        Args:
            gemini_api_key: Your Google Gemini API key
        """
        genai.configure(api_key=gemini_api_key)
        
        # Convert Pydantic models to JSON schema
        raw_schema = SignalResponse.model_json_schema()
        
        # Clean schema to remove fields Gemini doesn't support
        self.response_schema = self._clean_schema_for_gemini(raw_schema)
        
        # Format schema as JSON string for inclusion in prompt
        schema_json = json.dumps(self.response_schema, indent=2)
        
        # First, find an available model
        model_name = self._get_available_model()
        
        # Initialize model with structured output configuration
        # Try to use structured output if supported
        try:
            generation_config = genai.types.GenerationConfig(
                response_mime_type="application/json",
                response_schema=self.response_schema
            )
            self.model = genai.GenerativeModel(
                model_name,
                generation_config=generation_config
            )
            print(f"✅ Using model: {model_name} with structured output")
        except (AttributeError, TypeError, ValueError, Exception) as e:
            # Fallback if structured output not supported in this version
            # Just use regular model and include schema in prompt
            print(f"⚠️  Structured output not available, using prompt-based schema: {e}")
            try:
                self.model = genai.GenerativeModel(model_name)
                print(f"✅ Using model: {model_name} (without structured output)")
            except Exception as model_error:
                print(f"❌ Error initializing model {model_name}: {model_error}")
                raise
            generation_config = None
        
        # System prompt with JSON schema included
        self.system_prompt = f"""You are a trading signal parser. Your task is to analyze Telegram messages and determine if they contain trading signals.

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

REQUIRED JSON SCHEMA (you must follow this exact structure):
{schema_json}

RULES:
1. If the message is a trading signal (contains coin name, entry price, stop loss, and at least one TP), set "is_signal" to true and fill the "signal" object.
2. If the message is NOT a signal, set "is_signal" to false and set "signal" to null.
3. Extract coin name (e.g., "IDOLUSDT.P", "BTCUSDT", etc.)
4. Extract entry price (may be marked as "CMP" or "Current Market Price")
5. Extract stop loss price
6. Extract take profit prices (TP 1, TP 2, TP 3, TP 4) - fill them if present, otherwise set to null
7. If there are more than 4 TPs, only extract the first 4
8. The response MUST conform exactly to the JSON schema provided above.

Return ONLY a valid JSON object matching the schema, no additional text or explanation.
"""
    
    def _get_available_model(self) -> str:
        """
        Get an available Gemini model that supports generateContent.
        
        Returns:
            Model name string
        """
        # Try common model names first
        common_models = [
            'gemini-1.5-flash',
            'gemini-1.5-pro',
            'gemini-pro',
            'gemini-2.0-flash-exp',
            'models/gemini-1.5-flash',
            'models/gemini-1.5-pro',
            'models/gemini-pro',
        ]
        
        # Try each common model
        for model_name in common_models:
            try:
                # Just test if we can create the model (doesn't make API call yet)
                test_model = genai.GenerativeModel(model_name)
                # If successful, return this model name
                print(f"✅ Found available model: {model_name}")
                return model_name
            except Exception:
                continue
        
        # If common models don't work, list available models
        print("⚠️  Common models not available, listing all models...")
        try:
            models = genai.list_models()
            available_models = []
            for m in models:
                if hasattr(m, 'supported_generation_methods') and 'generateContent' in m.supported_generation_methods:
                    model_name = m.name
                    # Extract just the model name part
                    if '/' in model_name:
                        model_name = model_name.split('/')[-1]
                    available_models.append(model_name)
            
            if available_models:
                selected = available_models[0]
                print(f"✅ Found available model from API: {selected}")
                print(f"   All available models: {available_models}")
                return selected
            else:
                raise ValueError("No models with generateContent support found")
        except Exception as e:
            print(f"⚠️  Could not list models: {e}")
            # Last resort: try gemini-1.5-flash (most commonly available)
            print("⚠️  Trying gemini-1.5-flash as fallback...")
            return 'gemini-1.5-flash'
        
        # System prompt with JSON schema included
        self.system_prompt = f"""You are a trading signal parser. Your task is to analyze Telegram messages and determine if they contain trading signals.

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

REQUIRED JSON SCHEMA (you must follow this exact structure):
{schema_json}

RULES:
1. If the message is a trading signal (contains coin name, entry price, stop loss, and at least one TP), set "is_signal" to true and fill the "signal" object.
2. If the message is NOT a signal, set "is_signal" to false and set "signal" to null.
3. Extract coin name (e.g., "IDOLUSDT.P", "BTCUSDT", etc.)
4. Extract entry price (may be marked as "CMP" or "Current Market Price")
5. Extract stop loss price
6. Extract take profit prices (TP 1, TP 2, TP 3, TP 4) - fill them if present, otherwise set to null
7. If there are more than 4 TPs, only extract the first 4
8. The response MUST conform exactly to the JSON schema provided above.

Return ONLY a valid JSON object matching the schema, no additional text or explanation.
"""
    
    def _clean_schema_for_gemini(self, schema: Dict[str, Any], defs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Clean JSON schema to remove fields that Gemini doesn't support.
        
        Args:
            schema: Raw JSON schema from Pydantic
            defs: Dictionary of definitions from $defs (for resolving $ref)
            
        Returns:
            Cleaned schema compatible with Gemini
        """
        if isinstance(schema, dict):
            # Extract $defs if present (first time through)
            if defs is None and '$defs' in schema:
                defs = schema.get('$defs', {})
            
            # Remove unsupported fields
            cleaned = {}
            for key, value in schema.items():
                # Skip $defs and other unsupported fields
                if key in ['$defs', '$schema', 'definitions']:
                    continue
                
                # Handle $ref references by resolving them
                if key == '$ref' and defs:
                    ref_path = value.split('/')[-1]
                    if ref_path in defs:
                        # Recursively resolve the reference
                        resolved = self._clean_schema_for_gemini(defs[ref_path], defs)
                        # Merge resolved schema into cleaned
                        cleaned.update(resolved)
                    else:
                        # If reference not found, make it a generic object
                        cleaned['type'] = 'object'
                    continue
                
                # Recursively clean nested objects
                if isinstance(value, (dict, list)):
                    cleaned[key] = self._clean_schema_for_gemini(value, defs)
                else:
                    cleaned[key] = value
            
            return cleaned
        elif isinstance(schema, list):
            return [self._clean_schema_for_gemini(item, defs) for item in schema]
        else:
            return schema
    
    def parse_message(self, message_text: str) -> Dict[str, Any]:
        """
        Parse a message using Gemini to extract signal information.
        Uses Pydantic to validate the response structure.
        
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
            
            # Call Gemini API with structured output
            response = self.model.generate_content(full_prompt)
            
            # With structured output, response.text should be valid JSON
            response_text = response.text.strip()
            
            # Parse JSON (should be valid due to schema enforcement)
            json_data = json.loads(response_text)
            
            # Validate and parse with Pydantic (double validation for safety)
            signal_response = SignalResponse(**json_data)
            
            # Convert to dictionary format
            result = {
                "is_signal": signal_response.is_signal,
                "signal": None
            }
            
            # Convert signal to dict if present
            if signal_response.signal:
                result["signal"] = {
                    "coin_name": signal_response.signal.coin_name,
                    "entry_price": signal_response.signal.entry_price,
                    "stop_loss": signal_response.signal.stop_loss,
                    "tp1": signal_response.signal.tp1,
                    "tp2": signal_response.signal.tp2,
                    "tp3": signal_response.signal.tp3,
                    "tp4": signal_response.signal.tp4,
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
        except ValidationError as e:
            print(f"⚠️  Pydantic validation error: {e}")
            if 'response_text' in locals():
                print(f"Response text: {response_text[:200]}...")
            # Try to extract what we can from the invalid data
            try:
                if 'json_data' in locals():
                    # Fallback: create a basic response
                    is_signal = json_data.get("is_signal", False)
                    return {
                        "is_signal": bool(is_signal),
                        "signal": None  # Set to None if validation fails
                    }
            except:
                pass
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
            "entry_price",
            "stop_loss",
            "tp1",
            "tp2",
            "tp3",
            "tp4"
        ]
        
        # Write to CSV
        file_exists = os.path.exists(output_file)
        
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
    # chat_id = input("Enter group username or ID (e.g., @mygroup or -1001234567890): ").strip()
    chat_id="Sayan_Saba"
    if not chat_id:
        print("No chat ID provided. Exiting.")
        return
    
    # Choose mode
    print("\nWhat would you like to do?")
    print("1. Parse historical messages")
    print("2. Parse real-time messages (listen for new messages)")
    
    # choice = input("Enter choice (1/2): ").strip()
    choice="2"
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
        # output_file = input("Enter output CSV filename (default: parsed_signals_realtime.csv): ").strip() or "parsed_signals_realtime.csv"
        output_file="parsed_signals_realtime.csv"
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

