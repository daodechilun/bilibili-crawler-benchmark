"""
薪资格式解析器
=============
把各种五花八门的薪资格式统一解析成数值型字段。

招聘网站上薪资写得五花八门：
  「15-25K·14薪」   →  min=15000, max=25000, avg=20000
  「8千-1.2万/月」   →  min=8000, max=12000, avg=10000
  「300-500元/天」   →  按21.75工作日估算月薪
  「面议」           →  None（无法估算，跳过）
  「薪资open」       →  None

思路：
  1. 正则提取数字和单位
  2. 统一换算成「元/月」
  3. 计算 min、max、avg 三个字段
"""
import re
from typing import Optional, Tuple


# 学历关键词映射（标准化用，这里先定义，cleaner阶段也会用）
EDUCATION_MAP = {
    "学历不限": "不限", "不限": "不限",
    "初中及以下": "不限",
    "中专": "大专", "中技": "大专", "高中": "大专",
    "大专": "大专", "大专及以上": "大专",
    "本科": "本科", "本科及以上": "本科",
    "硕士": "硕士", "硕士及以上": "硕士",
    "博士": "博士",
}

# 城市标准名映射（51job城市名→标准名）
CITY_ALIAS = {
    "北京市": "北京", "上海市": "上海", "广州市": "广州", "深圳市": "深圳",
    "杭州市": "杭州", "成都市": "成都", "武汉市": "武汉",
    "南京市": "南京", "西安市": "西安", "长沙市": "长沙",
    "苏州市": "苏州", "郑州市": "郑州", "天津市": "天津",
    "重庆市": "重庆", "东莞市": "东莞", "厦门市": "厦门", "佛山市": "佛山",
    "合肥市": "合肥", "无锡市": "无锡", "福州市": "福州", "青岛市": "青岛",
    "大连市": "大连", "宁波市": "宁波", "济南市": "济南", "沈阳市": "沈阳",
    "贵阳市": "贵阳", "昆明市": "昆明", "石家庄市": "石家庄",
}

# 城市简称标准化（去掉"市"后缀和区名）
CITY_SHORT_MAP = {}
for full_name, short_name in CITY_ALIAS.items():
    CITY_SHORT_MAP[short_name] = short_name
    CITY_SHORT_MAP[full_name] = short_name


