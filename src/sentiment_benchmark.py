# -*- coding:utf-8 -*-
"""
sentiment_benchmark:TF-IDF+LR 对照 SnowNLP (金标 120 条)
主轨:银标(剔除金标防泄漏,14,433 条,SnowNLP 伪标签)训练LR → 金标折外评估
辅轨: 120 金标 5 折 CV (报 mean + std)
运行: conda activate my_py39_env 
     python src/sentiment_benchmark.py
"""
import os
import sys

import numpy as np
import pandas as pd
import jieba

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import ROOT_DIR, output_path, OUTPUT_ENCODING
from sentiment_analyzer import ECOMMERCE_WORDS, STOPWORDS

BENCH_DIR = os.path.join(output_path, "sentiment_bench")
GOLD_PATH = os.path.join(ROOT_DIR, "notes", "标注表_120条_filled.xlsx")
CLASSES = ["负面", "中性", "正面"]

# 文件头 + 载入金标并回连
def load_gold():
    """读金标 + 回连 SnowNLP 打分缓存 + 标签统一 + 数据校验"""
    # xlsx 为二进制格式，自带 UTF-8，无 CSV 的 ANSI/GBK 编码陷阱
    gold = pd.read_excel(GOLD_PATH, dtype={"user_id": "int64", "goods_id": "int64"})
    cache = pd.read_csv(os.path.join(BENCH_DIR, "_scored_cache.csv"), encoding="utf-8-sig")

    # (user_id, goods_id) 在缓存里不唯一：同一人同一商品可有多条不同评论（520 组现象）
    # 必须把 comment 并入连接键，否则左连接会"基数膨胀"（1 行金标 × 2 行缓存 = 2 行）
    df = gold.merge(cache[["user_id", "goods_id", "comment", "score", "label"]],
                    on=["user_id", "goods_id", "comment"], how="left", validate="one_to_one")

    assert len(df) ==120, f"回连后 {len(df)} 行 ≠ 120,检查 user_id/goods_id/comment 是否被 wps 改动"
    assert df["score"].notna().all(), "有金标没匹配上打分缓存, 检查键值"

    # # 标签统一: 真负面 → 负面(SnowNPL 用三分无"真"字)
    # df["gold_std"] = df["gold"].replace("真", "", regex=True)
    # vaild = set(CLASSES) | {"模糊"}
    # bad = set(df["gold_std"].unique()) - vaild
    
    # 标签统一：显式映射（白名单），不靠删字符——避免"真"出现在正文里被误删
    LABEL_MAP = {"真负面": "负面", "真中性": "中性", "真正面": "正面", "模糊": "模糊"}
    df["gold_std"] = df["gold"].map(LABEL_MAP)
    bad = set(df.loc[df["gold_std"].isna(), "gold"].unique())
    assert not bad, f"gold 列有非法标注值: {bad} (只允许 真负面/真中性/真正面/模糊)"

    vague =(df["gold"] == "模糊").sum()
    print(f"金标 {len(df)} 条, 其中模糊 {vague} 条 ({vague/len(df)*100:.2f}%, 上限 10%")
    return df[df["gold"] != "模糊"].copy()

# numpy 手算混淆矩阵
def manual_confusion(y_true, y_pred, classes=CLASSES):
    """纯 numpy 手算混淆矩阵与负面类 P/R/F1 -- 先手算一遍, 再看sklearn 的答案"""
    cm = np.zeros((len(classes), len(classes)), dtype=int)
    for i, c_t in enumerate(classes):
        for j, c_p in enumerate(classes):
            cm[i, j] = int(((y_true == c_t) & (y_pred ==c_p)).sum())

    # 负面类：按名字定位行列（不假设"负面"在第 0 位，改 CLASSES 顺序也不会算错）
    neg = classes.index("负面")
    assert classes[neg] == "负面"  # 保险：确认查到的确实是负面
    tp = cm[neg, neg]
    fp = cm[:, neg].sum() - tp    # 判为负面的列里, 不是真负面的
    fn = cm[neg, :].sum() - tp    # 真负面的行里, 没判成负面的
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return cm, precision, recall, f1

