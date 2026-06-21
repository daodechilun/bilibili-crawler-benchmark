"""
CSV 读写工具
============
封装 CSV 文件的读写操作，加上编码处理和错误恢复。

为什么不用 pandas 直接读？
- 爬虫阶段还在采集数据，pandas 的好处（向量化操作）体现不出来
- 用标准库 csv 模块更轻量，启动快
- 等清洗阶段再用 pandas 批量处理
"""
import csv
import os
from typing import List, Dict, Optional


def read_csv(filepath: str, encoding: str = "utf-8-sig") -> List[Dict]:
    """
    读取 CSV 文件，返回字典列表

    每一行是一个 dict，key 是列名，value 是单元格内容。
    比如 row["job_title"] 拿到岗位名。

    参数：
        filepath: CSV 文件路径
        encoding: 文件编码，默认 utf-8-sig（兼容 Excel 打开）
    返回：
        [{列名: 值, ...}, ...]
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"找不到文件: {filepath}")

    rows = []
    with open(filepath, "r", encoding=encoding, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def write_csv(
    filepath: str,
    rows: List[Dict],
    fieldnames: Optional[List[str]] = None,
    encoding: str = "utf-8-sig",
    append: bool = False,
):
    """
    把字典列表写入 CSV 文件

    参数：
        filepath: 目标文件路径
        rows: 数据行列表
        fieldnames: 列名列表（不传则自动从第一行数据提取）
        encoding: utf-8-sig 能让 Excel 正确识别中文
        append: True=追加, False=覆盖
    """
    if not rows:
        print(f"⚠️ 没有数据可写入 {filepath}")
        return

    # 自动提取列名
    if fieldnames is None:
        fieldnames = list(rows[0].keys())

    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    mode = "a" if append else "w"
    write_header = not append or not os.path.exists(filepath)

    with open(filepath, mode, encoding=encoding, newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerows(rows)

    action = "追加" if append else "保存"
    print(f"💾 {action} {len(rows)} 条数据到: {filepath}")


def count_rows(filepath: str) -> int:
    """快速统计 CSV 文件行数（不含表头）"""
    if not os.path.exists(filepath):
        return 0
    with open(filepath, "r", encoding="utf-8-sig", newline="") as f:
        return sum(1 for _ in f) - 1  # 减1因为表头


def get_fieldnames(filepath: str) -> List[str]:
    """获取 CSV 文件的列名"""
    if not os.path.exists(filepath):
        return []
    with open(filepath, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return reader.fieldnames or []
