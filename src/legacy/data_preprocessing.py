# -*- coding: utf-8 -*-
"""数据预处理模块"""
import pandas as pd
from config import output_path, OUTPUT_ENCODING

def data_preprocessing(df):
    """数据清洗+特征工程，生成建模用数据"""
    print("\n" + "="*60)
    print("3. 数据预处理开始")
    print("="*60)
    original_rows = df.shape[0]
    
    # 1. 缺失值处理
    print("=== 缺失值处理 ===")
    core_cols = ['user_id', 'goods_id', 'behavior', 'timestamp']
    df = df.dropna(subset=core_cols)
    # 补充缺失值策略优化
    df['sex'] = df['sex'].fillna(df['sex'].mode()[0] if not df['sex'].mode().empty else 0)  # 用众数更合理
    df['price'] = df['price'].fillna(0)  # 保留0值（按实际情况）
    df['amount'] = df['amount'].fillna(0)
    df['address'] = df['address'].fillna('未知')
    df['device'] = df['device'].fillna('未知')
    df['comment'] = df['comment'].fillna('无评论')
    print(f"缺失值处理后：{df.shape[0]} 条记录（删除 {original_rows - df.shape[0]} 条核心字段缺失记录）")
    
    # 2. 重复值处理
    print("=== 重复值处理 ===")
    before_dup = df.shape[0]
    df = df.drop_duplicates()
    df = df.drop_duplicates(subset=['user_id', 'goods_id', 'behavior', 'timestamp'])  # 复合主键去重
    print(f"重复值处理后：{df.shape[0]} 条记录（删除 {before_dup - df.shape[0]} 条重复记录）")
    
    # 3. 异常值处理（保留价格0值，仅处理极端异常）
    print("=== 异常值处理 ===")
    price_99 = df['price'].quantile(0.99)
    df.loc[df['price'] > price_99, 'price'] = price_99  # 仅截断极端高价
    df.loc[df['amount'] > 100, 'amount'] = 100  # 数量上限
    df.loc[df['amount'] < 0, 'amount'] = 0  # 数量下限
    print(f"异常值处理完成（价格99分位数：{price_99:.2f}）")
    
    # 4. 特征工程（修正数据泄露）
    print("=== 特征工程 ===")
    
    # 新增特征1：用户对同一商品的浏览次数
    df['user_goods_count'] = df.groupby(['user_id', 'goods_id']).cumcount() + 1
    
    # 新增特征2：标记热门分类（基于探索性分析的热门分类）
    hot_categories = [4756105, 4145813, 2355072]  # 热门分类ID
    df['is_hot_category'] = df['category_id'].apply(lambda x: 1 if x in hot_categories else 0)
    
    # 用户行为特征（避免未来信息泄露）
    user_features = df.groupby('user_id').agg({
        'behavior': 'count',  # 总行为次数
        'goods_id': 'nunique'  # 浏览商品种类
    }).rename(columns={
        'behavior': 'total_behavior_count',
        'goods_id': 'browse_goods_types'
    }).reset_index()
    # 移除直接泄露标签的buy_count特征，避免数据泄露
    
    # 商品特征（不使用price相关信息，避免数据泄露）
    goods_features = df.groupby('goods_id').agg({
        'behavior': 'count'  # 商品热度
    }).rename(columns={
        'behavior': 'goods_hot_score'
    }).reset_index()
    
    # 时间特征（修正高峰时段定义，与探索性分析一致）
    df['weekday'] = df['behavior_time'].dt.weekday
    # 重新计算小时分布以获取高峰时段
    hour_dist = df['hour'].value_counts().sort_index()
    peak_hours = [hour_dist.idxmax()]  # 使用数据中实际的高峰时段
    df['is_peak_hour'] = df['hour'].apply(lambda x: 1 if x in peak_hours else 0)
    df['is_weekend'] = df['weekday'].apply(lambda x: 1 if x >=5 else 0)
    # 合并特征
    df = df.merge(user_features, on='user_id', how='left')
    df = df.merge(goods_features, on='goods_id', how='left')
    
    # 标签定义
    df['label'] = (df['behavior'] == 'buy').astype(int)
    
    print(f"特征工程完成，最终字段数：{df.shape[1]}")
    print(f"新增特征：{', '.join(['user_goods_count', 'is_hot_category', 'total_behavior_count', 'browse_goods_types', 'goods_hot_score', 'is_peak_hour', 'is_weekend'])}")
    
    # 保存预处理后的数据
    df.to_csv(f"{output_path}预处理后的数据.csv", index=False, encoding=OUTPUT_ENCODING)
    print(f"预处理后的数据已保存至：{output_path}预处理后的数据.csv")
    
    return df

if __name__ == "__main__":
    from data_loader import load_data
    from exploratory_analysis import exploratory_analysis
    DATA_PATH = "UserBehavior--1.csv"
    df = load_data(DATA_PATH)
    df = exploratory_analysis(df)
    df = data_preprocessing(df)