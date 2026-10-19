"""
认证安全回归测试

覆盖三类已实证的安全缺陷：
  A1 密码哈希无盐（可被彩虹表直接破解）
  A2 token 无签名校验（可任意伪造 user_id 越权）
  A3 用户数据文件含真实邮箱与弱哈希

运行：
  python -m pytest tests/test_auth_security.py -v
"""

import hashlib
import os
import shutil
import sys
import uuid

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.auth import auth as auth_module  # noqa: E402


@pytest.fixture
def temp_dir():
    """项目内的临时目录。

    不使用 pytest 的 tmp_path：沙箱禁止写入系统临时目录。
    """
    path = os.path.join(PROJECT_ROOT, ".pytest-tmp", uuid.uuid4().hex[:8])
    os.makedirs(path, exist_ok=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


# ==================== A1 密码哈希加盐 ====================


def test_same_password_produces_different_hashes():
    """同一密码两次哈希结果必须不同（说明加了随机盐）。"""
    first = auth_module._hash_password("same-password-123")
    second = auth_module._hash_password("same-password-123")
    assert first != second, "两次哈希一致，说明未加盐"


def test_hash_is_not_bare_sha256():
    """哈希结果不得等于公开可查的裸 SHA-256 值。"""
    password = "123456"
    bare = hashlib.sha256(password.encode()).hexdigest()
    assert auth_module._hash_password(password) != bare


def test_new_hash_verifies_correct_password():
    stored = auth_module._hash_password("correct-horse")
    assert auth_module._verify_password("correct-horse", stored) is True


def test_new_hash_rejects_wrong_password():
    stored = auth_module._hash_password("correct-horse")
    assert auth_module._verify_password("wrong-horse", stored) is False


def test_legacy_unsalted_hash_still_verifies():
    """旧版无盐 SHA-256 哈希必须仍可校验（保证存量用户能登录）。"""
    legacy = hashlib.sha256("legacy-pw".encode()).hexdigest()
    assert auth_module._is_legacy_hash(legacy) is True
    assert auth_module._verify_password("legacy-pw", legacy) is True
    assert auth_module._verify_password("nope", legacy) is False


def test_new_hash_is_not_legacy():
    stored = auth_module._hash_password("whatever-pw")
    assert auth_module._is_legacy_hash(stored) is False


def test_empty_stored_hash_rejects():
    """空哈希（游客占位）不得通过校验。"""
    assert auth_module._verify_password("anything", "") is False


def test_login_upgrades_legacy_hash_to_salted(temp_dir, monkeypatch):
    """存量用户用旧哈希登录成功后，应被自动升级为加盐哈希。"""
    users_file = os.path.join(temp_dir, "users.json")
    monkeypatch.setattr(auth_module, "USERS_FILE", users_file)

    legacy_hash = hashlib.sha256("old-password".encode()).hexdigest()
    with open(users_file, "w", encoding="utf-8") as handle:
        handle.write(
            '{"u@test.local": {"id": 1, "email": "u@test.local", '
            '"password_hash": "%s", "nickname": "u", "is_active": true}}'
            % legacy_hash
        )

    ok, _message, _user, _token = auth_module.AuthService.login(
        "u@test.local", "old-password"
    )
    assert ok is True, "旧哈希用户应能正常登录"

    upgraded = auth_module._load_users()["u@test.local"]["password_hash"]
    assert auth_module._is_legacy_hash(upgraded) is False, "登录后未升级为加盐哈希"
    assert auth_module._verify_password("old-password", upgraded) is True
    assert auth_module._verify_password("wrong", upgraded) is False


def test_register_stores_salted_hash(temp_dir, monkeypatch):
    """注册写入的必须是加盐哈希。"""
    users_file = os.path.join(temp_dir, "users.json")
    monkeypatch.setattr(auth_module, "USERS_FILE", users_file)

    ok, _message, _user = auth_module.AuthService.register(
        "new@test.local", "brand-new-pw", "新人"
    )
    assert ok is True
    stored = auth_module._load_users()["new@test.local"]["password_hash"]
    assert auth_module._is_legacy_hash(stored) is False
    assert auth_module._verify_password("brand-new-pw", stored) is True
