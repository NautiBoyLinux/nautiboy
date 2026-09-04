"""Maintainable Qt stylesheet for the NautiBoy dark desktop theme."""

STYLESHEET = """
QWidget {
    color: #eef0ff;
    font-family: "Inter", "Noto Sans", "Open Sans", sans-serif;
    font-size: 14px;
}
QMainWindow, QWidget#centralWidget {
    background-color: #080a13;
}
QFrame#headerFrame, QFrame#contentCard, QFrame#deviceCard, QFrame#detailsCard {
    background-color: #111522;
    border: 1px solid #262c43;
    border-radius: 14px;
}
QLabel#brandTitle {
    color: #f5f3ff;
    font-size: 31px;
    font-weight: 750;
}
QLabel#brandAccent {
    color: #a956ff;
    font-size: 31px;
    font-weight: 750;
}
QLabel#subtitle, QLabel#previewCaption, QLabel#deviceMeta, QLabel#footerLabel {
    color: #939bbd;
}
QLabel#subtitle, QLabel#previewCaption, QLabel#footerLabel {
    font-size: 11px;
    letter-spacing: 2px;
}
QLabel#previewSurface {
    background-color: #06070d;
    border: 1px solid #8d36e8;
    border-radius: 16px;
    color: #7e86a4;
}
QPushButton, QComboBox {
    min-height: 48px;
    padding: 0 18px;
    background-color: #171b2b;
    border: 1px solid #303651;
    border-radius: 12px;
    color: #f2f2fb;
}
QPushButton:hover, QComboBox:hover {
    background-color: #1d2235;
    border-color: #7741a9;
}
QPushButton:pressed {
    background-color: #121625;
}
QPushButton:disabled, QComboBox:disabled {
    color: #626981;
    background-color: #111521;
    border-color: #202538;
}
QPushButton#sendButton {
    min-height: 64px;
    color: white;
    font-size: 16px;
    font-weight: 700;
    background-color: #7427e8;
    border: 1px solid #ad54ff;
    border-radius: 14px;
}
QPushButton#sendButton:hover {
    background-color: #8434f3;
    border-color: #ca7aff;
}
QPushButton#restoreButton {
    min-height: 56px;
}
QPushButton#detailsButton {
    min-height: 30px;
    padding: 0 12px;
    color: #b7bdd5;
    background: transparent;
    border: 1px solid #2a3047;
    border-radius: 9px;
}
QComboBox::drop-down {
    border: none;
    width: 30px;
}
QComboBox QAbstractItemView {
    color: #eef0ff;
    background-color: #171b2b;
    selection-background-color: #7427e8;
    border: 1px solid #303651;
}
QLabel#connectionDot[connected="true"] {
    background-color: #19d790;
    border: 1px solid #35f2ad;
    border-radius: 8px;
}
QLabel#connectionDot[connected="false"] {
    background-color: #e05268;
    border: 1px solid #ff7187;
    border-radius: 8px;
}
QLabel#statusBadge {
    min-width: 92px;
    min-height: 32px;
    padding: 0 10px;
    border-radius: 10px;
    font-size: 12px;
    font-weight: 700;
}
QLabel#statusBadge[state="ready"], QLabel#statusBadge[state="displaying"] {
    color: #35eda9;
    background-color: #0b332b;
    border: 1px solid #137c60;
}
QLabel#statusBadge[state="sending"], QLabel#statusBadge[state="restoring"] {
    color: #d9b2ff;
    background-color: #2b1741;
    border: 1px solid #7942ad;
}
QLabel#statusBadge[state="error"], QLabel#statusBadge[state="disconnected"] {
    color: #ff8495;
    background-color: #3a171e;
    border: 1px solid #86313f;
}
QPlainTextEdit {
    color: #bbc2dc;
    background-color: #090c15;
    border: 1px solid #262c43;
    border-radius: 10px;
    padding: 8px;
    font-family: monospace;
    font-size: 12px;
}
"""
