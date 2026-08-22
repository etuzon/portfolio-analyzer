from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from .auth import AuthStore
from .local_portfolio import LocalPortfolioStore


READ_ONLY_TOOL = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
WRITE_TOOL = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
UPSERT_TOOL = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)


def _bearer_token(ctx: Context) -> str:
    authorization = str((ctx.headers or {}).get("authorization") or "").strip()
    scheme, separator, token = authorization.partition(" ")
    if scheme.casefold() != "bearer" or not separator or not token.strip():
        raise ToolError("Authenticate with an MCP bearer token issued by POST /api/auth/token using service=mcp")
    return token.strip()


def _mcp_user(ctx: Context, auth_store: AuthStore, *, write: bool = False) -> dict[str, Any]:
    access = auth_store.mcp_access()
    if access["mode"] == "disabled":
        raise ToolError("MCP access is disabled by an administrator")
    token_session = auth_store.api_token(_bearer_token(ctx), service="mcp")
    if not token_session:
        raise ToolError("The MCP token is invalid or expired")
    user = token_session["user"]
    if write and access["mode"] != "read_write":
        raise ToolError("MCP write access is disabled by an administrator")
    if write and user["role"] == "Viewer":
        raise ToolError("Viewer access is read-only")
    return user


def _stored_date(value: str, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    for pattern in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:10], pattern).date().isoformat()
        except ValueError:
            continue
    raise ToolError(f"{field_name} must use dd/mm/yyyy")


def _display_date(value: Any) -> str:
    text = str(value or "").strip()
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return text


def _display_trend_dates(result: dict[str, Any]) -> dict[str, Any]:
    output = {**result, "from": _display_date(result.get("from")), "to": _display_date(result.get("to"))}
    output["accounts"] = [
        {
            **item,
            "points": [{**point, "date": _display_date(point.get("date"))} for point in item.get("points") or []],
        }
        for item in result.get("accounts") or []
    ]
    return output


def create_portfolio_mcp_server(
    get_auth_store: Callable[[], AuthStore],
    get_local_store: Callable[[], LocalPortfolioStore],
    clear_portfolio_cache: Callable[[], None],
) -> MCPServer:
    server = MCPServer(
        name="portfolio-analyzer",
        title="Portfolio Analyzer",
        description="Read and maintain the authenticated user's local portfolio data.",
        instructions=(
            "Use read tools to inspect accounts, holdings, long-term savings, and trends. "
            "Write tools change only the local portfolio database and require MCP Read & write mode. "
            "Never present portfolio output as investment advice. Dates are dd/mm/yyyy."
        ),
    )

    @server.tool(annotations=READ_ONLY_TOOL, structured_output=True)
    def get_access_status(ctx: Context) -> dict[str, Any]:
        """Return the caller identity and current MCP permissions."""
        user = _mcp_user(ctx, get_auth_store())
        access = get_auth_store().mcp_access()
        return {
            "service": "mcp",
            "mode": access["mode"],
            "endpoint": access["endpoint"],
            "user": {"username": user["username"], "role": user["role"]},
            "can_write": access["write_enabled"] and user["role"] in {"Admin", "Operator"},
        }

    @server.tool(annotations=READ_ONLY_TOOL, structured_output=True)
    def list_portfolio_accounts(
        ctx: Context,
        person_id: str = "",
        person_name: str = "",
        account_type: str = "",
        location: str = "",
    ) -> dict[str, Any]:
        """List matching accounts with owners, value, holdings, and linked long-term funds."""
        _mcp_user(ctx, get_auth_store())
        report = get_local_store().reports(
            {
                "person_id": person_id,
                "person_name": person_name,
                "account_type": account_type,
                "location": location,
            }
        )
        return {"count": report["accounts"], "items": report["account_details"], "scope": report["scope"]}

    @server.tool(annotations=READ_ONLY_TOOL, structured_output=True)
    def get_portfolio_report(
        ctx: Context,
        person_id: str = "",
        person_name: str = "",
        account_type: str = "",
        account_id: str = "",
        location: str = "",
    ) -> dict[str, Any]:
        """Return a complete portfolio report filtered by person, category, account, or location."""
        _mcp_user(ctx, get_auth_store())
        return get_local_store().reports(
            {
                "person_id": person_id,
                "person_name": person_name,
                "account_type": account_type,
                "account_id": account_id,
                "location": location,
            }
        )

    @server.tool(annotations=READ_ONLY_TOOL, structured_output=True)
    def get_account_trends(
        ctx: Context,
        date_from: str = "",
        date_to: str = "",
        person_id: str = "",
        person_name: str = "",
        account_type: str = "",
        account_id: str = "",
        location: str = "",
    ) -> dict[str, Any]:
        """Return account value and profit history. Enter dates as dd/mm/yyyy."""
        _mcp_user(ctx, get_auth_store())
        result = get_local_store().account_trends(
            {
                "from": _stored_date(date_from, "From date"),
                "to": _stored_date(date_to, "To date"),
                "person_id": person_id,
                "person_name": person_name,
                "account_type": account_type,
                "account_id": account_id,
                "location": location,
            }
        )
        return _display_trend_dates(result)

    @server.tool(annotations=WRITE_TOOL, structured_output=True)
    def record_portfolio_transaction(
        ctx: Context,
        account_id: str,
        action: str,
        symbol: str,
        stock_market: str,
        quantity: float,
        price: float,
        trade_date: str,
        asset_class: str = "EQUITY",
        currency: str = "",
        comments: str = "",
    ) -> dict[str, Any]:
        """Record a local buy, sell, add, remove, dividend, interest, or fee transaction."""
        _mcp_user(ctx, get_auth_store(), write=True)
        try:
            result = get_local_store().add_transaction(
                {
                    "account_db_id": account_id,
                    "action": action,
                    "symbol": symbol,
                    "stock_market": stock_market,
                    "quantity": quantity,
                    "price_input": price,
                    "trade_date": _stored_date(trade_date, "Trade date"),
                    "asset_class": asset_class,
                    "currency": currency,
                    "comments": comments,
                    "source": "mcp",
                }
            )
        except ValueError as exc:
            raise ToolError(str(exc)) from exc
        clear_portfolio_cache()
        return result

    @server.tool(annotations=UPSERT_TOOL, structured_output=True)
    def save_historical_price(
        ctx: Context,
        symbol: str,
        stock_market: str,
        price: float,
        price_date: str,
        asset_class: str = "EQUITY",
        location: str = "USA",
        currency: str = "",
        comments: str = "",
    ) -> dict[str, Any]:
        """Add or update a local historical price. Enter the price date as dd/mm/yyyy."""
        _mcp_user(ctx, get_auth_store(), write=True)
        try:
            result = get_local_store().save_price(
                {
                    "symbol": symbol,
                    "stock_market": stock_market,
                    "price_input": price,
                    "price_date": _stored_date(price_date, "Price date"),
                    "asset_class": asset_class,
                    "location": location,
                    "currency": currency,
                    "comments": comments,
                    "source": "mcp",
                }
            )
        except ValueError as exc:
            raise ToolError(str(exc)) from exc
        clear_portfolio_cache()
        return {**result, "price_date": _display_date(result.get("price_date"))}

    return server
