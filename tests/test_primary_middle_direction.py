"""
产品方向回归测试：小学到初中定位

锁定三类已完成的改造，防止回退到考研语境：
  C1 学段收敛为小学/初中（不含高中）
  C2 成就与文档去考研
  C3 目标/倒计时概念移除
  档案字段：target_school/target_major/target_score/exam_date 已废弃，
           改为 grade_mode / study_goal

运行：
  python -m pytest tests/test_primary_middle_direction.py -v
"""

import os
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.modules.challenge_manager import (  # noqa: E402
    DEFAULT_SUBJECTS,
    GRADE_LABELS,
    GRADE_MODES,
)


# ==================== C1 学段收敛 ====================


def test_grade_modes_only_primary_and_middle():
    """学段只保留小学与初中，不含高中。"""
    assert GRADE_MODES == ["primary", "middle"], (
        f"学段应为小学/初中两级，实际 {GRADE_MODES}"
    )
    assert "high" not in GRADE_LABELS
    assert set(GRADE_LABELS) == {"primary", "middle"}


def test_default_subjects_have_no_high_school():
    """学科模板不得包含高中。"""
    assert "high" not in DEFAULT_SUBJECTS
    assert set(DEFAULT_SUBJECTS) == {"primary", "middle"}


@pytest.mark.parametrize("grade_mode", ["primary", "middle"])
def test_each_grade_has_subjects(grade_mode):
    """每个学段都要有可用的学科模板。"""
    subjects = DEFAULT_SUBJECTS[grade_mode]
    assert subjects, f"{grade_mode} 没有学科模板"
    for subject in subjects:
        assert subject.get("name"), f"{grade_mode} 存在无名字的学科"
        assert "display_mode" in subject
        assert isinstance(subject.get("full_score"), int)


def test_primary_uses_star_display():
    """小学用星星（星级）呈现，更适合低龄。"""
    for subject in DEFAULT_SUBJECTS["primary"]:
        assert subject["display_mode"] == "star", (
            f"小学学科 {subject['name']} 未使用星级呈现"
        )


def test_migration_rejects_high_school():
    """挑战管理器不得接受高中作为学段。"""
    from src.modules.challenge_manager import ChallengeManager

    manager = ChallengeManager()
    with pytest.raises(ValueError):
        manager.set_grade_mode("high")


# ==================== C3 倒计时概念移除 ====================


def test_profile_has_no_exam_countdown_fields():
    """档案不得再包含考研向字段。"""
    from src.buddy.buddy_profile import BuddyProfile

    user_defaults = BuddyProfile.DEFAULT_DATA["user"]
    for obsolete in ("target_school", "target_major", "target_score", "exam_date"):
        assert obsolete not in user_defaults, f"档案仍保留废弃字段 {obsolete}"


def test_profile_uses_grade_mode_and_study_goal():
    """档案改为学段 + 学习目标。"""
    from src.buddy.buddy_profile import BuddyProfile

    user_defaults = BuddyProfile.DEFAULT_DATA["user"]
    assert "grade_mode" in user_defaults
    assert "study_goal" in user_defaults
    assert user_defaults["grade_mode"] in ("primary", "middle")


def test_days_remaining_no_longer_counts_down():
    """产品已不保留倒计时，get_days_remaining 应恒返回 -1。"""
    from src.buddy.buddy_profile import BuddyProfile

    assert BuddyProfile().get_days_remaining() == -1


def test_current_phase_is_not_exam_phase():
    """学习阶段不得再按考试倒计时划分（基础/强化/冲刺）。"""
    from src.buddy.buddy_profile import BuddyProfile

    phase = BuddyProfile().get_current_phase()
    for banned in ("冲刺阶段", "强化阶段", "基础阶段", "未设置目标"):
        assert phase != banned, f"阶段仍是考研向表述：{phase}"


def test_study_summary_has_no_countdown_or_school():
    """学习概况摘要不得出现目标院校 / 距离考试。"""
    from src.buddy.buddy_profile import BuddyProfile

    summary = BuddyProfile().get_study_summary()
    for banned in ("目标院校", "距离考试", "分数线", "考研"):
        assert banned not in summary, f"摘要仍含 {banned}：{summary}"


# ==================== C2 成就去考研 ====================


def test_achievements_contain_no_kaoyan_entries():
    """成就表不得再含考研专属条目。"""
    from src.modules.achievements import ALL_ACHIEVEMENTS

    ids = [a.id for a in ALL_ACHIEVEMENTS]
    for banned in ("kaoyan_start", "registration_done", "countdown_100",
                   "countdown_30", "countdown_7", "first_mock", "five_mocks",
                   "shang_an"):
        assert banned not in ids, f"仍存在考研成就 {banned}"

    texts = " ".join(a.name + (a.description or "") for a in ALL_ACHIEVEMENTS)
    for banned in ("考研", "上岸", "初试", "复试", "模拟考试"):
        assert banned not in texts, f"成就文案仍含考研词：{banned}"


def test_achievement_ids_stay_stable_for_shared_ones():
    """通用成就 id 必须保持不变（data/achievements.json 已按这些 id 记录）。"""
    from src.modules.achievements import ALL_ACHIEVEMENTS

    ids = {a.id for a in ALL_ACHIEVEMENTS}
    # 这些 id 已经被真实数据引用，改名会导致进度丢失
    for stable in ("first_pomodoro", "first_task", "three_day_streak",
                   "seven_day_streak", "early_bird", "night_owl"):
        assert stable in ids, f"通用成就 id 被误删：{stable}"


# ==================== 全仓库方向扫描 ====================


def test_python_sources_have_no_kaoyan_context():
    """后端源码不得把考研当语境（仅测试文件与显式禁令除外）。"""
    offenders = []
    for root, _dirs, files in os.walk(os.path.join(PROJECT_ROOT, "src")):
        for name in files:
            if not name.endswith(".py"):
                continue
            path = os.path.join(root, name)
            with open(path, encoding="utf-8") as handle:
                for line_no, line in enumerate(handle, start=1):
                    if "考研" not in line:
                        continue
                    # 允许出现：禁句，以及说明"旧版本/迁移/不再出现"的注释
                    if any(k in line for k in ("不要提", "不得", "旧版本", "已废弃",
                                               "旧版", "迁移", "不再出现")):
                        continue
                    rel = os.path.relpath(path, PROJECT_ROOT)
                    offenders.append(f"{rel}:{line_no}: {line.strip()}")
    assert not offenders, "后端仍有考研语境：\n  " + "\n  ".join(offenders)
