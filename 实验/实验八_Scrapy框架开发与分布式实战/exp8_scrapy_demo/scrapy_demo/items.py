"""
实验八 - Item 数据模型定义
定义爬取数据的字段规范，统一数据格式
"""
import scrapy


class ScrapyDemoItem(scrapy.Item):
    """基础数据模型：名言数据"""
    # 自定义爬取字段
    title = scrapy.Field()          # 名言文本（标题）
    author = scrapy.Field()         # 作者
    tags = scrapy.Field()           # 标签
    link = scrapy.Field()           # 详情页链接
    publish_time = scrapy.Field()   # 采集时间
    content = scrapy.Field()        # 内容简介
