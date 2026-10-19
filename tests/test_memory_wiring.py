"""
记忆写入与主动关心回归测试

已实证的断点：
  活前端唯一在用的对话入口 /api/buddy/quick-chat 只**读取**记忆来构造提示词，
  却从不**写入**记忆。因此孩子和搭子聊再多，记忆库始终是空的 —— 表现就是
  "搭子记不住我说过的话"。

设计意图（用户原话）：AI 搭子要"记住关于孩子的一切"。这需要一个真正的
写入路径：从对话里抽取值得记住的信息并落到记忆库。

运行：
  python -m pytest tests/test_memory_wiring.py -v
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
def memory(tmp_path_factory=None):
    """独立记忆实例，数据落在项目内临时目录。"""
    tmp = os.path.join(PROJECT_ROOT, ".pytest-tmp", uuid.uuid4().hex[:8])
    os.makedirs(tmp, exist_ok=True)
    try:
        from src.buddy.buddy_memory import BuddyMemory

        yield BuddyMemory(data_file=os.path.join(tmp, "memory.json"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ==================== 记忆抽取器 ====================


def test_extractor_finds_subject_mention():
    """对话中提到具体科目时，应抽取为可记忆的场景。"""
    from src.buddy.memory_extractor import extract_memories

    found = extract_memories("今天数学作业好难，应用题全不会")
    kinds = [m["kind"] for m in found]
    assert kinds, "未从对话中抽取到任何记忆"
    assert any("数学" in str(m.get("tags", [])) or "数学" in m["summary"] for m in found), (
        f"未识别出科目：{found}"
    )


def test_extractor_finds_emotional_state():
    """表达负面情绪时，应抽取情绪档案备注。"""
    from src.buddy.memory_extractor import extract_memories

    found = extract_memories("我不想写作业了，好烦")
    assert any(m["kind"] == "emotion" for m in found), f"未识别出情绪：{found}"


def test_extractor_finds_goal_or_exam_event():
    """提到考试/目标时，应抽取为重要场景。"""
    from src.buddy.memory_extractor import extract_memories

    found = extract_memories("下周期中考试，我要考好一点")
    assert any(m["kind"] in ("event", "goal") for m in found), f"未识别出事件：{found}"


def test_extractor_ignores_small_talk():
    """无信息量的寒暄不应产生记忆，避免污染记忆库。"""
    from src.buddy.memory_extractor import extract_memories

    assert extract_memories("你好") == []
    assert extract_memories("嗯嗯") == []
    assert extract_memories("") == []
    assert extract_memories("哈哈") == []


def test_extractor_output_shape():
    """抽取结果必须是结构化的，便于写入记忆库。"""
    from src.buddy.memory_extractor import extract_memories

    found = extract_memories("今天数学考了 95 分，很开心")
    assert found, "未抽取到记忆"
    valid_kinds = ("scene", "subject", "emotion", "event", "goal")
    for item in found:
        assert item.get("kind") in valid_kinds, item
        assert isinstance(item.get("summary"), str) and item["summary"], item
        assert isinstance(item.get("tags"), list), item
        assert isinstance(item.get("importance"), int), item
        assert 1 <= item["importance"] <= 5, item


def test_extractor_importance_is_meaningful():
    """情绪波动与考试事件应比普通提及更重要。"""
    from src.buddy.memory_extractor import extract_memories

    plain = extract_memories("今天学了数学")
    strong = extract_memories("我这次考试没考好，好难过")
    plain_max = max((m["importance"] for m in plain), default=0)
    strong_max = max((m["importance"] for m in strong), default=0)
    assert strong_max >= plain_max, "重要事件的重要度不应低于普通提及"


# ==================== 写入记忆库 ====================


def test_recorder_persists_scene(memory):
    """抽取到的场景必须真正落到记忆库并可按关键词检索到。"""
    from src.buddy.memory_extractor import record_memories

    count = record_memories(memory, "今天数学作业好难")
    assert count >= 1, "没有写入任何记忆"
    assert memory.get_memory_stats().get("scenes", 0) >= 1

    hits = memory.recall("数学")
    assert hits, "写入后无法按关键词检索到"


def test_recorder_persists_emotion_note(memory):
    """情绪状态必须写入用户画像备注（供后续关怀使用）。"""
    from src.buddy.memory_extractor import record_memories

    record_memories(memory, "我不想写作业了，好烦")
    note = memory.get_profile_note("recent_feeling")
    assert note, "情绪未写入画像备注"


def test_recorder_survives_reload(memory):
    """写入的记忆必须持久化，重新加载后仍在。"""
    from src.buddy.buddy_memory import BuddyMemory
    from src.buddy.memory_extractor import record_memories

    record_memories(memory, "下周期中考试，我要考好")
    reloaded = BuddyMemory(data_file=memory.data_file)
    assert reloaded.get_memory_stats().get("scenes", 0) >= 1, (
        "重新加载后记忆丢失"
    )


def test_recorder_returns_zero_for_small_talk(memory):
    """寒暄不写入，返回 0，且记忆库保持不变。"""
    from src.buddy.memory_extractor import record_memories

    before = memory.get_memory_stats().get("scenes", 0)
    assert record_memories(memory, "你好") == 0
    assert memory.get_memory_stats().get("scenes", 0) == before


# ==================== 端点真的会写记忆 ====================


class _RecordingAI:
    def __init__(self):
        self.last_system_prompt = None

    def ask(self, question, system_prompt=None, save_to_history=True, **kwargs):
        self.last_system_prompt = system_prompt
        return {"answer": "我在呢"}

    def get_current_model_info(self):
        return {"key": "fake", "name": "假模型", "base_url": "", "model": ""}


@pytest.fixture
def client(tmp_path_factory=None):
    """带假 AI 与独立记忆库的测试客户端。"""
    tmp = os.path.join(PROJECT_ROOT, ".pytest-tmp", uuid.uuid4().hex[:8])
    os.makedirs(tmp, exist_ok=True)

    try:
        import flask_cors  # noqa: F401
    except ImportError:
        stub = types.ModuleType("flask_cors")
        stub.CORS = lambda app=None, **kw: (lambda f: f)
        sys.modules["flask_cors"] = stub

    recorder = _RecordingAI()
    import src.ai.ai_helper as ai_helper

    ai_helper.build_ai_from_user = lambda user: recorder

    import src.buddy.buddy_memory as memory_module

    mem = memory_module.BuddyMemory(data_file=os.path.join(tmp, "mem.json"))
    memory_module._memory_instance = mem

    import app as mainapp

    mainapp.app.config["TESTING"] = True
    try:
        yield mainapp.app.test_client(), mem, recorder
    finally:
        memory_module._memory_instance = None
        shutil.rmtree(tmp, ignore_errors=True)


def test_quick_chat_writes_memory(client):
    """对话端点必须在回答后把值得记住的信息写入记忆库（核心要求）。"""
    test_client, mem, _recorder = client

    before = mem.get_memory_stats().get("scenes", 0)
    resp = test_client.post(
        "/api/buddy/quick-chat",
        json={"buddy_id": "xiaodou", "message": "今天数学作业好难"},
    )
    assert resp.status_code == 200
    after = mem.get_memory_stats().get("scenes", 0)
    assert after > before, (
        "对话后记忆库没有新增任何场景 —— 搭子记不住孩子说过的话"
    )
    assert mem.recall("数学"), "写入的记忆无法按关键词召回"


def test_quick_chat_injects_existing_memory(client):
    """已存在的记忆必须被注入到发给模型的提示词里（让孩子被记住）。"""
    test_client, mem, recorder = client

    from src.buddy.memory_extractor import record_memories

    record_memories(mem, "孩子说他最喜欢数学，数学是强项")

    resp = test_client.post(
        "/api/buddy/quick-chat",
        json={"buddy_id": "xiaodou", "message": "今天学什么好"},
    )
    assert resp.status_code == 200
    sent = recorder.last_system_prompt or ""
    assert "数学" in sent, (
        f"已有记忆未被注入提示词，模型无从知晓孩子的偏好：{sent[:200]}"
    )


def test_quick_chat_small_talk_does_not_pollute_memory(client):
    """寒暄不得污染记忆库。"""
    test_client, mem, _recorder = client
    before = mem.get_memory_stats().get("scenes", 0)
    for msg in ("你好", "在吗", "嗯嗯"):
        test_client.post(
            "/api/buddy/quick-chat", json={"buddy_id": "xiaodou", "message": msg}
        )
    assert mem.get_memory_stats().get("scenes", 0) == before, (
        "寒暄也写入了记忆，记忆库会被无意义内容淹没"
    )


def test_memory_endpoint_lists_recorded_scenes(client):
    """记忆查询端点应能列出对话写入的场景。"""
    test_client, _mem, _recorder = client
    test_client.post(
        "/api/buddy/quick-chat",
        json={"buddy_id": "xiaodou", "message": "下周期中考试我要考好"},
    )
    resp = test_client.get("/api/buddy/memory")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data.get("stats", {}).get("scenes", 0) >= 1, (
        "记忆查询端点看不到对话写入的内容"
    )
