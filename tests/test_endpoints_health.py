"""
端点健康度回归测试

用途：锁定"每个无参数 GET 端点都不得抛 500"这一契约。
背景：2026-07-16 勘察发现 9 个端点因以下三类缺陷直接 500：
  1. routes/buddy.py 调用 get_buddy() 但模块顶层未定义该名字（NameError）
  2. src/modules/daily_recommender.py 调用了 StudyTracker 上不存在的
     get_today_subjects()（AttributeError）
  3. src/routes/auth_routes.py 的 @auth_required 写在 @route 之上，
     Blueprint.route 返回原函数导致认证包装从未进入路由表，
     且 g.current_user 为 None 后 .get() 抛 AttributeError

运行：
  python -m pytest tests/test_endpoints_health.py -v
"""

import contextlib
import io
import logging
import os
import shutil
import types

import pytest

logging.disable(logging.CRITICAL)

# 项目根目录（tests/ 的上一级）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 数据目录与其中的 JSON 文件
DATA_DIR = os.path.join(PROJECT_ROOT, "data")


@pytest.fixture(scope="module", autouse=True)
def isolated_data_dir():
    """把 data/*.json 备份到临时目录，测试结束后逐一还原。

    这样端点回归测试即便触发写副作用（例如 GET /api/insights/weekly-insight
    会经 AI 自动创建会话），也不会污染仓库里的真实数据。

    注意：备份目录放在工作区内的 .pytest-data-backup/，因为沙箱不允许
    写入系统临时目录。
    """
    backup_dir = os.path.join(PROJECT_ROOT, ".pytest-data-backup")
    shutil.rmtree(backup_dir, ignore_errors=True)
    os.makedirs(backup_dir, exist_ok=True)

    # 备份真实数据
    for name in os.listdir(DATA_DIR):
        src = os.path.join(DATA_DIR, name)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(backup_dir, name))

    yield

    # 还原真实数据
    for name in os.listdir(backup_dir):
        shutil.copy2(os.path.join(backup_dir, name), os.path.join(DATA_DIR, name))
    shutil.rmtree(backup_dir, ignore_errors=True)


@pytest.fixture(scope="module")
def client():
    """构造 Flask 测试客户端；flask_cors 缺失时以最小存根替代。"""
    import sys

    sys.path.insert(0, PROJECT_ROOT)
    try:
        import flask_cors  # noqa: F401
    except ImportError:
        stub = types.ModuleType("flask_cors")
        stub.CORS = lambda app=None, **kw: (lambda f: f)
        sys.modules["flask_cors"] = stub

    import app as mainapp

    flask_app = mainapp.app
    flask_app.config["TESTING"] = True
    return flask_app.test_client()


@pytest.fixture(scope="module")
def app_obj():
    import sys

    sys.path.insert(0, PROJECT_ROOT)
    try:
        import flask_cors  # noqa: F401
    except ImportError:
        stub = types.ModuleType("flask_cors")
        stub.CORS = lambda app=None, **kw: (lambda f: f)
        sys.modules["flask_cors"] = stub

    import app as mainapp

    return mainapp.app


def _param_less_get_rules(flask_app):
    """收集所有无路径参数的 GET 规则。"""
    rules = []
    for rule in flask_app.url_map.iter_rules():
        path = str(rule)
        if path.startswith("/api/") and "GET" in rule.methods and "<" not in path:
            rules.append(path)
    return sorted(set(rules))


def _get_quietly(client, path):
    """发起请求并吞掉被探测端点写往 stdout/stderr 的日志。"""
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
        io.StringIO()
    ):
        return client.get(path)


def test_no_get_endpoint_returns_500(client, app_obj):
    """所有无参数 GET 端点都不得返回 5xx，也不得抛出未捕获异常。"""
    failures = []
    for path in _param_less_get_rules(app_obj):
        try:
            resp = _get_quietly(client, path)
        except Exception as exc:  # noqa: BLE001 - 探测目的就是捕获异常本身
            failures.append(f"{path} -> 未捕获 {type(exc).__name__}: {exc}")
            continue
        if resp.status_code >= 500:
            failures.append(f"{path} -> HTTP {resp.status_code}")

    assert not failures, "以下端点崩溃：\n  " + "\n  ".join(failures)


@pytest.mark.parametrize(
    "path",
    [
        "/api/buddy/roles",
        "/api/buddy/role",
        "/api/buddy/role/level",
    ],
)
def test_buddy_role_endpoints_reachable(client, path):
    """搭子角色类端点必须可访问（曾因 get_buddy 未定义抛 NameError）。"""
    resp = _get_quietly(client, path)
    assert resp.status_code == 200, f"{path} 返回 {resp.status_code}"


@pytest.mark.parametrize(
    "path",
    [
        "/api/recommend/daily",
        "/api/recommend/tasks",
    ],
)
def test_recommend_endpoints_reachable(client, path):
    """每日推荐端点必须可访问（曾因调用不存在的 get_today_subjects 抛 AttributeError）。"""
    resp = _get_quietly(client, path)
    assert resp.status_code == 200, f"{path} 返回 {resp.status_code}"


@pytest.mark.parametrize(
    "path",
    [
        "/api/auth/subscription",
        "/api/auth/ai/stats",
        "/api/auth/admin/users",
        "/api/auth/admin/stats",
    ],
)
def test_auth_required_endpoints_reject_anonymous(client, path):
    """需要登录的端点对匿名请求必须返回 401/403，而不是崩成 500。"""
    resp = _get_quietly(client, path)
    assert resp.status_code in (401, 403), (
        f"{path} 对匿名请求返回 {resp.status_code}，"
        "说明 @auth_required 未生效或视图未处理未登录状态"
    )


def test_get_endpoints_do_not_create_ai_conversations(client):
    """GET 端点不得产生写副作用。

    已知缺陷：GET /api/insights/weekly-insight 会调用 AI，而 AI 的 ask() 在
    current_conversation_id 为 None 时会执行 create_conversation()，导致一次
    只读请求凭空写入一条空会话（ai_history.json 里堆积了大量 messages 为空的
    "对话 N"）。

    触发条件是该单例的 current_conversation_id 为 None，因此这里显式把它清空，
    以稳定复现，而不是依赖测试执行顺序。
    """
    import json

    from src.ai import ai_helper

    history_file = os.path.join(DATA_DIR, "ai_history.json")

    def conversation_count():
        if not os.path.exists(history_file):
            return 0
        with open(history_file, encoding="utf-8") as handle:
            return len(json.load(handle).get("conversations", []))

    # 关键：清空单例的当前会话，强制走 create_conversation 分支
    singleton = ai_helper.get_ai_instance()
    singleton.current_conversation_id = None

    before = conversation_count()
    _get_quietly(client, "/api/insights/weekly-insight")
    after = conversation_count()

    assert after == before, (
        f"GET /api/insights/weekly-insight 写入了 {after - before} 条会话记录，"
        "只读端点不应产生副作用（应传 save_to_history=False 且不创建会话）"
    )
