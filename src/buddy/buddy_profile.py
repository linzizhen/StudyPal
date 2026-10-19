"""
StudyPal 搭子档案模块
管理用户档案和搭子基本信息

包含：
- 孩子的学习信息（昵称、学段、学习目标）
- 搭子基本信息（名字、性格设定）

作者：StudyPal
日期：2026-04-27
重构日期：2026-04-30（文件锁保护）
"""

import json
import os
from datetime import datetime
from typing import Dict, Any, Optional
from src.utils.file_lock import atomic_read_json, atomic_write_json


class BuddyProfile:
    """
    搭子档案类
    
    管理用户档案和搭子基本信息
    """

    DEFAULT_DATA = {
        "user": {
            "name": "",
            # 学段：primary（小学）/ middle（初中）
            "grade_mode": "middle",
            # 学习目标：想达到的水平（替代旧版的院校/分数线）
            "study_goal": "",
            "study_type": "normal",
            "daily_goal_minutes": 60,
            "weak_subjects": [],
            "strong_subjects": [],
            "created_at": ""
        },
        "buddy": {
            "name": "小豆",
            "emoji": "🌸",
            "personality": "温柔但有原则",
            "introduction": "我是小豆，会陪你一起把功课变简单",
            "role_id": "xiaodou",
            "level": 1,
            "custom_name": None,
            "total_interactions": 0,
            "created_at": ""
        }
    }

    def __init__(self, data_file: str = "data/buddy_profile.json"):
        self.data_file = data_file
        self.data: Dict[str, Any] = {}
        self._load()

    def _load(self):
        """从文件加载数据"""
        data = atomic_read_json(self.data_file, self.DEFAULT_DATA.copy())
        self.data = data
        if "user" not in self.data:
            self.data["user"] = self.DEFAULT_DATA["user"].copy()
        else:
            # 旧数据字段迁移：考研向字段（target_school/target_major/
            # target_score/exam_date）已废弃，统一转为学段 + 学习目标。
            user = self.data["user"]
            defaults = self.DEFAULT_DATA["user"]
            user.setdefault("grade_mode", defaults["grade_mode"])
            user.setdefault("study_goal", defaults["study_goal"])
            user.setdefault("study_type", defaults["study_type"])
            user.setdefault("daily_goal_minutes", defaults["daily_goal_minutes"])
            user.setdefault("weak_subjects", [])
            user.setdefault("strong_subjects", [])
            user.setdefault("created_at", "")
            for obsolete in ("target_school", "target_major",
                             "target_score", "exam_date", "daily_goal_hours"):
                user.pop(obsolete, None)
        if "buddy" not in self.data:
            self.data["buddy"] = self.DEFAULT_DATA["buddy"].copy()
        else:
            defaults = self.DEFAULT_DATA["buddy"]
            buddy = self.data["buddy"]
            if "role_id" not in buddy:
                buddy["role_id"] = defaults["role_id"]
            if "level" not in buddy:
                buddy["level"] = defaults["level"]
            if "custom_name" not in buddy:
                buddy["custom_name"] = defaults["custom_name"]
            if "total_interactions" not in buddy:
                buddy["total_interactions"] = defaults["total_interactions"]
            if "emoji" not in buddy:
                buddy["emoji"] = defaults["emoji"]

    def _save(self):
        """保存数据到文件"""
        atomic_write_json(self.data_file, self.data)

    def get_profile(self) -> Dict[str, Any]:
        """获取完整档案"""
        profile = self.data.copy()
        # 合并数据库用户配置
        db_user = self._get_db_user()
        if db_user:
            profile["user"]["ai_model_key"] = db_user["ai_model_key"]
            profile["user"]["ai_custom_config"] = db_user["ai_custom_config"]
            profile["user"]["current_role_id"] = db_user.get("current_role_id")
            profile["user"]["grade_mode"] = db_user.get("grade_mode", "middle")
            profile["user"]["study_goal"] = db_user.get("study_goal", "")
            profile["buddy"]["role_id"] = db_user.get("current_role_id")
            if db_user.get("custom_buddy_name"):
                profile["buddy"]["name"] = db_user["custom_buddy_name"]
        return profile

    def _get_db_user(self):
        """从数据库获取当前用户（未登录时返回第一个用户）"""
        try:
            from flask import g, current_app
            if hasattr(g, 'current_user') and g.current_user:
                return g.current_user
            if hasattr(current_app, '_user') and current_app._user:
                return current_app._user
            # 未登录时：取 users.json 第一个用户作为配置载体
            from src.auth.auth import _load_users
            users = _load_users()
            if users:
                for u in users.values():
                    return u
        except Exception:
            pass
        return None

    def get_user(self) -> Dict[str, Any]:
        """获取用户信息"""
        return self.data.get("user", {}).copy()

    def get_buddy_info(self) -> Dict[str, Any]:
        """获取搭子信息"""
        return self.data.get("buddy", {}).copy()

    def is_setup_complete(self) -> bool:
        """检查档案是否设置完整

        产品已不保留"考试倒计时"概念，因此完整性以"有昵称 + 有学段"为准。
        """
        user = self.data.get("user", {})
        return bool(user.get("name") and user.get("grade_mode"))

    def update_user(self, **kwargs):
        """更新用户信息"""
        if "user" not in self.data:
            self.data["user"] = {}
        for key, value in kwargs.items():
            if key in [
                "name", "grade_mode", "study_goal", "study_type",
                "daily_goal_minutes", "weak_subjects", "strong_subjects"
            ]:
                self.data["user"][key] = value
        self._save()

    def update_buddy(self, **kwargs):
        """更新搭子信息"""
        if "buddy" not in self.data:
            self.data["buddy"] = {}
        allowed_fields = ["name", "personality", "introduction", "role_id", "level", "custom_name", "emoji"]
        for key, value in kwargs.items():
            if key in allowed_fields:
                self.data["buddy"][key] = value
        self._save()

    def get_buddy_role_id(self) -> str:
        """获取当前搭子角色ID"""
        return self.data.get("buddy", {}).get("role_id", "xiaodou")

    def get_buddy_level(self) -> int:
        """获取搭子等级"""
        return self.data.get("buddy", {}).get("level", 1)

    def increment_interactions(self):
        """增加交互次数"""
        if "buddy" not in self.data:
            self.data["buddy"] = {}
        self.data["buddy"]["total_interactions"] = self.data["buddy"].get("total_interactions", 0) + 1
        self._save()

    def get_days_remaining(self) -> int:
        """已废弃：产品不再保留"距离考试还有 N 天"概念。

        保留该方法仅为兼容既有调用方（buddy.py 的 get_full_status 等），
        恒返回 -1，表示"未设置倒计时"。
        """
        return -1

    def get_current_phase(self) -> str:
        """获取当前学习阶段

        不再依据考试倒计时推算，改为按累计学习时长粗略分档。
        """
        total_minutes = 0
        try:
            from src.study.study_tracker import get_study_tracker
            total_minutes = get_study_tracker().get_stats().get("total_minutes", 0) or 0
        except Exception:
            total_minutes = 0

        hours = total_minutes / 60
        if hours <= 0:
            return "刚起步"
        elif hours < 10:
            return "打基础"
        elif hours < 50:
            return "稳步学"
        else:
            return "学得很稳"

    def get_study_summary(self) -> str:
        """获取学习概况摘要（用于 AI 提示词）"""
        user = self.data.get("user", {})

        parts = []
        grade_labels = {"primary": "小学", "middle": "初中"}
        grade = user.get("grade_mode")
        if grade in grade_labels:
            parts.append(f"学段：{grade_labels[grade]}")
        if user.get("study_goal"):
            parts.append(f"学习目标：{user['study_goal']}")
        if user.get("weak_subjects"):
            parts.append("需要多练的科目：" + "、".join(user["weak_subjects"]))
        if user.get("strong_subjects"):
            parts.append("擅长的科目：" + "、".join(user["strong_subjects"]))

        phase = self.get_current_phase()
        parts.append(f"当前阶段：{phase}")

        return "，".join(parts) if parts else "还没有填写学习信息"

    def reset(self):
        """重置档案"""
        self.data = self.DEFAULT_DATA.copy()
        self.data["user"]["created_at"] = datetime.now().isoformat()
        self._save()


# 全局单例
_profile_instance: Optional[BuddyProfile] = None


def get_buddy_profile() -> BuddyProfile:
    """获取搭子档案实例"""
    global _profile_instance
    if _profile_instance is None:
        _profile_instance = BuddyProfile()
    return _profile_instance
