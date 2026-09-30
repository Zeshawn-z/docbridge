"""右侧设置面板。

用「小号灰标签 + 控件」的纵向节奏组织内容，不加卡片、不加分隔线，
靠留白和字重区分层级。

面板分两层：
- 首屏（默认全部展开）：模板、输出、行距与字号、标题编号、选项——覆盖日常
  八成以上的使用场景，一屏看完。
- 详细配置（默认全部收起）：正文、逐级标题、页面、表格、编号逐级覆盖——
  排版规范的全部旋钮都在这里，不用时收起来，面板不会长得吓人。

详细配置里所有控件都遵循同一条规矩：**留空 = 沿用模板**。只有用户真的填过
的东西才会变成覆盖项，免得"打开界面转一遍，模板里写好的规范就没了"。
"""

from __future__ import annotations

import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFileDialog, QGridLayout, QHBoxLayout, QScrollArea,
                               QSizePolicy, QVBoxLayout, QWidget)

from . import config_bridge as bridge
from .theme import Color, Space
from .widgets import (CheckBox, CollapsibleSection, EditableCombo, ElidedLabel,
                      SectionStack, SegmentedControl, SlimComboBox, SlimLineEdit,
                      TextButton, section_label)

from md2docx.config import element_style
from md2docx.units import parse_chars, parse_size, size_name


class _Field(QWidget):
    """标签在上、控件在下的一个设置项。"""

    def __init__(self, label: str, control: QWidget, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Space.TIGHT)
        tag = section_label(label)
        layout.addWidget(tag)
        control.setParent(self)
        layout.addWidget(control)


