"""
实验八 - 数据持久化管道
实现爬取数据的 JSON 文件、CSV 文件和 JSON Lines 三种格式存储
"""
import json
import csv
import os


class JsonFilePipeline:
    """
    JSON 数组格式管道
    将所有数据保存为一个 JSON 数组文件
    """

    def __init__(self):
        self.items = []

    def process_item(self, item, spider):
        """收集 Item 数据"""
        data = dict(item)
        self.items.append(data)
        return item

    def close_spider(self, spider):
        """爬虫结束时，批量写入 JSON 文件"""
        output_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            '..', 'output'
        )
        os.makedirs(output_path, exist_ok=True)

        file_path = os.path.join(output_path, 'data.json')
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(self.items, f, ensure_ascii=False, indent=2)
        spider.logger.info(f"JSON 数据已保存至: {file_path}，共 {len(self.items)} 条")


class JsonLinesPipeline:
    """
    JSON Lines 格式管道（每行一条 JSON）
    适合大数据量场景，支持逐行追加写入
    """

    def open_spider(self, spider):
        output_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            '..', 'output'
        )
        os.makedirs(output_path, exist_ok=True)
        self.file = open(
            os.path.join(output_path, 'data.jsonl'),
            'w', encoding='utf-8'
        )
        self.count = 0

    def process_item(self, item, spider):
        """逐条写入 JSON 行"""
        data = dict(item)
        line = json.dumps(data, ensure_ascii=False)
        self.file.write(line + '\n')
        self.count += 1
        return item

    def close_spider(self, spider):
        self.file.close()
        spider.logger.info(f"JSONL 数据已保存，共 {self.count} 条")


class CsvFilePipeline:
    """
    CSV 文件管道
    适合表格化数据，可用 Excel 直接打开
    """

    def open_spider(self, spider):
        output_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            '..', 'output'
        )
        os.makedirs(output_path, exist_ok=True)
        self.file = open(
            os.path.join(output_path, 'data.csv'),
            'w', encoding='utf-8-sig', newline=''
        )
        self.writer = csv.writer(self.file)
        self.writer.writerow(['title', 'author', 'tags', 'link', 'publish_time', 'content'])
        self.count = 0

    def process_item(self, item, spider):
        """逐条写入 CSV 行"""
        data = dict(item)
        tags_str = ', '.join(data.get('tags', []))
        self.writer.writerow([
            data.get('title', ''),
            data.get('author', ''),
            tags_str,
            data.get('link', ''),
            data.get('publish_time', ''),
            data.get('content', ''),
        ])
        self.count += 1
        return item

    def close_spider(self, spider):
        self.file.close()
        spider.logger.info(f"CSV 数据已保存，共 {self.count} 条")
