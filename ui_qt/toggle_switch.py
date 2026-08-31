"""Rounded pill-shaped toggle switch with a sliding knob, matching the
tkinter build's CTkSwitch look. Drop-in QCheckBox replacement for on/off
toggles (setCheckable/isChecked/setChecked/.toggled all work the same),
but has no built-in text label — pair it with a QLabel."""

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QPropertyAnimation,
    QRectF,
    Qt,
)
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QAbstractButton


class ToggleSwitch(QAbstractButton):
    def __init__(self, palette: dict, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self._palette = {}
        self._knob_position = 0.0  # 0.0 = off (left), 1.0 = on (right)

        self._animation = QPropertyAnimation(self, b"knobPosition", self)
        self._animation.setDuration(150)
        self._animation.setEasingCurve(QEasingCurve.InOutCubic)

        self.setFixedSize(40, 22)
        self.apply_palette(palette)
        self.toggled.connect(self._animate_to_state)

    # ---------- theming ----------

    def apply_palette(self, palette: dict) -> None:
        self._palette = palette
        self.update()

    # ---------- animated knob position (Qt property, driven by QPropertyAnimation) ----------

    def _get_knob_position(self) -> float:
        return self._knob_position

    def _set_knob_position(self, value: float) -> None:
        self._knob_position = value
        self.update()

    knobPosition = Property(float, _get_knob_position, _set_knob_position)

    def _animate_to_state(self, checked: bool) -> None:
        self._animation.stop()
        self._animation.setStartValue(self._knob_position)
        self._animation.setEndValue(1.0 if checked else 0.0)
        self._animation.start()

    def setChecked(self, checked: bool) -> None:
        # Programmatic sync (e.g. loading a saved setting) jumps, no animation.
        super().setChecked(checked)
        self._animation.stop()
        self._knob_position = 1.0 if checked else 0.0
        self.update()

    # ---------- painting ----------

    def sizeHint(self):
        return self.size()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(Qt.NoPen)

        track_on = QColor(self._palette.get("button_bg_color", self._palette.get("accent", "#BB86FC")))
        track_off = QColor(self._palette.get("switch_bg", "#4a4a4a"))
        knob_color = QColor(self._palette.get("button_fg_color", "#ffffff"))

        t = self._knob_position
        track_color = QColor(
            int(track_off.red() + (track_on.red() - track_off.red()) * t),
            int(track_off.green() + (track_on.green() - track_off.green()) * t),
            int(track_off.blue() + (track_on.blue() - track_off.blue()) * t),
        )

        rect = QRectF(self.rect())
        painter.setBrush(track_color)
        painter.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)

        knob_diameter = rect.height() - 4
        knob_x = 2 + t * (rect.width() - knob_diameter - 4)
        painter.setBrush(knob_color)
        painter.drawEllipse(QRectF(knob_x, 2, knob_diameter, knob_diameter))
