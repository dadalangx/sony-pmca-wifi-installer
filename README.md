# Sony PMCA Wi-Fi Installer

English | [简体中文](README.zh-CN.md)

**Install apps over Wi-Fi on supported Sony PMCA cameras, even with a broken USB port.**

A Windows wizard in English and Simplified Chinese. Choose Recipe Lab or a compatible local APK, and the tool creates a Wi-Fi hotspot for your camera. No OpenWrt, router configuration, IP addresses or DNS knowledge required.

Current version: **0.1.1 experimental**. On November 4, 2026, the maintainer confirmed successful on-camera validation of the 0.1.1 Windows executable on the existing Sony A7R II setup. Version 0.1.1 adds localization without changing the camera installation protocol.

**[Download for Windows x64](https://github.com/dadalangx/sony-pmca-wifi-installer/releases/download/v0.1.1/Sony-PMCA-WiFi-Installer-v0.1.1-Windows-x64.zip)** · [All releases and release notes](https://github.com/dadalangx/sony-pmca-wifi-installer/releases)

## How to use

1. Download the Windows x64 ZIP and **extract the entire folder**. Do not run from inside the ZIP or move the EXE away from the other files.
2. Double-click `SonyPmcaWifiInstaller.exe` and accept the Windows administrator prompt.
3. Keep the default Recipe Lab selection, or select **Choose local APK**, then **Start installation**.
4. Wait for **Hotspot ready**. On the camera, go to **MENU → Wireless → Access Point Set.**, select the Wi-Fi shown in the wizard, and enter its 8-digit password. Set **Priority Connection** to **On** and leave **IP Address Setting** on **Auto**.
5. Open **Application List → PlayMemories Camera Apps** on the camera. Select **Install app** on the page, then confirm the native Sony installation prompt.
6. After installation, **open PlayMemories Camera Apps once more** and wait for verification to finish. Exit the camera store, then select **Finish and close hotspot** on the computer.

The computer needs an internet connection and a Wi-Fi adapter that can create a hotspot. Ethernet internet access is fine. The camera does not need a USB connection, and users do not need Python.

The tool remembers its generated Wi-Fi name and numeric password for future use. Credentials are stored locally and encrypted with Windows DPAPI.

### Language

On first launch, Chinese Windows display languages select Simplified Chinese; other display languages select English. Use **English / 简体中文** at the top right to switch at any time. The preference is saved, and switching does not interrupt an installation. The camera page remains in English. Diagnostic details returned by Windows remain in the system's language.

## App sources

- The default download is the author's unmodified [Recipe Lab v1.11.1 APK](https://github.com/voxivoid/recipe-lab-sony-pmca/releases/tag/v1.11.1). Its published SHA-256 is checked before use.
- Local APKs must be compatible apps made for Sony PMCA cameras. The current limit is 16 MB. Ordinary Android phone apps are not automatically compatible.
- Recipe Lab is downloaded separately; its APK is not bundled or modified. This tool does not provide paid Sony app packages.

## Tested compatibility

| Component | Result |
| --- | --- |
| Camera | One Sony A7R II; firmware version not recorded; Android API 16 |
| Computer | Windows 10 x64, build 19045 |
| Wi-Fi adapter | Ralink/MediaTek USB adapter, VID 148F / PID 760B, driver 5.1.22.0 |
| Hosted Network hotspot | 0.1.0 completed Recipe Lab installation, verification and temporary-package cleanup; the maintainer also confirmed successful 0.1.1 on-camera validation on November 4, 2026 |
| Windows Mobile Hotspot with that adapter | Phones could connect, but the camera store could not; the tool prefers Hosted Network when supported |
| Windows 11, other adapters, cameras and firmware | Not yet tested with a physical camera |
| Other PMCA APKs | Local selection and generic SPK packaging are implemented; individual apps have not been tested |

This is an experimental release with limited hardware testing. It is not a universal installer for every Sony camera. The tool checks the APK's Android version requirement; compatibility also depends on the app, camera and firmware.

## Troubleshooting

**The hotspot will not start:** Check that the Wi-Fi adapter is connected and its driver is installed. Close any other active hotspot or Internet Connection Sharing session. The tool does not take over an existing session.

**The camera cannot find a connectable access point:** Select the Wi-Fi shown in the wizard again. Check the password, Priority Connection and automatic IP settings. After saving, you can turn the camera off for five seconds and retry. Some adapters' Mobile Hotspot mode does not work with older cameras.

**The GitHub download fails:** Download the APK from the author's release yourself, then use **Choose local APK**. Downloads use Windows HTTPS with certificate verification enabled.

**The wizard is still waiting after installation:** The native installer pauses the camera browser. Follow step 6 to reopen the store so the tool can verify the installed app and remove the temporary package.

**The process crashes or the adapter is unplugged:** This version cleans up on normal exit and handled errors, but does not recover network state across a process crash. Avoid force-quitting or unplugging the adapter during installation. If a hotspot or sharing session remains, close it in Windows before retrying.

Local settings and error logs are stored in `%LOCALAPPDATA%\SonyPmcaWifiInstaller`. Do not upload credentials or logs to the repository.

## Run or build from source

Use Windows x64 and Python 3.12. Run the installer with administrator privileges.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/fetch_vendor.py
.\.venv\Scripts\python.exe main.py
```

Use `python main.py --lang en` or `python main.py --lang zh-CN` to override the interface language for one launch.

Build the Windows application and release archives:

```powershell
.\.venv\Scripts\python.exe build.py
.\.venv\Scripts\python.exe scripts/pack_release.py
```

Outputs are written to `dist/` and `releases/`. GitHub Actions supports manual builds; pushing a version tag creates a draft release for review, unless that release already exists. The build downloads a pinned official WinDivert archive, checks its SHA-256 and bundles the unmodified signed driver.

## How it works and credits

The camera store first requests a fixed HTTP entry page. Within its own hotspot, the tool resolves that store hostname locally, redirects the camera to an installation page, transfers an SPK through the legacy browser interface verified on the test camera, and invokes the camera's native installer. It verifies the result and removes the temporary SPK. Normal shutdown removes the tool's temporary firewall rule, stops redirection and closes the hotspot.

The page offers a fixed installation flow, without an arbitrary-command or arbitrary-file interface. The tool does not modify camera firmware or configure DNS for the whole home network.

- [Sony-PMCA-RE: app installation protocol](https://github.com/ma1co/Sony-PMCA-RE/blob/master/docs/AppInstallation.md)
- [Sony-PMCA-RE: SPK implementation](https://github.com/ma1co/Sony-PMCA-RE/tree/master/pmca/spk)
- [OpenMemories AppStore: native installer invocation](https://github.com/ma1co/OpenMemories-AppStore)
- [Recipe Lab](https://github.com/voxivoid/recipe-lab-sony-pmca)
- [WinDivert](https://reqrypt.org/windivert-doc.html)

Original project code is MIT-licensed; SPK constants retain ma1co's MIT notice. Dependencies and third-party apps keep their own licenses; see [THIRD_PARTY.md](THIRD_PARTY.md). This project is not affiliated with Sony.
