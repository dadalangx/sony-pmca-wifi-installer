0.1.0 是面向 Sony PMCA 相机的 Windows Wi-Fi 安装实验版。

- 中文图形向导，自动创建相机热点，无需 OpenWrt。
- 支持下载并校验 Recipe Lab 1.11.1，或选择本地兼容 APK。
- 自动封装 SPK、校验无线传输和相机文件，调用相机原生安装器。
- 安装后重新打开商店，核对应用并清理临时包。
- 正常结束时关闭热点并撤销本次临时网络设置。

已实测：一台 Sony A7R II + Windows 10 x64 + VID 148F / PID 760B USB 网卡的传统热点模式。其他机型、固件、网卡和 Windows 11 尚未实测。

下载 Windows x64 ZIP，完整解压后双击 EXE。首次启动需确认管理员权限，普通用户无需安装 Python。请阅读 README 中的操作步骤与实验版限制。
