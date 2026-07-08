; XianyuHunter 安装包脚本
; 由 build-exe.ps1 自动调用：iscc /DMyAppVersion=<version> installer.iss
; 产物：dist\XianyuHunter-Setup-v<version>.exe
;
; 版本号通过命令行参数 /DMyAppVersion 传入（build-exe.ps1 从 __init__.py 读取）
; 手动编译：iscc /DMyAppVersion=0.3.0 installer.iss

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0.0"
#endif

[Setup]
AppName=XianyuHunter
AppVersion={#MyAppVersion}
AppPublisher=XianyuHunter
DefaultDirName={autopf}\XianyuHunter
DefaultGroupName=XianyuHunter
UninstallDisplayIcon={app}\xianyu-hunter.exe
OutputDir=dist
OutputBaseFilename=XianyuHunter-Setup-v{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
; 仅支持 64 位系统（Playwright Chromium 仅提供 64 位）
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
; 安装到 Program Files 需要管理员权限
PrivilegesRequired=admin
; 跳过"选择开始菜单文件夹"页面（使用默认值）
DisableProgramGroupPage=yes


[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加选项:"

[Files]
; 整个 dist\xianyu-hunter\ 目录打包进安装包
Source: "dist\xianyu-hunter\*"; DestDir: "{app}"; Excludes: "*.log,data\*,.env,.secrets.json,.env.local"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\XianyuHunter"; Filename: "{app}\xianyu-hunter.exe"
Name: "{group}\卸载 XianyuHunter"; Filename: "{uninstallexe}"
Name: "{commondesktop}\XianyuHunter"; Filename: "{app}\xianyu-hunter.exe"; Tasks: desktopicon

[Run]
; 安装完成后可选启动
Filename: "{app}\xianyu-hunter.exe"; Description: "立即启动 XianyuHunter"; Flags: nowait postinstall skipifsilent
