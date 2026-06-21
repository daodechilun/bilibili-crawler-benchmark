"""
数据校验器
=========
清洗前的第一道关：逐条检查数据合法性，标记问题数据。
不合法的数据不会删除，但会标记原因，方便后续追溯。

为啥要这一步？
  爬虫抓回来的数据可能有各种奇怪问题：
  - 岗位名叫空字符串
  - 薪资 min > max（颠倒）
  - 发布日期是 1970-01-01
  - 城市名是乱码
  在清洗之前先过一遍校验，把问题数据标记出来，
  清洗时就能针对不同类型的问题做不同处理。
"""
from typing import Dict, List, Tuple, Optional
from datetime import datetime

# 合法的城市名白名单
VALID_CITIES = {
    "北京", "上海", "广州", "深圳", "杭州", "成都", "武汉",
    "南京", "西安", "长沙", "苏州", "郑州", "天津", "重庆",
    "东莞", "厦门", "佛山", "合肥", "无锡", "福州", "青岛",
    "大连", "宁波", "济南", "沈阳", "贵阳", "昆明", "石家庄",
}

# 合法的学历枚举
VALID_EDUCATION = {"不限", "大专", "本科", "硕士", "博士"}

# 合法的公司规模关键词
VALID_COMPANY_SIZE = ["少于50人", "50-150人", "150-500人", "500-1000人", "1000-5000人", "5000-10000人", "10000人以上"]


class DataValidator:
    """
    数据校验器
    ---------
    对每条岗位记录做合法性检查，返回问题标记。

    用法:
        validator = DataValidator()
        issues = validator.validate(record)  # 返回问题列表
        if not issues:
            # 数据干净
            pass
    """

    def check_face_to_face_ratio(self, records: List[Dict]) -> Dict:
        """
        🔥 统计各城市「面议」岗位占比

        如果某个城市面议岗位占比 > 30%，说明该城市的数据质量偏低。
        在薪资填补时应该乘 1.1 系数，因为面议岗（高管/急招）薪资通常偏高。

        返回：{city: ratio}，如 {"北京": 0.15, "深圳": 0.35}
        """
        city_total = {}
        city_face = {}

        for r in records:
            city = r.get("city", "未知")
            salary_text = str(r.get("salary_text", ""))
            city_total[city] = city_total.get(city, 0) + 1
            if "面议" in salary_text:
                city_face[city] = city_face.get(city, 0) + 1

        ratios = {}
        for city, total in city_total.items():
            face_count = city_face.get(city, 0)
            ratio = face_count / total if total > 0 else 0
            ratios[city] = ratio

        # 打印警告
        high_ratio_cities = {c: r for c, r in ratios.items() if r > 0.3}
        if high_ratio_cities:
            logger = __import__("loguru").logger
            logger.warning(f"⚠️ 以下城市面议占比超过30%，填补时将乘1.1系数:")
            for city, ratio in sorted(high_ratio_cities.items(), key=lambda x: -x[1]):
                logger.warning(f"   {city}: {ratio*100:.1f}% 面议")

        return ratios

    def validate(self, record: Dict) -> List[str]:
        """
        校验单条记录，返回问题列表

        没有问题是空列表 []，有问题比如 ['岗位名为空', '薪资异常']
        """
        issues = []

        # 1. 岗位名不能为空
        title = record.get("job_title", "")
        if not title or not title.strip():
            issues.append("岗位名为空")

        # 2. 薪资范围校验
        salary_min = self._to_float(record.get("salary_min"))
        salary_max = self._to_float(record.get("salary_max"))
        if salary_min is not None and salary_max is not None:
            if salary_min > salary_max:
                issues.append(f"薪资min({salary_min}) > max({salary_max})")
            if salary_min <= 0:
                issues.append(f"薪资min为0或负数: {salary_min}")
            if salary_max > 1000000:
                issues.append(f"薪资异常高: {salary_max}")

        # 3. 城市合法性
        city = record.get("city", "")
        if city and city != "未知" and city not in VALID_CITIES:
            # 不是标准名，尝试模糊匹配
            matched = False
            for valid_city in VALID_CITIES:
                if valid_city in city or city in valid_city:
                    matched = True
                    break
            if not matched:
                issues.append(f"无法识别的城市: {city}")

        # 4. 日期格式
        pub_date = record.get("publish_date", "")
        if pub_date:
            try:
                dt = datetime.strptime(str(pub_date)[:10], "%Y-%m-%d")
                if dt.year < 2000 or dt.year > 2030:
                    issues.append(f"日期年份异常: {pub_date}")
            except ValueError:
                issues.append(f"日期格式异常: {pub_date}")

        # 5. 学历
        edu = record.get("education", "")
        if edu and edu not in VALID_EDUCATION:
            issues.append(f"学历不在枚举中: {edu}")

        # 6. URL不能为空
        url = record.get("job_url", "")
        if not url:
            issues.append("job_url为空")

        return issues

    def validate_batch(self, records: List[Dict]) -> Tuple[List[Dict], Dict]:
        """
        批量校验，返回 (干净记录, 问题统计)

        参数：
            records: 原始记录列表
        返回：
            (干净的记录列表, 问题统计)
        """
        clean = []
        stats = {
            "total": len(records),
            "clean": 0,
            "issues": 0,
            "issue_breakdown": {},  # 问题类型 → 条数
        }

        for r in records:
            issues = self.validate(r)
            if issues:
                stats["issues"] += 1
                r["_issues"] = ", ".join(issues)  # 标记问题
                for issue in issues:
                    stats["issue_breakdown"][issue] = stats["issue_breakdown"].get(issue, 0) + 1
            else:
                stats["clean"] += 1
            clean.append(r)  # 即使是问题数据也保留，只是标记

        return clean, stats

    @staticmethod
    def _to_float(val) -> Optional[float]:
        """安全转float，失败返回None"""
        if val is None:
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None
