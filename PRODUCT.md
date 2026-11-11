# StudyPal 产品文档

> 本文档以当前代码实现为准。历史版本（v3.0 曾计划迁移到 SQLAlchemy）的设计与实现差异见文末「版本历史」。

## 产品概述

StudyPal 是一款面向**小学到初中**学生的 AI 学习搭子应用。核心特点是有一个有性格、会记事、会主动关心的虚拟学习伙伴，陪孩子把日常学习坚持下去。

### 目标用户

- 小学阶段（1–6 年级）的学生
- 初中阶段（7–9 年级）的学生
- 希望孩子有学习陪伴、养成学习习惯的家长

### 核心功能

1. **AI 搭子系统** — 6 种性格可选的虚拟学习伙伴，各自有独立人设与游戏化讲解风格
2. **学习记录** — 番茄钟 + 连续打卡 + 周统计
3. **心情日记** — 10 档情绪量表，记录与回顾
4. **任务与计划** — 待办事项 + 学习计划
5. **我的挑战** — 小学/初中两学段差异化挑战体系
6. **成就与成长时间线** — 激励持续学习
7. **搭子的记忆本** — 三层记忆（用户画像 / 场景记忆 / 对话摘要）+ 对话自动抽取，让搭子记住孩子说过的事
8. **账户与设置** — 注册登录、修改密码、个人偏好与数据导出

---

## 技术架构

### 技术栈

下表为**当前实际使用**的技术：

| 层级 | 技术 |
|------|------|
| 后端 | Flask 3 + Blueprint |
| 数据存储 | **JSON 文件**（`data/*.json`，带文件锁的原子读写） |
| 前端 | 原生 JavaScript 单页应用（`templates/dashboard.html`） |
| 认证 | 自制 Token（HMAC-SHA256 签名，非 JWT）+ PBKDF2 密码哈希 |
| AI | OpenAI 兼容 API + Ollama |
| 部署 | Docker（Gunicorn 已写入 Dockerfile） |

> 说明：早期版本（v3.0）曾计划迁移到 SQLAlchemy ORM + PostgreSQL + JWT，该迁移**未完成并已回退**。相关代码已移除，`requirements.txt` 中的 SQLAlchemy 依赖保持注释状态。

### 目录结构

```
StudyPal/
├── app.py                 # 应用入口与蓝图注册
├── config.py              # 全局配置（模型、情绪、计时器）
├── requirements.txt       # 依赖
├── Dockerfile             # 容器构建
├── docker-compose.yml     # 容器编排
│
├── src/
│   ├── auth/              # 认证模块
│   │   └── auth.py        # Token 签名 + 密码哈希 + 权限装饰器
│   ├── routes/
│   │   └── auth_routes.py # 认证与用户接口
│   ├── buddy/             # 搭子系统
│   │   ├── buddy_roles.py     # 6 种角色定义 + 风格规则
│   │   ├── buddy_profile.py   # 档案管理
│   │   ├── buddy_memory.py    # 三层记忆
│   │   ├── memory_extractor.py # 对话记忆抽取
│   │   └── caring_engine.py   # 主动关心引擎
│   ├── core/
│   │   ├── buddy.py       # 搭子系统门面
│   │   └── timer.py       # 计时器与监督器
│   ├── ai/                # AI 接口
│   │   ├── ai_helper.py   # 多模型调用
│   │   └── prompt_templates.py # 人设提示词组装
│   ├── study/             # 学习追踪
│   ├── diary/             # 日记与情绪
│   ├── modules/           # 成就、任务、计划、挑战、时间线、推荐
│   └── utils/             # 文件锁等工具
│
├── routes/                # API 路由（Blueprint）
├── templates/             # HTML 模板
│   ├── dashboard.html     # 单页应用主页面
│   ├── auth/              # 登录、注册
│   └── admin/             # 管理后台
├── static/                # 静态资源
│   ├── css/
│   └── js/
└── data/                  # JSON 数据存储
```

---

## API 文档

后端共注册 112 个 `/api/*` 端点。以下列出主要接口。

### 认证接口

#### POST /api/auth/register — 用户注册

**请求体：**

```json
{
  "email": "user@example.com",
  "password": "password123",
  "nickname": "小同学"
}
```

**响应：**

```json
{
  "success": true,
  "token": "…",
  "user": {
    "id": 1,
    "email": "user@example.com",
    "nickname": "小同学",
    "grade_mode": "middle",
    "subscription_tier": "free"
  }
}
```

#### POST /api/auth/login — 用户登录

