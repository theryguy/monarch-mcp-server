"""Tests for Monarch Money MCP Server tools and utilities."""

import asyncio
import json

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from monarch_mcp_server.server import (
    MonarchConfig,
    run_async,
    get_monarch_client,
    setup_authentication,
    check_auth_status,
    debug_session_loading,
    get_accounts,
    get_transactions,
    get_budgets,
    get_cashflow,
    get_account_holdings,
    create_transaction,
    update_transaction,
    refresh_accounts,
)


# ---------------------------------------------------------------------------
# MonarchConfig
# ---------------------------------------------------------------------------


class TestMonarchConfig:
    def test_default_values(self):
        config = MonarchConfig()
        assert config.email is None
        assert config.password is None
        assert config.session_file == "monarch_session.json"

    def test_custom_values(self):
        config = MonarchConfig(
            email="a@b.com", password="pw", session_file="custom.json"
        )
        assert config.email == "a@b.com"
        assert config.password == "pw"
        assert config.session_file == "custom.json"


# ---------------------------------------------------------------------------
# run_async
# ---------------------------------------------------------------------------


class TestRunAsync:
    def test_returns_result(self):
        async def coro():
            return 42

        assert run_async(coro()) == 42

    def test_propagates_exception(self):
        async def coro():
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            run_async(coro())

    def test_with_awaitable_work(self):
        async def coro():
            await asyncio.sleep(0)
            return "done"

        assert run_async(coro()) == "done"


# ---------------------------------------------------------------------------
# get_monarch_client
# ---------------------------------------------------------------------------


class TestGetMonarchClient:
    @pytest.mark.asyncio
    async def test_client_from_keyring(self):
        mock_client = MagicMock()
        with patch(
            "monarch_mcp_server.server.secure_session"
        ) as mock_session:
            mock_session.get_authenticated_client.return_value = mock_client
            result = await get_monarch_client()
            assert result is mock_client

    @pytest.mark.asyncio
    async def test_client_from_env_vars(self, monkeypatch):
        monkeypatch.setenv("MONARCH_EMAIL", "test@example.com")
        monkeypatch.setenv("MONARCH_PASSWORD", "secret")

        mock_client = AsyncMock()
        mock_client.token = "new-token"

        with (
            patch("monarch_mcp_server.server.secure_session") as mock_session,
            patch(
                "monarch_mcp_server.server.MonarchMoney",
                return_value=mock_client,
            ),
        ):
            mock_session.get_authenticated_client.return_value = None
            result = await get_monarch_client()

            mock_client.login.assert_awaited_once_with("test@example.com", "secret")
            mock_session.save_authenticated_session.assert_called_once_with(mock_client)
            assert result is mock_client

    @pytest.mark.asyncio
    async def test_client_no_auth_raises(self, monkeypatch):
        monkeypatch.delenv("MONARCH_EMAIL", raising=False)
        monkeypatch.delenv("MONARCH_PASSWORD", raising=False)

        with patch("monarch_mcp_server.server.secure_session") as mock_session:
            mock_session.get_authenticated_client.return_value = None
            with pytest.raises(RuntimeError, match="Authentication needed"):
                await get_monarch_client()

    @pytest.mark.asyncio
    async def test_client_env_login_failure(self, monkeypatch):
        monkeypatch.setenv("MONARCH_EMAIL", "test@example.com")
        monkeypatch.setenv("MONARCH_PASSWORD", "wrong")

        mock_client = AsyncMock()
        mock_client.login.side_effect = Exception("bad creds")

        with (
            patch("monarch_mcp_server.server.secure_session") as mock_session,
            patch(
                "monarch_mcp_server.server.MonarchMoney",
                return_value=mock_client,
            ),
        ):
            mock_session.get_authenticated_client.return_value = None
            with pytest.raises(Exception, match="bad creds"):
                await get_monarch_client()


# ---------------------------------------------------------------------------
# setup_authentication
# ---------------------------------------------------------------------------


class TestSetupAuthentication:
    def test_returns_instructions(self):
        result = setup_authentication()
        assert "login_setup.py" in result
        assert "One-Time Setup" in result


