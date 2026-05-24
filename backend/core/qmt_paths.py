"""
QMT/xtquant 路径解析工具

统一管理 QMT SDK 路径的查找逻辑，支持:
- Windows 原生路径 (D:\...)
- WSL 互操作路径 (/mnt/d/...)
- 环境变量 XTQUANT_QMT_SDK 手动指定

输入 Windows 原生路径 (如 D:\国金证券QMT交易端\bin.x64\Lib\site-packages)，
自动尝试 Windows 和 WSL 两种路径格式。
"""

import os
import sys
from pathlib import Path
from typing import Optional


_QMT_CANDIDATE_ROOTS = [
    r"D:\国金证券QMT交易端",
    r"D:\国金QMT交易端",
    r"C:\国金证券QMT交易端",
    r"D:\QMT",
]

_QMT_SDK_SUBPATH = r"bin.x64\Lib\site-packages"
_QMT_USERDATA_SUBPATH = r"userdata_mini"


def _to_wsl_path(windows_path: str) -> str:
    """将 Windows 路径转换为 WSL 路径 (/mnt/{drive}/...)"""
    if len(windows_path) >= 2 and windows_path[1] == ":":
        drive = windows_path[0].lower()
        rest = windows_path[2:].replace("\\", "/")
        return f"/mnt/{drive}{rest}"
    return windows_path


def _to_windows_path(windows_path: str) -> str:
    """确保返回 Windows 原生格式路径"""
    return windows_path.replace("/", "\\")


def _path_exists(path: str) -> bool:
    """检查路径是否存在 (支持 WSL 下的 Windows 路径转换)"""
    if os.path.isdir(path):
        return True
    wsl_path = _to_wsl_path(path)
    if wsl_path != path and os.path.isdir(wsl_path):
        return True
    return False


def find_qmt_root() -> Optional[str]:
    """查找 QMT 安装根目录

    查找优先级:
    1. 环境变量 XTQUANT_QMT_ROOT
    2. 预定义的候选路径 (Windows + WSL)
    """
    env_root = os.environ.get("XTQUANT_QMT_ROOT")
    if env_root and _path_exists(env_root):
        return env_root

    for candidate in _QMT_CANDIDATE_ROOTS:
        if _path_exists(candidate):
            return candidate
        wsl_path = _to_wsl_path(candidate)
        if wsl_path != candidate and _path_exists(wsl_path):
            return wsl_path

    return None


def find_qmt_sdk() -> Optional[str]:
    """查找 xtquant SDK 目录 (bin.x64/Lib/site-packages)

    查找优先级:
    1. 环境变量 XTQUANT_QMT_SDK
    2. 从 QMT 根目录推导
    3. 预定义的候选路径
    """
    env_sdk = os.environ.get("XTQUANT_QMT_SDK")
    if env_sdk and _path_exists(env_sdk):
        return env_sdk

    root = find_qmt_root()
    if root:
        sdk_path = os.path.join(root, _QMT_SDK_SUBPATH)
        if _path_exists(sdk_path):
            return sdk_path

    return None


def find_qmt_userdata() -> Optional[str]:
    """查找 QMT userdata_mini 目录

    查找优先级:
    1. 环境变量 XTQUANT_QMT_PATH (兼容旧版变量名)
    2. 从 QMT 根目录推导
    """
    env_path = os.environ.get("XTQUANT_QMT_PATH")
    if env_path and _path_exists(env_path):
        return env_path

    root = find_qmt_root()
    if root:
        userdata_path = os.path.join(root, _QMT_USERDATA_SUBPATH)
        if _path_exists(userdata_path):
            return userdata_path

    return None


def ensure_qmt_in_syspath() -> bool:
    """将 xtquant SDK 路径加入 sys.path (幂等)

    Returns:
        True 如果成功找到并加入 QMT 路径
    """
    if os.environ.get("XTQUANT_TESTING"):
        return False

    sdk_path = find_qmt_sdk()
    if sdk_path and sdk_path not in sys.path:
        sys.path.append(sdk_path)
        return True
    return False
