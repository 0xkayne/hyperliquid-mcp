"""
Hyperliquid MCP Server
======================
A Model Context Protocol server providing real-time data access
to the Hyperliquid decentralized exchange (DEX).

Covers: market data, user accounts, order books, candles, funding rates,
perpetuals metadata, spot metadata, vault details, staking, and more.
"""

import json
import sys
from typing import Optional, List, Any, Dict
from enum import Enum

import httpx
from pydantic import BaseModel, Field, ConfigDict, field_validator
from mcp.server.fastmcp import FastMCP

# =============================================================================
# Constants
# =============================================================================

MAINNET_API_URL = "https://api.hyperliquid.xyz"
TESTNET_API_URL = "https://api.hyperliquid-testnet.xyz"
DEFAULT_TIMEOUT = 30.0

# =============================================================================
# Server Initialization
# =============================================================================

mcp = FastMCP("hyperliquid_mcp")

# =============================================================================
# Shared Utilities
# =============================================================================


class Network(str, Enum):
    """Network selection."""
    MAINNET = "mainnet"
    TESTNET = "testnet"


class ResponseFormat(str, Enum):
    """Output format for tool responses."""
    MARKDOWN = "markdown"
    JSON = "json"


def _get_base_url(network: Network) -> str:
    """Get the API base URL for the given network."""
    return MAINNET_API_URL if network == Network.MAINNET else TESTNET_API_URL


async def _post_info(payload: dict, network: Network = Network.MAINNET) -> Any:
    """Make a POST request to the Hyperliquid /info endpoint."""
    url = f"{_get_base_url(network)}/info"
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        response = await client.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        return response.json()


def _handle_api_error(e: Exception) -> str:
    """Consistent error formatting across all tools."""
    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        if status == 404:
            return "Error: Resource not found. Please check that the parameters are correct."
        elif status == 429:
            return "Error: Rate limit exceeded. Please wait before making more requests."
        return f"Error: API request failed with status {status}. Response: {e.response.text[:500]}"
    elif isinstance(e, httpx.TimeoutException):
        return "Error: Request timed out. The Hyperliquid API may be slow — please try again."
    elif isinstance(e, httpx.ConnectError):
        return "Error: Could not connect to the Hyperliquid API. Please check network connectivity."
    return f"Error: {type(e).__name__}: {str(e)}"


def _format_json(data: Any) -> str:
    """Format data as indented JSON string."""
    return json.dumps(data, indent=2, ensure_ascii=False)


def _format_price(price_str: str) -> str:
    """Format a price string for display."""
    try:
        val = float(price_str)
        if val >= 1000:
            return f"${val:,.2f}"
        elif val >= 1:
            return f"${val:.4f}"
        else:
            return f"${val:.8f}"
    except (ValueError, TypeError):
        return str(price_str)


def _format_mids_markdown(data: dict) -> str:
    """Format allMids response as Markdown."""
    if not data:
        return "No mid prices available."
    lines = ["# All Mid Prices\n"]
    sorted_items = sorted(data.items(), key=lambda x: x[0])
    for coin, price in sorted_items:
        lines.append(f"- **{coin}**: {_format_price(price)}")
    lines.append(f"\n*Total: {len(data)} assets*")
    return "\n".join(lines)


def _format_orders_markdown(orders: list) -> str:
    """Format open orders as Markdown."""
    if not orders:
        return "No open orders found."
    lines = ["# Open Orders\n"]
    for o in orders:
        side = "🟢 Buy" if o.get("side") == "B" else "🔴 Sell"
        lines.append(
            f"- **{o.get('coin')}** | {side} | "
            f"Price: {_format_price(o.get('limitPx', 'N/A'))} | "
            f"Size: {o.get('sz', 'N/A')} | OID: {o.get('oid', 'N/A')}"
        )
    lines.append(f"\n*Total: {len(orders)} orders*")
    return "\n".join(lines)


