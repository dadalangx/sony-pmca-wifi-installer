## 0.1.1 — English / 简体中文

English and Simplified Chinese are now available in the Windows wizard.

- Automatically selects English or Simplified Chinese from the Windows display language on first launch.
- Switch languages at the top right without restarting or interrupting an installation; the preference is remembered.
- Translates instructions, buttons, status messages, file dialogs and tool-generated errors. Windows diagnostic details keep their original language.
- Adds an English project homepage and a linked Chinese guide. Both guides are included in the ZIP.
- Adds language preference and live UI-switching tests. The camera installation protocol is unchanged.

**Download the Windows x64 ZIP and extract the entire folder**, then run `SonyPmcaWifiInstaller.exe` as administrator. Python and OpenWrt are not required.

Physical camera testing covers the 0.1.0 installation flow on one Sony A7R II, Windows 10 x64 and a VID 148F / PID 760B adapter using Hosted Network. The 0.1.1 localization update has automated UI and regression coverage; its new EXE has not been retested on a physical camera. Other hardware and Windows 11 remain unverified.

### 中文

0.1.1 新增 Windows 界面中英文适配。

- 首次启动按 Windows 显示语言选择中英文，右上角可随时切换并保存选择。
- 操作说明、按钮、状态、文件选择窗口及工具自身错误提示均有中英文；Windows 原始诊断保留系统语言。
- 项目首页改为英文，中文指南单独保留并互相链接；压缩包内同时提供两份指南。
- 增加语言偏好和界面切换测试；相机安装协议未改变。

完整解压 Windows x64 ZIP 后，以管理员身份运行 EXE，无需 Python 或 OpenWrt。相机实测覆盖 0.1.0 的 A7R II 安装流程；0.1.1 的新 EXE 尚未重新进行相机安装实测，其他硬件及 Windows 11 仍待验证。

## 0.1.0

0.1.0 是面向 Sony PMCA 相机的 Windows Wi-Fi 安装实验版。

- 中文图形向导，自动创建相机热点，无需 OpenWrt。
- 支持下载并校验 Recipe Lab 1.11.1，或选择本地兼容 APK。
- 自动封装 SPK、校验无线传输和相机文件，调用相机原生安装器。
- 安装后重新打开商店，核对应用并清理临时包。
- 正常结束时关闭热点并撤销本次临时网络设置。

已实测：一台 Sony A7R II + Windows 10 x64 + VID 148F / PID 760B USB 网卡的传统热点模式。其他机型、固件、网卡和 Windows 11 尚未实测。

下载 Windows x64 ZIP，完整解压后双击 EXE。首次启动需确认管理员权限，普通用户无需安装 Python。请阅读 README 中的操作步骤与实验版限制。
