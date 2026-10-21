"""
界面可访问性与设计规范回归测试

背景：本项目的界面按 design-essence 的 65 条检测规则做了系统性修复。
这些修复容易被后续改动无意回退（例如再次写 `transition: all`、
用 `outline:none` 抹掉焦点环、把加载动画塞回 JS 内联样式）。
本测试把这些"已经改对的东西"固化成断言。

运行：
  python -m pytest tests/test_design_accessibility.py -v
"""

import os
import re

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(*parts):
    with open(os.path.join(PROJECT_ROOT, *parts), encoding="utf-8") as handle:
        return handle.read()


@pytest.fixture(scope="module")
def css():
    return _read("static", "css", "dashboard.css")


@pytest.fixture(scope="module")
def html():
    return _read("templates", "dashboard.html")


@pytest.fixture(scope="module")
def js():
    return _read("static", "js", "dashboard.js")


# ==================== 焦点可见性（WCAG 2.4.7） ====================


def test_global_focus_visible_exists(css):
    """必须存在全局焦点样式，键盘用户才能看到焦点位置。"""
    assert ":focus-visible" in css, "缺少 :focus-visible 焦点样式"
    assert "outline" in css, "焦点样式应使用 outline 或等效可见环"


def test_no_naked_outline_none(css):
    """不得用裸 outline:none 抹掉焦点环（那是剥夺键盘用户能力）。"""
    # 注释里提到 outline:none 不算违规，只看真实声明
    lines = [ln for ln in css.splitlines() if not ln.strip().startswith(("/*", "*", "//"))]
    real = "\n".join(lines)
    assert "outline: none" not in real, "存在裸 outline:none，键盘焦点会不可见"
    assert "outline:none" not in real, "存在裸 outline:none，键盘焦点会不可见"


def test_focus_uses_focus_visible_not_focus(css):
    """:focus 应改为 :focus-visible（避免鼠标点击也亮环）。"""
    plain_focus = re.findall(r"(?<!-):focus(?!-visible|-within)\s*\{", css)
    assert not plain_focus, f"仍有 {len(plain_focus)} 处裸 :focus"


# ==================== 动效降级（prefers-reduced-motion） ====================


def test_reduced_motion_fallback_exists(css):
    """必须提供减少动效的系统偏好降级。"""
    assert "prefers-reduced-motion" in css, "缺少 prefers-reduced-motion 降级"


def test_reduced_motion_keeps_content_visible(css):
    """降级必须是"一帧终态"，不能让元素永久不可见。"""
    idx = css.find("prefers-reduced-motion")
    block = css[idx:idx + 900]
    # 降级块里若出现 opacity:0 而没有恢复规则，就是永久隐藏
    assert "opacity: 0" not in block.split("}")[0], "降级块可能让元素永久不可见"


def test_js_has_no_inline_animation(js):
    """加载动画应交由 CSS 承担（已含降级），JS 不应内联 animation。"""
    inline = re.findall(r"animation\s*:", js)
    assert not inline, f"JS 中仍有 {len(inline)} 处内联 animation 声明"


def test_no_transition_all(css):
    """transition: all 会波及意外属性，必须显式列出。"""
    assert "transition: all" not in css, "存在 transition: all"


# ==================== 移动端适配 ====================


def test_touch_action_optimization(css):
    """移动端应消除 300ms 点击延迟。"""
    assert "touch-action: manipulation" in css


def test_uses_dvh_with_vh_fallback(css):
    """移动端地址栏收缩场景应使用 dvh，并保留 vh 回退。"""
    assert "100dvh" in css, "缺少 dvh"
    assert "100vh" in css, "应保留 vh 作为旧浏览器回退"


def test_safe_area_inset_in_calc(css):
    """安全区变量必须包在 calc() 内（裸用无效）。"""
    hits = re.findall(r"env\(safe-area-inset[^)]*\)", css)
    assert hits, "缺少安全区适配"
    for hit in hits:
        idx = css.find(hit)
        prefix = css[max(0, idx - 40):idx]
        assert "calc(" in prefix, f"{hit} 未包在 calc() 内"


