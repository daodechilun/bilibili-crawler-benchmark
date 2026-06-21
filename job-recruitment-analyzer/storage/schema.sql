-- ============================================================
-- IT岗位招聘数据分析项目 —— 数据库建表脚本
-- ============================================================
-- 使用方法：
--   1. 先创建数据库: CREATE DATABASE job_analysis DEFAULT CHARSET utf8mb4;
--   2. 执行本脚本:   mysql -u root -p job_analysis < schema.sql
-- ============================================================

-- 创建数据库（如果不存在）
CREATE DATABASE IF NOT EXISTS job_analysis
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;
USE job_analysis;

-- ============================================================
-- 主表：岗位信息
-- ============================================================
DROP TABLE IF EXISTS job_listing;
CREATE TABLE job_listing (
    -- 主键
    id              INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',

    -- 岗位基本信息
    job_title       VARCHAR(200)    NOT NULL COMMENT '岗位名称',
    job_url         VARCHAR(500)    NOT NULL COMMENT '51job详情链接',
    keyword         VARCHAR(50)     NOT NULL COMMENT '搜索关键词（数据分析/Python开发/AI算法/大数据开发）',

    -- 薪资（统一为月薪/元，未填薪资的为NULL）
    salary_text     VARCHAR(100)    DEFAULT NULL COMMENT '薪资原文（如15-25K·14薪）',
    salary_min      DECIMAL(10,2)   DEFAULT NULL COMMENT '最低月薪(元)',
    salary_max      DECIMAL(10,2)   DEFAULT NULL COMMENT '最高月薪(元)',
    salary_avg      DECIMAL(10,2)   DEFAULT NULL COMMENT '平均月薪(元) = (min+max)/2',

    -- 地点信息
    city            VARCHAR(50)     DEFAULT NULL COMMENT '城市（标准化后，如北京/上海）',
    district        VARCHAR(100)    DEFAULT NULL COMMENT '区/县',
    city_tier       ENUM('一线','新一线','二线','其他') DEFAULT NULL COMMENT '城市等级',

    -- 学历与经验
    education       VARCHAR(20)     DEFAULT NULL COMMENT '学历要求（不限/大专/本科/硕士/博士）',
    experience      VARCHAR(50)     DEFAULT NULL COMMENT '经验要求原文（如3-5年）',
    exp_min         DECIMAL(4,1)    DEFAULT 0   COMMENT '最低经验(年)',
    exp_max         DECIMAL(4,1)    DEFAULT 0   COMMENT '最高经验(年)',

    -- 公司信息
    company_name    VARCHAR(200)    DEFAULT NULL COMMENT '公司名称',
    company_size    VARCHAR(50)     DEFAULT NULL COMMENT '公司规模（如500-1000人）',
    industry        VARCHAR(100)    DEFAULT NULL COMMENT '所属行业',

    -- 技能标签
    skill_tags      TEXT            DEFAULT NULL COMMENT '技能标签（逗号分隔，如Python,SQL,Spark）',

    -- 元数据
    publish_date    DATE            DEFAULT NULL COMMENT '发布日期',
    created_at      TIMESTAMP       DEFAULT CURRENT_TIMESTAMP COMMENT '入库时间',

    -- ============================================================
    -- 索引设计说明：
    --   - uk_url: 唯一索引，防止重复入库 + 加速URL查询
    --   - idx_city/education/salary_avg/keyword: 业务查询常用索引
    --   - idx_publish: 按时间排序时用到
    --   - idx_city_salary: 联合索引，覆盖"查某城市高薪岗位"场景
    -- ============================================================
    UNIQUE KEY  uk_url          (job_url(255)),
    INDEX       idx_city        (city),
    INDEX       idx_education   (education),
    INDEX       idx_salary_avg  (salary_avg),
    INDEX       idx_keyword     (keyword),
    INDEX       idx_publish     (publish_date),
    INDEX       idx_city_salary (city, salary_avg)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='IT岗位招聘数据';


-- ============================================================
-- 辅助表1：技能-岗位关联表（技能标签拆分为多行后使用）
-- ============================================================
DROP TABLE IF EXISTS job_skill;
CREATE TABLE job_skill (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    job_id      INT             NOT NULL COMMENT '关联job_listing.id',
    skill_name  VARCHAR(100)    NOT NULL COMMENT '技能名称（如Python、SQL）',
    INDEX       idx_skill       (skill_name),
    INDEX       idx_job_id      (job_id),
    FOREIGN KEY (job_id) REFERENCES job_listing(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='技能-岗位关联表';


-- ============================================================
-- 辅助表2：分析结果缓存（避免每次都重新跑模型）
-- ============================================================
DROP TABLE IF EXISTS analysis_result;
CREATE TABLE analysis_result (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    result_name     VARCHAR(100)    NOT NULL COMMENT '分析名称（如salary_by_city）',
    result_data     JSON            NOT NULL COMMENT '分析结果JSON',
    updated_at      TIMESTAMP       DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_name (result_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='分析结果缓存';
