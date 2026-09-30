# DocBridge

Word 与 Markdown 双向转换工具，提供 Windows 图形界面和命令行。

## 功能

- Markdown 转 Word：模板排版、正文及标题 1–6 级样式、目录、页码、编号、列表、表格和图片。
- Word 转 Markdown：按原标题层级导出，保留粗体、斜体、列表、链接和表格；图片导出并重映射相对路径。
- 自动目录按正文标题重建为可点击目录；合并单元格表格使用 HTML 保留结构。
- 批量添加、目录导入、拖放、预览与日志。两个方向的队列、结果及任务状态相互独立。
- 无边框窗口、自定义 SVG 窗口按钮、拖动与缩放，保留原来的 M 图标。
- 旧版 `.doc` 使用可选 LibreOffice 引擎，默认不包含、不下载，也不启动引擎。

![Markdown 转 Word](docs/workbench-markdown.png)

![Word 转 Markdown](docs/workbench-word.png)

## 启动

便携版运行 `docbridge.exe`。从源码运行需要 Python 3.10 或更高版本：

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe md2docx_gui.py
```

Windows 下也可双击 `run-gui.bat`，使用项目内的虚拟环境。
原来的 `md2docx.py`、`docx2md.py` 和 `md2docx_gui.py` 入口继续可用。

## 输出

GUI 默认保存到每份原文件所在目录。重名时添加编号，勾选覆盖后才替换结果。
Word 转 Markdown 的输出名称保持一致：

```text
报告.docx
报告.md
报告_images/
    报告_001_图片摘要.png
```

Markdown 图片路径支持中文、空格及 URL 编码。转换保留内容和结构，页面版式无法逐字节还原；
Markdown 转 Word 暂不解析 HTML 合并表格。手工输入、没有目录样式的目录按原文保留。

## 排版

在 Markdown 转 Word 页选择模板，点击“排版设置”。设置按字体、段落、页面、编号与列表、
样式设计、表格与图片分类；正文和标题 1–6 级可分别调整。空白项沿用模板，支持导出 YAML 模板。

![逐级样式设置](docs/workbench-advanced.png)

`config/` 提供通用、论文、公文和紧凑模板。便携程序旁的同名模板可覆盖内置模板。
Mermaid 图使用系统 Chrome 或 Edge 本地渲染；缺少渲染工具时会保留源码。

## 可选的 .doc 支持

在 Word 转 Markdown 的“.doc 支持”页点击“下载并启用”，才会下载官方 LibreOffice 引擎。
首次下载约 358 MB，准备后约 1.2 GB；支持下载进度、取消、SHA-256 校验和失败重试。
文件准备期间取消会等待当前操作结束，不进行系统安装。`.docx` 无需引擎。

![按需启用引擎](docs/workbench-doc-support.png)

为兼容之前的版本，引擎缓存仍保存在 `%LOCALAPPDATA%/md2stdreport/runtime/libreoffice/`。
可通过 `DOCX2MD_RUNTIME_DIR` 指定缓存位置，或通过 `DOCX2MD_LIBREOFFICE` 指定可执行程序。
已有系统 LibreOffice 也可使用。启动、切换功能及缺少引擎时的转换不会触发下载。

## 命令行

```powershell
# Markdown 转 Word
.venv\Scripts\python.exe md2docx.py 报告.md
.venv\Scripts\python.exe md2docx.py 报告.md -c config\thesis.yaml

# Word 转 Markdown，默认输出到原目录
.venv\Scripts\python.exe docx2md.py 报告.docx
.venv\Scripts\python.exe docx2md.py 文档目录 -r -o 输出目录

# 用户主动下载并启用 .doc 引擎
.venv\Scripts\python.exe docx2md.py --download-engine
```

便携包提供 `md2docx.exe` 和 `docx2md.exe`，参数与对应 Python 入口相同。
各命令可用 `--help` 查看完整参数。

## 构建

```powershell
.venv\Scripts\python.exe -m pip install -r packaging\requirements-build.txt
.venv\Scripts\python.exe packaging\build.py
```

构建生成 `docbridge.exe`、两个命令行程序和 `docbridge-<版本>-win64.zip`，
并检查命令行双向转换及界面启动。验证产物写入临时目录，不依赖本地测试文件。
默认发布包不包含 LibreOffice 引擎。

GitHub Actions 在主分支提交时构建并上传产物；推送 `v*` 标签时创建 Release。
源码仓库排除虚拟环境、构建包、个人文档、引擎、临时文件及本地测试文件。

模块职责和扩展方式见 [架构说明](docs/architecture.md)。
