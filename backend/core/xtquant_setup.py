"""
xtquant SDK 路径初始化

将 QMT SDK 路径加入 sys.path，使 xtquant 模块可导入。
支持 Windows 原生路径和 WSL2 互操作路径 (/mnt/d/...)。

注意: QMT 自带的 google.protobuf 版本过旧(Python 3.11 不兼容)，
因此将 QMT 路径加在 sys.path 末尾，让 venv 的 protobuf 优先匹配。
"""

from backend.core.qmt_paths import ensure_qmt_in_syspath

ensure_qmt_in_syspath()
