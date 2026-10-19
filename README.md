# StudyPal 学习搭子

> 陪小学到初中的孩子，把学习变成一件不那么难的事。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)

---

StudyPal 是一款面向**小学到初中**学生的 AI 学习搭子。它提供 6 种性格可选的搭子、番茄钟、学习记录、心情日记、任务管理与成就系统，让日常学习有个伴。

## 目录

- [快速开始](#快速开始)
- [功能](#功能)
- [架构](#架构)
- [项目结构](#项目结构)
- [API 参考](#api-参考)
- [配置](#配置)
- [开发](#开发)

## 快速开始

### 1. 安装依赖

```bash
git clone https://github.com/linzizhen/StudyPal.git
cd StudyPal
pip install -r requirements.txt
```

### 2. 配置 AI 模型

推荐使用云端免费模型，无需本地部署，响应快。

```bash
cp .env.example .env
```

编辑 `.env`，填入 API Key（任选其一）：

| 提供商 | 获取地址 | 免费额度 |
|--------|----------|----------|
| **Groq**（推荐） | https://console.groq.com/keys | 充足 |
| DeepSeek | https://platform.deepseek.com/api_keys | 丰富 |
| 智谱 AI（国内推荐） | https://open.bigmodel.cn/usercenter/apikeys | 有免费模型 |
| OpenRouter | https://openrouter.ai/keys | 有限 |

```bash
AI_API_KEY=你的API密钥
DEFAULT_MODEL_KEY=groq_llama
```

也可以使用本地 Ollama 模型：

```bash
ollama pull qwen2.5:7b
```

### 3. 启动

```bash
python app.py
```

浏览器访问 http://localhost:5000

> 本项目在 Windows 下也提供 `run.bat`，它会先清理占用 5000 端口的旧进程再启动。注意该脚本内的路径需与你的实际克隆位置一致。

## 功能

### 搭子系统

| 功能 | 说明 |
|------|------|
| 6 种性格 | 小豆（温柔）、阿燃（热血）、小老师（耐心）、小夜（安静）、戏精（幽默）、阿正（理性） |
| 人设提示词 | 每个角色有独立的性格、语气、常用词与专属风格规则，AI 按人设作答 |
| 游戏化讲解 | 每个角色有自己的游戏化舞台：知识花园 / 竞技场 / 实验室 / 星图 / 喜剧厂 / 数据驾驶舱 |
| 三层记忆 | 用户画像、场景记忆、对话摘要 |
| 主动关心 | 早安问候、学习提醒、情绪关怀、成就庆祝（带冷却机制） |

### 学习功能

| 功能 | 说明 |
|------|------|
| 番茄钟 | 专注计时，支持多科目 |
| 学习记录 | 连续打卡天数、日/周统计、学习曲线 |
| 任务管理 | 优先级、截止时间、完成情况 |
| 学习计划 | AI 生成或手动制定阶段性计划 |
| 我的挑战 | 小学/初中两学段差异化挑战体系，含学科、里程碑与时间线 |
| 心情日记 | 10 档情绪量表 + 心情记录 |
| 我的成长 | 连续打卡天数与本周小星星（每学 1 小时点亮一颗） |

### AI 模型

| 功能 | 说明 |
|------|------|
| 多模型支持 | 13 种预设模型（Groq / DeepSeek / 智谱 / OpenRouter / Ollama） |
| 自定义模型 | 支持任意 OpenAI 兼容 API |
| 模型测试 | 内置连接测试 |

### 成就系统

| 功能 | 说明 |
|------|------|
| 成就徽章 | 53 个成就（番茄钟、连续学习、任务完成、测验等） |
| 积分等级 | 学习小白 → 学习传奇（7 个等级） |
| 成长时间线 | 记录学习路上的里程碑事件 |

## 架构

### 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Flask 3 + Blueprint 架构 |
| 前端 | HTML5 + CSS3 + 原生 JavaScript（单页应用） |
| AI | OpenAI 兼容 API（Groq / DeepSeek / 智谱 / OpenRouter）+ Ollama |
| 数据 | JSON 文件本地存储（带文件锁的原子读写） |
| 认证 | 自制 Token（HMAC-SHA256 签名）+ PBKDF2 密码哈希 |

### 请求链路

```
浏览器
  └─ templates/dashboard.html        （唯一页面入口，SPA）
       ├─ static/css/dashboard.css
       └─ static/js/dashboard.js
            └─ /api/*  →  routes/*.py  →  src/**  →  data/*.json
```

### 搭子系统

```
routes/buddy.py（API 层）
      ↓
src/core/buddy.py  Buddy 类（门面，编排各子模块）
      ↓ 组合
┌──────────────┬──────────────┬──────────────┬──────────────┐
BuddyProfile   BuddyMemory    CaringEngine   StudyTracker
（档案）        （三层记忆）    （主动关心）    （学习感知）
      ↓
src/buddy/buddy_roles.py   （角色定义 + 风格规则）
src/ai/prompt_templates.py （人设提示词组装）
src/ai/ai_helper.py        （多模型调用）
```

## 项目结构

```
StudyPal/
├── app.py                      # Flask 应用入口
├── config.py                   # 全局配置（模型、情绪、计时器）
├── requirements.txt            # Python 依赖
├── run.bat                     # Windows 启动脚本
├── Dockerfile                  # 容器构建
├── docker-compose.yml          # 容器编排
│
├── routes/                     # API 路由（Blueprint）
│   ├── buddy.py                # 搭子对话、角色、记忆、历史
│   ├── diary.py                # 日记与情绪
│   ├── study.py                # 学习计时与统计
│   ├── tasks.py                # 任务管理
│   ├── plans.py                # 学习计划
│   ├── achievements.py         # 成就
│   ├── challenges.py           # 我的挑战（小学/初中学段）
│   ├── timeline.py             # 成长时间线
│   ├── insights.py             # 周记、月报、洞察摘要
│   ├── recommend.py            # 每日推荐
│   ├── ai_model.py             # AI 模型配置
│   ├── user.py                 # 设置、座右铭、AI 历史
│   ├── home.py                 # 首页聚合数据
│   ├── utils.py                # 路由公共工具
│   └── __init__.py             # 蓝图注册
│
├── src/
│   ├── ai/
│   │   ├── ai_helper.py        # AI 调用核心（多模型、三级回退）
│   │   └── prompt_templates.py # 提示词模板与人设组装
│   ├── auth/
│   │   └── auth.py             # 认证（Token 签名、密码哈希）
│   ├── routes/
│   │   └── auth_routes.py      # 认证与用户接口
│   ├── buddy/
│   │   ├── buddy_profile.py    # 用户档案
│   │   ├── buddy_memory.py     # 三层记忆系统
│   │   ├── buddy_roles.py      # 6 种搭子角色 + 风格规则
│   │   └── caring_engine.py    # 主动关心引擎
│   ├── core/
│   │   ├── buddy.py            # 搭子系统门面
│   │   └── timer.py            # 计时器与监督器
│   ├── diary/
│   │   └── diary.py            # 日记与情绪量表
│   ├── modules/
│   │   ├── achievements.py     # 成就系统
│   │   ├── task_manager.py     # 任务管理
│   │   ├── plan_generator.py   # 学习计划生成
│   │   ├── challenge_manager.py# 我的挑战（学段体系）
│   │   ├── timeline.py         # 成长时间线
│   │   ├── daily_recommender.py# 每日推荐
│   │   ├── ai_memory.py        # AI 对话历史
│   │   └── data_manager.py     # 用户设置
│   ├── study/
│   │   └── study_tracker.py    # 学习追踪
│   └── utils/
│       └── file_lock.py        # JSON 原子读写
│
├── static/
│   ├── css/
│   │   ├── dashboard.css       # 主界面样式
│   │   └── challenge.css       # 挑战模块样式
│   └── js/
│       ├── dashboard.js        # 主界面逻辑
│       └── pages/              # 分页逻辑
│
├── templates/
│   ├── dashboard.html          # 单页应用主页面
│   ├── auth/                   # 登录、注册
│   └── admin/                  # 管理后台
│
└── data/                       # JSON 数据存储
    ├── buddy_memory.json       # 搭子记忆
    ├── diary.json              # 日记与情绪
    ├── study_tracker.json      # 学习记录
    ├── challenges.json         # 我的挑战
    ├── study_plans.json        # 学习计划
    ├── achievements.json       # 成就
    └── timeline.json           # 成长时间线
```

## API 参考

后端共注册 **110 个 `/api/*` 端点**。下表列出主要分组，完整清单可用 `flask routes` 查看。

### 搭子 API

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/buddy/status` | 搭子完整状态 |
| POST | `/api/buddy/chat` | 搭子对话（含记忆与情绪） |
| POST | `/api/buddy/quick-chat` | 轻量对话（按角色人设作答） |
| POST | `/api/buddy/explain` | 游戏化讲解（知识点 / 计划 / 方法） |
| GET | `/api/buddy/roles` | 6 个可选搭子 |
| POST | `/api/buddy/role/switch` | 切换搭子 |
| GET/PUT | `/api/buddy/profile` | 获取/更新档案 |
| GET/POST | `/api/buddy/memory` | 搭子记忆 |
| GET | `/api/buddy/caring` | 主动关心事件 |
| GET/POST | `/api/buddy/conversations` | 历史对话列表 |

### 学习 API

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/api/study/start` | 开始学习 |
| POST | `/api/study/stop` | 结束学习 |
| GET | `/api/study/stats` | 学习统计（连续打卡、本周时长） |

### 日记与心情 API

| 方法 | 端点 | 说明 |
|------|------|------|
| GET/POST | `/api/diary` | 日记列表 / 写入日记 |
| GET | `/api/diary/today` | 今日日记 |
| GET | `/api/diary/emotions` | 情绪曲线 |
| GET | `/api/diary/review` | 日记回顾 |

### 我的挑战 API（小学 / 初中）

| 方法 | 端点 | 说明 |
|------|------|------|
| GET/POST | `/api/challenges` | 挑战数据 |
| POST | `/api/challenges/grade` | 设置学段 |
| GET | `/api/challenges/presets/grade/<grade_mode>` | 学段学科模板 |
| POST | `/api/challenges/challenge` | 新建挑战 |
| POST | `/api/challenges/challenge/<id>/subject` | 添加学科 |
| POST | `/api/challenges/challenge/<id>/milestone` | 添加里程碑 |

### 任务与计划 API

| 方法 | 端点 | 说明 |
|------|------|------|
| GET/POST | `/api/tasks` | 任务列表 / 新建 |
| PUT/DELETE | `/api/tasks/<task_id>` | 更新 / 删除 |
| GET/POST | `/api/plans` | 学习计划 |
| GET | `/api/plans/expiring` | 即将到期的计划 |

### 成长与洞察 API

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/achievements` | 成就列表与进度 |
| GET/POST | `/api/timeline` | 成长时间线 |
| GET | `/api/insights/weekly-insight` | 每周周记 |
| GET | `/api/insights/monthly-report` | 月度报告 |
| GET | `/api/insights/insight-summary` | 洞察摘要 |
| GET | `/api/recommend/daily` | 每日推荐 |

### AI 模型 API

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/ai-model/presets` | 预设模型列表 |
| GET | `/api/ai-model/current` | 当前模型 |
| POST | `/api/ai-model/preset` | 切换预设 |
| POST | `/api/ai-model/custom` | 保存自定义模型 |
| POST | `/api/ai-model/test` | 测试连接 |

### 认证 API

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/api/auth/register` | 注册 |
| POST | `/api/auth/login` | 登录 |
| GET | `/api/auth/me` | 当前用户 |
| GET | `/api/auth/subscription` | 订阅与额度 |

## 配置

### 环境变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `AI_API_KEY` | 是 | AI 服务 API Key |
| `DEFAULT_MODEL_KEY` | 否 | 默认模型 key，默认 `groq_llama` |
| `SECRET_KEY` | 否 | Token 签名密钥；不填则自动生成并落盘 |
| `FLASK_DEBUG` | 否 | 设为 `true` 开启调试 |
| `PORT` | 否 | 服务端口，默认 `5000` |
| `CORS_ORIGINS` | 否 | CORS 允许来源，默认 `*` |

### 预设模型

`config.py` 的 `MODELS_CONFIG` 内置 13 个预设模型：

| Key | 名称 | 提供商 |
|-----|------|--------|
| `groq_llama` | Llama 3.3 70B | Groq |
| `groq_mixtral` | Mixtral 8x7B | Groq |
| `deepseek_chat` | DeepSeek Chat | DeepSeek |
| `deepseek_r1` | DeepSeek R1 | DeepSeek |
| `openrouter_deepseek` | DeepSeek R1 | OpenRouter |
| `zhipu_glm4_flash` | GLM-4-Flash | 智谱 |
| `zhipu_glm_z1_flash` | GLM-Z1-Flash | 智谱 |
| `zhipu_glm4` | GLM-4 | 智谱 |
| `zhipu_glm4v` | GLM-4V（多模态） | 智谱 |
| `qwen2.5_7b` | Qwen2.5 7B | Ollama |
| `qwen3.5_9b` | Qwen3.5 9B | Ollama |
| `llama3_8b` | Llama3 8B | Ollama |
| `mistral_7b` | Mistral 7B | Ollama |

### 情绪量表

心情日记使用 10 档量表（`src/diary/diary.py` 的 `DiaryEntry.EMOTIONS`）：

| 等级 | 标签 | 等级 | 标签 |
|------|------|------|------|
| 1 | 难过 | 6 | 开心 |
| 2 | 低落 | 7 | 兴奋 |
| 3 | 平静 | 8 | 感恩 |
| 4 | 思考 | 9 | 希望 |
| 5 | 愉快 | 10 | 疲惫 |

### 学段与学科（我的挑战）

`src/modules/challenge_manager.py` 的 `DEFAULT_SUBJECTS`：

| 学段 | 默认学科 | 呈现方式 |
|------|----------|----------|
| 小学（`primary`） | 语文城堡、数学森林、英语海洋、科学秘境 | 星级 |
| 初中（`middle`） | 语文、数学、英语、物理、化学 | 星级 |

## 开发

### 运行测试

项目自带回归测试套件（pytest）：

```bash
pip install pytest
python -m pytest tests/ -v
```

测试覆盖端点健康度、认证安全、日记契约、角色人设链路、产品方向与前端成长页。测试带有数据隔离，运行后会自动还原 `data/`，不会污染真实数据。

### 代码风格

- 后端遵循 PEP 8
- 前端沿用现有代码风格
- 提交格式见 [GITFLOW.md](GITFLOW.md)

### 提交前自检

1. 确保 `python -m pytest tests/` 全部通过
2. 手动验证改动涉及的功能
3. 更新相关文档

## License

MIT License
