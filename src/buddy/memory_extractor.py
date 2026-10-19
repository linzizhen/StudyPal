"""
搭子记忆抽取器

职责：从孩子与搭子的对话里挑出**值得长期记住**的信息，转成结构化记忆。

为什么需要它：
  此前活前端使用的 /api/buddy/quick-chat 只读取记忆来构造提示词，却从不写入。
  结果是记忆库永远是空的 —— 表现为"搭子记不住我说过的话"。

设计原则：
  1. 只记有意义的内容。寒暄（"你好""在吗"）不得写入，否则记忆库会被噪音
     淹没，后续注入提示词时反而挤掉真正有用的信息。
  2. 面向小学到初中语境，科目/事件/情绪词表都按这个学段选取。
  3. 纯规则匹配、不调用大模型 —— 保证零延迟、零成本，且行为可预测、
     可测试（这也是本模块能被单元测试覆盖的前提）。
  4. 情绪与考试类事件的重要度高于普通提及，以便在记忆条数受限时优先保留。

作者：StudyPal
"""

import re
from typing import Any, Dict, List

# ==================== 词表 ====================

# 学科：小学到初中常见科目
SUBJECT_KEYWORDS: Dict[str, List[str]] = {
    "语文": ["语文", "作文", "生字", "古诗", "课文", "阅读", "听写", "默写"],
    "数学": ["数学", "应用题", "口算", "几何", "算术", "方程", "计算题"],
    "英语": ["英语", "单词", "听力", "语法", "音标", "背单词"],
    "物理": ["物理", "力学", "电路"],
    "化学": ["化学", "元素", "方程式"],
    "科学": ["科学", "实验", "观察"],
}

# 与学业相关的事件
EVENT_KEYWORDS = ["考试", "测验", "小测", "期中", "期末", "单元测", "竞赛", "比赛", "作业", "成绩", "分数"]

# 情绪：负面与正面分开，处理方式不同
NEGATIVE_EMOTIONS = ["难过", "伤心", "委屈", "烦", "生气", "害怕", "紧张", "焦虑", "崩溃",
                     "不想学", "不想写", "不想做", "讨厌", "累", "困", "压力大", "没考好",
                     "考砸", "不会", "听不懂", "难"]
POSITIVE_EMOTIONS = ["开心", "高兴", "兴奋", "进步", "考好了", "学会了", "搞懂了", "有趣",
                     "喜欢", "有意思", "骄傲", "棒"]

# 目标/意愿类表达
GOAL_KEYWORDS = ["我要", "我想", "目标", "计划", "打算", "争取", "一定要"]

# 纯寒暄：命中且无其它信息时不产生记忆
SMALL_TALK = ["你好", "在吗", "嗯", "哦", "哈哈", "在么", "嗨", "hi", "hello", "谢谢", "好的"]

# 重要度基准
IMPORTANCE = {
    "emotion_strong": 4,
    "event": 4,
    "subject": 3,
    "goal": 3,
    "default": 2,
}

# 场景类型映射
_SCENE_TYPE = {
    "subject": "conversation",
    "event": "milestone",
    "goal": "conversation",
    "emotion": "emotion",
}


def _has_small_talk_only(message: str) -> bool:
    """判断是否属于"只有寒暄、没有信息量"的消息。"""
    text = message.strip().lower()
    if not text:
        return True
    # 去掉标点与空白后，若整体就是寒暄词，视为无信息
    stripped = re.sub(r"[\s，。！？、,.!?~～]+", "", text)
    if not stripped:
        return True
    if stripped in SMALL_TALK:
        return True
    # 极短的纯语气词（长度 <= 2）也视为寒暄
    return len(stripped) <= 2


def _matched_subjects(message: str) -> List[str]:
    """命中哪些科目。"""
    hit = []
    for subject, keywords in SUBJECT_KEYWORDS.items():
        if any(kw in message for kw in keywords):
            hit.append(subject)
    return hit


