"""
StudyPal 搭子路由
处理搭子对话、档案、记忆相关 API

作者：StudyPal
日期：2026-04-27
更新：2026-05-21 支持多用户认证
"""

from flask import Blueprint, jsonify, request, g
from typing import Dict, Any, Optional

from src.auth.auth import auth_required, auth_optional, get_current_user, ai_limit_required
from src.core.buddy import get_buddy

buddy_bp = Blueprint('buddy', __name__, url_prefix='/api/buddy')


def get_user_buddy():
    """获取当前用户的 Buddy 实例（基于用户数据）"""
    return get_buddy()


@buddy_bp.route('/status', methods=['GET'])
@auth_optional
def get_buddy_status():
    """获取搭子完整状态"""
    user = get_current_user()
    if not user:
        return jsonify({
            'success': True,
            'status': {
                'buddy': {'name': '小豆', 'emoji': '🌸'},
                'profile': {'is_setup': False},
                'message': '请先登录'
            }
        })

    buddy = get_user_buddy()
    return jsonify({
        'success': True,
        'status': buddy.get_full_status()
    })


@buddy_bp.route('/chat', methods=['POST'])
def buddy_chat():
    """搭子对话（无需登录，用用户配置或默认配置）"""
    user = get_current_user()

    data = request.json or {}
    message = data.get('message', '').strip()
    conversation_id = data.get('conversation_id')

    if not message:
        return jsonify({'success': False, 'error': '消息不能为空'}), 400

    buddy = get_user_buddy()
    # 已登录则增加 AI 调用计数（轻量防护）
    if user is not None and hasattr(user, 'increment_ai_calls'):
        try:
            user.increment_ai_calls()
        except Exception:
            pass

    result = buddy.chat(message, conversation_id)

    return jsonify({
        'success': True,
        'reply': result['reply'],
        'conversation_id': result.get('conversation_id'),
        'emotion': result['emotion'],
        'emoji': result['emoji'],
        'emotion_desc': result.get('emotion_desc', ''),
        'suggestions': result.get('suggestions', [])
    })


# ========== 搭子轻量聊天（无需登录，读取当前用户的 AI 配置） ==========
#
# 人设来源说明（重要）：
# 这里不再维护第二份角色提示词。角色人设的唯一真源是
# src/buddy/buddy_roles.py（BUDDY_ROLES / ROLE_STYLE_RULES），
# 由 src/ai/prompt_templates.get_chat_system_prompt() 合并成对话提示词。
# 这样 6 个角色都能拿到完整人设（80 条口语化规则 + 专属风格），
# 不同角色的回答才会真正不同。


