"""
前端方向回归测试：倒计时 -> 习惯养成

锁定 C3 改造，防止回退到考研倒计时：
- 仪表盘不得再出现"距离考研初试"、目标院校、分数线、写死的 175 天/380 分
- 不得再出现写死的考试日期 2026-12-21
- "我的成长"区域改为连续打卡天数 + 本周小星星
- 导航与右侧栏的 section 命名保持一致（growth）

同时做静态一致性检查：HTML 引用的 id 必须能在 JS 里找到，
且三处（html/js/css）不得残留 exam-goal 命名。

运行：
  python -m pytest tests/test_frontend_growth.py -v
"""

import os
import re
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

HTML_PATH = os.path.join(PROJECT_ROOT, "templates", "dashboard.html")
JS_PATH = os.path.join(PROJECT_ROOT, "static", "js", "dashboard.js")
CSS_PATH = os.path.join(PROJECT_ROOT, "static", "css", "dashboard.css")


def _read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


@pytest.fixture(scope="module")
def html():
    return _read(HTML_PATH)


@pytest.fixture(scope="module")
def js():
    return _read(JS_PATH)


@pytest.fixture(scope="module")
def css():
    return _read(CSS_PATH)


# ==================== 考研倒计时必须消失 ====================


@pytest.mark.parametrize(
    "banned",
    [
        "距离考研初试",
        "考研目标",
        "目标院校",
        "目标专业",
        "历年分数线",
        "考研初试",
        "考研学习搭子",
    ],
)
def test_dashboard_has_no_kaoyan_text(html, banned):
    """仪表盘不得再出现考研向文案。"""
    assert banned not in html, f"dashboard.html 仍含考研文案：{banned}"


def test_dashboard_has_no_hardcoded_exam_countdown(html):
    """不得再写死倒计时数字与考试日期。"""
    for banned in ("175", "380", "2026年12月21日", "2026-12-21", "376"):
        assert banned not in html, f"dashboard.html 仍写死考试数据：{banned}"


def test_js_has_no_hardcoded_exam_date(js):
    """JS 不得再写死考试日期或倒计时逻辑。"""
    for banned in ("2026-12-21", "updateCountdown", "examDate"):
        assert banned not in js, f"dashboard.js 仍含倒计时残留：{banned}"


def test_js_has_no_hardcoded_username(js):
    """不得再把用户名写死成"学习战士"。"""
    assert "学习战士" not in js, "dashboard.js 仍写死用户名"


# ==================== 我的成长（习惯养成）已就位 ====================


def test_growth_section_exists(html):
    """必须存在"我的成长"页面区块。"""
    assert 'id="section-growth"' in html
    assert "我的成长" in html


def test_growth_nav_matches_section(html):
    """导航项与页面区块的 section 名必须一致，否则点击无效。"""
    nav_sections = set(re.findall(r'data-section="([a-z-]+)"', html))
    page_sections = set(re.findall(r'id="section-([a-z-]+)"', html))
    assert "growth" in nav_sections, "导航缺少 growth 入口"
    assert "growth" in page_sections, "缺少 section-growth 区块"
    # 导航指向的每个 section 都应有对应区块
    missing = sorted(nav_sections - page_sections)
    assert not missing, f"导航指向了不存在的区块：{missing}"


def test_streak_and_stars_widgets_exist(html):
    """连续打卡与本周星星两个控件都要存在。"""
    assert 'id="growth-streak"' in html, "缺少连续打卡显示"
    assert 'id="week-stars-grid"' in html, "缺少本周星星区域"
    assert "连续打卡" in html
    assert "本周小星星" in html


def test_growth_reads_real_backend_data(js):
    """成长数据必须来自后端真实接口，而不是写死。"""
    assert "/api/study/stats" in js, "未接入 /api/study/stats"
    assert "loadGrowth" in js, "缺少 loadGrowth"
    assert "streak_days" in js, "未读取连续打卡天数"
    assert "week_hours" in js, "未读取本周学习时长（用于点亮星星）"


def test_growth_degrades_safely(js):
    """后端失败时必须安全降级，不得让页面崩溃。"""
    assert "renderGrowth" in js
    assert ".catch(" in js, "loadGrowth 缺少错误处理"


def test_username_is_not_hardcoded_in_html(html):
    """HTML 里不得写死用户名。"""
    assert "学习战士" not in html, "dashboard.html 仍写死用户名"


def test_username_loaded_from_user_source(js):
    """昵称应来自缓存或后端。"""
    assert "getDisplayName" in js
    assert "/api/auth/me" in js


# ==================== 命名一致性 ====================


def test_no_exam_goal_naming_left(html, js, css):
    """三处都不得残留 exam-goal 命名（否则样式/逻辑会脱节）。"""
    for name, content in (("dashboard.html", html),
                          ("dashboard.js", js),
                          ("dashboard.css", css)):
        assert "exam-goal" not in content, f"{name} 仍残留 exam-goal 命名"


def test_growth_class_names_are_consistent(html, js, css):
    """HTML、JS、CSS 三处的 growth 命名必须一致。

    注意：侧栏容器类 .rs-growth 在 CSS 中没有专属规则（只靠 .hidden 控制
    显隐，与原 .rs-exam-goal 的处理方式一致），因此这里只要求 HTML 与 JS
    一致，而布局类（growth-preview / growth-stats）必须能在 CSS 找到。
    """
    # 侧栏容器：HTML 与 JS 必须一致
    assert "rs-growth" in html, "HTML 缺少 rs-growth 容器"
    assert "rs-growth" in js, "JS 未按 rs-growth 查找容器"

    # 布局类：必须有 CSS 规则，否则样式会丢失
    for cls in ("growth-preview", "growth-stats"):
        assert cls in html, f"HTML 缺少 {cls}"
        assert "." + cls in css, f"CSS 缺少 .{cls} 规则"


def test_hidden_mechanism_still_available(css):
    """侧栏靠 .hidden 控制显隐，该规则必须存在。"""
    assert ".hidden" in css


def test_right_sidebar_toggles_on_growth(js):
    """切换到成长页时才显示成长侧栏。"""
    assert "section === 'growth'" in js or "=== 'growth'" in js, (
        "右侧栏未按 growth 区块切换"
    )
