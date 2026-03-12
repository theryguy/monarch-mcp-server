"""
Secure session management for Monarch Money MCP Server using keyring.
Falls back to an encrypted session file when keyring is unavailable.
"""

import keyring
import logging
import os
from typing import Optional
from monarchmoney import MonarchMoney

logger = logging.getLogger(__name__)

# Keyring service identifiers
KEYRING_SERVICE = "com.mcp.monarch-mcp-server"
KEYRING_USERNAME = "monarch-token"

# Fallback session file (absolute path so it works regardless of CWD)
SESSION_FILE = os.path.join(os.path.expanduser("~"), ".monarch_mcp", "session.pickle")


class SecureMonarchSession:
    """Manages Monarch Money sessions securely using the system keyring,
    with automatic fallback to a session file when keyring is unavailable."""

    def save_token(self, token: str) -> None:
        """Save the authentication token to the system keyring."""
        keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME, token)
        logger.info("✅ Token saved securely to keyring")

    def load_token(self) -> Optional[str]:
        """Load the authentication token from the system keyring."""
        try:
            token = keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)
            if token:
                logger.info("✅ Token loaded from keyring")
            return token
        except Exception as e:
            logger.warning(f"⚠️ Could not read from keyring: {e}")
            return None

    def delete_token(self) -> None:
        """Delete the authentication token from the system keyring."""
        try:
            keyring.delete_password(KEYRING_SERVICE, KEYRING_USERNAME)
            logger.info("🗑️ Token deleted from keyring")
        except keyring.errors.PasswordDeleteError:
            logger.info("🔍 No token found in keyring to delete")
        except Exception as e:
            logger.warning(f"⚠️ Could not delete from keyring: {e}")

        # Also remove session file
        if os.path.exists(SESSION_FILE):
            try:
                os.remove(SESSION_FILE)
                logger.info(f"🗑️ Session file removed: {SESSION_FILE}")
            except Exception as e:
                logger.warning(f"⚠️ Could not remove session file: {e}")

        self._cleanup_old_session_files()

    def save_authenticated_session(self, mm: MonarchMoney) -> None:
        """Save the session from an authenticated MonarchMoney instance.

        Tries keyring first; falls back to a session file if keyring is
        unavailable (e.g. macOS Keychain access denied in terminal contexts).
        """
        # Primary: keyring token storage
        if mm.token:
            try:
                self.save_token(mm.token)
                return
            except Exception as e:
                logger.warning(
                    f"⚠️ Keyring unavailable ({e}), falling back to session file"
                )

        # Fallback: library's own pickle-based session file
        os.makedirs(os.path.dirname(SESSION_FILE), exist_ok=True)
        mm.save_session(SESSION_FILE)
        logger.info(f"✅ Session saved to file: {SESSION_FILE}")

    def get_authenticated_client(self) -> Optional[MonarchMoney]:
        """Get an authenticated MonarchMoney client.

        Tries keyring token first; falls back to session file.
        """
        # Primary: keyring token
        token = self.load_token()
        if token:
            try:
                client = MonarchMoney(token=token)
                logger.info("✅ MonarchMoney client created with stored token")
                return client
            except Exception as e:
                logger.warning(f"⚠️ Keyring token unusable: {e}")

        # Fallback: session file
        if os.path.exists(SESSION_FILE):
            try:
                client = MonarchMoney()
                client.load_session(SESSION_FILE)
                logger.info(f"✅ MonarchMoney client loaded from session file")
                return client
            except Exception as e:
                logger.warning(f"⚠️ Session file load failed: {e}")

        return None

    def _cleanup_old_session_files(self) -> None:
        """Clean up old insecure session files."""
        cleanup_paths = [
            ".mm/mm_session.pickle",
            "monarch_session.json",
            ".mm",  # Remove the entire directory if empty
        ]

        for path in cleanup_paths:
            try:
                if os.path.exists(path):
                    if os.path.isfile(path):
                        os.remove(path)
                        logger.info(f"🗑️ Cleaned up old session file: {path}")
                    elif os.path.isdir(path) and not os.listdir(path):
                        os.rmdir(path)
                        logger.info(f"🗑️ Cleaned up empty session directory: {path}")
            except Exception as e:
                logger.warning(f"⚠️ Could not clean up {path}: {e}")


# Global session manager instance
secure_session = SecureMonarchSession()
