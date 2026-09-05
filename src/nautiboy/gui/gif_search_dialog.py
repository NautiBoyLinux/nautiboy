"""Provider-neutral optional online GIF search dialog."""

from __future__ import annotations

import uuid
from html import escape

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QThread, Qt, Signal, Slot
from PySide6.QtGui import QMovie, QPixmap
from PySide6.QtWidgets import (
    QDialog, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)

from nautiboy.network.worker import NetworkWorker
from nautiboy.providers.base import GifProvider, GifResult, SearchPage, SelectedGif


class GifSearchDialog(QDialog):
    media_selected = Signal(object)
    network_get = Signal(str, str, str)
    cancel_network = Signal()

    def __init__(self, provider: GifProvider, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.provider = provider
        self.setWindowTitle("GIF Search")
        self.resize(720, 590)
        self._page: str | None = None
        self._query = ""
        self._results: list[GifResult] = []
        self._requests: dict[str, tuple[str, object]] = {}
        self._movies: list[tuple[QBuffer, QMovie]] = []
        self._selected: GifResult | None = None
        self._build_ui()
        self._thread = QThread(self)
        self._network = NetworkWorker()
        self._network.moveToThread(self._thread)
        self._thread.finished.connect(self._network.deleteLater)
        self.network_get.connect(self._network.get)
        self.cancel_network.connect(self._network.cancel_all)
        self._network.completed.connect(self._completed)
        self._network.failed.connect(self._failed)
        self._thread.start()
        if not provider.available:
            self._show_unconfigured()
        else:
            self._request_page(trending=True)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        search_row = QHBoxLayout()
        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Search GIFs")
        self.search_button = QPushButton("Search")
        search_row.addWidget(self.search_field)
        search_row.addWidget(self.search_button)
        layout.addLayout(search_row)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setOpenExternalLinks(True)
        layout.addWidget(self.status)
        self.selected_details = QLabel("No GIF selected.")
        self.selected_details.setObjectName("selectedGifDetails")
        self.selected_details.setWordWrap(True)
        self.selected_details.setOpenExternalLinks(True)
        layout.addWidget(self.selected_details)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.grid_host = QWidget()
        self.grid = QGridLayout(self.grid_host)
        self.scroll.setWidget(self.grid_host)
        layout.addWidget(self.scroll)
        self.attribution = QLabel(self.provider.attribution)
        self.attribution.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.attribution)
        buttons = QHBoxLayout()
        self.load_more = QPushButton("Load More")
        self.use_button = QPushButton("Use GIF")
        self.use_button.setEnabled(False)
        cancel = QPushButton("Cancel")
        buttons.addWidget(self.load_more)
        buttons.addStretch()
        buttons.addWidget(cancel)
        buttons.addWidget(self.use_button)
        layout.addLayout(buttons)
        self.search_button.clicked.connect(self._search)
        self.search_field.returnPressed.connect(self._search)
        self.load_more.clicked.connect(self._more)
        self.use_button.clicked.connect(self._use)
        cancel.clicked.connect(self.reject)

    def _show_unconfigured(self) -> None:
        reason = getattr(self.provider, "credential_error", None)
        prefix = "Online GIF search is not configured."
        if reason:
            prefix += f" Secret storage is unavailable: {reason}."
        self.status.setText(f"{prefix} Local JPEG, PNG, and GIF selection remains fully available.")
        self.search_field.setEnabled(False)
        self.search_button.setEnabled(False)
        self.load_more.setEnabled(False)

    @Slot()
    def _search(self) -> None:
        query = self.search_field.text().strip()
        if not query:
            return
        self._query = query
        self._page = None
        self._clear_results()
        self._request_page(trending=False)

    @Slot()
    def _more(self) -> None:
        if self._page is not None:
            self._request_page(trending=not bool(self._query))

    def _request_page(self, *, trending: bool) -> None:
        try:
            url = self.provider.trending_url(self._page) if trending else self.provider.search_url(self._query, self._page)
        except (RuntimeError, ValueError) as error:
            self.status.setText(str(error))
            return
        request_id = uuid.uuid4().hex
        self._requests[request_id] = ("page", None)
        self.status.setText("Loading…")
        self.search_button.setEnabled(False)
        self.network_get.emit(request_id, url, "json")

    def _clear_results(self) -> None:
        self._results.clear()
        self._selected = None
        self.use_button.setEnabled(False)
        self.selected_details.setText("No GIF selected.")
        self._movies.clear()
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()

    def _show_page(self, page: SearchPage) -> None:
        start = len(self._results)
        self._results.extend(page.results)
        self._page = page.next_page
        self.load_more.setEnabled(self._page is not None)
        self.status.setText("No GIFs found." if not self._results else "Select a GIF to continue.")
        for position, result in enumerate(page.results, start=start):
            card = QPushButton()
            card.setToolTip(result.title or "GIF")
            card.setAccessibleName(result.title or "GIF")
            card.setCheckable(True)
            card.setFixedSize(150, 150)
            card.clicked.connect(lambda _checked=False, value=result: self._select(value))
            self.grid.addWidget(card, position // 4, position % 4)
            request_id = uuid.uuid4().hex
            self._requests[request_id] = ("preview", card)
            self.network_get.emit(request_id, result.preview_url, "gif")

    def _select(self, result: GifResult) -> None:
        self._selected = result
        creator = f" by {escape(result.creator)}" if result.creator else ""
        source = (
            f' — <a href="{escape(result.source_url, quote=True)}">View source</a>'
            if result.source_url
            else ""
        )
        self.selected_details.setText(
            f"{escape(result.title)}{creator} — {escape(self.provider.attribution)}{source}"
        )
        self.status.setText("Selected GIF ready to use.")
        self.use_button.setEnabled(True)

    @Slot()
    def _use(self) -> None:
        if self._selected is None:
            return
        request_id = uuid.uuid4().hex
        self._requests[request_id] = ("original", self._selected)
        self.status.setText("Downloading selected GIF…")
        self.use_button.setEnabled(False)
        self.network_get.emit(request_id, self._selected.original_url, "gif")

    @Slot(str, bytes, str)
    def _completed(self, request_id: str, data: bytes, _url: str) -> None:
        context = self._requests.pop(request_id, None)
        if context is None:
            return
        kind, value = context
        if kind == "page":
            self.search_button.setEnabled(True)
            try:
                self._show_page(self.provider.parse_page(data))
            except ValueError as error:
                self.status.setText(str(error))
        elif kind == "preview" and isinstance(value, QPushButton):
            byte_array = QByteArray(data)
            buffer = QBuffer()
            buffer.setData(byte_array)
            buffer.open(QIODevice.OpenModeFlag.ReadOnly)
            movie = QMovie(buffer, b"GIF", value)
            movie.setScaledSize(value.size())
            value.setIconSize(value.size())
            movie.frameChanged.connect(lambda _frame, button=value, animation=movie: button.setIcon(QPixmap.fromImage(animation.currentImage())))
            movie.start()
            self._movies.append((buffer, movie))
        elif kind == "original" and isinstance(value, GifResult):
            self.media_selected.emit(SelectedGif(data, value, self.provider.attribution))
            self.accept()

    @Slot(str, str)
    def _failed(self, request_id: str, message: str) -> None:
        self._requests.pop(request_id, None)
        self.search_button.setEnabled(self.provider.available)
        self.status.setText(f"Online GIF request failed: {message}")

    def shutdown(self) -> None:
        self.cancel_network.emit()
        self._thread.quit()
        self._thread.wait(2000)

    def done(self, result: int) -> None:
        self.shutdown()
        super().done(result)
