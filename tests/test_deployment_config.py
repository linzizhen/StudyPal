"""
多进程部署下的签名密钥与部署配置测试

已实证的两个部署缺陷：
  D1 签名密钥竞态：_get_signing_key() 在无 SECRET_KEY 时执行
     "读文件 -> 不存在则生成 -> 写入"。Dockerfile 用 gunicorn --workers 4，
     4 个进程同时启动会各自生成不同密钥并争抢写入，导致部分 worker 签发的
     token 被其它 worker 拒绝，用户随机掉线。
  D2 docker-compose 空跑：定义了 PostgreSQL(db) 与 Redis(cache) 服务并让
     web 依赖它们的健康检查，但代码从不读取 DATABASE_URL / REDIS_URL；
     另引用仓库中不存在的 nginx.conf 与 ssl/。

运行：
  python -m pytest tests/test_deployment_config.py -v
"""

import os
import re
import shutil
import subprocess
import sys
import uuid

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def _read(*parts):
    with open(os.path.join(PROJECT_ROOT, *parts), encoding="utf-8") as handle:
        return handle.read()


@pytest.fixture(scope="module")
def compose():
    return _read("docker-compose.yml")


@pytest.fixture(scope="module")
def dockerfile():
    return _read("Dockerfile")


# ==================== D1 签名密钥并发安全 ====================


def test_signing_key_is_stable_across_calls():
    """同一环境内重复获取签名密钥必须得到同一把密钥。"""
    from src.auth import auth as auth_module

    first = auth_module._get_signing_key()
    second = auth_module._get_signing_key()
    assert first == second, "两次获取得到不同密钥，token 会互相失效"