# ---------------------------------------------------------------------------
# check_auth_status
# ---------------------------------------------------------------------------


class TestCheckAuthStatus:
    def test_token_found(self):
        with patch("monarch_mcp_server.server.secure_session") as mock_session:
            mock_session.load_token.return_value = "tok"
            result = check_auth_status()
            assert "Authentication token found" in result

    def test_no_token(self):
        with patch("monarch_mcp_server.server.secure_session") as mock_session:
            mock_session.load_token.return_value = None
            result = check_auth_status()
            assert "No authentication token found" in result

    def test_with_env_email(self, monkeypatch):
        monkeypatch.setenv("MONARCH_EMAIL", "user@test.com")
        with patch("monarch_mcp_server.server.secure_session") as mock_session:
            mock_session.load_token.return_value = None
            result = check_auth_status()
            assert "user@test.com" in result

    def test_exception_handling(self):
        with patch("monarch_mcp_server.server.secure_session") as mock_session:
            mock_session.load_token.side_effect = Exception("fail")
            result = check_auth_status()
            assert "Error checking auth status" in result


# ---------------------------------------------------------------------------
# debug_session_loading
# ---------------------------------------------------------------------------


class TestDebugSessionLoading:
    def test_token_found(self):
        with patch("monarch_mcp_server.server.secure_session") as mock_session:
            mock_session.load_token.return_value = "tok123"
            result = debug_session_loading()
            assert "Token found" in result
            assert "length: 6" in result

    def test_no_token(self):
        with patch("monarch_mcp_server.server.secure_session") as mock_session:
            mock_session.load_token.return_value = None
            result = debug_session_loading()
            assert "No token found" in result

    def test_exception(self):
        with patch("monarch_mcp_server.server.secure_session") as mock_session:
            mock_session.load_token.side_effect = RuntimeError("keyring broken")
            result = debug_session_loading()
            assert "Keyring access failed" in result
            assert "keyring broken" in result


# ---------------------------------------------------------------------------
# get_accounts
# ---------------------------------------------------------------------------


class TestGetAccounts:
    def test_success(self, mock_get_monarch_client, sample_accounts_response):
        mock_get_monarch_client.get_accounts.return_value = sample_accounts_response
        result = json.loads(get_accounts())

        assert len(result) == 2
        assert result[0]["name"] == "Checking"
        assert result[0]["balance"] == 5000.00
        assert result[0]["institution"] == "Chase"
        assert result[0]["is_active"] is True

    def test_empty_accounts(self, mock_get_monarch_client):
        mock_get_monarch_client.get_accounts.return_value = {"accounts": []}
        result = json.loads(get_accounts())
        assert result == []

    def test_missing_nested_fields(self, mock_get_monarch_client):
        mock_get_monarch_client.get_accounts.return_value = {
            "accounts": [
                {
                    "id": "acc-3",
                    "displayName": None,
                    "name": "Fallback Name",
                    "type": None,
                    "currentBalance": 100.0,
                    "institution": None,
                    "deactivatedAt": None,
                }
            ]
        }
        result = json.loads(get_accounts())
        assert result[0]["name"] == "Fallback Name"
        assert result[0]["type"] is None
        assert result[0]["institution"] is None
        assert result[0]["is_active"] is True  # deactivatedAt is None -> active

    def test_error(self):
        with patch(
            "monarch_mcp_server.server.get_monarch_client",
            new_callable=AsyncMock,
            side_effect=RuntimeError("no auth"),
        ):
            result = get_accounts()
            assert "Error getting accounts" in result


# ---------------------------------------------------------------------------
# get_transactions
# ---------------------------------------------------------------------------


