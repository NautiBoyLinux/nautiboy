"""Secure per-user credentials backed by the desktop's system keyring."""

from __future__ import annotations

import os
from typing import Protocol

SERVICE_NAME = "io.github.nautiboy.nautiboy"
GIPHY_ACCOUNT = "giphy-api-key"
GIPHY_ENVIRONMENT_VARIABLE = "NAUTIBOY_GIPHY_API_KEY"


class CredentialError(RuntimeError):
    """A safe, non-secret-bearing credential storage failure."""


class KeyringBackend(Protocol):
    def get_password(self, service: str, username: str) -> str | None: ...
    def set_password(self, service: str, username: str, password: str) -> None: ...
    def delete_password(self, service: str, username: str) -> None: ...


def _system_keyring() -> KeyringBackend:
    try:
        import keyring
    except ImportError as error:
        raise CredentialError("desktop secret storage support is unavailable") from error
    return keyring


class GiphyCredentialStore:
    def __init__(self, backend: KeyringBackend | None = None) -> None:
        self._backend = backend

    @property
    def backend(self) -> KeyringBackend:
        return self._backend or _system_keyring()

    def retrieve(self) -> str | None:
        try:
            value = self.backend.get_password(SERVICE_NAME, GIPHY_ACCOUNT)
        except Exception as error:
            raise CredentialError("could not access desktop secret storage") from error
        return value.strip() if value and value.strip() else None

    def save(self, value: str) -> None:
        value = value.strip()
        if not value:
            raise CredentialError("enter a GIPHY API key before saving")
        try:
            self.backend.set_password(SERVICE_NAME, GIPHY_ACCOUNT, value)
        except Exception as error:
            raise CredentialError("could not save to desktop secret storage") from error

    def delete(self) -> None:
        try:
            self.backend.delete_password(SERVICE_NAME, GIPHY_ACCOUNT)
        except Exception as error:
            # keyring backends use backend-specific exceptions for a missing item.
            if error.__class__.__name__ != "PasswordDeleteError":
                raise CredentialError("could not remove the stored GIPHY API key") from error

    def configured(self) -> bool:
        return self.retrieve() is not None


def resolve_giphy_api_key(store: GiphyCredentialStore | None = None) -> str | None:
    environment_value = os.environ.get(GIPHY_ENVIRONMENT_VARIABLE, "").strip()
    if environment_value:
        return environment_value
    return (store or GiphyCredentialStore()).retrieve()
