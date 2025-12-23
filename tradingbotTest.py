import hmac
import hashlib
import time
import requests
from urllib.parse import urlencode

class BinanceFuturesTrader:
    def __init__(self, api_key, api_secret, testnet=False):
        """
        Initialize the Binance Futures Trading Bot
        
        Args:
            api_key (str): Your Binance API Key
            api_secret (str): Your Binance API Secret
            testnet (bool): Use testnet instead of live trading
        """
        self.api_key = api_key
        self.api_secret = api_secret
        
        # Use testnet or live API
        if testnet:
            self.base_url = "https://testnet.binancefuture.com"
            print("🧪 TESTNET MODE - No real money at risk")
        else:
            self.base_url = "https://fapi.binance.com"
            print("⚠️ LIVE TRADING MODE - Real money at risk!")
        
        self.headers = {'X-MBX-APIKEY': api_key}
    
    def _generate_signature(self, params):
        """Generate HMAC SHA256 signature"""
        query_string = urlencode(params)
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def _make_request(self, method, endpoint, params=None):
        """Make authenticated request to Binance API"""
        if params is None:
            params = {}
        
        params['timestamp'] = int(time.time() * 1000)
        params['signature'] = self._generate_signature(params)
        
        url = f"{self.base_url}{endpoint}"
        
        try:
            if method == "GET":
                response = requests.get(url, headers=self.headers, params=params)
            elif method == "POST":
                response = requests.post(url, headers=self.headers, params=params)
            elif method == "DELETE":
                response = requests.delete(url, headers=self.headers, params=params)
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"API Request Error: {e}")
            if hasattr(e.response, 'text'):
                print(f"Response: {e.response.text}")
            return None
    
    def set_leverage(self, symbol, leverage):
        """
        Set leverage for a symbol
        
        Args:
            symbol (str): Trading pair (e.g., 'BTCUSDT')
            leverage (int): Leverage value (1-125)
        """
        endpoint = "/fapi/v1/leverage"
        params = {
            'symbol': symbol,
            'leverage': leverage
        }
        
        result = self._make_request("POST", endpoint, params)
        if result:
            print(f"✓ Leverage set to {leverage}x for {symbol}")
            return result
        return None
    
    def get_position_info(self, symbol):
        """Get current position information"""
        endpoint = "/fapi/v2/positionRisk"
        params = {'symbol': symbol}
        
        result = self._make_request("GET", endpoint, params)
        if result:
            for pos in result:
                if pos['symbol'] == symbol and float(pos['positionAmt']) != 0:
                    return pos
        return None
    
    def place_market_order(self, symbol, side, quantity, position_side="BOTH"):
        """
        Place a market order
        
        Args:
            symbol (str): Trading pair
            side (str): 'BUY' or 'SELL'
            quantity (float): Order quantity
            position_side (str): 'BOTH', 'LONG', or 'SHORT' (for hedge mode)
        """
        endpoint = "/fapi/v1/order"
        params = {
            'symbol': symbol,
            'side': side,
            'type': 'MARKET',
            'quantity': quantity,
            'positionSide': position_side
        }
        
        result = self._make_request("POST", endpoint, params)
        if result:
            print(f"✓ Market order placed: {side} {quantity} {symbol}")
            return result
        return None
    
    def place_stop_loss(self, symbol, side, stop_price, quantity, position_side="BOTH"):
        """
        Place stop loss order
        
        Args:
            symbol (str): Trading pair
            side (str): 'BUY' or 'SELL' (opposite of entry)
            stop_price (float): Stop loss trigger price
            quantity (float): Order quantity
            position_side (str): 'BOTH', 'LONG', or 'SHORT'
        """
        endpoint = "/fapi/v1/order"
        params = {
            'symbol': symbol,
            'side': side,
            'type': 'STOP_MARKET',
            'stopPrice': stop_price,
            'closePosition': 'false',
            'quantity': quantity,
            'positionSide': position_side,
            'reduceOnly': 'true',
            'workingType': 'MARK_PRICE'
        }
        
        result = self._make_request("POST", endpoint, params)
        if result:
            print(f"✓ Stop Loss placed at {stop_price}")
            return result
        return None
    
    def place_take_profit(self, symbol, side, tp_price, quantity, position_side="BOTH"):
        """
        Place take profit order
        
        Args:
            symbol (str): Trading pair
            side (str): 'BUY' or 'SELL' (opposite of entry)
            tp_price (float): Take profit trigger price
            quantity (float): Order quantity (e.g., 25% of position)
            position_side (str): 'BOTH', 'LONG', or 'SHORT'
        """
        endpoint = "/fapi/v1/order"
        params = {
            'symbol': symbol,
            'side': side,
            'type': 'TAKE_PROFIT_MARKET',
            'stopPrice': tp_price,
            'quantity': quantity,
            'positionSide': position_side,
            'reduceOnly': 'true',
            'workingType': 'MARK_PRICE'
        }
        
        result = self._make_request("POST", endpoint, params)
        if result:
            print(f"✓ Take Profit placed at {tp_price} for {quantity}")
            return result
        return None
    
    def get_symbol_info(self, symbol):
        """Get trading rules for symbol (precision, min quantity, etc.)"""
        endpoint = "/fapi/v1/exchangeInfo"
        
        try:
            response = requests.get(f"{self.base_url}{endpoint}")
            data = response.json()
            
            for s in data['symbols']:
                if s['symbol'] == symbol:
                    return s
            return None
        except Exception as e:
            print(f"Error getting symbol info: {e}")
            return None
    
    def round_quantity(self, quantity, step_size):
        """Round quantity to match exchange precision"""
        precision = len(str(step_size).rstrip('0').split('.')[-1])
        return round(quantity, precision)
    
    def execute_trade(self, symbol, direction, leverage, entry_price, quantity, 
                      stop_loss_price, tp1_price, tp2_price, tp3_price, tp4_price):
        """
        Execute complete trade with entry, stop loss, and 4 take profits
        
        Args:
            symbol (str): Trading pair (e.g., 'BTCUSDT')
            direction (str): 'LONG' or 'SHORT'
            leverage (int): Leverage (1-125)
            entry_price (float): Entry price (for info, uses MARKET)
            quantity (float): Total position size
            stop_loss_price (float): Stop loss price
            tp1_price, tp2_price, tp3_price, tp4_price (float): Take profit prices
        """
        print(f"\n{'='*60}")
        print(f"EXECUTING TRADE FOR {symbol}")
        print(f"{'='*60}")
        
        # Get symbol info for precision
        symbol_info = self.get_symbol_info(symbol)
        if not symbol_info:
            print("❌ Could not get symbol information")
            return False
        
        # Find quantity precision
        quantity_precision = None
        for filter in symbol_info['filters']:
            if filter['filterType'] == 'LOT_SIZE':
                step_size = float(filter['stepSize'])
                quantity = self.round_quantity(quantity, step_size)
                break
        
        # Step 1: Set leverage
        print(f"\n[1/6] Setting leverage to {leverage}x...")
        if not self.set_leverage(symbol, leverage):
            return False
        
        # Step 2: Place entry order
        print(f"\n[2/6] Placing {direction} entry order...")
        entry_side = 'BUY' if direction == 'LONG' else 'SELL'
        entry_order = self.place_market_order(symbol, entry_side, quantity)
        if not entry_order:
            return False
        
        # Wait a moment for order to fill
        time.sleep(2)
        
        # Calculate TP quantities (25% each)
        tp_quantity = self.round_quantity(quantity * 0.25, step_size)
        
        # Determine close side (opposite of entry)
        close_side = 'SELL' if direction == 'LONG' else 'BUY'
        
        # Step 3: Place Stop Loss
        print(f"\n[3/6] Placing Stop Loss at {stop_loss_price}...")
        if not self.place_stop_loss(symbol, close_side, stop_loss_price, quantity):
            print("⚠️ Warning: Stop loss placement failed!")
        
        # Step 4-7: Place 4 Take Profits
        tp_prices = [tp1_price, tp2_price, tp3_price, tp4_price]
        for i, tp_price in enumerate(tp_prices, 1):
            print(f"\n[{3+i}/6] Placing Take Profit {i} at {tp_price}...")
            if not self.place_take_profit(symbol, close_side, tp_price, tp_quantity):
                print(f"⚠️ Warning: Take Profit {i} placement failed!")
        
        print(f"\n{'='*60}")
        print(f"✓ TRADE EXECUTION COMPLETE")
        print(f"{'='*60}")
        print(f"Position: {direction} {quantity} {symbol} @ {leverage}x leverage")
        print(f"Stop Loss: {stop_loss_price}")
        print(f"Take Profits: {tp1_price}, {tp2_price}, {tp3_price}, {tp4_price}")
        print(f"Each TP closes: {tp_quantity} ({symbol})")
        
        return True


