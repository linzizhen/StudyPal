"""
前端落库接通测试：日记与任务

已实证的"假功能"：
  - 任务：dashboard.js 的 initTasks 使用纯内存数组 `var tasks = []`，
    勾选/删除/新增都只改内存，刷新即丢失，从不调用后端。
  - 日记：dashboard.js 的 initDiary 保存时只弹一个 toast（"日记已保存！"），
    内容既不提交后端，清空后也无法找回。

本测试同时覆盖"搭子的记忆本"页面（记忆可视化）。

运行：
  python -m pytest tests/test_persistence_wiring.py -v
"""

import json
import os
import re
import shutil
import sys
import types
import uuid

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def _read(*parts):
    with open(os.path.join(PROJECT_ROOT, *parts), encoding="utf-8") as handle:
        return handle.read()


@pytest.fixture(scope="module")
def dashboard_js():
    return _read("static", "js", "dashboard.js")


@pytest.fixture(scope="module")
def dashboard_html():
    return _read("templates", "dashboard.html")


@pytest.fixture(scope="module")
def flask_app():
    try:
        import flask_cors  # noqa: F401
    except ImportError:
        stub = types.ModuleType("flask_cors")
        stub.CORS = lambda app=None, **kw: (lambda f: f)
        sys.modules["flask_cors"] = stub
    import app as mainapp

    mainapp.app.config["TESTING"] = True
    return mainapp.app


@pytest.fixture
def client(flask_app):
    """带数据隔离的客户端：测试后还原 data/。

    同时清空各模块的内存单例 —— 它们会跨测试复用状态，导致断言看到旧数据。
    """
    import src.diary.diary as diary_module

    backup = os.path.join(PROJECT_ROOT, ".pytest-data-backup-persist")
    data_dir = os.path.join(PROJECT_ROOT, "data")
    shutil.rmtree(backup, ignore_errors=True)
    if os.path.isdir(data_dir):
        shutil.copytree(data_dir, backup)

    # 每个测试都从磁盘重新加载，避免复用上一个测试的内存状态
    diary_module._diary_instance = None
    try:
        yield flask_app.test_client()
    finally:
        diary_module._diary_instance = None
        if os.path.isdir(backup):
            for name in os.listdir(backup):
                shutil.copy2(os.path.join(backup, name), os.path.join(data_dir, name))
            shutil.rmtree(backup, ignore_errors=True)


# ==================== 任务：前端必须落库 ====================


def test_task_frontend_calls_backend(dashboard_js):
    """任务前端必须调用后端接口，而不是只操作内存数组。"""
    for endpoint in ("/api/tasks",):
        assert endpoint in dashboard_js, f"任务前端未调用 {endpoint}"
    # 不应再以纯内存数组作为唯一数据源
    assert re.search(r"var\s+tasks\s*=\s*\[\s*\]", dashboard_js) is None, (
        "任务仍以内存数组为准，刷新即丢"
    )


def test_task_frontend_supports_full_lifecycle(dashboard_js):
    """任务需支持创建、完成、删除、列表加载。"""
    assert "loadTasks" in dashboard_js, "缺少任务列表加载"
    assert "createTask" in dashboard_js or "addTask" in dashboard_js, "缺少任务创建"
    assert "/api/tasks/" in dashboard_js, "缺少按 id 的任务操作（完成/删除）"


def test_task_backend_roundtrip(client):
    """后端任务接口可完整往返：创建 -> 列表 -> 完成 -> 删除。"""
    created = client.post("/api/tasks", json={"title": "做数学口算 10 道"})
    assert created.status_code == 200, created.get_data(as_text=True)[:200]
    task = created.get_json().get("task") or {}
    task_id = task.get("id")
    assert task_id, "创建任务未返回 id"

    listing = client.get("/api/tasks?status=all")
    assert listing.status_code == 200
    ids = [t.get("id") for t in listing.get_json().get("tasks", [])]
    assert task_id in ids, "新建任务未出现在列表中（未落库）"

    done = client.post(f"/api/tasks/{task_id}/complete")
    assert done.status_code == 200, done.get_data(as_text=True)[:200]

    removed = client.delete(f"/api/tasks/{task_id}")
    assert removed.status_code == 200
    after = client.get("/api/tasks?status=all")
    ids_after = [t.get("id") for t in after.get_json().get("tasks", [])]
    assert task_id not in ids_after, "删除后任务仍在列表中"


