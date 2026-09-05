"""Per-user Qt local-socket single-instance activation."""

from __future__ import annotations

import os

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from .branding import APP_ID, LEGACY_APP_IDS

ACTIVATE_MESSAGE = b"activate\n"
BACKGROUND_MESSAGE = b"background\n"


def instance_name(app_id: str = APP_ID) -> str:
    return f"{app_id}-{os.getuid()}"


class SingleInstance(QObject):
    activated = Signal()

    def __init__(self, name: str | None = None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.name = name or instance_name()
        self.legacy_names = () if name else tuple(instance_name(app_id) for app_id in LEGACY_APP_IDS)
        self._server: QLocalServer | None = None

    def _notify_existing(
        self, *, activate: bool, timeout_ms: int = 300, name: str | None = None
    ) -> bool:
        socket = QLocalSocket(self)
        if hasattr(QLocalSocket.SocketOption, "AbstractNamespaceOption"):
            socket.setSocketOptions(QLocalSocket.SocketOption.AbstractNamespaceOption)
        socket.connectToServer(name or self.name)
        if not socket.waitForConnected(timeout_ms):
            socket.abort()
            return False
        socket.write(ACTIVATE_MESSAGE if activate else BACKGROUND_MESSAGE)
        socket.flush()
        socket.waitForBytesWritten(timeout_ms)
        socket.disconnectFromServer()
        return True

    def acquire(self, *, activate_existing: bool = True) -> bool:
        """Return True only for the process that owns the activation socket."""
        for legacy_name in self.legacy_names:
            if self._notify_existing(activate=activate_existing, name=legacy_name):
                return False
        if self._notify_existing(activate=activate_existing):
            return False
        # A crashed process can leave a filesystem socket. Only remove it after
        # proving that no server accepts a connection.
        QLocalServer.removeServer(self.name)
        server = QLocalServer(self)
        if hasattr(QLocalServer.SocketOption, "AbstractNamespaceOption"):
            # Linux abstract sockets do not leave stale filesystem entries and
            # remain scoped by the UID embedded in the server name.
            server.setSocketOptions(QLocalServer.SocketOption.AbstractNamespaceOption)
        if not server.listen(self.name):
            # Handle a simultaneous-launch race: the winner may now be listening.
            if self._notify_existing(activate=activate_existing):
                return False
            raise RuntimeError(f"cannot establish single-instance socket: {server.errorString()}")
        self._server = server
        server.newConnection.connect(self._receive)
        return True

    def _receive(self) -> None:
        if self._server is None:
            return
        while self._server.hasPendingConnections():
            socket = self._server.nextPendingConnection()
            if socket is None:
                continue
            socket.readyRead.connect(lambda current=socket: self._read_activation(current))
            socket.disconnected.connect(socket.deleteLater)
            if socket.bytesAvailable():
                self._read_activation(socket)

    def _read_activation(self, socket: QLocalSocket) -> None:
        if bytes(socket.readAll()).startswith(ACTIVATE_MESSAGE.rstrip()):
            self.activated.emit()
        socket.disconnectFromServer()

    def close(self) -> None:
        if self._server is not None:
            self._server.close()
            self._server = None
        QLocalServer.removeServer(self.name)
