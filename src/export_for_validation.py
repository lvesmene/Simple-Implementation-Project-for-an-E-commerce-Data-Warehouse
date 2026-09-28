# -*- coding: utf-8 -*-
"""export_for_validation: Phase 5--导出交叉验证明细宽表(供 Excel 独立复算)

教学要点:
    1. 核对要导出"明细"而非"结果": Excel 拿到逐行数据才能独立重新聚合
    2. 一份宽表覆盖多个指标 = 数仓"单一事实来源"思想在核对环节的体现
    3. LEFT JOIN 以维度为左表,保证 10739 个用户一个不漏(含未购买者)

运行方式:
    conda activate my_py39_env
    python src/export_for_validation.py
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import ROOT_DIR, OUTPUT_ENCODING
from db_loader import get_engine

VALIDATION_DIR = os.path.join(ROOT_DIR, "output", "validation")
os.makedirs(VALIDATION_DIR, exist_ok=True)

# 列顺序固定为 A-I, Excel 公式按次引用:
# A=face  B=user_id  C=r_days  D=f_freq  E=m_amount  F=r_score  G=f_score  H=m_score  I=user_segment
SQL_RFM_WIDE = """
    SELECT
        TRIM(REPLACE(REPLACE(p.face, ' ', ''), ' ', '')) AS face,
        p.user_id,
        r.r_days,r.f_freq,r.m_amount,
        r.r_score,r.f_score,r.m_score,
        r.user_segment
    FROM dim_user_profile p
    LEFT JOIN ads_rfm_segments r ON p.user_id = r.user_id
    ORDER BY face, p.user_id
"""

def main():
    engine = get_engine()
    df = pd.read_sql(SQL_RFM_WIDE, engine)

    buyer = int(df["r_days"].notna().sum())
    print(f"明细宽表:{len(df)} 行 | {df['face'].nunique()} 个职业 | "
          f"{df['user_id'].nunique()} 个用户 | 购买用户 {buyer} 人")
    print(f"购买总额: {df['m_amount'].sum():,.2f}")
    print("  ↑ 这 4 个数字就是 Excel 的复算基准；导出本身错了，后面全白做")

    path = os.path.join(VALIDATION_DIR, "交叉验证_明细宽表.csv")
    df.to_csv(path, index=False, encoding=OUTPUT_ENCODING)
    print(f"已导出 → {path}")

if __name__ == "__main__":
    main()