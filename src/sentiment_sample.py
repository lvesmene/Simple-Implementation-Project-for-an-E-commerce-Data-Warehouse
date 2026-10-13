# -*- coding: utf-8 -*-
"""
sentiment_sample: 生成 120 条三带分层标注表(template, 不含 score/label)
口径与现行完全一致:直接用sentiment_analyzer 的 load_and_clean + analyze.
运行:conda activate my_py39_env && python src/sentiment_sample.py
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import output_path, OUTPUT_ENCODING
from db_loader import get_engine
from sentiment_analyzer import load_and_clean, analyze

BENCH_DIR = os.path.join(output_path, "sentiment_bench")

def main():
    os.makedirs(BENCH_DIR, exist_ok=True)
    engine = get_engine()

    # ---与现行口径完全一致的清洗 + 打分 （30~60秒）---
    df = load_and_clean(engine)
    df = analyze(df)

    # ---文本级去重已在 load_and_clean 内完成，此处不再重复---

    # ---缓存打分结果（benchmark脚本连用，含score/label，标注人勿看）---
    cache_path = os.path.join(BENCH_DIR, "_scored_cache.csv")
    df.drop(columns=["words", "norm"]).to_csv(cache_path, index=False, encoding=OUTPUT_ENCODING)
    print(F"打分已缓存（内部文件，含score，标注期间不要打开）:{cache_path}")

    #---三代分层抽样---
    parts=[]
    for band in ["负面", "中性", "正面"]:
        pool = df[df["label"] == band]
        n = min(40, len(pool))
        if n < 40:
            print(f"警告{band}带池子里只有{n}条,不足40条,验真标准要求每带≥40条")
        picked = pool.sample(n=n, random_state=42)
        parts.append(picked)
        print(F"{band}带:池{len(pool)} → 抽{n}")
    bench = pd.concat(parts)

    #---防污染三件套:去score/label列,只留标识+原文,随机打乱---
    out = bench[["user_id", "goods_id", "comment"]].sample(frac=1, random_state=42).reset_index(drop=True)
    out["gold"] = ""  # 人工填写:真负面/真中性/真正面/模糊

    out_path = os.path.join(BENCH_DIR, "标注表_120条_template.csv")
    out.to_csv(out_path, index=False, encoding=OUTPUT_ENCODING)
    print(f"\n标书模版已导出 → {out_path}")
    print(f"下一步:复制一份另存到notes/标注表_120条_filled.xlsx,在filled上标注")

if __name__ == "__main__":
    main()
