# -*- coding: utf-8 -*-
"""探索性分析模块"""
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns  # 显式导入
from scipy.stats import pointbiserialr
from config import output_path

def exploratory_analysis(df):
    """数据探索性分析，生成核心图表和统计报告"""
    print("\n" + "="*60)
    print("2. 数据探索性分析开始")
    print("="*60)

    # 1. 基础统计分析
    print("=== 基础统计信息 ===")
    numeric_cols = ['user_id', 'goods_id', 'category_id', 'price', 'amount', 'sex']
    stats_report = df[numeric_cols].describe().round(2)
    print(stats_report)
    stats_report.to_csv(f"{output_path}基础统计分析报告.csv", encoding='gb18030')

    # 2. 行为分布分析（饼图）
    behavior_count = df['behavior'].value_counts()
    print(f"\n=== 用户行为分布 ===")
    print(behavior_count)

    plt.figure(1, figsize=(8, 6))
    colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4']
    plt.pie(behavior_count.values, labels=behavior_count.index, autopct='%1.1f%%',
            colors=colors[:len(behavior_count)], startangle=90, textprops={'fontsize': 11})
    plt.title('图1 电商用户行为分布', fontsize=14, fontweight='bold', pad=20)
    plt.tight_layout()
    plt.savefig(f"{output_path}图1_用户行为分布饼图.png", dpi=300, bbox_inches='tight')
    plt.close()
    print("图1：用户行为分布饼图已保存")

    # 3. 时间特征分析（活跃时段柱状图）
    df['timestamp'] = pd.to_numeric(df['timestamp'], errors='coerce')
    df = df.dropna(subset=['timestamp']).copy()  # 确保副本操作
    df.loc[:, 'behavior_time'] = pd.to_datetime(df['timestamp'], unit='s')
    df.loc[:, 'hour'] = df['behavior_time'].dt.hour
    hour_dist = df['hour'].value_counts().sort_index()

    plt.figure(2, figsize=(12, 6))
    hour_dist.plot(kind='bar', color='#FF6B6B', alpha=0.7)
    plt.xlabel('小时', fontsize=12)
    plt.ylabel('行为次数', fontsize=12)
    plt.title('图2 电商用户活跃时段分布', fontsize=14, fontweight='bold', pad=20)
    plt.xticks(rotation=0)
    plt.grid(axis='y', alpha=0.3)
    # 标注高峰时段（新增）
    peak_hour = hour_dist.idxmax()
    plt.text(peak_hour, hour_dist.max()+1000, f'高峰', ha='center', color='red')
    plt.tight_layout()
    plt.savefig(f"{output_path}图2_用户活跃时段分布.png", dpi=300, bbox_inches='tight')
    plt.close()
    print("图2：用户活跃时段分布柱状图已保存")

    # 4. 商品分类热度分析（Top10柱状图）
    category_hot = df['category_id'].value_counts().head(10)
    plt.figure(3, figsize=(12, 6))
    category_hot.plot(kind='bar', color='#4ECDC4', alpha=0.7)
    plt.xlabel('商品分类ID', fontsize=12)
    plt.ylabel('累计行为次数', fontsize=12)
    plt.title('图3 热门商品分类Top10', fontsize=14, fontweight='bold', pad=20)
    plt.xticks(rotation=45)
    plt.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    plt.savefig(f"{output_path}图3_热门商品分类Top10.png", dpi=300, bbox_inches='tight')
    plt.close()
    print("图3：热门商品分类Top10柱状图已保存")

    # 5. 性别-行为相关性分析
    print("=== 性别-用户行为相关性分析 ===")
    gender_behavior = pd.crosstab(df['sex'], df['behavior'])
    print("性别-行为交叉表：")
    print(gender_behavior)

    gender_behavior_pct = gender_behavior.div(gender_behavior.sum(axis=1), axis=0)
    print("\n性别-行为占比表：")
    print(gender_behavior_pct.round(4))

    # 图4：行为占比热力图
    plt.figure(4, figsize=(8, 5))
    sns.heatmap(gender_behavior_pct,
                annot=True,
                fmt=".4f",
                cmap="YlOrRd",
                cbar_kws={'label': '行为占比'},
                linewidths=0.5,
                vmin=0.01, vmax=0.90)
    plt.title('图4 不同性别用户的行为占比热力图', fontsize=14, fontweight='bold', pad=15)
    plt.xlabel('用户行为')
    plt.ylabel('性别')
    plt.tight_layout()
    plt.savefig(f"{output_path}图4_性别行为占比热力图.png", dpi=300, bbox_inches='tight')
    plt.close()
    print("图4：性别-行为占比热力图已保存（优化渐变色）")

    # 图5：性别与行为相关性热力图
    behaviors = ['pv', 'cart', 'fav', 'buy']
    corr_values = []
    for behavior in behaviors:
        behavior_flag = (df['behavior'] == behavior).astype(int)
        corr, pval = pointbiserialr(df['sex'], behavior_flag)
        corr_values.append(corr)
    corr_df = pd.DataFrame([corr_values], columns=behaviors, index=['性别'])

    plt.figure(5, figsize=(8, 3))
    sns.heatmap(corr_df,
            annot=True,
            fmt=".4f",
            cmap="RdBu_r",
            center=0.0,
            cbar_kws={'label': '点二列相关系数'},
            linewidths=0.5)
    plt.title('图5 性别与各用户行为的相关性热力图', fontsize=14, fontweight='bold', pad=15)
    plt.xlabel('用户行为')
    plt.ylabel('性别')
    plt.tight_layout()
    plt.savefig(f"{output_path}图5_性别行为相关性热力图.png", dpi=300, bbox_inches='tight')
    plt.close()
    print("图5：性别-行为相关性热力图已保存")

    # 探索性分析总结（修正逻辑）
    print(f"\n=== 探索性分析总结 ===")
    main_behavior = '浏览' if 'pv' in behavior_count.index else '购买'
    main_behavior_ratio = behavior_count.max() / behavior_count.sum() * 100
    print(f"1. 用户行为以{main_behavior}为主，占比{main_behavior_ratio:.1f}%")
    print(f"2. 活跃高峰时段：{hour_dist.idxmax()}:00-{hour_dist.idxmax()+1}:00（行为次数：{hour_dist.max()}）")
    print(f"3. 最热门商品分类：{category_hot.index[0]}（行为次数：{category_hot.iloc[0]}）")
    
    # 修正性别购买占比计算（避免KeyError）
    gender_0_buy_pct = gender_behavior_pct.loc[0, 'buy'] if ('buy' in gender_behavior_pct.columns and 0 in gender_behavior_pct.index) else 0
    gender_1_buy_pct = gender_behavior_pct.loc[1, 'buy'] if ('buy' in gender_behavior_pct.columns and 1 in gender_behavior_pct.index) else 0
    print(f"4. 性别行为差异：性别0购买占比{gender_0_buy_pct:.2%}，性别1购买占比{gender_1_buy_pct:.2%}")

    return df

if __name__ == "__main__":
    from data_loader import load_data
    DATA_PATH = "UserBehavior--1.csv"
    df = load_data(DATA_PATH)
    df = exploratory_analysis(df)