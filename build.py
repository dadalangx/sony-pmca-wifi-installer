"""Build a Windows x64 folder: unzip, then double-click the executable."""
from pathlib import Path
import importlib.metadata
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def main():
    if sys.platform != "win32" or sys.maxsize <= 2 ** 32:
        raise RuntimeError("Build on 64-bit Windows with 64-bit Python")
    subprocess.run([sys.executable, str(ROOT / "scripts" / "fetch_vendor.py")], check=True)
    licenses = ROOT / "licenses"
    for name in ("pycryptodomex", "winrt-runtime", "winrt-Windows.Networking", "typing_extensions", "pyinstaller"):
        distribution = importlib.metadata.distribution(name)
        for file in distribution.files or []:
            if file.name.lower().startswith(("license", "copying")) and ".dist-info" in str(file):
                shutil.copyfile(distribution.locate_file(file), licenses / (name + "-" + file.name))
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if python_license.exists():
        shutil.copyfile(python_license, licenses / "Python-LICENSE.txt")
    # Keep LGPL libraries as separate, replaceable files in the application folder.
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--windowed", "--onedir", "--uac-admin",
               "--name", "SonyPmcaWifiInstaller", "--collect-all", "winrt",
               "--add-data", "pmca_wifi/camera.js;pmca_wifi",
               "--add-data", "licenses;licenses"]
    for name in ("x64/WinDivert.dll", "x64/WinDivert64.sys", "LICENSE", "README", "VERSION"):
        target = "vendor/WinDivert-2.2.2-A/" + str(Path(name).parent).replace("\\", "/")
        command += ["--add-data", "vendor/WinDivert-2.2.2-A/" + name + ";" + target]
    command.append("main.py")
    subprocess.run(command, check=True, cwd=ROOT)
    output = ROOT / "dist" / "SonyPmcaWifiInstaller"
    for name in ("README.md", "README.zh-CN.md", "LICENSE", "THIRD_PARTY.md", "RELEASE_NOTES.md"):
        shutil.copyfile(ROOT / name, output / name)
    print("Built dist/SonyPmcaWifiInstaller/SonyPmcaWifiInstaller.exe")


if __name__ == "__main__":
    main()
