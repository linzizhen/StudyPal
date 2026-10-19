"""
搭子人设链路回归测试

核心要求（用户明确提出）：
  AI 搭子必须"走我们写的人设提示词"——每个角色性格不同、回答不同，
  且每个角色有自己的游戏化学习风格。

已实证的缺陷：
  /api/buddy/quick-chat（活前端唯一在用的对话入口）使用的是
  routes/buddy.py 里硬编码的 BUDDY_QUICK_SYSTEM —— 每个角色只有 2-3 句、
  且只有 5 个角色（缺 xj 戏精 / azheng 阿正，会被兜底成小豆）。
  它完全拿不到 src/buddy/buddy_roles.py 的 ROLE_STYLE_RULES（80 条口语化规则
  + 每角色专属风格），也拿不到 BUDDY_ROLES 的性格与词汇。
  后果：孩子点不同角色聊天时，AI 收到的人设几乎一样，"每个搭子回答不同"做不到。

运行：
  python -m pytest tests/test_role_persona.py -v
"""

import os
import shutil
import sys
import types

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

try:
    import flask_cors  # noqa: F401
except ImportError:
    _stub = types.ModuleType("flask_cors")
    _stub.CORS = lambda app=None, **kw: (lambda f: f)
    sys.modules["flask_cors"] = _stub

from src.buddy.buddy_roles import BUDDY_ROLES, ROLE_STYLE_RULES  # noqa: E402
from src.ai.prompt_templates import get_chat_system_prompt  # noqa: E402

ALL_ROLE_IDS = ["xiaodou", "aran", "senior", "xiaoye", "xj", "azheng"]

# 各角色的标志性特征词：用于验证"人设真的写进去了"
ROLE_MARKERS = {
    "xiaodou": ["温柔", "呀"],
    "aran": ["热血", "冲"],
    "senior": ["理性", "实验"],
    "xiaoye": ["深夜", "星辰"],
    "xj": ["幽默", "绝了"],
    "azheng": ["理性", "数据"],
}


# ==================== 提示词构造 ====================


@pytest.mark.parametrize("role_id", ALL_ROLE_IDS)
def test_chat_prompt_exists_for_every_role(role_id):
    """6 个角色都必须能拿到对话系统提示词（此前缺 2 个）。"""
    prompt = get_chat_system_prompt(role_id)
    assert prompt and isinstance(prompt, str)
    assert len(prompt) > 200, f"{role_id} 的提示词过短（{len(prompt)} 字），人设不完整"


@pytest.mark.parametrize("role_id", ALL_ROLE_IDS)
def test_chat_prompt_contains_role_style_rules(role_id):
    """提示词必须包含该角色的 ROLE_STYLE_RULES（80 条口语化规则 + 专属风格）。"""
    prompt = get_chat_system_prompt(role_id)
    style = ROLE_STYLE_RULES.get(role_id, "")
    assert style, f"{role_id} 没有风格规则"
    # 专属风格段落必须整体出现
    marker = "【" + BUDDY_ROLES[role_id]["name"] + "专属风格】"
    assert marker in prompt, f"{role_id} 的专属风格段未注入提示词"
    assert "口语化规则" in prompt, f"{role_id} 未包含全局口语化规则"


@pytest.mark.parametrize("role_id", ALL_ROLE_IDS)
def test_chat_prompt_carries_role_identity(role_id):
    """提示词必须带上该角色的名字与性格描述。"""
    role = BUDDY_ROLES[role_id]
    prompt = get_chat_system_prompt(role_id)
    assert role["name"] in prompt, f"{role_id} 的名字未出现"
    assert role["personality"] in prompt, f"{role_id} 的性格未出现"


def test_chat_prompts_are_distinct_between_roles():
    """不同角色的提示词必须彼此不同 —— 否则 AI 无法给出不同回答。"""
    prompts = {rid: get_chat_system_prompt(rid) for rid in ALL_ROLE_IDS}
    seen = {}
    for rid, text in prompts.items():
        for other_rid, other_text in seen.items():
            assert text != other_text, f"{rid} 与 {other_rid} 的提示词完全相同"
        seen[rid] = text


@pytest.mark.parametrize("role_id", ALL_ROLE_IDS)
def test_chat_prompt_is_age_appropriate(role_id):
    """面向小学到初中，对话提示词不得把考研当成场景。

    注意：提示词里允许出现"不要提考研"这类**禁令**，因此只检测
    "把考研作为背景/目标"的表述，而不是简单禁词扫描。
    """
    prompt = get_chat_system_prompt(role_id)

    # 这些是"把考研当语境"的表述，必须不存在
    banned_contexts = [
        "考研搭子",
        "陪用户考研",
        "正在陪孩子考研",
        "为了考研",
        "考研备考",
        "考研目标",
        "考研路",
    ]
    for banned in banned_contexts:
        assert banned not in prompt, f"{role_id} 提示词仍把考研当语境：{banned}"

    # 若出现"考研"，只能出现在禁令句里
    for line in prompt.splitlines():
        if "考研" in line:
            assert "不要提" in line or "不得" in line, (
                f"{role_id} 提示词在非禁令语境出现考研：{line.strip()}"
            )