@buddy_bp.route('/quick-chat', methods=['POST'])
def buddy_quick_chat():
    """搭子轻量聊天（无需登录），读取当前用户已配置的 AI 模型。

    请求: { "buddy_id": "xiaodou", "message": "...", "explain_mode": "auto|game|speed" }
    返回: { "success": true, "reply": "...", "buddy_id", "buddy_name", "used_model" }
    """
    from src.ai.ai_helper import build_ai_from_user
    from src.buddy.buddy_roles import BUDDY_ROLES
    from src.ai.prompt_templates import get_chat_system_prompt, normalize_role_id
    from src.auth.auth import _load_users

    user = get_current_user()
    # 无登录时 fallback 到 users.json 第一个用户，确保能读到其 AI 配置
    if not user:
        try:
            users = _load_users() or {}
            if users:
                user = next(iter(users.values()))
        except Exception:
            user = None
    data = request.json or {}
    # 前端可能传 xuejie 等别名，统一归一化到权威角色 id
    buddy_id = normalize_role_id(data.get('buddy_id'))
    message = (data.get('message') or '').strip()
    explain_mode = (data.get('explain_mode') or 'auto').strip()

    if not message:
        return jsonify({'success': False, 'error': '消息不能为空'}), 400

    role = BUDDY_ROLES.get(buddy_id) or {}
    buddy_name = role.get('name', '小豆')

    # 组装人设提示词（含该角色专属风格 + 全局口语化规则 + 记忆与学习上下文）
    try:
        system_prompt = get_chat_system_prompt(
            role_id=buddy_id,
            user_name=(user or {}).get('nickname', '') or '',
            memory_context=_build_memory_context_for_chat(),
            study_summary=_build_study_summary_for_chat(),
        )
    except Exception:
        system_prompt = get_chat_system_prompt(role_id=buddy_id)

    # 根据讲解模式追加系统提示
    if explain_mode == 'game':
        system_prompt += "\n\n【当前模式：冒险探索】请用游戏化的方式回应：可以先抛出一个互动小问题，再给出鼓励。"
    elif explain_mode == 'speed':
        system_prompt += "\n\n【当前模式：学霸速读】请直接、高效、结构化地回答，少寒暄多干货。"

    try:
        ai = build_ai_from_user(user or {})
        result = ai.ask(
            question=message,
            system_prompt=system_prompt,
            save_to_history=False,
        )
        reply = (result.get('answer') or '').strip()
        return jsonify({
            'success': True,
            'reply': reply[:4000],
            'buddy_id': buddy_id,
            'buddy_name': buddy_name,
            'used_model': ai.get_current_model_info().get('name', ''),
        })
    except Exception as e:
        # 区分配置问题和网络/代理问题
        err_str = str(e)
        if 'ProxyError' in err_str or 'SSLError' in err_str or 'SSL' in err_str or 'ConnectionError' in err_str or '无法连接' in err_str:
            tip = '网络/SSL 错误，请检查代理设置、网络通畅、SSL 配置，或关闭窗口的代理插件后重试'
        else:
            tip = '请检查「设置 → AI 配置」中的 API 地址、密钥、模型名是否正确'
        return jsonify({
            'success': False,
            'error': f'AI 调用失败：{err_str}',
            'tip': tip
        }), 500


def _build_memory_context_for_chat() -> str:
    """取搭子记忆作为对话上下文；失败时静默降级为空串。

    这是"让 AI 记住孩子"的关键一步：把已有记忆注入人设提示词。
    """
    try:
        from src.buddy.buddy_memory import get_buddy_memory
        return get_buddy_memory().build_context_for_ai() or ""
    except Exception:
        return ""


def _build_study_summary_for_chat() -> str:
    """取最近学习情况；失败时静默降级为空串。"""
    try:
        from src.study.study_tracker import get_study_tracker
        stats = get_study_tracker().get_stats()
        parts = []
        streak = stats.get("streak_days", 0)
        today = stats.get("today_hours", 0)
        if streak:
            parts.append(f"已连续学习 {streak} 天")
        if today:
            parts.append(f"今天学了 {today:.1f} 小时")
        return "，".join(parts)
    except Exception:
        return ""


@buddy_bp.route('/profile', methods=['GET'])
@auth_optional
def get_buddy_profile():
    """获取用户档案"""
    from src.buddy.buddy_profile import get_buddy_profile
    profile = get_buddy_profile()

    return jsonify({
        'success': True,
        'profile': profile.get_profile(),
        'days_remaining': profile.get_days_remaining(),
        'current_phase': profile.get_current_phase(),
        'is_setup': profile.is_setup_complete()
    })


@buddy_bp.route('/profile', methods=['PUT', 'POST'])
@auth_optional
def update_buddy_profile():
    """更新用户档案"""
    from src.buddy.buddy_profile import get_buddy_profile
    profile = get_buddy_profile()
    data = request.json or {}
    profile.update_user(**data)

    return jsonify({
        'success': True,
        'message': '档案已更新',
        'profile': profile.get_profile()
    })


