# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r"e:\aPythontest\Simple-Implementation-Project-for-an-E-commerce-Data-Warehouse\src")
from db_loader import get_engine
import pandas as pd

eng = get_engine()

# 1) 合并候选：清洗后会坍缩的职业对
sql_pairs = """
SELECT face, COUNT(*) AS users,
       TRIM(REPLACE(REPLACE(face, ' ', ''), '　', '')) AS cleaned
FROM dim_user_profile
GROUP BY face
HAVING cleaned IN (
    SELECT cleaned FROM (
        SELECT TRIM(REPLACE(REPLACE(face, ' ', ''), '　', '')) AS cleaned
        FROM dim_user_profile GROUP BY cleaned HAVING COUNT(DISTINCT face) > 1
    ) t
)
ORDER BY cleaned
"""
print("== 清洗后会合并的职业 ==")
print(pd.read_sql(sql_pairs, eng).to_string(index=False))

# 2) 清洗后 >=100 人的职业数（图13 行数会不会变）
sql_having = """
SELECT COUNT(*) AS n FROM (
    SELECT TRIM(REPLACE(REPLACE(face, ' ', ''), '　', '')) AS cleaned, COUNT(*) AS c
    FROM dim_user_profile GROUP BY cleaned HAVING c >= 100
) t
"""
print("\n== 清洗后 >=100 人的职业数（期望 9） ==")
print(pd.read_sql(sql_having, eng).to_string(index=False))

# 3) 清洗前后总行数 / 非空数
sql_cnt = """
SELECT COUNT(*) AS total,
       SUM(face IS NOT NULL AND TRIM(face) <> '') AS non_empty
FROM dim_user_profile
"""
print("\n== 总行数与非空 face（期望 10739 / 10739） ==")
print(pd.read_sql(sql_cnt, eng).to_string(index=False))
