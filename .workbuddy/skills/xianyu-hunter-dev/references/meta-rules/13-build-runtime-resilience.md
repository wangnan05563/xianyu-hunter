# 构建与运行时韧性

> 构建产物资源指令显式化、构建运行时 Python 钉选与自愈。
>
> 涵盖规范: #112, #113
>
> 完整内容见 [../meta-rules.md](../meta-rules.md) | [返回索引](index.md)

---

### #112 构建产物资源指令显式化（BUILD-ARTIFACT-RESOURCE-EXPLICIT）
应用 exe 图标（PyInstaller --icon/.spec）与安装包图标（Inno Setup SetupIconFile）分别显式声明；自动生成模板须同步；系统资源须先抽取成 .ico 文件再引用（版权风险）
- grep: `grep "SetupIconFile" installer.iss` 缺失 → 安装包用默认图标
- grep: `grep "SetupIconFile" scripts/build-exe.ps1` 缺失 → 模板未同步，重建即丢失

### #113 构建运行时 Python 钉选与自愈（BUILD-RUNTIME-PYTHON-PINNING）
构建脚本禁止裸依赖 PATH 的 python；钉选已知完好运行时（PATH 前置）；校验 base 健康；外部工具调用 fail-soft 自愈重建 venv
- grep: `grep "python" scripts/*.ps1 scripts/*.bat` 裸用 python 而不前置钉选 → 违反
- grep: `grep "try" ` 包裹 pip 调用缺失 → 损坏环境会硬中止