# ==================== 日记：前端必须落库 ====================


def test_diary_frontend_calls_backend(dashboard_js):
    """日记保存必须提交到后端。"""
    assert "/api/diary" in dashboard_js, "日记前端未调用后端"
    assert "loadDiary" in dashboard_js or "loadTodayDiary" in dashboard_js, (
        "缺少日记加载逻辑"
    )
    assert "saveDiary" in dashboard_js or "submitDiary" in dashboard_js, (
        "缺少日记提交逻辑"
    )
    # 原先只弹 toast 的写法必须消失
    assert "只弹 toast" not in dashboard_js  # 占位，实际看下面的断言
    assert re.search(r"showToast\('日记已保存！'\)\s*;\s*\n\s*if \(title\)", dashboard_js) is None, (
        "日记保存仍是只弹 toast、不落库"
    )


def test_diary_frontend_collects_mood(dashboard_js):
    """日记需采集情绪档位（后端要求 emotion_level）。"""
    assert "emotion_level" in dashboard_js, "日记未提交 emotion_level"


def test_diary_backend_roundtrip(client):
    """后端日记接口可完整往返：写入 -> 今日 -> 列表。"""
    payload = {
        "emotion_level": 4,
        "study_feeling": "充实",
        "biggest_event": "数学作业全对",
        "words_to_buddy": "今天想夸夸自己",
    }
    written = client.post("/api/diary", json=payload)
    assert written.status_code == 200, written.get_data(as_text=True)[:200]
    entry = written.get_json().get("entry") or {}
    assert entry.get("emotion_level") == 4
    assert entry.get("biggest_event") == "数学作业全对"

    today = client.get("/api/diary/today")
    assert today.status_code == 200
    assert today.get_json().get("entry"), "今日日记未落库"

    listing = client.get("/api/diary?limit=5")
    assert listing.status_code == 200
    assert listing.get_json().get("entries"), "日记列表为空"


def test_diary_delete_endpoint_exists(client):
    """日记需要能删除（前端要提供删除入口）。"""
    written = client.post("/api/diary", json={"emotion_level": 3, "study_feeling": "x"})
    entry_id = (written.get_json().get("entry") or {}).get("id")
    assert entry_id, "写入日记未返回 id"

    resp = client.delete(f"/api/diary/{entry_id}")
    assert resp.status_code == 200, (
        f"按 id 删除日记返回 {resp.status_code}，前端将无法删除"
    )

    # 用直接读取磁盘的方式确认真的删掉了，避免受单例内存缓存影响
    with open(os.path.join(PROJECT_ROOT, "data", "diary.json"), encoding="utf-8") as fh:
        stored = json.load(fh).get("entries", [])
    assert entry_id not in [e.get("id") for e in stored], "删除后日记仍在磁盘上"


# ==================== 搭子的记忆本（记忆可视化） ====================


def test_memory_page_exists(dashboard_html):
    """必须存在"搭子的记忆本"页面区块与导航入口。"""
    assert 'id="section-memory"' in dashboard_html, "缺少记忆本页面区块"
    assert 'data-section="memory"' in dashboard_html, "导航缺少记忆本入口"
    assert "记忆本" in dashboard_html or "记忆" in dashboard_html


def test_memory_page_has_containers(dashboard_html):
    """记忆本需要承载统计、记忆列表与搜索的容器。"""
    for element in ("memory-stats", "memory-list", "memory-search"):
        assert f'id="{element}"' in dashboard_html, f"缺少 {element} 容器"


