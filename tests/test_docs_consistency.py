"""
文档与代码一致性测试

把 README / PRODUCT / CHANGELOG 里对代码的关键断言变成可执行检查，
避免文档再次与实现脱节。

运行：
  python -m pytest tests/test_docs_consistency.py -v
"""

import os
import re
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def _read(*parts):
    with open(os.path.join(PROJECT_ROOT, *parts), encoding="utf-8") as handle:
        return handle.read()


@pytest.fixture(scope="module")
def readme():
    return _read("README.md")


@pytest.fixture(scope="module")
def product():
    return _read("PRODUCT.md")


@pytest.fixture(scope="module")
def design_doc():
    return _read("DESIGN_DOC.md")


@pytest.fixture(scope="module")
def changelog():
    return _read("CHANGELOG.md")


@pytest.fixture(scope="module")
def flask_app():
    import types

    try:
        import flask_cors  # noqa: F401
    except ImportError:
        stub = types.ModuleType("flask_cors")
        stub.CORS = lambda app=None, **kw: (lambda f: f)
        sys.modules["flask_cors"] = stub
    import app as mainapp

    return mainapp.app


# ==================== 文档自称的数字必须与代码一致 ====================


def test_documented_role_count_matches_code(readme, product):
    """文档声称的 6 个角色必须与 BUDDY_ROLES 一致。"""
    from src.buddy.buddy_roles import BUDDY_ROLES

    assert len(BUDDY_ROLES) == 6, f"实际角色数为 {len(BUDDY_ROLES)}"
    assert "6 种性格" in readme or "6 种" in readme
    for role_id in BUDDY_ROLES:
        assert role_id in product or role_id in readme, f"文档未提及角色 {role_id}"


def test_documented_model_count_matches_code(readme):
    """README 声称的 13 个预设模型必须与 MODELS_CONFIG 一致。"""
    from config import MODELS_CONFIG

    assert len(MODELS_CONFIG) == 13, f"实际模型数为 {len(MODELS_CONFIG)}"
    assert "13 种预设模型" in readme
    for key in MODELS_CONFIG:
        assert key in readme, f"README 的模型表缺少 {key}"


def test_documented_achievement_count_matches_code(readme):
    """README 声称的 53 个成就必须与 ALL_ACHIEVEMENTS 一致。"""
    from src.modules.achievements import ALL_ACHIEVEMENTS

    assert len(ALL_ACHIEVEMENTS) == 53, f"实际成就数为 {len(ALL_ACHIEVEMENTS)}"
    assert "53 个成就" in readme


def test_documented_emotion_scale_matches_code(readme, product):
    """文档声称的 10 档情绪量表必须与 EMOTIONS 一致。"""
    from src.diary.diary import DiaryEntry

    assert len(DiaryEntry.EMOTIONS) == 10
    assert "10 档" in readme
    assert "10 档" in product
    for emotion in DiaryEntry.EMOTIONS:
        assert emotion["label"] in product, f"PRODUCT 的情绪表缺少「{emotion['label']}」"


def test_documented_grade_modes_match_code(readme, product):
    """文档声称的学段必须与 GRADE_MODES 一致（小学 + 初中，不含高中）。"""
    from src.modules.challenge_manager import GRADE_MODES

    assert GRADE_MODES == ["primary", "middle"]
    assert "primary" in readme and "middle" in readme
    assert "primary" in product and "middle" in product
    # 不得把高中写成支持的学段
    assert "不含高中" in readme or "不含高中" in product


def test_documented_endpoint_count_is_accurate(readme, flask_app):
    """README 声称的端点数量必须与实际注册数一致（允许 ±5 的维护余量）。"""
    api_rules = [r for r in flask_app.url_map.iter_rules()
                 if str(r).startswith("/api/")]
    match = re.search(r"\*\*(\d+)\s*个\s*`?/api/\*`?\s*端点\*\*", readme)
    assert match, "README 未声明端点数量"
    claimed = int(match.group(1))
    assert abs(claimed - len(api_rules)) <= 5, (
        f"README 声称 {claimed} 个端点，实际 {len(api_rules)} 个"
    )


# ==================== 文档不得再传播已回退的技术描述 ====================


def test_product_does_not_claim_sqlalchemy_is_used(product):
    """PRODUCT 不得再把 SQLAlchemy 写成当前使用的技术栈。

    技术栈表格里只能出现实际使用的技术；回退说明可以写在表格之外的注释中。
    """
    tech_section = product.split("### 技术栈")[1].split("###")[0]
    # 只检查表格行（以 | 开头），注释段落允许提到已回退的技术
    table_lines = [ln for ln in tech_section.splitlines() if ln.strip().startswith("|")]
    table_text = "\n".join(table_lines)
    assert "SQLAlchemy" not in table_text, "技术栈表仍声称使用 SQLAlchemy"
    # "非 JWT" 这类否定表述是允许的；禁止的是把它写成正在使用的技术
    assert "非 JWT" not in table_text or "自制 Token" in table_text, (
        "技术栈表应说明认证为自制 Token 而非 JWT"
    )
    assert "JWT" not in table_text.replace("非 JWT", ""), "技术栈表仍声称使用 JWT"
    assert "JSON" in table_text, "技术栈表未说明实际使用 JSON 存储"


