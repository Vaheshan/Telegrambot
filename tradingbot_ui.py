"""
Simple GUI for Binance Futures Trading Bot (tradingbotTest.py)

This creates a single-form window where you can:
- Choose testnet/live
- Enter API key & secret
- Fill all trade parameters at once
- Execute the trade with one button
"""

import threading
import tkinter as tk
from tkinter import ttk, messagebox

from tradingbotTest import BinanceFuturesTrader


class TradingBotUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Binance Futures Trading Bot")

        # Use a simple, compact layout
        self.root.geometry("700x900")
        self.root.resizable(False, False)
        
        # Store trader instance for monitor access
        self.trader = None

        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill="both", expand=True)

        row = 0

        # Mode (testnet/live)
        ttk.Label(main_frame, text="Mode (testnet/live):").grid(row=row, column=0, sticky="w", pady=2)
        self.mode_var = tk.StringVar(value="testnet")
        mode_combo = ttk.Combobox(main_frame, textvariable=self.mode_var, values=["testnet", "live"], state="readonly")
        mode_combo.grid(row=row, column=1, sticky="ew", pady=2)
        row += 1

        # API key
        ttk.Label(main_frame, text="API Key:").grid(row=row, column=0, sticky="w", pady=2)
        self.api_key_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.api_key_var).grid(row=row, column=1, sticky="ew", pady=2)
        row += 1

        # API secret
        ttk.Label(main_frame, text="API Secret:").grid(row=row, column=0, sticky="w", pady=2)
        self.api_secret_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.api_secret_var, show="*").grid(row=row, column=1, sticky="ew", pady=2)
        row += 1

        # Separator
        ttk.Separator(main_frame, orient="horizontal").grid(row=row, column=0, columnspan=2, sticky="ew", pady=5)
        row += 1

        # Symbol
        ttk.Label(main_frame, text="Symbol (e.g., BTCUSDT):").grid(row=row, column=0, sticky="w", pady=2)
        self.symbol_var = tk.StringVar(value="BTCUSDT")
        ttk.Entry(main_frame, textvariable=self.symbol_var).grid(row=row, column=1, sticky="ew", pady=2)
        row += 1

        # Direction
        ttk.Label(main_frame, text="Direction:").grid(row=row, column=0, sticky="w", pady=2)
        self.direction_var = tk.StringVar(value="LONG")
        direction_combo = ttk.Combobox(main_frame, textvariable=self.direction_var, values=["LONG", "SHORT"], state="readonly")
        direction_combo.grid(row=row, column=1, sticky="ew", pady=2)
        row += 1

        # Leverage
        ttk.Label(main_frame, text="Leverage (1-125):").grid(row=row, column=0, sticky="w", pady=2)
        self.leverage_var = tk.StringVar(value="20")
        ttk.Entry(main_frame, textvariable=self.leverage_var).grid(row=row, column=1, sticky="ew", pady=2)
        row += 1

        # Entry price
        ttk.Label(main_frame, text="LIMIT order entry price:").grid(row=row, column=0, sticky="w", pady=2)
        self.entry_price_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.entry_price_var).grid(row=row, column=1, sticky="ew", pady=2)
        row += 1

        # Quantity
        ttk.Label(main_frame, text="Quantity:").grid(row=row, column=0, sticky="w", pady=2)
        self.quantity_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.quantity_var).grid(row=row, column=1, sticky="ew", pady=2)
        row += 1

        # Wait timeout
        ttk.Label(main_frame, text="Wait timeout (seconds):").grid(row=row, column=0, sticky="w", pady=2)
        self.wait_timeout_var = tk.StringVar(value="300")
        ttk.Entry(main_frame, textvariable=self.wait_timeout_var).grid(row=row, column=1, sticky="ew", pady=2)
        ttk.Label(main_frame, text="(Time to wait for limit order to fill before placing SL/TP)", 
                  font=("TkDefaultFont", 7), foreground="gray").grid(row=row+1, column=1, sticky="w", pady=0)
        row += 2

        # Stop loss
        ttk.Label(main_frame, text="Stop Loss price:").grid(row=row, column=0, sticky="w", pady=2)
        self.sl_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.sl_var).grid(row=row, column=1, sticky="ew", pady=2)
        row += 1

        # Take profits
        ttk.Label(main_frame, text="TP1 price:").grid(row=row, column=0, sticky="w", pady=2)
        self.tp1_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.tp1_var).grid(row=row, column=1, sticky="ew", pady=2)
        row += 1

        ttk.Label(main_frame, text="TP2 price:").grid(row=row, column=0, sticky="w", pady=2)
        self.tp2_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.tp2_var).grid(row=row, column=1, sticky="ew", pady=2)
        row += 1

        ttk.Label(main_frame, text="TP3 price:").grid(row=row, column=0, sticky="w", pady=2)
        self.tp3_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.tp3_var).grid(row=row, column=1, sticky="ew", pady=2)
        row += 1

        ttk.Label(main_frame, text="TP4 price:").grid(row=row, column=0, sticky="w", pady=2)
        self.tp4_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.tp4_var).grid(row=row, column=1, sticky="ew", pady=2)
        row += 1

        # Auto-monitor checkbox
        self.auto_monitor_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            main_frame, 
            text="Auto-start order monitoring (runs in background)",
            variable=self.auto_monitor_var
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=5)
        row += 1

        # Live trading confirmation note (simple label, no extra prompt)
        self.live_warning_label = ttk.Label(
            main_frame,
            text="Warning: LIVE mode uses real money. Use TESTNET for practice.",
            foreground="red",
            wraplength=400
        )
        self.live_warning_label.grid(row=row, column=0, columnspan=2, sticky="w", pady=5)
        row += 1

        # Execute button
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=row, column=0, columnspan=2, pady=10)

        self.execute_button = ttk.Button(button_frame, text="Execute Trade", command=self.on_execute_clicked)
        self.execute_button.pack()
        row += 1

        # Separator before monitors
        ttk.Separator(main_frame, orient="horizontal").grid(row=row, column=0, columnspan=2, sticky="ew", pady=5)
        row += 1

        # Active Monitors section
        monitor_frame = ttk.LabelFrame(main_frame, text="Active Order Monitors", padding=5)
        monitor_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=5)
        
        # Refresh button
        refresh_frame = ttk.Frame(monitor_frame)
        refresh_frame.pack(fill="x", pady=2)
        ttk.Button(refresh_frame, text="🔄 Refresh Status", command=self.refresh_monitor_status).pack(side="left", padx=5)
        self.monitor_count_label = ttk.Label(refresh_frame, text="Active: 0", font=("TkDefaultFont", 9, "bold"))
        self.monitor_count_label.pack(side="left", padx=10)
        
        # Monitor status display (scrollable)
        monitor_scroll_frame = ttk.Frame(monitor_frame)
        monitor_scroll_frame.pack(fill="both", expand=True, pady=5)
        
        self.monitor_tree = ttk.Treeview(monitor_scroll_frame, columns=("Symbol", "TPs", "SL", "Runtime"), show="tree headings", height=4)
        self.monitor_tree.heading("#0", text="SL Order ID")
        self.monitor_tree.heading("Symbol", text="Symbol")
        self.monitor_tree.heading("TPs", text="TPs Filled")
        self.monitor_tree.heading("SL", text="SL Status")
        self.monitor_tree.heading("Runtime", text="Runtime")
        
        self.monitor_tree.column("#0", width=100)
        self.monitor_tree.column("Symbol", width=80)
        self.monitor_tree.column("TPs", width=80)
        self.monitor_tree.column("SL", width=100)
        self.monitor_tree.column("Runtime", width=80)
        
        monitor_scrollbar = ttk.Scrollbar(monitor_scroll_frame, orient="vertical", command=self.monitor_tree.yview)
        self.monitor_tree.configure(yscrollcommand=monitor_scrollbar.set)
        
        self.monitor_tree.pack(side="left", fill="both", expand=True)
        monitor_scrollbar.pack(side="right", fill="y")
        
        row += 1

        # Output/log area
        ttk.Label(main_frame, text="Log:").grid(row=row, column=0, sticky="nw")
        self.log_text = tk.Text(main_frame, height=8, width=50, state="disabled")
        self.log_text.grid(row=row, column=1, sticky="nsew", pady=2)
        row += 1
        
        # Auto-refresh monitors every 5 seconds
        self.auto_refresh_monitors()

        # Grid configuration
        main_frame.columnconfigure(1, weight=1)

        # Update warning based on mode
        self.mode_var.trace_add("write", self._update_mode_warning)
        self._update_mode_warning()

    def _update_mode_warning(self, *args):
        mode = self.mode_var.get()
        if mode == "live":
            self.live_warning_label.configure(
                text="WARNING: LIVE mode uses REAL MONEY from your Binance account."
            )
        else:
            self.live_warning_label.configure(
                text="TESTNET mode: practice only, no real money at risk."
            )

    def append_log(self, text: str):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", text + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def on_execute_clicked(self):
        # Run validation and trading in a background thread so UI doesn't freeze
        self.execute_button.configure(state="disabled")
        threading.Thread(target=self._execute_trade_thread, daemon=True).start()

    def _execute_trade_thread(self):
        trader = None
        try:
            # Collect and validate inputs
            mode = self.mode_var.get().strip().lower()
            testnet = (mode == "testnet")

            api_key = self.api_key_var.get().strip()
            api_secret = self.api_secret_var.get().strip()

            if not api_key or not api_secret:
                raise ValueError("API Key and Secret are required.")

            symbol = self.symbol_var.get().strip().upper()
            direction = self.direction_var.get().strip().upper()
            if direction not in ("LONG", "SHORT"):
                raise ValueError("Direction must be LONG or SHORT.")

            leverage = int(self.leverage_var.get().strip())
            entry_price = float(self.entry_price_var.get().strip())
            quantity = float(self.quantity_var.get().strip())
            wait_timeout = int(self.wait_timeout_var.get().strip())
            stop_loss_price = float(self.sl_var.get().strip())
            tp1_price = float(self.tp1_var.get().strip())
            tp2_price = float(self.tp2_var.get().strip())
            tp3_price = float(self.tp3_var.get().strip())
            tp4_price = float(self.tp4_var.get().strip())

            # Simple summary to log
            self.append_log("=" * 40)
            self.append_log(f"Mode: {'TESTNET' if testnet else 'LIVE'}")
            self.append_log(f"Symbol: {symbol}")
            self.append_log(f"Direction: {direction}")
            self.append_log(f"Leverage: {leverage}x")
            self.append_log(f"Quantity: {quantity}")
            self.append_log(f"Entry price (LIMIT ORDER): {entry_price}")
            self.append_log(f"Wait timeout: {wait_timeout} seconds")
            self.append_log(f"⚠️ SL/TP orders will be placed AFTER limit order fills")
            self.append_log(f"Stop Loss: {stop_loss_price}")
            self.append_log(f"TP1: {tp1_price}, TP2: {tp2_price}, TP3: {tp3_price}, TP4: {tp4_price}")
            self.append_log("Executing trade...")

            # Confirm live trading with dialog
            if not testnet:
                confirm = messagebox.askyesno(
                    "Live Trading Confirmation",
                    "You selected LIVE mode.\n\n"
                    "This will use REAL MONEY from your Binance account.\n\n"
                    "Do you want to continue?"
                )
                if not confirm:
                    self.append_log("Trade cancelled by user (live mode confirmation).")
                    return

            trader = BinanceFuturesTrader(api_key, api_secret, testnet=testnet)
            # Store trader instance for monitor access (thread-safe update)
            self.trader = trader
            auto_monitor = self.auto_monitor_var.get()
            success = trader.execute_trade(
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
                wait_timeout=wait_timeout,
                auto_monitor=auto_monitor
            )

            if success:
                self.append_log("Trade executed successfully ✅")
                if auto_monitor:
                    self.append_log("Order monitoring started in background thread")
                    self.refresh_monitor_status()
                messagebox.showinfo("Success", "Trade executed successfully.")
            else:
                self.append_log("Trade execution failed ❌")
                messagebox.showerror("Error", "Trade execution failed. Check console/logs.")

        except ValueError as ve:
            messagebox.showerror("Input Error", str(ve))
            self.append_log(f"Input error: {ve}")
        except Exception as e:
            messagebox.showerror("Error", str(e))
            self.append_log(f"Unexpected error: {e}")
        finally:
            # Re-enable button
            self.execute_button.configure(state="normal")
    
    def refresh_monitor_status(self):
        """Refresh the monitor status display"""
        # Clear existing items
        for item in self.monitor_tree.get_children():
            self.monitor_tree.delete(item)
        
        if not self.trader:
            self.monitor_count_label.config(text="Active: 0 (No trader instance)")
            return
        
        # Get monitor status
        try:
            monitors = self.trader.get_monitor_status()
            self.monitor_count_label.config(text=f"Active: {len(monitors)}")
            
            if len(monitors) == 0:
                # Show message when no monitors
                self.monitor_tree.insert("", "end", text="No active monitors", values=("", "", "", ""))
            else:
                for monitor in monitors:
                    sl_id = str(monitor['sl_order_id'])
                    symbol = monitor['symbol']
                    tps_filled = f"{monitor['filled_tps']}/{monitor['total_tps']}"
                    sl_status = monitor['sl_status']
                    runtime_sec = monitor['runtime_seconds']
                    runtime_str = f"{runtime_sec//60}m {runtime_sec%60}s"
                    
                    # Color coding based on status
                    tags = []
                    if monitor['filled_tps'] == 4:
                        tags.append("success")
                    elif monitor['sl_status'] == 'Filled':
                        tags.append("stopped")
                    
                    item = self.monitor_tree.insert("", "end", text=sl_id, values=(symbol, tps_filled, sl_status, runtime_str), tags=tags)
            
            # Configure tag colors
            self.monitor_tree.tag_configure("success", foreground="green")
            self.monitor_tree.tag_configure("stopped", foreground="red")
            
        except Exception as e:
            self.append_log(f"Error refreshing monitor status: {e}")
            self.monitor_count_label.config(text="Error loading monitors")
    
    def auto_refresh_monitors(self):
        """Auto-refresh monitor status every 5 seconds"""
        self.refresh_monitor_status()
        # Schedule next refresh
        self.root.after(5000, self.auto_refresh_monitors)


def main():
    root = tk.Tk()
    app = TradingBotUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()


