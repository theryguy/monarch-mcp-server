# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Monarch Money MCP Server — a Model Context Protocol server that exposes Monarch Money personal finance data (accounts, transactions, budgets, cashflow) as tools for Claude Desktop. Built with FastMCP, uses the `monarchmoneycommunity` Python library (community fork) for API access.

## Commands

```bash
# Install dependencies
uv sync

# Run server
uv run monarch-mcp-server

# Run authentication setup (interactive)
uv run python login_setup.py

# Format code
uv run black src/
uv run isort src/

# Type check (strict mode)
uv run mypy src/

# Run tests
uv run pytest
uv run pytest tests/test_foo.py::test_bar  # single test
```

## Architecture

Three main files in a `src/` layout package (`src/monarch_mcp_server/`):

- **server.py** — FastMCP server with 11 tool definitions (auth, accounts, transactions, analysis). Tools are synchronous but call async MonarchMoney API via `run_async()`, which spins up a new event loop in a ThreadPoolExecutor. Each tool independently obtains an authenticated client (no global state).

- **secure_session.py** — Keyring-based credential storage (`SecureMonarchSession`). Stores auth tokens in the OS keyring (service: `com.mcp.monarch-mcp-server`). Includes cleanup of legacy pickle/JSON session files. Exported as a module-level `secure_session` singleton.

- **login_setup.py** — Standalone interactive script for one-time auth setup. Handles MFA/2FA, pre-deletes stale keychain entries via `security` CLI, saves tokens to keyring.

**Auth flow:** Keyring token is primary; falls back to env vars (`MONARCH_EMAIL`, `MONARCH_PASSWORD`). Client obtained fresh per tool call via `get_monarch_client()`.

## Key Conventions

- Python >= 3.12 required
- Black formatter, line-length 88
- isort with black profile
- All dates use `YYYY-MM-DD` format
- Transaction amounts: positive = income, negative = expenses
- Tools return JSON-formatted strings
- pytest with `asyncio_mode = "auto"`

## Testing

Tests live in `tests/` with shared fixtures in `conftest.py`. All external dependencies (MonarchMoney API, keyring) are mocked — no real credentials needed. Two test modules:

- **test_secure_session.py** — token CRUD, client creation, legacy session cleanup
- **test_server.py** — all 11 MCP server tools (accounts, transactions, budgets, cashflow, holdings, create/update, refresh)

Key fixture: `mock_get_monarch_client` patches `get_monarch_client` to return a `MagicMock` with `AsyncMock` methods, used by most server tool tests.
