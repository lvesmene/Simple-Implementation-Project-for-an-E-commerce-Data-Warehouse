-- ============================================================
-- 02_build_dwd.sql — Phase 2 第二步：DWD 明细层清洗
-- 运行环境：MySQL 8.0.36，在 mysql 客户端用 SOURCE 执行
-- 执行方式：mysql -u root -p --default-character-set=utf8mb4
--          然后 SOURCE sql/02_build_dwd.sql;
-- ============================================================

USE ecommerce_dw;

-- ============================================================
-- Step 1: 数据质量审计（先看脏数据长什么样，再决定清洗策略）
-- 教学点：清洗前必须先探查，否则可能误删有效数据
-- ============================================================

-- 1.1 timestamp 列健康度盘点
SELECT
    COUNT(*) AS total_rows,
    SUM(CASE WHEN `timestamp` IS NULL OR `timestamp` = '' THEN 1 ELSE 0 END) AS null_or_empty,
    SUM(CASE WHEN `timestamp` REGEXP '^[0-9]+$' THEN 1 ELSE 0 END) AS pure_numeric,
    SUM(CASE WHEN `timestamp` REGEXP '^[0-9]+$' THEN 0 ELSE 1 END) AS non_numeric
FROM ods_user_behavior;

-- 1.2 看看非数字 timestamp 长什么样（抽样）
SELECT `timestamp`, COUNT(*) AS cnt
FROM ods_user_behavior
WHERE `timestamp` NOT REGEXP '^[0-9]+$'
   OR `timestamp` IS NULL
GROUP BY `timestamp`
ORDER BY cnt DESC
LIMIT 20;

-- 1.3 behavior 取值分布（确认只有 pv/cart/fav/buy 四种合法值）
SELECT behavior, COUNT(*) AS cnt
FROM ods_user_behavior
GROUP BY behavior
ORDER BY cnt DESC;

-- 1.4 各行为的 price/amount 填充情况（验证业务逻辑：非 buy 行不该有金额）
SELECT behavior,
       SUM(CASE WHEN price > 0 THEN 1 ELSE 0 END) AS has_price,
       SUM(CASE WHEN amount > 0 THEN 1 ELSE 0 END) AS has_amount
FROM ods_user_behavior
GROUP BY behavior;

-- ============================================================
-- Step 2: 建 DWD 表（显式 DDL，带主键和索引）
-- 教学点：不用 CTAS，因为 CTAS 无法建索引/设 COMMENT/控类型
-- ============================================================

DROP TABLE IF EXISTS dwd_user_behavior;
CREATE TABLE dwd_user_behavior (
    id           BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '自增代理键',
    user_id      BIGINT        NOT NULL COMMENT '用户ID',
    goods_id     BIGINT        NOT NULL COMMENT '商品ID',
    category_id  BIGINT        NOT NULL COMMENT '品类ID',
    behavior     VARCHAR(10)   NOT NULL COMMENT '行为类型: pv/cart/fav/buy',
    event_time   DATETIME      NOT NULL COMMENT '行为发生时间(由时间戳派生)',
    event_date   DATE          NOT NULL COMMENT '日期(派生,用于按天聚合)',
    event_hour   TINYINT       NOT NULL COMMENT '小时0-23(派生,用于时段分析)',
    sex          TINYINT       NULL     COMMENT '性别: 0/1',
    address      VARCHAR(50)   NULL     COMMENT '城市',
    device       VARCHAR(50)   NULL     COMMENT '设备型号',
    price        DECIMAL(12,2) NULL     COMMENT '商品价格',
    amount       INT           NULL     COMMENT '购买数量',
    INDEX idx_user      (user_id),
    INDEX idx_time      (event_time),
    INDEX idx_date      (event_date),
    INDEX idx_cate      (category_id),
    INDEX idx_beh_time  (behavior, event_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
  COMMENT='DWD: 用户行为明细(清洗后,带派生时间字段)';

-- ============================================================
-- Step 3: 清洗装载（INSERT...SELECT）
-- 教学点：
--   a. WHERE 用 REGEXP '^[0-9]+$' 只放行纯数字时间戳
--   b. FROM_UNIXTIME + CAST 把字符串转 Unix 秒再转 datetime
--   c. behavior IN (...) 防御性过滤未知行为类型
--   d. 同一个 CAST 出现3次,MySQL 8 会复用,不必担心性能
-- ============================================================

INSERT INTO dwd_user_behavior (
    user_id, goods_id, category_id, behavior,
    event_time, event_date, event_hour,
    sex, address, device, price, amount
)
SELECT
    user_id,
    goods_id,
    category_id,
    behavior,
    FROM_UNIXTIME(CAST(`timestamp` AS UNSIGNED)) AS event_time,
    DATE(FROM_UNIXTIME(CAST(`timestamp` AS UNSIGNED))) AS event_date,
    HOUR(FROM_UNIXTIME(CAST(`timestamp` AS UNSIGNED))) AS event_hour,
    sex, address, device, price, amount
FROM ods_user_behavior
WHERE `timestamp` REGEXP '^[0-9]+$'
  AND behavior IN ('pv', 'cart', 'fav', 'buy');

-- ============================================================
-- Step 4: 验证（对账闭环）
-- ============================================================

-- 4.1 行数对账：ODS → DWD 流失了多少
SELECT 'ODS原始' AS layer, COUNT(*) AS rows_cnt FROM ods_user_behavior
UNION ALL
SELECT 'DWD清洗后', COUNT(*) FROM dwd_user_behavior
UNION ALL
SELECT '被过滤行数',
       (SELECT COUNT(*) FROM ods_user_behavior) -
       (SELECT COUNT(*) FROM dwd_user_behavior);

-- 4.2 时间范围（确认数据覆盖哪几天——之前推断是 7 天）
SELECT MIN(event_date) AS start_date,
       MAX(event_date) AS end_date,
       COUNT(DISTINCT event_date) AS days
FROM dwd_user_behavior;

-- 4.3 行为分布（与 ODS 对比，确认过滤合理）
SELECT behavior, COUNT(*) AS cnt
FROM dwd_user_behavior
GROUP BY behavior
ORDER BY cnt DESC;

-- 4.4 抽样检查时间转换是否正确
SELECT user_id, behavior, event_time, event_date, event_hour, address
FROM dwd_user_behavior
ORDER BY id DESC
LIMIT 10;