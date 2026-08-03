# status_panel.py
"""Live PASS/FAIL checklist shown beside the Program Device form.

Replaces the static instruction text with the actual provisioning milestones,
each flipping green PASS or red FAIL as the device script reports it. The row
currently running shows an elapsed timer next to its estimate.

Steps come from `devices/{device}/checklist.json`; a device without that file
gets an empty panel and keeps its old behaviour.
"""

import json
import os

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

GREEN = "#4CAF50"
RED = "#D32F2F"
GREY = "#888888"

ICON_PENDING = "○"   # hollow circle
ICON_RUNNING = "→"   # arrow
ICON_PASS = "✔"      # check
ICON_FAIL = "✖"      # cross
ICON_WAIT = "○"

# state -> (icon, icon colour, default status text, status colour)
STATES = {
    "PENDING": (ICON_PENDING, GREY, "", GREY),
    "RUNNING": (ICON_RUNNING, GREEN, "", GREEN),
    "PASS": (ICON_PASS, GREEN, "PASS", GREEN),
    "SENT": (ICON_RUNNING, GREEN, "SENT", GREEN),
    "WAIT": (ICON_WAIT, GREY, "", GREY),
    "FAIL": (ICON_FAIL, RED, "FAIL", RED),
}


def load_checklist(device_dir):
    """Read checklist.json from a device folder. Returns (steps, image_path)."""
    path = os.path.join(device_dir, "checklist.json")
    if not os.path.isfile(path):
        return [], None

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Could not read {path}: {exc}")
        return [], None

    steps = data.get("steps", [])
    image = data.get("device_image")
    image_path = os.path.join(device_dir, image) if image else None
    if image_path and not os.path.isfile(image_path):
        image_path = None
    return steps, image_path


class StepRow(QWidget):
    """One checklist line: [icon]  label (estimate) ............  STATUS"""

    def __init__(self, step_id, label, estimate="", parent=None):
        super().__init__(parent)
        self.step_id = step_id
        self.base_label = label
        self.estimate = estimate
        self.state = "PENDING"
        self.note = ""

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 3, 4, 3)
        layout.setSpacing(8)

        self.icon = QLabel(ICON_PENDING)
        self.icon.setFixedWidth(18)
        self.icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.text = QLabel(label)
        self.text.setWordWrap(True)
        self.text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self.status = QLabel("")
        self.status.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.status.setMinimumWidth(52)

        layout.addWidget(self.icon)
        layout.addWidget(self.text, 1)
        layout.addWidget(self.status)

        self.set_state("PENDING")

    def set_state(self, state, detail=""):
        state = state.upper()
        if state not in STATES:
            state = "PENDING"
        self.state = state
        if state in ("PENDING", "PASS"):
            self.note = ""
        icon, icon_color, status_text, status_color = STATES[state]

        self.icon.setText(icon)
        self.icon.setStyleSheet(f"color: {icon_color}; font-size: 14px; font-weight: bold;")

        if state == "FAIL" and detail:
            self.note = detail

        self._render_text()
        self.set_status_text(status_text, status_color)

    def set_note(self, note):
        """A progress note inside a running step (e.g. the reboot wait)."""
        self.note = note or ""
        self._render_text()

    def set_status_text(self, text, color=None):
        if color is None:
            color = STATES.get(self.state, STATES["PENDING"])[3]
        self.status.setText(text)
        self.status.setStyleSheet(f"color: {color}; font-weight: bold;")

    def _render_text(self):
        body = self.base_label
        if self.estimate:
            body = f"{body}  ({self.estimate})"
        if self.note:
            body = f"{body}\n{self.note}"
        self.text.setText(body)
        self.text.setStyleSheet(
            f"color: {GREY};" if self.state == "PENDING" else "color: #0B0000;"
        )


