# Bilibili 动态网页爬虫 — Ajax vs Selenium 方案对比

针对 Bilibili 热门视频榜单，实现并对比两种动态网页数据爬取方案。

## 两种方案

| 方案 | 技术栈 | 效率 |
|------|--------|------|
| Ajax 接口爬取 | Python `requests` + JSON 解析 | 500 条 / 1.44 秒（0.14 秒/页） |
| Selenium 自动化 | `selenium` + ChromeDriver | 60 条 / 22 秒（2-4 秒/页） |
| **效率差距** | | **Ajax 快约 100 倍** |

## Ajex 方案核心实现

- 抓包分析 B站 API：`api.bilibili.com/x/web-interface/popular`
- 构造完整浏览器请求头（User-Agent / Referer 防反爬）
- 指数退避重试机制（最多 3 次）
- JSON 解析 + 分页爬取 + CSV 导出（UTF-8-BOM）

## Selenium 方案核心实现

- ChromeDriver 自动版本匹配
- CDP 命令隐藏 webdriver 属性（反检测）
- 显式等待机制（WebDriverWait 10s）
- 页面滚动触发懒加载

## 性能对比

| 维度 | Ajax | Selenium |
|------|------|----------|
| 内存占用 | <100 MB | 300-800 MB |
| CPU 占用 | <5% | 20-40% |
| 请求次数 | 10 次 HTTP | 1 次完整页面加载 |
| 数据准确性 | 100%（直接解析 JSON）| 95%+（依赖页面结构） |

## 运行

```bash
pip install requests selenium psutil
python exp7_ajax_crawler.py
python exp7_selenium_crawler.py
python exp7_benchmark.py
```

## 结论

Ajax 方案效率优于 Selenium 约 100 倍，适合接口可抓包的场景。Selenium 兼容性更强，适合接口加密或反爬严格场景。
