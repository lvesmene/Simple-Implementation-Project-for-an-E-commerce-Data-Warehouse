# -*- coding: utf-8 -*-
"""建模分析模块（修复模型评估异常）"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC  # 替换SVR为SVC（分类模型）
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, precision_recall_curve
from sklearn.cluster import KMeans
from config import output_path, OUTPUT_ENCODING

def modeling_analysis(df):
    """构建分类模型和聚类模型（修复评估指标异常）"""
    print("\n" + "="*60)
    print("4. 数据分析与建模开始")
    print("="*60)
    
    # 1. 数据准备
    features = [
        'sex', 'browse_goods_types', 'total_behavior_count',
        'goods_hot_score', 'is_peak_hour', 'is_weekend',
        'user_goods_count', 'is_hot_category'  # 新增特征
    ]
    X = df[features].copy()
    y = df['label']
    
    # 处理特征中的缺失值（新增）
    X = X.fillna(0)
    
    # 数据标准化
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # 数据分割（分层抽样保持分布）
    X_train_full, X_test, y_train_full, y_test = train_test_split(
        X_scaled, y, test_size=0.3, random_state=42, stratify=y
    )
    
    # SVM抽样训练（解决样本不均衡）
    sample_ratio = 0.1 if len(X_train_full) > 100000 else 0.3
    sample_size = int(len(X_train_full) * sample_ratio)
    sample_size = min(sample_size, len(X_train_full))
    X_train_svm, _, y_train_svm, _ = train_test_split(
        X_train_full, y_train_full, 
        train_size=sample_size, 
        random_state=42, 
        stratify=y_train_full
    )
    
    print(f"训练集规模：{X_train_full.shape[0]} 条，测试集规模：{X_test.shape[0]} 条")
    print(f"SVM抽样训练集规模：{X_train_svm.shape[0]} 条（原训练集的{sample_ratio*100:.0f}%）")
    print(f"正样本占比（购买行为）：{y.mean():.2%}")  # 修正为百分比显示
    
    # 2. 逻辑回归模型（添加class_weight解决不均衡）
    print("=== 逻辑回归模型训练 ===")
    lr_model = LogisticRegression(
        max_iter=1000, 
        random_state=42,
        class_weight='balanced',  # 平衡正负样本权重
        penalty='l2',  # 添加L2正则化
        C=1.0  # 正则化强度
    )
    lr_model.fit(X_train_full, y_train_full)
    
    lr_pred = lr_model.predict(X_test)
    lr_pred_prob = lr_model.predict_proba(X_test)[:, 1]
    
    # 修正评估指标计算（处理极端情况）
    lr_metrics = {
        '准确率': accuracy_score(y_test, lr_pred),
        '精确率': precision_score(y_test, lr_pred, zero_division=1),  # 避免0除错误
        '召回率': recall_score(y_test, lr_pred, zero_division=0),
        'F1分数': f1_score(y_test, lr_pred, zero_division=0),
        'AUC分数': roc_auc_score(y_test, lr_pred_prob) if len(np.unique(y_test)) > 1 else 0.5
    }
    print("逻辑回归模型评估指标：")
    for key, value in lr_metrics.items():
        print(f"  {key}：{value:.4f}")
    
    # 3. SVM模型（替换为分类模型SVC）
    print("=== SVM模型训练 ===")
    svm_model = SVC(
        kernel='linear',
        C=1.0,
        probability=True,  # 启用概率预测
        class_weight='balanced',  # 平衡权重
        max_iter=5000,
        random_state=42
    )
    svm_model.fit(X_train_svm, y_train_svm)

    svm_pred = svm_model.predict(X_test)
    svm_pred_prob = svm_model.predict_proba(X_test)[:, 1]  # 概率值用于AUC
    
    svm_metrics = {
        '准确率': accuracy_score(y_test, svm_pred),
        '精确率': precision_score(y_test, svm_pred, zero_division=1),
        '召回率': recall_score(y_test, svm_pred, zero_division=0),
        'F1分数': f1_score(y_test, svm_pred, zero_division=0),
        'AUC分数': roc_auc_score(y_test, svm_pred_prob) if len(np.unique(y_test)) > 1 else 0.5
    }  
    print("SVM模型评估指标：")
    for key, value in svm_metrics.items():
        print(f"  {key}：{value:.4f}")
    
    # 4. K-Means聚类（优化聚类数量）
    print("=== K-Means用户分群 ===")
    kmeans = KMeans(n_clusters=3, random_state=42)
    df['user_cluster'] = kmeans.fit_predict(X_scaled)
    cluster_count = df['user_cluster'].value_counts().sort_index()
    print("用户分群结果：")
    for cluster, count in cluster_count.items():
        cluster_buy_rate = df[df['user_cluster'] == cluster]['label'].mean()
        print(f"  集群{cluster}：{count} 人，购买转化率：{cluster_buy_rate:.2%}")  # 修正为百分比
    
    # 5. 逻辑回归交叉验证（新增）
    print("=== 逻辑回归交叉验证 ===")
    from sklearn.model_selection import cross_val_score
    cv_scores = {
        '准确率': cross_val_score(lr_model, X_scaled, y, cv=5, scoring='accuracy'),
        '精确率': cross_val_score(lr_model, X_scaled, y, cv=5, scoring='precision'),
        '召回率': cross_val_score(lr_model, X_scaled, y, cv=5, scoring='recall'),
        'F1分数': cross_val_score(lr_model, X_scaled, y, cv=5, scoring='f1'),
    }
    
    print("交叉验证平均指标：")
    cv_mean_scores = {}
    for metric, scores in cv_scores.items():
        cv_mean_scores[metric] = scores.mean()
        print(f"  {metric}：{cv_mean_scores[metric]:.4f}（±{scores.std():.4f}）")
    
    # 6. 模型可视化
    models = ['逻辑回归', 'SVM']
    metrics = ['准确率', '精确率', '召回率', 'F1分数', 'AUC分数']
    lr_scores = [lr_metrics[metric] for metric in metrics]
    svm_scores = [svm_metrics[metric] for metric in metrics]
    
    x = np.arange(len(metrics))
    width = 0.35
    
    plt.figure(6, figsize=(12, 6))  # 修正图表编号
    plt.bar(x - width/2, lr_scores, width, label='逻辑回归', color='#FF6B6B', alpha=0.7)
    plt.bar(x + width/2, svm_scores, width, label='SVM', color='#4ECDC4', alpha=0.7)
    plt.xlabel('评估指标', fontsize=12)
    plt.ylabel('分数', fontsize=12)
    plt.title('图6 模型性能对比', fontsize=14, fontweight='bold', pad=20)
    plt.xticks(x, metrics, rotation=45)
    plt.legend()
    plt.grid(axis='y', alpha=0.3)
    plt.ylim(0, 1.05)  # 设置y轴范围，更直观展示差异
    plt.tight_layout()
    plt.savefig(f"{output_path}图6_模型性能对比.png", dpi=300, bbox_inches='tight')
    plt.close()
    print("图6：模型性能对比柱状图已保存")
    
    # 特征重要性
    feature_importance = pd.DataFrame({
        '特征': features,
        '重要性': np.abs(lr_model.coef_[0])
    }).sort_values('重要性', ascending=False)
    
    plt.figure(7, figsize=(12, 6))
    plt.barh(feature_importance['特征'], feature_importance['重要性'], color='#45B7D1', alpha=0.7)
    plt.xlabel('重要性系数', fontsize=12)
    plt.ylabel('特征名称', fontsize=12)
    plt.title('图7 特征重要性排名（逻辑回归）', fontsize=14, fontweight='bold', pad=20)
    plt.grid(axis='x', alpha=0.3)
    plt.tight_layout()
    plt.savefig(f"{output_path}图7_特征重要性排名.png", dpi=300, bbox_inches='tight')
    plt.close()
    print("图7：特征重要性排名图已保存")
    
    # 用户分群转化率对比
    cluster_buy_rate = df.groupby('user_cluster')['label'].mean()
    plt.figure(8, figsize=(8, 6))
    cluster_buy_rate.plot(kind='bar', color='#96CEB4', alpha=0.7)
    plt.xlabel('用户集群', fontsize=12)
    plt.ylabel('购买转化率', fontsize=12)
    plt.title('图8 各集群用户购买转化率对比', fontsize=14, fontweight='bold', pad=20)
    plt.xticks(rotation=0)
    plt.grid(axis='y', alpha=0.3)
    for i, v in enumerate(cluster_buy_rate):
        plt.text(i, v + 0.001, f'{v:.2%}', ha='center', fontweight='bold')
    plt.tight_layout()
    plt.savefig(f"{output_path}图8_用户分群转化率对比.png", dpi=300, bbox_inches='tight')
    plt.close()
    print("图8：用户分群转化率对比图已保存")
    
    # 新增：PR曲线绘制（精确率-召回率曲线）
    print("=== PR曲线绘制 ===")
    plt.figure(9, figsize=(10, 6))  # 使用新的图表编号
    
    # 逻辑回归PR曲线
    precision_lr, recall_lr, _ = precision_recall_curve(y_test, lr_pred_prob)
    plt.plot(recall_lr, precision_lr, color='#FF6B6B', label='逻辑回归', linewidth=2, alpha=0.8)
    
    # SVM PR曲线
    precision_svm, recall_svm, _ = precision_recall_curve(y_test, svm_pred_prob)
    plt.plot(recall_svm, precision_svm, color='#4ECDC4', label='SVM', linewidth=2, alpha=0.8)
    
    plt.xlabel('召回率', fontsize=12)
    plt.ylabel('精确率', fontsize=12)
    plt.title('图9 精确率-召回率曲线（PR曲线）', fontsize=14, fontweight='bold', pad=20)
    plt.grid(axis='both', alpha=0.3)
    plt.legend(fontsize=11)
    plt.tight_layout()
    plt.savefig(f"{output_path}图9_PR曲线.png", dpi=300, bbox_inches='tight')
    plt.close()
    print("图9：PR曲线已保存")
    
    # 保存模型评估报告
    metrics_df = pd.DataFrame({
        '评估指标': metrics,
        '逻辑回归': lr_scores,
        'SVM': svm_scores
    })
    # 添加交叉验证结果
    cv_metrics = list(cv_mean_scores.keys())
    cv_mean_values = [cv_mean_scores[metric] for metric in cv_metrics]
    cv_metrics_df = pd.DataFrame({
        '评估指标': cv_metrics,
        '逻辑回归交叉验证': cv_mean_values
    })
    metrics_df = pd.merge(metrics_df, cv_metrics_df, on='评估指标', how='left')
    metrics_df.to_csv(f"{output_path}模型评估报告.csv", index=False, encoding=OUTPUT_ENCODING)
    print(f"模型评估报告已保存")
    
    return df, lr_model, svm_model, kmeans

if __name__ == "__main__":
    from data_loader import load_data
    from exploratory_analysis import exploratory_analysis
    from data_preprocessing import data_preprocessing
    DATA_PATH = "UserBehavior--1.csv"
    df = load_data(DATA_PATH)
    df = exploratory_analysis(df)
    df = data_preprocessing(df)
    df, _, _, _ = modeling_analysis(df)