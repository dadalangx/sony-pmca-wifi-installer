"""Beginner-facing Windows wizard. Network work stays off the UI thread."""
import asyncio
import argparse
import ctypes
from datetime import datetime
from pathlib import Path
import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, ttk
import traceback

from . import __version__
from .dns import DnsRedirect
from .i18n import LANGUAGES, UserError, text
from .network import NetworkSession
from .package import download_recipe, prepare_apk, MAX_APK
from .server import InstallerServer
from .settings import credentials, state_dir, load_language, save_language
from .windows import FirewallRule, is_admin


class App:
    def __init__(self, root, lab=False, language=None):
        self.root, self.lab = root, lab
        self.language = language or load_language()
        self.queue = queue.Queue()
        self.stop = threading.Event()
        self.thread = None
        self.closing = False
        self.file = None
        self.completed = False
        self.status_key, self.status_params = "idle", {}
        self.creds = {"ssid": "CAMSETUP", "password": "24682468"} if lab else credentials()
        self.copy = {key: tk.StringVar() for key in (
            "detail", "steps", "app_label", "choose", "wifi_label", "password",
            "instructions", "start", "stop", "badge")}
        self.choice, self.title, self.status = tk.StringVar(), tk.StringVar(), tk.StringVar()
        self.language_choice = tk.StringVar()
        scale = max(1.0, root.winfo_fpixels("1i") / 96)
        root.geometry(f"{int(860 * scale)}x{int(740 * scale)}")
        root.minsize(int(820 * scale), int(700 * scale))
        root.configure(background="#f5f6f8")
        self.style = ttk.Style(root)
        self.style.theme_use("clam")
        self.style.configure("TFrame", background="#f5f6f8")
        self.style.configure("Title.TLabel", foreground="#182133")
        self.style.configure("TButton", padding=(14, 9))
        frame = ttk.Frame(root, padding=24)
        frame.pack(fill="both", expand=True)
        header = ttk.Frame(frame)
        header.pack(fill="x", pady=(0, 12))
        self.language_picker = ttk.Combobox(header, textvariable=self.language_choice,
            values=list(LANGUAGES.values()), state="readonly", width=13)
        self.language_picker.pack(side="right")
        self.language_picker.bind("<<ComboboxSelected>>", self.change_language)
        ttk.Label(header, text="Language / 语言").pack(side="right", padx=8)
        ttk.Label(frame, textvariable=self.title, style="Title.TLabel", wraplength=int(780 * scale)).pack(anchor="w")
        ttk.Label(frame, textvariable=self.copy["detail"], foreground="#5c6575").pack(anchor="w", pady=(7, 16))
        ttk.Label(frame, textvariable=self.copy["steps"], foreground="#385d96").pack(anchor="w")
        self.progress = ttk.Progressbar(frame, maximum=4, mode="determinate")
        self.progress.pack(fill="x", pady=(10, 16))
        row = ttk.Frame(frame)
        row.pack(fill="x")
        ttk.Label(row, textvariable=self.copy["app_label"]).pack(side="left")
        self.choose = ttk.Button(row, textvariable=self.copy["choose"], command=self.select_file)
        self.choose.pack(side="right")
        self.choice_label = ttk.Label(frame, textvariable=self.choice, wraplength=int(780 * scale))
        self.choice_label.pack(anchor="w", pady=(7, 14))
        card = tk.Frame(frame, bg="white", padx=20, pady=16, highlightbackground="#dce1e8", highlightthickness=1)
        card.pack(fill="x")
        self.wifi_label = tk.Label(card, textvariable=self.copy["wifi_label"], bg="white", fg="#5c6575")
        self.wifi_label.pack(anchor="w")
        tk.Label(card, text=self.creds["ssid"], bg="white", fg="#182133", font=("Consolas", 22, "bold")).pack(anchor="w", pady=(3, 8))
        self.password_label = tk.Label(card, textvariable=self.copy["password"], bg="white", fg="#182133")
        self.password_label.pack(anchor="w")
        ttk.Label(frame, textvariable=self.copy["instructions"], wraplength=int(780 * scale), justify="left").pack(anchor="w", pady=16)
        ttk.Label(frame, textvariable=self.status, wraplength=int(780 * scale), foreground="#24514c").pack(anchor="w", pady=(0, 12))
        actions = ttk.Frame(frame)
        actions.pack(side="bottom", fill="x")
        self.start_button = ttk.Button(actions, textvariable=self.copy["start"], command=self.start)
        self.start_button.pack(side="right")
        self.stop_button = ttk.Button(actions, textvariable=self.copy["stop"], command=self.cancel, state="disabled")
        self.stop_button.pack(side="right", padx=10)
        ttk.Label(actions, textvariable=self.copy["badge"], foreground="#737b87").pack(side="left")
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.after(100, self.poll)
        self.apply_language()
        if not is_admin():
            self.set_status("admin")
            self.start_button.configure(state="disabled")
        elif lab:
            root.after(500, self.start)

    def tr(self, key, **params):
        return text(key, self.language, **params)

    def apply_language(self):
        self.root.title(self.tr("window", version=__version__))
        self.language_choice.set(LANGUAGES[self.language])
        for key, variable in self.copy.items():
            variable.set(self.tr(key, password=self.creds["password"]))
        self.title.set(self.tr("complete_title" if self.completed else "title"))
        self.choice.set(self.file.name if self.file else self.tr("recipe"))
        self.status.set(self.tr(self.status_key, **self.status_params))
        font = "Microsoft YaHei UI" if self.language == "zh-CN" else "Segoe UI"
        self.style.configure("TLabel", background="#f5f6f8", font=(font, 10))
        self.style.configure("Title.TLabel", font=(font, 21, "bold"))
        self.style.configure("TButton", font=(font, 11))
        self.style.configure("TCombobox", font=(font, 10))
        self.choice_label.configure(font=(font, 13, "bold"))
        self.wifi_label.configure(font=(font, 10))
        self.password_label.configure(font=(font, 13))

    def change_language(self, event=None):
        self.language = next(key for key, label in LANGUAGES.items() if label == self.language_choice.get())
        self.apply_language()
        try:
            save_language(self.language)
        except OSError as error:
            self.set_status("incomplete", message=UserError("save_language", detail=str(error)))

    def set_status(self, key, **params):
        self.status_key, self.status_params = key, params
        self.status.set(self.tr(key, **params))

    def select_file(self):
        name = filedialog.askopenfilename(title=self.tr("file_title"), filetypes=[(self.tr("file_type"), "*.apk")])
        if name:
            self.file = Path(name)
            self.choice.set(self.file.name)

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.stop.clear()
        self.completed = False
        self.title.set(self.tr("title"))
        self.start_button.configure(state="disabled")
        self.choose.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.thread = threading.Thread(target=self.run, name="installer", daemon=False)
        self.thread.start()

    def event(self, kind, data):
        self.queue.put((kind, data))
        if self.lab:
            # Development telemetry: no hotspot password, IP, MAC, or shell data.
            import json
            with (state_dir() / "lab-events.jsonl").open("a", encoding="utf-8") as out:
                safe = {key: value for key, value in data.items() if key in ("message", "mode", "alreadyInstalled", "cleaned", "sdk")}
                out.write(json.dumps({"time": time.time(), "event": kind, **safe}) + "\n")

    def run(self):
        from winrt.runtime import init_apartment, uninit_apartment, ApartmentType
        init_apartment(ApartmentType.MULTI_THREADED)
        try:
            asyncio.run(self.session())
        except Exception as error:
            self.event("fatal", {"message": str(error), "error": error})
            with (state_dir() / "error.log").open("a", encoding="utf-8") as out:
                out.write(datetime.now().isoformat() + "\n" + traceback.format_exc() + "\n")
        finally:
            uninit_apartment()
            self.event("stopped", {})

    async def session(self):
        network, firewall, dns, server = NetworkSession(), None, None, None
        finished = threading.Event()
        cleanup_errors = []
        def camera_event(kind, data):
            self.event(kind, data)
            if kind == "verified":
                finished.set()
        try:
            self.event("preparing", {})
            if self.file:
                with self.file.open("rb") as stream:
                    data = stream.read(MAX_APK + 1)
                package = prepare_apk(data, self.file.stem)
            else:
                package = download_recipe()
            if self.stop.is_set():
                return
            self.event("network", {"app": package.name, "version": package.version})
            adapter, mode = await network.start(**self.creds)
            if self.stop.is_set():
                return
            firewall = FirewallRule(adapter)
            firewall.start()
            server = InstallerServer(adapter, package, camera_event)
            server.start()
            vendor = Path(__file__).resolve().parents[1] / "vendor" / "WinDivert-2.2.2-A"
            dns = DnsRedirect(adapter, vendor, lambda kind, data: self.event("network_error", data) if kind == "error" else None)
            dns.start()
            self.event("hotspot", {"mode": mode})
            deadline = time.monotonic() + 2400
            while not self.stop.is_set() and time.monotonic() < deadline:
                await asyncio.sleep(0.25)
            if not finished.is_set() and not self.stop.is_set():
                error = UserError("timeout")
                self.event("fatal", {"message": str(error), "error": error})
            if finished.is_set():
                await asyncio.sleep(1)  # Let the camera receive its completion response.
        finally:
            self.event("cleanup", {})
            for resource in (dns, server, firewall):
                if resource:
                    try:
                        resource.close()
                    except Exception as error:
                        cleanup_errors.append(error)
            try:
                await network.close()
            except Exception as error:
                cleanup_errors.append(error)
            if cleanup_errors:
                raise UserError("cleanup_failed", errors=cleanup_errors)

    def cancel(self):
        self.stop.set()
        self.stop_button.configure(state="disabled")
        self.set_status("cleanup")

    def close(self):
        if self.thread and self.thread.is_alive():
            self.closing = True
            self.cancel()
        else:
            self.root.destroy()

    def poll(self):
        while True:
            try:
                kind, data = self.queue.get_nowait()
            except queue.Empty:
                break
            messages = {"preparing": 1, "network": 2, "hotspot": 2,
                        "ready": 3, "downloading": 3, "prepared": 3, "opening": 4}
            if kind in messages:
                self.progress["value"] = messages[kind]
                self.set_status(kind)
            elif kind == "verified":
                self.progress["value"] = 4
                self.completed = True
                self.title.set(self.tr("complete_title"))
                self.set_status("already_installed" if data.get("alreadyInstalled") else "verified")
            elif kind in ("fatal", "network_error", "error"):
                self.set_status("incomplete", message=data.get("error") or data.get("message") or UserError("camera_error"))
            elif kind == "stopped":
                self.start_button.configure(state="normal" if is_admin() else "disabled")
                self.choose.configure(state="normal")
                self.stop_button.configure(state="disabled")
                if self.status_key != "incomplete":
                    self.set_status("stopped")
                if self.closing:
                    self.root.destroy()
                    return
        self.root.after(100, self.poll)


def main():
    parser = argparse.ArgumentParser(description="Install apps on supported Sony PMCA cameras over Wi-Fi.")
    parser.add_argument("--lang", choices=list(LANGUAGES), help="Override the saved/display language")
    parser.add_argument("--lab", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass
    root = tk.Tk()
    App(root, lab=args.lab, language=args.lang)
    root.mainloop()


if __name__ == "__main__":
    main()
