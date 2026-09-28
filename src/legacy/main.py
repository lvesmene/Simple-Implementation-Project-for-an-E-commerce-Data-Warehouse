# -*- coding: utf-8 -*-
"""主程序：一键运行全流程分析"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from data_loader import load_data
from exploratory_analysis import exploratory_analysis
from data_preprocessing import data_preprocessing
from modeling import modeling_analysis
from result_analysis import predict_analysis
from config import output_path, DATA_PATH

def main(data_path):
    """主函数：调用所有模块，完成全流程分析"""
    # 1. 数据读取
    df = load_data(data_path)
    
    # 2. 数据探索性分析
    df = exploratory_analysis(df)
    
    # 3. 数据预处理
    df = data_preprocessing(df)
    
    # 4. 数据分析与建模
    df, lr_model, svm_model, kmeans = modeling_analysis(df)
    
    # 5. 预测与结果分析
    predict_analysis(df)
    
    print("\n" + "="*60)
    print("电商用户行为大数据分析全流程完成！")
    print(f"所有结果已保存至：{output_path}")
    print("包含以下内容：")
    print("1. 基础统计分析报告.csv")
    print("2. 预处理后的数据.csv")
    print("3. 模型评估报告.csv")
    print("4. 结果分析与策略建议.txt")
    print("5. 10张标准化图表（图1-图10）")  # 修正图表数量
    print("="*60)

if __name__ == "__main__":
    main(DATA_PATH)