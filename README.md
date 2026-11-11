# StudyPal 学习搭子

> 陪小学到初中的孩子，把学习变成一件不那么难的事。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)

---

StudyPal 是一款面向 **小学到初中** 学生的 AI 学习搭子。它提供 6 种性格可选的搭子、番茄钟、学习记录、心情日记、任务与计划、成长挑战、成就系统，还有一本「搭子的记忆本」——让搭子真正记住孩子说过的话。

本文档以当前代码实现为准。历史设计与实现差异（如 v3.0 曾计划迁移 SQLAlchemy）见 [PRODUCT.md](PRODUCT.md) 与 [DESIGN_DOC.md](DESIGN_DOC.md) 顶部说明。

## 目录

- [快速开始](#快速开始)
- [功能](#功能)
- [架构](#架构)
- [项目结构](#项目结构)
- [API 参考](#api-参考)
- [配置](#配置)
- [开发](#开发)
- [部署](#部署)
- [License](#license)

## 快速开始

### 1. 安装依赖

```bash
git clone https://github.com/linzizhen/StudyPal.git
cd StudyPal
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 配置 AI 模型

推荐使用云端免费模型，无需本地部署，响应快。

```bash
# Windows
copy .env.example .env
# macOS / Linux
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

> Windows 下也可双击 `run.bat`。脚本会先清理占用 5000 端口的旧进程，再优先使用项目内的 `.venv` 启动，无需手动改路径。

## 功能

应用采用单页应用（SPA）结构，左侧导航对应 10 个页面：仪表盘、番茄专注、待办任务、学习日记、学习搭子、数据统计、我的成长、我的挑战、搭子的记忆本、设置。

### 搭子系统

| 功能 | 说明 |
|------|------|
| 6 种性格 | 小豆（温柔）、阿燃（热血）、小老师（耐心）、小夜（安静）、戏精（幽默）、阿正（理性） |
| 人设提示词 | 每个角色有独立的性格、语气、常用词与专属风格规则，AI 按人设作答 |
| 游戏化讲解 | 每个角色有自己的游戏化舞台：知识花园 / 竞技场 / 实验室 / 星图 / 喜剧厂 / 数据驾驶舱 |
| 主动关心 | 早安问候、学习提醒、情绪关怀、成就庆祝，触发冷却状态已持久化（`data/caring_state.json`） |

### 搭子的记忆本

| 功能 | 说明 |
|------|------|
| 三层记忆 | 用户画像（长期信息）、场景记忆（具体事件）、对话摘要（关键信息） |
| 自动抽取 | `src/buddy/memory_extractor.py` 从对话中按规则挑出值得长期记住的信息，寒暄等噪音不写入 |
| 记忆本页面 | 查看记忆概览、近期场景，并按主题搜索（`/api/buddy/memory`、`/api/buddy/memory/search`） |

### 学习与成长

| 功能 | 说明 |
|------|------|
| 番茄钟 | 专注计时，支持多科目 |
| 学习记录 | 连续打卡天数、日 / 周统计 |
| 我的成长 | 连续打卡天数与本周小星星（每学满 1 小时点亮一颗，最多 7 颗） |
| 心情日记 | 10 档情绪量表 + 心情记录与回顾 |
| 数据统计 | 学习时长、任务完成、情绪趋势等汇总视图 |

### 任务与计划

| 功能 | 说明 |
|------|------|
| 任务管理 | 优先级、截止时间、完成与删除，数据落库到服务端 |
| 学习计划 | AI 生成或手动制定阶段性计划，支持到期提醒 |
| 每日推荐 | 依据学习记录给出每日任务推荐 |

### 我的挑战（小学 / 初中）

| 功能 | 说明 |
|------|------|
| 两学段体系 | 小学（`primary`）与初中（`middle`）差异化挑战，已接入主界面 |
| 学科与里程碑 | 按学段提供学科模板、里程碑与时间线，支持记录成绩与切换完成状态 |
| 全屏模块 | 独立的 `challenge.css` 与 `pages/challenges.js`，在主界面切页时挂载 |

### 成就系统

| 功能 | 说明 |
|------|------|
| 成就徽章 | 53 个成就（番茄钟、连续学习、任务完成、测验等） |
| 积分等级 | 学习小白 → 学习传奇（7 个等级） |
| 成长时间线 | 记录学习路上的里程碑事件 |

### AI 模型

| 功能 | 说明 |
|------|------|
| 多模型支持 | 13 种预设模型（Groq / DeepSeek / 智谱 / OpenRouter / Ollama） |
| 自定义模型 | 支持任意 OpenAI 兼容 API，可增删自定义配置 |
| 模型测试 | 内置连接测试，未登录也可验证配置 |

### 账户与设置

| 功能 | 说明 |
|------|------|
| 注册登录 | 邮箱 + 密码，PBKDF2 加盐哈希，登录后签发自制 Token |
| 修改密码 | 在「设置」页凭原密码修改（`POST /api/auth/password`） |
| 个人偏好 | 昵称、头像、主题、学段、学习目标、每日目标时长等 |
| 数据导出 | `GET /api/data/export` 导出个人数据 |

## 架构

### 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Flask 3 + Blueprint 架构 |
| 前端 | HTML5 + CSS3 + 原生 JavaScript（单页应用，无构建步骤） |
| AI | OpenAI 兼容 API（Groq / DeepSeek / 智谱 / OpenRouter）+ Ollama |
| 数据 | JSON 文件本地存储（带文件锁的原子读写） |
| 认证 | 自制 Token（HMAC-SHA256 签名）+ PBKDF2 密码哈希（非 JWT） |
| 部署 | Docker + Gunicorn |

### 请求链路

```text
浏览器
  └─ templates/dashboard.html        （唯一页面入口，SPA）
       ├─ static/css/dashboard.css
       ├─ static/js/dashboard.js
       └─ static/js/api.js + static/js/pages/challenges.js（我的挑战模块）
            └─ /api/*  →  routes/*.py  →  src/**  →  data/*.json
```

### 搭子系统

```text
routes/buddy.py（API 层）
      ↓
src/core/buddy.py  Buddy 类（门面，编排各子模块）
      ↓ 组合
┌──────────────┬──────────────┬──────────────┬──────────────┐
BuddyProfile   BuddyMemory    CaringEngine   StudyTracker
（档案）        （三层记忆）    （主动关心）    （学习感知）
      ↓
src/buddy/buddy_roles.py      （角色定义 + 风格规则）
src/buddy/memory_extractor.py（记忆抽取，从对话写入记忆）
src/ai/prompt_templates.py    （人设提示词组装）
src/ai/ai_helper.py           （多模型调用）
```

## 项目结构

```text
StudyPal/
├── app.py                      # Flask 应用入口、蓝图注册、错误处理
├── config.py                   # 全局配置（模型、情绪、计时器）
├── requirements.txt            # Python 依赖
├── run.bat                     # Windows 启动脚本
├── Dockerfile                  # 容器构建（Gunicorn 启动）
├── docker-compose.yml          # 容器编排（单 web 服务 + 数据卷）
├── .env.example                # 环境变量示例
├── CHANGELOG.md                # 变更记录
├── PRODUCT.md                  # 产品文档（以代码为准）
├── DESIGN_DOC.md               # 历史设计稿（顶部标注与实现差异）
├── GITFLOW.md                  # 分支与提交规范
├── CONTRIBUTING.md             # 贡献说明
│
├── routes/                     # API 路由（Blueprint）
│   ├── buddy.py                # 搭子对话、角色、记忆、关心、历史
│   ├── diary.py                # 日记与情绪
│   ├── study.py                # 学习计时与统计
│   ├── tasks.py                # 任务管理
│   ├── plans.py                # 学习计划
│   ├── achievements.py         # 成就
│   ├── challenges.py           # 我的挑战（小学 / 初中学段）
│   ├── timeline.py             # 成长时间线
│   ├── insights.py             # 周记、月报、洞察摘要
│   ├── recommend.py            # 每日推荐
│   ├── ai_model.py             # AI 模型配置
│   ├── user.py                 # 设置、座右铭、AI 历史、通知、导出
│   ├── home.py                 # 首页聚合数据
│   ├── utils.py                # 路由公共工具
│   └── __init__.py             # 蓝图注册
│
├── src/
│   ├── ai/
│   │   ├── ai_helper.py        # AI 调用核心（多模型、三级回退）
│   │   └── prompt_templates.py # 提示词模板与人设组装
│   ├── auth/
│   │   └── auth.py             # 认证（Token 签名、密码哈希、权限装饰器）
│   ├── routes/
│   │   └── auth_routes.py      # 认证与用户接口
│   ├── buddy/
│   │   ├── buddy_profile.py    # 用户档案
│   │   ├── buddy_memory.py     # 三层记忆系统
│   │   ├── memory_extractor.py # 对话记忆抽取
│   │   ├── buddy_roles.py      # 6 种搭子角色 + 风格规则
│   │   └── caring_engine.py    # 主动关心引擎（冷却持久化）
│   ├── core/
│   │   ├── buddy.py            # 搭子系统门面
│   │   └── timer.py            # 计时器与监督器
│   ├── diary/
│   │   └── diary.py            # 日记与情绪量表
│   ├── study/
│   │   └── study_tracker.py    # 学习追踪
│   ├── modules/
│   │   ├── achievements.py     # 成就系统
│   │   ├── task_manager.py     # 任务管理
│   │   ├── plan_generator.py   # 学习计划生成
│   │   ├── challenge_manager.py# 我的挑战（学段体系）
│   │   ├── timeline.py         # 成长时间线
│   │   ├── daily_recommender.py# 每日推荐
│   │   ├── ai_memory.py        # AI 对话历史
│   │   └── data_manager.py     # 用户设置
│   └── utils/
│       └── file_lock.py        # JSON 原子读写
│
├── static/
│   ├── avatars/
│   │   ├── preset_xj1.svg      # 戏精头像
│   │   └── preset_azheng1.svg  # 阿正头像
│   ├── css/
│   │   ├── dashboard.css       # 主界面样式
│   │   └── challenge.css       # 挑战模块样式
│   └── js/
│       ├── api.js              # API 请求封装（挑战模块依赖）
│       ├── dashboard.js        # 主界面逻辑
│       └── pages/
│           └── challenges.js   # 我的挑战页面逻辑
│
├── templates/
│   ├── dashboard.html          # 单页应用主页面
│   ├── auth/                   # 登录、注册
│   └── admin/                  # 管理后台
│
├── tests/                      # pytest 回归测试（数据隔离）
├── tools/
│   └── dev_preview_server.py   # 本地预览辅助服务
│
└── data/                       # JSON 数据存储（运行时生成，已 gitignore）
    ├── buddy_memory.json       # 搭子记忆
    ├── diary.json              # 日记与情绪
    ├── study_tracker.json      # 学习记录
    ├── study_plans.json        # 学习计划
    ├── challenges.json         # 我的挑战
    ├── achievements.json       # 成就
    ├── timeline.json           # 成长时间线
    ├── tasks.json              # 任务
    ├── ai_history.json         # AI 对话历史
    ├── caring_state.json       # 主动关心冷却状态
    └── model_config.json       # 模型配置
```

## API 参考

后端共注册 **112 个 `/api/*` 端点**。下表列出主要分组，完整清单可用 `flask routes` 查看。

### 认证 API（`src/routes/auth_routes.py`）

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/api/auth/register` | 注册 |
| POST | `/api/auth/login` | 登录 |
| GET | `/api/auth/me` | 当前用户 |
| PUT/PATCH | `/api/auth/me` | 更新当前用户资料 |
| POST | `/api/auth/password` | 修改密码（原密码 + 新密码） |
| GET | `/api/auth/subscription` | 订阅与额度 |
| GET | `/api/auth/ai/stats` | AI 调用统计 |
| GET | `/api/auth/admin/users` | 管理员：用户列表 |
| GET | `/api/auth/admin/stats` | 管理员：系统统计 |

### 搭子 API（`routes/buddy.py`）

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/buddy/status` | 搭子完整状态 |
| POST | `/api/buddy/chat` | 搭子对话（含记忆与情绪） |
| POST | `/api/buddy/quick-chat` | 轻量对话（按角色人设作答，并写入记忆） |
| POST | `/api/buddy/explain` | 游戏化讲解（知识点 / 计划 / 方法） |
| GET | `/api/buddy/roles` | 6 个可选搭子 |
| GET | `/api/buddy/role` | 当前角色信息 |
| POST | `/api/buddy/role/switch` | 切换搭子 |
| GET | `/api/buddy/role/level` | 搭子等级信息 |
| GET/PUT | `/api/buddy/profile` | 获取 / 更新档案 |
| GET/POST | `/api/buddy/memory` | 记忆概览与新增场景记忆 |
| GET | `/api/buddy/memory/search` | 按主题 / 语义搜索记忆 |
| GET | `/api/buddy/caring` | 主动关心事件 |
| POST | `/api/buddy/achievement` | 上报成就 |
| GET/POST | `/api/buddy/conversations` | 历史对话列表 / 保存 |
| GET/DELETE | `/api/buddy/conversation/<conv_id>` | 单条历史对话 |

### 学习、日记与任务 API

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/api/study/start` | 开始学习 |
| POST | `/api/study/stop` | 结束学习 |
| GET | `/api/study/stats` | 学习统计（连续打卡、本周时长） |
| GET/POST | `/api/diary` | 日记列表 / 写入日记 |
| GET | `/api/diary/today` | 今日日记 |
| GET | `/api/diary/emotions` | 情绪曲线 |
| GET | `/api/diary/review` | 日记回顾 |
| DELETE | `/api/diary/<entry_id>` | 删除日记 |
| GET/POST | `/api/tasks` | 任务列表 / 新建 |
| PUT/DELETE | `/api/tasks/<task_id>` | 更新 / 删除任务 |
| POST | `/api/tasks/<task_id>/complete` | 完成任务 |
| GET | `/api/tasks/stats` | 任务统计 |

### 计划与我的挑战 API

| 方法 | 端点 | 说明 |
|------|------|------|
| GET/POST | `/api/plans` | 学习计划 |
| GET/PUT/DELETE | `/api/plans/<int:plan_id>` | 单个计划 |
| GET | `/api/plans/expiring` | 即将到期的计划 |
| GET/POST | `/api/challenges` | 挑战数据 |
| POST | `/api/challenges/grade` | 设置学段（`primary` / `middle`） |
| GET | `/api/challenges/presets/grade/<grade_mode>` | 学段学科模板 |
| GET | `/api/challenges/presets/icons` | 图标集合 |
| POST | `/api/challenges/challenge` | 新建挑战 |
| PUT/DELETE | `/api/challenges/challenge/<challenge_id>` | 更新 / 删除挑战 |
| POST | `/api/challenges/challenge/<challenge_id>/activate` | 激活挑战 |
| POST/PUT/DELETE | `/api/challenges/challenge/<challenge_id>/subject/...` | 学科的增改删与记分 |
| POST/DELETE | `/api/challenges/challenge/<challenge_id>/milestone/...` | 里程碑增删与勾选 |
| POST/DELETE | `/api/challenges/challenge/<challenge_id>/timeline/...` | 时间线节点增删与勾选 |

### 成长与洞察 API

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/achievements` | 成就列表与进度 |
| POST | `/api/achievements/unlock` | 解锁成就 |
| GET/POST | `/api/timeline` | 成长时间线 |
| GET | `/api/timeline/stats` | 时间线统计 |
| POST | `/api/timeline/record/<event_type>` | 记录事件（学习 / 里程碑 / 成就 / 挫折 / 突破 / 情绪） |
| GET | `/api/insights/weekly-insight` | 每周周记 |
| GET | `/api/insights/monthly-report` | 月度报告 |
| GET | `/api/insights/insight-summary` | 洞察摘要 |
| GET | `/api/recommend/daily` | 每日推荐 |
| GET | `/api/recommend/tasks` | 每日任务推荐 |

### AI 模型与用户 API

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/ai-model/presets` | 预设模型列表 |
| GET | `/api/ai-model/current` | 当前模型 |
| POST | `/api/ai-model/preset` | 切换预设 |
| POST/DELETE | `/api/ai-model/custom` | 保存 / 删除自定义模型 |
| POST | `/api/ai-model/test` | 测试连接 |
| GET | `/api/home` | 首页聚合数据 |
| GET/POST | `/api/motto` | 座右铭 |
| GET/POST | `/api/favorite_quote` | 收藏句子 |
| GET/POST/DELETE | `/api/ai/history` | AI 对话历史 |
| GET | `/api/ai/models` | 可用 AI 模型 |
| GET | `/api/ai/stats` | AI 使用统计 |
| GET/POST | `/api/notification/settings` | 通知设置 |
| GET | `/api/data/export` | 导出个人数据 |

## 配置

### 环境变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `AI_API_KEY` | 是 | AI 服务 API Key |
| `DEFAULT_MODEL_KEY` | 否 | 默认模型 key，默认 `groq_llama` |
| `DEFAULT_MODEL` | 否 | 默认模型名，默认 `llama-3.3-70b-versatile` |
| `SECRET_KEY` | 否 | Token 签名密钥；不填则自动生成并落盘（多 worker 部署必须显式设置） |
| `FLASK_DEBUG` | 否 | 设为 `true` 开启调试 |
| `HOST` | 否 | 监听地址，默认 `0.0.0.0` |
| `PORT` | 否 | 服务端口，默认 `5000` |
| `CORS_ORIGINS` | 否 | CORS 允许来源，默认 `*` |
| `LOG_LEVEL` | 否 | 日志级别，默认 `INFO` |
| `AI_TIMEOUT` | 否 | AI 请求超时（秒），默认 `60` |
| `AI_MAX_RETRIES` | 否 | AI 请求最大重试次数，默认 `3` |
| `OLLAMA_BASE_URL` | 否 | Ollama 服务地址，默认 `http://localhost:11434` |

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
| `qwen3.5_9b` | Qwen3.5 9B | Ollama |
| `qwen2.5_7b` | Qwen2.5 7B | Ollama |
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

`src/modules/challenge_manager.py` 定义小学与初中两学段：

| 学段 | 值 | 默认学科 | 呈现方式 |
|------|-----|----------|----------|
| 小学 | `primary` | 语文城堡、数学森林、英语海洋、科学秘境 | 星级 |
| 初中 | `middle` | 语文、数学、英语、物理、化学 | 星级 |

> 说明：本产品定位为小学到初中，不含高中。`GRADE_MODES` 与 `DEFAULT_SUBJECTS` 均已移除 `high`。

## 开发

### 运行测试

项目自带回归测试套件（pytest）：

```bash
pip install pytest
python -m pytest tests/ -v
```

测试覆盖端点健康度、认证安全、Token 签名、日记契约、角色人设链路、产品方向、前端成长页、记忆接线、主动关心、持久化落库、修改密码、界面可访问性与文档一致性。测试带数据隔离，运行后会自动还原 `data/`，不会污染真实数据。

### 代码风格

- 后端遵循 PEP 8
- 前端沿用现有代码风格
- 提交格式见 [GITFLOW.md](GITFLOW.md)

### 提交前自检

1. 确保 `python -m pytest tests/` 全部通过
2. 手动验证改动涉及的功能
3. 更新相关文档（README / PRODUCT / CHANGELOG）

## 部署

### Docker 部署

```bash
cp .env.production .env
# 编辑 .env，至少填写 SECRET_KEY 与 AI_API_KEY
docker compose up -d
```

> `docker-compose.yml` 只定义单个 web 服务，通过 `./data` 卷持久化 JSON 数据。多 worker 部署必须显式设置 `SECRET_KEY`，否则 Token 会在重启后失效。

### 传统部署

生产环境建议用 Gunicorn 启动（与 Dockerfile 一致）：

```bash
gunicorn --bind 0.0.0.0:5000 --workers 4 --threads 2 --timeout 120 app:app
```

## License

MIT License
