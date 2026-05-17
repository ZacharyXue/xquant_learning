import sys
import os
import pytest

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# 确保测试环境变量设置
os.environ.setdefault('PYTHONPATH', os.path.join(os.path.dirname(__file__), 'src'))

# 添加tests目录到路径以便导入测试工具
tests_dir = os.path.join(os.path.dirname(__file__), 'tests')
sys.path.insert(0, tests_dir)