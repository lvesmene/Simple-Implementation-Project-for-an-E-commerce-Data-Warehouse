# -*- coding: utf-8 -*-
"""sentiment_analyzer: Phase 3 收尾——评论情感分析（jieba 分词 + SnowNLP 情感打分）

教学要点：
    1. SnowNLP 的情感模型用电商购物评论训练，与本项目数据天然匹配
       但它是"词袋 + 朴素贝叶斯"，对反讽/长否定句会误判，结果需抽样人工复核
    2. jieba 默认词典是通用语料，"发货速度""性价比"等电商词会被切碎
       → add_word 加载领域词，这是文本分析的标准做法
    3. 情感阈值三分法：>0.8 正面 / 0.2~0.8 中性 / <0.2 负面（阈值可按业务调）

运行方式：
    conda activate my_py39_env
    python src/sentiment_analyzer.py
"""
import os
import sys
from collections import Counter

import pandas as pd
import matplotlib.pyplot as plt
import jieba
from snownlp import SnowNLP

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import output_path, OUTPUT_ENCODING
from db_loader import get_engine

# ---------- jieba 电商领域自定义词（防止被切碎） ----------
ECOMMERCE_WORDS = [
    "物流", "发货速度", "快递员", "客服", "售后", "性价比", "正品",
    "包装", "退换货", "返修", "赠品", "促销", "京东商城", "实体店",
    "快递小哥", "第三方", "卖家", "买家", "好评", "差评", "给力",
]

# ---------- 简版停用词（高频但无情感信息的词） ----------
STOPWORDS = {
    "的", "了", "是", "我", "不", "都", "也", "很", "就", "还", "啊", "吧",
    "吗", "呢", "在", "有", "一个", "这个", "那个", "自己", "什么", "没有",
    "可以", "因为", "所以", "但是", "就是", "觉得", "东西", "京东",
    "买", "收到", "感觉", "知道", "时间", "问题", "地方", "应该", "现在",
    # 第2轮：高频无情感词
    "一直", "不是", "本书", "非常", "真的", "其实", "可能", "还是",
    # 第3轮：连接词/程度副词/时间 filler（仍无情感信号）
    # 注意："不好" 是负面情感词，不要加入此组
    "时候", "这样", "而且", "比较", "已经", "其他", "这么", "怎么",
    # meta 词：用户在评论里描述自己行为（给差评/给好评），非商品反馈
    "差评", "好评", "中评",
    # 歧义词：不结合品类无法判别情感（苹果手机/水果）
    "苹果",
    # 第4轮: 通过绘制的评论高频词 Top20 发现弱情感信号,模糊词
    "有点", "一样",
    # 第5轮: 通过绘制的评论的高频词 Top20 发现模糊词
    "效果", "第一次", "以后", "一次", "还有",
}

# ============================================================
# Step 1: 读数 + 清洗（对账思维：每步打印行数漏斗）
# ============================================================
def load_and_clean(engine):
    print("\n--- Step 1: 读取 ods_comment 并清洗 ---")
    sql = "SELECT user_id, goods_id, category_id, comment FROM ods_comment"
    df = pd.read_sql(sql, engine)
    print(f"  原始评论：{len(df)} 行")

    df = df.dropna(subset=["comment"]).copy()
    df["comment"] = df["comment"].astype(str).str.strip()
    print(f"  去空评论：{len(df)} 行")

    before = len(df)
    df = df.drop_duplicates(subset=["user_id", "goods_id"], keep="first")
    print(f"  同人同商品去重：{before} → {len(df)} 行")

    before = len(df)
    df = df[df["comment"].str.len() >= 5]
    print(f"  过滤超短文本(<5字)：{before} → {len(df)} 行")
    return df.reset_index(drop=True)

# ============================================================
# Step 2: jieba 分词 + SnowNLP 情感打分（1.4万条约需 30-60 秒）
# ============================================================
def analyze(df):
    print("\n--- Step 2: jieba 分词 + SnowNLP 情感打分 ---")
    for w in ECOMMERCE_WORDS:
        jieba.add_word(w)

    # 分词结果存列，供高频词统计复用
    df["words"] = df["comment"].apply(
        lambda t: [w for w in jieba.cut(t)
                   if len(w) >= 2 and w not in STOPWORDS and not w.isdigit()]
    )

    scores = []
    for i, text in enumerate(df["comment"]):
        scores.append(SnowNLP(text).sentiments)
        if (i + 1) % 3000 == 0:
            print(f"  情感打分进度：{i + 1}/{len(df)}")
    df["score"] = scores
    # 阈值校准：紧到[0.2, 0.8]:把中等置信度区间归到中性，让分布更接近真实
    df["label"] = pd.cut(df["score"], bins=[-0.01, 0.2, 0.8, 1.01],
                         labels=["负面", "中性", "正面"])
    dist = df["label"].value_counts()
    print(f"  情感分布：正面 {dist.get('正面', 0)} | 中性 {dist.get('中性', 0)}"
          f" | 负面 {dist.get('负面', 0)}")
    return df

