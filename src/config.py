# # -*- coding: utf-8 -*-
# """配置文件：存储全局参数和路径"""
# import matplotlib.pyplot as plt
# import os

# # 图表配置
# plt.rcParams['font.sans-serif'] = ['SimHei']  # 中文支持
# plt.rcParams['axes.unicode_minus'] = False  # 负号显示
# plt.rcParams['figure.figsize'] = (12, 8)  # 图表默认大小
# plt.rcParams['font.size'] = 10  # 字体大小

# # 路径配置
# output_path = "电商用户行为分析结果/"
# # 自动创建输出目录（新增）
# os.makedirs(output_path, exist_ok=True)


# src/config.py
import os

import matplotlib.pyplot as plt

# 项目根目录（自动获取，无需手动修改）
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# 路径配置
DATA_PATH = os.path.join(ROOT_DIR, "data", "UserBehavior--1.csv")
OUTPUT_PATH = os.path.join(ROOT_DIR, "output", "")
DOCS_PATH = os.path.join(ROOT_DIR, "docs", "")

# 创建输出文件夹（不存在则自动创建）
os.makedirs(OUTPUT_PATH, exist_ok=True)

# 可视化参数（统一风格）
PLOT_CONFIG = {
    "dpi": 300,
    "bbox_inches": "tight",
    "font_family": "SimHei",  # 解决中文显示问题
    "fontsize": 11
}

# 全局应用中文字体（导入config即生效，所有绘图模块自动继承）
plt.rcParams["font.sans-serif"] = [PLOT_CONFIG["font_family"]]
plt.rcParams["axes.unicode_minus"] = False

# 建模参数（统一管理，方便调优）
MODEL_CONFIG = {
    "test_size": 0.3,
    "random_state": 42,
    "kmeans_n_clusters": 3,
    "lr_max_iter": 1000,
    "svm_max_iter": 5000
}

output_path = OUTPUT_PATH

# 输出文件统一编码（utf-8-sig 带 BOM：Excel 双击打开不乱码，pandas 通用）
OUTPUT_ENCODING = "utf-8-sig"