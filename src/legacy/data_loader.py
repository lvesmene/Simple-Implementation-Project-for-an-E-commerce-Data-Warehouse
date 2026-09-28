# -*- coding: utf-8 -*-
"""数据读取模块"""
import pandas as pd

def load_data(data_path):
    """读取电商用户行为数据，返回DataFrame"""
    print("="*60)
    print("1. 数据读取开始")
    print("="*60)
    # 读取数据
    df = pd.read_csv(data_path, encoding='gb18030', low_memory=False)
    # 数据基础信息输出
    print(f"数据规模：{df.shape[0]} 条记录 × {df.shape[1]} 个字段")
    print(f"字段列表：{', '.join(df.columns)}")
    print(f"数据前5行预览：")
    print(df.head())
    print(f"数据类型：")
    print(df.dtypes)
    return df

# 单独运行时的测试代码
if __name__ == "__main__":
    DATA_PATH = "UserBehavior--1.csv"  # 替换为实际路径
    df = load_data(DATA_PATH)