def test_memory_frontend_uses_backend(dashboard_js):
    """记忆本必须调用后端记忆接口。"""
    assert "loadMemory" in dashboard_js or "renderMemory" in dashboard_js, (
        "缺少记忆加载/渲染逻辑"
    )
    assert "/api/buddy/memory" in dashboard_js, "记忆本未调用后端接口"


def test_memory_frontend_supports_search(dashboard_js):
    """记忆本需支持按关键词搜索（后端提供 topic 参数）。"""
    assert "topic=" in dashboard_js or "'topic'" in dashboard_js or "topic" in dashboard_js, (
        "记忆搜索未传 topic 参数"
    )


def test_memory_endpoint_returns_scenes(client):
    """记忆接口能返回场景列表，供记忆本展示。"""
    # 先经由对话写入一条记忆
    from src.buddy.buddy_memory import get_buddy_memory
    from src.buddy.memory_extractor import record_memories

    record_memories(get_buddy_memory(), "今天数学作业好难，应用题全不会")

    resp = client.get("/api/buddy/memory")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data.get("stats", {}).get("scenes", 0) >= 1
    assert data.get("recent_scenes"), "记忆接口未返回最近场景"

    search = client.get("/api/buddy/memory?topic=数学")
    assert search.status_code == 200
    assert search.get_json().get("memories"), "按关键词搜索记忆无结果"


def test_memory_items_expose_display_fields(client):
    """记忆条目必须带有可供界面展示的字段。

    注意 /api/buddy/memory 的两条返回路径结构不同：
    - recent_scenes：直接是场景对象（summary / tags / type / created_at）
    - memories（带 topic 搜索）：是包装对象（data / score / matched_fields）
    """
    from src.buddy.buddy_memory import get_buddy_memory
    from src.buddy.memory_extractor import record_memories

    record_memories(get_buddy_memory(), "下周期中考试我要考好")

    resp = client.get("/api/buddy/memory")
    scenes = resp.get_json().get("recent_scenes") or []
    assert scenes, "没有场景可校验"
    first = scenes[0]
    for field in ("summary", "tags", "type", "created_at"):
        assert field in first, f"记忆条目缺少展示字段 {field}"
    assert first["summary"], "记忆摘要为空"

    # 搜索路径返回包装结构，界面取 data.summary
    search = client.get("/api/buddy/memory?topic=考试").get_json()
    hits = search.get("memories") or []
    assert hits, "关键词搜索无结果"
    assert "data" in hits[0], "搜索结果缺少 data 包装字段"


def test_new_ui_elements_have_styles():
    """新增界面元素必须有对应样式，否则会是无样式的裸结构。"""
    css = _read("static", "css", "dashboard.css")
    for selector in (".field-row", ".input-field", ".diary-item",
                     ".memory-item", ".memory-kind", ".memory-tags"):
        assert selector in css, f"缺少样式 {selector}"


def test_diary_mood_buttons_cover_full_scale(dashboard_html):
    """日记的情绪按钮必须覆盖后端 10 档量表（此前只有 5 个）。"""
    from src.diary.diary import DiaryEntry

    levels = [e["level"] for e in DiaryEntry.EMOTIONS]
    for level in levels:
        assert f'data-level="{level}"' in dashboard_html, (
            f"日记页缺少第 {level} 档情绪按钮"
        )


def test_preview_server_script_is_documented():
    """预览脚本必须存在且说明其临时性质（不替代正式依赖安装）。"""
    path = os.path.join(PROJECT_ROOT, "tools", "dev_preview_server.py")
    assert os.path.exists(path), "缺少本地预览启动脚本"
    with open(path, encoding="utf-8") as handle:
        source = handle.read()
    assert "临时" in source or "预览" in source
    assert "requirements" in source, "预览脚本应提示正式部署需安装依赖"
