import asyncio
import sqlite3
from contextlib import asynccontextmanager

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from app import main
from app.auth import AuthStore
from app.local_portfolio import LocalPortfolioStore


def _environment(tmp_path, monkeypatch):
    store = LocalPortfolioStore(tmp_path / "local.sqlite3")
    auth = AuthStore(store.path)
    auth.initialize()
    admin, _session, _csrf = auth.authenticate("admin", "admin")
    auth.change_password(admin["id"], "admin", "mcp-admin-password")
    monkeypatch.setattr(main, "local_store", store)
    monkeypatch.setattr(main, "auth_store", auth)
    return store, auth


def _issue(auth, service="mcp", username="admin", password="mcp-admin-password"):
    _user, token, _expires = auth.create_api_token(username, password, service=service)
    return token


@asynccontextmanager
async def _mcp_client(token):
    headers = {"Authorization": f"Bearer {token}"}
    transport = httpx2.ASGITransport(app=main.app)
    async with httpx2.AsyncClient(
        transport=transport,
        base_url="https://localhost:6443",
        headers=headers,
    ) as http_client:
        async with Client(
            streamable_http_client("https://localhost:6443/mcp/", http_client=http_client)
        ) as client:
            yield client


def test_mcp_read_tools_and_read_write_mode(tmp_path, monkeypatch):
    store, auth = _environment(tmp_path, monkeypatch)
    member = store.save_family_member(
        {"first_name": "Maya", "last_name": "Levy", "birth_date": "1990-02-03"}
    )
    account = store.save_account(
        {
            "type": "Investment",
            "location": "Israel",
            "currency": "ILS",
            "initial_cash": 10000,
            "management_company": "Local Broker",
            "persons": [member],
        }
    )
    auth.set_mcp_access_mode("read_only")
    token = _issue(auth)
    auth.set_api_access_mode("read_only")
    rest_token = _issue(auth, service="rest")
    viewer = auth.create_user(
        {
            "first_name": "Vera",
            "last_name": "Viewer",
            "username": "mcp-viewer",
            "password": "viewer-temporary-password",
            "role": "Viewer",
        }
    )
    auth.change_password(viewer["id"], "viewer-temporary-password", "viewer-mcp-password")
    viewer_token = _issue(auth, username="mcp-viewer", password="viewer-mcp-password")

    async def read_only_calls(client):
        tools = await client.list_tools()
        tool_names = {tool.name for tool in tools.tools}
        assert {
            "get_access_status",
            "list_portfolio_accounts",
            "get_portfolio_report",
            "get_account_trends",
            "record_portfolio_transaction",
            "save_historical_price",
        } <= tool_names
        status = await client.call_tool("get_access_status", {})
        assert status.is_error is False
        assert status.structured_content["mode"] == "read_only"
        assert status.structured_content["can_write"] is False
        accounts = await client.call_tool("list_portfolio_accounts", {"person_name": "Maya Levy"})
        assert accounts.is_error is False
        assert accounts.structured_content["count"] == 1
        blocked = await client.call_tool(
            "record_portfolio_transaction",
            {
                "account_id": account["id"],
                "action": "BUY",
                "symbol": "MCPQ",
                "stock_market": "NASDAQ",
                "quantity": 2,
                "price": 25,
                "trade_date": "22/08/2026",
            },
        )
        assert blocked.is_error is True
        assert "write access is disabled" in blocked.content[0].text

    async def write_call(client):
        saved = await client.call_tool(
            "record_portfolio_transaction",
            {
                "account_id": account["id"],
                "action": "BUY",
                "symbol": "MCPQ",
                "stock_market": "NASDAQ",
                "quantity": 2,
                "price": 25,
                "trade_date": "22/08/2026",
            },
        )
        assert saved.is_error is False
        assert saved.structured_content["symbol"] == "MCPQ"
        price = await client.call_tool(
            "save_historical_price",
            {
                "symbol": "MCPQ",
                "stock_market": "NASDAQ",
                "price": 27,
                "price_date": "22/08/2026",
            },
        )
        assert price.is_error is False
        assert price.structured_content["price_date"] == "22/08/2026"

    async def rejected_rest_token():
        transport = httpx2.ASGITransport(app=main.app)
        async with httpx2.AsyncClient(transport=transport, base_url="https://localhost:6443") as client:
            missing = await client.post("/mcp/", json={})
            assert missing.status_code == 401
            wrong_service = await client.post(
                "/mcp/", headers={"Authorization": f"Bearer {rest_token}"}, json={}
            )
            assert wrong_service.status_code == 401
            assert wrong_service.json()["detail"]["code"] == "invalid_token"

    async def viewer_calls(client):
        report = await client.call_tool("get_portfolio_report", {})
        assert report.is_error is False
        blocked = await client.call_tool(
            "record_portfolio_transaction",
            {
                "account_id": account["id"],
                "action": "BUY",
                "symbol": "VIEW",
                "stock_market": "NASDAQ",
                "quantity": 1,
                "price": 10,
                "trade_date": "22/08/2026",
            },
        )
        assert blocked.is_error is True
        assert "Viewer access is read-only" in blocked.content[0].text

    async def scenario():
        async with main.portfolio_mcp.session_manager.run():
            async with _mcp_client(token) as client:
                await read_only_calls(client)
            assert store.list_transactions() == []
            auth.set_mcp_access_mode("read_write")
            async with _mcp_client(token) as client:
                await write_call(client)
            await rejected_rest_token()
            async with _mcp_client(viewer_token) as client:
                await viewer_calls(client)

    asyncio.run(scenario())
    assert len(store.list_transactions()) == 1
    assert len(store.list_prices()) == 1


def test_rest_and_mcp_modes_and_tokens_are_independent(tmp_path, monkeypatch):
    _store, auth = _environment(tmp_path, monkeypatch)
    auth.set_integration_access_modes("read_only", "read_only")
    rest_token = _issue(auth, service="rest")
    mcp_token = _issue(auth, service="mcp")

    access = auth.integration_access()
    assert access["rest"]["active_tokens"] == 1
    assert access["mcp"]["active_tokens"] == 1
    auth.set_api_access_mode("disabled")
    assert auth.api_token(rest_token, service="rest") is None
    assert auth.api_token(mcp_token, service="mcp") is not None
    assert auth.mcp_access()["mode"] == "read_only"

    auth.set_mcp_access_mode("disabled")
    assert auth.api_token(mcp_token, service="mcp") is None
    assert auth.integration_access()["mcp"]["active_tokens"] == 0


def test_existing_api_auth_schema_migrates_with_mcp_disabled(tmp_path):
    database = tmp_path / "old-auth.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "create table api_tokens (token_hash text primary key, user_id text not null, created_at text not null, last_used_at text not null, expires_at text not null)"
        )
        connection.execute(
            "create table api_access_settings (singleton integer primary key, mode text not null, updated_at text not null)"
        )
        connection.execute(
            "insert into api_access_settings (singleton, mode, updated_at) values (1, 'read_only', '2026-08-22T00:00:00Z')"
        )

    auth = AuthStore(database)
    auth.initialize()

    with sqlite3.connect(database) as connection:
        token_columns = {row[1] for row in connection.execute("pragma table_info(api_tokens)")}
        access_columns = {row[1] for row in connection.execute("pragma table_info(api_access_settings)")}
    assert "service" in token_columns
    assert "mcp_mode" in access_columns
    assert auth.api_access()["mode"] == "read_only"
    assert auth.mcp_access()["mode"] == "disabled"