def test_mobile_inputs_avoid_ios_zoom(css):
    """移动端输入框 ≥16px，避免 iOS 聚焦自动放大。

    注意：必须定位到媒体查询内的那条规则，而不是全文第一个 font-size: 16px
    （后者可能是 .btn-lg 这类无关声明）。
    """
    # 必须定位到 768px 那个块（文件里还有 1200px / 900px 的响应式块）
    m = re.search(r"@media[^{]*max-width:\s*768px[^{]*\{(?P<body>.*?)\n\}", css, re.S)
    assert m, "缺少 768px 移动端媒体查询"
    body = m.group("body")
    assert "font-size: 16px" in body, "媒体查询内缺少 16px 输入字号"
    assert "input" in body, "16px 规则未覆盖 input"


# ==================== 触控与可点击元素 ====================


def test_small_buttons_have_min_hit_area(css):
    """小按钮需 min-* 兜底，保证命中区 ≥24×24（WCAG 2.2）。"""
    for selector in (".btn-sm", ".diary-delete", ".task-delete", ".mood-btn"):
        idx = css.find(selector + " {")
        if idx < 0:
            continue
        block = css[idx:css.find("}", idx)]
        assert "min-" in block, f"{selector} 缺少 min-width/min-height 命中区兜底"


def test_clickable_non_semantic_elements_removed(js):
    """可点击元素不得用 span/div 挂 onclick（键盘不可达）。"""
    assert 'onclick="this.parentElement.remove()' not in js, (
        "标签删除仍是 span onclick，键盘用户无法操作"
    )
    assert 'class="tag-remove"' in js, "标签删除应使用 button.tag-remove"


def test_no_hardcoded_line_breaks(js):
    """不得用 <br><br> 硬造换行（破坏响应式）。"""
    assert "<br><br>" not in js, "存在硬编码 <br><br>"


# ==================== 可访问名称与排版 ====================


def test_interactive_inputs_have_accessible_names(html, js):
    """输入控件必须有可访问名称（placeholder 不能当 label）。"""
    # 检查 HTML 中的 input/textarea/select：要么有 aria-label，要么有 id 且存在 for=id
    # 注意用 finditer 取完整标签：findall 带捕获组时只返回组内容（标签名），会误判
    tags = [m.group(0) for m in re.finditer(r"<(?:input|textarea|select)\b[^>]*>", html)]
    missing = []
    for tag in tags:
        if "aria-label" in tag or 'type="hidden"' in tag or 'type="checkbox"' in tag:
            continue
        if 'type="radio"' in tag:
            continue  # 单选框在 HTML 中有可见 <label> 包裹
        idm = re.search(r'id="([^"]+)"', tag)
        if idm and f'for="{idm.group(1)}"' in html:
            continue
        # 允许被 <label> 直接包裹的写法
        missing.append(tag[:70])
    assert not missing, "以下控件缺少可访问名称：\n  " + "\n  ".join(missing)


def test_form_labels_are_associated(html):
    """创建搭子弹窗的 label 应通过 for 关联控件（点标签可聚焦）。"""
    for field in ("bd-name", "bd-personality", "bd-desc", "bd-greeting"):
        assert f'for="{field}"' in html, f"label 未关联 {field}"


def test_no_three_dot_ellipsis_in_ui_text(html, js):
    """界面文案应使用单字符省略号 …，而不是三个点。

    只检查中文文案里的三点省略号 —— 代码注释、正则、被省略号截断的
    技术说明（如 "data: {...}"）不属于用户可见文案。
    """
    assert "..." not in html, "HTML 中存在三点省略号"
    offenders = []
    for line_no, line in enumerate(js.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith(("*", "/*", "//")):
            continue
        # 只挑「中文字符紧跟三个点」的文案场景
        if re.search(r"[\u4e00-\u9fa5]\.\.\.", line):
            offenders.append(f"行{line_no}: {stripped[:80]}")
    assert not offenders, "JS 中文文案中仍有三点省略号：\n  " + "\n  ".join(offenders)


def test_no_tiny_font_sizes(css):
    """正文字号不得小于 12px（10px 小字影响可读性）。"""
    tiny = re.findall(r"font-size:\s*(10|11)px", css)
    assert not tiny, f"仍存在 {len(tiny)} 处 10/11px 小字"


# ==================== 配对完整性（不是断言"检测器通过"，而是断言结构正确） ====================


def test_animation_references_are_defined(css):
    """引用的动画名必须有对应 @keyframes，否则动画静默失效。"""
    used = set(re.findall(r"animation:\s*([\w-]+)", css))
    defined = set(re.findall(r"@keyframes\s+([\w-]+)", css))
    missing = sorted(used - defined)
    assert not missing, f"以下动画被引用但未定义（会静默失效）：{missing}"