@buddy_bp.route('/memory', methods=['GET'])
@auth_optional
def get_buddy_memory():
    """获取搭子记忆"""
    from src.buddy.buddy_memory import get_buddy_memory
    memory = get_buddy_memory()

    topic = request.args.get('topic')
    if topic:
        memories = memory.recall(topic)
        return jsonify({
            'success': True,
            'type': 'search',
            'memories': memories
        })

    stats = memory.get_memory_stats()
    recent = memory.get_recent_scenes(7)

    return jsonify({
        'success': True,
        'type': 'overview',
        'stats': stats,
        'recent_scenes': recent
    })


@buddy_bp.route('/memory', methods=['POST'])
@auth_optional
def add_buddy_memory():
    """添加场景记忆"""
    from src.buddy.buddy_memory import get_buddy_memory
    memory = get_buddy_memory()
    data = request.json or {}

    scene_id = memory.add_scene(
        summary=data.get('summary', ''),
        scene_type=data.get('scene_type', 'conversation'),
        details=data.get('details', ''),
        tags=data.get('tags', [])
    )

    return jsonify({
        'success': True,
        'scene_id': scene_id
    })


@buddy_bp.route('/memory/search', methods=['GET'])
def search_buddy_memory():
    """语义搜索搭子记忆"""
    from src.buddy.buddy_memory import get_buddy_memory
    memory = get_buddy_memory()

    query = request.args.get('q', '')
    limit = request.args.get('limit', 5, type=int)

    results = memory.semantic_search(query, limit) if hasattr(memory, 'semantic_search') else memory.recall(query)[:limit]

    return jsonify({
        'success': True,
        'results': results
    })


@buddy_bp.route('/caring', methods=['GET'])
def get_caring_events():
    """获取主动关心事件"""
    from src.buddy.caring_engine import get_caring_engine
    caring = get_caring_engine()
    events = caring.check_all()

    return jsonify({
        'success': True,
        'events': [
            {
                'type': e.type,
                'message': e.message,
                'priority': e.priority
            }
            for e in events
        ]
    })


@buddy_bp.route('/achievement', methods=['POST'])
def trigger_achievement():
    """触发成就关心"""
    from src.buddy.caring_engine import get_caring_engine
    caring = get_caring_engine()
    data = request.json or {}

    event = caring.trigger_achievement(
        achievement_type=data.get('achievement_type', 'milestone'),
        sub_key=data.get('sub_key'),
        context=data.get('context', {})
    )

    if event:
        return jsonify({
            'success': True,
            'message': event.message,
            'type': event.type
        })

    return jsonify({
        'success': True,
        'message': '太棒了！你真厉害！',
        'type': 'achievement'
    })


# ========== 角色系统 API ==========

@buddy_bp.route('/roles', methods=['GET'])
def get_all_roles():
    """获取所有可选角色"""
    buddy = get_buddy()
    roles = buddy.get_all_roles()

    current_role_id = buddy.get_current_role_id()

    return jsonify({
        'success': True,
        'roles': roles,
        'current_role_id': current_role_id
    })


@buddy_bp.route('/role', methods=['GET'])
def get_current_role():
    """获取当前角色信息"""
    buddy = get_buddy()
    role = buddy.get_current_role()
    level_info = buddy.get_buddy_level_info()

    return jsonify({
        'success': True,
        'role': role,
        'level': level_info
    })


@buddy_bp.route('/role/switch', methods=['POST'])
def switch_role():
    """切换搭子角色"""
    data = request.json or {}
    role_id = data.get('role_id')

    if not role_id:
        return jsonify({'success': False, 'error': '请选择要切换的角色'}), 400

    buddy = get_buddy()
    result = buddy.switch_role(role_id)

    if result['success']:
        return jsonify({
            'success': True,
            'message': result['message'],
            'role': result['role'],
            'greeting': result['role']['greeting']
        })

    return jsonify({'success': False, 'error': result.get('message', '切换失败')}), 400