# 与 sklearn 对照 + 加权召回
from sklearn.metrics import classification_report
def evaluate_baseline(df, n_bands):
    """SnowNLP 基线: 手算对照 sklearn + 按带大小加权的召回/F1 (方案 3.3.1)"""
    y_true, y_pred = df["gold_std"], df["label"]

    cm, p, r, f1 = manual_confusion(y_true, y_pred)
    print("手算混淆矩阵(行=真实, 列=预测) : \n", cm)
    print(f"手算负面类 P={p:.4f} R={r:.4f} F1={f1:.4f}")
    print("\nsklearn classification_report(对照手算,应该一致):")
    print(classification_report(y_true, y_pred, labels=CLASSES, digits=4, zero_division=0))

    # ---加权召回 (分层抽样偏差修正): 召回_负 = ∑(p_b·N_b) / ∑_b(p_b·N_b)) ---
    p_band = {b: (df[df["label"] == b]["gold_std"] == "负面").mean() for b in CLASSES}
    numer = p_band["负面"] * n_bands["负面"]
    denom = sum(p_band[b] * n_bands[b] for b in CLASSES)
    r_w = numer / denom if denom else 0.0
    f1_w = 2 * p * r_w /(p + r_w) if p + r_w else 0.0
    print(f"加权负面召回: 朴素 {r:.4f} → 加权 {r_w:.4f}; 加权 F1={f1_w:.4f}")
    return {"P": p, "R_w": r_w, "F1_w": f1_w}

# TF-IDF + 逻辑回归流水线
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

for w in ECOMMERCE_WORDS:
    jieba.add_word(w)

def tokenize(text):
    """与现行口径同源的分词:jieba + 领域词 + 停用词 + 长度≥2 + 去纯数字"""
    return [w for w in jieba.cut(str(text))
            if len(w) >= 2 and w not in STOPWORDS and not w.isdigit()]

def make_pipeline():
    return Pipeline([
        ("tfidf", TfidfVectorizer(tokenizer=tokenize, token_pattern=None,ngram_range=(1, 2), min_df=2)),
        ("lr", LogisticRegression(class_weight="balanced", max_iter=1000, random_state=42)),
    ])

# 主轨训练 + 评估 + 看模型学了什么
def run_main_track(df, cache):
    """主轨: 全量银标(剔除金标评估集)训练 → 金标评估(方案4.2.2)"""
    # 关键: 金标本身就在 cache 里, 直接全量训练会让模型"见过"评估样本 → 指标偏乐观
    # 按 load_gold 的连接键反连接剔除, 让评估集对主轨也是"没见过的"(折外预测)
    key = ["user_id", "goods_id", "comment"]
    train = cache.merge(df[key].drop_duplicates(), on=key, how="left", indicator=True)
    train = train[train["_merge"] == "left_only"].drop(columns="_merge")
    print(f"主轨训练集: cache {len(cache)} 条 → 剔除金标 {len(cache) - len(train)} 条 → {len(train)} 条")

    pipe = make_pipeline()
    pipe.fit(train["comment"], train["label"])     # 银标: SnowNLP 伪标签
    
    # 对金标数据df进行预测(模型没见过它们, 属折外预测)，用来评估模型性能
    # 对全量银标cache进行预测，用来统计模型预测各带的条数(加权召回的分母)
    df["lr_label"] = pipe.predict(df["comment"])
    cache["lr_label"] = pipe.predict(cache["comment"])

    # LR 自己预测的带的条数，有别与SnowNLP预测的带的条数n_bands
    n_bands_lr = cache["lr_label"].value_counts().to_dict()
    print(f"LR 主轨各带条数: {n_bands_lr}")   

    # --- 看一眼模型: 特征维度与稀疏度 ---
    vec = pipe.named_steps["tfidf"]
    X = vec.transform(cache["comment"])
    print(f"TF-IDF 矩阵: {X.shape[0]} 条 × {X.shape[1]} 维特征,"
          f"稀疏度 {1 - X.nnz / (X.shape[0] * X.shape[1]):.4f}")

    # --- 系数解读: 哪些词最指向负面 ---
    lr = pipe.named_steps["lr"]
    vocab = np.array(vec.get_feature_names_out())
    neg_i = list(lr.classes_).index("负面")
    top = np.argsort(lr.coef_[neg_i])
    print("最指向负面的 20 个特征: ", " ".join(vocab[top[-20:]]))
    print("最排斥负面的 20 个特征: ", " ".join(vocab[top[:20]]))

    cm, p, r, f1 = manual_confusion(df["gold_std"].values, df["lr_label"].values)
    # 加权同3.3: p_band 换成 lr 的预测带
    p_band = {b: (df[df["lr_label"] == b]["gold_std"] == "负面").mean() for b in CLASSES}
    r_w = (p_band["负面"] * n_bands_lr["负面"]) / sum(p_band[b] * n_bands_lr[b] for b in CLASSES)
    f1_w = 2 * p * r_w / (p + r_w) if p + r_w else 0.0
    print(f"LR 主轨负面类: P={p:.4f} 加权R={r_w:.4f} 加权F1={f1_w:.4f}")
    return df, {"P": p, "R_w": r_w, "F1_w": f1_w}, pipe

