"""
死链路清理回归测试

背景：项目曾有两套并行前端。
  - 活链路：templates/dashboard.html + static/css/dashboard.css +
    static/js/dashboard.js（app.py 只渲染它）
  - 死链路：templates/index.html + app.js + api.js + pages/*（无任何路由可达）
本批已删除死链路中与本产品方向无关的部分，并保留"我的挑战"模块前端
（challenges.js + api.js + challenge.css）作为待接线资产。

运行：
  python -m pytest tests/test_dead_code_cleanup.py -v
"""

import os
import re
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def _path(*parts):
    return os.path.join(PROJECT_ROOT, *parts)


def _exists(*parts):
    return os.path.exists(_path(*parts))


# ==================== 已删除的死链路 ====================


@pytest.mark.parametrize(
    "removed",
    [
        ("templates", "index.html"),
        ("static", "js", "app.js"),
        ("static", "js", "pages", "home.js"),
        ("static", "js", "pages", "diary.js"),
        ("static", "css", "variables.css"),
        ("static", "css", "base.css"),
        ("static", "css", "components.css"),
        ("static", "css", "mobile.css"),
    ],
)
def test_dead_chain_files_are_removed(removed):
    """已确认不可达的文件应已删除。"""
    assert not _exists(*removed), f"{'/'.join(removed)} 仍存在"


@pytest.mark.parametrize(
    "kept",
    [
        ("static", "js", "pages", "challenges.js"),
        ("static", "js", "api.js"),
        ("static", "css", "challenge.css"),
        ("static", "avatars", "preset_xj1.svg"),
        ("static", "avatars", "preset_azheng1.svg"),
    ],
)
def test_pending_assets_are_kept(kept):
    """待接线的挑战模块前端与头像资源应保留。"""
    assert _exists(*kept), f"{'/'.join(kept)} 被误删"


# ==================== 活链路必须完好 ====================


@pytest.mark.parametrize(
    "alive",
    [
        ("templates", "dashboard.html"),
        ("static", "css", "dashboard.css"),
        ("static", "js", "dashboard.js"),
        ("templates", "auth", "login.html"),
        ("templates", "auth", "register.html"),
        ("templates", "admin", "index.html"),
    ],
)
def test_live_chain_files_still_exist(alive):
    """活链路文件必须完整保留。"""
    assert _exists(*alive), f"活链路文件缺失：{'/'.join(alive)}"


def test_app_renders_dashboard_not_index(flask_app):
    """应用入口必须渲染 dashboard.html，且不再引用已删除的 index.html。"""
    with open(_path("app.py"), encoding="utf-8") as handle:
        app_source = handle.read()
    # 只允许 admin/index.html
    for match in re.finditer(r"render_template\(['\"]([^'\"]+)['\"]\)", app_source):
        template = match.group(1)
        assert template != "index.html", "app.py 仍在渲染已删除的 index.html"


@pytest.fixture(scope="module")
def flask_app():
    import types

    try:
        import flask_cors  # noqa: F401
    except ImportError:
        stub = types.ModuleType("flask_cors")
        stub.CORS = lambda app=None, **kw: (lambda f: f)
        sys.modules["flask_cors"] = stub
    import app as mainapp

    mainapp.app.config["TESTING"] = True
    return mainapp.app


def test_pages_still_render(flask_app):
    """删除死链路后，活链路页面仍能正常渲染。"""
    client = flask_app.test_client()
    for path in ("/", "/dashboard", "/pomodoro", "/tasks", "/diary",
                 "/buddy", "/stats", "/growth", "/settings"):
        resp = client.get(path)
        assert resp.status_code == 200, f"{path} 返回 {resp.status_code}"
        body = resp.get_data(as_text=True)
        assert "StudyPal" in body, f"{path} 未渲染出页面内容"


def test_static_assets_resolve(flask_app):
    """活链路引用的静态资源必须能取到。"""
    client = flask_app.test_client()
    for asset in ("/static/css/dashboard.css", "/static/js/dashboard.js"):
        resp = client.get(asset)
        assert resp.status_code == 200, f"{asset} 返回 {resp.status_code}"


def test_removed_assets_no_longer_resolve(flask_app):
    """已删除的资源应返回 404，避免"以为还在"。"""
    client = flask_app.test_client()
    for asset in ("/static/js/app.js", "/static/css/components.css"):
        resp = client.get(asset)
        assert resp.status_code == 404, f"{asset} 仍可访问（{resp.status_code}）"


# ==================== 保留资产的方向一致性 ====================


def test_kept_challenge_frontend_has_no_high_school():
    """保留的挑战模块前端不得残留高中档。

    注意：`'high'` 在本文件中还有合法含义（里程碑紧急度 urgency），
    因此只检测"作为学段使用"的写法。
    """
    with open(_path("static", "js", "pages", "challenges.js"), encoding="utf-8") as handle:
        source = handle.read()
    assert "高中" not in source, "challenges.js 仍残留高中档"
    assert 'data-grade="high"' not in source, "challenges.js 仍有高中选项"
    # 作为学段 key 的写法（字典键或等级数组元素）不得存在
    assert re.search(r"\bhigh:\s*'高中'", source) is None, "仍存在 high 学段标签"
    assert "_selectGrade('high')" not in source, "仍有切换到高中的入口"
    assert "gradeMode === 'high'" not in source, "仍有针对高中学段的判断"


