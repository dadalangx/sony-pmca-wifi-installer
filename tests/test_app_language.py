from pathlib import Path
import tkinter as tk

import pytest

from pmca_wifi import app
from pmca_wifi.i18n import UserError


@pytest.fixture
def wizard(monkeypatch):
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk display is unavailable")
    root.withdraw()
    monkeypatch.setattr(app, "credentials", lambda: {"ssid": "SONY-APPS-ABCD", "password": "12345678"})
    monkeypatch.setattr(app, "is_admin", lambda: False)
    monkeypatch.setattr(app, "save_language", lambda value: None)
    try:
        yield app.App(root, language="en")
    finally:
        root.destroy()


def switch(wizard, label):
    wizard.language_choice.set(label)
    wizard.change_language()
    wizard.root.update_idletasks()


def test_live_switch_preserves_file_credentials_and_progress(wizard):
    wizard.file = Path("camera-style.apk")
    wizard.event("ready", {})
    wizard.poll()
    before = dict(wizard.creds)
    assert "Select Install app" in wizard.status.get()
    switch(wizard, "简体中文")
    assert "相机已连接" in wizard.status.get()
    assert wizard.choice.get() == "camera-style.apk"
    assert wizard.progress["value"] == 3 and wizard.creds == before
    switch(wizard, "English")
    assert "Select Install app" in wizard.status.get()
    assert "12345678" in wizard.copy["password"].get()
    assert wizard.copy["start"].get() == "Start installation"


def test_error_and_completed_state_retranslate_without_restart(wizard):
    wizard.event("fatal", {"error": UserError("download_http", code=404)})
    wizard.poll()
    assert "HTTP 404" in wizard.status.get() and "GitHub download failed" in wizard.status.get()
    switch(wizard, "简体中文")
    assert "HTTP 404" in wizard.status.get() and "GitHub 下载失败" in wizard.status.get()
    wizard.event("verified", {"alreadyInstalled": True})
    wizard.poll()
    switch(wizard, "English")
    assert wizard.title.get() == "Your app is ready"
    assert "already installed" in wizard.status.get()
    wizard.event("stopped", {})
    wizard.poll()
    assert "hotspot closed" in wizard.status.get()
    assert str(wizard.start_button["state"]) == "disabled"  # Non-admin check remains in force.
