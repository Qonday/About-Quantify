"""通过 Tushare 获取股票数据。

配置 token（任选一种）：
1. 在项目根目录的 .env 里写一行 TUSHARE_TOKEN=你的token（该文件已被 .gitignore 排除）
2. 设置环境变量 TUSHARE_TOKEN
token 在 https://tushare.pro/user/token 获取。

用法：
    python getdata.py                    # 拉取 2024 年全部 A 股日线，并存到 data/
    from getdata import get_market_daily
    df = get_market_daily("20240101", "20241231")   # 全市场
    from getdata import get_stock_daily
    df = get_stock_daily("000001.SZ", "20240101", "20241231")  # 单只股票
"""

import os
import time
from pathlib import Path

import pandas as pd
import tushare as ts

DATA_DIR = Path(__file__).parent / "data"
ENV_FILE = Path(__file__).parent / ".env"


def _load_token():
    """优先读环境变量，其次读同目录 .env 里的 TUSHARE_TOKEN=xxx。"""
    token = os.getenv("TUSHARE_TOKEN", "").strip()
    if token:
        return token
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            key, _, value = line.strip().partition("=")
            if key.strip() == "TUSHARE_TOKEN":
                return value.strip().strip("'\"")
    return ""


TOKEN = _load_token()

_pro = None


def get_pro():
    """获取 Tushare Pro 接口对象（只初始化一次）。"""
    global _pro
    if _pro is None:
        if not TOKEN:
            raise ValueError("未找到 token，请设置环境变量 TUSHARE_TOKEN 或直接修改本文件中的 TOKEN")
        ts.set_token(TOKEN)
        _pro = ts.pro_api()
    return _pro


def get_stock_list():
    """获取 A 股股票列表。"""
    return get_pro().stock_basic(exchange="", list_status="L", fields="ts_code,symbol,name,industry,list_date")


def get_stock_daily(ts_code, start_date, end_date, save=True):
    """获取单只股票日线行情。

    参数：
        ts_code:    股票代码，如 "000001.SZ"
        start_date: 开始日期，如 "20240101"
        end_date:   结束日期，如 "20241231"
        save:       是否保存到 data/ 目录为 CSV
    返回：
        DataFrame（按交易日期升序），无数据时返回空 DataFrame
    """
    df = get_pro().daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.sort_values("trade_date").reset_index(drop=True)
    if save:
        DATA_DIR.mkdir(exist_ok=True)
        df.to_csv(DATA_DIR / f"{ts_code}_{start_date}_{end_date}.csv", index=False, encoding="utf-8-sig")
    return df


def get_trade_dates(start_date, end_date):
    """获取区间内的交易日列表（升序）。"""
    cal = get_pro().trade_cal(exchange="SSE", start_date=start_date, end_date=end_date, fields="cal_date,is_open")
    return sorted(cal.loc[cal["is_open"] == 1, "cal_date"].tolist())


def get_market_daily(start_date="20240101", end_date="20241231", save=True, sleep=0.2):
    """获取区间内全部 A 股的日线行情（按交易日逐日拉取后拼接）。

    参数：
        start_date: 开始日期，如 "20240101"
        end_date:   结束日期，如 "20241231"
        save:       是否保存到 data/daily_{起}_{止}.csv
        sleep:      每次请求之间的间隔秒数，避免触发频率限制
    返回：
        DataFrame，按 交易日 + 股票代码 排序
    """
    dates = get_trade_dates(start_date, end_date)
    frames = []
    for i, date in enumerate(dates, 1):
        df = get_pro().daily(trade_date=date)
        if df is not None and not df.empty:
            frames.append(df)
        total = sum(len(f) for f in frames)
        print(f"\r进度 {i}/{len(dates)}  日期 {date}  累计 {total} 条", end="", flush=True)
        if i < len(dates):
            time.sleep(sleep)
    print()

    if not frames:
        return pd.DataFrame()

    data = pd.concat(frames, ignore_index=True)
    data = data.sort_values(["trade_date", "ts_code"]).reset_index(drop=True)
    if save:
        DATA_DIR.mkdir(exist_ok=True)
        path = DATA_DIR / f"daily_{start_date}_{end_date}.csv"
        data.to_csv(path, index=False, encoding="utf-8-sig")
        print(f"已保存到 {path}")
    return data


if __name__ == "__main__":
    data = get_market_daily("20240101", "20241231")
    print(data.head())
    print(f"共 {len(data)} 条，{data['ts_code'].nunique()} 只股票")
