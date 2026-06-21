"""
实验八 - 基础 Spider 爬虫
使用 XPath/CSS 选择器提取网页数据，封装为 Item 对象
"""
import scrapy
from datetime import datetime
from scrapy_demo.items import ScrapyDemoItem


class DemoSpider(scrapy.Spider):
    """基础爬虫：爬取 quotes.toscrape.com 名言数据"""
    name = 'demo'
    allowed_domains = ['quotes.toscrape.com']
    start_urls = ['https://quotes.toscrape.com/']

    def parse(self, response):
        """
        核心解析逻辑：
        1. 定位页面中每条名言的卡片容器
        2. 使用 XPath/CSS 选择器提取各字段
        3. 封装为 Item 对象并 yield 提交
        """
        # 定位每条名言所在的 div.quote 容器
        quotes = response.css('div.quote')

        for quote in quotes:
            item = ScrapyDemoItem()

            # 方法一：CSS 选择器提取
            item["title"] = quote.css('span.text::text').get()
            item["author"] = quote.css('small.author::text').get()
            item["tags"] = quote.css('a.tag::text').getall()
            item["link"] = response.urljoin(
                quote.css('span a::attr(href)').get()
            )

            # 方法二：XPath 提取（等效实现，演示两种方式）
            # item["title"] = quote.xpath(".//span[@class='text']/text()").get()
            # item["author"] = quote.xpath(".//small[@class='author']/text()").get()

            item["publish_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            item["content"] = f"作者 {item['author']} 的名言，标签: {', '.join(item['tags'])}"

            yield item

        # 处理分页：查找"下一页"链接并跟踪
        next_page = response.css('li.next a::attr(href)').get()
        if next_page:
            yield response.follow(next_page, callback=self.parse)