class TestGetTransactions:
    def test_success_default_params(
        self, mock_get_monarch_client, sample_transactions_response
    ):
        mock_get_monarch_client.get_transactions.return_value = (
            sample_transactions_response
        )
        result = json.loads(get_transactions())

        assert len(result) == 2
        assert result[0]["id"] == "txn-1"
        assert result[0]["amount"] == -42.50
        assert result[0]["category"] == "Groceries"
        assert result[0]["merchant"] == "Whole Foods"
        assert result[0]["is_pending"] is False

        mock_get_monarch_client.get_transactions.assert_awaited_once_with(
            limit=100, offset=0
        )

    def test_with_filters(self, mock_get_monarch_client):
        mock_get_monarch_client.get_transactions.return_value = {
            "allTransactions": {"results": []}
        }
        get_transactions(
            limit=10,
            offset=5,
            start_date="2024-01-01",
            end_date="2024-12-31",
            account_id="acc-1",
        )

        mock_get_monarch_client.get_transactions.assert_awaited_once_with(
            limit=10,
            offset=5,
            start_date="2024-01-01",
            end_date="2024-12-31",
            account_id="acc-1",
        )

    def test_null_category_and_merchant(self, mock_get_monarch_client):
        mock_get_monarch_client.get_transactions.return_value = {
            "allTransactions": {
                "results": [
                    {
                        "id": "txn-3",
                        "date": "2024-01-10",
                        "amount": 50.0,
                        "description": "Transfer",
                        "category": None,
                        "account": {"displayName": "Checking"},
                        "merchant": None,
                        "isPending": True,
                    }
                ]
            }
        }
        result = json.loads(get_transactions())
        assert result[0]["category"] is None
        assert result[0]["merchant"] is None
        assert result[0]["is_pending"] is True

    def test_error(self):
        with patch(
            "monarch_mcp_server.server.get_monarch_client",
            new_callable=AsyncMock,
            side_effect=RuntimeError("no auth"),
        ):
            result = get_transactions()
            assert "Error getting transactions" in result


# ---------------------------------------------------------------------------
# get_budgets
# ---------------------------------------------------------------------------


class TestGetBudgets:
    def test_success(self, mock_get_monarch_client, sample_budgets_response):
        mock_get_monarch_client.get_budgets.return_value = sample_budgets_response
        result = json.loads(get_budgets())

        assert len(result) == 1
        assert result[0]["name"] == "Groceries Budget"
        assert result[0]["amount"] == 500.00
        assert result[0]["remaining"] == 250.00

    def test_error(self):
        with patch(
            "monarch_mcp_server.server.get_monarch_client",
            new_callable=AsyncMock,
            side_effect=RuntimeError("no auth"),
        ):
            result = get_budgets()
            assert "Error getting budgets" in result


# ---------------------------------------------------------------------------
# get_cashflow
# ---------------------------------------------------------------------------


class TestGetCashflow:
    def test_success_no_dates(self, mock_get_monarch_client):
        mock_get_monarch_client.get_cashflow.return_value = {"income": 5000, "expenses": 3000}
        result = json.loads(get_cashflow())
        assert result["income"] == 5000

        mock_get_monarch_client.get_cashflow.assert_awaited_once_with()

    def test_success_with_dates(self, mock_get_monarch_client):
        mock_get_monarch_client.get_cashflow.return_value = {}
        get_cashflow(start_date="2024-01-01", end_date="2024-01-31")

        mock_get_monarch_client.get_cashflow.assert_awaited_once_with(
            start_date="2024-01-01", end_date="2024-01-31"
        )

    def test_error(self):
        with patch(
            "monarch_mcp_server.server.get_monarch_client",
            new_callable=AsyncMock,
            side_effect=RuntimeError("no auth"),
        ):
            result = get_cashflow()
            assert "Error getting cashflow" in result


# ---------------------------------------------------------------------------
# get_account_holdings
# ---------------------------------------------------------------------------


class TestGetAccountHoldings:
    def test_success(self, mock_get_monarch_client):
        mock_get_monarch_client.get_account_holdings.return_value = {
            "holdings": [{"ticker": "VTI", "value": 10000}]
        }
        result = json.loads(get_account_holdings("acc-1"))
        assert result["holdings"][0]["ticker"] == "VTI"

        mock_get_monarch_client.get_account_holdings.assert_awaited_once_with("acc-1")

    def test_error(self):
        with patch(
            "monarch_mcp_server.server.get_monarch_client",
            new_callable=AsyncMock,
            side_effect=RuntimeError("no auth"),
        ):
            result = get_account_holdings("acc-1")
            assert "Error getting account holdings" in result


