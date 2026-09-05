"""Secure per-user credentials backed by the desktop's system keyring."""

from __future__ import annotations

import os
from typing import Protocol

from .branding import APP_ID, LEGACY_APP_IDS

SERVICE_NAME = APP_ID
LEGACY_SERVICE_NAMES = LEGACY_APP_IDS
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
        if value and value.strip():
            return value.strip()

        # Development builds used the provisional application ID as their
        # Secret Service name. Move that item entirely within the keyring.
        for legacy_service in LEGACY_SERVICE_NAMES:
            try:
                legacy_value = self.backend.get_password(legacy_service, GIPHY_ACCOUNT)
            except Exception as error:
                raise CredentialError("could not access desktop secret storage") from error
            if not legacy_value or not legacy_value.strip():
                continue
            migrated_value = legacy_value.strip()
            try:
                self.backend.set_password(SERVICE_NAME, GIPHY_ACCOUNT, migrated_value)
                self._delete_from_service(legacy_service)
            except Exception as error:
                raise CredentialError("could not migrate the stored GIPHY API key") from error
            return migrated_value
        return None

    def save(self, value: str) -> None:
        value = value.strip()
        if not value:
            raise CredentialError("enter a GIPHY API key before saving")
        try:
            self.backend.set_password(SERVICE_NAME, GIPHY_ACCOUNT, value)
            for legacy_service in LEGACY_SERVICE_NAMES:
                self._delete_from_service(legacy_service)
        except Exception as error:
            raise CredentialError("could not save to desktop secret storage") from error

    def delete(self) -> None:
        try:
            self._delete_from_service(SERVICE_NAME)
            for legacy_service in LEGACY_SERVICE_NAMES:
                self._delete_from_service(legacy_service)
        except Exception as error:
            raise CredentialError("could not remove the stored GIPHY API key") from error

    def _delete_from_service(self, service: str) -> None:
        try:
            self.backend.delete_password(service, GIPHY_ACCOUNT)
        except Exception as error:
            if error.__class__.__name__ != "PasswordDeleteError":
                raise

    def configured(self) -> bool:
        return self.retrieve() is not None


def resolve_giphy_api_key(store: GiphyCredentialStore | None = None) -> str | None:
    environment_value = os.environ.get(GIPHY_ENVIRONMENT_VARIABLE, "").strip()
    if environment_value:
        return environment_value
    return (store or GiphyCredentialStore()).retrieve()
