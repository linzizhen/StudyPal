"""
密码修改能力测试

背景：项目原本没有任何"修改密码"入口 —— AuthService.update_user 在
字段白名单里明确排除了 password_hash，认证路由也只提供注册/登录/me。
配合已修复的无盐哈希与明文泄露风险，用户需要一个能自助改密码的入口。

运行：
  python -m pytest tests/test_password_change.py -v
"""

import hashlib
import os
import shutil
import sys
import types
import uuid

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.auth import auth as auth_module  # noqa: E402


@pytest.fixture
def temp_dir():
    """项目内临时目录（沙箱禁止写系统临时目录）。"""
    path = os.path.join(PROJECT_ROOT, ".pytest-tmp", uuid.uuid4().hex[:8])
    os.makedirs(path, exist_ok=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def users_file(temp_dir, monkeypatch):
    """把用户数据文件指向临时副本。"""
    path = os.path.join(temp_dir, "users.json")
    monkeypatch.setattr(auth_module, "USERS_FILE", path)
    return path


def _seed_user(users_file, password="origin-pw-123", legacy=False):
    """写入一个测试用户，返回其邮箱。"""
    email = "kid@test.local"
    if legacy:
        pwd_hash = hashlib.sha256(password.encode()).hexdigest()
    else:
        pwd_hash = auth_module._hash_password(password)
    with open(users_file, "w", encoding="utf-8") as handle:
        handle.write(
            '{"%s": {"id": 1, "email": "%s", "password_hash": "%s", '
            '"nickname": "小同学", "is_active": true}}' % (email, email, pwd_hash)
        )
    return email


# ==================== AuthService.change_password ====================


def test_change_password_requires_old_password(users_file):
    """旧密码错误时必须拒绝，且不得改动存储的哈希。"""
    email = _seed_user(users_file)
    before = auth_module._load_users()[email]["password_hash"]

    ok, message = auth_module.AuthService.change_password(
        email, "wrong-old-pw", "brand-new-pw"
    )
    assert ok is False, "旧密码错误却通过了"
    after = auth_module._load_users()[email]["password_hash"]
    assert after == before, "拒绝后哈希被改动了"


def test_change_password_succeeds_with_correct_old_password(users_file):
    """旧密码正确时应修改成功，且新密码可登录、旧密码不可登录。"""
    email = _seed_user(users_file)

    ok, _message = auth_module.AuthService.change_password(
        email, "origin-pw-123", "brand-new-pw"
    )
    assert ok is True

    # 新密码可登录
    login_ok, _m, _u, _t = auth_module.AuthService.login(email, "brand-new-pw")
    assert login_ok is True, "改密码后新密码无法登录"

    # 旧密码不可登录
    old_ok, _m2, _u2, _t2 = auth_module.AuthService.login(email, "origin-pw-123")
    assert old_ok is False, "改密码后旧密码仍可登录"


def test_new_password_is_salted(users_file):
    """新密码必须存为加盐哈希（不留旧的裸 SHA-256）。"""
    email = _seed_user(users_file)
    auth_module.AuthService.change_password(email, "origin-pw-123", "brand-new-pw")

    stored = auth_module._load_users()[email]["password_hash"]
    assert auth_module._is_legacy_hash(stored) is False, "新密码仍是无盐哈希"
    assert auth_module._verify_password("brand-new-pw", stored) is True


def test_change_password_rejects_weak_new_password(users_file):
    """新密码长度不足时拒绝（与注册保持一致的下限）。"""
    email = _seed_user(users_file)
    ok, message = auth_module.AuthService.change_password(email, "origin-pw-123", "123")
    assert ok is False
    assert "位" in message or "长度" in message

    # 确认未被改动
    login_ok, _m, _u, _t = auth_module.AuthService.login(email, "origin-pw-123")
    assert login_ok is True


def test_change_password_rejects_same_password(users_file):
    """新密码与旧密码相同时应拒绝，避免误操作假装修改成功。"""
    email = _seed_user(users_file)
    ok, _message = auth_module.AuthService.change_password(
        email, "origin-pw-123", "origin-pw-123"
    )
    assert ok is False


def test_change_password_unknown_user(users_file):
    """用户不存在时安全返回失败。"""
    _seed_user(users_file)
    ok, _message = auth_module.AuthService.change_password(
        "nobody@test.local", "whatever", "brand-new-pw"
    )
    assert ok is False


def test_change_password_works_for_legacy_hash_user(users_file):
    """存量无盐哈希用户也必须能改密码。"""
    email = _seed_user(users_file, legacy=True)
    ok, _message = auth_module.AuthService.change_password(
        email, "origin-pw-123", "brand-new-pw"
    )
    assert ok is True
    stored = auth_module._load_users()[email]["password_hash"]
    assert auth_module._is_legacy_hash(stored) is False
    login_ok, _m, _u, _t = auth_module.AuthService.login(email, "brand-new-pw")
    assert login_ok is True


def test_change_password_does_not_touch_other_fields(users_file):
    """改密码不得影响其它用户字段。"""
    email = _seed_user(users_file)
    auth_module.AuthService.change_password(email, "origin-pw-123", "brand-new-pw")
    user = auth_module._load_users()[email]
    assert user["nickname"] == "小同学"
    assert user["id"] == 1
    assert user["is_active"] is True


# ==================== 路由层 ====================


@pytest.fixture
def client(users_file):
    """带临时用户库的测试客户端。"""
    try:
        import flask_cors  # noqa: F401
    except ImportError:
        stub = types.ModuleType("flask_cors")
        stub.CORS = lambda app=None, **kw: (lambda f: f)
        sys.modules["flask_cors"] = stub

    import app as mainapp

    mainapp.app.config["TESTING"] = True
    return mainapp.app.test_client()


def test_password_endpoint_requires_authentication(client, users_file):
    """未登录不得改密码。"""
    _seed_user(users_file)
    resp = client.post(
        "/api/auth/password",
        json={"old_password": "origin-pw-123", "new_password": "brand-new-pw"},
    )
    assert resp.status_code in (401, 403), (
        f"匿名请求返回 {resp.status_code}，改密码接口必须要求登录"
    )


def test_password_endpoint_changes_password_when_authenticated(client, users_file):
    """已登录时改密码成功，并能用新密码登录。"""
    email = _seed_user(users_file)

    # 用正确密码登录拿到 token
    login_resp = client.post(
        "/api/auth/login", json={"email": email, "password": "origin-pw-123"}
    )
    assert login_resp.status_code == 200, "登录失败，无法继续测试"
    token = login_resp.get_json()["token"]

    resp = client.post(
        "/api/auth/password",
        json={"old_password": "origin-pw-123", "new_password": "brand-new-pw"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)[:200]
    assert resp.get_json().get("success") is True

    # 新密码可登录
    again = client.post(
        "/api/auth/login", json={"email": email, "password": "brand-new-pw"}
    )
    assert again.status_code == 200


def test_password_endpoint_rejects_wrong_old_password(client, users_file):
    """已登录但旧密码输错时应 400。"""
    email = _seed_user(users_file)
    login_resp = client.post(
        "/api/auth/login", json={"email": email, "password": "origin-pw-123"}
    )
    token = login_resp.get_json()["token"]

    resp = client.post(
        "/api/auth/password",
        json={"old_password": "not-the-password", "new_password": "brand-new-pw"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400, f"返回 {resp.status_code}，应拒绝错误的旧密码"


# ==================== 前端入口必须存在 ====================


def test_dashboard_has_password_form():
    """设置页必须提供改密码表单（否则功能存在但用户用不到）。"""
    with open(os.path.join(PROJECT_ROOT, "templates", "dashboard.html"),
              encoding="utf-8") as handle:
        html = handle.read()
    for required in ("old-password", "new-password", "new-password2",
                     "btn-change-password", "password-section"):
        assert required in html, f"设置页缺少改密码所需元素 {required}"
    assert "修改密码" in html


def test_dashboard_js_calls_password_api():
    """前端必须真的调用改密码接口，并在未登录时隐藏表单。"""
    with open(os.path.join(PROJECT_ROOT, "static", "js", "dashboard.js"),
              encoding="utf-8") as handle:
        js = handle.read()
    assert "/api/auth/password" in js, "前端未调用改密码接口"
    assert "initChangePassword" in js, "缺少改密码初始化函数"
    # 未登录时隐藏
    assert "password-section" in js, "前端未按登录状态控制改密码区域显隐"
    # 前端应做基本校验，减少无效请求
    assert "两次输入的新密码不一致" in js or "不一致" in js


def test_frontend_buddy_tables_cover_all_roles():
    """前端内存对话表与思考语表必须覆盖后端全部 6 个角色。

    已知历史缺陷：这两张表长期只有 4 个角色，导致新增角色（戏精/阿正）
    在切换后取不到数据、甚至报错。
    """
    import re

    from src.buddy.buddy_roles import BUDDY_ROLES

    with open(os.path.join(PROJECT_ROOT, "static", "js", "dashboard.js"),
              encoding="utf-8") as handle:
        js = handle.read()

    def keys_of(var_name):
        """取出某个对象字面量的顶层键。"""
        match = re.search(
            r"var\s+" + var_name + r"\s*=\s*\{(.*?)\n\};", js, re.DOTALL
        )
        assert match, f"未找到 {var_name} 的定义"
        body = match.group(1)
        return set(re.findall(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:", body, re.MULTILINE))

    expected = set(BUDDY_ROLES)
    conversations = keys_of("BUDDY_CONVERSATIONS")
    thinking = keys_of("BUDDY_THINKING")

    missing_c = sorted(expected - conversations)
    missing_t = sorted(expected - thinking)
    assert not missing_c, f"BUDDY_CONVERSATIONS 缺少角色：{missing_c}"
    assert not missing_t, f"BUDDY_THINKING 缺少角色：{missing_t}"