# ============================================================
# 图15: 情感分布柱状图
# ============================================================
def plot_sentiment(df):
    print("\n--- 图15: 评论情感分布 ---")
    order = ["正面", "中性", "负面"]
    cnt = df["label"].value_counts().reindex(order, fill_value=0)
    colors = ["#2ecc71", "#f39c12", "#e74c3c"]

    plt.figure(15, figsize=(8, 6))
    bars = plt.bar(order, cnt.values, color=colors, alpha=0.8, width=0.55)
    plt.ylabel("评论数", fontsize=12)
    plt.title("图15 评论情感分布（SnowNLP 三分法）", fontsize=14, fontweight="bold", pad=15)
    plt.grid(axis="y", alpha=0.3)
    plt.ylim(0, cnt.max() * 1.15)  # 顶部留白，防止标注压边框（图11同款经验）
    for bar, val in zip(bars, cnt.values):
        pct = val / cnt.sum() * 100
        plt.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + cnt.max() * 0.02,
                 f"{val:,}\n({pct:.1f}%)", ha="center", fontsize=11)
    plt.tight_layout()
    plt.savefig(f"{output_path}图15_评论情感分布.png", dpi=300, bbox_inches="tight")
    plt.close()
    print("图15 已保存")

# ============================================================
# 图16: 评论高频词 Top20
# ============================================================
def plot_top_words(df):
    print("\n--- 图16: 评论高频词 Top20 ---")
    all_words = Counter()
    for words in df["words"]:
        all_words.update(words)

    top20 = all_words.most_common(20)
    print("  " + " | ".join(f"{w}:{c}" for w, c in top20[:10]))

    # 导出评论高频词top20供powerbi导入
    pd.DataFrame(top20, columns=["关键词", "出现次数"]).to_csv(
        f"{output_path}图16_评论高频词Top20.csv", index=False, encoding=OUTPUT_ENCODING
    )
    print("  词频 Top20 已导出 → 图16_评论高频词Top20.csv（供 PowerBI 导入）")

    words, counts = zip(*top20)
    plt.figure(16, figsize=(10, 8))
    plt.barh(range(len(words))[::-1], counts, color="#3498db", alpha=0.8)
    # barh 把 counts[0] 放在位置19（顶端），yticks 位置同步倒序才能让 words[0] 对齐同一根柱
    plt.yticks(range(len(words))[::-1], words, fontsize=11)

    plt.xlabel("出现次数", fontsize=12)
    plt.title("图16 评论高频词 Top20", fontsize=14, fontweight="bold", pad=15)
    plt.grid(axis="x", alpha=0.3)
    plt.xlim(0, max(counts) * 1.12)  # 右侧留白，防止条末标注压边框
    for y, c in zip(range(len(words))[::-1], counts):
        plt.text(c + max(counts) * 0.01, y, f"{c:,}", va="center", fontsize=9)
    plt.tight_layout()
    plt.savefig(f"{output_path}图16_评论高频词Top20.png", dpi=300, bbox_inches="tight")
    plt.close()
    print("图16 已保存")
    return all_words

# ============================================================
# 图17: 品类维度负面率 Top10（JOIN dim_category 拿中文名）
# 教学点：分组后过滤小样本（评论<20 的品类占比不稳定）——pandas 写法等价于 SQL 的 HAVING COUNT(*)>=20
# ============================================================
def plot_category_negative(engine, df):
    print("\n--- 图17: 品类负面率 Top10 ---")
    cat = df.groupby("category_id").agg(
        total=("label", "size"),
        neg=("label", lambda s: (s == "负面").sum()),
    )
    cat["neg_pct"] = cat["neg"] / cat["total"] * 100
    cat = cat[cat["total"] >= 20].sort_values("neg_pct", ascending=False).head(10)

    with engine.connect() as conn:
        names = pd.read_sql("SELECT category_id, category_label FROM dim_category", conn)
    cat = cat.merge(names, on="category_id", how="left")
    cat["label_txt"] = cat["category_label"].fillna("未知品类")

    plt.figure(17, figsize=(12, 6))
    plt.barh(range(len(cat))[::-1], cat["neg_pct"], color="#e74c3c", alpha=0.8)
    # 同图16：yticks 位置同步倒序，label_txt[0]（最高负面率品类）对应顶端柱
    plt.yticks(range(len(cat))[::-1], cat["label_txt"], fontsize=10)

    plt.xlabel("负面评论占比 (%)", fontsize=12)
    plt.title("图17 负面率最高品类 Top10（评论数≥20）", fontsize=14, fontweight="bold", pad=15)
    plt.grid(axis="x", alpha=0.3)
    plt.xlim(0, cat["neg_pct"].max() * 1.3)  # 右侧留白（图13同款经验）
    for y, pct, neg, tot in zip(range(len(cat))[::-1], cat["neg_pct"], cat["neg"], cat["total"]):
        plt.text(pct + cat["neg_pct"].max() * 0.01, y,
                 f"{pct:.1f}% ({neg}/{tot})", va="center", fontsize=9)
    plt.tight_layout()
    plt.savefig(f"{output_path}图17_品类负面率Top10.png", dpi=300, bbox_inches="tight")
    plt.close()
    print("图17 已保存")

