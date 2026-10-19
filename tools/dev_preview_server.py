"""
本地预览启动脚本

用途：在缺少 flask_cors 依赖的环境里启动 StudyPal 供预览。
仅在进程内注入一个最小存根（CORS 装饰器），不改动项目任何文件，
也不写入 requirements。

用法：
    python tools/dev_preview_server.py

注意：这是开发预览的临时手段。正式部署请安装 requirements.txt。
"""

import os
import sys
import types

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def _install_flask_cors_stub_if_missing():
    """缺少 flask_cors 时注入最小存根。

    项目对 CORS 的使用仅为 `CORS(app, resources=...)`，存根返回一个
    恒等装饰器即可满足运行时需求。
    """
    try:
        import flask_cors  # noqa: F401

        print("[预览] flask_cors 已安装，正常使用")
        return
    except ImportError:
        pass

    stub = types.ModuleType("flask_cors")

    def CORS(app=None, **kwargs):
        def decorator(func):
            return func

        return decorator

    stub.CORS = CORS
    sys.modules["flask_cors"] = stub
    print("[预览] 未安装 flask_cors，已注入内存存根（不影响功能，仅跳过 CORS 头）")


def main():
    _install_flask_cors_stub_if_missing()
    import app as studypal

    port = int(os.getenv("PORT", "5000"))
    print(f"[预览] 启动 StudyPal，访问 http://127.0.0.1:{port}")
    print("[预览] 停止：在终端按 Ctrl+C")
    studypal.app.run(debug=False, port=port, host="127.0.0.1", use_reloader=False)


if __name__ == "__main__":
    main()
