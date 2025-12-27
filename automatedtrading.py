"""
Automated Trading System
Combines Telegram scraping, signal parsing, and automated order placement.
Scrapes messages from Telegram, parses them using LLM, and places orders on Binance.
"""

import asyncio
import json
import os
import time
from typing import Optional, Dict, Any, Tuple
from datetime import datetime
from dotenv import load_dotenv
from google import genai
from scrapper import TelegramGroupScraper
from tradingbotTest import BinanceFuturesTrader

# Load environment variables from .env file
load_dotenv()


class SignalParser:
    """Parser to extract trading signals from Telegram messages using Gemini LLM."""
    
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
    "coin_name": "IDOLUSDT" or null,
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


class AutomatedTradingSystem:
    """
    Automated Trading System that combines:
    - Telegram message scraping
    - Signal parsing using LLM
    - Automated order placement on Binance
    - Order monitoring
    """
    
    def __init__(
        self,
        gemini_api_key: str,
        telegram_api_id: int,
        telegram_api_hash: str,
        binance_api_key: str,
        binance_api_secret: str,
        testnet: bool = True,
        leverage: int = 1,
        dollar_amount: float = 10.0,
        wait_timeout: int = 300
    ):
        """
        Initialize the Automated Trading System.
        
        Args:
            gemini_api_key: Google Gemini API key for signal parsing
            telegram_api_id: Telegram API ID
            telegram_api_hash: Telegram API Hash
            binance_api_key: Binance API Key
            binance_api_secret: Binance API Secret
            testnet: Use Binance testnet (default: True)
            leverage: Default leverage for trades (default: 1)
            dollar_amount: Default amount in USDT to invest per trade (default: 10.0)
            wait_timeout: Timeout for order fills in seconds (default: 300)
        """
        # Initialize components
        self.parser = SignalParser(gemini_api_key)
        self.scraper = TelegramGroupScraper(
            api_id=telegram_api_id,
            api_hash=telegram_api_hash
        )
        self.trader = BinanceFuturesTrader(
            api_key=binance_api_key,
            api_secret=binance_api_secret,
            testnet=testnet
        )
        
        # Trading parameters
        self.leverage = leverage
        self.dollar_amount = dollar_amount
        self.wait_timeout = wait_timeout
        
        # Track processed signals to avoid duplicates
        self.processed_signals = set()
        
        print(f"\n{'='*60}")
        print(f"🤖 AUTOMATED TRADING SYSTEM INITIALIZED")
        print(f"{'='*60}")
        print(f"Mode: {'🧪 TESTNET' if testnet else '⚠️ LIVE TRADING'}")
        print(f"Default Leverage: {leverage}x")
        print(f"Default Trade Amount: ${dollar_amount:.2f} USDT per trade")
        print(f"{'='*60}\n")
    
    def validate_signal(self, signal: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validate that a signal has all required fields.
        
        Args:
            signal: Signal dictionary from parser
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not signal:
            return False, "Signal is None"
        
        # Check required fields
        coin_name = signal.get("coin_name")
        side = signal.get("side")
        entry_price = signal.get("entry_price")
        stop_loss = signal.get("stop_loss")
        
        # Check at least one take profit exists
        tp1 = signal.get("tp1")
        tp2 = signal.get("tp2")
        tp3 = signal.get("tp3")
        tp4 = signal.get("tp4")
        
        has_tp = any(tp is not None for tp in [tp1, tp2, tp3, tp4])
        
        # Validate each field
        if not coin_name:
            return False, "Missing coin_name"
        
        if not side or side not in ["LONG", "SHORT"]:
            return False, f"Invalid or missing side: {side}"
        
        if entry_price is None or entry_price <= 0:
            return False, f"Invalid entry_price: {entry_price}"
        
        if stop_loss is None or stop_loss <= 0:
            return False, f"Invalid stop_loss: {stop_loss}"
        
        if not has_tp:
            return False, "Missing all take profit levels"
        
        return True, "Valid signal"
    
    def normalize_symbol(self, coin_name: str) -> str:
        """
        Normalize coin name to Binance symbol format.
        Removes .P suffix and converts to uppercase.
        
        Args:
            coin_name: Coin name from signal (e.g., "IDOLUSDT.P", "BTCUSDT")
            
        Returns:
            Normalized symbol (e.g., "IDOLUSDT", "BTCUSDT")
        """
        # Remove .P suffix if present
        symbol = coin_name.replace(".P", "").upper()
        return symbol
    
    def get_take_profits(self, signal: Dict[str, Any]) -> list[float]:
        """
        Extract all non-null take profit prices from signal.
        
        Args:
            signal: Signal dictionary
            
        Returns:
            List of take profit prices
        """
        tps = []
        for tp_key in ["tp1", "tp2", "tp3", "tp4"]:
            tp_value = signal.get(tp_key)
            if tp_value is not None and tp_value > 0:
                tps.append(tp_value)
        return tps
    
    def place_order_from_signal(self, signal: Dict[str, Any]) -> bool:
        """
        Place order on Binance based on validated signal.
        
        Args:
            signal: Validated signal dictionary
            
        Returns:
            True if order was placed successfully, False otherwise
        """
        # Extract signal data
        coin_name = signal.get("coin_name")
        side = signal.get("side")
        entry_price = signal.get("entry_price")
        stop_loss = signal.get("stop_loss")
        
        # Normalize symbol
        symbol = self.normalize_symbol(coin_name)
        
        # Get take profits
        tp_list = self.get_take_profits(signal)
        
        # Ensure we have at least 4 TPs (pad with None if needed)
        while len(tp_list) < 4:
            tp_list.append(None)
        
        tp1, tp2, tp3, tp4 = tp_list[:4]
        
        # If we have fewer than 4 TPs, use the last TP for remaining ones
        if tp4 is None and tp3 is not None:
            tp4 = tp3
        if tp3 is None and tp2 is not None:
            tp3 = tp2
        if tp2 is None and tp1 is not None:
            tp2 = tp1
        
        print(f"\n{'='*60}")
        print(f"📊 PLACING ORDER FROM SIGNAL")
        print(f"{'='*60}")
        print(f"Symbol: {symbol}")
        print(f"Side: {side}")
        print(f"Entry Price: {entry_price}")
        print(f"Stop Loss: {stop_loss}")
        print(f"Take Profits: {tp1}, {tp2}, {tp3}, {tp4}")
        print(f"Trade Amount: ${self.dollar_amount:.2f} USDT")
        print(f"Leverage: {self.leverage}x")
        print(f"{'='*60}\n")
        
        # Execute trade
        try:
            success = self.trader.execute_trade(
                symbol=symbol,
                direction=side,
                leverage=self.leverage,
                entry_price=entry_price,
                dollar_amount=self.dollar_amount,
                stop_loss_price=stop_loss,
                tp1_price=tp1,
                tp2_price=tp2,
                tp3_price=tp3,
                tp4_price=tp4,
                wait_timeout=self.wait_timeout,
                auto_monitor=True  # Automatically start monitoring
            )
            
            if success:
                print(f"\n✅ Order placed successfully!")
                return True
            else:
                print(f"\n❌ Failed to place order")
                return False
                
        except Exception as e:
            print(f"\n❌ Error placing order: {e}")
            return False
    
    def create_signal_id(self, signal: Dict[str, Any]) -> str:
        """
        Create a unique ID for a signal to avoid duplicate processing.
        
        Args:
            signal: Signal dictionary
            
        Returns:
            Unique signal ID string
        """
        coin_name = signal.get("coin_name", "")
        side = signal.get("side", "")
        entry_price = signal.get("entry_price", 0)
        timestamp = int(time.time())
        
        return f"{coin_name}_{side}_{entry_price}_{timestamp}"
    
    async def process_message(self, message, formatted_msg: Dict[str, Any]):
        """
        Process an incoming Telegram message.
        Parses, validates, and places order if valid signal.
        
        Args:
            message: Pyrogram Message object
            formatted_msg: Formatted message dictionary
        """
        message_text = formatted_msg.get("text", "")
        
        if not message_text:
            return
        
        print(f"\n📨 New message received: {message.id}")
        print(f"   Preview: {message_text[:100]}...")
        
        # Parse message
        parsed_result = self.parser.parse_message(message_text)
        
        # Check if it's a signal
        if not parsed_result.get("is_signal"):
            print(f"   ℹ️  Normal message (not a signal)")
            return
        
        signal = parsed_result.get("signal")
        if not signal:
            print(f"   ⚠️  Signal flag is True but signal data is None")
            return
        
        # Validate signal
        is_valid, error_msg = self.validate_signal(signal)
        
        if not is_valid:
            print(f"   ❌ Invalid signal: {error_msg}")
            print(f"   Signal data: {signal}")
            return
        
        # Create signal ID to avoid duplicates
        signal_id = self.create_signal_id(signal)
        
        if signal_id in self.processed_signals:
            print(f"   ⚠️  Signal already processed (duplicate)")
            return
        
        # Mark as processed
        self.processed_signals.add(signal_id)
        
        # Display signal info
        print(f"\n   ✅ VALID SIGNAL DETECTED!")
        print(f"   Coin: {signal.get('coin_name')}")
        print(f"   Side: {signal.get('side')}")
        print(f"   Entry: {signal.get('entry_price')}")
        print(f"   Stop Loss: {signal.get('stop_loss')}")
        print(f"   TPs: {[tp for tp in [signal.get('tp1'), signal.get('tp2'), signal.get('tp3'), signal.get('tp4')] if tp is not None]}")
        
        # Place order
        print(f"\n   🚀 Attempting to place order...")
        success = self.place_order_from_signal(signal)
        
        if success:
            print(f"   ✅ Order placed and monitoring started!")
        else:
            print(f"   ❌ Failed to place order")
    
    async def start_monitoring(self, chat_id: str):
        """
        Start monitoring Telegram chat for new messages and process them.
        
        Args:
            chat_id: Telegram group/channel username or ID
        """
        print(f"\n{'='*60}")
        print(f"📡 STARTING AUTOMATED TRADING MONITOR")
        print(f"{'='*60}")
        print(f"Chat ID: {chat_id}")
        print(f"Monitoring for trading signals...")
        print(f"Press Ctrl+C to stop.\n")
        print(f"{'='*60}\n")
        
        # Start real-time monitoring
        await self.scraper.listen_realtime(
            chat_id=chat_id,
            output_file=None,
            print_messages=False,
            callback=self.process_message
        )


async def main():
    """Main function to run the automated trading system."""
    print("="*60)
    print("AUTOMATED TRADING SYSTEM")
    print("="*60)
    print("\n⚠️  IMPORTANT SECURITY & RISK INFORMATION ⚠️")
    print("This system will automatically place trades based on Telegram signals.")
    print("Use at your own risk!")
    print("="*60)
    
    # Get API credentials from environment or user input
    gemini_api_key = os.getenv("GEMINI_API_KEY", "")
    telegram_api_id = int(os.getenv("TELEGRAM_API_ID", "0"))
    telegram_api_hash = os.getenv("TELEGRAM_API_HASH", "")
    
    if not gemini_api_key:
        gemini_api_key = input("\nEnter Gemini API Key: ").strip()
    if telegram_api_id == 0:
        telegram_api_id = int(input("Enter Telegram API ID: ").strip())
    if not telegram_api_hash:
        telegram_api_hash = input("Enter Telegram API Hash: ").strip()
    
    # Choose testnet or live
    mode = input("\nUse TESTNET (practice) or LIVE (real money)? (testnet/live): ").strip().lower()
    testnet = (mode == 'testnet')
    
    if not testnet:
        print("\n" + "!"*60)
        print("⚠️  WARNING: YOU ARE USING LIVE TRADING MODE!")
        print("!"*60)
        print("This will use REAL MONEY from your Binance account.")
        confirm_live = input("Type 'I UNDERSTAND' to continue: ").strip()
        if confirm_live != 'I UNDERSTAND':
            print("Exiting for safety...")
            return
    
    # Get Binance credentials
    binance_api_key = input("\nEnter Binance API Key: ").strip()
    binance_api_secret = input("Enter Binance API Secret: ").strip()
    
    # Get trading parameters
    print("\n--- Trading Parameters ---")
    leverage = int(input("Enter leverage (1-125, default 1): ").strip() or "1")
    dollar_amount = float(input("Enter amount in USDT to invest per trade (default 10.0): ").strip() or "10.0")
    wait_timeout = int(input("Enter order wait timeout in seconds (default 300): ").strip() or "300")
    
    # Get chat ID
    chat_id = input("\nEnter Telegram chat ID to monitor: ").strip()
    if not chat_id:
        print("No chat ID provided. Exiting.")
        return
    
    # Initialize automated trading system
    trading_system = AutomatedTradingSystem(
        gemini_api_key=gemini_api_key,
        telegram_api_id=telegram_api_id,
        telegram_api_hash=telegram_api_hash,
        binance_api_key=binance_api_key,
        binance_api_secret=binance_api_secret,
        testnet=testnet,
        leverage=leverage,
        dollar_amount=dollar_amount,
        wait_timeout=wait_timeout
    )
    
    # Start monitoring
    try:
        await trading_system.start_monitoring(chat_id)
    except KeyboardInterrupt:
        print(f"\n\n🛑 Monitoring stopped by user.")
        print(f"Active monitors: {len(trading_system.trader.active_monitors)}")
        if trading_system.trader.active_monitors:
            print(f"⚠️  IMPORTANT: Orders are still being monitored in background!")
            print(f"   Monitor status:")
            for monitor in trading_system.trader.get_active_monitors():
                print(f"   - {monitor['symbol']}: SL={monitor['sl_order_id']}, TPs={monitor['tp_order_ids']}")


if __name__ == "__main__":
    asyncio.run(main())

