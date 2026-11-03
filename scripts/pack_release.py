"""Create an end-user ZIP and an explicit allowlist-only source ZIP."""
import hashlib
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pmca_wifi import __version__


def source_files():
    names = ["README.md", "LICENSE", "THIRD_PARTY.md", "RELEASE_NOTES.md", ".gitignore",
             "requirements.txt", "requirements-dev.txt", "build.py", "main.py",
             "scripts/fetch_vendor.py", "scripts/pack_release.py"]
    result = [ROOT / name for name in names]
    for directory in ("pmca_wifi", "tests", "licenses", ".github"):
        for path in (ROOT / directory).rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix not in (".pyc", ".pyo"):
                result.append(path)
    return sorted(set(result))


def main():
    output = ROOT / "releases"
    output.mkdir(exist_ok=True)
    application = ROOT / "dist" / "SonyPmcaWifiInstaller"
    if not (application / "SonyPmcaWifiInstaller.exe").is_file():
        raise RuntimeError("Build the Windows application first")
    stem = "Sony-PMCA-WiFi-Installer-v" + __version__
    windows_zip = output / (stem + "-Windows-x64.zip")
    source_zip = output / (stem + "-source.zip")
    with zipfile.ZipFile(windows_zip, "w", zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(application.rglob("*")):
            if file.is_file():
                if file.suffix.lower() in (".apk", ".spk", ".pcap", ".pcapng", ".log"):
                    raise RuntimeError("Unexpected application/user data in distribution")
                archive.write(file, "SonyPmcaWifiInstaller/" + file.relative_to(application).as_posix())
    with zipfile.ZipFile(source_zip, "w", zipfile.ZIP_DEFLATED) as archive:
        for file in source_files():
            archive.write(file, "sony-pmca-wifi-installer/" + file.relative_to(ROOT).as_posix())
    hashes = []
    for file in (windows_zip, source_zip):
        hashes.append(hashlib.sha256(file.read_bytes()).hexdigest() + "  " + file.name)
        print(file.name, file.stat().st_size)
    (output / "SHA256SUMS.txt").write_text("\n".join(hashes) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
