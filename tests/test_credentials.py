from __future__ import annotations

import pytest

from nautiboy.credentials import (
    GIPHY_ACCOUNT,
    GIPHY_ENVIRONMENT_VARIABLE,
    LEGACY_SERVICE_NAMES,
    SERVICE_NAME,
    CredentialError,
    GiphyCredentialStore,
    resolve_giphy_api_key,
)


class FakeKeyring:
    def __init__(self) -> None:
        self.items: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, username: str) -> str | None:
        return self.items.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self.items[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        self.items.pop((service, username), None)


def test_secure_store_save_retrieve_and_delete() -> None:
    backend = FakeKeyring()
    store = GiphyCredentialStore(backend)
    store.save(" fake-secret ")
    assert backend.items == {(SERVICE_NAME, GIPHY_ACCOUNT): "fake-secret"}
    assert store.retrieve() == "fake-secret"
    store.delete()
    assert store.retrieve() is None


def test_legacy_service_key_is_migrated_only_within_keyring() -> None:
    backend = FakeKeyring()
    legacy_service = LEGACY_SERVICE_NAMES[0]
    backend.items[(legacy_service, GIPHY_ACCOUNT)] = "legacy-fake-secret"
    store = GiphyCredentialStore(backend)

    assert store.retrieve() == "legacy-fake-secret"
    assert backend.items == {(SERVICE_NAME, GIPHY_ACCOUNT): "legacy-fake-secret"}


def test_delete_removes_current_and_legacy_service_keys() -> None:
    backend = FakeKeyring()
    backend.items[(SERVICE_NAME, GIPHY_ACCOUNT)] = "current-fake"
    backend.items[(LEGACY_SERVICE_NAMES[0], GIPHY_ACCOUNT)] = "legacy-fake"
    GiphyCredentialStore(backend).delete()
    assert backend.items == {}


def test_environment_key_overrides_secure_store(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = FakeKeyring()
    store = GiphyCredentialStore(backend)
    store.save("stored-fake")
    monkeypatch.setenv(GIPHY_ENVIRONMENT_VARIABLE, "environment-fake")
    assert resolve_giphy_api_key(store) == "environment-fake"


def test_no_key_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(GIPHY_ENVIRONMENT_VARIABLE, raising=False)
    assert resolve_giphy_api_key(GiphyCredentialStore(FakeKeyring())) is None


def test_backend_failure_is_safe_and_does_not_include_secret() -> None:
    class BrokenKeyring(FakeKeyring):
        def set_password(self, service: str, username: str, password: str) -> None:
            raise RuntimeError(f"backend rejected {password}")

    with pytest.raises(CredentialError) as caught:
        GiphyCredentialStore(BrokenKeyring()).save("never-expose-this")
    assert "never-expose-this" not in str(caught.value)


def test_empty_key_is_rejected() -> None:
    with pytest.raises(CredentialError, match="enter a GIPHY API key"):
        GiphyCredentialStore(FakeKeyring()).save("   ")
