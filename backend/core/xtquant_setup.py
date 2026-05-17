"""
xtquant SDK 路径初始化

将 QMT SDK 路径加入 sys.path，使 xtquant 模块可导入。
仅在 Windows 环境下且非测试模式时生效。

注意: QMT 自带的 google.protobuf 版本过旧(Python 3.11 不兼容)，
因此将 QMT 路径加在 sys.path 末尾，让 venv 的 protobuf 优先匹配。
"""

import os
import sys

_QMT_SITE_PACKAGES = r"D:\国金证券QMT交易端\bin.x64\Lib\site-packages"

if (
    os.path.isdir(_QMT_SITE_PACKAGES)
    and _QMT_SITE_PACKAGES not in sys.path
    and not os.environ.get("XTQUANT_TESTING")
):
    sys.path.append(_QMT_SITE_PACKAGES)
