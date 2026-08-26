"""CMhelper PC Agent - API Client

Provides UI-independent HTTP client functionality for the Windows PC Agent.
Retains JWT access tokens exclusively in instance/process memory.
Never persists credentials or tokens to disk, registry, or environment variables.
Never exposes credentials, tokens, or raw customer data in error messages or logs.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
import requests


class AgentApiError(Exception):
    """Base exception for Agent API errors."""
    pass


class AuthenticationError(AgentApiError):
    """Raised when authentication fails, credentials are rejected, or tokens expire (401/403)."""
    pass


class AgentApiClient:
    """Client for authenticated communication with the CMhelper backend API."""

    def __init__(
        self,
        base_url: str = "https://cmhelper-v1.vercel.app/api",
        session: Optional[requests.Session] = None,
    ) -> None:
        self.base_url: str = base_url.rstrip("/")
        self._access_token: Optional[str] = None
        self.session: requests.Session = session or requests.Session()

    def is_authenticated(self) -> bool:
        """Return True if an access token is held in process memory."""
        return bool(self._access_token)

    def clear_auth(self) -> None:
        """Clear the in-memory access token (fail-closed reset)."""
        self._access_token = None

    def login(self, email: str, password: str) -> bool:
        """Authenticate against POST /api/auth/login and retain the token in memory.

        Raises AuthenticationError on 401/403 or invalid credentials.
        Never logs or stores the submitted password.
        """
        clean_email = (email or "").strip().lower()
        if not clean_email or not password:
            raise AuthenticationError("Email and password are required")

        url = f"{self.base_url}/auth/login"
        payload = {"email": clean_email, "password": password}

        try:
            res = self.session.post(url, json=payload, timeout=15)
        except Exception as exc:
            self.clear_auth()
            raise AgentApiError(f"Network error during login: {type(exc).__name__}") from exc

        if res.status_code == 200:
            try:
                data = res.json()
                token = data.get("access_token")
                if not token or not isinstance(token, str):
                    self.clear_auth()
                    raise AuthenticationError("Server response did not contain a valid access token")
                self._access_token = token
                return True
            except Exception as exc:
                self.clear_auth()
                if isinstance(exc, AuthenticationError):
                    raise
                raise AgentApiError("Failed to parse login response") from exc

        self.clear_auth()
        if res.status_code in (401, 403):
            raise AuthenticationError(f"Login rejected: HTTP {res.status_code}")
        raise AgentApiError(f"Login failed: HTTP {res.status_code}")

    def _get_auth_headers(self) -> Dict[str, str]:
        """Return authorization headers with Bearer token, or raise AuthenticationError."""
        if not self._access_token:
            raise AuthenticationError("Not authenticated: Access token is missing")
        return {"Authorization": f"Bearer {self._access_token}"}

    def get_pending_messages(self) -> List[Dict[str, Any]]:
        """Fetch pending message tasks via GET /api/messages/pending.

        Server determines tenant and user scope based on the Bearer token.
        """
        headers = self._get_auth_headers()
        url = f"{self.base_url}/messages/pending"

        try:
            res = self.session.get(url, headers=headers, timeout=15)
        except Exception as exc:
            raise AgentApiError(f"Network error while fetching pending messages: {type(exc).__name__}") from exc

        if res.status_code == 200:
            try:
                data = res.json()
                if isinstance(data, list):
                    return data
                raise AgentApiError("Invalid pending messages payload format")
            except Exception as exc:
                if isinstance(exc, AgentApiError):
                    raise
                raise AgentApiError("Failed to parse pending messages response") from exc

        if res.status_code in (401, 403):
            self.clear_auth()
            raise AuthenticationError(f"Authentication invalid while fetching messages: HTTP {res.status_code}")

        raise AgentApiError(f"Failed to fetch pending messages: HTTP {res.status_code}")

    def update_message_status(self, task_id: int, status: str) -> Dict[str, Any]:
        """Update task status via PUT /api/messages/{task_id}/status.

        Server validates ownership and authorization.
        """
        headers = self._get_auth_headers()
        url = f"{self.base_url}/messages/{task_id}/status"

        try:
            res = self.session.put(url, json={"status": status}, headers=headers, timeout=15)
        except Exception as exc:
            raise AgentApiError(f"Network error while updating message status: {type(exc).__name__}") from exc

        if res.status_code == 200:
            try:
                return res.json()
            except Exception as exc:
                raise AgentApiError("Failed to parse status update response") from exc

        if res.status_code in (401, 403):
            self.clear_auth()
            raise AuthenticationError(f"Authentication invalid while updating status: HTTP {res.status_code}")

        raise AgentApiError(f"Failed to update message status: HTTP {res.status_code}")

    def cancel_pending_messages(self) -> Dict[str, Any]:
        """Cancel all pending tasks via DELETE /api/messages/pending."""
        headers = self._get_auth_headers()
        url = f"{self.base_url}/messages/pending"

        try:
            res = self.session.delete(url, headers=headers, timeout=15)
        except Exception as exc:
            raise AgentApiError(f"Network error while canceling pending messages: {type(exc).__name__}") from exc

        if res.status_code == 200:
            try:
                return res.json()
            except Exception as exc:
                raise AgentApiError("Failed to parse cancel response") from exc

        if res.status_code in (401, 403):
            self.clear_auth()
            raise AuthenticationError(f"Authentication invalid while canceling messages: HTTP {res.status_code}")

        raise AgentApiError(f"Failed to cancel pending messages: HTTP {res.status_code}")

    def download_image(self, image_url: str) -> bytes:
        """Download estimate image bytes from the given URL."""
        try:
            res = self.session.get(image_url, timeout=15)
        except Exception as exc:
            raise AgentApiError(f"Network error while downloading image: {type(exc).__name__}") from exc

        if res.status_code == 200:
            return res.content

        raise AgentApiError(f"Failed to download image: HTTP {res.status_code}")

    def __repr__(self) -> str:
        return f"<AgentApiClient base_url='{self.base_url}' authenticated={self.is_authenticated()}>"

    def __str__(self) -> str:
        return self.__repr__()