@buddy_bp.route('/role/level', methods=['GET'])
def get_buddy_level():
    """获取搭子等级信息"""
    buddy = get_buddy()
    level_info = buddy.get_buddy_level_info()

    return jsonify({
        'success': True,
        'level': level_info
    })


# ========== 知识点讲解 ==========

@buddy_bp.route('/explain', methods=['POST'])
def buddy_explain():
    """游戏化讲解：知识点 / 学习计划 / 学习方法"""
    from src.ai.prompt_templates import get_buddy_explain_prompt, parse_explain_response
    from src.ai.ai_helper import build_ai_from_user
    from src.buddy.buddy_roles import BUDDY_ROLES

    data = request.json or {}
    topic = (data.get('topic') or '').strip()
    role_id = (data.get('buddy_id') or 'xiaodou').strip()
    request_type = (data.get('request_type') or 'topic').strip()  # topic | plan | method

    if not topic:
        return jsonify({'success': False, 'error': '请输入内容'}), 400

    # 兼容前端会传的 xuejie → senior
    role_alias = {
        'xuejie': 'senior',
        'xiaodou': 'xiaodou',
        'aran': 'aran',
        'xiaoye': 'xiaoye',
    }
    role_id = role_alias.get(role_id, role_id)

    # 获取当前用户（如果登录了）
    user = get_current_user()

    # 获取角色信息（默认给一个）
    role = BUDDY_ROLES.get(role_id) or BUDDY_ROLES.get('xiaodou') or {}
    role_name = role.get('name', '小豆')
    role_emoji = role.get('emoji', '🌸')

    # 取系统提示词（plan/method 用通用模板，否则用搭子专属游戏化模板）
    system_prompt = get_buddy_explain_prompt(role_id, request_type)

    # 根据 request_type 生成不同的用户问题
    question_templates = {
        'plan': f"请帮我制定学习计划：{topic}（请严格按照 ---GAME_START---/---GAME_END---/---EXPLAIN_START---/---EXPLAIN_END--- 标记输出）",
        'method': f"请帮我推荐学习方法：{topic}（请严格按照 ---GAME_START---/---GAME_END---/---EXPLAIN_START---/---EXPLAIN_END--- 标记输出）",
    }
    user_question = question_templates.get(request_type,
        f"请帮我讲解这个知识点：{topic}（请严格按照 ---GAME_START---/---GAME_END---/---EXPLAIN_START---/---EXPLAIN_END--- 标记输出）")

    # card 标签（用于前端区分类型）
    card_labels = {
        'plan': '🎯 学习计划',
        'method': '💡 学习方法',
    }
    card_label = card_labels.get(request_type, '📖 知识点讲解')

    try:
        ai = build_ai_from_user(user or {})
        result = ai.ask(
            question=user_question,
            system_prompt=system_prompt,
            save_to_history=False,
        )
        raw = (result.get('answer') or '').strip()
        parsed = parse_explain_response(raw)

        parsed["game"] = (parsed.get("game") or "")[:4000]
        parsed["explain"] = (parsed.get("explain") or "")[:4000]

        return jsonify({
            'success': True,
            'buddy_id': role_id,
            'buddy_name': role_name,
            'buddy_emoji': role_emoji,
            'topic': topic,
            'request_type': request_type,
            'card_label': card_label,
            'game': parsed.get('game', ''),
            'explain': parsed.get('explain', ''),
            'used_model': ai.get_current_model_info().get('name', ''),
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'AI 调用失败：{str(e)}',
            'tip': '请检查「设置 → AI 配置」中的 API 地址、密钥、模型名是否正确'
        }), 500


# ========== 历史对话（需登录） ==========

def _ensure_history_list(user: dict):
    if not isinstance(user, dict):
        return []
    hist = user.get('buddy_conversations_history')
    if not isinstance(hist, list):
        hist = []
        user['buddy_conversations_history'] = hist
    return hist


