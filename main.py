import sys
import threading
import time
from pynput import keyboard
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QLabel, QCheckBox, QPushButton)
from PySide6.QtCore import Signal, QObject, Qt
from PySide6.QtGui import QFont

__version__ = "1.0.0"

# The hotkey combination
HOTKEY = '<ctrl>+<alt>+v'

# Typing speed. Raise these if a slow remote console still garbles text.
KEY_HOLD_SECONDS = 0.015  # how long each key stays down
KEY_GAP_SECONDS = 0.015   # pause after each key is released

KEY_FOR_CHAR = {
    '\n': keyboard.Key.enter,
    '\r': keyboard.Key.enter,
    '\t': keyboard.Key.tab,
}

class WorkerSignals(QObject):
    update_status = Signal(str, str) # text, color
    hotkey_triggered = Signal()

class ClipToKeyApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ClipToKey")
        self.setFixedSize(320, 280)
        # Try to make window stay on top
        self.setWindowFlag(Qt.WindowStaysOnTopHint)

        self.listener_active = True
        self.signals = WorkerSignals()
        self.signals.update_status.connect(self._update_status_label)
        self.signals.hotkey_triggered.connect(self._on_hotkey_triggered_main_thread)

        self.init_ui()

        # Start background listener
        self.listener_thread = threading.Thread(target=self.start_listener, daemon=True)
        self.listener_thread.start()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout()
        central_widget.setLayout(layout)

        title_label = QLabel("ClipToKey")
        title_font = QFont("Helvetica", 16, QFont.Bold)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        hotkey_label = QLabel(f"Global Hotkey:\n{HOTKEY}")
        hotkey_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(hotkey_label)

        self.toggle_cb = QCheckBox("Enable Hotkey Listener")
        self.toggle_cb.setChecked(True)
        self.toggle_cb.stateChanged.connect(self.toggle_listener)
        layout.addWidget(self.toggle_cb, alignment=Qt.AlignCenter)

        self.status_label = QLabel("Status: Active")
        status_font = QFont("Helvetica", 10, QFont.Bold)
        self.status_label.setFont(status_font)
        self.status_label.setStyleSheet("color: green;")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

        self.delay_btn = QPushButton("Type Clipboard (3s Delay)")
        self.delay_btn.clicked.connect(self.on_delay_type_clicked)
        layout.addWidget(self.delay_btn)

        info_label = QLabel("Click the button above, then quickly focus\nthe window you want to paste into.")
        info_label.setAlignment(Qt.AlignCenter)
        info_font = QFont("Helvetica", 8)
        info_label.setFont(info_font)
        layout.addWidget(info_label)

        version_label = QLabel(f"v{__version__}")
        version_label.setFont(QFont("Helvetica", 7))
        version_label.setStyleSheet("color: gray;")
        version_label.setAlignment(Qt.AlignRight)
        layout.addWidget(version_label)

    def do_typing(self, text, delay=0):
        if delay > 0:
            time.sleep(delay)
        
        if text:
            controller = keyboard.Controller()
            # Release common modifier keys
            controller.release(keyboard.Key.ctrl)
            controller.release(keyboard.Key.alt)
            controller.release(keyboard.Key.shift)
            time.sleep(0.1)
            
            # Remote consoles (VNC/noVNC/KVM) drop or reorder key events that
            # arrive too fast, which loses characters and leaves Shift stuck.
            # Hold each key briefly and pause between keys so they keep up.
            for char in text.replace('\r\n', '\n'):
                key = KEY_FOR_CHAR.get(char, char)
                try:
                    controller.press(key)
                    time.sleep(KEY_HOLD_SECONDS)
                    controller.release(key)
                except (ValueError, controller.InvalidKeyException):
                    print(f"Skipping untypable character: {char!r}")
                time.sleep(KEY_GAP_SECONDS)

    def on_activate_hotkey(self):
        if self.listener_active:
            print("Hotkey detected, queuing clipboard typing...")
            # We must emit a signal to handle clipboard reading in the main thread
            self.signals.hotkey_triggered.emit()

    def _on_hotkey_triggered_main_thread(self):
        text = QApplication.clipboard().text()
        threading.Thread(target=self.do_typing, args=(text, 0), daemon=True).start()

    def start_listener(self):
        with keyboard.GlobalHotKeys({
            HOTKEY: self.on_activate_hotkey
        }) as h:
            h.join()

    def on_delay_type_clicked(self):
        # Read clipboard safely from main thread
        text = QApplication.clipboard().text()
        threading.Thread(target=self.do_typing, args=(text, 3), daemon=True).start()

    def toggle_listener(self):
        self.listener_active = self.toggle_cb.isChecked()
        if self.listener_active:
            self.signals.update_status.emit("Status: Active", "green")
        else:
            self.signals.update_status.emit("Status: Inactive", "red")

    def _update_status_label(self, text, color):
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color: {color};")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = ClipToKeyApp()
    window.show()
    sys.exit(app.exec())
