#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
生成gRPC Python代码的脚本
"""

import os
import subprocess
import sys

def generate_grpc_code():
    """生成gRPC Python代码"""
    # 获取当前目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # proto文件路径
    proto_file = os.path.join(current_dir, "trade_service.proto")
    
    # 检查proto文件是否存在
    if not os.path.exists(proto_file):
        print(f"错误: 找不到proto文件 {proto_file}")
        return False
    
    # 生成gRPC Python代码的命令
    cmd = [
        sys.executable, "-m", "grpc_tools.protoc",
        f"--proto_path={current_dir}",
        f"--python_out={current_dir}",
        f"--grpc_python_out={current_dir}",
        proto_file
    ]
    
    try:
        # 执行命令
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=current_dir)
        
        if result.returncode == 0:
            print("gRPC Python代码生成成功!")
            
            # 修复生成的_pb2_grpc.py文件中的导入问题
            pb2_grpc_file = os.path.join(current_dir, "trade_service_pb2_grpc.py")
            if os.path.exists(pb2_grpc_file):
                with open(pb2_grpc_file, "r", encoding="utf-8") as f:
                    content = f.read()
                
                # 修复导入语句
                content = content.replace(
                    "import trade_service_pb2 as trade__service__pb2",
                    "from . import trade_service_pb2 as trade__service__pb2"
                )
                
                with open(pb2_grpc_file, "w", encoding="utf-8") as f:
                    f.write(content)
                
                print("已修复_pb2_grpc.py文件中的导入问题")
            
            return True
        else:
            print(f"生成gRPC Python代码失败: {result.stderr}")
            return False
    except Exception as e:
        print(f"执行命令时发生错误: {e}")
        return False

if __name__ == "__main__":
    success = generate_grpc_code()
    if not success:
        sys.exit(1)