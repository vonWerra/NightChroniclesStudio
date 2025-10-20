"""Log pane widget for displaying subprocess output."""
from __future__ import annotations

from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextEdit


class LogPane(QWidget):
    """Text widget for displaying subprocess stdout/stderr."""

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.view = QTextEdit(self)
        self.view.setReadOnly(True)
        layout.addWidget(self.view)

    def append(self, stream: str, text: str) -> None:
        """Append a line to the log with stream prefix.

        Args:
            stream: "stdout" or "stderr"
            text: Line of text to append
        """
        prefix = "[OUT]" if stream == "stdout" else "[ERR]"
        self.view.append(f"{prefix} {text}")

    def clear(self) -> None:
        """Clear all log content."""
        self.view.clear()