def extract_memories(message: str, reply: str = "") -> List[Dict[str, Any]]:
    """从一轮对话中抽取值得记住的信息。

    参数:
        message: 孩子说的话
        reply:   搭子的回答（可选，用于记录搭子当时说了什么）

    返回:
        结构化记忆列表，每项含 kind / summary / details / tags / importance。
        没有值得记住的内容时返回空列表。
    """
    if not message or not isinstance(message, str):
        return []

    raw = message.strip()
    if _has_small_talk_only(raw):
        return []

    results: List[Dict[str, Any]] = []
    subjects = _matched_subjects(raw)
    negative = [kw for kw in NEGATIVE_EMOTIONS if kw in raw]
    positive = [kw for kw in POSITIVE_EMOTIONS if kw in raw]
    events = [kw for kw in EVENT_KEYWORDS if kw in raw]
    goals = [kw for kw in GOAL_KEYWORDS if kw in raw]

    # 1) 情绪（优先，重要度最高）
    if negative:
        results.append({
            "kind": "emotion",
            "summary": f"孩子提到情绪：{'、'.join(negative[:3])}",
            "details": raw[:200],
            "tags": ["情绪"] + negative[:3] + subjects,
            "importance": IMPORTANCE["emotion_strong"],
            "feeling": negative[0],
        })
    elif positive:
        results.append({
            "kind": "emotion",
            "summary": f"孩子心情不错：{'、'.join(positive[:3])}",
            "details": raw[:200],
            "tags": ["情绪"] + positive[:3] + subjects,
            "importance": IMPORTANCE["emotion_strong"] - 1,
            "feeling": positive[0],
        })

    # 2) 学业事件（考试/测验/作业）
    if events:
        label = "、".join(events[:2])
        summary = f"孩子提到{label}"
        if subjects:
            summary += f"（{'、'.join(subjects)}）"
        results.append({
            "kind": "event",
            "summary": summary,
            "details": raw[:200],
            "tags": ["事件"] + events[:2] + subjects,
            "importance": IMPORTANCE["event"],
        })

    # 3) 科目偏好/薄弱点
    if subjects and not events:
        results.append({
            "kind": "subject",
            "summary": f"孩子聊到了{'、'.join(subjects)}",
            "details": raw[:200],
            "tags": subjects,
            "importance": IMPORTANCE["subject"],
        })

    # 4) 目标/意愿
    if goals and len(raw) > 4:
        results.append({
            "kind": "goal",
            "summary": f"孩子表达了意愿：{raw[:40]}",
            "details": raw[:200],
            "tags": ["目标"] + subjects,
            "importance": IMPORTANCE["goal"],
        })

    return results


def record_memories(memory, message: str, reply: str = "") -> int:
    """把抽取到的记忆写入记忆库，返回写入条数。

    参数:
        memory:  BuddyMemory 实例
        message: 孩子说的话
        reply:   搭子的回答

    情绪类会额外写入画像备注键 ``recent_feeling``，
    供主动关心引擎判断孩子最近的状态。
    """
    items = extract_memories(message, reply)
    if not items:
        return 0

    written = 0
    for item in items:
        kind = item["kind"]
        scene_type = _SCENE_TYPE.get(kind, "conversation")
        try:
            memory.add_scene(
                summary=item["summary"],
                scene_type=scene_type,
                details=item.get("details", ""),
                tags=item.get("tags", []),
                feeling=item.get("feeling", ""),
                buddy_said=(reply or "")[:200],
                importance=item.get("importance"),
            )
            written += 1
        except TypeError:
            # 兼容 add_scene 未接受 importance 的实现
            memory.add_scene(
                summary=item["summary"],
                scene_type=scene_type,
                details=item.get("details", ""),
                tags=item.get("tags", []),
            )
            written += 1

        # 情绪额外写入画像备注，便于后续关怀与提示词注入
        if kind == "emotion":
            try:
                memory.set_profile_note("recent_feeling", item.get("feeling", "有波动"))
            except Exception:
                pass

    return written
