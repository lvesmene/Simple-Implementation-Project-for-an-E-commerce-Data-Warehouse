# -*- coding: utf-8 -*-
"""ads_visualizer: Phase 3 可视化——从 MySQL 数仓读 ADS/DWD 数据并绘图

教学要点：
    1. pd.read_sql + SQLAlchemy engine 是 pandas 读数据库的标准方式
    2. 用户级漏斗用 COUNT(DISTINCT user_id) 去重，比行级 COUNT 更准
    3. 职业交叉必须算占比（分子/分母），绝对数会被基数大小误导

运行方式：
    cd 项目根目录
    python src/ads_visualizer.py
"""
from numpy._typing._array_like import NDArray
import os
from pandas.core.series import Series
from pandas.core.frame import DataFrame
import sys
from typing import Any

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import output_path, OUTPUT_ENCODING
from db_loader import get_engine


# ============================================================
# 图11: RFM 八类客户分布柱状图
# 教学点：pd.read_sql 把 SQL 结果直接读成 DataFrame
# ============================================================
def plot_rfm_distribution(engine):
    print("\n--- 图11: RFM 八类客户分布 ---")
    sql = """
        SELECT user_segment, COUNT(*) AS users
        FROM ads_rfm_segments
        GROUP BY user_segment
        ORDER BY users DESC
    """
    df = pd.read_sql(sql, engine)
    print(df.to_string(index=False))

    # 按业务优先级排序：价值>保持>挽留>发展（按 avg_m + 紧迫度，与图12热力图保持一致）
    order = ['重要价值客户', '重要保持客户', '重要挽留客户', '重要发展客户',
             '一般价值客户', '一般保持客户', '一般挽留客户', '一般发展客户']
    df['order'] = df['user_segment'].map({name: i for i, name in enumerate(order)})
    df = df.sort_values('order')

    plt.figure(11, figsize=(12, 6))
    colors = ['#e74c3c' if '重要' in s else '#3498db' for s in df['user_segment']]
    bars = plt.bar(range(len(df)), df['users'], color=colors, alpha=0.8)
    plt.xticks(range(len(df)), df['user_segment'], rotation=35, ha='right', fontsize=10)
    plt.ylabel('用户数', fontsize=12)
    plt.title('图11 RFM 八类客户分布', fontsize=14, fontweight='bold', pad=15)
    plt.grid(axis='y', alpha=0.3)
    plt.ylim(0, df['users'].max() * 1.15)  # 顶部留白15%，防止柱顶标注压到边框
    for bar, val in zip(bars, df['users']):
        pct = val / df['users'].sum() * 100
        plt.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 10,
                 f'{val}\n({pct:.1f}%)', ha='center', fontsize=9)
    plt.tight_layout()
    plt.savefig(f"{output_path}图11_RFM八类客户分布.png", dpi=300, bbox_inches='tight')
    plt.close()
    print("图11 已保存")


# ============================================================
# 图12: RFM 均值梯度热力图
# 教学点：均值矩阵用热力图验证分群合理性（重要价值应最"深"）
# ============================================================
def plot_rfm_means(engine):
    print("\n--- 图12: RFM 均值梯度热力图 ---")
    sql = """
        SELECT user_segment,
               ROUND(AVG(r_days), 2)     AS avg_r,
               ROUND(AVG(f_freq), 2)     AS avg_f,
               ROUND(AVG(m_amount), 2)   AS avg_m
        FROM ads_rfm_segments
        GROUP BY user_segment
    """
    df = pd.read_sql(sql, engine)
    print(df.to_string(index=False))

    # 按业务优先级排序（与图11一致）：价值>保持>挽留>发展
    order = ['重要价值客户', '重要保持客户', '重要挽留客户', '重要发展客户',
             '一般价值客户', '一般保持客户', '一般挽留客户', '一般发展客户']
    df['order'] = df['user_segment'].map({name: i for i, name in enumerate(order)})
    df = df.sort_values('order').set_index('user_segment')[['avg_r', 'avg_f', 'avg_m']]

    # 三个维度量纲不同，分别归一化到 0-1 让热力图可比
    # R 维度是逆向指标（越小越好），需反向归一化使颜色越深=越近购买；F/M 保持正向
    df_norm = df.copy()
    for col in df_norm.columns:
        col_min, col_max = df_norm[col].min(), df_norm[col].max()
        if col_max > col_min:
            if col == 'avg_r':
                df_norm[col] = (col_max - df_norm[col]) / (col_max - col_min)
            else:
                df_norm[col] = (df_norm[col] - col_min) / (col_max - col_min)
        else:
            df_norm[col] = 0

    plt.figure(12, figsize=(10, 6))
    # 颜色映射用 df_norm（颜色越深=该维度越好），格子数字用 df（原始均值）
    sns.heatmap(df_norm, annot=df, fmt='.2f', cmap='YlOrRd',
                linewidths=0.5, cbar_kws={'label': '列内归一化值（越深=越好）'})
    plt.title('图12 RFM 八类客户均值梯度（颜色=归一化[越深越好]，数字=原始均值）', fontsize=14, fontweight='bold', pad=15)
    plt.xlabel('RFM 维度')
    plt.ylabel('客户分群')
    plt.tight_layout()
    plt.savefig(f"{output_path}图12_RFM均值梯度热力图.png", dpi=300, bbox_inches='tight')
    plt.close()
    print("图12 已保存")


