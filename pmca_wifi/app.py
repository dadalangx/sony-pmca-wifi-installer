"""Beginner-facing Windows wizard. Network work stays off the UI thread."""
import asyncio
import ctypes
from datetime import datetime
from pathlib import Path
import queue
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, ttk
import traceback

from . import __version__
from .dns import DnsRedirect
from .network import NetworkSession
from .package import download_recipe, prepare_apk, MAX_APK
from .server import InstallerServer
from .settings import credentials, state_dir
from .windows import FirewallRule, is_admin


class App:
    def __init__(self, root, lab=False):
        self.root, self.lab = root, lab
        self.queue = queue.Queue()
        self.stop = threading.Event()
        self.thread = None
        self.closing = False
        self.file = None
        self.creds = {"ssid": "CAMSETUP", "password": "24682468"} if lab else credentials()
        self.choice = tk.StringVar(value="Recipe Lab 1.11.1（作者原版）")
        self.title = tk.StringVar(value="通过 Wi-Fi，为相机安装应用")
        self.detail = tk.StringVar(value="支持的 Sony PMCA 相机 · 无需 USB · 无需特殊路由器")
        self.step = tk.StringVar(value="选择应用 → 连接相机 → 确认安装 → 完成")
        self.status = tk.StringVar(value="选择 Recipe Lab，或打开兼容的本地 APK。")
        root.title("Sony 相机应用安装助手 · " + __version__ + " 实验版")
        scale = max(1.0, root.winfo_fpixels("1i") / 96)
        root.geometry(f"{int(780 * scale)}x{int(680 * scale)}")
        root.minsize(int(720 * scale), int(650 * scale))
        root.configure(background="#f5f6f8")
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("TFrame", background="#f5f6f8")
        style.configure("TLabel", background="#f5f6f8", font=("Microsoft YaHei UI", 10))
        style.configure("Title.TLabel", font=("Microsoft YaHei UI", 21, "bold"), foreground="#182133")
        style.configure("TButton", font=("Microsoft YaHei UI", 11), padding=(16, 9))
        frame = ttk.Frame(root, padding=28)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, textvariable=self.title, style="Title.TLabel").pack(anchor="w")
        ttk.Label(frame, textvariable=self.detail, foreground="#5c6575").pack(anchor="w", pady=(7, 20))
        ttk.Label(frame, textvariable=self.step, foreground="#385d96").pack(anchor="w")
        self.progress = ttk.Progressbar(frame, maximum=4, mode="determinate")
        self.progress.pack(fill="x", pady=(10, 20))
        row = ttk.Frame(frame)
        row.pack(fill="x")
        ttk.Label(row, text="安装应用").pack(side="left")
        self.choose = ttk.Button(row, text="选择本地 APK…", command=self.select_file)
        self.choose.pack(side="right")
        ttk.Label(frame, textvariable=self.choice, font=("Microsoft YaHei UI", 13, "bold"), wraplength=660).pack(anchor="w", pady=(7, 14))
        card = tk.Frame(frame, bg="white", padx=20, pady=16, highlightbackground="#dce1e8", highlightthickness=1)
        card.pack(fill="x")
        tk.Label(card, text="相机要连接的 Wi-Fi", bg="white", fg="#5c6575", font=("Microsoft YaHei UI", 10)).pack(anchor="w")
        tk.Label(card, text=self.creds["ssid"], bg="white", fg="#182133", font=("Consolas", 22, "bold")).pack(anchor="w", pady=(3, 8))
        tk.Label(card, text="密码：" + self.creds["password"] + "  （8 位数字）", bg="white", fg="#182133", font=("Microsoft YaHei UI", 13)).pack(anchor="w")
        instructions = "① 点击开始，等待热点就绪\n② 相机 MENU → 无线 → 访问点手动设置，选择上面的 Wi-Fi\n③ 打开 PlayMemories 商店，选择 Install app 并确认安装"
        ttk.Label(frame, text=instructions, wraplength=680, justify="left").pack(anchor="w", pady=16)
        ttk.Label(frame, textvariable=self.status, wraplength=680, foreground="#24514c").pack(anchor="w", pady=(0, 12))
        actions = ttk.Frame(frame)
        actions.pack(side="bottom", fill="x")
        self.start_button = ttk.Button(actions, text="开始安装", command=self.start)
        self.start_button.pack(side="right")
        self.stop_button = ttk.Button(actions, text="结束并关闭热点", command=self.cancel, state="disabled")
        self.stop_button.pack(side="right", padx=10)
        ttk.Label(actions, text="实验版 · 已实测 A7R II", foreground="#737b87").pack(side="left")
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.after(100, self.poll)
        if not is_admin():
            self.status.set("请关闭窗口，以管理员身份重新运行工具。")
            self.start_button.configure(state="disabled")
        elif lab:
            root.after(500, self.start)

    def select_file(self):
        name = filedialog.askopenfilename(title="选择 Sony PMCA 兼容应用", filetypes=[("安卓应用 APK", "*.apk")])
        if name:
            self.file = Path(name)
            self.choice.set(self.file.name)

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.stop.clear()
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
            self.event("fatal", {"message": str(error)})
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
                self.event("fatal", {"message": "等待超过 40 分钟，已结束本次连接，请重新开始。"})
            if finished.is_set():
                await asyncio.sleep(1)  # Let the camera receive its completion response.
        finally:
            self.event("cleanup", {})
            for resource in (dns, server, firewall):
                if resource:
                    try:
                        resource.close()
                    except Exception as error:
                        cleanup_errors.append(str(error))
            try:
                await network.close()
            except Exception as error:
                cleanup_errors.append(str(error))
            if cleanup_errors:
                raise RuntimeError("；".join(cleanup_errors))

    def cancel(self):
        self.stop.set()
        self.stop_button.configure(state="disabled")
        self.status.set("正在结束连接并关闭热点，请稍候…")

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
            messages = {
                "preparing": (1, "正在准备应用并校验安装包…"),
                "network": (2, "应用已校验，正在开启电脑热点…"),
                "hotspot": (2, "热点已就绪。请让相机连接上面的 Wi-Fi，然后打开 PlayMemories 商店。"),
                "ready": (3, "相机已连接。请在相机选择 Install app。"),
                "downloading": (3, "正在向相机传输应用，请保持相机页面打开…"),
                "prepared": (3, "相机上的安装包校验通过。"),
                "opening": (4, "请在相机确认安装。安装结束后，再打开一次 PlayMemories 商店完成核对。"),
            }
            if kind in messages:
                step, text = messages[kind]
                self.progress["value"] = step
                self.status.set(text)
            elif kind == "verified":
                self.progress["value"] = 4
                self.title.set("应用已就绪")
                result = "相机已有相同版本，无线传输和文件校验通过。" if data.get("alreadyInstalled") else "安装已核对，临时安装包已清理。"
                self.status.set(result + "请退出相机商店，再点击结束并关闭热点。")
            elif kind in ("fatal", "network_error", "error"):
                self.status.set("未完成：" + str(data.get("message", "请查看相机提示，重试或结束连接。")))
            elif kind == "stopped":
                self.start_button.configure(state="normal")
                self.choose.configure(state="normal")
                self.stop_button.configure(state="disabled")
                if self.closing:
                    self.root.destroy()
                    return
        self.root.after(100, self.poll)


def main():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass
    root = tk.Tk()
    App(root, lab="--lab" in sys.argv)
    root.mainloop()


if __name__ == "__main__":
    main()