@buddy_bp.route('/conversations', methods=['GET'])
@auth_optional
def list_conversations():
    """获取当前用户的历史对话列表"""
    user = get_current_user()
    if not user:
        return jsonify({'success': False, 'error': '请先登录'}), 401

    hist = _ensure_history_list(user)
    hist_sorted = sorted(hist, key=lambda x: x.get('updated_at', ''), reverse=True)
    return jsonify({'success': True, 'conversations': hist_sorted})


@buddy_bp.route('/conversation', methods=['POST'])
@auth_optional
def save_conversation():
    """保存当前对话到历史（追加到末尾，只保留最近 20 条）"""
    import uuid
    from datetime import datetime
    from src.auth.auth import _load_users, _save_users

    user = get_current_user()
    if not user:
        return jsonify({'success': False, 'error': '请先登录'}), 401

    data = request.json or {}
    buddy_id = (data.get('buddy_id') or '').strip()
    messages = data.get('messages') or []

    if not buddy_id:
        return jsonify({'success': False, 'error': 'buddy_id 不能为空'}), 400
    if not isinstance(messages, list) or len(messages) < 2:
        return jsonify({'success': False, 'error': '对话内容太少，无需保存'}), 400

    users = _load_users()
    user_dict = None
    for v in users.values():
        if v.get('id') == user.get('id'):
            user_dict = v
            break
    if not user_dict:
        return jsonify({'success': False, 'error': '用户不存在'}), 404

    hist = _ensure_history_list(user_dict)

    preview = ''
    for m in messages:
        if m.get('sender') == 'user':
            preview = (m.get('text') or '')[:30]
            break
    if not preview:
        preview = '新对话'

    from src.buddy.buddy_roles import BUDDY_ROLES
    role = BUDDY_ROLES.get(buddy_id) or {}

    conv = {
        'id': 'conv_' + uuid.uuid4().hex[:10],
        'buddy_id': buddy_id,
        'buddy_name': role.get('name', buddy_id),
        'buddy_avatar': role.get('emoji', '🤖'),
        'preview': preview,
        'message_count': len(messages),
        'created_at': datetime.now().isoformat(),
        'updated_at': datetime.now().isoformat(),
        'messages': messages,
    }
    hist.append(conv)
    if len(hist) > 20:
        hist[:] = hist[-20:]
    _save_users(users)

    return jsonify({'success': True, 'conversation': conv})


@buddy_bp.route('/conversation/<conv_id>', methods=['GET'])
@auth_optional
def get_conversation(conv_id):
    """获取某条历史对话详情"""
    user = get_current_user()
    if not user:
        return jsonify({'success': False, 'error': '请先登录'}), 401

    hist = _ensure_history_list(user)
    conv = next((c for c in hist if c.get('id') == conv_id), None)
    if not conv:
        return jsonify({'success': False, 'error': '对话不存在'}), 404
    return jsonify({'success': True, 'conversation': conv})


@buddy_bp.route('/conversation/<conv_id>', methods=['DELETE'])
@auth_optional
def delete_conversation(conv_id):
    """删除某条历史对话"""
    from src.auth.auth import _load_users, _save_users

    user = get_current_user()
    if not user:
        return jsonify({'success': False, 'error': '请先登录'}), 401

    users = _load_users()
    user_dict = None
    for v in users.values():
        if v.get('id') == user.get('id'):
            user_dict = v
            break
    if not user_dict:
        return jsonify({'success': False, 'error': '用户不存在'}), 404

    hist = _ensure_history_list(user_dict)
    before = len(hist)
    user_dict['buddy_conversations_history'] = [c for c in hist if c.get('id') != conv_id]
    if len(user_dict['buddy_conversations_history']) == before:
        return jsonify({'success': False, 'error': '对话不存在'}), 404
    _save_users(users)
    return jsonify({'success': True, 'message': '已删除'})