class StatusPanel(QWidget):
    """The right-hand Status column: header, device image, checklist rows."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows = {}
        self._order = []
        self._running_id = None
        self._elapsed = 0

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(10)

        header = QLabel("Status")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet(
            f"background: {GREEN}; color: white; font-weight: bold; padding: 5px;"
        )
        outer.addWidget(header)

        self.image = QLabel()
        self.image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image.hide()
        outer.addWidget(self.image)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)

        self.container = QWidget()
        self.rows_layout = QVBoxLayout(self.container)
        self.rows_layout.setContentsMargins(4, 4, 4, 4)
        self.rows_layout.setSpacing(0)
        self.scroll.setWidget(self.container)
        outer.addWidget(self.scroll, 1)

        self.placeholder = QLabel("No automated checklist for this device.")
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder.setWordWrap(True)
        self.placeholder.setStyleSheet(f"color: {GREY};")
        self.rows_layout.addWidget(self.placeholder)
        self.rows_layout.addStretch()

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)

    # -- building -----------------------------------------------------------

    def set_steps(self, steps, image_path=None):
        """Replace the checklist rows. `steps` is a list of dicts from JSON."""
        self._timer.stop()
        self._running_id = None
        self._rows = {}
        self._order = []

        while self.rows_layout.count():
            item = self.rows_layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        if image_path:
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                self.image.setPixmap(
                    pixmap.scaledToWidth(220, Qt.TransformationMode.SmoothTransformation)
                )
                self.image.show()
            else:
                self.image.hide()
        else:
            self.image.clear()
            self.image.hide()

        if not steps:
            self.placeholder = QLabel("No automated checklist for this device.")
            self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.placeholder.setWordWrap(True)
            self.placeholder.setStyleSheet(f"color: {GREY};")
            self.rows_layout.addWidget(self.placeholder)
            self.rows_layout.addStretch()
            return

        for step in steps:
            step_id = str(step.get("id", ""))
            if not step_id:
                continue
            row = StepRow(step_id, step.get("label", step_id), step.get("estimate", ""))
            self.rows_layout.addWidget(row)
            self._rows[step_id] = row
            self._order.append(step_id)

        self.rows_layout.addStretch()

    def reset(self):
        """Return every row to pending, e.g. when a new run starts."""
        self._timer.stop()
        self._running_id = None
        self._elapsed = 0
        for row in self._rows.values():
            row.set_state("PENDING")

    # -- updating -----------------------------------------------------------

    def update_step(self, step_id, state, detail=""):
        row = self._rows.get(step_id)
        if row is None:
            return

        state = (state or "").upper()

        if state == "RUNNING":
            self._running_id = step_id
            self._elapsed = 0
            row.set_state("RUNNING")
            row.set_status_text("0:00")
            self._timer.start()
            self.scroll.ensureWidgetVisible(row)
            return

        if state in ("PASS", "FAIL"):
            if self._running_id == step_id:
                self._timer.stop()
                self._running_id = None
            row.set_state(state, detail)
            return

        if state == "SENT":
            # Momentary acknowledgement; the elapsed timer takes the column back.
            row.set_status_text("SENT", GREEN)
            return

        if state == "WAIT":
            # Keeps ticking; the wait wording lands under the label.
            row.set_note(detail)
            return

    def fail_running(self, detail=""):
        """Mark whatever was in flight as failed (used when the run crashes)."""
        self._timer.stop()
        target = self._running_id
        if target is None:
            for step_id in self._order:
                if self._rows[step_id].state == "RUNNING":
                    target = step_id
                    break
        if target is not None:
            self._rows[target].set_state("FAIL", detail)
        self._running_id = None

    def _tick(self):
        if self._running_id is None:
            self._timer.stop()
            return
        self._elapsed += 1
        row = self._rows.get(self._running_id)
        if row is None:
            self._timer.stop()
            return
        minutes, seconds = divmod(self._elapsed, 60)
        row.set_status_text(f"{minutes}:{seconds:02d}")
