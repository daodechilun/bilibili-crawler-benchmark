"""
解析模块 (parser)
================
负责解析51job返回的JSON数据，把各种格式统一标准化。

包含：
  - job_parser.py    → 岗位信息提取（列表+详情）
  - salary_parser.py → 薪资格式解析 + 城市/学历/经验标准化
"""
from parser.job_parser import parse_list_item, parse_detail_item, normalize_salary_field
from parser.salary_parser import (
    parse_salary, normalize_city, normalize_education, parse_experience,
)
