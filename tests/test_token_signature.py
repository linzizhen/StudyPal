"""
Token 签名与身份伪造回归测试

已实证的缺陷：_generate_token 产出 ``<随机hex>.<user_id>:<ts>:<随机hex>``，
但 _verify_token 只解析 payload 的 user_id 与时间戳，**从不校验前半段"签名"**。
后果：任何人构造 ``任意串.<user_id>:<当前时间>:任意`` 即可冒充该用户。

运行：
  python -m pytest tests/test_token_signature.py -v
"""

import os
import sys
import time

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.auth import auth as auth_module  # noqa: E402


@pytest.fixture
def secret(monkeypatch):
    """固定签名密钥，保证测试可复现。"""
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-for-signature")
    monkeypatch.setattr(auth_module, "_get_signing_key", lambda: b"test-signing-key")
    return True


def test_generated_token_is_accepted(secret):
    """自签发的 token 必须能通过校验。"""
    token = auth_module._generate_token(42)
    assert auth_module._verify_token(token) == 42


def test_forged_token_without_signature_is_rejected(secret):
    """无有效签名的伪造 token 必须被拒绝。"""
    forged = "f" * 32 + "." + f"1:{int(time.time())}:x"
    assert auth_module._verify_token(forged) is None, "伪造 token 被接受，存在身份伪造漏洞"


@pytest.mark.parametrize("victim_id", [1, 2, 99, 999999])
def test_cannot_enumerate_arbitrary_user_ids(secret, victim_id):
    """不得能通过改 payload 冒充任意 user_id。"""
    forged = "a" * 32 + "." + f"{victim_id}:{int(time.time())}:y"
    assert auth_module._verify_token(forged) is None


def test_expired_token_is_rejected(secret):
    """超过 24 小时的 token 必须失效。"""
    issued = auth_module._generate_token(7)
    assert auth_module._verify_token(issued) == 7

    # 直接构造一个已过期的签名 token
    expired_at = int(time.time()) - 86401
    expired = auth_module._sign_payload(f"7:{expired_at}:deadbeef")
    assert auth_module._verify_token(expired) is None, "过期 token 未被拒绝"


def test_tampered_user_id_is_rejected(secret):
    """改动 payload 中的 user_id 必须导致签名失效。"""
    token = auth_module._generate_token(5)
    payload = token.split(".", 1)[1]
    parts = payload.split(":")
    tampered_payload = ":".join(["6"] + parts[1:])
    tampered = token.split(".", 1)[0] + "." + tampered_payload
    assert auth_module._verify_token(tampered) is None, "篡改 user_id 后仍被接受"


def test_malformed_tokens_are_rejected(secret):
    """各类畸形输入一律拒绝，不得抛异常。"""
    for bad in ("", "no-dot", "only.", ".", "a.b.c:d:e", "x.y:z:w", None):
        assert auth_module._verify_token(bad) is None


def test_signature_depends_on_secret(monkeypatch):
    """换密钥后，旧 token 必须失效（说明签名真正绑定密钥）。"""
    monkeypatch.setattr(auth_module, "_get_signing_key", lambda: b"key-one")
    token = auth_module._generate_token(3)
    assert auth_module._verify_token(token) == 3

    monkeypatch.setattr(auth_module, "_get_signing_key", lambda: b"key-two")
    assert auth_module._verify_token(token) is None, "换密钥后旧 token 仍有效"