# 辅轨：120 金标 5 折交叉验证   
from sklearn.model_selection import StratifiedKFold, cross_val_predict, cross_validate

def run_aux_track(df):
    """辅轨: 金标 5 折CV, 报 mean ± std (数据极少时的下限估计)"""
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    pipe = make_pipeline()

    res = cross_validate(pipe, df["comment"], df["gold_std"], cv=skf, scoring=["f1_macro", "f1_weighted"])

    m, s = res["test_f1_macro"].mean(), res["test_f1_macro"].std()
    print(f"辅轨 5 折 macro-f1: {m:.4f} ± {s:.4f} (各折: {np.round(res['test_f1_macro'], 3)})")

    # 折外预测: 每条样本的预测都来自于"没见过它"的那一模型的折 -- 可公平地与 SnowNLP 配对比较
    # 新建了一个`make_pipeline() （全新的、没训练过的空管道）
    df["lr_cv_label"] = cross_val_predict(make_pipeline(), df["comment"], df["gold_std"], cv=skf)
    return df

# McNemar 检验
from statsmodels.stats.contingency_tables import mcnemar

def mcnemar_test(df, lr_col="lr_label"):
    """
    负面二分类视角的配对检验(逐行比较两个模型的对错).
    默认用 lr_label(主轨): 它由银标(SnowNLP伪标签)训练, 评估的是"若上线该模型,
    逐条预测相对 SnowNLP 有多少翻转、是否显著改善" (金标 119 条已剔除, 无泄漏).
    注意: 因其训练标签来自 SnowNLP, 两模型错误高度相关 → 不一致对天然偏少,
    该检验功效有限, "p 不显著"应读作"行为几乎不变"而非"证明两者等价".
    硬样本挖掘请用 export_errors 的 lr_cv_label(人工金标训练的独立模型).
    """
    y_true_bin = (df["gold_std"] == "负面").values
    snow_ok = (df["label"].values == "负面") == y_true_bin   # 逐元素,保证按行对齐
    lr_ok = (df[lr_col].values == "负面") == y_true_bin

    n01 = int((snow_ok & ~lr_ok).sum())    # SnowNLP 对, LR 错
    n10 = int((~snow_ok & lr_ok).sum())    # SnowNLP 错, LR 对
    table = [[int((snow_ok & lr_ok).sum()), n01],
             [n10, int((~snow_ok & ~lr_ok).sum())]]
    result = mcnemar(table, exact=(n01 + n10 < 25))
    print(f"McNemar({lr_col}): SnowNLP对/LR错={n01}, SnowNLP错/LR对={n10}, p={result.pvalue:.4f}")
    return result.pvalue

# PR-AUC 与 P-R 曲线（定性参考）
from sklearn.metrics import average_precision_score, precision_recall_curve
import matplotlib.pyplot as plt

