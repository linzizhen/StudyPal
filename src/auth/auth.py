"""
StudyPal 认证模块（轻量版）
不依赖 flask-sqlalchemy / pyjwt，使用内置实现

作者：StudyPal
日期：2026-05-21
"""

import json
import os
import time
import hmac
import secrets
import hashlib
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify, g, current_app

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
USERS_FILE = os.path.join(DATA_DIR, 'users.json')


def _ensure_data_dir():
    """确保数据目录存在"""
    os.makedirs(DATA_DIR, exist_ok=True)


def _load_users():
    """加载用户数据"""
    _ensure_data_dir()
    if not os.path.exists(USERS_FILE):
        return {}
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}


def _save_users(users):
    """保存用户数据"""
    _ensure_data_dir()
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2, default=str)


# ==================== 密码哈希 ====================
#
# 存储格式：pbkdf2_sha256$<迭代次数>$<盐(hex)>$<派生密钥(hex)>
#
# 历史上用的是无盐 SHA-256，已被彩虹表攻破（sha256("123456") 是公开已知值）。
# 现在改为 PBKDF2-HMAC-SHA256 + 每用户随机盐。为不打断存量用户登录，
# _verify_password 仍兼容旧格式，并在登录成功后把旧哈希就地升级为新格式。

_HASH_ALGORITHM = "pbkdf2_sha256"
_HASH_ITERATIONS = 200_000
_LEGACY_HEX_LENGTH = 64


def _hash_password(password: str) -> str:
    """生成加盐哈希。

    返回形如 ``pbkdf2_sha256$200000$<salt>$<digest>`` 的字符串。
    """
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        _HASH_ITERATIONS,
    )
    return f"{_HASH_ALGORITHM}${_HASH_ITERATIONS}${salt}${digest.hex()}"


def _is_legacy_hash(stored: str) -> bool:
    """判断是否为旧版无盐 SHA-256 哈希（64 位十六进制）。"""
    if not stored or not isinstance(stored, str):
        return False
    if stored.startswith(_HASH_ALGORITHM + "$"):
        return False
    if len(stored) != _LEGACY_HEX_LENGTH:
        return False
    try:
        int(stored, 16)
    except ValueError:
        return False
    return True


def _verify_password(password: str, stored: str) -> bool:
    """校验密码，兼容旧版无盐哈希。

    使用定时安全比较，避免通过响应时间侧信道推断哈希。
    """
    if not password or not stored or not isinstance(stored, str):
        return False

    if stored.startswith(_HASH_ALGORITHM + "$"):
        parts = stored.split("$")
        if len(parts) != 4:
            return False
        _, iterations, salt, expected = parts
        try:
            digest = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                bytes.fromhex(salt),
                int(iterations),
            )
        except (ValueError, TypeError):
            return False
        return secrets.compare_digest(digest.hex(), expected)

    if _is_legacy_hash(stored):
        legacy = hashlib.sha256(password.encode("utf-8")).hexdigest()
        return secrets.compare_digest(legacy, stored.lower())

    return False


def _get_signing_key() -> bytes:
    """获取 token 签名密钥。

    优先级：环境变量 SECRET_KEY > 本地持久化密钥文件 > 新生成并落盘。

    为什么必须持久化：若每次启动都随机生成，进程重启后所有已签发 token
    立即失效。

    并发安全：多 worker 部署（Dockerfile 用 gunicorn --workers 4）时，多个
    进程会同时首次初始化。若只用"检查文件 -> 生成 -> 写入"，各进程会各自
    生成不同密钥并争抢写入，先写者获胜，导致部分 worker 签发的 token 被
    其它 worker 拒绝、用户随机掉线。这里改用 O_CREAT|O_EXCL 原子创建：
    只有一个进程能创建成功，其余进程回到读取分支，从而拿到同一把密钥。
    """
    import os as _os

    env_secret = _os.getenv('SECRET_KEY')
    if env_secret:
        return env_secret.encode('utf-8')

    key_file = _os.path.join(DATA_DIR, '.signing_key')
    key_length = 32

    def _read_key():
        """读取密钥，只有长度正确才认可。

        为什么校验长度：写入方可能尚未写完，若只判断"非空"就会读到
        残缺内容（表现为长度多出或少掉几个字符），进而签发出与其它
        worker 不同的 token。
        """
        try:
            with open(key_file, 'rb') as handle:
                value = handle.read().strip()
        except OSError:
            return None
        if value and len(value) == key_length:
            return value
        return None

    try:
        _ensure_data_dir()

        existing = _read_key()
        if existing:
            return existing

        # 发布密钥采用"写临时文件 + link() 原子发布"：
        #
        # 为什么不用 O_CREAT|O_EXCL 直接写目标文件：该方式创建成功后、
        # 写入完成前，文件对其它进程是"存在但长度为 0"的，读者无法区分
        # "正在写入"与"已成空文件"，只能盲等。
        #
        # 为什么不用 rename/os.replace：rename 会无条件覆盖目标，
        # 多进程同时启动时后写者会覆盖先写者，导致先发布的进程持有的
        # 密钥与文件不一致。
        #
        # link() 的正确语义：仅当目标不存在时创建硬链接，目标已存在则
        # 抛 FileExistsError。因此恰好一个进程发布成功，其余进程转为读取
        # 那份已写完的完整内容。
        tmp_file = f"{key_file}.{secrets.token_hex(8)}.tmp"
        try:
            with open(tmp_file, 'wb') as handle:
                handle.write(secrets.token_bytes(key_length))
                handle.flush()
                _os.fsync(handle.fileno())
            try:
                _os.link(tmp_file, key_file)
                published = True
            except FileExistsError:
                # 已有其它进程抢先发布：丢弃自己的临时文件，去读那一份
                published = False
            except OSError:
                # 文件系统不支持硬链接（如部分网络盘）：退化为直接写入。
                # 此时可能出现覆盖，但已有环境变量 SECRET_KEY 作为首选
                # 方案覆盖该场景。
                with open(key_file, 'wb') as handle:
                    handle.write(secrets.token_bytes(key_length))
                    handle.flush()
                    _os.fsync(handle.fileno())
                published = True
        finally:
            try:
                if _os.path.exists(tmp_file):
                    _os.remove(tmp_file)
            except OSError:
                pass

        if published:
            value = _read_key()
            if value:
                return value

        # 去读已发布的那一份（带耐心等待，覆盖极端时序）
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            value = _read_key()
            if value:
                return value
            time.sleep(0.01)

        raise RuntimeError(
            f"签名密钥文件长期未就绪：{key_file}。"
            "请检查该文件权限，或改用环境变量 SECRET_KEY 显式指定密钥。"
        )
    except OSError:
        # 落盘不可用：退化为进程内临时密钥（仅当次运行有效）
        return secrets.token_bytes(key_length)