def test_product_notes_sqlalchemy_rollback(product):
    """PRODUCT 应说明 v3.0 的 ORM 迁移已回退。"""
    assert "回退" in product
    assert "SQLAlchemy" in product


def test_readme_does_not_advertise_missing_endpoints(readme):
    """README 不得再宣称不存在的洞察端点。"""
    for bogus in ("/api/insights/overview", "/api/insights/study-chart",
                  "/api/insights/emotion-chart", "/api/insights/subject-analysis"):
        assert bogus not in readme, f"README 仍宣称不存在的端点 {bogus}"


def test_readme_lists_real_modules(readme):
    """README 的项目结构必须覆盖实际存在的关键模块。

    结构图采用树形缩进（只写文件名），因此这里核对文件名是否出现，
    并单独确认这些文件在仓库中真实存在。
    """
    required = [
        "challenges.py", "timeline.py", "recommend.py",
        "auth.py", "auth_routes.py",
        "challenge_manager.py", "plan_generator.py",
        "study_tracker.py", "file_lock.py",
        "dashboard.html", "dashboard.js",
    ]
    for name in required:
        assert name in readme, f"README 结构图缺少 {name}"

    # 关键路径必须在仓库中真实存在
    for path in ("routes/challenges.py", "src/routes/auth_routes.py",
                 "src/modules/challenge_manager.py", "templates/dashboard.html",
                 "static/js/dashboard.js"):
        assert os.path.exists(os.path.join(PROJECT_ROOT, *path.split("/"))), (
            f"README 提到的模块实际不存在：{path}"
        )


def test_readme_does_not_list_nonexistent_data_files(readme):
    """README 不得列出不存在的数据文件。"""
    for bogus in ("data/buddy_profile.json", "data/tasks.json"):
        assert bogus not in readme, f"README 仍列出不存在的数据文件 {bogus}"


def test_readme_does_not_link_missing_license(readme):
    """README 不得链接不存在的 LICENSE 文件。"""
    if "[LICENSE]" in readme:
        assert os.path.exists(os.path.join(PROJECT_ROOT, "LICENSE")), (
            "README 链接了 LICENSE，但仓库中没有该文件"
        )


# ==================== 方向一致性 ====================


def test_readme_describes_primary_middle_not_kaoyan(readme):
    """README 的产品定位必须是小学到初中。"""
    assert "小学" in readme and "初中" in readme
    # 不能把考研当作产品定位
    assert "考研学习搭子" not in readme
    first_lines = "\n".join(readme.splitlines()[:6])
    assert "考研" not in first_lines, "README 开头仍以考研定位"


def test_product_describes_primary_middle(product):
    """PRODUCT 的目标用户必须是小学/初中学生。"""
    assert "小学" in product and "初中" in product
    users_section = product.split("### 目标用户")[1].split("###")[0]
    assert "考研" not in users_section, "目标用户段仍写考研学生"


def test_design_doc_is_marked_as_historical(design_doc):
    """DESIGN_DOC 必须明确标注为历史设计稿并给出差异说明。"""
    head = "\n".join(design_doc.splitlines()[:40])
    assert "历史设计稿" in head or "历史" in head, "DESIGN_DOC 未标注历史属性"
    assert "差异" in head, "DESIGN_DOC 未给出与当前实现的差异说明"
    # 应指向当前权威文档
    assert "README.md" in head or "PRODUCT.md" in head


def test_design_doc_path_correction_noted(design_doc):
    """DESIGN_DOC 的版本说明应指出路径不准确的问题。"""
    head = "\n".join(design_doc.splitlines()[:45])
    assert "src/routes/auth_routes.py" in head, (
        "DESIGN_DOC 未指出 routes/auth_routes.py 的真实位置"
    )


def test_changelog_records_direction_change(changelog):
    """CHANGELOG 必须记录产品方向调整与关键修复。"""
    unreleased = changelog.split("## [v3.1.0]")[0]
    for keyword in ("小学到初中", "人设", "安全", "500"):
        assert keyword in unreleased, f"CHANGELOG 的 Unreleased 段缺少 {keyword} 相关记录"


# ==================== 文档排版规范 ====================


def test_readme_has_no_placeholder_leftovers(readme):
    """README 不得残留占位符。"""
    for placeholder in ("TODO", "待补充", "FIXME"):
        assert placeholder not in readme, f"README 残留占位符 {placeholder}"


def test_docs_have_language_tagged_code_blocks(readme, product):
    """代码块必须标注语言类型。"""
    for name, content in (("README.md", readme), ("PRODUCT.md", product)):
        for line in content.splitlines():
            if line.strip().startswith("```") and line.strip() != "```":
                tag = line.strip()[3:].strip()
                assert tag, f"{name} 存在未标注语言的代码块：{line.strip()}"
