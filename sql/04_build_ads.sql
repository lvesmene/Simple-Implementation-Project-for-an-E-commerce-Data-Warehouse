-- ============================================================
-- 04_build_ads.sql — Phase 2 第四步：ADS 应用层（RFM 分层）
-- 职责：用户级 RFM 打分 + 8 类分群（每人一行）
-- 教学点：CTE + NTILE 窗口函数 + CASE WHEN 组合分群
-- 执行：mysql -u root -p --default-character-set=utf8mb4
--      SOURCE sql/04_build_ads.sql;
-- ============================================================

USE ecommerce_dw;

-- ============================================================
-- Step 0: 探查 - 购买用户规模（确认分群样本量）
-- 教学点：RFM 只对有购买行为的用户打分,无购买用户直接排除
-- ============================================================
SELECT
    COUNT(DISTINCT user_id) AS total_users,
    SUM(CASE WHEN is_buyer = 1 THEN 1 ELSE 0 END) AS buyer_user_days,
    COUNT(DISTINCT CASE WHEN is_buyer = 1 THEN user_id END) AS distinct_buyers
FROM dws_user_day;

-- ============================================================
-- Step 1: 建表
-- ============================================================
DROP TABLE IF EXISTS ads_rfm_segments;
CREATE TABLE ads_rfm_segments (
    user_id      BIGINT        NOT NULL PRIMARY KEY COMMENT '用户ID',
    r_days       INT           NOT NULL COMMENT 'R: 最近购买距今天数',
    f_freq       INT           NOT NULL COMMENT 'F: 购买总次数',
    m_amount     DECIMAL(14,2) NOT NULL COMMENT 'M: 购买总金额',
    r_score      TINYINT       NOT NULL COMMENT 'R分(1-4,4=最近)',
    f_score      TINYINT       NOT NULL COMMENT 'F分(1-4,4=最频)',
    m_score      TINYINT       NOT NULL COMMENT 'M分(1-4,4=最高)',
    user_segment VARCHAR(20)   NOT NULL COMMENT 'RFM八类分群标签',
    INDEX idx_segment (user_segment)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
  COMMENT='ADS: 用户RFM分群(每人一行)';

-- ============================================================
-- Step 2: CTE 计算 R/F/M 原始值 → 窗口函数打分 → 分群
-- 教学点：
--   a. CTE 链式：user_rfm → rfm_scored，按思维顺序写
--   b. NTILE(4) 把用户等分4档，返回1-4
--   c. 风格A: 让 score=4 表示"维度好"(直觉友好):
--      r_days DESC  → 最远购买得到1(R差), 最近购买得到4(R好)
--      f_freq ASC   → 最少频次得到1(F差), 最频繁得到4(F好)
--      m_amount ASC → 最低金额得到1(M差), 最高金额得到4(M好)
--      因此"高R/F/M" → score>=3, "低" → score<=2
--   d. HAVING f_freq > 0 只保留购买用户
-- ============================================================
INSERT INTO ads_rfm_segments (
    user_id, r_days, f_freq, m_amount, r_score, f_score, m_score, user_segment
)
WITH user_rfm AS (
    SELECT
        user_id,
        -- R: 用数据集末日 2024-06-04 作基准日,距今多少天
        DATEDIFF('2024-06-04', MAX(CASE WHEN is_buyer = 1 THEN event_date END)) AS r_days,
        -- F: 7天内的购买总次数
        SUM(buy_cnt) AS f_freq,
        -- M: 7天内的购买总金额
        SUM(buy_amount) AS m_amount
    FROM dws_user_day
    GROUP BY user_id
    HAVING f_freq > 0
),
rfm_scored AS (
    SELECT
        user_id, r_days, f_freq, m_amount,
        NTILE(4) OVER (ORDER BY r_days DESC)  AS r_score,
        NTILE(4) OVER (ORDER BY f_freq ASC)   AS f_score,
        NTILE(4) OVER (ORDER BY m_amount ASC) AS m_score
    FROM user_rfm
)
SELECT
    user_id, r_days, f_freq, m_amount, r_score, f_score, m_score,
    CASE
        WHEN r_score >= 3 AND f_score >= 3 AND m_score >= 3 THEN '重要价值客户'
        WHEN r_score >= 3 AND f_score <= 2 AND m_score >= 3 THEN '重要发展客户'
        WHEN r_score <= 2 AND f_score >= 3 AND m_score >= 3 THEN '重要保持客户'
        WHEN r_score <= 2 AND f_score <= 2 AND m_score >= 3 THEN '重要挽留客户'
        WHEN r_score >= 3 AND f_score >= 3 AND m_score <= 2 THEN '一般价值客户'
        WHEN r_score >= 3 AND f_score <= 2 AND m_score <= 2 THEN '一般发展客户'
        WHEN r_score <= 2 AND f_score >= 3 AND m_score <= 2 THEN '一般保持客户'
        WHEN r_score <= 2 AND f_score <= 2 AND m_score <= 2 THEN '一般挽留客户'
    END AS user_segment
FROM rfm_scored;

-- ============================================================
-- Step 3: 验证
-- ============================================================

-- 3.1 八类客户分布（对照手册第三章策略表）
SELECT user_segment, COUNT(*) AS users,
       ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM ads_rfm_segments), 2) AS pct
FROM ads_rfm_segments
GROUP BY user_segment
ORDER BY users DESC;

-- 3.2 每类客户的平均 RFM 指标（看分群是否合理）
SELECT user_segment,
       ROUND(AVG(r_days), 1) AS avg_r_days,
       ROUND(AVG(f_freq), 1) AS avg_f_freq,
       ROUND(AVG(m_amount), 2) AS avg_m_amount,
       COUNT(*) AS users
FROM ads_rfm_segments
GROUP BY user_segment
ORDER BY avg_m_amount DESC;

-- 3.3 关联职业维度:看哪个职业的高价值客户最多（dim_user_profile 的化学反应）
SELECT
    COALESCE(p.face, '未知') AS occupation,
    COUNT(*) AS high_value_users
FROM ads_rfm_segments r
LEFT JOIN dim_user_profile p ON r.user_id = p.user_id
WHERE r.user_segment IN ('重要价值客户', '重要发展客户', '重要保持客户', '重要挽留客户')
GROUP BY p.face
ORDER BY high_value_users DESC
LIMIT 10;

-- 3.4 抽样:用户9998 的 RFM 画像
SELECT * FROM ads_rfm_segments WHERE user_id = 9998;