def main():
    """Main trading interface"""
    print("="*60)
    print("BINANCE FUTURES TRADING BOT")
    print("="*60)
    print("\n⚠️  IMPORTANT SECURITY & RISK INFORMATION ⚠️")
    print("\nPlease read the SECURITY_GUIDE.txt before using!")
    print("="*60)
    
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
    
    # Get API credentials
    api_key = input("\nEnter your Binance API Key: ").strip()
    api_secret = input("Enter your Binance API Secret: ").strip()
    
    # Initialize trader
    trader = BinanceFuturesTrader(api_key, api_secret, testnet=testnet)
    
    while True:
        print("\n" + "="*60)
        print("NEW TRADE SETUP")
        print("="*60)
        
        # Get trade parameters
        symbol = input("\nEnter symbol (e.g., BTCUSDT): ").strip().upper()
        
        direction = input("Enter direction (LONG/SHORT): ").strip().upper()
        while direction not in ['LONG', 'SHORT']:
            direction = input("Invalid! Enter LONG or SHORT: ").strip().upper()
        
        leverage = int(input("Enter leverage (1-125): ").strip())
        
        entry_price = float(input("Enter entry price (for reference): ").strip())
        quantity = float(input("Enter quantity to trade: ").strip())
        
        stop_loss_price = float(input("Enter Stop Loss price: ").strip())
        
        print("\n--- Take Profit Levels (25% each) ---")
        tp1_price = float(input("Enter Take Profit 1 price: ").strip())
        tp2_price = float(input("Enter Take Profit 2 price: ").strip())
        tp3_price = float(input("Enter Take Profit 3 price: ").strip())
        tp4_price = float(input("Enter Take Profit 4 price: ").strip())
        
        # Confirm trade
        print("\n" + "="*60)
        print("TRADE SUMMARY")
        print("="*60)
        print(f"Symbol: {symbol}")
        print(f"Direction: {direction}")
        print(f"Leverage: {leverage}x")
        print(f"Quantity: {quantity}")
        print(f"Entry Price: {entry_price}")
        print(f"Stop Loss: {stop_loss_price}")
        print(f"Take Profit 1 (25%): {tp1_price}")
        print(f"Take Profit 2 (25%): {tp2_price}")
        print(f"Take Profit 3 (25%): {tp3_price}")
        print(f"Take Profit 4 (25%): {tp4_price}")
        print("="*60)
        
        confirm = input("\nExecute this trade? (yes/no): ").strip().lower()
        
        if confirm == 'yes':
            trader.execute_trade(
                symbol=symbol,
                direction=direction,
                leverage=leverage,
                entry_price=entry_price,
                quantity=quantity,
                stop_loss_price=stop_loss_price,
                tp1_price=tp1_price,
                tp2_price=tp2_price,
                tp3_price=tp3_price,
                tp4_price=tp4_price
            )
        else:
            print("\n❌ Trade cancelled")
        
        # Ask if user wants to place another trade
        another = input("\nPlace another trade? (yes/no): ").strip().lower()
        if another != 'yes':
            print("\nThank you for using Binance Futures Trading Bot!")
            break


if __name__ == "__main__":
    main()