# ============================================================
# 图13: 职业 × 高价值客户占比（修正昨天的绝对数问题）
# 教学点：
#   a. LEFT JOIN dim_user_profile → ads_rfm_segments
#      （以画像表为左表，保留所有职业，RFM 缺失算 0）
#   b. 占比 = 高价值人数 / 该职业总人数（不是 / 总高价值人数）
#   c. 过滤掉总人数<100 的职业（样本太小，占比不稳定）
# ============================================================
def plot_occupation_cross(engine):
    print("\n--- 图13: 职业 × 高价值客户占比 ---")
    sql = """
        SELECT
            p.face AS occupation,
            COUNT(*) AS total_users,
            SUM(CASE WHEN r.user_segment IN
                ('重要价值客户','重要发展客户','重要保持客户','重要挽留客户')
                THEN 1 ELSE 0 END) AS high_value
        FROM dim_user_profile p
        LEFT JOIN ads_rfm_segments r ON p.user_id = r.user_id
        GROUP BY p.face
        HAVING total_users >= 100
        ORDER BY high_value * 1.0 / total_users DESC
    """
    df = pd.read_sql(sql, engine)
    df['high_value_pct'] = (df['high_value'] / df['total_users'] * 100).round(2)
    print(df.to_string(index=False))

    plt.figure(13, figsize=(12, 6))
    # barh + yticks 同步倒序，让占比最高的职业位于最顶端（与图16/17 一致风格）
    bars = plt.barh(range(len(df))[::-1], df['high_value_pct'], color='#2ecc71', alpha=0.8)
    plt.yticks(range(len(df))[::-1], df['occupation'], fontsize=10)
    plt.xlabel('高价值客户占比 (%)', fontsize=12)
    plt.title('图13 各职业高价值客户占比（总人数≥100）', fontsize=14, fontweight='bold', pad=15)
    plt.grid(axis='x', alpha=0.3)
    plt.xlim(0, df['high_value_pct'].max() * 1.3)  # 右侧留白30%，防止条末标注压到边框
    for bar, pct, hv, tot in zip(bars, df['high_value_pct'], df['high_value'], df['total_users']):
        plt.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height() / 2,
                 f'{pct:.1f}% ({hv}/{tot})', va='center', fontsize=9)
    # plt.gca().invert_yaxis()  # 兑现倒序意图的备选写法（与上面 [::-1] 等价，二选一即可），且等同于ax.invert_yaxis()
    plt.tight_layout()
    plt.savefig(f"{output_path}图13_职业高价值客户占比.png", dpi=300, bbox_inches='tight')
    plt.close()
    print("图13 已保存")