def _sign_payload(payload: str) -> str:
    """用 HMAC-SHA256 对 payload 签名，返回 ``<签名>.<payload>``。"""
    signature = hmac.new(
        _get_signing_key(), payload.encode('utf-8'), hashlib.sha256
    ).hexdigest()
    return f"{signature}.{payload}"


def _generate_token(user_id: int, ttl_seconds: int = 86400) -> str:
    """生成带 HMAC 签名的 Token。

    payload 形如 ``<user_id>:<签发时间戳>:<随机数>``，签名绑定整段 payload，
    因此改动 user_id 或时间戳都会导致签名校验失败。
    """
    payload = f"{user_id}:{int(time.time())}:{secrets.token_hex(8)}"
    return _sign_payload(payload)


def _verify_token(token: str):
    """验证 Token：先校验 HMAC 签名，再校验有效期。

    返回 user_id；任何异常情况（格式错误、签名不符、已过期）一律返回 None。
    """
    if not token or not isinstance(token, str):
        return None
    try:
        signature, separator, payload = token.partition('.')
        if not separator or not signature or not payload:
            return None

        expected = hmac.new(
            _get_signing_key(), payload.encode('utf-8'), hashlib.sha256
        ).hexdigest()
        # 定时安全比较，避免签名校验的时序侧信道
        if not secrets.compare_digest(signature, expected):
            return None

        fields = payload.split(':')
        if len(fields) < 2:
            return None
        user_id = int(fields[0])
        issued_at = int(fields[1])
        if time.time() - issued_at > 86400:
            return None
        return user_id
    except (ValueError, TypeError, AttributeError):
        return None


