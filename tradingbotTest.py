import hmac
import hashlib
import time
import threading
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
        
        # Track active monitoring threads
        self.active_monitors = []
    
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
    
    def place_limit_order(self, symbol, side, quantity, price, position_side="BOTH", time_in_force="GTC"):
        """
        Place a limit order
        
        Args:
            symbol (str): Trading pair
            side (str): 'BUY' or 'SELL'
            quantity (float): Order quantity
            price (float): Limit price
            position_side (str): 'BOTH', 'LONG', or 'SHORT' (for hedge mode)
            time_in_force (str): 'GTC' (Good Till Cancel), 'IOC', 'FOK'
        """
        endpoint = "/fapi/v1/order"
        params = {
            'symbol': symbol,
            'side': side,
            'type': 'LIMIT',
            'quantity': quantity,
            'price': price,
            'timeInForce': time_in_force,
            'positionSide': position_side
        }
        
        result = self._make_request("POST", endpoint, params)
        if result:
            print(f"✓ Limit order placed: {side} {quantity} {symbol} @ {price}")
            return result
        return None
    
    def cancel_order(self, symbol, order_id):
        """Cancel an open order"""
        endpoint = "/fapi/v1/order"
        params = {
            'symbol': symbol,
            'orderId': order_id
        }
        
        result = self._make_request("DELETE", endpoint, params)
        if result:
            print(f"✓ Order {order_id} cancelled")
            return result
        return None
    
    def check_order_status(self, symbol, order_id):
        """Check if order is filled"""
        endpoint = "/fapi/v1/order"
        params = {
            'symbol': symbol,
            'orderId': order_id
        }
        
        result = self._make_request("GET", endpoint, params)
        return result
    
    def wait_for_order_fill(self, symbol, order_id, timeout_seconds):
        """
        Wait for order to fill, cancel if timeout
        
        Args:
            symbol (str): Trading pair
            order_id (int): Order ID to monitor
            timeout_seconds (int): How long to wait before canceling
            
        Returns:
            bool: True if filled, False if cancelled/failed
        """
        print(f"\n⏳ Waiting up to {timeout_seconds} seconds for order to fill...")
        
        start_time = time.time()
        check_interval = 2  # Check every 2 seconds
        
        while time.time() - start_time < timeout_seconds:
            elapsed = int(time.time() - start_time)
            remaining = timeout_seconds - elapsed
            print(f"   Checking order status... ({remaining}s remaining)", end='\r')
            
            order_status = self.check_order_status(symbol, order_id)
            
            if order_status:
                status = order_status.get('status')
                
                if status == 'FILLED':
                    filled_qty = order_status.get('executedQty')
                    avg_price = order_status.get('avgPrice')
                    print(f"\n✓ Order FILLED! Quantity: {filled_qty}, Avg Price: {avg_price}")
                    return True
                
                elif status in ['CANCELED', 'REJECTED', 'EXPIRED']:
                    print(f"\n❌ Order {status}")
                    return False
            
            time.sleep(check_interval)
        
        # Timeout reached - cancel the order
        print(f"\n⏰ Timeout reached ({timeout_seconds}s). Canceling order...")
        self.cancel_order(symbol, order_id)
        return False
    
    def place_stop_loss(self, symbol, side, stop_price, quantity, position_side="BOTH", client_order_id=None):
        """
        Place stop loss order
        
        Args:
            symbol (str): Trading pair
            side (str): 'BUY' or 'SELL' (opposite of entry)
            stop_price (float): Stop loss trigger price
            quantity (float): Order quantity
            position_side (str): 'BOTH', 'LONG', or 'SHORT'
            client_order_id (str): Custom order ID for tracking
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
        
        if client_order_id:
            params['newClientOrderId'] = client_order_id
        
        result = self._make_request("POST", endpoint, params)
        if result:
            order_id = result.get('orderId')
            print(f"✓ Stop Loss placed at {stop_price} (Order ID: {order_id})")
            return result
        return None
    
    def place_take_profit(self, symbol, side, tp_price, quantity, position_side="BOTH", client_order_id=None):
        """
        Place take profit order
        
        Args:
            symbol (str): Trading pair
            side (str): 'BUY' or 'SELL' (opposite of entry)
            tp_price (float): Take profit trigger price
            quantity (float): Order quantity (e.g., 25% of position)
            position_side (str): 'BOTH', 'LONG', or 'SHORT'
            client_order_id (str): Custom order ID for tracking
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
        
        if client_order_id:
            params['newClientOrderId'] = client_order_id
        
        result = self._make_request("POST", endpoint, params)
        if result:
            order_id = result.get('orderId')
            print(f"✓ Take Profit placed at {tp_price} for {quantity} (Order ID: {order_id})")
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
    
    def round_price(self, price, tick_size):
        """Round price to match exchange precision"""
        precision = len(str(tick_size).rstrip('0').split('.')[-1])
        return round(price, precision)
    
    def get_all_open_orders(self, symbol):
        """Get all open orders for a symbol"""
        endpoint = "/fapi/v1/openOrders"
        params = {'symbol': symbol}
        
        result = self._make_request("GET", endpoint, params)
        return result if result else []
    
    def monitor_and_manage_orders(self, symbol, sl_order_id, tp_order_ids):
        """
        Monitor and manage orders automatically (runs in background thread)
        
        Features:
        - Monitors SL and all 4 TP orders
        - Shows real-time status: "TPs filled: 2/4"
        - Auto-cancels SL when all TPs are filled
        - Auto-cancels remaining TPs when SL is filled
        - Runs in background so you can place new orders
        
        Args:
            symbol (str): Trading pair
            sl_order_id (int): Stop Loss order ID
            tp_order_ids (list): List of 4 Take Profit order IDs
        """
        thread_name = threading.current_thread().name
        print(f"\n{'='*60}")
        print(f"🔍 ORDER MONITORING ACTIVE [{thread_name}]")
        print(f"{'='*60}")
        print(f"Monitoring orders every 10 seconds...")
        print(f"Symbol: {symbol}")
        print(f"Stop Loss Order ID: {sl_order_id}")
        print(f"Take Profit Order IDs: {tp_order_ids}")
        print(f"Running in background - you can place new orders!")
        print(f"{'='*60}\n")
        
        check_interval = 10  # Check every 10 seconds
        monitoring = True
        
        while monitoring:
            try:
                # Check status of all orders
                sl_status = self.check_order_status(symbol, sl_order_id)
                tp_statuses = [self.check_order_status(symbol, tp_id) for tp_id in tp_order_ids]
                
                # Count filled TPs and track active ones
                filled_tps = 0
                active_tp_ids = []
                
                for i, tp_status in enumerate(tp_statuses):
                    if tp_status:
                        status = tp_status.get('status', 'UNKNOWN')
                        if status == 'FILLED':
                            filled_tps += 1
                        elif status in ['NEW', 'PARTIALLY_FILLED']:
                            active_tp_ids.append(tp_order_ids[i])
                    # If order doesn't exist (None), assume it was filled or cancelled
                    # This handles edge cases where order might have been manually cancelled
                
                # Check SL status
                sl_filled = False
                sl_active = False
                if sl_status:
                    sl_status_value = sl_status.get('status', 'UNKNOWN')
                    if sl_status_value == 'FILLED':
                        sl_filled = True
                    elif sl_status_value in ['NEW', 'PARTIALLY_FILLED']:
                        sl_active = True
                
                # Update monitor status for UI access
                self._update_monitor_status(symbol, sl_order_id, filled_tps, sl_active, sl_filled)
                
                # Display status (with timestamp for better tracking)
                timestamp = time.strftime("%H:%M:%S")
                print(f"[{timestamp}] 📊 Status: TPs filled: {filled_tps}/4 | SL: {'Active' if sl_active else 'Filled/Cancelled'}", end='\r')
                
                # Scenario 1: All 4 TPs filled - Cancel SL
                if filled_tps == 4:
                    print(f"\n\n{'='*60}")
                    print(f"✓ All 4 Take Profits have been FILLED!")
                    print(f"{'='*60}")
                    
                    # Check if SL is still active
                    if sl_active:
                        print(f"Canceling Stop Loss order {sl_order_id}...")
                        cancel_result = self.cancel_order(symbol, sl_order_id)
                        if cancel_result:
                            print(f"✓ Stop Loss successfully cancelled!")
                        else:
                            print(f"⚠️ Warning: Failed to cancel Stop Loss. Please check manually.")
                    else:
                        print(f"ℹ️ Stop Loss already filled or cancelled.")
                    
                    print(f"\n🎉 Trade completed successfully - All profits taken!")
                    print(f"{'='*60}")
                    # Remove from active monitors
                    self._remove_monitor(symbol, sl_order_id)
                    monitoring = False
                    break
                
                # Scenario 2: Stop Loss filled - Cancel remaining TPs
                if sl_filled:
                    print(f"\n\n{'='*60}")
                    print(f"❌ Stop Loss was triggered!")
                    print(f"{'='*60}")
                    print(f"Remaining TPs: {len(active_tp_ids)}")
                    
                    if active_tp_ids:
                        print(f"Canceling remaining TP orders...")
                        for tp_id in active_tp_ids:
                            cancel_result = self.cancel_order(symbol, tp_id)
                            if cancel_result:
                                print(f"✓ TP order {tp_id} cancelled")
                            else:
                                print(f"⚠️ Warning: Failed to cancel TP {tp_id}")
                    
                    print(f"\n⚠️ Trade stopped out.")
                    print(f"{'='*60}")
                    # Remove from active monitors
                    self._remove_monitor(symbol, sl_order_id)
                    monitoring = False
                    break
                
                # Scenario 3: All orders filled or cancelled (edge case)
                # If SL is not active and no TPs are active, monitoring is complete
                if not sl_active and len(active_tp_ids) == 0:
                    print(f"\n\n{'='*60}")
                    if filled_tps == 4:
                        print(f"ℹ️ All Take Profits filled and Stop Loss handled.")
                    else:
                        print(f"ℹ️ All orders have been filled or cancelled.")
                    print(f"{'='*60}")
                    # Remove from active monitors
                    self._remove_monitor(symbol, sl_order_id)
                    monitoring = False
                    break
                
                # Continue monitoring
                time.sleep(check_interval)
                
            except KeyboardInterrupt:
                print(f"\n\n🛑 Monitoring stopped by user.")
                print(f"⚠️  IMPORTANT: Orders are still active on Binance!")
                print(f"   You may need to manually manage them.")
                # Remove from active monitors
                self._remove_monitor(symbol, sl_order_id)
                monitoring = False
                break
            except Exception as e:
                print(f"\n⚠️ Error during monitoring: {e}")
                print(f"Continuing to monitor...")
                time.sleep(check_interval)
    
    def _update_monitor_status(self, symbol, sl_order_id, filled_tps, sl_active, sl_filled):
        """Update status information for a monitor"""
        for monitor in self.active_monitors:
            if monitor['symbol'] == symbol and monitor['sl_order_id'] == sl_order_id:
                monitor['status']['filled_tps'] = filled_tps
                if sl_filled:
                    monitor['status']['sl_status'] = 'Filled'
                elif sl_active:
                    monitor['status']['sl_status'] = 'Active'
                else:
                    monitor['status']['sl_status'] = 'Cancelled/Unknown'
                monitor['status']['last_update'] = time.time()
                break
    
    def _remove_monitor(self, symbol, sl_order_id):
        """Remove completed monitor from active monitors list"""
        self.active_monitors = [
            m for m in self.active_monitors 
            if not (m['symbol'] == symbol and m['sl_order_id'] == sl_order_id)
        ]
    
    def get_active_monitors(self):
        """Get list of active monitoring threads with basic info"""
        return [
            {
                'symbol': m['symbol'],
                'sl_order_id': m['sl_order_id'],
                'tp_order_ids': m['tp_order_ids'],
                'thread_alive': m['thread'].is_alive(),
                'runtime': int(time.time() - m['started_at'])
            }
            for m in self.active_monitors
        ]
    
    def get_monitor_status(self, symbol=None, sl_order_id=None):
        """
        Get detailed status of monitoring threads
        
        Args:
            symbol (str, optional): Filter by symbol
            sl_order_id (int, optional): Filter by SL order ID
            
        Returns:
            list: List of monitor status dictionaries
        """
        monitors = self.active_monitors
        if symbol:
            monitors = [m for m in monitors if m['symbol'] == symbol]
        if sl_order_id:
            monitors = [m for m in monitors if m['sl_order_id'] == sl_order_id]
        
        result = []
        for m in monitors:
            status = m.get('status', {})
            result.append({
                'symbol': m['symbol'],
                'sl_order_id': m['sl_order_id'],
                'tp_order_ids': m['tp_order_ids'],
                'filled_tps': status.get('filled_tps', 0),
                'total_tps': status.get('total_tps', 4),
                'sl_status': status.get('sl_status', 'Unknown'),
                'thread_alive': m['thread'].is_alive(),
                'runtime_seconds': int(time.time() - m['started_at']),
                'last_update': status.get('last_update', m['started_at'])
            })
        
        return result
    
    def execute_trade(self, symbol, direction, leverage, entry_price, quantity, 
                      stop_loss_price, tp1_price, tp2_price, tp3_price, tp4_price, 
                      wait_timeout=300, auto_monitor=False):
        """
        Execute complete trade with entry, stop loss, and 4 take profits
        
        Args:
            symbol (str): Trading pair (e.g., 'BTCUSDT')
            direction (str): 'LONG' or 'SHORT'
            leverage (int): Leverage (1-125)
            entry_price (float): Limit order entry price
            quantity (float): Total position size
            stop_loss_price (float): Stop loss price
            tp1_price, tp2_price, tp3_price, tp4_price (float): Take profit prices
            wait_timeout (int): Seconds to wait for entry order to fill (default 300s = 5min)
            auto_monitor (bool): Automatically start monitoring in background (default False)
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
        step_size = None
        for filter in symbol_info['filters']:
            if filter['filterType'] == 'LOT_SIZE':
                step_size = float(filter['stepSize'])
                quantity = self.round_quantity(quantity, step_size)
                break
        
        # Find price precision
        price_precision = None
        for filter in symbol_info['filters']:
            if filter['filterType'] == 'PRICE_FILTER':
                tick_size = float(filter['tickSize'])
                # Round all prices to proper precision
                entry_price = self.round_price(entry_price, tick_size)
                stop_loss_price = self.round_price(stop_loss_price, tick_size)
                tp1_price = self.round_price(tp1_price, tick_size)
                tp2_price = self.round_price(tp2_price, tick_size)
                tp3_price = self.round_price(tp3_price, tick_size)
                tp4_price = self.round_price(tp4_price, tick_size)
                break
        
        # Step 1: Set leverage
        print(f"\n[1/7] Setting leverage to {leverage}x...")
        if not self.set_leverage(symbol, leverage):
            return False
        
        # Step 2: Place LIMIT entry order
        print(f"\n[2/7] Placing {direction} LIMIT entry order at {entry_price}...")
        entry_side = 'BUY' if direction == 'LONG' else 'SELL'
        entry_order = self.place_limit_order(symbol, entry_side, quantity, entry_price)
        
        if not entry_order:
            print("❌ Failed to place entry order")
            return False
        
        order_id = entry_order.get('orderId')
        print(f"   Order ID: {order_id}")
        
        # Step 3: Wait for order to fill
        print(f"\n[3/7] Waiting for order to fill (timeout: {wait_timeout}s)...")
        order_filled = self.wait_for_order_fill(symbol, order_id, wait_timeout)
        
        if not order_filled:
            print("\n❌ Entry order was not filled within timeout period")
            print("   Trade cancelled. No positions opened.")
            return False
        
        # Step 4: Verify position exists
        print(f"\n[4/7] Verifying position created...")
        time.sleep(2)  # Small delay to ensure position is registered
        position = self.get_position_info(symbol)
        
        if not position or float(position['positionAmt']) == 0:
            print("⚠️  Warning: Position not found after order fill!")
            print("   This might be a system delay. Check Binance manually.")
            return False
        
        print(f"✓ Position confirmed: {position['positionAmt']} {symbol}")
        
        # Calculate TP quantities (25% each)
        tp_quantity = self.round_quantity(quantity * 0.25, step_size)
        
        # Determine close side (opposite of entry)
        close_side = 'SELL' if direction == 'LONG' else 'BUY'
        
        # Step 5: Place Stop Loss
        print(f"\n[5/7] Placing Stop Loss at {stop_loss_price}...")
        sl_result = self.place_stop_loss(symbol, close_side, stop_loss_price, quantity)
        if not sl_result:
            print("⚠️ Warning: Stop loss placement failed!")
            print("   IMPORTANT: You should manually set a stop loss on Binance!")
            return False
        
        sl_order_id = sl_result.get('orderId')
        
        # Step 6-9: Place 4 Take Profits
        tp_prices = [tp1_price, tp2_price, tp3_price, tp4_price]
        tp_order_ids = []
        
        for i, tp_price in enumerate(tp_prices, 1):
            print(f"\n[{5+i}/9] Placing Take Profit {i} at {tp_price}...")
            tp_result = self.place_take_profit(symbol, close_side, tp_price, tp_quantity)
            if not tp_result:
                print(f"⚠️ Warning: Take Profit {i} placement failed!")
            else:
                tp_order_ids.append(tp_result.get('orderId'))
        
        if len(tp_order_ids) == 0:
            print("\n❌ No take profit orders were placed successfully!")
            print("   Canceling stop loss...")
            self.cancel_order(symbol, sl_order_id)
            return False
        
        print(f"\n{'='*60}")
        print(f"✓ TRADE EXECUTION COMPLETE")
        print(f"{'='*60}")
        print(f"Position: {direction} {quantity} {symbol} @ {leverage}x leverage")
        print(f"Entry Price: {entry_price}")
        print(f"Stop Loss: {stop_loss_price} (Order ID: {sl_order_id})")
        print(f"Take Profits: {tp1_price}, {tp2_price}, {tp3_price}, {tp4_price}")
        print(f"Each TP closes: {tp_quantity} ({symbol})")
        print(f"TP Order IDs: {tp_order_ids}")
        
        # Ask if user wants to monitor orders (skip prompt if auto_monitor is True)
        if auto_monitor:
            monitor = 'yes'
        else:
            monitor = input("\nStart automatic order monitoring? (yes/no): ").strip().lower()
        
        if monitor == 'yes':
            # Start monitoring in a background thread so user can continue trading
            monitor_thread = threading.Thread(
                target=self.monitor_and_manage_orders,
                args=(symbol, sl_order_id, tp_order_ids),
                daemon=True,
                name=f"Monitor-{symbol}-{sl_order_id}"
            )
            monitor_thread.start()
            
            # Store thread info for tracking
            monitor_info = {
                'thread': monitor_thread,
                'symbol': symbol,
                'sl_order_id': sl_order_id,
                'tp_order_ids': tp_order_ids,
                'started_at': time.time(),
                'status': {
                    'filled_tps': 0,
                    'total_tps': 4,
                    'sl_status': 'Active',
                    'last_update': time.time()
                }
            }
            self.active_monitors.append(monitor_info)
            
            print(f"\n✓ Monitoring started in background thread")
            print(f"  You can now place new orders while monitoring continues...")
            print(f"  Active monitors: {len(self.active_monitors)}")
        else:
            print("\n⚠️  IMPORTANT: Stop Loss will NOT auto-cancel when TPs fill!")
            print("   You'll need to manually cancel it or run monitoring later.")
        
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
        
        entry_price = float(input("Enter LIMIT entry price: ").strip())
        quantity = float(input("Enter quantity to trade: ").strip())
        
        wait_timeout = int(input("Enter wait timeout in seconds (e.g., 300 for 5min): ").strip())
        
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
        print(f"Entry Price (LIMIT): {entry_price}")
        print(f"Quantity: {quantity}")
        print(f"Wait Timeout: {wait_timeout} seconds")
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
                tp4_price=tp4_price,
                wait_timeout=wait_timeout
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