def test_kept_assets_have_no_kaoyan():
    """保留的三件套不得残留考研文案。"""
    for rel in (("static", "js", "pages", "challenges.js"),
                ("static", "js", "api.js"),
                ("static", "css", "challenge.css")):
        with open(_path(*rel), encoding="utf-8") as handle:
            source = handle.read()
        assert "考研" not in source, f"{'/'.join(rel)} 仍残留考研文案"


def test_challenge_frontend_grade_options_match_backend():
    """挑战前端的学段选项必须与后端 GRADE_MODES 一致。"""
    from src.modules.challenge_manager import GRADE_MODES

    with open(_path("static", "js", "pages", "challenges.js"), encoding="utf-8") as handle:
        source = handle.read()

    for mode in GRADE_MODES:
        assert f"data-grade=\"{mode}\"" in source, f"前端缺少学段选项 {mode}"
    # 前端声明的学段集合不应多于后端
    declared = set(re.findall(r'data-grade="([a-z]+)"', source))
    assert declared <= set(GRADE_MODES), (
        f"前端声明了后端不支持的学段：{sorted(declared - set(GRADE_MODES))}"
    )


def test_kept_css_has_no_orphan_import_of_deleted_files():
    """保留的 CSS 不得 import 已删除的样式文件。"""
    with open(_path("static", "css", "challenge.css"), encoding="utf-8") as handle:
        source = handle.read()
    for deleted in ("variables.css", "base.css", "components.css", "mobile.css"):
        assert deleted not in source, f"challenge.css 仍 import 已删除的 {deleted}"


# ==================== 挑战模块已接线 ====================


def test_challenge_module_is_wired_into_dashboard():
    """挑战模块必须真正接进主界面（此前它是不可达的死链路资产）。"""
    with open(_path("templates", "dashboard.html"), encoding="utf-8") as handle:
        html = handle.read()

    # 页面区块与挂载容器
    assert 'id="section-challenges"' in html, "缺少挑战页面区块"
    assert 'id="page-challenges"' in html, "缺少挑战挂载容器"
    # 导航入口
    assert 'data-section="challenges"' in html, "导航缺少挑战入口"
    # 资源引用
    assert "/static/css/challenge.css" in html, "未引入挑战样式"
    assert "/static/js/api.js" in html, "未引入 API 层"
    assert "/static/js/pages/challenges.js" in html, "未引入挑战模块"
    # 加载顺序：api.js 必须在 challenges.js 之前
    assert html.index("/static/js/api.js") < html.index(
        "/static/js/pages/challenges.js"
    ), "api.js 必须在 challenges.js 之前加载"


def test_dashboard_js_mounts_challenge_module():
    """dashboard.js 必须在切到挑战页时挂载该模块，并安全降级。"""
    with open(_path("static", "js", "dashboard.js"), encoding="utf-8") as handle:
        js = handle.read()
    assert "mountChallenges" in js, "缺少挑战模块挂载函数"
    assert "window.ChallengePage" in js, "未访问 ChallengePage"
    assert "sectionName === 'challenges'" in js, "未在切换到挑战页时挂载"
    # 模块缺失时必须给出可读提示而不是静默失败
    assert "挑战模块暂时不可用" in js or "暂时不可用" in js


def test_challenge_css_vars_have_fallbacks():
    """挑战样式引用的 CSS 变量必须带兜底值（variables.css 已删除）。"""
    with open(_path("static", "css", "challenge.css"), encoding="utf-8") as handle:
        css = handle.read()
    for match in re.finditer(r"var\((--[\w-]+)([^)]*)\)", css):
        assert "," in match.group(2), (
            f"var({match.group(1)}) 缺少兜底值，且定义它的 variables.css 已删除"
        )


def test_challenge_endpoints_reachable(flask_app):
    """挑战模块依赖的后端端点必须可用。"""
    client = flask_app.test_client()
    for path in ("/api/challenges", "/api/challenges/presets/icons",
                 "/api/challenges/presets/grade/primary",
                 "/api/challenges/presets/grade/middle"):
        resp = client.get(path)
        assert resp.status_code == 200, f"{path} 返回 {resp.status_code}"


def test_challenge_presets_match_backend_grades(flask_app):
    """前端可选的学段预设必须与后端一致（小学 + 初中）。"""
    from src.modules.challenge_manager import GRADE_MODES

    client = flask_app.test_client()
    for mode in GRADE_MODES:
        resp = client.get(f"/api/challenges/presets/grade/{mode}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get("presets"), f"{mode} 学段没有学科预设"
    # 高中必须不可用
    resp = client.get("/api/challenges/presets/grade/high")
    assert resp.status_code == 200
    assert not resp.get_json().get("presets"), "高中仍返回学科预设"

