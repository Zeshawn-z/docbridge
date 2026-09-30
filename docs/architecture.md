# GUI 模块

`gui/workbench.py` 是启动兼容入口，`gui/shell.py` 只负责导航和页面容器。

| 模块 | 职责 |
| --- | --- |
| `window_chrome.py` | 无边框窗口、SVG 窗口按钮、拖动与边缘缩放 |
| `conversion_page.py` | 可复用任务页面，每个实例持有独立队列、状态、输出选项、结果、预览和日志 |
| `task_worker.py` | 接收转换函数与参数快照，后台运行；不判断转换方向 |
| `features/base.py` | 功能接口约定 |
| `features/markdown_to_word.py` | Markdown 排版选项与原 Word 排版引擎适配 |
| `features/word_to_markdown.py` | Word 导出适配 |
| `file_inputs.py` | 文件与目录收集，不依赖任何转换引擎 |
| `report_options.py`、`layout_editor.py` | Markdown 转 Word 专用排版设置 |
| `src/docx2md/legacy.py` | `.doc` 转换引擎查找与调用，不依赖 Qt |
| `src/docx2md/runtime.py` | 用户主动触发的下载、SHA-256 校验、文件准备与本地缓存 |
| `doc_options.py` | `.doc 支持`页与独立下载线程 |

切换页面时不复制、不清空、不重新填充任务状态。后台信号连接到所属页面，即使页面隐藏，结果仍写入该页面。各页面可以同时运行；关闭主窗口会检查所有页面的后台任务。

添加功能时实现 `ConversionFeature` 的元数据、选项、转换函数与结果路径，再在 `features/__init__.py` 注册。窗口和后台线程无需增加按功能判断的分支。也可以给 `MainWindow(features=...)` 传入自己的功能集合。

## `.doc` 运行环境

默认发行包不包含引擎，也不会自动下载。用户在 Word 转 Markdown 的“.doc 支持”页点击“下载并启用”，或运行 `docx2md.py --download-engine`，才会访问官方下载地址。首次下载约 358 MB，准备后占用约 1.2 GB；引擎存放在 `%LOCALAPPDATA%/md2stdreport/runtime/libreoffice/`，可通过 `DOCX2MD_RUNTIME_DIR` 指定位置。启动与切换页面只检查本地文件，不启动引擎。

`legacy.py` 先检查明确设置的 `DOCX2MD_LIBREOFFICE`，再检查按需下载的缓存、兼容手动放置的 `runtime/libreoffice/` 和系统 LibreOffice。每次转换使用独立临时配置目录，输出经过原来的临时目录发布流程，源 `.doc` 文件不会修改。缺少引擎只报告启用入口，不自动下载。

下载模块固定官方版本与 SHA-256，通过 HTTPS 下载；验证通过后使用 `msiexec /a` 提取文件镜像，不进行系统安装。文件准备完成后才发布引擎目录，保留授权与源码地址。下载可取消、失败可重试；文件准备时取消会等待当前操作结束。不同窗口通过文件锁避免重复准备，下载线程不依赖转换任务线程。
