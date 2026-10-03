"""Word-style formatting categories with visible per-level style selection."""
import copy
import html
import re
import yaml
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QComboBox, QPushButton, QDialogButtonBox, QLineEdit, QPlainTextEdit,
    QMessageBox, QScrollArea, QWidget, QListWidget, QListWidgetItem,
    QStackedWidget, QGroupBox, QColorDialog, QCheckBox, QFileDialog)
from PySide6.QtGui import QColor
from md2docx.config import load_config, element_style, heading_numbering
from md2docx.numbering import heading_plan
from md2docx.units import parse_size
from . import config_bridge as bridge
from .icons import icon


def choice(items):
    combo = QComboBox()
    for title, value in items:
        combo.addItem(title, value)
    return combo


class AdvancedOptions(QDialog):
    CATEGORIES = [('模板', 'folder'), ('字体', 'font'), ('段落', 'paragraph'), ('页面', 'page'),
                  ('编号与列表', 'list'), ('样式设计', 'style'),
                  ('表格与图片', 'table'), ('高级配置', 'settings')]
    TARGETS = [('正文', 'body'), *[(f'标题 {i}', f'heading{i}') for i in range(1, 7)],
               ('表格正文', 'table_text'), ('表格表头', 'table_header'),
               ('代码块', 'code'), ('图注', 'caption'), ('引用', 'quote'),
               ('无序列表', 'list'), ('有序列表', 'list_ordered')]

    TEMPLATE_PAGE, FONT_PAGE, PARAGRAPH_PAGE, STYLE_PAGE, RAW_PAGE = 0, 1, 2, 5, 7

    def __init__(self, template, overrides, parent=None, inherited=None, text_only=False):
        super().__init__(parent)
        self.setWindowTitle('排版设置')
        self.resize(1000, 740)
        self.setMinimumSize(940, 680)
        self.template = template
        self.values = copy.deepcopy(overrides)
        self.inherited = inherited or {}
        self.text_only = text_only
        self.config = load_config(template, self.inherited)
        self.element_fields, self.element_flags = {}, {}
        self.global_fields, self.global_choices = {}, {}
        self.raw_dirty = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(16)
        header = QHBoxLayout()
        title = QLabel('排版设置')
        title.setObjectName('sectionTitle')
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)
        body = QHBoxLayout()
        self.categories = QListWidget()
        self.categories.setObjectName('categories')
        self.categories.setFixedWidth(154)
        for label, glyph in self.CATEGORIES:
            self.categories.addItem(QListWidgetItem(icon(glyph), label))
        body.addWidget(self.categories)
        self.style_panel = QWidget()
        styles = QVBoxLayout(self.style_panel)
        styles.setContentsMargins(0, 0, 8, 0)
        styles.addWidget(QLabel('文档样式'))
        self.style_list = QListWidget()
        self.style_list.setObjectName('styleList')
        self.style_list.setFixedWidth(136)
        self.element = QComboBox(self)  # Selection model retained for integrations.
        self.element.hide()
        for title, key in self.TARGETS:
            self.style_list.addItem(title)
            self.element.addItem(title, key)
        styles.addWidget(self.style_list)
        body.addWidget(self.style_panel)
        content = QVBoxLayout()
        self.section_heading = QLabel()
        self.section_heading.setObjectName('sectionTitle')
        content.addWidget(self.section_heading)
        self.pages = QStackedWidget()
        content.addWidget(self.pages, 1)
        body.addLayout(content, 1)
        layout.addLayout(body, 1)

        template_page = QWidget()
        template_layout = QVBoxLayout(template_page)
        template_layout.setContentsMargins(8, 12, 12, 12)
        template_layout.setSpacing(16)
        template_layout.addWidget(QLabel('选择模板'))
        self.template_combo = QComboBox()
        for spec in bridge.template_choices():
            self.template_combo.addItem(spec['label'], spec['path'])
        if template and self.template_combo.findData(template) < 0:
            from pathlib import Path
            self.template_combo.addItem(Path(template).stem, template)
        self.template_combo.setCurrentIndex(max(0, self.template_combo.findData(template)))
        template_layout.addWidget(self.template_combo)
        self.template_description = QLabel()
        self.template_description.setObjectName('muted')
        self.template_description.setWordWrap(True)
        template_layout.addWidget(self.template_description)
        template_actions = QHBoxLayout()
        self.import_button = QPushButton('导入模板')
        self.import_button.setIcon(icon('upload'))
        self.import_button.clicked.connect(self.import_template)
        self.export_button = QPushButton('导出模板')
        self.export_button.setIcon(icon('download'))
        self.export_button.clicked.connect(self.export_template)
        template_actions.addWidget(self.import_button)
        template_actions.addWidget(self.export_button)
        template_actions.addStretch()
        template_layout.addLayout(template_actions)
        group = QGroupBox('输出')
        output_form = self.page()
        group.setLayout(output_form)
        modes = [('Word 可编辑公式', 'omml'), ('PNG 图片（KaTeX）', 'image'), ('LaTeX 源码', 'text')]
        self.global_choice(output_form, '公式格式', 'math.mode', [item for item in modes if not text_only or item[1] != 'image'])
        template_layout.addWidget(group)
        template_layout.addStretch()
        self.pages.addWidget(template_page)

        page = self.page()
        self.element_edit(page, '中文字体', 'font_zh', bridge.FONT_ZH_CHOICES)
        self.element_edit(page, '西文字体', 'font_en', bridge.FONT_EN_CHOICES)
        self.element_edit(page, '字号', 'size', bridge.DETAIL_SIZE_CHOICES)
        self.element_edit(page, '字体颜色', 'color')
        self.element_flag(page, '加粗', 'bold')
        self.element_flag(page, '斜体', 'italic')
        self.global_choice(page, 'Markdown 斜体处理', 'markdown.emphasis_as_bold', [('保留斜体', False), ('转为加粗', True)])
        self.add_page(page)

        page = self.page()
        self.element_flag(page, '对齐方式', 'align', bridge.ALIGN_CHOICES)
        for title, key in [('行距（倍）', 'line_spacing'), ('段前（磅）', 'space_before'),
                           ('段后（磅）', 'space_after'), ('首行缩进', 'first_line_indent'),
                           ('左缩进', 'left_indent'), ('悬挂缩进', 'hanging_indent')]:
            self.element_edit(page, title, key, bridge.DETAIL_LINE_SPACING_CHOICES if key == 'line_spacing' else None)
        for title, key in [('与下段同页', 'keep_with_next'), ('段中不分页', 'keep_lines'),
                           ('段前分页', 'page_break_before')]:
            self.element_flag(page, title, key)
        self.add_page(page)

        page = self.page()
        self.global_choice(page, '纸张大小', 'page.size', [(s, s) for s in bridge.PAGE_SIZE_CHOICES])
        self.global_choice(page, '纸张方向', 'page.orientation', bridge.ORIENTATION_CHOICES)
        for title, key in [('上边距', 'top'), ('下边距', 'bottom'), ('左边距', 'left'), ('右边距', 'right')]:
            self.global_edit(page, title, 'page.margin.' + key)
        self.global_choice(page, '页脚页码', 'page.footer_page_number')
        self.global_choice(page, '插入目录', 'output.toc')
        self.global_edit(page, '目录级别', 'output.toc_levels')
        self.add_page(page)

        page = self.page()
        group = self.group(page, '标题编号')
        self.global_choice(group, '编号方案', 'numbering.headings', [('关闭编号', 'off'), *[(label, key) for key, label in bridge.NUMBERING_CHOICES]])
        self.global_choice(group, '编号层级', 'numbering.levels', [(f'前 {i} 级', i) for i in range(1, 7)])
        for title, key in [('跳过一级主标题', 'skip_first_level'), ('移除手写编号', 'strip_text_prefix'), ('上级变化后重新编号', 'restart')]:
            self.global_choice(group, title, 'numbering.' + key)
        self.global_edit(group, '编号缩进', 'numbering.indent')
        self.global_edit(group, '编号悬挂缩进', 'numbering.hanging')
        group = self.group(page, '逐级编号格式')
        self.number_level = QComboBox()
        for i in range(1, 7):
            self.number_level.addItem(f'第 {i} 级', i)
        group.addRow('级别', self.number_level)
        self.number_fields = {}
        for title, key, items in [('数字格式', 'num_fmt', [(v, k) for k, v in bridge.NUM_FMT_CHOICES]),
                                   ('编号文字', 'text', None),
                                   ('编号后分隔', 'suff', [(v, k) for k, v in bridge.SUFF_CHOICES])]:
            if items is None:
                control = QLineEdit()
                control.setToolTip('%1 表示一级序号，%2 表示二级序号，例如 第%1章。')
                control.textEdited.connect(lambda text, k=key: self.set_value(f'numbering.format.{self.number_level.currentData()}.{k}', text.strip() or None))
            else:
                control = choice(items)
                control.activated.connect(lambda _i, k=key, c=control: self.set_value(f'numbering.format.{self.number_level.currentData()}.{k}', c.currentData()))
            self.number_fields[key] = control
            group.addRow(title, control)
        self.number_level.currentIndexChanged.connect(self.fill_numbering)
        self.fill_numbering()
        group = self.group(page, '列表缩进')
        for target, title in [('list', '无序列表'), ('list_ordered', '有序列表')]:
            self.global_edit(group, title + '左缩进', f'elements.{target}.left_indent')
            self.global_edit(group, title + '悬挂缩进', f'elements.{target}.hanging_indent')
            self.global_edit(group, title + '层级间距（字符）', f'elements.{target}.level_step_chars')
        self.add_page(page)

        style_page = QWidget()
        style_layout = QVBoxLayout(style_page)
        style_layout.setSpacing(16)
        self.sample = QLabel('标题样式预览')
        self.sample.setWordWrap(True)
        self.sample.setMinimumHeight(150)
        self.sample.setStyleSheet('background:white;border:1px solid #dce3ed;border-radius:8px;padding:24px;')
        style_layout.addWidget(self.sample)
        self.style_summary = QLabel()
        self.style_summary.setWordWrap(True)
        style_layout.addWidget(self.style_summary)
        actions = QHBoxLayout()
        for title, index, glyph in [('编辑字体', self.FONT_PAGE, 'font'), ('编辑段落', self.PARAGRAPH_PAGE, 'paragraph')]:
            button = QPushButton(title)
            button.setIcon(icon(glyph))
            button.clicked.connect(lambda _checked, i=index: self.categories.setCurrentRow(i))
            actions.addWidget(button)
        reset = QPushButton('恢复此样式')
        reset.clicked.connect(self.reset_style)
        actions.addWidget(reset)
        style_layout.addLayout(actions)
        style_layout.addStretch()
        self.pages.addWidget(style_page)

        page = self.page()
        group = self.group(page, '表格')
        for title, key in [('宽度（%）', 'table.width_pct'), ('表头底色', 'table.header_fill'),
                           ('边框颜色', 'table.border.color'), ('边框粗细', 'table.border.size')]:
            self.global_edit(group, title, key)
        self.global_choice(group, '单元格垂直对齐', 'table.valign', bridge.VALIGN_CHOICES)
        group = self.group(page, '图片与图表')
        for title, key in [('图片最大高度', 'elements.image.max_height'), ('图片宽度比例', 'elements.image.max_width_ratio'),
                           ('图表缩放', 'mermaid.scale'), ('图表最大高度', 'mermaid.max_height')]:
            self.global_edit(group, title, key)
        self.global_choice(group, '渲染图表', 'mermaid.renderer', [('自动', 'auto'), ('关闭', 'off')])
        self.add_page(page)

        raw_page = QWidget()
        raw_layout = QVBoxLayout(raw_page)
        self.yaml_edit = QPlainTextEdit()
        self.yaml_edit.setFont(QFont('Consolas', 11))
        self.yaml_edit.textChanged.connect(self.raw_changed)
        raw_layout.addWidget(self.yaml_edit)
        self.pages.addWidget(raw_page)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText('确定')
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('取消')
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.style_list.currentRowChanged.connect(self.element.setCurrentIndex)
        self.element.currentIndexChanged.connect(self.fill_element)
        self.categories.currentRowChanged.connect(self.show_category)
        self.template_combo.currentIndexChanged.connect(self.select_template)
        self.style_list.setCurrentRow(0)
        self.categories.setCurrentRow(self.TEMPLATE_PAGE)
        self.update_template_description()

    @staticmethod
    def page():
        form = QFormLayout()
        form.setContentsMargins(8, 12, 12, 12)
        form.setVerticalSpacing(14)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        return form

    def group(self, page, title):
        box = QGroupBox(title)
        form = self.page()
        box.setLayout(form)
        page.addRow(box)
        return form

    def add_page(self, form):
        content = QWidget()
        content.setObjectName('formatPage')
        content.setLayout(form)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(content)
        self.pages.addWidget(scroll)

    def element_edit(self, form, title, key, suggestions=None):
        control = edit = QLineEdit()
        if suggestions:
            control = QComboBox()
            control.setEditable(True)
            control.addItems(suggestions)
            control.setCurrentIndex(-1)
            edit = control.lineEdit()
            control.activated.connect(lambda _i, k=key, c=control: self.update_element(k, c.currentText()))
        if key == 'color':
            edit.setToolTip('六位颜色值，例如 000000。')
        if key.endswith('indent'):
            edit.setToolTip('可填 2字符、0.5cm 或磅值。')
        self.element_fields[key] = edit
        edit.textEdited.connect(lambda text, k=key: self.update_element(k, text))
        if key == 'color':
            control = self.color_control(edit)
        form.addRow(title, control)

    def color_control(self, edit):
        widget = QWidget()
        row = QHBoxLayout(widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(edit, 1)
        pick = QPushButton('选择颜色')
        def choose_color():
            current = edit.text() or edit.placeholderText()
            color = QColorDialog.getColor(QColor('#' + current), self, '选择颜色')
            if color.isValid():
                text = color.name()[1:].upper()
                edit.setText(text)
                edit.textEdited.emit(text)
        pick.clicked.connect(choose_color)
        row.addWidget(pick)
        return widget

    def element_flag(self, form, title, key, items=None):
        if items is None:
            control = QCheckBox()
            control.clicked.connect(lambda checked, k=key: self.set_value(f'elements.{self.element.currentData()}.{k}', checked))
        else:
            control = choice(items)
            control.activated.connect(lambda _i, k=key, c=control: self.set_value(f'elements.{self.element.currentData()}.{k}', c.currentData()))
        self.element_flags[key] = control
        form.addRow(title, control)

    def global_edit(self, form, title, key):
        edit = QLineEdit(str(self.lookup(key)))
        if key.endswith(('color', 'header_fill')):
            edit.setToolTip('六位颜色值，例如 F2F2F2。')
        edit.textEdited.connect(lambda text, k=key: self.set_value(k, (text.strip() or None) if k.endswith(('color', 'header_fill', 'toc_levels')) else self.coerce(text)))
        self.global_fields[key] = edit
        form.addRow(title, self.color_control(edit) if key.endswith(('color', 'header_fill')) else edit)

    def global_choice(self, form, title, key, items=None):
        if items is None:
            control = QCheckBox()
            control.clicked.connect(lambda checked, k=key: self.set_value(k, checked))
        else:
            control = choice(items)
            control.activated.connect(lambda _i, k=key, c=control: self.set_value(k, c.currentData()))
        self.set_control_value(control, self.lookup(key))
        self.global_choices[key] = control
        form.addRow(title, control)

    def effective_config(self):
        config = copy.deepcopy(self.config)
        for key, value in self.values.items():
            node = config
            parts = key.split('.')
            for part in parts[:-1]:
                if not isinstance(node.get(part), dict):
                    node[part] = {}
                node = node[part]
            node[parts[-1]] = copy.deepcopy(value)
        if self.text_only and config.get('math', {}).get('mode') == 'image':
            config['math']['mode'] = 'omml'
        return config

    def lookup(self, key):
        config = self.effective_config()
        if key == 'numbering.headings':
            try:
                numbering = heading_numbering(config)
                return numbering['preset'] if numbering else 'off'
            except ValueError:
                pass
        value = config
        for part in key.split('.'):
            value = value.get(part, '') if isinstance(value, dict) else ''
        return value

    @staticmethod
    def set_control_value(control, value):
        control.blockSignals(True)
        if isinstance(control, QCheckBox):
            control.setChecked(bool(value))
        else:
            index = control.findData(value)
            if index < 0:
                control.addItem(str(value), value)
                index = control.count() - 1
            control.setCurrentIndex(index)
        control.blockSignals(False)

    @staticmethod
    def coerce(text):
        text = text.strip()
        if not text:
            return None
        try:
            value = yaml.safe_load(text)
            return value if isinstance(value, (str, float, int, bool)) else text
        except yaml.YAMLError:
            return text

    def set_value(self, key, value):
        if value is None:
            self.values.pop(key, None)
        else:
            self.values[key] = value
        if key == 'numbering.headings':
            self.fill_numbering()
        self.refresh_sample()

    def update_element(self, key, text):
        self.set_value(f'elements.{self.element.currentData()}.{key}', (text.strip() or None) if key == 'color' else self.coerce(text))

    def fill_element(self):
        self.style_list.blockSignals(True)
        self.style_list.setCurrentRow(self.element.currentIndex())
        self.style_list.blockSignals(False)
        key = self.element.currentData()
        style = element_style(self.effective_config(), key)
        for field, edit in self.element_fields.items():
            edit.setText(str(style.get(field, '')))
        for field, control in self.element_flags.items():
            self.set_control_value(control, style.get(field, False))
        self.refresh_sample()
        self.update_section_heading()

    def fill_numbering(self):
        config = self.effective_config()
        config.setdefault('numbering', {})['headings'] = self.lookup('numbering.headings')
        if config['numbering']['headings'] == 'off':
            config['numbering']['headings'] = True
        try:
            level = heading_plan(heading_numbering(config)).levels[self.number_level.currentData() - 1]
        except (ValueError, TypeError, IndexError):
            level = {}
        for key, control in self.number_fields.items():
            value = level.get(key, '')
            if isinstance(control, QLineEdit):
                control.setText(str(value))
                control.setPlaceholderText('例如 第%1章')
            else:
                self.set_control_value(control, value)

    def refresh_sample(self):
        if not hasattr(self, 'sample'):
            return
        style = element_style(self.effective_config(), self.element.currentData())
        font = QFont(str(style.get('font_zh', '宋体')))
        try:
            font.setPointSizeF(parse_size(style.get('size', '小四')))
        except (TypeError, ValueError):
            font.setPointSizeF(12)
        font.setBold(bool(style.get('bold')))
        font.setItalic(bool(style.get('italic')))
        color = str(style.get('color', '000000'))
        if not re.fullmatch(r'[0-9a-fA-F]{6}', color):
            color = '000000'
        self.sample.setStyleSheet('background:white;border:1px solid #dce3ed;border-radius:8px;padding:24px;'
            f'font-family:"{str(style.get("font_zh", "宋体")).replace(chr(34), "")}";'
            f'font-size:{font.pointSizeF()}pt;font-weight:{700 if font.bold() else 400};'
            f'font-style:{"italic" if font.italic() else "normal"};color:#{color};')
        self.sample.setText(html.escape(self.element.currentText()) + '<br>文档排版示例 '
            f'<span style="font-family:&quot;{html.escape(str(style.get("font_en", "Times New Roman")))}&quot;">Aa 123</span>')
        self.sample.setAlignment({'center': Qt.AlignmentFlag.AlignCenter, 'right': Qt.AlignmentFlag.AlignRight}.get(style.get('align'), Qt.AlignmentFlag.AlignLeft) | Qt.AlignmentFlag.AlignVCenter)
        self.style_summary.setText(f"中文字体：{style.get('font_zh', '')}\n西文字体：{style.get('font_en', '')}\n字号：{style.get('size', '')}    行距：{style.get('line_spacing', '')}\n段前：{style.get('space_before', 0)}    段后：{style.get('space_after', 0)}")

    def reset_style(self):
        prefix = f'elements.{self.element.currentData()}.'
        self.values = {k: v for k, v in self.values.items() if not k.startswith(prefix)}
        self.refresh_controls()

    def update_section_heading(self):
        row = self.categories.currentRow()
        if row >= 0:
            title = self.CATEGORIES[row][0]
            self.section_heading.setText(f'{self.element.currentText()} / {title}' if row in (self.FONT_PAGE, self.PARAGRAPH_PAGE, self.STYLE_PAGE) else title)

    def show_category(self, row):
        if self.pages.currentIndex() == self.RAW_PAGE and self.raw_dirty and not self.apply_raw():
            self.categories.blockSignals(True)
            self.categories.setCurrentRow(self.RAW_PAGE)
            self.categories.blockSignals(False)
            return
        self.pages.setCurrentIndex(row)
        self.refresh_controls()
        self.style_panel.setVisible(row in (self.FONT_PAGE, self.PARAGRAPH_PAGE, self.STYLE_PAGE))
        self.update_section_heading()
        if row == self.RAW_PAGE:
            self.raw_snapshot = self.flatten(self.effective_config())
            self.yaml_edit.blockSignals(True)
            self.yaml_edit.setPlainText(yaml.safe_dump(self.raw_snapshot, allow_unicode=True, sort_keys=True))
            self.yaml_edit.blockSignals(False)
            self.raw_dirty = False

    def raw_changed(self):
        self.raw_dirty = True

    def apply_raw(self):
        try:
            parsed = yaml.safe_load(self.yaml_edit.toPlainText())
            values = {} if parsed is None else parsed
            if not isinstance(values, dict) or any(not isinstance(k, str) for k in values):
                raise ValueError('配置必须是 YAML 映射，键为配置路径。')
            updates = dict(self.values)
            for key in self.raw_snapshot.keys() - values.keys():
                updates.pop(key, None)
            for key, value in values.items():
                if key not in self.raw_snapshot or value != self.raw_snapshot[key]:
                    updates[key] = value
            load_config(self.template, {**self.inherited, **updates})
            self.values = updates
            self.raw_dirty = False
            self.refresh_controls()
            return True
        except Exception as exc:
            QMessageBox.warning(self, '配置未保存', str(exc))
            return False

    def refresh_controls(self):
        self.fill_element()
        self.fill_numbering()
        for key, control in self.global_fields.items():
            control.setText(str(self.lookup(key)))
        for key, control in self.global_choices.items():
            self.set_control_value(control, self.lookup(key))

    @staticmethod
    def flatten(config, prefix=''):
        result = {}
        for key, value in config.items():
            if str(key).startswith('_'):
                continue
            path = prefix + str(key)
            if isinstance(value, dict) and value:
                result.update(AdvancedOptions.flatten(value, path + '.'))
            else:
                result[path] = value
        return result

    def update_template_description(self):
        from pathlib import Path
        name = Path(self.template).name if self.template else 'default.yaml'
        self.template_description.setText(bridge.TEMPLATE_DESC.get(name, '自定义模板').replace(' · ', '，'))

    def select_template(self, index):
        template = self.template_combo.itemData(index)
        try:
            config = load_config(template)
        except Exception as exc:
            self.template_combo.blockSignals(True)
            self.template_combo.setCurrentIndex(max(0, self.template_combo.findData(self.template)))
            self.template_combo.blockSignals(False)
            QMessageBox.warning(self, '模板无效', str(exc))
            return
        self.template = template
        self.inherited = {}
        self.values = {}
        self.config = config
        self.raw_dirty = False
        self.refresh_controls()
        self.update_template_description()

    def load_template(self, path):
        from pathlib import Path
        path = str(Path(path).resolve())
        load_config(path)
        index = self.template_combo.findData(path)
        if index < 0:
            self.template_combo.addItem(Path(path).stem, path)
            index = self.template_combo.count() - 1
        if index == self.template_combo.currentIndex():
            self.select_template(index)
        else:
            self.template_combo.setCurrentIndex(index)

    def import_template(self):
        path, _ = QFileDialog.getOpenFileName(self, '导入模板', '', 'YAML 模板 (*.yaml *.yml)')
        if path:
            try:
                self.load_template(path)
            except Exception as exc:
                QMessageBox.warning(self, '模板无效', str(exc))

    def export_to(self, path):
        if self.raw_dirty and not self.apply_raw():
            raise ValueError('请先修正高级配置。')
        config = load_config(self.template, {**self.inherited, **self.values})
        if self.text_only and config.get('math', {}).get('mode') == 'image':
            config['math']['mode'] = 'omml'
        config.pop('_meta', None)
        from pathlib import Path
        Path(path).write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding='utf-8')

    def export_template(self):
        path, _ = QFileDialog.getSaveFileName(self, '导出排版模板', '自定义排版.yaml', 'YAML 模板 (*.yaml)')
        if path:
            try:
                self.export_to(path)
            except Exception as exc:
                QMessageBox.warning(self, '导出失败', str(exc))

    def save(self):
        if self.raw_dirty and not self.apply_raw():
            return
        try:
            load_config(self.template, {**self.inherited, **self.values})
            self.accept()
        except Exception as exc:
            QMessageBox.warning(self, '配置未保存', str(exc))
