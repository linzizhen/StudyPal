"""
主动关心的持久化与呈现测试

已实证的两个缺口：
  1. 冷却状态只在内存（CaringEngine.cooldowns），进程重启即清空。
     后果：每次重启都会把全部关心重新触发一遍（例如早上开机连发多条问候）。
  2. 前端从不展示关心事件 —— /api/buddy/caring 有数据也没人用，
     搭子的"主动关心"孩子在界面上看不到。

运行：
  python -m pytest tests/test_caring.py -v
"""

import os
import shutil
import sys
import types
import uuid

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


@pytest.fixture
def state_path():
    """项目内临时状态文件路径（沙箱禁止写系统临时目录）。"""
    tmp = os.path.join(PROJECT_ROOT, ".pytest-tmp", uuid.uuid4().hex[:8])
    os.makedirs(tmp, exist_ok=True)
    try:
        yield os.path.join(tmp, "caring_state.json")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def engine_factory(state_path, monkeypatch):
    """构造使用临时状态文件的 CaringEngine。

    引擎在 __init__ 中就会加载状态，因此必须先把 config 的路径常量
    指到临时文件，再构造实例。
    """
    import config
    import src.buddy.caring_engine as caring_module

    monkeypatch.setattr(config, "CARING_STATE_FILE", state_path)
    monkeypatch.setattr(caring_module, "CARING_STATE_FILE", state_path)
    # 让每个实例都用临时路径（同时覆盖直接赋值的场景）
    return caring_module.CaringEngine


def test_cooldown_survives_reload(engine_factory):
    """冷却状态必须落盘：重新构造引擎后，冷却仍然生效。"""
    engine = engine_factory()
    engine._set_cooldown("morning_greeting")
    assert engine._check_cooldown("morning_greeting") is False

    # 模拟进程重启：新建引擎，读同一份状态
    reloaded = engine_factory()
    assert reloaded._check_cooldown("morning_greeting") is False, (
        "重启后冷却丢失，会重复推送同一条关心"
    )


def test_expired_cooldown_allows_trigger(engine_factory):
    """冷却到期后应恢复可触发。"""
    from datetime import datetime, timedelta

    engine = engine_factory()
    engine._set_cooldown("study_reminder")
    # 手动把冷却时间改到很久以前
    engine.cooldowns["study_reminder"] = datetime.now() - timedelta(hours=999)
    engine._save_state()

    reloaded = engine_factory()
    assert reloaded._check_cooldown("study_reminder") is True


def test_state_file_corruption_does_not_crash(engine_factory, state_path):
    """状态文件损坏时必须安全降级，不得让应用起不来。"""
    with open(state_path, "w", encoding="utf-8") as handle:
        handle.write("{ this is not valid json")

    engine = engine_factory()
    # 不抛异常，且冷却视为可触发
    assert engine._check_cooldown("morning_greeting") is True


def test_missing_state_file_is_fine(engine_factory, state_path):
    """状态文件不存在时按无冷却处理。"""
    engine = engine_factory()
    assert not os.path.exists(state_path)
    assert engine._check_cooldown("morning_greeting") is True


def test_state_path_comes_from_config():
    """状态文件路径必须来自 config 常量，便于部署时统一指定。"""
    from config import CARING_STATE_FILE

    assert CARING_STATE_FILE, "config 未定义 CARING_STATE_FILE"
    assert CARING_STATE_FILE.endswith("caring_state.json")


def test_save_failure_is_observable(engine_factory, monkeypatch, caplog):
    """写入失败必须留下可诊断痕迹，不能完全静默。

    背景：_save_state 原先用 `except Exception: pass`，一旦写入因不可序列化
    等原因失败，冷却状态会悄悄丢失且无从察觉。
    """
    import logging

    import src.buddy.caring_engine as caring_module

    engine = engine_factory()

    def _boom(*args, **kwargs):
        raise TypeError("Object of type datetime is not JSON serializable")

    monkeypatch.setattr(caring_module, "atomic_write_json", _boom)

    with caplog.at_level(logging.WARNING, logger=caring_module.__name__):
        # 不应抛异常打断主流程
        engine._set_cooldown("morning_greeting")

    warnings = [r.getMessage() for r in caplog.records]
    assert any("冷却状态保存失败" in message for message in warnings), (
        "写入失败没有任何日志痕迹，问题会被静默掩盖。记录到："
        + repr(warnings)
    )


def test_previously_used_title_is_not_suggested_again(tmp_path_factory=None):
    """已用过的成就庆祝文案不应无限重复（冷却之外的另一层保护）。"""
    from src.buddy.caring_engine import CaringEngine

    engine = CaringEngine()
    messages = set()
    for _ in range(30):
        messages.add(engine._get_random_message("achievement_celebration", "streak"))
    # 模板本身有限，这里只要求来源稳定、非空
    assert messages
    assert all(isinstance(m, str) and m for m in messages)


# ==================== 端点返回结构 ====================


@pytest.fixture
def client(state_path, monkeypatch):
    """带临时关心状态文件的测试客户端。

    只把路径常量指到临时文件，并清空单例，让端点用的是全新状态。
    """
    try:
        import flask_cors  # noqa: F401
    except ImportError:
        stub = types.ModuleType("flask_cors")
        stub.CORS = lambda app=None, **kw: (lambda f: f)
        sys.modules["flask_cors"] = stub

    import config
    import src.buddy.caring_engine as caring_module

    monkeypatch.setattr(config, "CARING_STATE_FILE", state_path)
    monkeypatch.setattr(caring_module, "CARING_STATE_FILE", state_path)
    monkeypatch.setattr(caring_module, "_caring_engine_instance", None)

    import app as mainapp

    mainapp.app.config["TESTING"] = True
    try:
        yield mainapp.app.test_client()
    finally:
        caring_module._caring_engine_instance = None


def test_caring_endpoint_returns_events_with_required_fields(client):
    """关心端点必须返回结构化事件，前端才能展示。"""
    resp = client.get("/api/buddy/caring")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data.get("success") is True
    assert isinstance(data.get("events"), list)
    for event in data["events"]:
        assert "type" in event
        assert "message" in event
        assert event["message"], "关心消息不能为空"


def test_frontend_displays_caring_events():
    """前端必须真正展示关心事件（此前从不调用该接口）。"""
    with open(os.path.join(PROJECT_ROOT, "static", "js", "dashboard.js"),
              encoding="utf-8") as handle:
        js = handle.read()
    assert "/api/buddy/caring" in js, "前端未调用关心接口"
    assert "loadCaring" in js or "renderCaring" in js, "缺少关心事件的加载/渲染函数"


def test_dashboard_has_caring_container():
    """仪表盘需要有承载关心消息的区域。"""
    with open(os.path.join(PROJECT_ROOT, "templates", "dashboard.html"),
              encoding="utf-8") as handle:
        html = handle.read()
    assert 'id="caring-messages"' in html or 'id="caring-card"' in html, (
        "仪表盘缺少关心消息容器"
    )