def _format_l2_book_markdown(data: dict) -> str:
    """Format L2 book snapshot as Markdown."""
    coin = data.get("coin", "Unknown")
    levels = data.get("levels", [[], []])
    bids = levels[0] if len(levels) > 0 else []
    asks = levels[1] if len(levels) > 1 else []

    lines = [f"# Order Book: {coin}\n"]
    lines.append("## Asks (Sell)")
    for lvl in reversed(asks[:10]):
        lines.append(f"  {_format_price(lvl.get('px', '0'))}  |  {lvl.get('sz', '0')}  ({lvl.get('n', 0)} orders)")
    lines.append("\n---  **Spread**  ---\n")
    lines.append("## Bids (Buy)")
    for lvl in bids[:10]:
        lines.append(f"  {_format_price(lvl.get('px', '0'))}  |  {lvl.get('sz', '0')}  ({lvl.get('n', 0)} orders)")
    return "\n".join(lines)


def _format_candles_markdown(candles: list) -> str:
    """Format candle data as Markdown."""
    if not candles:
        return "No candle data available."
    lines = [f"# Candle Data ({candles[0].get('s', 'Unknown')}, {candles[0].get('i', '')})\n"]
    lines.append("| Time | Open | High | Low | Close | Volume | Trades |")
    lines.append("|------|------|------|-----|-------|--------|--------|")
    for c in candles[-20:]:  # last 20 candles
        from datetime import datetime, timezone
        t = datetime.fromtimestamp(c["t"] / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
        lines.append(f"| {t} | {c['o']} | {c['h']} | {c['l']} | {c['c']} | {c['v']} | {c['n']} |")
    if len(candles) > 20:
        lines.append(f"\n*Showing last 20 of {len(candles)} candles*")
    return "\n".join(lines)


def _format_fills_markdown(fills: list) -> str:
    """Format user fills as Markdown."""
    if not fills:
        return "No fills found."
    lines = ["# Recent Fills\n"]
    for f in fills[:20]:
        side = "🟢 Buy" if f.get("side") == "B" else "🔴 Sell"
        from datetime import datetime, timezone
        t = datetime.fromtimestamp(f["time"] / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        pnl = f.get("closedPnl", "0.0")
        lines.append(
            f"- **{f.get('coin')}** | {side} | {f.get('dir', '')} | "
            f"Px: {_format_price(f.get('px', '0'))} | Sz: {f.get('sz', '0')} | "
            f"PnL: {pnl} | {t}"
        )
    if len(fills) > 20:
        lines.append(f"\n*Showing first 20 of {len(fills)} fills*")
    return "\n".join(lines)


def _format_account_markdown(data: dict) -> str:
    """Format clearinghouse state as Markdown."""
    ms = data.get("marginSummary", {})
    cms = data.get("crossMarginSummary", {})
    positions = data.get("assetPositions", [])

    lines = ["# Account Summary\n"]
    lines.append(f"**Account Value**: {_format_price(ms.get('accountValue', '0'))}")
    lines.append(f"**Total Margin Used**: {_format_price(ms.get('totalMarginUsed', '0'))}")
    lines.append(f"**Total Position Notional**: {_format_price(ms.get('totalNtlPos', '0'))}")
    lines.append(f"**Withdrawable**: {_format_price(data.get('withdrawable', '0'))}")

    if positions:
        lines.append(f"\n## Open Positions ({len(positions)})\n")
        for ap in positions:
            pos = ap.get("position", {})
            coin = pos.get("coin", "?")
            entry = pos.get("entryPx", "0")
            size = pos.get("szi", "0")
            pnl = pos.get("unrealizedPnl", "0")
            lev = pos.get("leverage", {})
            liq = pos.get("liquidationPx", "N/A")
            lines.append(
                f"- **{coin}** | Size: {size} | Entry: {_format_price(entry)} | "
                f"uPnL: {pnl} | Liq: {_format_price(liq)} | "
                f"Leverage: {lev.get('value', 'N/A')}x ({lev.get('type', '')})"
            )
    else:
        lines.append("\n*No open positions*")

    return "\n".join(lines)


def _format_response(data: Any, fmt: ResponseFormat, markdown_formatter=None) -> str:
    """Generic response formatter."""
    if fmt == ResponseFormat.JSON:
        return _format_json(data)
    if markdown_formatter:
        return markdown_formatter(data)
    return _format_json(data)


# =============================================================================
# Pydantic Input Models
# =============================================================================


class NetworkInput(BaseModel):
    """Base model with network selection."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    network: Network = Field(default=Network.MAINNET, description="Network: 'mainnet' or 'testnet'")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN, description="Output format: 'markdown' or 'json'")


class AllMidsInput(NetworkInput):
    """Input for retrieving all mid prices."""
    dex: Optional[str] = Field(default=None, description="Perp dex name. Defaults to the first perp dex (empty string).")


class UserInput(NetworkInput):
    """Input requiring a user address."""
    user: str = Field(..., description="User address in 42-char hex format, e.g. '0x1234...abcd'", min_length=42, max_length=42)

    @field_validator("user")
    @classmethod
    def validate_address(cls, v: str) -> str:
        if not v.startswith("0x"):
            raise ValueError("Address must start with '0x'")
        return v.lower()


class UserWithDexInput(UserInput):
    """Input requiring user address and optional dex."""
    dex: Optional[str] = Field(default=None, description="Perp dex name. Defaults to the first perp dex.")


class OpenOrdersInput(UserWithDexInput):
    """Input for retrieving open orders."""
    pass


class UserFillsInput(UserInput):
    """Input for retrieving user fills."""
    aggregate_by_time: Optional[bool] = Field(default=None, description="When true, partial fills are combined.")


class UserFillsByTimeInput(UserFillsInput):
    """Input for retrieving user fills by time range."""
    start_time: int = Field(..., description="Start time in milliseconds, inclusive")
    end_time: Optional[int] = Field(default=None, description="End time in milliseconds, inclusive. Defaults to current time.")


class L2BookInput(NetworkInput):
    """Input for L2 book snapshot."""
    coin: str = Field(..., description="Coin symbol, e.g. 'BTC', 'ETH', or '@107' for spot")
    n_sig_figs: Optional[int] = Field(default=None, description="Aggregate to N significant figures (2-5 or null)")


class CandleSnapshotInput(NetworkInput):
    """Input for candle snapshot."""
    coin: str = Field(..., description="Coin symbol, e.g. 'BTC', 'ETH'. For HIP-3 prefix with dex name, e.g. 'xyz:XYZ100'")
    interval: str = Field(..., description="Candle interval: '1m','3m','5m','15m','30m','1h','2h','4h','8h','12h','1d','3d','1w','1M'")
    start_time: int = Field(..., description="Start time in epoch milliseconds")
    end_time: int = Field(..., description="End time in epoch milliseconds")

    @field_validator("interval")
    @classmethod
    def validate_interval(cls, v: str) -> str:
        valid = {"1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "8h", "12h", "1d", "3d", "1w", "1M"}
        if v not in valid:
            raise ValueError(f"Invalid interval '{v}'. Must be one of: {', '.join(sorted(valid))}")
        return v


class MetaInput(NetworkInput):
    """Input for retrieving perpetuals metadata."""
    dex: Optional[str] = Field(default=None, description="Perp dex name. Defaults to the first perp dex.")


class FundingHistoryInput(NetworkInput):
    """Input for funding rate history."""
    coin: str = Field(..., description="Coin symbol, e.g. 'ETH'")
    start_time: int = Field(..., description="Start time in epoch milliseconds, inclusive")
    end_time: Optional[int] = Field(default=None, description="End time in epoch milliseconds, inclusive.")


class UserFundingInput(UserInput):
    """Input for user funding history."""
    start_time: int = Field(..., description="Start time in epoch milliseconds, inclusive")
    end_time: Optional[int] = Field(default=None, description="End time in epoch milliseconds, inclusive.")


class OrderStatusInput(UserInput):
    """Input for querying order status."""
    oid: str = Field(..., description="Order ID (u64 number) or client order ID (16-byte hex string)")


class VaultDetailsInput(NetworkInput):
    """Input for vault details."""
    vault_address: str = Field(..., description="Vault address in 42-char hex format", min_length=42, max_length=42)
    user: Optional[str] = Field(default=None, description="Optional user address for follower-specific info")


class TokenInput(NetworkInput):
    """Input requiring a token index."""
    token: int = Field(..., description="Token index number", ge=0)


# =============================================================================
# Tools — Market Data
# =============================================================================


@mcp.tool(
    name="hyperliquid_get_all_mids",
    annotations={
        "title": "Get All Mid Prices",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def hyperliquid_get_all_mids(params: AllMidsInput) -> str:
    """Retrieve current mid prices for all traded assets on Hyperliquid.

    Returns a dictionary mapping coin symbols to their current mid prices.
    If the order book is empty, the last trade price is used as fallback.

    Args:
        params (AllMidsInput): Input parameters.

    Returns:
        str: Mid prices for all coins in the requested format.
    """
    try:
        payload: Dict[str, Any] = {"type": "allMids"}
        if params.dex is not None:
            payload["dex"] = params.dex
        data = await _post_info(payload, params.network)
        return _format_response(data, params.response_format, _format_mids_markdown)
    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="hyperliquid_get_l2_book",
    annotations={
        "title": "Get L2 Order Book Snapshot",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def hyperliquid_get_l2_book(params: L2BookInput) -> str:
    """Retrieve the L2 order book snapshot for a given coin.

    Returns up to 20 price levels per side (bid/ask) with aggregated sizes.

    Args:
        params (L2BookInput): Input parameters including coin and optional aggregation.

    Returns:
        str: Order book data in the requested format.
    """
    try:
        payload: Dict[str, Any] = {"type": "l2Book", "coin": params.coin}
        if params.n_sig_figs is not None:
            payload["nSigFigs"] = params.n_sig_figs
        data = await _post_info(payload, params.network)
        return _format_response(data, params.response_format, _format_l2_book_markdown)
    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="hyperliquid_get_candles",
    annotations={
        "title": "Get Candle Snapshot (OHLCV)",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def hyperliquid_get_candles(params: CandleSnapshotInput) -> str:
    """Retrieve OHLCV candle data for a given coin and time range.

    Supports intervals from 1 minute to 1 month. Only the most recent 5000 candles are available.

    Args:
        params (CandleSnapshotInput): Input parameters.

    Returns:
        str: Candle data in the requested format.
    """
    try:
        payload = {
            "type": "candleSnapshot",
            "req": {
                "coin": params.coin,
                "interval": params.interval,
                "startTime": params.start_time,
                "endTime": params.end_time,
            },
        }
        data = await _post_info(payload, params.network)
        return _format_response(data, params.response_format, _format_candles_markdown)
    except Exception as e:
        return _handle_api_error(e)


# =============================================================================
# Tools — Perpetuals
# =============================================================================


@mcp.tool(
    name="hyperliquid_get_perp_meta",
    annotations={
        "title": "Get Perpetuals Metadata",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def hyperliquid_get_perp_meta(params: MetaInput) -> str:
    """Retrieve perpetuals metadata including the universe of tradable assets and margin tables.

    Each asset includes name, size decimals, max leverage, and margin mode.

    Args:
        params (MetaInput): Input parameters.

    Returns:
        str: Perpetuals metadata in the requested format.
    """
    try:
        payload: Dict[str, Any] = {"type": "meta"}
        if params.dex is not None:
            payload["dex"] = params.dex
        data = await _post_info(payload, params.network)
        return _format_response(data, params.response_format)
    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="hyperliquid_get_perp_meta_and_asset_ctxs",
    annotations={
        "title": "Get Perpetuals Metadata and Asset Contexts",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def hyperliquid_get_perp_meta_and_asset_ctxs(params: MetaInput) -> str:
    """Retrieve perpetuals metadata AND current asset contexts together.

    Asset contexts include mark price, funding rate, open interest, oracle price,
    24h volume, and impact prices for each perpetual asset.

    Args:
        params (MetaInput): Input parameters.

    Returns:
        str: Combined metadata and asset context data.
    """
    try:
        payload: Dict[str, Any] = {"type": "metaAndAssetCtxs"}
        if params.dex is not None:
            payload["dex"] = params.dex
        data = await _post_info(payload, params.network)
        return _format_response(data, params.response_format)
    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="hyperliquid_get_funding_history",
    annotations={
        "title": "Get Historical Funding Rates",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def hyperliquid_get_funding_history(params: FundingHistoryInput) -> str:
    """Retrieve historical funding rates for a specific perpetual coin.

    Returns up to 500 funding rate entries within the given time range.
    Use pagination (last timestamp as next startTime) for larger ranges.

    Args:
        params (FundingHistoryInput): Input parameters.

    Returns:
        str: Historical funding rate data.
    """
    try:
        payload: Dict[str, Any] = {
            "type": "fundingHistory",
            "coin": params.coin,
            "startTime": params.start_time,
        }
        if params.end_time is not None:
            payload["endTime"] = params.end_time
        data = await _post_info(payload, params.network)
        return _format_response(data, params.response_format)
    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="hyperliquid_get_predicted_fundings",
    annotations={
        "title": "Get Predicted Funding Rates",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def hyperliquid_get_predicted_fundings(params: NetworkInput) -> str:
    """Retrieve predicted funding rates for all perpetuals across venues (Binance, Bybit, Hyperliquid).

    Only supported for the first perp dex.

    Args:
        params (NetworkInput): Input parameters.

    Returns:
        str: Predicted funding rates by coin and venue.
    """
    try:
        data = await _post_info({"type": "predictedFundings"}, params.network)
        return _format_response(data, params.response_format)
    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="hyperliquid_get_perp_dexs",
    annotations={
        "title": "Get All Perpetual DEXs",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def hyperliquid_get_perp_dexs(params: NetworkInput) -> str:
    """Retrieve all registered perpetual DEXs on Hyperliquid, including HIP-3 builder-deployed markets.

    Args:
        params (NetworkInput): Input parameters.

    Returns:
        str: List of all perpetual DEX configurations.
    """
    try:
        data = await _post_info({"type": "perpDexs"}, params.network)
        return _format_response(data, params.response_format)
    except Exception as e:
        return _handle_api_error(e)


# =============================================================================
# Tools — Spot
# =============================================================================


@mcp.tool(
    name="hyperliquid_get_spot_meta",
    annotations={
        "title": "Get Spot Metadata",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def hyperliquid_get_spot_meta(params: NetworkInput) -> str:
    """Retrieve spot market metadata including all token details and configurations.

    Returns token specs (name, decimals), genesis balances, and gas auction info.

    Args:
        params (NetworkInput): Input parameters.

    Returns:
        str: Spot metadata in the requested format.
    """
    try:
        data = await _post_info({"type": "spotMeta"}, params.network)
        return _format_response(data, params.response_format)
    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="hyperliquid_get_spot_meta_and_asset_ctxs",
    annotations={
        "title": "Get Spot Metadata and Asset Contexts",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def hyperliquid_get_spot_meta_and_asset_ctxs(params: NetworkInput) -> str:
    """Retrieve spot metadata AND current asset contexts (prices, volumes, etc.) together.

    Args:
        params (NetworkInput): Input parameters.

    Returns:
        str: Combined spot metadata and asset context data.
    """
    try:
        data = await _post_info({"type": "spotMetaAndAssetCtxs"}, params.network)
        return _format_response(data, params.response_format)
    except Exception as e:
        return _handle_api_error(e)


# =============================================================================
# Tools — User Account Data
# =============================================================================


@mcp.tool(
    name="hyperliquid_get_open_orders",
    annotations={
        "title": "Get User Open Orders",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def hyperliquid_get_open_orders(params: OpenOrdersInput) -> str:
    """Retrieve a user's currently open orders on Hyperliquid.

    Args:
        params (OpenOrdersInput): Input parameters.

    Returns:
        str: List of open orders with coin, side, price, size, and OID.
    """
    try:
        payload: Dict[str, Any] = {"type": "openOrders", "user": params.user}
        if params.dex is not None:
            payload["dex"] = params.dex
        data = await _post_info(payload, params.network)
        return _format_response(data, params.response_format, _format_orders_markdown)
    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="hyperliquid_get_frontend_open_orders",
    annotations={
        "title": "Get User Open Orders (Frontend Info)",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def hyperliquid_get_frontend_open_orders(params: OpenOrdersInput) -> str:
    """Retrieve a user's open orders with additional frontend information.

    Includes order type, trigger conditions, reduce-only flag, TP/SL info, etc.

    Args:
        params (OpenOrdersInput): Input parameters.

    Returns:
        str: Detailed open orders with frontend metadata.
    """
    try:
        payload: Dict[str, Any] = {"type": "frontendOpenOrders", "user": params.user}
        if params.dex is not None:
            payload["dex"] = params.dex
        data = await _post_info(payload, params.network)
        return _format_response(data, params.response_format)
    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="hyperliquid_get_user_fills",
    annotations={
        "title": "Get User Trade Fills",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def hyperliquid_get_user_fills(params: UserFillsInput) -> str:
    """Retrieve a user's recent trade fills (up to 2000 most recent).

    Each fill includes coin, price, size, side, PnL, fee, and timestamp.

    Args:
        params (UserFillsInput): Input parameters.

    Returns:
        str: Trade fill history.
    """
    try:
        payload: Dict[str, Any] = {"type": "userFills", "user": params.user}
        if params.aggregate_by_time is not None:
            payload["aggregateByTime"] = params.aggregate_by_time
        data = await _post_info(payload, params.network)
        return _format_response(data, params.response_format, _format_fills_markdown)
    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="hyperliquid_get_user_fills_by_time",
    annotations={
        "title": "Get User Trade Fills by Time Range",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def hyperliquid_get_user_fills_by_time(params: UserFillsByTimeInput) -> str:
    """Retrieve a user's trade fills within a specific time range.

    Returns up to 2000 fills. Only the 10000 most recent fills are available.

    Args:
        params (UserFillsByTimeInput): Input parameters.

    Returns:
        str: Trade fills within the specified time range.
    """
    try:
        payload: Dict[str, Any] = {
            "type": "userFillsByTime",
            "user": params.user,
            "startTime": params.start_time,
        }
        if params.end_time is not None:
            payload["endTime"] = params.end_time
        if params.aggregate_by_time is not None:
            payload["aggregateByTime"] = params.aggregate_by_time
        data = await _post_info(payload, params.network)
        return _format_response(data, params.response_format, _format_fills_markdown)
    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="hyperliquid_get_clearinghouse_state",
    annotations={
        "title": "Get User Perpetuals Account Summary",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def hyperliquid_get_clearinghouse_state(params: UserWithDexInput) -> str:
    """Retrieve a user's perpetuals account summary including positions and margin info.

    Shows account value, margin used, withdrawable amount, and all open positions
    with entry price, leverage, liquidation price, and unrealized PnL.

    Args:
        params (UserWithDexInput): Input parameters.

    Returns:
        str: Account summary and positions.
    """
    try:
        payload: Dict[str, Any] = {"type": "clearinghouseState", "user": params.user}
        if params.dex is not None:
            payload["dex"] = params.dex
        data = await _post_info(payload, params.network)
        return _format_response(data, params.response_format, _format_account_markdown)
    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="hyperliquid_get_spot_clearinghouse_state",
    annotations={
        "title": "Get User Spot Account State",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def hyperliquid_get_spot_clearinghouse_state(params: UserInput) -> str:
    """Retrieve a user's spot account balances.

    Shows all spot token balances including total, held, and entry notional.

    Args:
        params (UserInput): Input parameters.

    Returns:
        str: Spot balances.
    """
    try:
        payload = {"type": "spotClearinghouseState", "user": params.user}
        data = await _post_info(payload, params.network)
        return _format_response(data, params.response_format)
    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="hyperliquid_get_order_status",
    annotations={
        "title": "Get Order Status",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def hyperliquid_get_order_status(params: OrderStatusInput) -> str:
    """Query the status of a specific order by order ID or client order ID.

    Possible statuses: open, filled, canceled, triggered, rejected, marginCanceled, etc.

    Args:
        params (OrderStatusInput): Input parameters.

    Returns:
        str: Order status details.
    """
    try:
        # Determine if oid is numeric or hex string
        oid: Any = params.oid
        try:
            oid = int(params.oid)
        except ValueError:
            pass  # keep as string (cloid)

        payload = {"type": "orderStatus", "user": params.user, "oid": oid}
        data = await _post_info(payload, params.network)
        return _format_response(data, params.response_format)
    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="hyperliquid_get_historical_orders",
    annotations={
        "title": "Get User Historical Orders",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def hyperliquid_get_historical_orders(params: UserInput) -> str:
    """Retrieve a user's historical orders (up to 2000 most recent).

    Includes order details and final status (filled, canceled, rejected, etc.).

    Args:
        params (UserInput): Input parameters.

    Returns:
        str: Historical order data.
    """
    try:
        payload = {"type": "historicalOrders", "user": params.user}
        data = await _post_info(payload, params.network)
        return _format_response(data, params.response_format)
    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="hyperliquid_get_user_funding",
    annotations={
        "title": "Get User Funding History",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def hyperliquid_get_user_funding(params: UserFundingInput) -> str:
    """Retrieve a user's funding payment history within a time range.

    Returns up to 500 entries per request. Use pagination for larger ranges.

    Args:
        params (UserFundingInput): Input parameters.

    Returns:
        str: Funding payment history.
    """
    try:
        payload: Dict[str, Any] = {
            "type": "userFunding",
            "user": params.user,
            "startTime": params.start_time,
        }
        if params.end_time is not None:
            payload["endTime"] = params.end_time
        data = await _post_info(payload, params.network)
        return _format_response(data, params.response_format)
    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="hyperliquid_get_user_rate_limit",
    annotations={
        "title": "Get User Rate Limit Info",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def hyperliquid_get_user_rate_limit(params: UserInput) -> str:
    """Query a user's current API rate limit usage and capacity.

    Shows cumulative volume, requests used, requests cap, and surplus.

    Args:
        params (UserInput): Input parameters.

    Returns:
        str: Rate limit information.
    """
    try:
        payload = {"type": "userRateLimit", "user": params.user}
        data = await _post_info(payload, params.network)
        return _format_response(data, params.response_format)
    except Exception as e:
        return _handle_api_error(e)


# =============================================================================
# Tools — Vaults
# =============================================================================


@mcp.tool(
    name="hyperliquid_get_vault_details",
    annotations={
        "title": "Get Vault Details",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def hyperliquid_get_vault_details(params: VaultDetailsInput) -> str:
    """Retrieve detailed information about a Hyperliquid vault.

    Includes vault name, description, portfolio performance (day/week/month/allTime),
    APR, followers list, leader info, and withdrawal limits.

    Args:
        params (VaultDetailsInput): Input parameters.

    Returns:
        str: Comprehensive vault details.
    """
    try:
        payload: Dict[str, Any] = {"type": "vaultDetails", "vaultAddress": params.vault_address}
        if params.user:
            payload["user"] = params.user
        data = await _post_info(payload, params.network)
        return _format_response(data, params.response_format)
    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="hyperliquid_get_user_vault_equities",
    annotations={
        "title": "Get User Vault Deposits",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def hyperliquid_get_user_vault_equities(params: UserInput) -> str:
    """Retrieve a user's vault deposit positions.

    Shows vault address and current equity for each vault the user has deposited into.

    Args:
        params (UserInput): Input parameters.

    Returns:
        str: User's vault equity positions.
    """
    try:
        payload = {"type": "userVaultEquities", "user": params.user}
        data = await _post_info(payload, params.network)
        return _format_response(data, params.response_format)
    except Exception as e:
        return _handle_api_error(e)


# =============================================================================
# Tools — Account Info
# =============================================================================


@mcp.tool(
    name="hyperliquid_get_user_role",
    annotations={
        "title": "Get User Role",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def hyperliquid_get_user_role(params: UserInput) -> str:
    """Query a user's role on Hyperliquid.

    Possible roles: user, agent, vault, subAccount, missing.

    Args:
        params (UserInput): Input parameters.

    Returns:
        str: User role information.
    """
    try:
        payload = {"type": "userRole", "user": params.user}
        data = await _post_info(payload, params.network)
        return _format_response(data, params.response_format)
    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="hyperliquid_get_portfolio",
    annotations={
        "title": "Get User Portfolio",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def hyperliquid_get_portfolio(params: UserInput) -> str:
    """Query a user's portfolio performance history.

    Returns account value history and PnL history across different time periods
    (day, week, month, allTime, and perp-specific periods).

    Args:
        params (UserInput): Input parameters.

    Returns:
        str: Portfolio performance data.
    """
    try:
        payload = {"type": "portfolio", "user": params.user}
        data = await _post_info(payload, params.network)
        return _format_response(data, params.response_format)
    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="hyperliquid_get_user_fees",
    annotations={
        "title": "Get User Fee Schedule",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def hyperliquid_get_user_fees(params: UserInput) -> str:
    """Query a user's fee information including fee schedule, volume, and discounts.

    Includes daily volume, VIP/MM tiers, cross/add rates, referral and staking discounts.

    Args:
        params (UserInput): Input parameters.

    Returns:
        str: Fee schedule and user-specific rates.
    """
    try:
        payload = {"type": "userFees", "user": params.user}
        data = await _post_info(payload, params.network)
        return _format_response(data, params.response_format)
    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="hyperliquid_get_referral",
    annotations={
        "title": "Get User Referral Info",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def hyperliquid_get_referral(params: UserInput) -> str:
    """Query a user's referral information including referrer, rewards, and referred users.

    Args:
        params (UserInput): Input parameters.

    Returns:
        str: Referral data.
    """
    try:
        payload = {"type": "referral", "user": params.user}
        data = await _post_info(payload, params.network)
        return _format_response(data, params.response_format)
    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="hyperliquid_get_sub_accounts",
    annotations={
        "title": "Get User Sub-Accounts",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def hyperliquid_get_sub_accounts(params: UserInput) -> str:
    """Retrieve a user's sub-accounts including their clearinghouse and spot states.

    Args:
        params (UserInput): Input parameters.

    Returns:
        str: Sub-account details.
    """
    try:
        payload = {"type": "subAccounts", "user": params.user}
        data = await _post_info(payload, params.network)
        return _format_response(data, params.response_format)
    except Exception as e:
        return _handle_api_error(e)


# =============================================================================
# Tools — Staking
# =============================================================================


@mcp.tool(
    name="hyperliquid_get_delegations",
    annotations={
        "title": "Get User Staking Delegations",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def hyperliquid_get_delegations(params: UserInput) -> str:
    """Query a user's staking delegations.

    Shows validator addresses, staked amounts, and lock-up periods.

    Args:
        params (UserInput): Input parameters.

    Returns:
        str: Delegation details.
    """
    try:
        payload = {"type": "delegations", "user": params.user}
        data = await _post_info(payload, params.network)
        return _format_response(data, params.response_format)
    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="hyperliquid_get_delegator_summary",
    annotations={
        "title": "Get User Staking Summary",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def hyperliquid_get_delegator_summary(params: UserInput) -> str:
    """Query a user's staking summary.

    Shows total delegated, undelegated, and pending withdrawal amounts.

    Args:
        params (UserInput): Input parameters.

    Returns:
        str: Staking summary.
    """
    try:
        payload = {"type": "delegatorSummary", "user": params.user}
        data = await _post_info(payload, params.network)
        return _format_response(data, params.response_format)
    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="hyperliquid_get_delegator_rewards",
    annotations={
        "title": "Get User Staking Rewards",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def hyperliquid_get_delegator_rewards(params: UserInput) -> str:
    """Query a user's staking rewards history.

    Shows reward timestamps, sources (delegation/commission), and amounts.

    Args:
        params (UserInput): Input parameters.

    Returns:
        str: Staking rewards history.
    """
    try:
        payload = {"type": "delegatorRewards", "user": params.user}
        data = await _post_info(payload, params.network)
        return _format_response(data, params.response_format)
    except Exception as e:
        return _handle_api_error(e)


# =============================================================================
# Tools — Borrow/Lend
# =============================================================================


@mcp.tool(
    name="hyperliquid_get_borrow_lend_user_state",
    annotations={
        "title": "Get User Borrow/Lend State",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def hyperliquid_get_borrow_lend_user_state(params: UserInput) -> str:
    """Query a user's borrow/lend positions.

    Shows borrow and supply basis/value for each token, plus health status.

    Args:
        params (UserInput): Input parameters.

    Returns:
        str: User's borrow/lend state.
    """
    try:
        payload = {"type": "borrowLendUserState", "user": params.user}
        data = await _post_info(payload, params.network)
        return _format_response(data, params.response_format)
    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="hyperliquid_get_all_borrow_lend_reserve_states",
    annotations={
        "title": "Get All Borrow/Lend Reserve States",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def hyperliquid_get_all_borrow_lend_reserve_states(params: NetworkInput) -> str:
    """Query all borrow/lend reserve states across all tokens.

    Shows borrow/supply rates, utilization, total supplied/borrowed, oracle prices, and LTV.

    Args:
        params (NetworkInput): Input parameters.

    Returns:
        str: All reserve states.
    """
    try:
        data = await _post_info({"type": "allBorrowLendReserveStates"}, params.network)
        return _format_response(data, params.response_format)
    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="hyperliquid_get_borrow_lend_reserve_state",
    annotations={
        "title": "Get Borrow/Lend Reserve State for Token",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def hyperliquid_get_borrow_lend_reserve_state(params: TokenInput) -> str:
    """Query the borrow/lend reserve state for a specific token.

    Shows borrow/supply yearly rates, balance, utilization, oracle price, LTV, and totals.

    Args:
        params (TokenInput): Input parameters.

    Returns:
        str: Reserve state for the given token.
    """
    try:
        payload = {"type": "borrowLendReserveState", "token": params.token}
        data = await _post_info(payload, params.network)
        return _format_response(data, params.response_format)
    except Exception as e:
        return _handle_api_error(e)


# =============================================================================
# Entry Point
# =============================================================================


def main():
    """CLI entry point for the Hyperliquid MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
