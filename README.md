# Simple-Implementation-Project-for-an-E-commerce-Data-Warehouse

电商数据仓库搭建与用户行为分析：76 万+ 条用户行为记录入仓，MySQL 五层分层（ODS→DIM→DWD→DWS→ADS），产出 RFM 用户分群、Power BI 交互看板与 1.45 万条评论的情感分析（120 条人工金标验证，负面精确率 92.3%），支撑精细化营销策略。

> 仓库名保留项目初期命名。实现已从"单表分析脚本"演进为分层数仓 + BI + NLP 流水线；旧版单表分析代码归档于 `src/legacy/`，旧版 README 归档于本地 `notes/legacy/`。

## 核心成果

数字口径以 [指标口径字典](notes/指标口径字典.md) 为唯一权威来源，关键指标全部经 Excel 交叉验证（差异 = 0）：

- **用户资产**：全体用户 10,739 / 购买用户 6,110 / 购买总额 1,805,829.50 元 / 客单价 295.55 元
- **RFM 八分群**：重要价值客户占购买用户 25.99%；锁定高 ROI 挽回群体"重要挽留客户"520 人（人均历史消费 309.18 元，约为一般挽留群体的 3.4 倍）
- **情感分析**：清洗后评论 14,552 条，负面占 39.5%；120 条三带人工金标（评估集 119 条）实测负面精确率 92.3%、加权召回 0.80、加权 F1 0.86（见 [复核表](notes/负面评论抽样复核表.xlsx)）
- **情感模型选型**：TF-IDF + 逻辑回归对照实验（McNemar 检验 + PR-AUC）支持**维持 SnowNLP 口径**——监督模型折外落后 10.6pp 且 p=0.109 不显著，避免为追新模型引入回归风险
- **策略交付**：[电商用户行为分析与精细化营销策略报告](docs/电商用户行为分析与精细化营销策略报告.md)

## 技术栈

- **数据仓库**：MySQL 8，五层分层建模，显式 DDL（CREATE TABLE + INSERT...SELECT）
- **ETL / 分析**：Python（pandas、SQLAlchemy + PyMySQL）
- **文本分析**：jieba 分词（电商领域自定义词典）+ SnowNLP 情感打分
- **可视化**：Power BI（DAX 度量值）、Matplotlib / Seaborn
- **机器学习 / 统计（对照实验已收官）**：scikit-learn（TF-IDF + 逻辑回归对照 SnowNLP，含数据泄漏修复与折外评估）、statsmodels（McNemar 配对检验）

## 项目结构

```
├── sql/                          # 数仓分层 DDL（按序执行）
│   ├── 01_create_dw.sql          # 建库 + ODS/DIM 表
│   ├── 02_build_dwd.sql          # DWD 明细清洗（只清洗，不聚合）
│   ├── 03_build_dws.sql          # DWS 轻度聚合（用户 × 日期）
│   └── 04_build_ads.sql          # ADS 应用层（RFM 分群）
├── src/
│   ├── config.py                 # 路径 / 绘图 / 编码全局配置
│   ├── db_loader.py              # CSV → ODS/DIM 入仓（含职业标签入口清洗）
│   ├── ads_visualizer.py         # 图11~14：RFM 分布 / 热力图 / 职业占比 / 转化漏斗
│   ├── sentiment_analyzer.py     # 图15~18：情感分布 / 高频词 / 品类负面率 / 分数直方图
│   ├── sentiment_sample.py       # 情感实验：120 条三带分层金标抽样（模板 + 打分缓存）
│   ├── sentiment_benchmark.py    # 情感实验：TF-IDF+LR 对照 SnowNLP（金标评估 + McNemar + PR-AUC）
│   ├── export_for_validation.py  # 导出核对宽表（Excel / Power BI 验证用）
│   └── legacy/                   # 旧版单表分析脚本（归档，不再维护）
├── docs/                         # 对外交付文档（策略报告）
├── notes/
│   ├── 指标口径字典.md            # 每个指标"怎么算"的唯一权威定义
│   ├── 负面评论抽样复核表.xlsx     # 情感模型人工复核记录
│   └── 标注表_120条_filled.xlsx   # 情感对照实验人工金标（120 条三带分层）
├── data/                         # 源数据 CSV（不入 git，见 data/README.md）
├── output/                       # 运行产出（图表 / CSV，不入 git）
├── requirements.txt
└── README.md
```

## 快速开始

### 1. 环境

```bash
conda create -n my_py39_env python=3.9
conda activate my_py39_env
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 2. 数据准备

将 4 个 CSV 放入 `data/`：

| 文件 | 内容 |
|---|---|
| `UserBehavior--1.csv` | 用户行为明细（约 76 万行） |
| `user_comments.csv` | 用户评论 |
| `category_mapping.csv` | 品类映射 |
| `user_face.csv` | 用户画像（职业标签） |

### 3. 建库与密码配置

1. MySQL Workbench 执行 `sql/01_create_dw.sql`
2. 配置数据库密码环境变量（避免密码硬编码进 git）：

```powershell
setx MYSQL_PASSWORD "你的密码"      # 永久生效，需新开终端
if($env:MYSQL_PASSWORD) {"已设置"}  # 新开终端后验证（不显示密码本身）
```

### 4. 流水线执行

```bash
python src/db_loader.py               # CSV → ODS/DIM 入仓
# MySQL Workbench 依次执行 02 → 03 → 04（DWD → DWS → ADS）
python src/ads_visualizer.py          # 图11~14
python src/sentiment_analyzer.py      # 图15~18 + 负面评论清单 + 20 条复核试点
python src/sentiment_sample.py        # 情感实验第一步：120 条金标标注模板 + 打分缓存
#    ↑ 人工标注：把模板另存为 notes/标注表_120条_filled.xlsx，填 gold 列（真负面/真中性/真正面/模糊）
python src/sentiment_benchmark.py     # 情感实验第二步：SnowNLP vs TF-IDF+LR（金标评估 + McNemar + PR-AUC + 决策线）
python src/export_for_validation.py   # 导出核对宽表
```

### 5. Power BI 看板

连接 MySQL `ecommerce_dw` 库，建模关系 `dim_user_profile (1) → (*) ads_rfm_segments`；KPI 与图表的 DAX 度量值口径逐条见 [指标口径字典](notes/指标口径字典.md)。

## 情感模型选型实验（已收官，2026-10-12）

预注册决策线：监督模型负面类加权 F1 提升 ≥ 5 个百分点且 McNemar 检验 p < 0.05，方建议更换现行口径。实验结果（120 条三带人工金标，剔除 1 条"模糊"后评估集 119 条）：

| 指标（负面类） | SnowNLP（基线） | TF-IDF+LR（主轨银标，已剔除金标防泄漏） |
|---|---|---|
| 精确率 P | **0.9231** | 0.8140 |
| 加权召回 R_w | **0.8049** | 0.7015 |
| 加权 F1_w | **0.8599** | 0.7536 |

McNemar 配对检验 p=0.109（n01=8 / n10=2），监督模型折外落后 10.64pp——未达决策线，**结论：维持 SnowNLP 阈值法**，现有口径在本数据规模下足够。实验产出：`output/sentiment_bench/`（对照结果、两法误判对照 20 条硬样本、PR 曲线）；实施细节见 `notes/项目日志_20261012.md`。
