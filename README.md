# StudyPal

面向 **小学到初中** 学生的 AI 学习搭子 Web 应用。后端 Flask + 原生前端单页应用，数据存 JSON 文件，无需数据库与前端构建。

- **6 种性格搭子**：小豆（温柔）、阿燃（热血）、小老师（耐心）、小夜（安静）、戏精（幽默）、阿正（理性），各自带人设提示词与游戏化讲解舞台。
- **学习工具**：番茄钟、待办任务、10 档心情日记、学习统计、成长打卡、小学/初中两级挑战、53 个成就徽章。
- **搭子的记忆本**：三层记忆 + 从对话自动抽取值得长期记住的信息。
- **多模型 AI**：13 种预设模型（Groq / DeepSeek / 智谱 / OpenRouter / Ollama），也可接任意 OpenAI 兼容接口。

## 技术栈

| 层 | 选型 |
|----|------|
| 后端 | Flask 3 + Blueprint |
| 前端 | HTML/CSS/原生 JavaScript（SPA，无构建步骤） |
| 数据 | JSON 文件 + 文件锁原子读写 |
| 认证 | 自制 HMAC-SHA256 Token + PBKDF2 密码哈希（非 JWT） |
| AI | OpenAI 兼容 API + Ollama |
| 部署 | Docker + Gunicorn |

## 快速开始

```bash
git clone https://github.com/linzizhen/StudyPal.git
cd StudyPal
python -m venv .venv
.venv\Scripts\activate           # Windows
source .venv/bin/activate        # macOS / Linux
pip install -r requirements.txt

cp .env.example .env             # Windows: copy .env.example .env
# 编辑 .env，至少填写 AI_API_KEY
python app.py
```

访问 http://localhost:5000 。Windows 也可直接运行 `run.bat`（会先释放 5000 端口并优先使用 `.venv`）。

## 配置

常用环境变量（完整见 `.env.example`）：

| 变量 | 说明 |
|------|------|
| `AI_API_KEY` | AI 服务密钥（必填） |
| `DEFAULT_MODEL_KEY` | 默认模型 key，默认 `groq_llama` |
| `SECRET_KEY` | Token 签名密钥；多 worker 部署必须显式设置 |
| `HOST` / `PORT` | 监听地址与端口，默认 `0.0.0.0:5000` |
| `FLASK_DEBUG` | 是否开启调试 |
| `CORS_ORIGINS` | CORS 允许来源，默认 `*` |
| `AI_TIMEOUT` / `AI_MAX_RETRIES` | AI 超时（秒）与重试次数 |
| `OLLAMA_BASE_URL` | 本地 Ollama 地址 |

`config.py` 的 `MODELS_CONFIG` 内置 13 种预设模型：

| Key | 提供商 |
|-----|--------|
| `groq_llama` / `groq_mixtral` | Groq |
| `deepseek_chat` / `deepseek_r1` | DeepSeek |
| `openrouter_deepseek` | OpenRouter |
| `zhipu_glm4_flash` / `zhipu_glm_z1_flash` / `zhipu_glm4` / `zhipu_glm4v` | 智谱 |
| `qwen3.5_9b` / `qwen2.5_7b` / `llama3_8b` / `mistral_7b` | Ollama |

心情日记使用 **10 档** 情绪量表（`src/diary/diary.py` 的 `DiaryEntry.EMOTIONS`）。我的挑战只支持 **小学（`primary`）与初中（`middle`）** 两学段，**不含高中**。

## 目录结构

