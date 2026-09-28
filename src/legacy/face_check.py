# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r"e:\aPythontest\Simple-Implementation-Project-for-an-E-commerce-Data-Warehouse\src")
from db_loader import get_engine
import pandas as pd

sql = """
SELECT DISTINCT face, CHAR_LENGTH(face) AS len
FROM dim_user_profile
WHERE face LIKE '%% %%' OR face LIKE '%%　%%'
   OR face LIKE '%%、%%' OR face LIKE '%%／%%' OR face LIKE '%%-%%'
   OR face REGEXP '[a-zA-Z]'
ORDER BY face
"""
df = pd.read_sql(sql, get_engine())
print(df.to_string(index=False))
print("命中行数:", len(df))

# 全量职业去重后按空格前后对比预览清洗效果
sql2 = """
SELECT
  COUNT(DISTINCT face) AS raw_cnt,
  COUNT(DISTINCT TRIM(REPLACE(REPLACE(face, ' ', ''), '　', ''))) AS cleaned_cnt
FROM dim_user_profile
"""
print(pd.read_sql(sql2, get_engine()).to_string(index=False))
