"""Trade execution module for Binance futures."""

import hmac
import hashlib
import time
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

import requests


@dataclass
class Order:
    """Order data."""

    order_id: int
    symbol: str
    side: str  # "BUY" or "SELL"
    order_type: str  # "MARKET", "LIMIT", "STOP", "TAKE_PROFIT"
    quantity: float
    price: Optional[float]
    status: str
    executed_qty: float
    timestamp: datetime


@dataclass
class PositionInfo:
    """Position information."""

    symbol: str
    position_amt: float  # Negative for short
    entry_price: float
    unrealized_pnl: float
    leverage: int


class BinanceExecutor:
    """Executor for Binance futures trades."""

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        testnet: bool = False,
        dry_run: bool = True,
    ):
        """Initialize Binance executor.

        Args:
            api_key: Binance API key
            api_secret: Binance API secret
            testnet: Use testnet
            dry_run: If True, don't execute real trades
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.dry_run = dry_run

        if testnet:
            self.base_url = "https://testnet.binance.vision"
        else:
            self.base_url = "https://fapi.binance.com"

        self._dry_run_orders: List[Order] = []

    def _generate_signature(self, params: Dict[str, any]) -> str:
        """Generate HMAC signature for API request.

        Args:
            params: Request parameters

        Returns:
            HMAC signature
        """
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        return hmac.new(
            self.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _request(
        self, method: str, endpoint: str, params: Optional[Dict] = None, signed: bool = False
    ) -> Optional[Dict]:
        """Make authenticated API request.

        Args:
            method: HTTP method (GET, POST, DELETE)
            endpoint: API endpoint
            params: Request parameters
            signed: Whether request requires signature

        Returns:
            Response JSON or None
        """
        url = f"{self.base_url}{endpoint}"

        headers = {"X-MBX-APIKEY": self.api_key}

        if params is None:
            params = {}

        if signed:
            params["timestamp"] = int(time.time() * 1000)
            params["signature"] = self._generate_signature(params)

        try:
            if method == "GET":
                response = requests.get(url, headers=headers, params=params, timeout=10)
            elif method == "POST":
                response = requests.post(url, headers=headers, params=params, timeout=10)
            elif method == "DELETE":
                response = requests.delete(url, headers=headers, params=params, timeout=10)
            else:
                return None

            response.raise_for_status()
            return response.json()

        except requests.RequestException as e:
            print(f"API request error: {e}")
            if hasattr(e.response, "text"):
                print(f"Response: {e.response.text}")
            return None

    def set_leverage(self, symbol: str, leverage: int) -> bool:
        """Set leverage for a symbol.

        Args:
            symbol: Trading pair symbol
            leverage: Leverage multiplier (1-125)

        Returns:
            True if successful
        """
        if self.dry_run:
            print(f"[DRY RUN] Set leverage {leverage}x for {symbol}")
            return True

        params = {
            "symbol": symbol,
            "leverage": leverage,
        }

        response = self._request("POST", "/fapi/v1/leverage", params, signed=True)

        return response is not None

    def set_margin_type(
        self, symbol: str, margin_type: str = "ISOLATED"
    ) -> bool:
        """Set margin type for a symbol.

        Args:
            symbol: Trading pair symbol
            margin_type: "ISOLATED" or "CROSSED"

        Returns:
            True if successful
        """
        if self.dry_run:
            print(f"[DRY RUN] Set margin type {margin_type} for {symbol}")
            return True

        params = {
            "symbol": symbol,
            "marginType": margin_type,
        }

        response = self._request("POST", "/fapi/v1/marginType", params, signed=True)

        return response is not None

    def place_market_order(
        self, symbol: str, side: str, quantity: float
    ) -> Optional[Order]:
        """Place a market order.

        Args:
            symbol: Trading pair symbol
            side: "BUY" or "SELL"
            quantity: Order quantity

        Returns:
            Order object or None
        """
        params = {
            "symbol": symbol,
            "side": side,
            "type": "MARKET",
            "quantity": quantity,
        }

        if self.dry_run:
            print(f"[DRY RUN] Market {side} {quantity} {symbol}")
            order = Order(
                order_id=len(self._dry_run_orders) + 1,
                symbol=symbol,
                side=side,
                order_type="MARKET",
                quantity=quantity,
                price=None,
                status="FILLED",
                executed_qty=quantity,
                timestamp=datetime.now(),
            )
            self._dry_run_orders.append(order)
            return order

        response = self._request("POST", "/fapi/v1/order", params, signed=True)

        if response:
            return self._parse_order(response)

        return None

    def place_limit_order(
        self, symbol: str, side: str, quantity: float, price: float, time_in_force: str = "GTC"
    ) -> Optional[Order]:
        """Place a limit order.

        Args:
            symbol: Trading pair symbol
            side: "BUY" or "SELL"
            quantity: Order quantity
            price: Limit price
            time_in_force: "GTC", "IOC", "FOK", "GTX"

        Returns:
            Order object or None
        """
        params = {
            "symbol": symbol,
            "side": side,
            "type": "LIMIT",
            "quantity": quantity,
            "price": price,
            "timeInForce": time_in_force,
        }

        if self.dry_run:
            print(f"[DRY RUN] Limit {side} {quantity} {symbol} @ {price}")
            order = Order(
                order_id=len(self._dry_run_orders) + 1,
                symbol=symbol,
                side=side,
                order_type="LIMIT",
                quantity=quantity,
                price=price,
                status="NEW",
                executed_qty=0,
                timestamp=datetime.now(),
            )
            self._dry_run_orders.append(order)
            return order

        response = self._request("POST", "/fapi/v1/order", params, signed=True)

        if response:
            return self._parse_order(response)

        return None

    def place_stop_market_order(
        self, symbol: str, side: str, quantity: float, stop_price: float
    ) -> Optional[Order]:
        """Place a stop market order.

        Args:
            symbol: Trading pair symbol
            side: "BUY" or "SELL"
            quantity: Order quantity
            stop_price: Stop trigger price

        Returns:
            Order object or None
        """
        params = {
            "symbol": symbol,
            "side": side,
            "type": "STOP_MARKET",
            "quantity": quantity,
            "stopPrice": stop_price,
        }

        if self.dry_run:
            print(f"[DRY RUN] Stop Market {side} {quantity} {symbol} @ {stop_price}")
            order = Order(
                order_id=len(self._dry_run_orders) + 1,
                symbol=symbol,
                side=side,
                order_type="STOP_MARKET",
                quantity=quantity,
                price=stop_price,
                status="NEW",
                executed_qty=0,
                timestamp=datetime.now(),
            )
            self._dry_run_orders.append(order)
            return order

        response = self._request("POST", "/fapi/v1/order", params, signed=True)

        if response:
            return self._parse_order(response)

        return None

    def place_take_profit_order(
        self, symbol: str, side: str, quantity: float, price: float
    ) -> Optional[Order]:
        """Place a take profit order.

        Args:
            symbol: Trading pair symbol
            side: "BUY" or "SELL"
            quantity: Order quantity
            price: Take profit price

        Returns:
            Order object or None
        """
        params = {
            "symbol": symbol,
            "side": side,
            "type": "TAKE_PROFIT_MARKET",
            "quantity": quantity,
            "stopPrice": price,
        }

        if self.dry_run:
            print(f"[DRY RUN] Take Profit {side} {quantity} {symbol} @ {price}")
            order = Order(
                order_id=len(self._dry_run_orders) + 1,
                symbol=symbol,
                side=side,
                order_type="TAKE_PROFIT_MARKET",
                quantity=quantity,
                price=price,
                status="NEW",
                executed_qty=0,
                timestamp=datetime.now(),
            )
            self._dry_run_orders.append(order)
            return order

        response = self._request("POST", "/fapi/v1/order", params, signed=True)

        if response:
            return self._parse_order(response)

        return None

    def cancel_order(self, symbol: str, order_id: int) -> bool:
        """Cancel an order.

        Args:
            symbol: Trading pair symbol
            order_id: Order ID to cancel

        Returns:
            True if successful
        """
        if self.dry_run:
            print(f"[DRY RUN] Cancel order {order_id} for {symbol}")
            return True

        params = {
            "symbol": symbol,
            "orderId": order_id,
        }

        response = self._request("DELETE", "/fapi/v1/order", params, signed=True)

        return response is not None

    def cancel_all_orders(self, symbol: str) -> bool:
        """Cancel all open orders for a symbol.

        Args:
            symbol: Trading pair symbol

        Returns:
            True if successful
        """
        if self.dry_run:
            print(f"[DRY RUN] Cancel all orders for {symbol}")
            return True

        params = {"symbol": symbol}

        response = self._request("DELETE", "/fapi/v1/allOpenOrders", params, signed=True)

        return response is not None

    def get_open_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """Get open orders.

        Args:
            symbol: Trading pair symbol (None for all)

        Returns:
            List of Order objects
        """
        params = {}

        if symbol:
            params["symbol"] = symbol

        response = self._request("GET", "/fapi/v1/openOrders", params, signed=True)

        if response:
            return [self._parse_order(order) for order in response]

        return []

    def get_position(self, symbol: str) -> Optional[PositionInfo]:
        """Get position information for a symbol.

        Args:
            symbol: Trading pair symbol

        Returns:
            PositionInfo or None
        """
        params = {"symbol": symbol}

        response = self._request("GET", "/fapi/v2/positionRisk", params, signed=True)

        if response and len(response) > 0:
            pos = response[0]
            return PositionInfo(
                symbol=pos["symbol"],
                position_amt=float(pos["positionAmt"]),
                entry_price=float(pos["entryPrice"]),
                unrealized_pnl=float(pos["unRealizedProfit"]),
                leverage=int(pos["leverage"]),
            )

        return None

    def get_account_balance(self) -> Optional[Dict[str, float]]:
        """Get account balance.

        Returns:
            Dictionary of asset -> balance
        """
        response = self._request("GET", "/fapi/v2/balance", {}, signed=True)

        if response:
            # Response is a list of balance objects
            return {item["asset"]: float(item["balance"]) for item in response}

        return None

    def _parse_order(self, data: Dict) -> Order:
        """Parse order data from API response.

        Args:
            data: Raw order data

        Returns:
            Order object
        """
        return Order(
            order_id=int(data["orderId"]),
            symbol=data["symbol"],
            side=data["side"],
            order_type=data["type"],
            quantity=float(data["origQty"]),
            price=float(data.get("price", 0)),
            status=data["status"],
            executed_qty=float(data["executedQty"]),
            timestamp=datetime.fromtimestamp(data["time"] / 1000),
        )

    def execute_short(
        self,
        symbol: str,
        quantity: float,
        leverage: int = 3,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> Dict[str, Optional[Order]]:
        """Execute a short trade with optional stop loss and take profit.

        Args:
            symbol: Trading pair symbol
            quantity: Position size
            leverage: Leverage multiplier
            stop_loss: Stop loss price
            take_profit: Take profit price

        Returns:
            Dictionary with order results
        """
        results = {
            "leverage": None,
            "entry": None,
            "stop_loss": None,
            "take_profit": None,
        }

        # Set leverage
        self.set_leverage(symbol, leverage)

        # Set margin type to isolated
        self.set_margin_type(symbol, "ISOLATED")

        # Entry order (market sell for short)
        results["entry"] = self.place_market_order(symbol, "SELL", quantity)

        if not results["entry"]:
            print(f"Failed to place entry order for {symbol}")
            return results

        # Place stop loss
        if stop_loss:
            results["stop_loss"] = self.place_stop_market_order(
                symbol, "BUY", quantity, stop_loss
            )

        # Place take profit
        if take_profit:
            results["take_profit"] = self.place_take_profit_order(
                symbol, "BUY", quantity, take_profit
            )

        return results

    def close_position(self, symbol: str, quantity: Optional[float] = None) -> Optional[Order]:
        """Close a position.

        Args:
            symbol: Trading pair symbol
            quantity: Quantity to close (None = close all)

        Returns:
            Order or None
        """
        position = self.get_position(symbol)

        if not position:
            print(f"No position found for {symbol}")
            return None

        # Determine quantity
        if quantity is None:
            quantity = abs(position.position_amt)

        # Buy to cover short
        order = self.place_market_order(symbol, "BUY", quantity)

        # Cancel any pending orders
        self.cancel_all_orders(symbol)

        return order