```text
StudyPal/
├── app.py                      # 应用入口、蓝图注册、错误处理
├── config.py                   # 全局配置（模型、情绪、计时）
├── requirements.txt
├── run.bat / Dockerfile / docker-compose.yml
├── routes/                     # HTTP 层（Blueprint）
│   ├── buddy.py                # 搭子对话、角色、记忆、关心
│   ├── diary.py                # 日记与情绪
│   ├── study.py                # 学习计时与统计
│   ├── tasks.py                # 任务管理
│   ├── plans.py                # 学习计划
│   ├── achievements.py
│   ├── challenges.py           # 我的挑战（小学/初中）
│   ├── timeline.py             # 成长时间线
│   ├── insights.py             # 周记 / 月报 / 洞察
│   └── recommend.py            # 每日推荐  ← 对应 src/modules/daily_recommender.py
├── src/
│   ├── ai/                     # ai_helper.py、prompt_templates.py
│   ├── auth/auth.py            # Token 签名、密码哈希
│   ├── routes/auth_routes.py   # 认证与用户接口
│   ├── buddy/                  # buddy_profile / buddy_memory / memory_extractor / buddy_roles / caring_engine
│   ├── core/                   # buddy.py（门面）、timer.py
│   ├── diary/diary.py
│   ├── study/study_tracker.py
│   ├── modules/                # achievements.py、task_manager.py、plan_generator.py、challenge_manager.py、timeline.py
│   └── utils/file_lock.py      # JSON 原子读写
├── static/
│   ├── css/                    # dashboard.css、challenge.css、redesign.css、pages.css、polish.css
│   ├── js/                     # api.js、dashboard.js、ui-enhance.js、interactions.js
│   └── js/pages/challenges.js
├── templates/
│   ├── dashboard.html          # SPA 主页面
│   ├── auth/                   # 登录、注册
│   └── admin/                  # 管理后台
├── tests/                      # pytest 回归测试
└── data/                       # 运行时 JSON（gitignore）
```

## API 概览

后端共 **112 个 `/api/*` 端点**，按模块分组：

| 分组 | 代表端点 |
|------|----------|
| 认证 `auth_routes.py` | `POST /api/auth/register`、`POST /api/auth/login`、`POST /api/auth/password`、`GET /api/auth/me` |
| 搭子 `buddy.py` | `POST /api/buddy/chat`、`POST /api/buddy/quick-chat`、`GET /api/buddy/roles`、`GET/POST /api/buddy/memory` |
| 学习 / 日记 / 任务 | `GET /api/study/stats`、`GET/POST /api/diary`、`GET/POST /api/tasks`、`GET /api/tasks/stats` |
| 计划 / 挑战 | `GET/POST /api/plans`、`GET/POST /api/challenges`、`POST /api/challenges/grade` |
| 成长 / 洞察 | `GET /api/achievements`、`GET/POST /api/timeline`、`GET /api/insights/insight-summary`、`GET /api/recommend/daily` |
| 模型 / 用户 | `GET /api/ai-model/presets`、`POST /api/ai-model/test`、`GET /api/home`、`GET /api/data/export` |

完整清单可用 `flask routes` 查看。

## 开发与测试

```bash
pip install pytest
python -m pytest tests/ -v
```

测试覆盖端点健康、认证安全、Token 签名、日记契约、角色人设、产品方向、前端成长、记忆接线、主动关心、持久化、修改密码、界面可访问性与文档一致性；测试自动隔离并还原 `data/`。

提交规范见 [GITFLOW.md](GITFLOW.md)，贡献说明见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 部署

```bash
cp .env.production .env          # 至少填写 SECRET_KEY 与 AI_API_KEY
docker compose up -d
```

`docker-compose.yml` 只有一个 web 服务，通过 `./data` 卷持久化 JSON。多 worker 必须显式设置 `SECRET_KEY`。非容器部署推荐 Gunicorn：

```bash
gunicorn --bind 0.0.0.0:5000 --workers 4 --threads 2 --timeout 120 app:app
```

## 文档

- [PRODUCT.md](PRODUCT.md)：产品说明（以当前代码为准）
- [DESIGN_DOC.md](DESIGN_DOC.md)：历史设计稿（顶部标注与实现差异）
- [CHANGELOG.md](CHANGELOG.md)：变更记录

> 仓库当前未附带 LICENSE 文件；如需开源发布请自行补充。