# ============================================================
# Step 3: 输出负面评论清单（供策略报告引用）
# ============================================================
def save_negative_list(df):
    print("\n--- Step 3: 导出负面评论清单 ---")
    # Bug fix：原来写死 score<0.4，与 analyze() 里的 bins(0.2) 不一致
    # 统一改用 label 列，导出与分布统计同源
    neg = df[df["label"] == "负面"].sort_values("score")[
        ["user_id", "goods_id", "category_id", "comment", "score"]
    ].round({"score": 4})
    neg.to_csv(f"{output_path}负面评论清单.csv", index=False, encoding=OUTPUT_ENCODING)
    print(f"  已导出 {len(neg)} 条负面评论（按分数升序=最差在前）")
    print(neg.head(3).to_string(index=False))

def plot_score_distribution(df):
    print("\n--- 图18: SnowNLP 情感分数分布直方图 ---")
    plt.figure(18, figsize=(10, 6))
    plt.hist(df["score"], bins=20, color="#9b59b6", alpha=0.8, edgecolor="white")
    plt.axvline(0.2, color="#e74c3c", linestyle="--", linewidth=1.5, label="负面阈值 0.2")
    plt.axvline(0.8, color="#2ecc71", linestyle="--", linewidth=1.5, label="正面阈值 0.8")
    plt.xlabel("SnowNLP 情感分数", fontsize=12)
    plt.ylabel("评论数", fontsize=12)
    plt.title("图18 SnowNLP 情感分数分布（双峰特征）", fontsize=14, fontweight="bold", pad=15)
    plt.legend(loc="upper center")
    plt.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(f"{output_path}图18_情感分数分布直方图.png", dpi=300, bbox_inches="tight")
    plt.close()
    print("图18 已保存")

# ============================================================
# Step 4: 导出人工复核样本（分层等距 20 条）
# ============================================================
def export_sample_for_review(df):
    print("\n--- Step 4: 导出人工复核样本（分层等距 20 条） ---")
    neg = df[df["label"] == "负面"].copy()
    # 分层：低分 [0,0.1) / 中低 [0.1,0.2) 
    bins = [(-0.01, 0.1), (0.1, 0.2), ]
    samples = []
    for lo, hi in bins:
        seg = neg[(neg["score"] >= lo) & (neg["score"] < hi)].sort_values("score")
        n = min(10, len(seg))
        if n == 0:
            print(f"  分层 [{lo:.2f}, {hi:.2f})：0 条，跳过")
            continue
        step = max(1, len(seg) // n)
        picked = seg.iloc[::step].head(n)
        samples.append(picked)
        print(f"  分层 [{lo:.2f}, {hi:.2f})：{len(seg)} 条，抽 {n} 条")
    if not samples:
        print("  ⚠ 未取到样本")
        return
    sample = pd.concat(samples).sort_values("score")[
        ["score", "comment"]
    ].copy()
    sample["comment"] = sample["comment"].str.slice(0, 80)
    sample["review"] = ""  # 人工填入：真负面 / 误判 / 模糊
    sample.to_csv(f"{output_path}负面评论抽样复核表.csv", index=False, encoding=OUTPUT_ENCODING)
    print(f"  已导出 {len(sample)} 条待复核样本 → 负面评论抽样复核表.csv")
    print("  复核完成后填入 review 列：真负面 / 误判 / 模糊")


def main():
    print("=" * 60)
    print("Phase 3 收尾：评论情感分析（jieba + SnowNLP）")
    print("=" * 60)
    engine = get_engine()
    df = load_and_clean(engine)
    df = analyze(df)
    plot_sentiment(df)
    plot_score_distribution(df)
    plot_top_words(df)
    plot_category_negative(engine, df)
    save_negative_list(df)
    export_sample_for_review(df)
    print("\n✅ 情感分析完成！产出：图15/16/17/18 + 图16_评论高频词Top20.csv + 负面评论清单.csv + 负面评论抽样复核表.csv")
    print(f"保存位置：{output_path}")

if __name__ == "__main__":
    main()