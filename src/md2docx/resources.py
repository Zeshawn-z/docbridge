"""资源定位：区分"只读的打包资源"与"用户可见的可写目录"。

源码运行时两者都指向项目根目录；被 PyInstaller 冻结成 exe 之后就不是一回事了：

- **只读资源**（默认配置模板、mermaid 内核）随 exe 一起打包，PyInstaller 会把它们
  解到 `sys._MEIPASS` 指向的临时目录。这个目录每次启动都可能不同，且不该被写入。
- **可写目录**是 exe 自己所在的目录。用户可以在这里放 `config/` 覆盖内置模板，
  也能直接看到自己加的模板——便携软件的常规做法。

所以取路径一律走这里的函数，不要再用 `os.path.dirname(__file__)` 往上推。
"""

from __future__ import annotations

import os
import sys

#: 是否运行在冻结环境（PyInstaller / cx_Freeze 等）
IS_FROZEN = bool(getattr(sys, "frozen", False))


def _module_file() -> str:
    return os.path.abspath(__file__)


def project_root() -> str:
    """源码布局下的项目根目录（src/md2docx/resources.py 往上三层）。"""
    return os.path.dirname(os.path.dirname(os.path.dirname(_module_file())))


def resource_root() -> str:
    """只读资源的根目录。"""
    if IS_FROZEN:
        base = getattr(sys, "_MEIPASS", None)
        if base:
            return base
        return os.path.dirname(os.path.abspath(sys.executable))
    return project_root()


def app_root() -> str:
    """可写、用户能看到的目录：冻结后是 exe 所在目录。"""
    if IS_FROZEN:
        return os.path.dirname(os.path.abspath(sys.executable))
    return project_root()


# --------------------------------------------------------------------------
# 配置模板
# --------------------------------------------------------------------------

def bundled_config_dir() -> str:
    return os.path.join(resource_root(), "config")


def user_config_dir() -> str:
    return os.path.join(app_root(), "config")


def config_dirs() -> list[str]:
    """按优先级返回要搜索模板的目录，前面的同名文件优先。"""
    dirs = []
    for candidate in (user_config_dir(), bundled_config_dir()):
        real = os.path.abspath(candidate)
        if real not in dirs and os.path.isdir(real):
            dirs.append(real)
    return dirs


def config_files() -> dict[str, str]:
    """模板名 → 绝对路径。用户目录里的同名模板覆盖打包内的。"""
    found: dict[str, str] = {}
    for directory in reversed(config_dirs()):     # 反向遍历 → 高优先级后写入生效
        for name in sorted(os.listdir(directory)):
            if name.lower().endswith((".yaml", ".yml")):
                found[name] = os.path.join(directory, name)
    return found


def default_config_path() -> str:
    """默认规范的路径。优先取用户目录里那份，方便用户整体替换排版规范。"""
    for directory in config_dirs():
        candidate = os.path.join(directory, "default.yaml")
        if os.path.exists(candidate):
            return candidate
    return os.path.join(bundled_config_dir(), "default.yaml")


def writable_config_dir() -> str:
    """用户放自定义模板的目录（不存在则返回待创建的路径）。"""
    return user_config_dir()


# --------------------------------------------------------------------------
# mermaid 内核
# --------------------------------------------------------------------------

def vendor_dir() -> str:
    return os.path.join(resource_root(), "tools", "vendor")


def mermaid_js_path() -> str:
    return os.path.join(vendor_dir(), "mermaid.min.js")


def describe() -> str:
    """给 --show-paths / 自检用的环境说明。

    每行末尾标出该路径当前是否存在——排查"打包后缺文件"时一眼就能看到，
    不用再去猜哪个目录没带上。
    """
    config_path = default_config_path()
    mermaid_path = mermaid_js_path()
    return "\n".join([
        f"frozen={IS_FROZEN}",
        f"resource_root={resource_root()}",
        f"app_root={app_root()}",
        f"config_dirs={config_dirs()}",
        f"default_config={config_path} [{_mark(config_path)}]",
        f"mermaid_js={mermaid_path} [{_mark(mermaid_path)}]",
    ])


def _mark(path: str) -> str:
    return "OK" if os.path.exists(path) else "MISSING"