def parse_salary(salary_text: str) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """
    解析薪资格式，返回 (min, max, avg)

    处理以下格式：
    - 「15-25K」         → min=15000, max=25000
    - 「8千-1.2万/月」   → min=8000, max=12000
    - 「300-500元/天」   → 估算月薪（日薪×21.75）
    - 「面议」           → None, None, None

    参数：
        salary_text: 原始薪资文本
    返回：
        (salary_min, salary_max, salary_avg)，无法解析则为 None
    """
    if not salary_text or not isinstance(salary_text, str):
        return None, None, None

    text = salary_text.strip()

    # ---- 处理特殊值 ----
    if any(kw in text for kw in ["面议", "薪资面议", "待遇面议", "open"]):
        return None, None, None

    # ---- 判断周期 ----
    is_daily = "天" in text or "日" in text
    is_hourly = "时" in text or "小时" in text
    is_annual = "年" in text and "经验" not in text and "工作" not in text

    # ---- 提取「数字+单位」组合 ----
    # 匹配如：8千、1.3万、15K、5000元、20万
    pattern = re.compile(r'(\d+(?:\.\d+)?)\s*([万千kK元/]?)')
    matches = pattern.findall(text)
    if not matches:
        return None, None, None

    # 过滤掉 "X薪" 里的数字
    raw_values = []
    for num_str, unit in matches:
        num = float(num_str)
        search_str = num_str + (unit if unit else "")
        idx = text.find(search_str)
        if idx >= 0 and "薪" in text[max(0, idx-2):idx+len(search_str)+2]:
            continue
        raw_values.append((num, unit))

    if not raw_values:
        return None, None, None

    # 给没有单位的数字继承后面最近的单位（处理 "15-25K"）
    values = []
    for i, (num, unit) in enumerate(raw_values):
        if not unit:
            # 向后查找单位
            for j in range(i+1, len(raw_values)):
                if raw_values[j][1]:
                    unit = raw_values[j][1]
                    break
            # 向前查找单位
            if not unit:
                for j in range(i-1, -1, -1):
                    if raw_values[j][1]:
                        unit = raw_values[j][1]
                        break
        values.append((num, unit))

    # ---- 根据每个数字自己的单位换算成 元/月 ----
    def to_monthly(num, unit):
        unit = (unit or "").lower()
        if "万" in unit:
            return num * 10000
        if "千" in unit or unit == "k":
            return num * 1000
        if "元" in unit:
            return num
        # 没有单位，根据数值大小和全文单位猜测
        if "万" in text and num < 100:
            return num * 10000
        if "千" in text and num < 100:
            return num * 1000
        return num

    monthly_values = [to_monthly(n, u) for n, u in values]

    # ---- 确定 min/max ----
    if len(monthly_values) == 1:
        salary_min = salary_max = monthly_values[0]
    else:
        salary_min = min(monthly_values[0], monthly_values[1])
        salary_max = max(monthly_values[0], monthly_values[1])

    # ---- 判断是否为年薪：
    # 规则：
    # 1. 文本明确含"/年"或"每年" → 年薪，除以12
    # 2. "X-Y万·N薪" 且数值很大（>5万）→ 年薪，除以N
    # 3. 其他情况（含"X-Y万·N薪"数值≤5万、"X-Y万"无标记）→ 月薪，不除
    # 注：51job上 "X-Y万" 无"/年"标记时几乎都是月薪；
    #       "X-Y万·N薪" 中 X-Y≤5万 为月薪+N个月年终，X-Y>5万 为年薪÷N
    has_monthly_unit = any(
        "千" in (u or "") or (u or "").lower() == "k" for _, u in values
    )
    bonus_match = re.search(r'(\d+)\s*薪', text)
    # 明确写"/年"
    is_explicit_annual = ("年" in text) and ("经验" not in text) and ("工作" not in text)
    # "X-Y万·N薪" 且数值很大（>8万）→ 年薪除以N
    is_bonus_annual = bool(bonus_match) and salary_max > 80000 and not has_monthly_unit

    # ---- 日薪/时薪/年薪转月薪 ----
    if is_daily:
        salary_min = round(salary_min * 21.75)
        salary_max = round(salary_max * 21.75)
    elif is_hourly:
        salary_min = round(salary_min * 8 * 21.75)
        salary_max = round(salary_max * 8 * 21.75)
    elif is_explicit_annual and not bonus_match:
        # 明确写 "/年" 且无 N薪：年薪除以 12
        salary_min = round(salary_min / 12)
        salary_max = round(salary_max / 12)
    elif is_bonus_annual:
        # "X-Y万·N薪" 且数值很大：年薪除以 N 薪得到月薪
        bonus_months = int(bonus_match.group(1))
        salary_min = round(salary_min / bonus_months)
        salary_max = round(salary_max / bonus_months)
    # 注：其他情况（"X-Y万·N薪"数值≤5万、"X-Y万"无标记）不做处理，即为月薪

    # ---- 计算平均值 ----
    salary_avg = round((salary_min + salary_max) / 2)

    return round(salary_min), round(salary_max), salary_avg


def normalize_city(city_text: str) -> Tuple[str, str]:
    """
    标准化城市名

    输入可能是：
    - 「北京朝阳区」  →  city=北京, district=朝阳区
    - 「上海市」      →  city=上海, district=
    - 「深圳-南山区」 →  city=深圳, district=南山区

    返回：(城市, 区县)
    """
    if not city_text or not isinstance(city_text, str):
        return "未知", ""

    text = city_text.strip()

    # 先尝试精确匹配
    for full, short in CITY_ALIAS.items():
        if full in text:
            district = text.replace(full, "").strip()
            return short, district

    # 尝试匹配城市简称
    for short in sorted(CITY_SHORT_MAP.keys(), key=len, reverse=True):
        if text.startswith(short):
            district = text[len(short):].strip().lstrip("-").lstrip("·")
            return CITY_SHORT_MAP.get(short, short), district

    # 兜底：保持原文
    return text, ""


def normalize_education(edu_text: str) -> str:
    """
    标准化教育程度

    「本科及以上」→「本科」
    「学历不限」  →「不限」
    """
    if not edu_text:
        return "不限"
    for key, value in EDUCATION_MAP.items():
        if key in edu_text:
            return value
    return edu_text.strip()


def parse_experience(exp_text: str) -> Tuple[float, float]:
    """
    解析工作经验

    「3-5年」      → (3.0, 5.0)
    「1-3年经验」  → (1.0, 3.0)
    「经验不限」    → (0.0, 0.0)
    「在校/应届」  → (0.0, 0.0)
    「5年以上」    → (5.0, 999.0)
    """
    if not exp_text or not isinstance(exp_text, str):
        return 0.0, 0.0

    text = exp_text.strip()

    if any(kw in text for kw in ["不限", "应届", "在校", "无需"]):
        return 0.0, 0.0

    if "以上" in text:
        nums = re.findall(r'(\d+(?:\.\d+)?)', text)
        if nums:
            return float(nums[0]), 999.0

    nums = re.findall(r'(\d+(?:\.\d+)?)', text)
    if len(nums) >= 2:
        return float(nums[0]), float(nums[1])
    elif len(nums) == 1:
        return float(nums[0]), float(nums[0])
    return 0.0, 0.0
