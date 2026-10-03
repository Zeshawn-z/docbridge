# DocBridge 命令行使用说明

DocBridge 提供两个命令行程序：

| 程序 | 用途 |
| --- | --- |
| `md2docx.exe` | Markdown 文件或文本写入 Word |
| `docx2md.exe` | Word 文件导出 Markdown，或读取为文本 |

以下示例使用 Windows PowerShell，在程序所在目录运行。路径包含空格时使用双引号。
不需要安装 Microsoft Word，也不需要打开图形界面。

## 1. 运行方式

### 使用便携版

从 [GitHub Releases](https://github.com/Zeshawn-z/docbridge/releases/latest) 下载并解压
`docbridge-<版本>-win64.zip`，在解压目录打开 PowerShell：

```powershell
.\md2docx.exe --help
.\docx2md.exe --help
.\md2docx.exe --version
```

便携版不需要安装 Python。使用模板示例时，请保留 ZIP 中的 `config` 目录。

### 从源码运行

在项目根目录执行，需要 Python 3.10 或更高版本：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe md2docx.py --help
.\.venv\Scripts\python.exe docx2md.py --help
```

无需激活虚拟环境。下文的 `.\md2docx.exe` 可替换为
`.\.venv\Scripts\python.exe md2docx.py`；`.\docx2md.exe` 同理。

## 2. Markdown 文件转 Word

```powershell
# 默认生成原文件目录下的“报告.docx”
.\md2docx.exe "D:\文档\报告.md"

# 指定输出文件
.\md2docx.exe "报告.md" -o "输出\报告.docx"

# 多个文件写入同一输出目录
.\md2docx.exe "报告.md" "说明.md" -o "输出"

# 目录输入会递归查找子目录中的 .md 文件
.\md2docx.exe "Markdown文档" -o "输出"

# 通配符：只处理当前目录中匹配的文件
.\md2docx.exe "*.md" -o "输出"
```

标题层级映射为 Word 标题样式；加粗、斜体、列表、表格、图片及公式按配置转换。
图片路径以输入 Markdown 文件所在目录为基准解析。

**文件输入模式会覆盖同名 Word 输出。** 批量指定输出目录时文件统一写入该目录，
不保留输入目录树；不同子目录中的同名文件也可能使用相同输出路径。
`--overwrite` 仅控制下面的文本输入模式。

## 3. Word 文件转 Markdown

```powershell
# 默认输出到 Word 文件所在目录
.\docx2md.exe "D:\文档\报告.docx"

# -o 指定的是输出目录，而不是 Markdown 文件名
.\docx2md.exe "报告.docx" -o "输出"

# 多个文件
.\docx2md.exe "报告.docx" "说明.docx" -o "输出"

# 目录输入：默认只读取该目录，-r 包含子目录
.\docx2md.exe "Word文档" -r -o "输出"

# 主动覆盖已有结果
.\docx2md.exe "报告.docx" --overwrite
```

以 `报告.docx` 为例，存在图片时生成：

```text
报告.md
报告_images/
    报告_001_<摘要>.png
    报告_002_<摘要>.jpg
```

图片在 Markdown 中使用相对路径。没有导出图片时不创建图片目录。
默认遇到已有结果会同步改名为 `报告_2.md` 和 `报告_2_images/`，避免覆盖。
标题层级、加粗、斜体和表格会保留；合并单元格表格使用 HTML 表示。

## 4. 直接写入文本，不创建 MD 文件

适合将 AI 输出或脚本生成的 Markdown 直接写入 Word。

```powershell
# 一段文本，必须通过 -o 指定 .docx 文件
.\md2docx.exe --text "正文 **加粗** 和 *斜体*。" -o "文本报告.docx"

# 文本模式默认不覆盖已有文件
.\md2docx.exe --text "更新后的正文" -o "文本报告.docx" --overwrite
```

多行粘贴和管道输入使用 `--stdin`。输入编码为 UTF-8；以下设置保证 PowerShell
向外部程序传递中文时使用 UTF-8，仅作用于当前 PowerShell 会话：

```powershell
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

@'
# 工作报告

## 本周进展

完成 **功能开发**，接下来进行 *验证*。

| 任务 | 状态 |
| --- | --- |
| 文档转换 | 完成 |
'@ | .\md2docx.exe --stdin -o "工作报告.docx"

# - 也表示标准输入
"**一段文字**" | .\md2docx.exe - -o "简报.docx"

# 读取 UTF-8 文本，再通过管道写入 Word
Get-Content "AI输出.txt" -Raw -Encoding UTF8 | .\md2docx.exe --stdin -o "AI输出.docx"
```

`--text`、`--stdin` 和 `-` 不能与 Markdown 文件输入混用。
文本模式保留排版、表格和可编辑公式，默认保留斜体；不插入图片或 Mermaid 图片，
也不生成中间 MD 文件。公式格式可选 `omml` 或 `text`。

## 5. Word 读取为 Markdown 文本

```powershell
# 让 PowerShell 按 UTF-8 接收命令行程序的中文输出
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

# 直接显示 Markdown 文本，不创建 MD 文件和图片目录
.\docx2md.exe "报告.docx" --stdout

# 在 PowerShell 中取得文本，继续交给其他脚本处理
$markdownText = .\docx2md.exe "报告.docx" --stdout
$markdownText
```

`--stdout` 每次只能读取一个 Word 文件，不接受 `-o` 或 `--math-mode image`。
图片会略过，公式输出为 LaTeX，转换提示写入标准错误。
源码入口用于中文管道输出时，建议加 Python 的 `-X utf8` 参数：

```powershell
.\.venv\Scripts\python.exe -X utf8 docx2md.py "报告.docx" --stdout
```

## 6. 模板与排版

文件和文本写入使用相同的 YAML 排版配置。

```powershell
# 内置模板文件
.\md2docx.exe "报告.md" -c "config\thesis.yaml"
.\md2docx.exe "报告.md" -c "config\gongwen.yaml"
.\md2docx.exe "报告.md" -c "config\compact.yaml"

# 使用 GUI 导出的模板，或自己编写的 YAML 模板
.\md2docx.exe "报告.md" -c "我的模板.yaml"

# 临时覆盖正文、标题和行距，可重复使用 --set
.\md2docx.exe "报告.md" --set elements.body.size=小四 --set defaults.line_spacing=1.5 --set "elements.heading1.color=#000000"

# 标题自动编号，并剥离参与编号标题中的手写前缀
.\md2docx.exe "报告.md" --set numbering.headings=true --set numbering.preset=decimal --set numbering.levels=3

# 保留 Markdown 原本的斜体
.\md2docx.exe "报告.md" --set markdown.emphasis_as_bold=false

# 查看最终合并后的配置，不执行转换
.\md2docx.exe --show-config -c "config\thesis.yaml"
```

配置优先级为：默认配置、`-c` 模板、`--set` 临时覆盖；`--math-mode` 优先于
`--set math.mode=...`。模板只需填写希望调整的项目。
通过 `--set` 设置颜色时使用带 `#` 的六位颜色值，并将整个参数加引号。

自动编号只剥离参与编号的标题前缀，正文的 `[1]` 等引文标记保留。
不自动生成 Word 目录；旧模板中的 `output.toc` 和 `output.toc_levels` 会忽略。

## 7. 公式和流程图

```powershell
# Markdown 公式写为可编辑 Word 原生公式，默认方式
.\md2docx.exe "公式.md" --math-mode omml

# 使用内置 KaTeX 渲染为 PNG，再插入 Word
.\md2docx.exe "公式.md" --math-mode image

# 保留 LaTeX 源码文字
.\md2docx.exe "公式.md" --math-mode text

# Word 原生公式导出为 LaTeX，默认方式
.\docx2md.exe "公式.docx" --math-mode latex

# Word 公式导出为 PNG，保存在“公式_images”目录
.\docx2md.exe "公式.docx" --math-mode image

# 不渲染 Mermaid，保留为代码块
.\md2docx.exe "流程图.md" --no-mermaid
```

普通转换、可编辑 Word 公式和 LaTeX 导出不需要浏览器。
公式 PNG 和 Mermaid 图片渲染支持系统 Edge 或 Chrome，浏览器在后台运行。
KaTeX 已内置，可离线渲染，不会自动下载浏览器。
渲染失败会保留源码并提示；普通公式截图不执行 OCR。

## 8. 旧版 .doc 文件

`.docx` 无需额外引擎。`.doc` 需要 LibreOffice，可使用已安装的版本，或主动下载可选引擎：

```powershell
# 仅在执行此命令时下载并启用引擎
.\docx2md.exe --download-engine

# 引擎准备好后转换旧版 Word 文件
.\docx2md.exe "旧报告.doc"

# 旧版文件也能读取为文本
.\docx2md.exe "旧报告.doc" --stdout
```

引擎默认不随便携包提供，下载后缓存供后续使用。默认启动和普通转换不会下载引擎。
`--download-engine` 与 `--stdout` 请分开执行。
可用 `DOCX2MD_LIBREOFFICE` 指定 LibreOffice 可执行程序，用 `DOCX2MD_RUNTIME_DIR` 指定引擎缓存目录。

## 9. 参数速查

### md2docx

| 参数 | 含义 |
| --- | --- |
| 输入文件、目录、通配符 | 读取 Markdown；目录递归查找 `.md` |
| `-o`、`--output` | 单文件输出路径，或批量输出目录；文本模式必须指定 `.docx` |
| `-c`、`--config` | YAML 排版模板路径 |
| `--set KEY=VALUE` | 临时覆盖配置，可重复 |
| `--text TEXT` | 直接写入文本 |
| `--stdin`、输入 `-` | 读取 UTF-8 标准输入 |
| `--overwrite` | 文本模式允许覆盖已有文件 |
| `--math-mode omml/image/text` | Word 原生公式、PNG 或 LaTeX 源码 |
| `--no-mermaid` | 流程图保留为代码块 |
| `--show-config` | 打印实际配置并退出 |
| `--show-paths` | 打印资源路径与打包状态 |
| `-q`、`--quiet` | 减少日志 |
| `-V`、`--version` | 显示版本 |
| `-h`、`--help` | 显示帮助 |

### docx2md

| 参数 | 含义 |
| --- | --- |
| 输入文件、目录、通配符 | 读取 `.docx` 或 `.doc` |
| `-o`、`--output` | Markdown 和图片的输出目录 |
| `-r`、`--recursive` | 目录输入包含子目录 |
| `--overwrite` | 覆盖已有结果，否则自动加编号 |
| `--math-mode latex/image` | LaTeX 或 PNG 公式 |
| `--stdout` | 只输出一个 Word 文件的 Markdown 文本 |
| `--download-engine` | 主动下载并启用 `.doc` 引擎 |
| `-h`、`--help` | 显示帮助 |

## 10. 脚本调用与排查

转换成功返回退出码 `0`；转换失败返回 `1`；参数错误通常返回 `2`。
批量任务只要有文件转换失败，退出码就为 `1`。

```powershell
.\md2docx.exe "报告.md" -o "输出\报告.docx"
if ($LASTEXITCODE -ne 0) {
    throw "Word 转换失败"
}

# 检查配置和资源路径
.\md2docx.exe --show-config
.\md2docx.exe --show-paths
```

提示模板不存在时，请检查 `-c` 路径及当前目录。文本模式提示文件已存在时，
更换输出文件名或使用 `--overwrite`。公式或流程图未渲染时，检查系统 Edge/Chrome 是否可运行。
普通 Word/Markdown 文件转换不受缺少浏览器影响。

更多格式支持和限制见 [主 README](README.md)。
