"""Qt Network worker intended to live entirely outside the GUI thread."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

SEARCH_MAX_BYTES = 2 * 1024 * 1024
MEDIA_MAX_BYTES = 25 * 1024 * 1024
SEARCH_TIMEOUT_MS = 10_000
MEDIA_TIMEOUT_MS = 20_000


class NetworkValidationError(ValueError):
    pass


def validate_response(status: int | None, mime: str, data: bytes, *, kind: str) -> None:
    if status is None or not 200 <= status < 300:
        raise NetworkValidationError(f"HTTP request failed ({status or 'unknown status'})")
    expected, maximum = (("application/json",), SEARCH_MAX_BYTES) if kind == "json" else (("image/gif",), MEDIA_MAX_BYTES)
    normalized = mime.split(";", 1)[0].strip().lower()
    if normalized not in expected:
        raise NetworkValidationError(f"unexpected content type: {normalized or 'missing'}")
    if len(data) > maximum:
        raise NetworkValidationError("download exceeds size limit")


@dataclass(slots=True)
class _Transfer:
    reply: QNetworkReply
    data: bytearray
    maximum: int
    expected_mimes: tuple[str, ...]
    timer: QTimer


class NetworkWorker(QObject):
    completed = Signal(str, bytes, str)
    failed = Signal(str, str)

    def __init__(self) -> None:
        super().__init__()
        self._manager: QNetworkAccessManager | None = None
        self._transfers: dict[str, _Transfer] = {}

    def _network(self) -> QNetworkAccessManager:
        if self._manager is None:
            self._manager = QNetworkAccessManager(self)
        return self._manager

    @Slot(str, str, str)
    def get(self, request_id: str, url: str, kind: str) -> None:
        if request_id in self._transfers:
            self.failed.emit(request_id, "duplicate network request")
            return
        parsed = QUrl(url)
        if not parsed.isValid() or parsed.scheme().lower() != "https":
            self.failed.emit(request_id, "only valid HTTPS URLs are allowed")
            return
        if kind == "json":
            maximum, timeout, mimes = SEARCH_MAX_BYTES, SEARCH_TIMEOUT_MS, ("application/json",)
        elif kind == "gif":
            maximum, timeout, mimes = MEDIA_MAX_BYTES, MEDIA_TIMEOUT_MS, ("image/gif",)
        else:
            self.failed.emit(request_id, "unsupported download type")
            return
        request = QNetworkRequest(parsed)
        request.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute, QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy)
        reply = self._network().get(request)
        timer = QTimer(self)
        timer.setSingleShot(True)
        transfer = _Transfer(reply, bytearray(), maximum, mimes, timer)
        self._transfers[request_id] = transfer
        reply.readyRead.connect(lambda rid=request_id: self._read(rid))
        reply.finished.connect(lambda rid=request_id: self._finish(rid))
        timer.timeout.connect(lambda rid=request_id: self._timeout(rid))
        timer.start(timeout)

    def _read(self, request_id: str) -> None:
        transfer = self._transfers.get(request_id)
        if transfer is None:
            return
        transfer.data.extend(bytes(transfer.reply.readAll()))
        if len(transfer.data) > transfer.maximum:
            transfer.reply.abort()
            self._fail(request_id, "download exceeds size limit")

    def _finish(self, request_id: str) -> None:
        transfer = self._transfers.get(request_id)
        if transfer is None:
            return
        self._read(request_id)
        transfer = self._transfers.get(request_id)
        if transfer is None:
            return
        status = transfer.reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        if transfer.reply.error() != QNetworkReply.NetworkError.NoError:
            self._fail(request_id, transfer.reply.errorString())
            return
        mime = str(transfer.reply.header(QNetworkRequest.KnownHeaders.ContentTypeHeader) or "").split(";", 1)[0].lower()
        data = bytes(transfer.data)
        try:
            validate_response(status if isinstance(status, int) else None, mime, data, kind="json" if transfer.maximum == SEARCH_MAX_BYTES else "gif")
        except NetworkValidationError as error:
            self._fail(request_id, str(error))
            return
        final_url = transfer.reply.url().toString()
        self._remove(request_id)
        self.completed.emit(request_id, data, final_url)

    def _timeout(self, request_id: str) -> None:
        transfer = self._transfers.get(request_id)
        if transfer is not None:
            transfer.reply.abort()
            self._fail(request_id, "network request timed out")

    def _fail(self, request_id: str, message: str) -> None:
        if request_id not in self._transfers:
            return
        self._remove(request_id)
        self.failed.emit(request_id, message)

    def _remove(self, request_id: str) -> None:
        transfer = self._transfers.pop(request_id, None)
        if transfer is not None:
            transfer.timer.stop()
            transfer.timer.deleteLater()
            transfer.reply.deleteLater()

    @Slot()
    def cancel_all(self) -> None:
        for request_id in tuple(self._transfers):
            transfer = self._transfers.get(request_id)
            if transfer is not None:
                transfer.reply.abort()
                self._remove(request_id)
