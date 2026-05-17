"""
gRPC 代码生成脚本

从 trade.proto 生成 Python 代码。
需安装: pip install grpcio-tools
"""

import subprocess
from pathlib import Path

PROTO_DIR = Path(__file__).parent
PROTO_FILE = PROTO_DIR / "trade.proto"


def generate():
    cmd = [
        "python", "-m", "grpc_tools.protoc",
        f"--proto_path={PROTO_DIR}",
        f"--python_out={PROTO_DIR}",
        f"--grpc_python_out={PROTO_DIR}",
        str(PROTO_FILE),
    ]
    subprocess.run(cmd, check=True)

    # Fix generated import path
    _fix_imports()


def _fix_imports():
    pb2_grpc = PROTO_DIR / "trade_pb2_grpc.py"
    if pb2_grpc.exists():
        content = pb2_grpc.read_text(encoding="utf-8")
        content = content.replace(
            "import trade_pb2 as trade__pb2",
            "from backend.grpc import trade_pb2 as trade__pb2",
        )
        pb2_grpc.write_text(content, encoding="utf-8")
        print("Fixed imports in trade_pb2_grpc.py")


if __name__ == "__main__":
    generate()
