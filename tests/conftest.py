"""Shared fixtures for Monarch MCP Server tests."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def mock_monarch_client():
    """Create a mock MonarchMoney client with async methods."""
    client = MagicMock()
    client.token = "fake-token-abc"

    # Configure async methods
    client.get_accounts = AsyncMock()
    client.get_transactions = AsyncMock()
    client.get_budgets = AsyncMock()
    client.get_cashflow = AsyncMock()
    client.get_account_holdings = AsyncMock()
    client.create_transaction = AsyncMock()
    client.update_transaction = AsyncMock()
    client.request_accounts_refresh = AsyncMock()
    client.login = AsyncMock()

    return client


@pytest.fixture
def mock_get_monarch_client(mock_monarch_client):
    """Patch get_monarch_client to return the mock client."""
    with patch(
        "monarch_mcp_server.server.get_monarch_client",
        new_callable=AsyncMock,
        return_value=mock_monarch_client,
    ):
        yield mock_monarch_client


@pytest.fixture
def sample_accounts_response():
    return {
        "accounts": [
            {
                "id": "acc-1",
                "displayName": "Checking",
                "type": {"name": "depository"},
                "currentBalance": 5000.00,
                "institution": {"name": "Chase"},
                "isActive": True,
            },
            {
                "id": "acc-2",
                "displayName": "Savings",
                "type": {"name": "depository"},
                "currentBalance": 15000.00,
                "institution": {"name": "Ally"},
                "isActive": True,
            },
        ]
    }


@pytest.fixture
def sample_transactions_response():
    return {
        "allTransactions": {
            "results": [
                {
                    "id": "txn-1",
                    "date": "2024-01-15",
                    "amount": -42.50,
                    "description": "Grocery Store",
                    "category": {"name": "Groceries"},
                    "account": {"displayName": "Checking"},
                    "merchant": {"name": "Whole Foods"},
                    "isPending": False,
                },
                {
                    "id": "txn-2",
                    "date": "2024-01-14",
                    "amount": 3000.00,
                    "description": "Paycheck",
                    "category": {"name": "Income"},
                    "account": {"displayName": "Checking"},
                    "merchant": None,
                    "isPending": False,
                },
            ]
        }
    }


@pytest.fixture
def sample_budgets_response():
    return {
        "budgets": [
            {
                "id": "bud-1",
                "name": "Groceries Budget",
                "amount": 500.00,
                "spent": 250.00,
                "remaining": 250.00,
                "category": {"name": "Groceries"},
                "period": "monthly",
            }
        ]
    }
