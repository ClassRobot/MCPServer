# HTML Fixtures

这里放离线 HTML fixture，用来验证搜索结果解析与过滤逻辑。

## 使用原则

- 只保留最小必要结构
- 优先表达页面结构差异，而不是复制整页 HTML
- 一个 fixture 服务一个主要测试场景

## 当前场景

- `bing_results.html`: 正常自然结果页
- `bing_ads.html`: 混有广告候选结果
- `bing_empty.html`: 空结果页
