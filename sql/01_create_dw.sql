-- ============================================================
-- 01_create_dw.sql — Phase 2 第一步：建库 + ODS/DIM 建表
-- 运行环境：MySQL 8.0.36，在终端用SOURCE执行（也可在 Workbench 中直接执行本文件）
-- 执行：mysql -u root -p --default-character-set=utf8mb4
--      SOURCE sql/01_create_dw.sql;
-- ============================================================

-- 1. 建库：utf8mb4 是 MySQL8 默认字符集，完整支持中文与特殊字符
CREATE DATABASE IF NOT EXISTS ecommerce_dw
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_0900_ai_ci;

USE ecommerce_dw;

-- ============================================================
-- 2. ODS 层（原始数据缓冲区）
-- 设计原则：
--   a. 原样保存：字段名与 CSV 表头一一对应，不做任何清洗
--   b. 类型宽容：timestamp 原始数据混有约 7 千行脏值，
--      用 VARCHAR 收留，类型转换留给 DWD 层（ODS 管"存"，DWD 管"清"）
--   c. 不建主键/索引：导入速度优先，索引到 DWD 层再加
-- 注意：timestamp 是 MySQL 保留字，必须用反引号包裹
-- ============================================================
CREATE TABLE IF NOT EXISTS ods_user_behavior (
    user_id     BIGINT        NOT NULL COMMENT '用户ID',
    goods_id    BIGINT        NOT NULL COMMENT '商品ID',
    category_id BIGINT        NOT NULL COMMENT '品类ID',
    behavior    VARCHAR(10)   NOT NULL COMMENT '行为类型: pv/cart/fav/buy',
    `timestamp` VARCHAR(32)   NULL     COMMENT 'Unix时间戳(原始字符串,容忍脏数据)',
    sex         TINYINT       NULL     COMMENT '性别: 0/1',
    address     VARCHAR(50)   NULL     COMMENT '城市',
    device      VARCHAR(50)   NULL     COMMENT '设备型号',
    price       DECIMAL(12,2) NULL     COMMENT '商品价格',
    amount      INT           NULL     COMMENT '数量',
    comment     TEXT          NULL     COMMENT '评论内容'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
  COMMENT='ODS: 用户行为原始日志(约76.5万行)';

CREATE TABLE IF NOT EXISTS ods_comment (
    user_id     BIGINT NULL COMMENT '用户ID',
    goods_id    BIGINT NULL COMMENT '商品ID',
    category_id BIGINT NULL COMMENT '品类ID',
    comment     TEXT   NULL COMMENT '评论长文本'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
  COMMENT='ODS: 用户评论原始数据(Phase3 情感分析素材)';

-- ============================================================
-- 3. DIM 层（维度表）
-- 与 ODS 相反：主键约束在这里建立，导入脚本会先做主键去重
-- ============================================================
CREATE TABLE IF NOT EXISTS dim_category (
    category_id    BIGINT       NOT NULL PRIMARY KEY COMMENT '品类ID',
    category_count INT          NULL     COMMENT '行为次数(映射文件自带)',
    category_label VARCHAR(100) NULL     COMMENT '品类中文名'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
  COMMENT='DIM: 品类维表(手机壳/数据线等中文名)';

CREATE TABLE IF NOT EXISTS dim_user_profile (
    user_id BIGINT      NOT NULL PRIMARY KEY COMMENT '用户ID',
    face    VARCHAR(50) NULL     COMMENT '职业身份标签'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
  COMMENT='DIM: 用户画像维表(职业)';

-- ============================================================
-- 4. 建表验证
-- ============================================================
SHOW TABLES;