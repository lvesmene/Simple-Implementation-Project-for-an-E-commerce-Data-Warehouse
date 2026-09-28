# -*- coding: utf-8 -*-
"""db_loader: Phase 2 数据导入——把 CSV 装入 MySQL 数仓 ODS/DIM 层

使用步骤：
    1. Workbench 中执行 sql/01_create_dw.sql 建库建表
    2. 安装依赖：pip install pymysql sqlalchemy -i https://pypi.tuna.tsinghua.edu.cn/simple
    3. 修改下方 DB_CONFIG 的密码（建议设置环境变量 MYSQL_PASSWORD，避免密码进 git）
    4. 运行：python src/db_loader.py                  # 全量导入 4 张表
              python src/db_loader.py dim_user_profile  # 只导指定表（可写多个）
"""
import os
import sys
import time

import re

import pandas as pd
from sqlalchemy import create_engine, text

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import ROOT_DIR, DATA_PATH

DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": os.environ.get("MYSQL_PASSWORD", "请改成你的密码"),
    "database": "ecommerce_dw",
    "charset": "utf8mb4",
}

CHUNK_SIZE = 50000  # 分块大小：内存友好 + 批量插入提速

def norm_face(value):
    """职业标签规范化：去首尾空白（含全角空格）+ 斜杠分隔符统一为无空格

    例：'上班族  ' → '上班族'；'农民 / 种植户' → '农民/种植户'
    注意：re.sub(pattern, repl, string) 的第二个参数是"替换成什么"，
         第三个参数才是被处理的字符串——只给两个参数会直接 TypeError。
    """
    if pd.isna(value):
        return value
    return re.sub(r"\s*/\s*", "/", str(value).strip())

# 四个数据源：ODS 大表走分块流式导入；DIM 小表整读 + 主键去重
DATA_SOURCES = [
    {
        "table": "ods_user_behavior",
        "path": DATA_PATH,
        "encoding": "gb18030",
        "dedup_keys": None,
        "dtype": {"timestamp": str},
    },
    {
        "table": "ods_comment",
        "path": os.path.join(ROOT_DIR, "data", "user_comments.csv"),
        "encoding": "utf-8-sig",
        "dedup_keys": None,
        "dtype": None,
    },
    {
        "table": "dim_category",
        "path": os.path.join(ROOT_DIR, "data", "category_mapping.csv"),
        "encoding": "utf-8-sig",
        "dedup_keys": ["category_id"],
        "dtype": None,
    },
    {
        "table": "dim_user_profile",
        "path": os.path.join(ROOT_DIR, "data", "user_face.csv"),
        "encoding": "utf-8-sig",
        "dedup_keys": ["user_id"],
        "dtype": None,
        "cleaners": {"face":norm_face},
    },
]

def get_engine():
    """创建 SQLAlchemy 引擎（pymysql 驱动）"""
    url = (
        f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
        f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
        f"?charset={DB_CONFIG['charset']}"
    )
    return create_engine(url)

def load_small_table(engine, source):
    """小表导入：整读 → 按 cleaners 规范化 → 主键去重 → 全量覆盖写入

    DIM 是"镜像源文件的查找表"，语义上是全量覆盖而不是追加：
    先清空目标表再写入，两步放在同一事务里（失败自动回滚，不会留下空表）。
    """
    df = pd.read_csv(source["path"], encoding=source["encoding"])
    for col, fn in (source.get("cleaners") or {}).items():
        n_before = df[col].nunique()          # 打印变化量，终端即可自证清洗生效
        df[col] = df[col].map(fn)
        print(f"  {col} 规范化：{n_before} → {df[col].nunique()} 个去重值")
    before = len(df)
    df = df.drop_duplicates(subset=source["dedup_keys"], keep="first")
    print(f"  主键去重：{before} → {len(df)} 行")

    with engine.begin() as conn:
        n_old = conn.execute(text(f"SELECT COUNT(*) FROM {source['table']}")).scalar()
        conn.execute(text(f"DELETE FROM {source['table']}"))
        df.to_sql(source["table"], conn, if_exists="append",
                  index=False, method="multi")
    print(f"  全量覆盖：清空原有 {n_old} 行 → 写入 {len(df)} 行")
    return len(df)

def load_big_table(engine, source):
    """大表导入：先清空 → 分块流式读取，逐块写入（76万行不撑爆内存）

    ODS 按设计不建主键，追加会"静默翻倍"（76万→152万且一句报错都没有），
    所以同样先清空。这里不复用 DIM 的单事务写法：76万行塞进一个事务会产生
    超大回滚段；拆开后万一中断，重跑一次即可——"清空+重写"本身就是幂等的。
    """
    with engine.begin() as conn:
        n_old = conn.execute(text(f"SELECT COUNT(*) FROM {source['table']}")).scalar()
        conn.execute(text(f"DELETE FROM {source['table']}"))
    print(f"  全量覆盖：清空原有 {n_old} 行")

    total = 0
    reader = pd.read_csv(  
        source["path"],
        encoding=source["encoding"],
        dtype=source["dtype"],
        chunksize=CHUNK_SIZE,
    )
    for chunk in reader:
        chunk.to_sql(source["table"], engine, if_exists="append",
                     index=False, method="multi", chunksize=CHUNK_SIZE)
        total += len(chunk)
        print(f"  已写入 {total} 行...")
    return total

def main():
    if DB_CONFIG["password"] in ("", "请改成你的密码"):
        sys.exit("请先修改 DB_CONFIG 中的密码，或设置环境变量 MYSQL_PASSWORD")
        
    # 可选: 只导入指定表.例: python src/db_loader.py dim_user_profile
    only = set(sys.argv[1:])
    sources = [s for s in DATA_SOURCES if not only or s["table"] in only]
    if only:
        print(f"仅导入: {[s['table'] for s in sources]}")

    print("=" * 60)
    print("Phase 2: CSV → MySQL 数仓导入开始")
    print("=" * 60)
    engine = get_engine()

    for source in sources:
        print(f"\n>>> {os.path.basename(source['path'])} → {source['table']}")
        start = time.time()
        if source["dedup_keys"]:
            n = load_small_table(engine, source)
        else:
            n = load_big_table(engine, source)
        elapsed = time.time() - start
        speed = n / elapsed if elapsed > 0 else 0
        print(f"  完成：{n} 行，耗时 {elapsed:.1f}s（{speed:.0f} 行/秒）")

    print("\n=== 行数核对（对账） ===")
    with engine.connect() as conn:
        for source in sources:
            n = conn.execute(text(f"SELECT COUNT(*) FROM {source['table']}")).scalar()
            print(f"  {source['table']}: {n} 行")

    print("\n✅ ODS/DIM 层导入完成！下一步：构建 DWD 明细层（02_build_dwd.sql）")

if __name__ == "__main__":
    main()