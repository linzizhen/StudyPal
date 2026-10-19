# Changelog

所有重要的版本更新都会记录在此文件中。

格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/) 规范。

## [Unreleased]

### Changed

- **产品方向重新定义**：由「考研陪伴应用」改为面向**小学到初中**学生的学习陪伴应用
  - 学段收敛为小学（`primary`）与初中（`middle`），移除高中（`high`）
  - 移除「目标院校 / 目标专业 / 分数线 / 考试倒计时」概念
  - 仪表盘与「考研目标页」改为「我的成长页」：连续打卡天数 + 本周小星星
  - 学科体系更换为小学/初中科目（语文、数学、英语、科学、物理、化学）
  - 「学姐」角色改为「小老师」；「小夜」去掉熬夜导向
  - 成就系统移除 12 个考研专属成就，替换为习惯养成向成就
  - 学习计划与每日推荐的措辞去考研化

### Added

- **搭子人设链路接通**：6 个角色均获得完整人设提示词
  - 新增 `get_chat_system_prompt()`，把角色定义、80 条口语化规则与专属风格合并为对话提示词
  - 新增 `normalize_role_id()`，统一处理前端历史别名（`xuejie` → `senior`）
  - `/api/buddy/quick-chat` 改为使用完整人设，此前仅使用 2 句话的降级提示词且缺少 2 个角色
- **回归测试套件**：新增 `tests/`，覆盖端点健康度、认证安全、日记契约、角色人设、产品方向与前端成长页
- **安全加固**
  - 密码哈希由无盐 SHA-256 改为 PBKDF2-HMAC-SHA256（20 万次迭代 + 随机盐），旧哈希在登录时自动升级
  - Token 由「只解析不校验」改为 HMAC-SHA256 签名校验，修复身份伪造漏洞
  - `src/data/users.json` 移出版本控制，清除 15 个自动化测试残留账号

### Fixed

- 修复 9 个返回 500 的端点
  - `routes/buddy.py` 的 3 个角色端点因 `get_buddy` 未在模块层导入而抛 NameError
  - `routes/auth_routes.py` 与 `routes/buddy.py` 共 11 处装饰器顺序写反，导致 `@auth_required` 从未生效
  - `src/modules/daily_recommender.py` 调用了 `StudyTracker` 上不存在的 `get_today_subjects`
- 修复 `POST /api/diary` 任何请求都 500：`add_entry` 签名与调用方关键字不匹配
- 修复 `GET /api/insights/weekly-insight` 的写副作用：只读请求会经 AI 自动创建空会话
- 修复情绪量表契约冲突：`EMOTION_LABELS` 此前被引用但未定义；`insights.py` 用 5 元素数组索引 10 档量表导致 `IndexError`
- 修复前端角色数据表缺 2 个角色（点「戏精」「阿正」会 JS 崩溃）与 `xuejie`/`senior` 别名断裂
- 修复未知路径不返回 404（`not_found` 未设置状态码）

### Removed

- 删除 SQLAlchemy 死代码层：`src/db.py`、`src/db_service.py`、`src/migrate.py`、`src/models/`
- 删除 5 个零引用孤儿模块：`validators.py`、`role_identity.py`、`buddy_tools.py`、`option_parser.py`、`buddy_conversations.py`
- 删除陈旧日志与失效文件：`flask.err`、`test_results.txt`、`package-lock.json`

### Docs

- 重写 `README.md`：结构与 API 清单以代码为准（110 个 `/api/*` 端点、13 个预设模型、53 个成就、10 档情绪量表、两学段学科）
- 重写 `PRODUCT.md`：技术栈改为事实描述（JSON 存储、非 JWT 的自制 Token、无支付流程），并如实标注 v3.0 的 SQLAlchemy 迁移已回退
- `DESIGN_DOC.md` 保留为历史设计稿，顶部新增与当前实现的差异对照表

## [v3.1.0] - 2026-05-25

### Added

- **AI 模型配置功能**
  - 支持 9 种预设模型（Groq、DeepSeek、OpenRouter、Ollama）
  - 用户自定义模型配置
  - 模型连接测试功能
  - 6 种搭子性格完全兼容用户自定义模型

- **数据洞察页面**
  - 学习曲线柱状图
  - 科目分布分析
  - 情绪趋势可视化
  - 近 7/30/90 天时间切换

- **移动端优化**
  - 完整的响应式布局
  - 触摸友好的按钮和输入框
  - 底部导航适配
  - 模态框优化

### Changed

- 重构数据模型为 dataclass 格式
- 新增数据库服务层（`src/db_service.py`）
- 优化搭子系统支持用户自定义 AI 模型
- 完善移动端样式（`static/css/mobile.css`）

## [v3.0.0] - 2026-05-21

### Added

- **商业化版本基础架构**
  - 用户认证系统
  - 订阅等级（Free/Pro/VIP）
  - AI 调用次数限制
  - 用户数据持久化

- **6 种搭子性格系统**
  - 小豆（温柔陪伴型）
  - 阿燃（热血激励型）
  - 学姐（学霸导师型）
  - 小夜（深夜倾听型）
  - 戏精（幽默搞怪型）
  - 阿正（理性分析型）

- **80 条口语化规则**
  - 自然语言风格
  - 场景限定规则
  - 细节补充规则
  - 互动感规则

## [v2.0.0] - 2026-04-27

### Added

- Flask Blueprint 架构，模块化路由
- 前端 CSS/JS 模块化分离
- 新增任务管理页面
- 新增学习计划页面
- 新增每日推荐页面
- 三层记忆系统
- 主动关心引擎
- 32 个成就徽章与积分等级系统
- 考研历程时间线
- 单页应用（SPA）架构

## [v1.0.0] - 2026-04-13

### Added

- 初始版本
- 番茄钟计时器
- 基础搭子对话
- 日记系统
- 成就系统
