"""
xtquant 可用性诊断脚本

三级检查：
  1. 能否导入 xtdata
  2. 能否下载/获取历史数据
  3. 本地数据文件是否存在

用法:
  .venv\Scripts\python.exe demo_xtquant_test.py
"""

import sys
import os
import glob

# 必须先移除 XTQUANT_TESTING 环境变量, 否则 xtquant 路径不会被加入 sys.path
if os.environ.get("XTQUANT_TESTING"):
    del os.environ["XTQUANT_TESTING"]

# 手动添加 QMT SDK 路径
_QMT_PATH = r"D:\国金证券QMT交易端\bin.x64\Lib\site-packages"
if os.path.isdir(_QMT_PATH) and _QMT_PATH not in sys.path:
    sys.path.append(_QMT_PATH)

print("=" * 55)
print("  XTQUANT Diagnostic")
print("=" * 55)

# === Step 1: 检查 xtquant 是否可导入 ===
print("\n[Step 1] Check xtquant import")
try:
    from xtquant import xtdata
    print("  [OK] xtdata imported")
except ImportError as e:
    print(f"  [FAIL] Import error: {e}")
    print(f"  QMT path: {_QMT_PATH}")
    print(f"  Path exists: {os.path.isdir(_QMT_PATH)}")
    sys.exit(1)

# === Step 2: 测试下载历史数据 ===
print("\n[Step 2] Test download_history_data")
stock = "510880.SH"
try:
    xtdata.download_history_data(
        stock_code=stock,
        period='1d',
        start_time='20240101',
        end_time='20240301'
    )
    print(f"  [OK] {stock} download requested (no exception)")
except Exception as e:
    print(f"  [WARN] {stock} download error: {e}")
    print("  -> This may be a network issue, trying local data...")

# === Step 3: 获取市场数据 (不要求下载成功) ===
print("\n[Step 3] Get market data")
try:
    data = xtdata.get_market_data(
        field_list=['close', 'open', 'high', 'low', 'volume'],
        stock_list=[stock],
        start_time='20240101',
        end_time='20240301',
        period='1d'
    )
    if data and 'close' in data and len(data['close']) > 0:
        df = data['close']
        if stock in df.index:
            vals = df.loc[stock].dropna()
            print(f"  [OK] Got {len(vals)} bars for {stock}")
            print(f"    Date range: {vals.index[0]} ~ {vals.index[-1]}")
            print(f"    Price range: {vals.min():.4f} ~ {vals.max():.4f}")
            print(f"    Last 5:")
            for i in range(max(0, len(vals) - 5), len(vals)):
                print(f"      {vals.index[i]}  close={vals.iloc[i]:.4f}")
        else:
            print(f"  [WARN] {stock} not in result, available: {list(df.index)[:5]}")
    else:
        print(f"  [FAIL] No data: keys={list(data.keys()) if data else 'None'}")
        print("  -> QMT client may not be running or data not downloaded")
except Exception as e:
    print(f"  [FAIL] Error: {e}")

# === Step 4: 查看本地数据缓存 ===
print("\n[Step 4] Local data cache")
qmt_root = r"D:\国金证券QMT交易端\bin.x64"
for sub in ['datadir', 'data', 'cache', r'Lib\site-packages\xtquant\datadir']:
    p = os.path.join(qmt_root, sub)
    if os.path.exists(p):
        all_files = glob.glob(os.path.join(p, '**', '*'), recursive=True)
        print(f"  {sub}/ exists: {len(all_files)} files")
        for f in all_files[:5]:
            print(f"    {os.path.relpath(f, p)}")
    else:
        print(f"  {sub}/ not found")

# === Step 5: 批量测试多只 ETF ===
print("\n[Step 5] Multi-stock test")
etfs = ["510880.SH", "159905.SZ", "510300.SH", "510050.SH"]
for etf in etfs:
    try:
        data = xtdata.get_market_data(
            field_list=['close'],
            stock_list=[etf],
            start_time='20240101',
            end_time='20240131',
            period='1d'
        )
        if data and 'close' in data and etf in data['close'].index:
            cnt = len(data['close'].loc[etf].dropna())
            print(f"  {etf}: {cnt} bars")
        else:
            print(f"  {etf}: no data")
    except Exception as e:
        print(f"  {etf}: error - {type(e).__name__}")

# === Step 6: 环境检查 ===
print("\n[Step 6] Environment")
print(f"  Python: {sys.executable}")
print(f"  Platform: {sys.platform}")
print(f"  QMT root exists: {os.path.exists(qmt_root)}")

pth_file = os.path.join(
    os.path.dirname(sys.executable),
    "Lib", "site-packages", "xtquant.pth"
)
if os.path.exists(pth_file):
    with open(pth_file) as f:
        print(f"  xtquant.pth: {f.read().strip()[:100]}")
else:
    print(f"  xtquant.pth: not found")

print("\n" + "=" * 55)
print("  Done")
print("=" * 55)