# ============================================================
# 图14: 用户级漏斗（浏览→加购→购买→收藏，去重版本）
# 教学点：
#   a. COUNT(DISTINCT user_id) 是用户级去重，比 COUNT(*) 行级更准
#      行级漏斗：pv 68万行 → 看着转化率只有 2%
#      用户级漏斗：pv 1万独立用户 → 购买转化率 ~57%（6110/10739）
#      两个数字都对，但讲的故事完全不同
#   b. 漏斗顺序 pv→cart→buy→fav 是数据驱动决策：
#      fav 用户3488 < buy 用户6110，若 fav 是 pre-buy 步骤应 fav ≥ buy
#      数据反向说明 fav 是 post-buy 行为（买完顺手收藏备复购）
#      同时业务逻辑：cart 是"现在要买"，fav 是"以后可能买"，两者互斥不重叠
# ============================================================
def plot_user_funnel(engine):
    print("\n--- 图14: 用户级转化漏斗 ---")
    sql = """
        SELECT
            COUNT(DISTINCT CASE WHEN behavior = 'pv'   THEN user_id END) AS pv_users,
            COUNT(DISTINCT CASE WHEN behavior = 'cart' THEN user_id END) AS cart_users,
            COUNT(DISTINCT CASE WHEN behavior = 'fav'  THEN user_id END) AS fav_users,
            COUNT(DISTINCT CASE WHEN behavior = 'buy'  THEN user_id END) AS buy_users
        FROM dwd_user_behavior
    """
    df = pd.read_sql(sql, engine)
    print(df.to_string(index=False))

    stages = ['浏览 PV', '加购 Cart', '购买 Buy', '收藏 Fav']
    values = [df['pv_users'][0], df['cart_users'][0],
              df['buy_users'][0], df['fav_users'][0]]

    # 计算转化率
    rates = [100.0]
    for i in range(1, len(values)):
        rate = values[i] / values[0] * 100 if values[0] > 0 else 0
        rates.append(rate)

    step_rates = [100.0]
    for i in range(1, len(values)):
        rate = values[i] / values[i - 1] * 100 if values[i - 1] > 0 else 0
        step_rates.append(rate)

    plt.figure(14, figsize=(12, 6))
    # buy 用红色（重要转化点），fav 用黄色（post-buy 辅助行为）
    colors = ['#3498db', '#2ecc71', '#e74c3c', '#f39c12']
    bars = plt.barh(range(len(stages))[::-1], values, color=colors, alpha=0.8, height=0.6)
    plt.yticks(range(len(stages))[::-1], stages, fontsize=11)
    plt.xlabel('独立用户数', fontsize=12)
    plt.title('图14 用户级转化漏斗（去重）', fontsize=14, fontweight='bold', pad=15)
    plt.grid(axis='x', alpha=0.3)
    plt.xlim(0, max(values) * 1.18)  # 右侧留白18%，防止条末标注压到边框
    for i, (bar, val, overall, step) in enumerate(zip(bars, values, rates, step_rates)): 
        label = f'{val:,}人'
        if i > 0:
            label += f'\n总体{overall:.1f}% | 步骤{step:.1f}%'
        plt.text(bar.get_width() + 200, bar.get_y() + bar.get_height() / 2,
                 label, va='center', fontsize=10)
    plt.tight_layout()
    plt.savefig(f"{output_path}图14_用户级转化漏斗.png", dpi=300, bbox_inches='tight')
    plt.close()
    print("图14 已保存")


# ============================================================
# 汇总报告
# ============================================================
def save_rfm_report(engine):
    print("\n--- 生成 RFM 分析报告 ---")
    sql = """
        SELECT user_segment, COUNT(*) AS users,
               ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM ads_rfm_segments), 2) AS pct,
               ROUND(AVG(r_days), 1)   AS avg_r_days,
               ROUND(AVG(f_freq), 1)   AS avg_f_freq,
               ROUND(AVG(m_amount), 2) AS avg_m_amount
        FROM ads_rfm_segments
        GROUP BY user_segment
        ORDER BY avg_m_amount DESC
    """
    df = pd.read_sql(sql, engine)
    df.to_csv(f"{output_path}RFM分群报告.csv", index=False, encoding=OUTPUT_ENCODING)
    print("RFM 分群报告已保存")
    print(df.to_string(index=False))


def main():
    print("=" * 60)
    print("Phase 3: ADS 可视化 + 用户级漏斗分析")
    print("=" * 60)

    engine = get_engine()

    plot_rfm_distribution(engine)
    plot_rfm_means(engine)
    plot_occupation_cross(engine)
    plot_user_funnel(engine)
    save_rfm_report(engine)

    print("\n✅ Phase 3 可视化完成！")
    print(f"所有图表已保存至：{output_path}")


if __name__ == "__main__":
    main()
