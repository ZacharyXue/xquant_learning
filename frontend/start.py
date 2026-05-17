"""
启动脚本

并行启动 FastAPI 后端和 Vite 前端开发服务器
"""

import subprocess
import sys
import os
import time


def run_backend():
    """启动 FastAPI 后端"""
    print("正在启动后端服务...")
    subprocess.Popen(
        [sys.executable, "backend.py"],
        cwd=os.path.dirname(os.path.abspath(__file__)),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True,
    )


def run_frontend():
    """启动 Vite 前端"""
    print("正在启动前端服务...")
    # npm 在 F:\nodejs 目录
    cmd = [r"F:\nodejs\npm.cmd", "run", "dev"]

    subprocess.Popen(
        cmd,
        cwd=os.path.dirname(os.path.abspath(__file__)),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True,
    )


def main():
    # 获取项目根目录 (frontend 目录)
    frontend_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(frontend_dir)
    if project_root:
        os.chdir(project_root)

    # 并行启动
    run_backend()
    time.sleep(2)
    run_frontend()

    print("\n" + "=" * 50)
    print("回测系统已启动!")
    print("前端: http://localhost:5173")
    print("后端: http://localhost:8000")
    print("=" * 50)
    print("\n按 Ctrl+C 停止服务")

    # 保持运行
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n正在停止服务...")


if __name__ == "__main__":
    main()