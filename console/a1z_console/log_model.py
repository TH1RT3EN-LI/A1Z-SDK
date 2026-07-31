"""Incremental bounded log model for the QML diagnostics view."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
import unicodedata

from PySide6.QtCore import (
    Property,
    QAbstractListModel,
    QModelIndex,
    QObject,
    Qt,
    Signal,
)


class ConsoleLogModel(QAbstractListModel):
    """Keep recent console lines without rebuilding one large text document."""

    LineRole = Qt.UserRole + 1
    maximumLineLengthChanged = Signal()
    maximumDisplayColumnsChanged = Signal()

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        maximum_lines: int = 1000,
    ) -> None:
        super().__init__(parent)
        self._maximum_lines = max(1, int(maximum_lines))
        self._lines: list[str] = []
        self._line_lengths: list[int] = []
        self._line_columns: list[int] = []
        self._length_counts: Counter[int] = Counter()
        self._column_counts: Counter[int] = Counter()
        self._maximum_line_length = 0
        self._maximum_display_columns = 0

    @Property(int, notify=maximumLineLengthChanged)
    def maximumLineLength(self) -> int:
        return self._maximum_line_length

    @Property(int, notify=maximumDisplayColumnsChanged)
    def maximumDisplayColumns(self) -> int:
        return self._maximum_display_columns

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._lines)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> object:
        if not index.isValid() or not 0 <= index.row() < len(self._lines):
            return None
        if role in {Qt.DisplayRole, self.LineRole}:
            return self._lines[index.row()]
        return None

    def roleNames(self) -> dict[int, bytes]:
        return {self.LineRole: b"line"}

    def append_lines(self, lines: Iterable[str]) -> None:
        additions = [str(line) for line in lines]
        if not additions:
            return
        previous_maximum = self._maximum_line_length
        previous_columns = self._maximum_display_columns
        if len(additions) >= self._maximum_lines:
            additions = additions[-self._maximum_lines :]
            addition_lengths = [len(line) for line in additions]
            addition_columns = [self._display_columns(line) for line in additions]
            self.beginResetModel()
            self._lines = additions
            self._line_lengths = addition_lengths
            self._line_columns = addition_columns
            self._length_counts = Counter(addition_lengths)
            self._column_counts = Counter(addition_columns)
            self.endResetModel()
            self._publish_maximum_metrics(previous_maximum, previous_columns)
            return

        addition_lengths = [len(line) for line in additions]
        addition_columns = [self._display_columns(line) for line in additions]

        overflow = max(
            0,
            len(self._lines) + len(additions) - self._maximum_lines,
        )
        if overflow:
            self.beginRemoveRows(QModelIndex(), 0, overflow - 1)
            removed_lengths = self._line_lengths[:overflow]
            removed_columns = self._line_columns[:overflow]
            del self._lines[:overflow]
            del self._line_lengths[:overflow]
            del self._line_columns[:overflow]
            self._remove_metric_counts(self._length_counts, removed_lengths)
            self._remove_metric_counts(self._column_counts, removed_columns)
            self.endRemoveRows()

        first = len(self._lines)
        last = first + len(additions) - 1
        self.beginInsertRows(QModelIndex(), first, last)
        self._lines.extend(additions)
        self._line_lengths.extend(addition_lengths)
        self._line_columns.extend(addition_columns)
        self._length_counts.update(addition_lengths)
        self._column_counts.update(addition_columns)
        self.endInsertRows()
        self._publish_maximum_metrics(previous_maximum, previous_columns)

    def clear(self) -> None:
        if not self._lines:
            return
        self.beginRemoveRows(QModelIndex(), 0, len(self._lines) - 1)
        self._lines.clear()
        self._line_lengths.clear()
        self._line_columns.clear()
        self._length_counts.clear()
        self._column_counts.clear()
        self.endRemoveRows()
        self._maximum_line_length = 0
        self._maximum_display_columns = 0
        self.maximumLineLengthChanged.emit()
        self.maximumDisplayColumnsChanged.emit()

    def entries(self) -> list[str]:
        """Return a copy for diagnostics and unit tests."""

        return list(self._lines)

    @staticmethod
    def _display_columns(line: str) -> int:
        columns = 0
        for character in line:
            if character == "\t":
                columns += 8 - (columns % 8)
            elif unicodedata.combining(character):
                continue
            elif unicodedata.category(character).startswith("C"):
                continue
            elif unicodedata.east_asian_width(character) in {"W", "F"}:
                columns += 2
            else:
                columns += 1
        return columns

    @staticmethod
    def _remove_metric_counts(
        counts: Counter[int],
        values: Iterable[int],
    ) -> None:
        counts.subtract(values)
        counts += Counter()

    def _publish_maximum_metrics(
        self,
        previous_length: int,
        previous_columns: int,
    ) -> None:
        self._maximum_line_length = max(self._length_counts, default=0)
        self._maximum_display_columns = max(self._column_counts, default=0)
        if self._maximum_line_length != previous_length:
            self.maximumLineLengthChanged.emit()
        if self._maximum_display_columns != previous_columns:
            self.maximumDisplayColumnsChanged.emit()