class AuthService:
    """认证服务（轻量版）"""

    @staticmethod
    def register(email: str, password: str, nickname: str = None) -> tuple:
        email = email.lower().strip()
        if '@' not in email or '.' not in email:
            return False, '邮箱格式不正确', None
        if len(password) < 6:
            return False, '密码至少6位', None

        users = _load_users()
        if email in users:
            return False, '该邮箱已注册', None

        nickname = nickname or email.split('@')[0][:20]
        user_id = len(users) + 1

        users[email] = {
            'id': user_id,
            'email': email,
            'password_hash': _hash_password(password),
            'nickname': nickname[:50],
            'avatar': '🌸',
            'subscription_tier': 'free',
            'subscription_expires': None,
            'ai_api_calls': 0,
            'ai_api_reset_date': None,
            'theme': 'light',
            'ai_model_key': None,
            'ai_custom_config': None,
            'current_role_id': 'xiaodou',
            'custom_buddy_name': None,
            # 学段与学习目标（替代旧版考研向字段）
            'grade_mode': 'middle',
            'study_goal': '',
            'daily_goal_minutes': 60,
            'total_study_hours': 0.0,
            'total_sessions': 0,
            'current_streak': 0,
            'longest_streak': 0,
            'created_at': datetime.now().isoformat(),
            'last_active': datetime.now().isoformat(),
            'is_active': True,
            'is_admin': False,
        }
        _save_users(users)

        user = users[email].copy()
        user['token'] = _generate_token(user_id)
        return True, '注册成功', user

    @staticmethod
    def login(email: str, password: str) -> tuple:
        email = email.lower().strip()
        users = _load_users()

        if email not in users:
            return False, '邮箱或密码错误', None, None

        user = users[email]
        if not _verify_password(password, user.get('password_hash', '')):
            return False, '邮箱或密码错误', None, None

        if not user.get('is_active', True):
            return False, '账号已被禁用', None, None

        # 存量用户仍在使用无盐 SHA-256：登录成功后就地升级为加盐哈希
        if _is_legacy_hash(user.get('password_hash', '')):
            user['password_hash'] = _hash_password(password)

        user['last_active'] = datetime.now().isoformat()
        _save_users(users)

        token = _generate_token(user['id'])
        user['token'] = token
        return True, '登录成功', user, token

    @staticmethod
    def get_user_by_id(user_id: int):
        """根据 ID 获取用户"""
        users = _load_users()
        for email, user in users.items():
            if user['id'] == user_id:
                return user
        return None

    @staticmethod
    def update_user(user_id: int, updates: dict):
        """更新用户信息"""
        users = _load_users()
        for email, user in users.items():
            if user['id'] == user_id:
                for key, value in updates.items():
                    if key not in ('id', 'email', 'password_hash'):
                        user[key] = value
                _save_users(users)
                return user
        return None

    # 新密码长度下限，与注册保持一致
    MIN_PASSWORD_LENGTH = 6

    @staticmethod
    def change_password(email: str, old_password: str, new_password: str) -> tuple:
        """校验旧密码后修改为新密码。

        返回 ``(是否成功, 提示信息)``。

        安全要点：
        - 必须校验旧密码，避免 token 被窃后直接改密码
        - 新密码不得与旧密码相同，也不得短于 MIN_PASSWORD_LENGTH
        - 新密码一律以加盐哈希存储（旧的无盐哈希在此被覆盖掉）
        """
        if not email or not old_password or not new_password:
            return False, '请填写完整信息'

        if len(new_password) < AuthService.MIN_PASSWORD_LENGTH:
            return False, f'新密码至少 {AuthService.MIN_PASSWORD_LENGTH} 位'

        if new_password == old_password:
            return False, '新密码不能和旧密码相同'

        email = email.lower().strip()
        users = _load_users()
        if email not in users:
            return False, '用户不存在'

        user = users[email]
        if not _verify_password(old_password, user.get('password_hash', '')):
            return False, '原密码不正确'

        user['password_hash'] = _hash_password(new_password)
        user['password_changed_at'] = datetime.now().isoformat()
        _save_users(users)
        return True, '密码已修改'

    @staticmethod
    def increment_ai_calls(user_id: int):
        """增加AI调用次数"""
        users = _load_users()
        for email, user in users.items():
            if user['id'] == user_id:
                user['ai_api_calls'] = user.get('ai_api_calls', 0) + 1
                _save_users(users)
                return
        _save_users(users)

    @staticmethod
    def get_all_users():
        """获取所有用户（管理员用）"""
        return _load_users()


def auth_required(f):
    """认证装饰器"""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({'success': False, 'error': '请先登录'}), 401

        token = auth_header[7:]
        user_id = _verify_token(token)
        if not user_id:
            return jsonify({'success': False, 'error': 'Token已过期，请重新登录'}), 401

        user = AuthService.get_user_by_id(user_id)
        if not user:
            return jsonify({'success': False, 'error': '用户不存在'}), 401
        if not user.get('is_active', True):
            return jsonify({'success': False, 'error': '账号已被禁用'}), 401

        g.current_user = user
        return f(*args, **kwargs)
    return decorated


def auth_optional(f):
    """可选认证装饰器"""
    @wraps(f)
    def decorated(*args, **kwargs):
        g.current_user = None
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]
            user_id = _verify_token(token)
            if user_id:
                user = AuthService.get_user_by_id(user_id)
                if user and user.get('is_active', True):
                    g.current_user = user
        return f(*args, **kwargs)
    return decorated


def get_current_user():
    """获取当前用户"""
    return getattr(g, 'current_user', None)


def subscription_required(required_tier='pro'):
    """订阅等级装饰器"""
    def decorator(f):
        @wraps(f)
        @auth_required
        def decorated(*args, **kwargs):
            user = get_current_user()
            tier_map = {'free': 0, 'pro': 1, 'vip': 2}
            user_level = tier_map.get(user.get('subscription_tier', 'free'), 0)
            required_level = tier_map.get(required_tier, 1)
            if user_level < required_level:
                return jsonify({
                    'success': False,
                    'error': f'此功能需要 {required_tier.upper()} 会员',
                    'upgrade_url': '/subscription'
                }), 403
            return f(*args, **kwargs)
        return decorated
    return decorator


def ai_limit_required(f):
    """AI调用限制装饰器"""
    @wraps(f)
    @auth_required
    def decorated(*args, **kwargs):
        user = get_current_user()
        tier = user.get('subscription_tier', 'free')
        limits = {'free': 100, 'pro': 1000, 'vip': 10000}
        limit = limits.get(tier, 100)
        calls = user.get('ai_api_calls', 0)
        if calls >= limit:
            return jsonify({
                'success': False,
                'error': '本月AI调用次数已用完，请升级会员',
                'upgrade_url': '/subscription'
            }), 429
        return f(*args, **kwargs)
    return decorated
