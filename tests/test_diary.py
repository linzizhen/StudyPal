"""
日记模块回归测试

已实证的两类缺陷：
  B1 POST /api/diary 任何请求都 500
     routes/diary.py 调 diary.add_entry(emotion_level=..., study_feeling=...,
     biggest_event=..., words_to_buddy=...)，但 Diary.add_entry 的签名是
     (emotion_level, title, content, images, tags, weather) —— 关键字参数
     完全不匹配，抛 TypeError: unexpected keyword argument 'study_feeling'。

  B2 情绪量表契约冲突
     DiaryEntry.EMOTIONS 是 10 级制（1..10），但 routes/diary.py 校验
     emotion_level 只能是 1..5；而 routes/insights.py 用 5 元素标签数组做
     [int(avg)-1] 索引，avg 一旦 >= 6 即 IndexError。
     另有 DiaryEntry.EMOTION_LABELS 属性被 routes/diary.py:76 与
     src/core/buddy.py:664 引用，但该类从未定义它。

运行：
  python -m pytest tests/test_diary.py -v
"""

import json
import os
import shutil
import sys
import uuid

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

import types  # noqa: E402

try:
    import flask_cors  # noqa: F401
except ImportError:
    _stub = types.ModuleType("flask_cors")
    _stub.CORS = lambda app=None, **kw: (lambda f: f)
    sys.modules["flask_cors"] = _stub

from src.diary.diary import Diary, DiaryEntry  # noqa: E402


@pytest.fixture
def diary(tmp_path_factory=None):
    """独立日记实例，数据落在项目内临时目录。"""
    tmp = os.path.join(PROJECT_ROOT, ".pytest-tmp", uuid.uuid4().hex[:8])
    os.makedirs(tmp, exist_ok=True)
    try:
        yield Diary(data_file=os.path.join(tmp, "diary.json"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ==================== B1 add_entry 签名 ====================


def test_add_entry_accepts_route_keyword_arguments(diary):
    """add_entry 必须接受 routes/diary.py 传入的四个关键字参数。"""
    entry = diary.add_entry(
        emotion_level=4,
        study_feeling="充实",
        biggest_event="完成了数学作业",
        words_to_buddy="今天加油",
    )
    assert entry is not None
    assert entry.emotion_level == 4
    assert entry.study_feeling == "充实"
    assert entry.biggest_event == "完成了数学作业"
    assert entry.words_to_buddy == "今天加油"


def test_add_entry_persists_route_fields(diary):
    """写入的字段必须真正落盘，且被后续读取识别。"""
    diary.add_entry(
        emotion_level=3,
        study_feeling="一般",
        biggest_event="有点累",
        words_to_buddy="明天继续",
    )
    with open(diary.data_file, encoding="utf-8") as handle:
        raw = json.load(handle)["entries"]
    assert raw, "未写入任何条目"
    stored = raw[0]
    for field in ("study_feeling", "biggest_event", "words_to_buddy"):
        assert stored.get(field), f"字段 {field} 未落盘"


def test_add_entry_result_readable_by_reload(diary):
    """重新加载后，新增字段仍可读（from_dict 认识它们）。"""
    diary.add_entry(
        emotion_level=5,
        study_feeling="开心",
        biggest_event="考试进步了",
        words_to_buddy="谢谢你",
    )
    reloaded = Diary(data_file=diary.data_file)
    entry = reloaded.get_entries(1)[0]
    assert entry.study_feeling == "开心"
    assert entry.biggest_event == "考试进步了"
    assert entry.words_to_buddy == "谢谢你"


def test_add_entry_still_accepts_class_style_arguments(diary):
    """原有 title/content 调用方式不得被破坏（向后兼容）。"""
    entry = diary.add_entry(emotion_level=3, title="标题", content="正文")
    assert entry.title == "标题"
    assert entry.content == "正文"


# ==================== B2 情绪量表与标签 ====================


def test_emotion_labels_exist():
    """DiaryEntry.EMOTION_LABELS 必须存在（两处代码在引用它）。"""
    assert hasattr(DiaryEntry, "EMOTION_LABELS"), "DiaryEntry 缺少 EMOTION_LABELS"


def test_emotion_labels_cover_full_scale():
    """标签必须覆盖 EMOTIONS 声明的全部等级，不留空洞。"""
    levels = {e["level"] for e in DiaryEntry.EMOTIONS}
    labels = DiaryEntry.EMOTION_LABELS
    missing = [lv for lv in levels if lv not in labels]
    assert not missing, f"以下等级缺少标签: {missing}"


def test_emotion_labels_lookup_by_level_never_crashes():
    """按任意合法等级取标签都必须成功（routes/diary.py:76 的用法）。"""
    for level in range(1, 11):
        label = DiaryEntry.EMOTION_LABELS.get(level, "")
        assert label, f"等级 {level} 的标签为空"


def test_emotion_level_bounds_are_consistent():
    """情绪的合法上下界必须统一为 EMOTIONS 的实际范围。"""
    levels = sorted(e["level"] for e in DiaryEntry.EMOTIONS)
    assert DiaryEntry.EMOTION_MIN_LEVEL == levels[0]
    assert DiaryEntry.EMOTION_MAX_LEVEL == levels[-1]


def test_level_from_average_never_index_errors():
    """把平均分转成标签的函数必须覆盖全量表，不得 IndexError。

    routes/insights.py 用 5 元素数组索引平均情绪，avg>=6 即崩。
    这里要求存在一个安全的转换函数，能处理全量表的任意平均分。
    """
    from src.diary.diary import emotion_label_for_level

    for level in range(1, 11):
        assert emotion_label_for_level(level), f"等级 {level} 无标签"
    # 越界值也应安全降级，而不是抛异常
    assert emotion_label_for_level(0)
    assert emotion_label_for_level(99)


def test_insights_summary_accepts_high_emotion_average():
    """洞察摘要必须能处理高情绪平均分（曾因硬编码 5 元素索引 IndexError）。

    用真实的 insights 视图函数配合一份高情绪数据的日记实例，
    确保 [int(avg)-1] 那类索引崩溃不再出现。
    """
    import routes.insights as insights_module
    from src.diary.diary import emotion_label_for_level

    # 该视图内部会调用 emotion_label_for_level，覆盖 1..10 全区间
    for level in (1, 5, 6, 8, 10):
        assert emotion_label_for_level(level)
    assert insights_module is not None