**请求体：**

```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

#### GET /api/auth/me — 获取当前用户

**请求头：**

```
Authorization: Bearer <token>
```

#### POST /api/auth/password — 修改密码

需登录（请求头带 `Authorization: Bearer <token>`）。

**请求体：**

```json
{
  "old_password": "原密码",
  "new_password": "新密码"
}
```

---

### 搭子接口

#### GET /api/buddy/status — 获取搭子状态

#### POST /api/buddy/quick-chat — 轻量对话（按角色人设作答）

**请求体：**

```json
{
  "buddy_id": "xiaodou",
  "message": "今天不想写作业",
  "explain_mode": "auto"
}
```

**响应：**

```json
{
  "success": true,
  "reply": "…",
  "buddy_id": "xiaodou",
  "buddy_name": "小豆",
  "used_model": "…"
}
```

> `buddy_id` 必须是 `BUDDY_ROLES` 中的 6 个之一：`xiaodou`、`aran`、`senior`、`xiaoye`、`xj`、`azheng`。前端历史别名 `xuejie` 会被归一化为 `senior`。

#### POST /api/buddy/explain — 游戏化讲解

**请求体：**

```json
{
  "buddy_id": "aran",
  "topic": "分数的加减法",
  "request_type": "topic"
}
```

`request_type` 可取 `topic`（知识点）、`plan`（学习计划）、`method`（学习方法）。响应含 `game` 与 `explain` 两段，用于前端的游戏区与讲解区。

#### GET /api/buddy/roles — 获取所有角色

#### POST /api/buddy/role/switch — 切换角色

#### GET/POST /api/buddy/memory — 记忆概览 / 新增场景记忆

`GET` 返回记忆概览，可选查询参数 `topic` 过滤；`POST` 新增一条场景记忆。

#### GET /api/buddy/memory/search — 按主题搜索记忆

查询参数：`q`（关键词）、`limit`（返回条数，默认 5）。

---

### 学习接口

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/api/study/start` | 开始学习 |
| POST | `/api/study/stop` | 结束学习 |
| GET | `/api/study/stats` | 学习统计（连续打卡、本周时长） |

---

### 我的挑战接口（小学 / 初中）

| 方法 | 端点 | 说明 |
|------|------|------|
| GET/POST | `/api/challenges` | 挑战数据 |
| POST | `/api/challenges/grade` | 设置学段（`primary` / `middle`） |
| GET | `/api/challenges/presets/grade/<grade_mode>` | 学段学科模板 |

---

## 角色人设

6 个角色各有独立人设，由 `src/buddy/buddy_roles.py` 定义，经 `src/ai/prompt_templates.py` 的 `get_chat_system_prompt()` 组装为对话提示词。

| 角色 id | 名字 | 性格 | 游戏化讲解舞台 |
|---------|------|------|----------------|
| `xiaodou` | 小豆 | 温柔陪伴型 | 知识花园 |
| `aran` | 阿燃 | 热血激励型 | 知识竞技场 |
| `senior` | 小老师 | 耐心讲解型 | 知识实验室 |
| `xiaoye` | 小夜 | 安静倾听型 | 知识星图 |
| `xj` | 戏精 | 幽默搞怪型 | 欢乐喜剧厂 |
| `azheng` | 阿正 | 理性分析型 | 数据驾驶舱 |

人设由三层组成：

1. **角色定义**（`BUDDY_ROLES`）— 名字、性格、适合的孩子、常用词、开场白
2. **对话风格**（`ROLE_STYLE_RULES`）— 80 条口语化规则 + 每角色专属风格
3. **游戏化讲解**（`BUDDY_EXPLAIN_PROMPTS`）— 每角色独立的游戏化舞台与输出格式

---

## 情绪量表

心情日记使用 **10 档**量表（`src/diary/diary.py` 的 `DiaryEntry.EMOTIONS`）：

| 等级 | 标签 | emoji | 等级 | 标签 | emoji |
|------|------|-------|------|------|-------|
| 1 | 难过 | 😢 | 6 | 开心 | 😀 |
| 2 | 低落 | 😔 | 7 | 兴奋 | 🥳 |
| 3 | 平静 | 😌 | 8 | 感恩 | ❤️ |
| 4 | 思考 | 🤔 | 9 | 希望 | 🌈 |
| 5 | 愉快 | 😊 | 10 | 疲惫 | 😴 |

