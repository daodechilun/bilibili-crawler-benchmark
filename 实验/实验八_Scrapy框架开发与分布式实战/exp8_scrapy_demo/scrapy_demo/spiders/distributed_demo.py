"""
实验八 - 分布式爬虫 Spider（基于 scrapy-redis）
继承 RedisSpider，通过 Redis 共享任务队列实现多机协同爬取

使用方法:
1. 确保 Redis 服务已启动（127.0.0.1:6379）
2. 在 settings.py 中启用分布式配置（取消注释）
3. 向 Redis 推送起始 URL:
   redis-cli lpush distributed_demo:start_urls "https://quotes.toscrape.com/"
4. 在多个终端同时启动爬虫:
   scrapy crawl distributed_demo
"""
from scrapy_redis.spiders import RedisSpider
from scrapy_demo.items import ScrapyDemoItem
from datetime import datetime


class DistributedDemoSpider(RedisSpider):
    """分布式爬虫：多机共享 Redis 任务队列"""
    name = 'distributed_demo'

    # 分布式任务 key —— 通过 Redis 的 lpush 推送起始链接
    # redis-cli lpush distributed_demo:start_urls "https://quotes.toscrape.com/"
    redis_key = "distributed_demo:start_urls"

    # 允许的域名
    allowed_domains = ['quotes.toscrape.com']

    def parse(self, response):
        """
        核心解析逻辑（与单机版 DemoSpider 一致）
        数据提取完成后提交到 Item Pipeline
        """
        quotes = response.css('div.quote')

        for quote in quotes:
            item = ScrapyDemoItem()

            # CSS 选择器提取
            item["title"] = quote.css('span.text::text').get()
            item["author"] = quote.css('small.author::text').get()
            item["tags"] = quote.css('a.tag::text').getall()
            item["link"] = response.urljoin(
                quote.css('span a::attr(href)').get()
            )
            item["publish_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            item["content"] = (
                f"作者 {item['author']} 的名言，"
                f"标签: {', '.join(item['tags'])}"
            )

            yield item

        # 分页跟踪：将下一页 URL 加入 Redis 队列
        next_page = response.css('li.next a::attr(href)').get()
        if next_page:
            yield response.follow(next_page, callback=self.parse)
