"""
xtquant SDK 路径初始化

将 QMT SDK 路径加入 sys.path，使 xtquant 模块可导入。
仅在 Windows 环境下且非测试模式时生效。
"""

import os
import sys

_QMT_SITE_PACKAGES = r"D:\国金证券QMT交易端\bin.x64\Lib\site-packages"

if (
    os.path.isdir(_QMT_SITE_PACKAGES)
    and _QMT_SITE_PACKAGES not in sys.path
    and not os.environ.get("XTQUANT_TESTING")
):
    sys.path.insert(0, _QMT_SITE_PACKAGES)