量表边界与标签映射统一由 `DiaryEntry.EMOTION_MIN_LEVEL`、`EMOTION_MAX_LEVEL`、`EMOTION_LABELS` 与 `emotion_label_for_level()` 提供，各处不得再硬编码范围。

---

## 学段与学科

`src/modules/challenge_manager.py` 定义小学与初中两学段：

| 学段 | 值 | 默认学科 | 满分 | 呈现方式 |
|------|-----|----------|------|----------|
| 小学 | `primary` | 语文城堡、数学森林、英语海洋、科学秘境 | 100 | 星级 |
| 初中 | `middle` | 语文、数学、英语、物理、化学 | 120 / 100 | 星级 |

> 说明：本产品定位为小学到初中，**不含高中**。`GRADE_MODES` 与 `DEFAULT_SUBJECTS` 均已移除 `high`。

---

## 会员体系

| 等级 | AI 调用额度 | 说明 |
|------|-------------|------|
| free | 100 次/月 | 基础功能 |
| pro | 1000 次/月 | 全部功能优先 |
| vip | 10000 次/月 | 全部功能 |

> 说明：额度限制由 `src/auth/auth.py` 的 `ai_limit_required` 装饰器实现。**目前没有支付或订阅购买接口**，等级字段与额度判断存在，但无计费流程。

---

## 部署指南

### Docker 部署

1. 复制环境配置：

```bash
cp .env.production .env
```

2. 编辑 `.env` 填写实际值：

```bash
SECRET_KEY=your-secure-random-key
AI_API_KEY=your-api-key
```

3. 启动服务：

```bash
docker-compose up -d
```

> 注意：`docker-compose.yml` 只定义单个 `web` 服务，通过 `./data` 卷持久化 JSON 数据；当前代码不依赖外部数据库或缓存，因此不再定义 PostgreSQL / Redis / Nginx 等服务。多 worker 部署必须显式设置 `SECRET_KEY`，否则 Token 会在重启后失效。

### 传统部署

1. 安装依赖：

```bash
pip install -r requirements.txt
```

2. 启动应用：

```bash
python app.py
```

> 早期文档提到的 `python -m src.db init` 已不可用：数据库层已移除。

---

## 开发指南

### 本地开发

```bash
git clone https://github.com/linzizhen/StudyPal.git
cd StudyPal
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 填写 AI API Key
python app.py
```

### 运行测试

```bash
pip install pytest
python -m pytest tests/ -v
```

测试套件带数据隔离，运行后自动还原 `data/`。

---

## 版本历史

### 当前状态（未发布版本）

- **产品方向调整**：由「考研陪伴」重新定位为「小学到初中学习陪伴」
- 移除「目标院校 / 分数线 / 考试倒计时」概念，仪表盘改为习惯养成（连续打卡 + 本周小星星）
- 搭子人设链路接通：6 个角色均获得完整人设提示词（此前活前端只拿到 2 句话的降级提示词）
- 「学姐」改为「小老师」；「小夜」去掉熬夜导向
- 学段收敛为小学 / 初中，移除高中
- 成就系统去除 12 个考研专属成就，替换为习惯养成向成就
- 修复 9 个 500 端点、认证装饰器顺序错误、Token 伪造漏洞与密码无盐哈希
- 引入 pytest 回归测试套件
- 新增修改密码能力（`POST /api/auth/password`）
- 打通搭子的记忆本：三层记忆 + 记忆抽取写入链路（`src/buddy/memory_extractor.py`）
- 日记与任务改为服务端落库；主动关心冷却状态持久化至 `data/caring_state.json` 并呈现到界面
- 我的挑战模块接入主界面（此前为不可达死链路）
- 按设计判据修复 38 项界面可用性与可访问性缺陷
- 根治部署签名密钥并发竞态，清理 `docker-compose.yml` 空跑服务

### v3.1 (2026-05-25)

- AI 模型配置功能（预设模型、自定义模型、连接测试）
- 数据洞察页面
- 移动端样式优化
- 数据模型改为 dataclass 格式

### v3.0 (2026-05-21)

- 用户认证系统
- 订阅等级（Free / Pro / VIP）
- AI 调用次数限制
- 6 种搭子性格系统
- 80 条口语化规则

> 注：v3.0 规划中的「迁移到 SQLAlchemy ORM」「多用户数据隔离」「PostgreSQL」并未落地，相关代码已在后续清理中移除。

### v2.0 (2026-04-30)

- 重构为 Flask Web 应用
- 番茄钟、情绪日记、成就系统
- Blueprint 架构

### v1.0 (2026-04-13)

- CLI 版本发布
