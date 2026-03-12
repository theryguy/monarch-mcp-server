"""Tests for SecureMonarchSession."""

import pytest
from unittest.mock import patch, MagicMock

import keyring.errors

from monarch_mcp_server.secure_session import (
    SecureMonarchSession,
    KEYRING_SERVICE,
    KEYRING_USERNAME,
)


class TestSaveToken:
    def test_save_token_success(self):
        session = SecureMonarchSession()
        with (
            patch("monarch_mcp_server.secure_session.keyring.set_password") as mock_set,
            patch.object(session, "_cleanup_old_session_files") as mock_cleanup,
        ):
            session.save_token("tok123")

            mock_set.assert_called_once_with(KEYRING_SERVICE, KEYRING_USERNAME, "tok123")
            mock_cleanup.assert_called_once()

    def test_save_token_keyring_error(self):
        session = SecureMonarchSession()
        with patch(
            "monarch_mcp_server.secure_session.keyring.set_password",
            side_effect=Exception("Keyring locked"),
        ):
            with pytest.raises(Exception, match="Keyring locked"):
                session.save_token("tok123")


class TestLoadToken:
    def test_load_token_found(self):
        session = SecureMonarchSession()
        with patch(
            "monarch_mcp_server.secure_session.keyring.get_password",
            return_value="stored-token",
        ):
            assert session.load_token() == "stored-token"

    def test_load_token_not_found(self):
        session = SecureMonarchSession()
        with patch(
            "monarch_mcp_server.secure_session.keyring.get_password",
            return_value=None,
        ):
            assert session.load_token() is None

    def test_load_token_keyring_error(self):
        session = SecureMonarchSession()
        with patch(
            "monarch_mcp_server.secure_session.keyring.get_password",
            side_effect=Exception("Keyring unavailable"),
        ):
            assert session.load_token() is None


class TestDeleteToken:
    def test_delete_token_success(self):
        session = SecureMonarchSession()
        with (
            patch("monarch_mcp_server.secure_session.keyring.delete_password") as mock_del,
            patch.object(session, "_cleanup_old_session_files"),
        ):
            session.delete_token()

            mock_del.assert_called_once_with(KEYRING_SERVICE, KEYRING_USERNAME)

    def test_delete_token_not_found(self):
        session = SecureMonarchSession()
        with patch(
            "monarch_mcp_server.secure_session.keyring.delete_password",
            side_effect=keyring.errors.PasswordDeleteError("not found"),
        ):
            # Should not raise
            session.delete_token()

    def test_delete_token_other_error(self):
        session = SecureMonarchSession()
        with patch(
            "monarch_mcp_server.secure_session.keyring.delete_password",
            side_effect=RuntimeError("unexpected"),
        ):
            # Should not raise
            session.delete_token()


class TestGetAuthenticatedClient:
    def test_get_client_with_token(self):
        session = SecureMonarchSession()
        mock_client = MagicMock()
        with (
            patch(
                "monarch_mcp_server.secure_session.keyring.get_password",
                return_value="the-token",
            ),
            patch(
                "monarch_mcp_server.secure_session.MonarchMoney",
                return_value=mock_client,
            ) as mock_mm_cls,
        ):
            result = session.get_authenticated_client()

            mock_mm_cls.assert_called_once_with(token="the-token")
            assert result is mock_client

    def test_get_client_no_token(self):
        session = SecureMonarchSession()
        with patch(
            "monarch_mcp_server.secure_session.keyring.get_password",
            return_value=None,
        ):
            assert session.get_authenticated_client() is None

    def test_get_client_constructor_error(self):
        session = SecureMonarchSession()
        with (
            patch(
                "monarch_mcp_server.secure_session.keyring.get_password",
                return_value="the-token",
            ),
            patch(
                "monarch_mcp_server.secure_session.MonarchMoney",
                side_effect=Exception("bad token"),
            ),
        ):
            assert session.get_authenticated_client() is None


class TestSaveAuthenticatedSession:
    def test_save_session_with_token(self):
        session = SecureMonarchSession()
        mock_mm = MagicMock()
        mock_mm.token = "session-tok"
        with (
            patch("monarch_mcp_server.secure_session.keyring.set_password") as mock_set,
            patch.object(session, "_cleanup_old_session_files"),
        ):
            session.save_authenticated_session(mock_mm)

            mock_set.assert_called_once_with(
                KEYRING_SERVICE, KEYRING_USERNAME, "session-tok"
            )

    def test_save_session_no_token(self):
        session = SecureMonarchSession()
        mock_mm = MagicMock()
        mock_mm.token = None
        with patch(
            "monarch_mcp_server.secure_session.keyring.set_password"
        ) as mock_set:
            session.save_authenticated_session(mock_mm)

            mock_set.assert_not_called()


class TestCleanupOldSessionFiles:
    def test_cleanup_removes_existing_file(self):
        session = SecureMonarchSession()
        with (
            patch("monarch_mcp_server.secure_session.os.path.exists", return_value=True),
            patch("monarch_mcp_server.secure_session.os.path.isfile", return_value=True),
            patch("monarch_mcp_server.secure_session.os.remove") as mock_remove,
            patch("monarch_mcp_server.secure_session.os.path.isdir", return_value=False),
        ):
            session._cleanup_old_session_files()

            assert mock_remove.call_count >= 1

    def test_cleanup_removes_empty_directory(self):
        session = SecureMonarchSession()

        def fake_exists(path):
            return path == ".mm"

        def fake_isfile(path):
            return False

        def fake_isdir(path):
            return path == ".mm"

        with (
            patch("monarch_mcp_server.secure_session.os.path.exists", side_effect=fake_exists),
            patch("monarch_mcp_server.secure_session.os.path.isfile", side_effect=fake_isfile),
            patch("monarch_mcp_server.secure_session.os.path.isdir", side_effect=fake_isdir),
            patch("monarch_mcp_server.secure_session.os.listdir", return_value=[]),
            patch("monarch_mcp_server.secure_session.os.rmdir") as mock_rmdir,
        ):
            session._cleanup_old_session_files()

            mock_rmdir.assert_called_once_with(".mm")

    def test_cleanup_skips_nonempty_directory(self):
        session = SecureMonarchSession()

        def fake_exists(path):
            return path == ".mm"

        def fake_isfile(path):
            return False

        def fake_isdir(path):
            return path == ".mm"

        with (
            patch("monarch_mcp_server.secure_session.os.path.exists", side_effect=fake_exists),
            patch("monarch_mcp_server.secure_session.os.path.isfile", side_effect=fake_isfile),
            patch("monarch_mcp_server.secure_session.os.path.isdir", side_effect=fake_isdir),
            patch("monarch_mcp_server.secure_session.os.listdir", return_value=["keep_me"]),
            patch("monarch_mcp_server.secure_session.os.rmdir") as mock_rmdir,
        ):
            session._cleanup_old_session_files()

            mock_rmdir.assert_not_called()

    def test_cleanup_handles_permission_error(self):
        session = SecureMonarchSession()
        with (
            patch("monarch_mcp_server.secure_session.os.path.exists", return_value=True),
            patch("monarch_mcp_server.secure_session.os.path.isfile", return_value=True),
            patch(
                "monarch_mcp_server.secure_session.os.remove",
                side_effect=PermissionError("denied"),
            ),
        ):
            # Should not raise
            session._cleanup_old_session_files()
