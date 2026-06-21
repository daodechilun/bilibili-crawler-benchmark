"""
岗位信息解析器
=============
负责从 51job API 返回的 JSON 中提取我们需要的字段。

分为两部分：
1. parse_list_item()   —— 解析搜索列表中的单条岗位数据
2. parse_detail_item() —— 解析岗位详情页的数据（补充技能标签等）
3. normalize_salary_field() —— 对已解析的岗位数据补算 salary_min/max/avg
"""
import re
from datetime import datetime
from typing import Dict, Optional

from parser.salary_parser import (
    parse_salary,
    normalize_city,
    normalize_education,
    parse_experience,
)


def parse_list_item(item: dict, keyword: str) -> Optional[Dict]:
    """
    解析搜索列表中的单条岗位数据

    51job 搜索API返回的字段（常见情况）：
    {
        "jobId": "12345678",
        "jobName": "数据分析师",
        "companyName": "XX科技有限公司",
        "providesalary": "15-25K·14薪",          -- 原始薪资文本
        "workarea": "北京朝阳区",                 -- 工作地点
        "companySize": "500-1000人",
        "companyind_text": "互联网/电子商务",
        "degreefrom": "本科",
        "workyear": "3-5年",
        "issuedate": "2025-06-15",
        "attribute": ["Python", "SQL", "..."]
    }

    返回标准化后的字典，字段与 CSV 列对齐。
    """
    if not isinstance(item, dict):
        return None

    # --- 岗位名 ---
    job_title = item.get("jobName") or item.get("job_name") or item.get("jobTitle") or ""
    job_title = job_title.strip()

    if not job_title:
        return None

    # --- 薪资 ---
    salary_text = item.get("providesalary") or item.get("providesalary_text") or item.get("salary") or ""
    salary_text = salary_text.strip()
    salary_min, salary_max, salary_avg = parse_salary(salary_text)

    # --- 城市 ---
    workarea = item.get("workarea") or item.get("workArea") or item.get("city") or ""
    city, district = normalize_city(workarea)

    # --- 学历 ---
    education = normalize_education(
        item.get("degreefrom") or item.get("degree") or item.get("education") or ""
    )

    # --- 经验 ---
    experience = item.get("workyear") or item.get("workingExp") or item.get("experience") or ""
    experience = experience.strip()
    exp_min, exp_max = parse_experience(experience)

    # --- 公司 ---
    company_name = item.get("companyName") or item.get("company_name") or ""
    company_name = company_name.strip()

    company_size = item.get("companySize") or item.get("companysize") or item.get("company_size") or ""
    company_size = company_size.strip()

    industry = item.get("companyind_text") or item.get("industry") or item.get("industry_text") or ""
    industry = industry.strip()

    # --- 技能标签 ---
    # 51job列表页中的 attribute 字段就是技能标签数组
    skill_tags_raw = item.get("attribute") or item.get("skill_tags") or item.get("tags") or []
    if isinstance(skill_tags_raw, list):
        skill_tags = ", ".join(skill_tags_raw)
    elif isinstance(skill_tags_raw, str):
        skill_tags = skill_tags_raw
    else:
        skill_tags = ""

    # --- 发布日期 ---
    publish_date = item.get("issuedate") or item.get("publishDate") or item.get("publish_date") or ""
    if isinstance(publish_date, str) and publish_date:
        # 处理可能的各种日期格式
        for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S"]:
            try:
                dt = datetime.strptime(publish_date[:10], fmt)
                publish_date = dt.strftime("%Y-%m-%d")
                break
            except ValueError:
                continue

    # --- 岗位URL ---
    job_id = item.get("jobId") or item.get("jobid") or item.get("job_id") or item.get("encrypt_job_id") or ""
    if job_id:
        job_url = f"https://jobs.51job.com/all/{job_id}.html"
    else:
        job_url = item.get("job_href") or item.get("jobUrl") or ""

    # --- 构建返回 ---
    return {
        "job_title": job_title,
        "salary_text": salary_text,
        "salary_min": salary_min,
        "salary_max": salary_max,
        "salary_avg": salary_avg,
        "city": city,
        "district": district,
        "education": education,
        "experience": experience if experience else f"{exp_min}-{exp_max}年" if exp_max else f"{exp_min}年",
        "exp_min": exp_min,
        "exp_max": exp_max,
        "company_name": company_name,
        "company_size": company_size,
        "industry": industry,
        "skill_tags": skill_tags,
        "publish_date": publish_date,
        "job_url": job_url,
        "job_id": str(job_id) if job_id else "",
        "keyword": keyword,
        "crawl_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def parse_detail_item(data: dict) -> Dict:
    """
    解析岗位详情API返回的数据

    详情页通常有：
    - 完整的技能标签（jobTags / skillList）
    - 详细的职位描述
    - 公司更多信息

    返回一个字典，只包含新增的字段（用于补充到已有数据上）。
    """
    result = {}

    if not isinstance(data, dict):
        return result

    # 提取详情数据（兼容多种嵌套结构）
    detail = data.get("jobDetail") or data.get("detail") or data.get("data") or data

    if isinstance(detail, dict):
        # 技能标签
        skill_tags = detail.get("skillTags") or detail.get("jobTags") or detail.get("tags") or []
        if isinstance(skill_tags, list):
            result["skill_tags"] = ", ".join(skill_tags)
        elif isinstance(skill_tags, str):
            result["skill_tags"] = skill_tags

        # 学历（详情页可能更准确）
        edu = detail.get("degreeName") or detail.get("degree") or ""
        if edu:
            result["education"] = normalize_education(edu)

        # 经验
        exp = detail.get("workingYears") or detail.get("workingExp") or ""
        if exp:
            exp_min, exp_max = parse_experience(exp)
            result["exp_min"] = exp_min
            result["exp_max"] = exp_max
            result["experience"] = f"{exp_min}-{exp_max}年" if exp_max and exp_max < 999 else f"{exp_min}年以上"

    # 公司规模（详情页可能有更准的数据）
    company = data.get("companyInfo") or data.get("company") or {}
    if isinstance(company, dict):
        size = company.get("companySize") or company.get("scale") or ""
        if size:
            result["company_size"] = size.strip()

    return result


def normalize_salary_field(job: Dict) -> Dict:
    """
    对已经抓到但没解析薪资的岗位数据，补算 salary_min/max/avg

    这用在爬虫解析阶段，确保每条记录三个薪资字段都有值。
    如果 salary_text 有值但 min/max 为空，重新解析一遍。
    """
    if job.get("salary_min") is None and job.get("salary_text"):
        smin, smax, savg = parse_salary(job["salary_text"])
        if smin is not None:
            job["salary_min"] = smin
        if smax is not None:
            job["salary_max"] = smax
        if savg is not None:
            job["salary_avg"] = savg
    return job
