-- =============================================
-- 销售数据表 - 建表语句 (MySQL)
-- =============================================
-- 1. 不存在则创建demo数据库
CREATE DATABASE IF NOT EXISTS demo DEFAULT CHARACTER SET utf8mb4;
-- 2. 切换至demo库
USE demo;
DROP TABLE IF EXISTS `sales_data`;

CREATE TABLE `sales_data` (
    `id`            BIGINT UNSIGNED  NOT NULL AUTO_INCREMENT   COMMENT '主键ID',
    `sale_date`     DATE             NOT NULL                  COMMENT '销售日期',
    `product_name`  VARCHAR(100)     NOT NULL                  COMMENT '产品名称',
    `category`      VARCHAR(50)      NOT NULL                  COMMENT '产品类别',
    `region`        VARCHAR(50)      NOT NULL                  COMMENT '大区',
    `city`          VARCHAR(50)      NOT NULL                  COMMENT '城市',
    `sales_amount`  DECIMAL(12,2)    NOT NULL DEFAULT 0.00     COMMENT '销售额（元）',
    `profit`        DECIMAL(12,2)    NOT NULL DEFAULT 0.00     COMMENT '利润（元）',
    `quantity`      INT UNSIGNED     NOT NULL DEFAULT 0        COMMENT '销售数量',
    `unit_price`    DECIMAL(10,2)    NOT NULL DEFAULT 0.00     COMMENT '单价（元）',
    `channel`       VARCHAR(30)      NOT NULL DEFAULT '线下'   COMMENT '销售渠道（线上/线下）',
    `salesperson`   VARCHAR(50)      NOT NULL DEFAULT ''       COMMENT '销售员',
    `created_at`    DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`    DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    INDEX `idx_sale_date` (`sale_date`),
    INDEX `idx_product` (`product_name`),
    INDEX `idx_region` (`region`),
    INDEX `idx_category` (`category`),
    INDEX `idx_region_date` (`region`, `sale_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='销售数据表';