def pr_analysis(df, pipe):
    """阈值无关对比 + P-R 曲线 (仅定性, 见方案 4.3 限定词)"""
    y_bin = (df["gold_std"] == "负面").astype(int).values

    # SnowNLP score 是"正面置信度" → 1 - score 转为"越负面越高"
    ap_snow = average_precision_score(y_bin, 1 - df["score"].values)
    neg_i = list(pipe.classes_).index("负面") 
    lr_neg_prob = pipe.predict_proba(df["comment"])[:, neg_i]
    ap_lr = average_precision_score(y_bin, lr_neg_prob)
    print(f"负面类 PR_AUC: SnowNLP={ap_snow:.4f} | LR={ap_lr:.4f}")
    
    plt.figure(figsize=(8, 6))
    for prob, name, color in [(1 - df["score"].values, f"SnowNLP (AP={ap_snow:.3f})", "#e74c3c"),
                              (lr_neg_prob, f"TF-IDF+LR (AP={ap_lr:.3f})", "#3498db")]:

        prec, rec, _ = precision_recall_curve(y_bin, prob)
        plt.plot(rec, prec, label=name, color=color, linewidth=2)
    plt.xlabel("召回率")
    plt.ylabel("精确率")
    plt.title("负面类 P-R 曲线 (金标集, 仅定性参考)")
    plt.legend()
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(BENCH_DIR, "PR曲线_负面类.png"), dpi=300, bbox_inches="tight")
    plt.close()

def export_errors(df):
    """两法误判对照: 重点看'都判错'的样本 -- 那是数据本身的硬骨头"""
    both_wrong = df[(df["label"] != df["gold_std"]) & (df["lr_cv_label"] != df["gold_std"])]
    cols = ["user_id", "goods_id", "comment", "gold_std", "label", "lr_cv_label", "score"]
    both_wrong[cols].to_csv(os.path.join(BENCH_DIR, "SnowNLP和LR_CV两法误判对照.csv"), index=False, encoding=OUTPUT_ENCODING)

    print(f"两法都判错共: {len(both_wrong)} 条 → SnowNLP和LR_CV两法误判对照.csv(人工归纳失效模式)")

def main():
    df = load_gold()
    cache = pd.read_csv(os.path.join(BENCH_DIR, "_scored_cache.csv"), encoding="utf-8-sig")
    n_bands = cache["label"].value_counts().to_dict()       # 去重后全量各带真实条数
    print(f"抽样框各带条数: {n_bands}")

    print("\n========== 基线: SnowNLP ==========")
    res_snow = evaluate_baseline(df, n_bands)

    print("\n========== 主轨: TF_IDF + LR (银标训练) ===========")
    df, res_lr, pipe = run_main_track(df, cache)

    print("\n========== 辅轨: 金标 5 折 CV ==========")
    df = run_aux_track(df)

    print("\n========== 显著性与阈值无关对比 ===========")
    p_mcnemar = mcnemar_test(df)
    pr_analysis(df, pipe)

    print("\n========== 误判分析 ============")
    export_errors(df)

    summary = pd.DataFrame([
        {"模型": "SnowNLP(基线)", **res_snow},
        {"模型": "TF-IDF+LR(主轨银标)", **res_lr},
    ])
    summary.to_csv(os.path.join(BENCH_DIR, "对照结果.csv"), index=False, encoding=OUTPUT_ENCODING)
    print("\n", summary.round(4).to_string(index=False))

    # --- 决策线(预注册：加权 F1 提升≥5pp 且 p<0.05 才换口径；res_lr 为金标剔除后的折外预测，无泄漏) ---
    delta = (res_lr["F1_w"] - res_snow["F1_w"]) * 100
    print(f"\n负面加权 F1 相差: {delta:+.2f} pp | McNemar p={p_mcnemar:.4f}")
    print("决策线判定:", "建议更换口径" if (delta >= 5 and p_mcnemar < 0.05)
          else "维持 SnowNLP 现行口径 (差异不足或不显著)" )

if __name__ == "__main__":
    main()
