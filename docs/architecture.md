# GUI 模块

`gui/workbench.py` 是启动兼容入口，`gui/shell.py` 只负责导航和页面容器。

| 模块 | 职责 |
| --- | --- |
| `window_chrome.py` | 圆角无边框窗口、右上角 SVG 窗口按钮、页首和侧栏拖动与边缘缩放 |
| `conversion_page.py` | 可复用任务页面，每个实例持有独立队列、状态、输出选项、结果、预览和日志 |
| `task_worker.py` | 接收转换函数与参数快照，后台运行；不判断转换方向 |
| `text_pages.py`、`text_worker.py` | 两个简单文本页面及独立的后台文本任务，不复用文件队列状态 |
| `features/text.py` | 粘贴转 Word 和 Word 转文本页面注册 |
| `src/docbridge_text/` | 无 Qt 的文本读写接口，GUI 与 CLI 共用，直接读写内存文本 |
| `features/base.py` | 功能接口约定 |
| `features/markdown_to_word.py` | Markdown 排版选项与原 Word 排版引擎适配 |
| `features/word_to_markdown.py` | Word 导出适配 |
| `file_inputs.py` | 文件与目录收集，不依赖任何转换引擎 |
| `report_options.py`、`layout_editor.py` | 两个 Word 写入页面共用的排版入口与弹窗，各自持有模板和修改项 |
| `src/docx2md/legacy.py` | `.doc` 转换引擎查找与调用，不依赖 Qt |
| `src/docx2md/runtime.py` | 用户主动触发的下载、SHA-256 校验、文件准备与本地缓存 |
| `doc_options.py` | `.doc 支持`页与独立下载线程 |
| `formula_options.py` | 公式输出选项，独立于排版和下载引擎 |
| `formula_preview.py` | Qt 公式图片预览，源码保持原样 |
| `src/docbridge_math/` | LaTeX、MathML、OMML 与 PNG 转换，不依赖 Qt 或任务状态 |

切换页面时不复制、不清空、不重新填充任务状态。后台信号连接到所属页面，即使页面隐藏，结果仍写入该页面。各页面可以同时运行；关闭主窗口会检查所有页面的后台任务。

添加功能时实现 `ConversionFeature` 的元数据、选项、转换函数与结果路径，再在 `features/__init__.py` 注册。窗口和后台线程无需增加按功能判断的分支。也可以给 `MainWindow(features=...)` 传入自己的功能集合。

不使用文件队列的功能可提供 `create_page(parent)` 自行创建页面，仍通过同一个注册表加入导航。
页面提供 `header`、`workspace`、`busy`、`add_files()` 和 `start()`，供窗口拖动、圆角、快捷键及关闭检查使用。
文本页面的输入、设置、结果和线程均属于页面自身，切换功能不会修改其他任务。

`docbridge_text.write_docx()` 使用原排版引擎并禁用图片，直接生成临时 DOCX 后替换目标，
不会创建临时 MD；默认沿用排版并保留 Markdown 斜体语义。`read_docx()` 以无资源目录的
`DocxReader` 读取正文，跳过图片，无法表达的公式只保留文字并提示，不生成 XML 附件。
CLI 的 `--text` / `--stdin` / `-` 和 `--stdout` 共用这些接口。

功能可选提供 `create_output_options(parent)`，返回带 `values()` 的控件；任务页面将其值合入
后台参数快照，转换开始后锁定该控件。Word 读取的公式格式通过这个接口接入；Word 写入的公式格式
位于排版弹窗中，使用 `math.mode` 配置，不在输出页重复展示。

排版弹窗使用模板配置叠加修改项计算实际值，再回填控件。程序回填不触发修改信号，因此查看或
切换样式不会把模板默认值固定成逐元素覆盖。布尔控件为双态复选框，显式取消勾选会保存 `false`。
模板选择、导入和导出集中在“模板”分类，换模板会重建基准配置并清除旧的修改项；对话框取消
不会改变所属页面。高级 YAML 显示完整实际配置，通过差异保存修改项。复选框勾选图形由本地 SVG 提供。

## 公式后端

Markdown 公式分隔符由 markdown-it 插件解析，代码块和行内代码保持原样。`codec.py` 使用
latex2mathml 解析，再用 mathml2omml 生成原生 Word 公式；修正该库的常见重音与横线节点。
PNG 路径在 `katex.py` 中运行本地 KaTeX，通过本机 Edge / Chrome 的 Chromium DevTools
协议捕获 288 dpi 图片。KaTeX 脚本、CSS 和字体随三个 EXE 打包，浏览器按需启动，
只读取回环 HTTP 服务提供的静态资源；公式通过 JSON 参数传入，不写入 HTML 文件。
测量等待字体加载和布局完成，图片尺寸与行内基线一起返回。可编辑公式不依赖浏览器。

浏览器使用独立临时配置目录，不连接用户现有窗口；多个转换页面共享一个渲染进程，
请求串行执行，重复公式缓存图片。宏定义不跨公式共享。退出时关闭自身进程并清理
自身配置目录。缺少浏览器、解析或截图失败均报告 `FormulaError`，继续原有保留内容的流程。

`omml.py` 读取常见 Office Math 结构，保持分式、脚标、根号、矩阵与运算符结构。
无法表达的节点报告提示，并导出原始 XML，避免把复杂公式静默压成文字。
公式 PNG 的 Word 替代文字携带原始 LaTeX，支持本程序生成图片的再次导出。

Word 导出公式资源继续使用临时目录与回滚发布流程；Markdown 转 Word 的 PNG 直接嵌入
DOCX，不留下临时图片。预览独立于输出格式，不会修改原文件或生成的 Markdown。

## `.doc` 运行环境

默认发行包不包含引擎，也不会自动下载。用户在 Word 转 Markdown 的“.doc 支持”页点击“下载并启用”，或运行 `docx2md.py --download-engine`，才会访问官方下载地址。首次下载约 358 MB，准备后占用约 1.2 GB；引擎存放在 `%LOCALAPPDATA%/md2stdreport/runtime/libreoffice/`，可通过 `DOCX2MD_RUNTIME_DIR` 指定位置。启动与切换页面只检查本地文件，不启动引擎。

`legacy.py` 先检查明确设置的 `DOCX2MD_LIBREOFFICE`，再检查按需下载的缓存、兼容手动放置的 `runtime/libreoffice/` 和系统 LibreOffice。每次转换使用独立临时配置目录，输出经过原来的临时目录发布流程，源 `.doc` 文件不会修改。缺少引擎只报告启用入口，不自动下载。

下载模块固定官方版本与 SHA-256，通过 HTTPS 下载；验证通过后使用 `msiexec /a` 提取文件镜像，不进行系统安装。文件准备完成后才发布引擎目录，保留授权与源码地址。下载可取消、失败可重试；文件准备时取消会等待当前操作结束。不同窗口通过文件锁避免重复准备，下载线程不依赖转换任务线程。

## 自动发布

`packaging/release.py` 在构建前选择版本，同一来源提交复用已有版本；主分支新增提交递增补丁号，手动提高源码基线可升级大版本或小版本。构建过程把选定版本写入临时检出的源码，使 CLI、Windows 属性和 ZIP 名称一致。

只有主分支成功构建和验证后，独立发布任务才获得写入权限；PR 仅构建。发布版本提交只写入标签、不回写主分支。标签记录来源提交，支持重跑恢复；Release 先以草稿创建，上传四个程序/压缩包及 SHA-256 清单后再公开。工作流串行执行发布，避免同时分配同一版本。