class SettingsPanel(QWidget):
    changed = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedWidth(Space.SIDEBAR)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        self._output_dir = ""
        self._output_mode = bridge.OUTPUT_ALONGSIDE
        #: 详细配置控件登记表：key → getter，取值时统一走这里
        self._detail: dict[str, object] = {}

        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Space.SECTION)

        layout.addWidget(section_label("转换设置"))

        # 模板
        self._templates = bridge.template_choices()
        self._template_combo = SlimComboBox()
        for item in self._templates:
            self._template_combo.addItem(item["label"])
        self._template_combo.currentIndexChanged.connect(self._on_template)
        self._template_desc = self._hint(self._templates[0]["desc"])
        layout.addWidget(self._wrap(_Field("模板", self._template_combo),
                                   self._template_desc))

        # 输出位置
        self._output_combo = SlimComboBox()
        self._output_combo.addItems(["与源文件同目录", "指定文件夹…"])
        self._output_combo.currentIndexChanged.connect(self._on_output)
        self._output_hint = self._hint("转换结果会生成在 Markdown 旁边")
        layout.addWidget(self._wrap(_Field("输出位置", self._output_combo),
                                   self._output_hint))

        # 行距 + 字号 放在一张网格里，视觉上成组
        grid_host = QWidget()
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(Space.ITEM)

        self._line_spacing = SegmentedControl(bridge.LINE_SPACING_CHOICES, value=1.25)
        self._line_spacing.changed.connect(lambda _v: self.changed.emit())
        grid.addWidget(self._group("行距", self._line_spacing), 0, 0, 1, 2)

        self._body_size = SlimComboBox()
        self._body_size.addItems(bridge.FONT_SIZE_CHOICES)
        self._body_size.setCurrentText("小四")
        self._body_size.currentIndexChanged.connect(lambda _i: self.changed.emit())
        grid.addWidget(self._group("正文字号", self._body_size), 1, 0)

        self._heading_size = SlimComboBox()
        self._heading_size.addItems(["小三", "三号", "四号", "小四"])
        self._heading_size.setCurrentText("小三")
        self._heading_size.currentIndexChanged.connect(lambda _i: self.changed.emit())
        grid.addWidget(self._group("一级标题字号", self._heading_size), 1, 1)
        layout.addWidget(grid_host)

        # 标题自动编号：开关 + 方案 + 层级
        self._numbering_on = CheckBox("标题自动编号", checked=False)
        self._numbering_on.toggled.connect(self._on_numbering_toggle)

        self._numbering_preset = SlimComboBox()
        for name, label in bridge.NUMBERING_CHOICES:
            self._numbering_preset.addItem(label, name)
        self._numbering_preset.currentIndexChanged.connect(lambda _i: self.changed.emit())

        self._numbering_levels = SegmentedControl(
            bridge.NUMBERING_LEVEL_CHOICES, value=3)
        self._numbering_levels.changed.connect(lambda _v: self.changed.emit())

        # 跳过第 1 级：Markdown 的 `#` 常被当作整篇主标题，不该有"一、"
        self._skip_first_level = CheckBox("第 1 级标题不编号（# 作主标题）",
                                          checked=False)
        self._skip_first_level.toggled.connect(lambda _v: self.changed.emit())

        self._strip_prefix = CheckBox("剥离标题里手写的编号", checked=True)
        self._strip_prefix.toggled.connect(lambda _v: self.changed.emit())

        numbering_body = QWidget()
        numbering_layout = QVBoxLayout(numbering_body)
        numbering_layout.setContentsMargins(0, 0, 0, 0)
        numbering_layout.setSpacing(Space.ITEM)
        numbering_layout.addWidget(self._numbering_preset)
        numbering_layout.addWidget(self._group("编号层级", self._numbering_levels))
        numbering_layout.addWidget(self._skip_first_level)
        numbering_layout.addWidget(self._strip_prefix)
        self._numbering_body = numbering_body

        numbering_host = QWidget()
        numbering_host_layout = QVBoxLayout(numbering_host)
        numbering_host_layout.setContentsMargins(0, 0, 0, 0)
        numbering_host_layout.setSpacing(Space.ITEM)
        numbering_host_layout.addWidget(section_label("标题编号"))
        numbering_host_layout.addWidget(self._numbering_on)
        numbering_host_layout.addWidget(numbering_body)
        layout.addWidget(numbering_host)
        self._on_numbering_toggle(False)

        # 选项
        options = QWidget()
        option_layout = QVBoxLayout(options)
        option_layout.setContentsMargins(0, 0, 0, 0)
        option_layout.setSpacing(2)
        self._checks: dict[str, CheckBox] = {}
        for key, text, checked in (
            ("indent", "正文首行缩进 2 字符", True),
            ("mermaid", "mermaid 转成图片", True),
            ("toc", "插入目录", False),
            ("page_number", "页脚页码", False),
        ):
            box = CheckBox(text, checked=checked)
            box.toggled.connect(lambda _v: self.changed.emit())
            self._checks[key] = box
            option_layout.addWidget(box)
        layout.addWidget(self._wrap(section_label("选项"), options))

        # 详细配置。五个分组共用一个外层 layout，全收起时那 16px 的分组间距
        # 加起来有一百多像素、白白把面板顶高，所以把它们收进一个自带容器，
        # 由 `SectionStack` 统一控制收起 / 展开时的节奏。
        layout.addWidget(section_label("详细配置"))
        stack = SectionStack([
            self._build_body_section(),
            self._build_headings_section(),
            self._build_page_section(),
            self._build_table_section(),
            self._build_numbering_format_section(),
        ])
        self._sections = stack.sections()
        layout.addWidget(stack)

        layout.addStretch(1)

        self._reset = TextButton("恢复默认设置", color=Color.TEXT_TERTIARY)
        self._reset.clicked.connect(self.reset)
        layout.addWidget(self._reset, 0, Qt.AlignLeft)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        # 详细配置展开后内容会超出窗口高度，所以必须留滚动能力。用 as-needed
        # 而不是 always-on：内容放得下时滚动条不占位，仍保持"无线条"的观感；
        # 滚动条本身在 QSS 里做成了 8px 的细线，悬停才明显。
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(body)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        # 构造阶段的控件赋值会一路发出 changed，这时候外面还没接上信号，
        # 而且也不是"用户改了参数"，所以等装配完再统一回填一次。
        self.reload_template()

    # ------------------------------------------------------------- 详细配置
    def _detail_rows(self, host_layout: QVBoxLayout, rows: list[list]) -> None:
        """往分组内容里摆若干行。每行是若干 (标签, 控件) 对，横向等分。"""
        for row in rows:
            line = QWidget()
            grid = QHBoxLayout(line)
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setSpacing(8)
            for label, control in row:
                grid.addWidget(_Field(label, control), 1)
            host_layout.addWidget(line)

    def _new_panel(self) -> tuple[QWidget, QVBoxLayout]:
        host = QWidget()
        layout = QVBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Space.FIELD)
        return host, layout

    @staticmethod
    def _editable(items: list[str], value: str, key: str) -> EditableCombo:
        combo = EditableCombo(items)
        combo.setValue(value)
        return combo

    def _blank_flag(self, text: str) -> CheckBox:
        """三态复选框的"三态"在这里体现：勾上就是显式打开。

        想让某一级"不继承模板的加粗"，得能表达出来；但界面又不想再塞一组
        单选按钮，所以约定：勾 = 加粗，不勾 = 沿用模板。想显式取消加粗，
        在模板里写 bold: false。
        """
        box = CheckBox(text, checked=False)
        box.toggled.connect(lambda _v: self.changed.emit())
        return box

    def _build_body_section(self) -> CollapsibleSection:
        host, layout = self._new_panel()
        self._body_font_zh = EditableCombo(bridge.FONT_ZH_CHOICES)
        self._body_font_en = EditableCombo(bridge.FONT_EN_CHOICES)
        self._body_color = SlimLineEdit(placeholder="留空＝随主题")
        self._body_align = SlimComboBox()
        for label, data in bridge.ALIGN_CHOICES:
            self._body_align.addItem(label, data)
        self._body_space_before = SlimLineEdit(placeholder="磅", align_center=True)
        self._body_space_after = SlimLineEdit(placeholder="磅", align_center=True)
        self._body_line_spacing = EditableCombo(bridge.DETAIL_LINE_SPACING_CHOICES)
        self._body_size_detail = EditableCombo(bridge.DETAIL_SIZE_CHOICES)
        self._body_indent = SlimLineEdit(placeholder="如 2字符", align_center=True)
        self._body_left_indent = SlimLineEdit(placeholder="如 0字符", align_center=True)
        self._body_keep_next = self._blank_flag("与下段同页")

        controls = (
            self._body_font_zh, self._body_font_en, self._body_color,
            self._body_align, self._body_space_before, self._body_space_after,
            self._body_line_spacing, self._body_size_detail, self._body_indent,
            self._body_left_indent,
        )
        for control in controls:
            self._bind(control)
        self._body_keep_next.toggled.connect(lambda _v: self.changed.emit())

        self._detail_rows(layout, [
            [("中文字体", self._body_font_zh), ("西文字体", self._body_font_en)],
            [("字号", self._body_size_detail), ("行距", self._body_line_spacing)],
            [("段前（磅）", self._body_space_before), ("段后（磅）", self._body_space_after)],
            [("首行缩进", self._body_indent), ("左缩进", self._body_left_indent)],
            [("对齐", self._body_align), ("字色", self._body_color)],
            [("", self._body_keep_next)],
        ])
        layout.addWidget(self._hint("留空的项按模板走；这里填的会覆盖模板"))
        return CollapsibleSection("正文", host)

    def _build_headings_section(self) -> CollapsibleSection:
        host, layout = self._new_panel()
        self._heading_level = SegmentedControl(
            [("1 级", 1), ("2 级", 2), ("3 级", 3), ("4 级", 4), ("5 级", 5), ("6 级", 6)],
            value=1)
        layout.addWidget(self._group("正在配置", self._heading_level))

        self._h_size = EditableCombo(bridge.DETAIL_SIZE_CHOICES)
        self._h_font_zh = EditableCombo(bridge.FONT_ZH_CHOICES)
        self._h_font_en = EditableCombo(bridge.FONT_EN_CHOICES)
        self._h_color = SlimLineEdit(placeholder="留空＝随主题")
        self._h_align = SlimComboBox()
        for label, data in bridge.ALIGN_CHOICES:
            self._h_align.addItem(label, data)
        self._h_line_spacing = EditableCombo(bridge.DETAIL_LINE_SPACING_CHOICES)
        self._h_space_before = SlimLineEdit(placeholder="磅", align_center=True)
        self._h_space_after = SlimLineEdit(placeholder="磅", align_center=True)
        self._h_indent = SlimLineEdit(placeholder="如 0字符", align_center=True)
        self._h_bold = CheckBox("加粗", checked=False)
        self._h_keep_next = CheckBox("与下段同页", checked=False)
        self._h_page_break = CheckBox("段前分页", checked=False)

        for control in (self._h_size, self._h_font_zh, self._h_font_en,
                        self._h_color, self._h_align, self._h_line_spacing,
                        self._h_space_before, self._h_space_after, self._h_indent):
            self._bind(control)
        for box in (self._h_bold, self._h_keep_next, self._h_page_break):
            box.toggled.connect(self._on_heading_field_changed)

        self._detail_rows(layout, [
            [("字号", self._h_size), ("行距", self._h_line_spacing)],
            [("中文字体", self._h_font_zh), ("西文字体", self._h_font_en)],
            [("段前（磅）", self._h_space_before), ("段后（磅）", self._h_space_after)],
            [("对齐", self._h_align), ("字色", self._h_color)],
            [("首行缩进", self._h_indent), ("加粗", self._h_bold)],
            [("与下段同页", self._h_keep_next), ("段前分页", self._h_page_break)],
        ])
        # 逐级切换：界面只有一套控件，切换时把那一级的实际取值填回来
        self._heading_level.changed.connect(self._on_heading_level_changed)
        self._heading_values: dict[int, dict] = {}
        self._heading_level_index = 1
        return CollapsibleSection("标题层级", host)

    def _build_page_section(self) -> CollapsibleSection:
        host, layout = self._new_panel()
        self._page_size = SlimComboBox()
        self._page_size.addItems(bridge.PAGE_SIZE_CHOICES)
        self._page_size.currentIndexChanged.connect(lambda _i: self.changed.emit())
        self._page_orientation = SegmentedControl(bridge.ORIENTATION_CHOICES,
                                                 value="portrait")
        self._page_orientation.changed.connect(lambda _v: self.changed.emit())
        self._margin_top = SlimLineEdit(align_center=True)
        self._margin_bottom = SlimLineEdit(align_center=True)
        self._margin_left = SlimLineEdit(align_center=True)
        self._margin_right = SlimLineEdit(align_center=True)
        for edit in (self._margin_top, self._margin_bottom, self._margin_left,
                     self._margin_right):
            self._bind(edit)

        self._detail_rows(layout, [
            [("纸张", self._page_size), ("纸张方向", self._page_orientation)],
            [("页边距上", self._margin_top), ("页边距下", self._margin_bottom)],
            [("页边距左", self._margin_left), ("页边距右", self._margin_right)],
        ])
        return CollapsibleSection("页面", host)

    def _build_table_section(self) -> CollapsibleSection:
        host, layout = self._new_panel()
        self._table_width = SlimLineEdit(align_center=True)
        self._table_fill = SlimLineEdit(placeholder="如 F2F2F2", align_center=True)
        self._table_border_color = SlimLineEdit(placeholder="如 7F7F7F",
                                                align_center=True)
        self._table_border_size = SlimLineEdit(align_center=True)
        self._table_valign = SlimComboBox()
        for label, data in bridge.VALIGN_CHOICES:
            self._table_valign.addItem(label, data)
        self._table_fixed = CheckBox("按 tblGrid 固定列宽", checked=False)
        for control in (self._table_width, self._table_fill,
                        self._table_border_color, self._table_border_size):
            self._bind(control)
        self._table_valign.currentIndexChanged.connect(lambda _i: self.changed.emit())
        self._table_fixed.toggled.connect(lambda _v: self.changed.emit())

        self._detail_rows(layout, [
            [("表格宽度 %", self._table_width), ("单元格对齐", self._table_valign)],
            [("表头底纹", self._table_fill), ("边框颜色", self._table_border_color)],
            [("边框粗细", self._table_border_size), ("固定列宽", self._table_fixed)],
        ])
        return CollapsibleSection("表格", host)

    def _build_numbering_format_section(self) -> CollapsibleSection:
        host, layout = self._new_panel()
        self._num_level = SegmentedControl(
            [(f"{i} 级", i) for i in bridge.NUMBERING_FORMAT_LEVELS], value=1)
        layout.addWidget(self._group("正在配置", self._num_level))

        self._num_fmt = SlimComboBox()
        self._num_fmt.addItem("沿用预设", None)
        for value, label in bridge.NUM_FMT_CHOICES:
            self._num_fmt.addItem(label, value)
        self._num_text = SlimLineEdit(placeholder="如 第%1章")
        self._num_suff = SlimComboBox()
        self._num_suff.addItem("沿用预设", None)
        for value, label in bridge.SUFF_CHOICES:
            self._num_suff.addItem(label, value)
        self._num_fmt.currentIndexChanged.connect(self._on_numbering_field_changed)
        self._num_suff.currentIndexChanged.connect(self._on_numbering_field_changed)
        self._bind(self._num_text)

        self._detail_rows(layout, [
            [("编号格式", self._num_fmt)],
            [("编号写法", self._num_text)],
            [("与标题的分隔", self._num_suff)],
        ])
        layout.addWidget(self._hint("%1 %2 代表各级序号，如 第%1章 / %1.%2"))

        self._num_level.changed.connect(self._on_num_level_changed)
        self._num_values: dict[int, dict] = {}
        self._num_level_index = 1
        return CollapsibleSection("编号逐级覆盖", host)

    # ------------------------------------------------------------------ 绑定
    def _bind(self, control: QWidget) -> None:
        """把详细配置里的控件统一挂上"变了就通知"的钩子。"""
        self._detail[id(control)] = control
        if isinstance(control, SlimComboBox):
            control.currentIndexChanged.connect(lambda _i: self.changed.emit())
        elif isinstance(control, EditableCombo):
            control.currentTextChanged.connect(lambda _t: self.changed.emit())
        elif isinstance(control, SlimLineEdit):
            control.textChanged.connect(lambda _t: self.changed.emit())

    def _on_heading_field_changed(self, *_args) -> None:
        self._changed = True
        self.changed.emit()

    def _on_numbering_field_changed(self, *_args) -> None:
        self.changed.emit()

    # ------------------------------------------------------------------ 组装
    def _hint(self, text: str = ""):
        label = ElidedLabel(text)
        # 提示文字要能跟着面板宽度收缩，否则会把布局顶宽
        label.setMinimumWidth(120)
        return label

    def _group(self, label: str, control: QWidget) -> QWidget:
        return _Field(label, control)

    def _wrap(self, *widgets: QWidget) -> QWidget:
        host = QWidget()
        layout = QVBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Space.TIGHT)
        for widget in widgets:
            layout.addWidget(widget)
        return host

    # ------------------------------------------------------------------ 取值
    def sections(self) -> list[CollapsibleSection]:
        """五个详细配置分组，供自检与截图工具统一展开/收起。"""
        return list(self._sections)

    def template_path(self) -> str | None:
        index = self._template_combo.currentIndex()
        if 0 <= index < len(self._templates):
            return self._templates[index]["path"]
        return None

    def template_label(self) -> str:
        return self._template_combo.currentText()

    def output_mode(self) -> str:
        return self._output_mode

    def output_dir(self) -> str:
        return self._output_dir

    def overrides(self) -> dict:
        return bridge.build_overrides(
            **self._first_screen_overrides(),
            heading_numbering=(self._numbering_preset.currentData()
                               if self._numbering_on.isChecked() else None),
            numbering_levels=(self._numbering_levels.value()
                              if self._numbering_on.isChecked() else None),
            skip_first_level=self._numbering_flag(
                "skip_first_level", self._skip_first_level.isChecked()),
            strip_prefix=self._numbering_flag(
                "strip_text_prefix", self._strip_prefix.isChecked()),
            body=self._body_values(),
            headings={level: self.heading_overrides(level)
                      for level in bridge.HEADING_LEVELS},
            page=self._page_values(),
            table=self._table_values(),
            numbering_format={level: self.numbering_format_overrides(level)
                              for level in bridge.NUMBERING_FORMAT_LEVELS},
        )

    def _numbering_flag(self, key: str, current: bool):
        """编号相关的开关，跟模板比过之后再决定要不要覆盖。

        沿用首屏那套约定：**与模板一致就不产生覆盖项**，返回 None 让 bridge
        跳过。否则用户打开一个 `skip_first_level: true` 的模板时，界面上没勾
        的复选框会被当成"显式关掉"，把模板的取值顶掉。

        跟模板不一致时要能表达两个方向：勾上而模板没开 → True，
        没勾而模板开着 → False。两者都靠 `is not None` 放行。
        """
        if not self._numbering_on.isChecked():
            return None
        base = getattr(self, "_base_config", {}) or {}
        template = bool((base.get("numbering") or {}).get(key, False))
        return None if current == template else current

    def base_overrides(self) -> dict:
        """接上模板后必然产生的覆盖项（首屏那几项），供自检核对。"""
        return bridge.build_overrides(**self._first_screen_overrides())

    # -- 差异比较 --------------------------------------------------------
    # 详细配置的控件里填的是"模板当前的取值"，方便用户照着改。但只要用户没
    # 亲手动过，就不该生成覆盖项——否则模板里的全局旋钮会被这些回填出来的
    # 同名数值按元素钉死。所以取值时跟模板快照比一比，一致的一律跳过。
    @staticmethod
    def _raw(value) -> str:
        if value is None:
            return ""
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value).strip()

    def _param_diff(self, current, template) -> str:
        text = self._raw(current)
        if not text:
            return ""                                  # 留空＝沿用模板
        if text == self._raw(template):
            return ""                                  # 跟模板一样，不算改过
        return text

    def _flag_diff(self, current: bool, template) -> str:
        """开关类参数：只有跟模板不同才产出覆盖项。

        返回值刻意用 `_param_diff` 那套空串约定——界面上的复选框只有"开/关"
        两种表达，没改过必须能被认出来，否则会变成"显式打开"而把模板的取值
        顶掉。返回空串即"沿用模板"。
        """
        if not current:
            return ""
        return "" if bool(template) else "true"

    # -- 首屏项的差异比较 -------------------------------------------------
    def _first_screen_overrides(self) -> dict:
        """首屏那几项与模板比较后再决定要不要覆盖。

        首屏的「行距」「正文字号」是全局旋钮，模板里通常也写了自己的取值。
        用户没动它们的时候不该覆盖，否则切到学位论文模板（1.5 倍行距）会被
        界面按 1.25 钉死——这条路径和详细配置一样要走差异比较。
        """
        base = getattr(self, "_base_config", {}) or {}
        out: dict = {}

        spacing = float(self._line_spacing.value())
        want_spacing = float((base.get("defaults") or {}).get("line_spacing", 1.25))
        if abs(spacing - want_spacing) > 1e-6:
            out["line_spacing"] = spacing

        # 要比的是"合并后这一级实际用什么字号"，不是 elements.body 里那几行字。
        # 默认规范的正文字号写在 defaults 里，只看 elements 会以为没设过。
        body = element_style(base, "body")
        heading1 = element_style(base, "heading1")
        body_size = size_name(parse_size(body.get("size", "小四")))
        heading_size = size_name(parse_size(heading1.get("size", "小三")))
        if self._body_size.currentText() != body_size:
            out["body_size"] = self._body_size.currentText()
        if self._heading_size.currentText() != heading_size:
            out["heading_size"] = self._heading_size.currentText()

        flags = {
            "first_line_indent": (
                self._checks["indent"].isChecked(),
                parse_chars(body.get("first_line_indent") or 0) not in (None, 0.0),
            ),
            "mermaid": (self._checks["mermaid"].isChecked(),
                        (base.get("mermaid") or {}).get("renderer", "auto") != "off"),
            "toc": (self._checks["toc"].isChecked(),
                    bool((base.get("output") or {}).get("toc", False))),
            "page_number": (self._checks["page_number"].isChecked(),
                            bool((base.get("page") or {}).get("footer_page_number",
                                                              False))),
        }
        for key, (current, template) in flags.items():
            if current != template:
                out[key] = current
        return out

    def _body_values(self) -> dict:
        keys = ("size", "font_zh", "font_en", "color", "align", "line_spacing",
                "space_before", "space_after", "first_line_indent", "left_indent")
        base = getattr(self, "_body_snapshot", {}) or {}
        current = {
            "size": self._body_size_detail.value(),
            "font_zh": self._body_font_zh.value(),
            "font_en": self._body_font_en.value(),
            "color": self._body_color.value(),
            "align": self._body_align.currentData() or "",
            "line_spacing": self._body_line_spacing.value(),
            "space_before": self._body_space_before.value(),
            "space_after": self._body_space_after.value(),
            "first_line_indent": self._body_indent.value(),
            "left_indent": self._body_left_indent.value(),
        }
        out = {key: self._param_diff(current[key], base.get(key)) for key in keys}
        flag = self._flag_diff(self._body_keep_next.isChecked(),
                               base.get("keep_with_next"))
        out["keep_with_next"] = flag
        return out

    def _current_heading(self) -> dict:
        return {
            "size": self._h_size.value(),
            "font_zh": self._h_font_zh.value(),
            "font_en": self._h_font_en.value(),
            "color": self._h_color.value(),
            "align": self._h_align.currentData() or "",
            "line_spacing": self._h_line_spacing.value(),
            "space_before": self._h_space_before.value(),
            "space_after": self._h_space_after.value(),
            "first_line_indent": self._h_indent.value(),
            "bold": self._h_bold.isChecked(),
            "keep_with_next": self._h_keep_next.isChecked(),
            "page_break_before": self._h_page_break.isChecked(),
        }

    def heading_overrides(self, level: int) -> dict:
        """某一级的覆盖项——与模板一致的项自动丢掉。

        正在配置的那一级直接读控件：用户改完不一定马上切走，靠"切换时写回"
        会把这批改动丢掉。
        """
        base = self._base_heading(level)
        if level == self._heading_level_index:
            current = self._current_heading()
        else:
            current = dict(self._heading_values.get(level) or {})
        out: dict = {}
        for key, value in current.items():
            if key in ("bold", "keep_with_next", "page_break_before"):
                out[key] = self._flag_diff(value, base.get(key))
                continue
            out[key] = self._param_diff(value, base.get(key))
        return out

    def _base_heading(self, level: int) -> dict:
        return (getattr(self, "_heading_snapshots", {}) or {}).get(level, {})

    def _page_values(self) -> dict:
        base = getattr(self, "_page_snapshot", {}) or {}
        values = {
            "size": self._page_size.currentText(),
            "orientation": self._page_orientation.value(),
            "margin_top": self._margin_top.value(),
            "margin_bottom": self._margin_bottom.value(),
            "margin_left": self._margin_left.value(),
            "margin_right": self._margin_right.value(),
        }
        return {key: self._param_diff(value, base.get(key))
                for key, value in values.items()}

    def page_footer_flag(self) -> bool:
        """页脚页码：首屏复选框与详细配置里的页面快照共用一个开关。"""
        return self._checks["page_number"].isChecked()

    def toc_flag(self) -> bool:
        return self._checks["toc"].isChecked()

    def _table_values(self) -> dict:
        base = getattr(self, "_table_snapshot", {}) or {}
        current = {
            "width_pct": self._table_width.value(),
            "header_fill": self._table_fill.value(),
            "border_color": self._table_border_color.value(),
            "border_size": self._table_border_size.value(),
            "valign": self._table_valign.currentData() or "",
        }
        out = {key: self._param_diff(current[key], base.get(key))
               for key in current}
        out["fixed_layout"] = self._flag_diff(self._table_fixed.isChecked(),
                                              base.get("fixed_layout"))
        return out

    def numbering_format_overrides(self, level: int) -> dict:
        """某一级的编号覆盖——同样优先读控件，避免"改完还没切走"的改动丢失。"""
        base = (getattr(self, "_num_snapshot", {}) or {}).get(level, {})
        if level == self._num_level_index:
            current = self._current_num_format()
        else:
            current = self._num_values.get(level) or {}
        out: dict = {}
        for key in ("num_fmt", "text", "suff"):
            out[key] = self._param_diff(current.get(key), base.get(key))
        return out

    def output_target(self, src_path: str) -> str:
        """按当前设置算出某个源文件对应的输出路径。"""
        stem = os.path.splitext(os.path.basename(src_path))[0]
        if self._output_mode == bridge.OUTPUT_FOLDER and self._output_dir:
            return os.path.join(self._output_dir, stem + ".docx")
        return os.path.join(os.path.dirname(os.path.abspath(src_path)), stem + ".docx")

    def effective_output_dir(self, sources: list[str]) -> str:
        if self._output_mode == bridge.OUTPUT_FOLDER and self._output_dir:
            return self._output_dir
        if sources:
            return os.path.dirname(os.path.abspath(sources[0]))
        return ""

    # ------------------------------------------------------------------ 回填
    def apply_config(self, config: dict) -> None:
        """把当前模板的取值回填到详细配置里。

        打开详细分组时，用户看到的应该是"这个模板现在长什么样"，而不是一片
        空白——否则根本不知道自己改的是什么。回填只影响显示：取值时会把控件里
        的值跟这份快照比一比，一致的就不生成覆盖项（见 `_param_diff`）。
        """
        self._body_snapshot = bridge.element_snapshot(config, "body")
        self._heading_snapshots = {}
        self._heading_values = {}
        for level in bridge.HEADING_LEVELS:
            snapshot = bridge.element_snapshot(config, f"heading{level}")
            self._heading_snapshots[level] = self._snapshot_to_values(snapshot)
            self._heading_values[level] = dict(self._heading_snapshots[level])
        self._heading_level_index = self._heading_level.value()
        self._load_heading(self._heading_level_index)

        page = bridge.page_snapshot(config)
        self._page_snapshot = dict(page)
        self._set_combo(self._page_size, page["size"])
        self._page_orientation.setValue(page["orientation"], animate=False)
        for edit, key in ((self._margin_top, "margin_top"),
                          (self._margin_bottom, "margin_bottom"),
                          (self._margin_left, "margin_left"),
                          (self._margin_right, "margin_right")):
            edit.setValue(page[key])

        table = bridge.table_snapshot(config)
        self._table_snapshot = dict(table)
        self._table_width.setValue(table["width_pct"])
        self._table_fill.setValue(table["header_fill"])
        self._table_border_color.setValue(table["border_color"])
        self._table_border_size.setValue(table["border_size"])
        self._set_combo_value(self._table_valign, bridge.VALIGN_CHOICES,
                              table["valign"])
        self._table_fixed.setChecked(table["fixed_layout"], animate=False)

        numbering = bridge.numbering_snapshot(config)
        self._num_snapshot = {}
        self._num_values = {}
        for level in bridge.NUMBERING_FORMAT_LEVELS:
            spec = numbering["format"].get(level) or {}
            self._num_snapshot[level] = {
                "num_fmt": spec.get("num_fmt") or "",
                "text": spec.get("text") or "",
                "suff": spec.get("suff") or "",
            }
            self._num_values[level] = dict(self._num_snapshot[level])
        self._num_level_index = self._num_level.value()
        self._load_num_format(self._num_level_index)
        self.apply_body_snapshot()

    def apply_body_snapshot(self) -> None:
        """正文分组的显示值——回填时不被首屏的字号/行距覆盖掉。"""
        snapshot = getattr(self, "_body_snapshot", None)
        if not snapshot:
            return
        self._body_size_detail.setValue(snapshot["size"])
        self._body_font_zh.setValue(snapshot["font_zh"])
        self._body_font_en.setValue(snapshot["font_en"])
        self._body_color.setValue("" if snapshot["color"] == "auto" else snapshot["color"])
        self._set_combo_value(self._body_align, bridge.ALIGN_CHOICES,
                              snapshot["align"])
        self._body_line_spacing.setValue(snapshot["line_spacing"])
        self._body_space_before.setValue(snapshot["space_before"])
        self._body_space_after.setValue(snapshot["space_after"])
        self._body_indent.setValue(snapshot["first_line_indent"])
        self._body_left_indent.setValue(snapshot["left_indent"])
        self._body_keep_next.setChecked(snapshot["keep_with_next"], animate=False)

    @staticmethod
    def _snapshot_to_values(snapshot: dict) -> dict:
        return {
            "size": snapshot["size"],
            "font_zh": snapshot["font_zh"],
            "font_en": snapshot["font_en"],
            "color": "" if snapshot["color"] == "auto" else snapshot["color"],
            "align": snapshot["align"],
            "line_spacing": snapshot["line_spacing"],
            "space_before": snapshot["space_before"],
            "space_after": snapshot["space_after"],
            "first_line_indent": snapshot["first_line_indent"],
            "bold": snapshot["bold"],
            "keep_with_next": snapshot["keep_with_next"],
            "page_break_before": snapshot["page_break_before"],
        }

    def _load_heading(self, level: int) -> None:
        """把某一级的取值填进界面控件（切换层级与回填模板都走这里）。"""
        values = (self._heading_values or {}).get(level)
        if not values:
            return
        self._h_size.setValue(values["size"])
        self._h_font_zh.setValue(values["font_zh"])
        self._h_font_en.setValue(values["font_en"])
        self._h_color.setValue(values["color"])
        self._set_combo_value(self._h_align, bridge.ALIGN_CHOICES, values["align"])
        self._h_line_spacing.setValue(values["line_spacing"])
        self._h_space_before.setValue(values["space_before"])
        self._h_space_after.setValue(values["space_after"])
        self._h_indent.setValue(values["first_line_indent"])
        self._h_bold.setChecked(bool(values["bold"]), animate=False)
        self._h_keep_next.setChecked(bool(values["keep_with_next"]), animate=False)
        self._h_page_break.setChecked(bool(values["page_break_before"]), animate=False)

    def _load_num_format(self, level: int) -> None:
        spec = (self._num_values or {}).get(level) or {}
        self._set_combo_data(self._num_fmt, spec.get("num_fmt") or None)
        self._num_text.setValue(spec.get("text") or "")
        self._set_combo_data(self._num_suff, spec.get("suff") or None)

    @staticmethod
    def _set_combo(combo: SlimComboBox, text: str) -> None:
        index = combo.findText(str(text))
        if index >= 0:
            combo.setCurrentIndex(index)

    @staticmethod
    def _set_combo_value(combo: SlimComboBox, choices: list[tuple[str, str]],
                         value: str) -> None:
        """按取值选中下拉项（choices 是 (展示文案, 取值)）。"""
        for index, (_label, data) in enumerate(choices):
            if data == value:
                combo.setCurrentIndex(index)
                return

    @staticmethod
    def _set_combo_data(combo: SlimComboBox, data) -> None:
        index = combo.findData(data)
        combo.setCurrentIndex(index if index >= 0 else 0)

    # ------------------------------------------------------------------ 交互
    def _on_template(self, index: int) -> None:
        if 0 <= index < len(self._templates):
            self._template_desc.setText(self._templates[index]["desc"])
        self.reload_template()
        self.changed.emit()

    def reload_template(self) -> None:
        """按当前模板把详细配置的显示值刷一遍。

        切换模板后详细分组里显示的应该是新模板的取值，否则用户看到的是上一个
        模板的数值，照着改就会写出莫名其妙的覆盖项。
        """
        from md2docx.config import load_config

        try:
            config = load_config(self.template_path(), None)
        except Exception:  # noqa: BLE001
            return
        self._base_config = config
        self._sync_first_screen(config)
        self.apply_config(config)

    def _sync_first_screen(self, config: dict) -> None:
        """把首屏的快捷项对齐到模板，让界面显示的与模板一致。"""
        line = (config.get("defaults") or {}).get("line_spacing")
        try:
            self._line_spacing.setValue(float(line), animate=False)
        except (TypeError, ValueError):
            pass
        body = (config.get("elements") or {}).get("body") or {}
        if body.get("size"):
            self._body_size.setCurrentText(str(body["size"]))
        heading1 = (config.get("elements") or {}).get("heading1") or {}
        if heading1.get("size") and self._heading_size.findText(
                str(heading1["size"])) >= 0:
            self._heading_size.setCurrentText(str(heading1["size"]))

        body_indent = (config.get("elements") or {}).get("body") or {}
        self._checks["indent"].setChecked(
            parse_chars(body_indent.get("first_line_indent") or 0) not in (None,
                                                                          0.0),
            animate=False)
        self._checks["mermaid"].setChecked(
            (config.get("mermaid") or {}).get("renderer", "auto") != "off",
            animate=False)
        self._checks["toc"].setChecked(
            bool((config.get("output") or {}).get("toc", False)), animate=False)
        self._checks["page_number"].setChecked(
            bool((config.get("page") or {}).get("footer_page_number", False)),
            animate=False)

        numbering = (config.get("numbering") or {}).get("headings", False)
        enabled = bool(numbering)
        self._numbering_on.setChecked(enabled, animate=False)
        preset = (config.get("numbering") or {}).get("preset")
        if preset:
            index = self._numbering_preset.findData(preset)
            if index >= 0:
                self._numbering_preset.setCurrentIndex(index)
        levels = int((config.get("numbering") or {}).get("levels", 3) or 3)
        self._numbering_levels.setValue(levels, animate=False)
        self._skip_first_level.setChecked(
            bool((config.get("numbering") or {}).get("skip_first_level", False)),
            animate=False)
        self._strip_prefix.setChecked(
            bool((config.get("numbering") or {}).get("strip_text_prefix", True)),
            animate=False)

    def _on_output(self, index: int) -> None:
        if index == 1:
            folder = QFileDialog.getExistingDirectory(self, "选择导出目录",
                                                     bridge.default_output_dir())
            if folder:
                self._output_mode = bridge.OUTPUT_FOLDER
                self._output_dir = folder
                self._output_hint.setText(folder)
                self._output_hint.setToolTip(folder)
            else:
                self._output_combo.blockSignals(True)
                self._output_combo.setCurrentIndex(0)
                self._output_combo.blockSignals(False)
                self._output_mode = bridge.OUTPUT_ALONGSIDE
                self._output_hint.setText("转换结果会生成在 Markdown 旁边")
        else:
            self._output_mode = bridge.OUTPUT_ALONGSIDE
            self._output_hint.setText("转换结果会生成在 Markdown 旁边")
        self.changed.emit()

    def _on_numbering_toggle(self, checked: bool) -> None:
        """没开编号时把方案选项收起来，避免设置面板上出现一堆无效控件。"""
        self._numbering_body.setVisible(checked)
        self.changed.emit()

    def _on_heading_level_changed(self, level) -> None:
        """切换标题层级：先把上一级界面上的改动存下来，再载入新的一级。"""
        previous = self._heading_level_index
        if previous != level:
            self._heading_values[previous] = self._current_heading()
        self._heading_level_index = int(level)
        self._load_heading(int(level))
        self.changed.emit()

    def _on_num_level_changed(self, level) -> None:
        previous = self._num_level_index
        if previous != level:
            self._num_values[previous] = self._current_num_format()
        self._num_level_index = int(level)
        self._load_num_format(int(level))
        self.changed.emit()

    def _current_num_format(self) -> dict:
        return {
            "num_fmt": self._num_fmt.currentData() or "",
            "text": self._num_text.value(),
            "suff": self._num_suff.currentData() or "",
        }

    def reset(self) -> None:
        self._template_combo.setCurrentIndex(0)
        self._output_combo.setCurrentIndex(0)
        self._output_mode = bridge.OUTPUT_ALONGSIDE
        self._output_dir = ""
        self._output_hint.setText("转换结果会生成在 Markdown 旁边")
        self._line_spacing.setValue(1.25)
        self._body_size.setCurrentText("小四")
        self._heading_size.setCurrentText("小三")
        self._numbering_on.setChecked(False)
        self._numbering_preset.setCurrentIndex(0)
        self._numbering_levels.setValue(3)
        self._skip_first_level.setChecked(False)
        self._strip_prefix.setChecked(True)
        for key, box in self._checks.items():
            box.setChecked(key in ("indent", "mermaid"))
        self._reset_detail()
        self.changed.emit()

    def _reset_detail(self) -> None:
        """详细配置回到"默认规范"的样子，而不是一片空白。"""
        from md2docx.config import load_config

        try:
            config = load_config(None, None)
        except Exception:  # noqa: BLE001
            return
        self.apply_config(config)

    # ------------------------------------------------------------------ 初始化
    def load_initial_template(self) -> None:
        """构造完成后把"默认规范"的取值填进详细配置。"""
        self.reload_template()