def test_signing_key_survives_concurrent_first_init(tmp_path_factory=None):
    """模拟 4 个 worker 并发首次初始化，必须全部拿到同一把密钥。

    做法：把 DATA_DIR 指向一个空目录，用多进程同时调用 _get_signing_key()，
    再比较各进程得到的密钥是否一致。
    """
    tmp = os.path.join(PROJECT_ROOT, ".pytest-tmp", uuid.uuid4().hex[:8])
    os.makedirs(tmp, exist_ok=True)
    try:
        worker_script = os.path.join(tmp, "worker.py")
        out_dir = os.path.join(tmp, "out")
        os.makedirs(out_dir, exist_ok=True)
        with open(worker_script, "w", encoding="utf-8") as handle:
            handle.write(
                "import sys, os\n"
                f"sys.path.insert(0, {PROJECT_ROOT!r})\n"
                "from src.auth import auth as A\n"
                f"A.DATA_DIR = {tmp!r}\n"
                "key = A._get_signing_key()\n"
                "print(key.hex())\n"
            )

        # 并发启动 4 个进程
        env = dict(os.environ)
        env.pop("SECRET_KEY", None)
        procs = [
            subprocess.Popen(
                [sys.executable, worker_script],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
                cwd=PROJECT_ROOT,
            )
            for _ in range(4)
        ]
        keys = []
        for proc in procs:
            out, err = proc.communicate(timeout=60)
            text = out.decode().strip().splitlines()
            assert text, f"worker 未输出密钥：{err.decode()[:200]}"
            keys.append(text[-1])

        assert len(set(keys)) == 1, (
            f"并发初始化得到 {len(set(keys))} 把不同密钥，token 会互相失效：{keys}"
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_signing_key_respects_env_secret(monkeypatch):
    """设置 SECRET_KEY 时必须直接使用它（不落盘）。"""
    from src.auth import auth as auth_module

    monkeypatch.setenv("SECRET_KEY", "explicit-secret-value")
    assert auth_module._get_signing_key() == b"explicit-secret-value"


# ==================== D2 compose 与实际依赖一致 ====================


def test_compose_has_no_unused_database_service(compose):
    """compose 不得定义代码从不使用的 PostgreSQL 服务。"""
    assert "postgres" not in compose.lower(), (
        "compose 仍定义 PostgreSQL，但代码使用 JSON 文件存储"
    )
    assert "DATABASE_URL" not in compose, "compose 仍传递 DATABASE_URL，但无人读取"
    assert "DB_USER" not in compose, "compose 仍引用未使用的数据库凭据变量"


def test_compose_has_no_unused_redis_service(compose):
    """compose 不得定义代码从不使用的 Redis 服务。"""
    assert "redis" not in compose.lower(), (
        "compose 仍定义 Redis，但代码从不使用缓存服务"
    )
    assert "REDIS_URL" not in compose, "compose 仍传递 REDIS_URL，但无人读取"


def test_compose_only_references_existing_files(compose):
    """compose 挂载的文件必须真实存在，否则容器起不来。"""
    for match in re.finditer(r"-\s+\./([\w./-]+):", compose):
        rel = match.group(1)
        assert os.path.exists(os.path.join(PROJECT_ROOT, rel)), (
            f"compose 挂载了不存在的 {rel}"
        )


def test_compose_web_depends_on_nothing_missing(compose):
    """web 服务的 depends_on 不得指向已被移除的服务。"""
    web_block = compose.split("web:")[1].split("\n  #")[0]
    depends = re.search(r"depends_on:\n((?:\s+.*\n)+)", web_block)
    if depends:
        referenced = re.findall(r"^\s{6}(\w+):", depends.group(1), re.MULTILINE)
        defined = set(re.findall(r"^  (\w+):", compose, re.MULTILINE))
        for name in referenced:
            assert name in defined, f"depends_on 指向未定义的服务 {name}"


def test_compose_passes_secret_key_for_multi_worker(compose):
    """多 worker 部署必须显式提供 SECRET_KEY，否则签名密钥会靠文件竞态。"""
    assert "SECRET_KEY" in compose, "compose 未传递 SECRET_KEY"


def test_compose_mounts_data_dir(compose):
    """JSON 数据目录必须挂载出来，否则容器重建即丢数据。"""
    assert "./data:/app/data" in compose or "./data" in compose


# ==================== D2 Dockerfile 可用性 ====================


def test_dockerfile_healthcheck_command_is_available(dockerfile):
    """HEALTHCHECK 使用的工具必须在镜像里可用。

    python:3.11-slim 不含 curl，原 HEALTHCHECK 会恒失败。
    """
    has_healthcheck = "HEALTHCHECK" in dockerfile
    if not has_healthcheck:
        return
    uses_curl = "curl" in dockerfile.split("HEALTHCHECK")[1].split("\n\n")[0]
    if uses_curl:
        # 若用 curl，必须显式安装
        assert re.search(r"apt-get install[^\n]*curl|apt install[^\n]*curl", dockerfile), (
            "HEALTHCHECK 使用 curl，但 Dockerfile 未安装 curl"
        )


def test_dockerfile_does_not_install_unneeded_db_client(dockerfile):
    """不得为未使用的 PostgreSQL 安装 libpq-dev。"""
    assert "libpq-dev" not in dockerfile, (
        "Dockerfile 仍安装 libpq-dev，但不再使用 PostgreSQL"
    )


def test_dockerignore_exists_and_covers_noise():
    """.dockerignore 必须存在，避免把 .git/data/tests 打进镜像。"""
    path = os.path.join(PROJECT_ROOT, ".dockerignore")
    assert os.path.exists(path), "缺少 .dockerignore"
    with open(path, encoding="utf-8") as handle:
        content = handle.read()
    for entry in (".git", "tests", "__pycache__"):
        assert entry in content, f".dockerignore 未忽略 {entry}"


def test_dockerfile_copies_requirements_and_app(dockerfile):
    """基本构建步骤不得缺失。"""
    assert "COPY requirements.txt" in dockerfile
    assert "COPY . ." in dockerfile or "COPY ./" in dockerfile
    assert "app:app" in dockerfile, "启动命令未指向 app:app"


def test_env_production_has_no_obsolete_services():
    """.env.production 不得再宣传已不使用的数据库与缓存。"""
    content = _read(".env.production")
    assert "DATABASE_URL" not in content, ".env.production 仍含 DATABASE_URL"
    assert "REDIS_URL" not in content, ".env.production 仍含 REDIS_URL"
    assert "JWT" not in content, ".env.production 仍含 JWT 配置（认证为自制 Token）"
