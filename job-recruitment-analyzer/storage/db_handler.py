"""
MySQL 数据库操作封装
====================
提供建库、建表、插入、查询等操作。用 PyMySQL 直连，没有引入 ORM，
因为课程作业的查询比较简单，SQL 更直观也更快。

安全提醒：使用参数化查询防止 SQL 注入。
                 不要直接拼 SQL 字符串！（反面教材：f"SELECT * FROM x WHERE y='{user_input}'"）
"""
import os
import json
import pymysql
from pymysql.cursors import DictCursor
from loguru import logger
from typing import List, Dict, Optional
from contextlib import contextmanager

import config


class Database:
    """
    MySQL 操作封装
    --------------
    用法：
        db = Database()
        db.init_database()           # 建库建表
        db.insert_many(rows)         # 批量插入
        results = db.query(sql, params)  # 参数化查询

    注意：
        密码在 config.py 的 DB_CONFIG 里改。
        生产环境密码应该从环境变量读，这里为了课程作业方便直接写配置里。
    """

    def __init__(self, db_config: dict = None):
        self.config = db_config or config.DB_CONFIG

    # ---- 获取连接 ----

    def _get_connection(self, with_db: bool = True):
        """获取数据库连接"""
        cfg = self.config.copy()
        if not with_db:
            cfg.pop("database", None)  # 连接时不指定数据库（用于建库）
        return pymysql.connect(
            host=cfg["host"],
            port=cfg.get("port", 3306),
            user=cfg["user"],
            password=cfg["password"],
            database=cfg.get("database") if with_db else None,
            charset=cfg.get("charset", "utf8mb4"),
            cursorclass=DictCursor,  # 返回字典格式结果
        )

    @contextmanager
    def _cursor(self, conn=None):
        """上下文管理器：自动处理连接打开/关闭"""
        close_conn = False
        if conn is None:
            conn = self._get_connection()
            close_conn = True
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            if close_conn:
                conn.close()

    # ---- 建库建表 ----

    def init_database(self):
        """
        初始化数据库：
        1. 创建数据库（如果不存在）
        2. 执行 schema.sql 建表

        这是整个数据流程的第一步，跑一次就行。
        """
        # Step 1: 建库
        conn = self._get_connection(with_db=False)
        try:
            with conn.cursor() as cur:
                cur.execute(f"CREATE DATABASE IF NOT EXISTS {self.config['database']} "
                            f"DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
                logger.info(f"✅ 数据库 {self.config['database']} 已就绪")
        finally:
            conn.close()

        # Step 2: 建表（读sql文件执行）
        schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")

        conn = self._get_connection(with_db=True)
        try:
            with conn.cursor() as cur:
                with open(schema_path, "r", encoding="utf-8") as f:
                    sql_content = f.read()
                # 按分号分割SQL语句执行
                statements = [s.strip() for s in sql_content.split(";") if s.strip()]
                for stmt in statements:
                    # 跳过注释行和USE语句
                    if stmt.startswith("--") or stmt.upper().startswith("USE "):
                        continue
                    try:
                        cur.execute(stmt)
                    except pymysql.err.OperationalError as e:
                        # 忽略"数据库已存在"等错误
                        if "exists" in str(e).lower() or "already" in str(e).lower():
                            pass
                        else:
                            raise e
                logger.info("✅ 数据库表已创建")
        finally:
            conn.close()

    # ---- 数据写入 ----

    def insert_one(self, row: Dict) -> int:
        """
        插入单条记录（参数化查询，防SQL注入）

        参数：
            row: 字段名→值的字典
        返回：
            新插入记录的ID
        """
        # 只取数据库表中存在的字段
        allowed_fields = {"job_title", "job_url", "keyword",
                          "salary_text", "salary_min", "salary_max", "salary_avg",
                          "city", "district", "city_tier",
                          "education", "experience", "exp_min", "exp_max",
                          "company_name", "company_size", "industry",
                          "skill_tags", "publish_date"}

        row_filtered = {k: v for k, v in row.items() if k in allowed_fields}

        # 参数化SQL（%s 是占位符，不是字符串拼接！）
        columns = ", ".join(row_filtered.keys())
        placeholders = ", ".join(["%s"] * len(row_filtered))
        sql = f"INSERT INTO job_listing ({columns}) VALUES ({placeholders})"
        values = list(row_filtered.values())

        with self._cursor() as cur:
            try:
                cur.execute(sql, values)
                return cur.lastrowid
            except pymysql.err.IntegrityError as e:
                if "Duplicate" in str(e):
                    logger.debug(f"重复数据跳过: {row.get('job_url', '')[:60]}")
                    return 0
                raise

    def insert_many(self, rows: List[Dict], batch_size: int = 100) -> int:
        """
        批量插入（用 ON DUPLICATE KEY UPDATE 避免重复插入报错）

        每 batch_size 条提交一次事务，兼顾速度和内存。

        参数：
            rows: 要插入的数据列表
            batch_size: 每批多少条
        返回：
            成功插入的条数
        """
        if not rows:
            return 0

        allowed_fields = {"job_title", "job_url", "keyword",
                          "salary_text", "salary_min", "salary_max", "salary_avg",
                          "city", "district", "city_tier",
                          "education", "experience", "exp_min", "exp_max",
                          "company_name", "company_size", "industry",
                          "skill_tags", "publish_date"}

        columns = [f for f in allowed_fields if f in rows[0]]
        placeholders = ", ".join(["%s"] * len(columns))
        col_str = ", ".join(columns)

        # INSERT ... ON DUPLICATE KEY UPDATE: 如果URL重复就更新数据
        update_clause = ", ".join([f"{c}=VALUES({c})" for c in columns if c != "job_url"])

        sql = (f"INSERT INTO job_listing ({col_str}) VALUES ({placeholders}) "
               f"ON DUPLICATE KEY UPDATE {update_clause}")

        total = 0
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]
            values_batch = []
            for row in batch:
                values = [row.get(c) for c in columns]
                # JSON字段序列化
                values_batch.append(values)

            with self._cursor() as cur:
                cur.executemany(sql, values_batch)
                total += cur.rowcount
            logger.debug(f"  已入库 {min(i + batch_size, len(rows))}/{len(rows)}")

        logger.info(f"✅ 批量入库完成: {total} 条")
        return total

    # ---- 数据查询 ----

    def query(self, sql: str, params: tuple = None) -> List[Dict]:
        """
        执行查询（参数化，防SQL注入）

        参数：
            sql: SQL语句（用 %s 做占位符）
            params: 参数元组
        返回：
            查询结果列表
        """
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchall()
        finally:
            conn.close()

    def query_one(self, sql: str, params: tuple = None) -> Optional[Dict]:
        """查询单条记录"""
        results = self.query(sql, params)
        return results[0] if results else None

    # ---- 统计查询（给Flask API用） ----

    def count_by_city(self) -> List[Dict]:
        """各城市岗位数量统计"""
        sql = """
            SELECT city, COUNT(*) as count, AVG(salary_avg) as avg_salary
            FROM job_listing
            WHERE city IS NOT NULL AND city != '未知'
            GROUP BY city
            ORDER BY count DESC
        """
        return self.query(sql)

    def count_by_education(self) -> List[Dict]:
        """学历分布统计"""
        sql = """
            SELECT education, COUNT(*) as count, AVG(salary_avg) as avg_salary
            FROM job_listing
            WHERE education IS NOT NULL
            GROUP BY education
            ORDER BY count DESC
        """
        return self.query(sql)

    def count_by_keyword(self) -> List[Dict]:
        """各关键词岗位数量"""
        sql = """
            SELECT keyword, COUNT(*) as count, AVG(salary_avg) as avg_salary
            FROM job_listing
            GROUP BY keyword
            ORDER BY count DESC
        """
        return self.query(sql)

    # ---- 数据清理 ----

    def truncate(self, table: str = "job_listing"):
        """清空表数据（谨慎使用！）"""
        with self._cursor() as cur:
            cur.execute(f"TRUNCATE TABLE {table}")
        logger.warning(f"⚠️ 表 {table} 已清空")


# 全局单例
db = Database()