def test_unknown_role_falls_back_to_default():
    """未知角色 id 必须安全兜底，不得抛异常。"""
    prompt = get_chat_system_prompt("not_a_real_role")
    assert prompt and "小豆" in prompt


# ==================== 端点真的用了人设提示词 ====================


class _RecordingAI:
    """记录 system_prompt 的假 AI，用于验证路由真的把人设传给了模型。"""

    def __init__(self):
        self.last_system_prompt = None
        self.calls = []

    def ask(self, question, system_prompt=None, save_to_history=True, **kwargs):
        self.last_system_prompt = system_prompt
        self.calls.append({"question": question, "system_prompt": system_prompt})
        return {"answer": f"reply-for-{question}"}

    def get_current_model_info(self):
        return {"key": "fake", "name": "假模型", "base_url": "", "model": ""}


@pytest.fixture
def client(monkeypatch):
    """带假 AI 的测试客户端，避免真实调用大模型。"""
    recorder = _RecordingAI()
    monkeypatch.setattr(
        "src.ai.ai_helper.build_ai_from_user", lambda user: recorder
    )
    import app as mainapp

    mainapp.app.config["TESTING"] = True
    return mainapp.app.test_client(), recorder


@pytest.fixture(autouse=True)
def isolate_real_data():
    """防止测试改动仓库真实数据。"""
    backup = os.path.join(PROJECT_ROOT, ".pytest-data-backup-persona")
    data_dir = os.path.join(PROJECT_ROOT, "data")
    shutil.rmtree(backup, ignore_errors=True)
    if os.path.isdir(data_dir):
        shutil.copytree(data_dir, backup)
    try:
        yield
    finally:
        if os.path.isdir(backup):
            for name in os.listdir(backup):
                shutil.copy2(os.path.join(backup, name), os.path.join(data_dir, name))
            shutil.rmtree(backup, ignore_errors=True)


@pytest.mark.parametrize("role_id", ALL_ROLE_IDS)
def test_quick_chat_sends_role_persona_to_model(client, role_id):
    """quick-chat 必须把该角色的人设提示词送给模型（核心要求）。"""
    test_client, recorder = client
    resp = test_client.post(
        "/api/buddy/quick-chat",
        json={"buddy_id": role_id, "message": "你好"},
    )
    assert resp.status_code == 200, f"{role_id} 调用失败"

    sent = recorder.last_system_prompt
    assert sent, "未向模型传 system_prompt"
    marker = "【" + BUDDY_ROLES[role_id]["name"] + "专属风格】"
    assert marker in sent, (
        f"发送给模型的提示词未包含 {role_id} 的人设，"
        f"实际发送内容片段：{sent[:120]}"
    )


def test_quick_chat_personas_differ_between_roles(client):
    """连续用不同角色提问，送给模型的提示词必须不同。"""
    test_client, recorder = client
    sent_by_role = {}
    for role_id in ALL_ROLE_IDS:
        test_client.post(
            "/api/buddy/quick-chat",
            json={"buddy_id": role_id, "message": "同一句话"},
        )
        sent_by_role[role_id] = recorder.last_system_prompt

    unique = set(sent_by_role.values())
    assert len(unique) == len(ALL_ROLE_IDS), (
        "存在多个角色发送了完全相同的提示词，人设未生效："
        + str({k: v[:40] for k, v in sent_by_role.items()})
    )


def test_quick_chat_accepts_frontend_alias_xuejie(client):
    """前端用 xuejie 作为学姐的 id，后端必须归一化为 senior。"""
    test_client, recorder = client
    resp = test_client.post(
        "/api/buddy/quick-chat",
        json={"buddy_id": "xuejie", "message": "你好"},
    )
    assert resp.status_code == 200
    sent = recorder.last_system_prompt
    assert "小老师" in sent, (
        f"xuejie 未映射到小老师人设，实际提示词：{sent[:120]}"
    )


# ==================== 提示词模块整体去考研 ====================


def test_no_prompt_template_uses_kaoyan_as_context():
    """整套提示词模板不得再把考研当语境（仅允许出现在禁令句中）。

    覆盖 prompt_templates.py 里除角色对话外的其他模板：
    情绪支持、学习计划、鼓励、每日总结、早安问候、周记、讲解、plan、method。
    """
    import inspect

    import src.ai.prompt_templates as pt

    source = inspect.getsource(pt)
    offenders = []
    for line_no, line in enumerate(source.splitlines(), start=1):
        if "考研" not in line:
            continue
        # 禁令句允许
        if "不要提" in line or "不得" in line:
            continue
        offenders.append(f"{line_no}: {line.strip()}")
    assert not offenders, "以下位置仍把考研当语境：\n  " + "\n  ".join(offenders)


def test_insight_prompt_speaks_to_a_child_not_a_kaoyan_candidate():
    """周记提示词不得出现考研搭子字样。"""
    from src.ai.prompt_templates import WEEKLY_INSIGHT_PROMPT

    assert "考研" not in WEEKLY_INSIGHT_PROMPT
    assert "学习搭子" in WEEKLY_INSIGHT_PROMPT