# ---------------------------------------------------------------------------
# create_transaction
# ---------------------------------------------------------------------------


class TestCreateTransaction:
    def test_success_required_fields(self, mock_get_monarch_client):
        mock_get_monarch_client.create_transaction.return_value = {"id": "new-txn-1"}
        result = json.loads(
            create_transaction(
                account_id="acc-1",
                amount=-50.0,
                description="Coffee",
                date="2024-01-20",
            )
        )
        assert result["id"] == "new-txn-1"

        mock_get_monarch_client.create_transaction.assert_awaited_once_with(
            account_id="acc-1",
            amount=-50.0,
            description="Coffee",
            date="2024-01-20",
        )

    def test_success_all_fields(self, mock_get_monarch_client):
        mock_get_monarch_client.create_transaction.return_value = {"id": "new-txn-2"}
        create_transaction(
            account_id="acc-1",
            amount=-50.0,
            description="Coffee",
            date="2024-01-20",
            category_id="cat-1",
            merchant_name="Starbucks",
        )

        mock_get_monarch_client.create_transaction.assert_awaited_once_with(
            account_id="acc-1",
            amount=-50.0,
            description="Coffee",
            date="2024-01-20",
            category_id="cat-1",
            merchant_name="Starbucks",
        )

    def test_error(self):
        with patch(
            "monarch_mcp_server.server.get_monarch_client",
            new_callable=AsyncMock,
            side_effect=RuntimeError("no auth"),
        ):
            result = create_transaction(
                account_id="acc-1",
                amount=-50.0,
                description="Coffee",
                date="2024-01-20",
            )
            assert "Error creating transaction" in result


# ---------------------------------------------------------------------------
# update_transaction
# ---------------------------------------------------------------------------


class TestUpdateTransaction:
    def test_update_single_field(self, mock_get_monarch_client):
        mock_get_monarch_client.update_transaction.return_value = {"success": True}
        result = json.loads(update_transaction(transaction_id="txn-1", amount=50.0))
        assert result["success"] is True

        mock_get_monarch_client.update_transaction.assert_awaited_once_with(
            transaction_id="txn-1", amount=50.0
        )

    def test_update_all_fields(self, mock_get_monarch_client):
        mock_get_monarch_client.update_transaction.return_value = {"success": True}
        update_transaction(
            transaction_id="txn-1",
            amount=75.0,
            description="Updated",
            category_id="cat-2",
            date="2024-02-01",
        )

        mock_get_monarch_client.update_transaction.assert_awaited_once_with(
            transaction_id="txn-1",
            amount=75.0,
            description="Updated",
            category_id="cat-2",
            date="2024-02-01",
        )

    def test_update_no_optional_fields(self, mock_get_monarch_client):
        mock_get_monarch_client.update_transaction.return_value = {"success": True}
        update_transaction(transaction_id="txn-1")

        mock_get_monarch_client.update_transaction.assert_awaited_once_with(
            transaction_id="txn-1"
        )

    def test_error(self):
        with patch(
            "monarch_mcp_server.server.get_monarch_client",
            new_callable=AsyncMock,
            side_effect=RuntimeError("no auth"),
        ):
            result = update_transaction(transaction_id="txn-1")
            assert "Error updating transaction" in result


# ---------------------------------------------------------------------------
# refresh_accounts
# ---------------------------------------------------------------------------


class TestRefreshAccounts:
    def test_success(self, mock_get_monarch_client):
        mock_get_monarch_client.request_accounts_refresh.return_value = {
            "status": "refreshing"
        }
        result = json.loads(refresh_accounts())
        assert result["status"] == "refreshing"

    def test_error(self):
        with patch(
            "monarch_mcp_server.server.get_monarch_client",
            new_callable=AsyncMock,
            side_effect=RuntimeError("no auth"),
        ):
            result = refresh_accounts()
            assert "Error refreshing accounts" in result
