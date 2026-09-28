-- ============================================================
-- 03_build_dws.sql — Phase 2 第三步：DWS 轻度汇总层
-- 职责：按 用户×天 聚合，每人每天一行
-- 教学点：行转列 pivot 模式 + 自然复合主键 + GROUP BY
-- 执行：mysql -u root -p --default-character-set=utf8mb4
--      SOURCE sql/03_build_dws.sql;
-- ============================================================

USE ecommerce_dw;

DROP TABLE IF EXISTS dws_user_day;
CREATE TABLE dws_user_day (
    user_id      BIGINT       NOT NULL COMMENT '用户ID',
    event_date   DATE        NOT NULL COMMENT '日期',
    pv_cnt       INT          NOT NULL DEFAULT 0 COMMENT '当日浏览次数',
    cart_cnt     INT          NOT NULL DEFAULT 0 COMMENT '当日加购次数',
    fav_cnt      INT          NOT NULL DEFAULT 0 COMMENT '当日收藏次数',
    buy_cnt      INT          NOT NULL DEFAULT 0 COMMENT '当日购买次数',
    buy_amount   DECIMAL(14,2) NOT NULL DEFAULT 0 COMMENT '当日购买总额(price*amount)',
    is_active    TINYINT      NOT NULL DEFAULT 1 COMMENT '是否活跃(必有行为才进表)',
    is_buyer    TINYINT      NOT NULL DEFAULT 0 COMMENT '当日是否购买',
    PRIMARY KEY (user_id, event_date),
    INDEX idx_date_active (event_date, is_active),
    INDEX idx_buyer       (is_buyer)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
  COMMENT='DWS: 用户日度行为汇总(每人每天一行)';

-- ============================================================
-- 装载：GROUP BY 用户×天，行转列统计各行为次数
-- 教学点：SUM(CASE WHEN...) 是 SQL 行转列的经典 pivot 模式
-- ============================================================
INSERT INTO dws_user_day (
    user_id, event_date,
    pv_cnt, cart_cnt, fav_cnt, buy_cnt,
    buy_amount, is_active, is_buyer
)
SELECT
    user_id,
    event_date,
    SUM(CASE WHEN behavior = 'pv'   THEN 1 ELSE 0 END) AS pv_cnt,
    SUM(CASE WHEN behavior = 'cart' THEN 1 ELSE 0 END) AS cart_cnt,
    SUM(CASE WHEN behavior = 'fav'  THEN 1 ELSE 0 END) AS fav_cnt,
    SUM(CASE WHEN behavior = 'buy'  THEN 1 ELSE 0 END) AS buy_cnt,
    COALESCE(SUM(CASE WHEN behavior = 'buy' THEN price * amount ELSE 0 END), 0) AS buy_amount,
    1 AS is_active,
    CASE WHEN SUM(CASE WHEN behavior = 'buy' THEN 1 ELSE 0 END) > 0 THEN 1 ELSE 0 END AS is_buyer
FROM dwd_user_behavior
GROUP BY user_id, event_date;

-- ============================================================
-- 验证
-- ============================================================

-- 1. 行数：DWS 应远小于 DWD（每人每天一行 vs 每行为一行）
SELECT 'DWD明细' AS layer, COUNT(*) AS rows_cnt FROM dwd_user_behavior
UNION ALL
SELECT 'DWS汇总', COUNT(*) FROM dws_user_day
UNION ALL
SELECT '独立用户数', COUNT(DISTINCT user_id) FROM dws_user_day;

-- 2. 行为总数对账：DWS 横向求和应等于 DWD 纵向 COUNT
SELECT
    SUM(pv_cnt)   AS total_pv,
    SUM(cart_cnt) AS total_cart,
    SUM(fav_cnt)  AS total_fav,
    SUM(buy_cnt)  AS total_buy,
    SUM(buy_amount) AS total_gmv
FROM dws_user_day;
-- 预期：pv≈679668, cart=42714, fav=20601, buy=14582（与 DWD 完全一致）

-- 3. 日活 DAU 趋势（7 天）
SELECT
    event_date,
    COUNT(*) AS dau,
    SUM(is_buyer) AS buyers,
    ROUND(SUM(is_buyer) / COUNT(*) * 100, 2) AS buy_rate_pct
FROM dws_user_day
GROUP BY event_date
ORDER BY event_date;

-- 4. 抽样：查看某用户 7 天行为画像
SELECT * FROM dws_user_day
WHERE user_id = 9998
ORDER BY event_date;