# 数据源地图

## 当前(v0.1)

情报数据内嵌在首页 `https://www.aiera.com.cn/` 的 JS 数组里,由官网的 `site_baodian.py` 生成。
`scripts/asi_fetch.py` 负责提取和规范化,**你只跟脚本的 JSON 输出打交道**,不用自己解析 HTML。

## 字段含义

### `feed` —— 秒追 ASI(滚动情报流,最近约 3 天)

| 字段 | 含义 | 注意 |
|---|---|---|
| `time` | 发布时刻,如 `15:55` | 当天时间,不含日期 |
| `date` | 日期,如 `09/10` | **没有年份**,按当前年理解 |
| `title` | 情报标题 | |
| `summary` | 一两句摘要 | 这就是全文,爆点本来就短 |
| `source` | 信源 | 多为"新智元",也可能是外部信源 |
| `id` | 条目标识 | 也是详情页的 URL 参数,但**不要自己拼**,用现成的 `url` 字段 |
| `weight` | 权重 | 用途未确认,别据此下结论 |
| `url` | **详情页真链接** | `asi-item.html?id=` —— 直接给读者,已实测可打开 |

### `board` —— 爆点榜(24 小时窗口)

| 字段 | 含义 |
|---|---|
| `title` | 标题 |
| `summary` | 摘要,通常比 feed 长 |
| `bullets` | **要点列表**,几条干货,讲深时很有用 |
| `quote` | **引语** `{who 谁说的, role 什么身份, said 说了什么}` |
| `reads` | 阅读数,如 `1096万` |
| `ago` | 相对时间,如 `3 小时前` |
| `category` | 官方分类,如 `产品与生态` |
| `tag` / `story` | 热度标记 / 所属故事线(可能为 null) |
| `url` | **恒为 `null`** —— 爆点榜在官网上是折叠块,原地展开不跳转,没有独立网址。给栏目页 + 说明"在榜第 N 位" |

**feed 和 board 是两套数据**,同一件事可能都出现,措辞不同。board 有分类和阅读量,回答"什么最火"用它。

## 时间字段(判断"今天"靠它)

| 字段 | 含义 |
|---|---|
| `fetched_at` | 本次抓取的完整时间戳,**带年份和时区** |
| `today` | 抓取当天的日期,格式与 feed 的 `date` 一致(如 `09/10`) |

feed 里的 `date` **没有年份**。要判断哪条算"今天",拿它跟 `today` 比,别靠自己推测当前日期。

### `articles` —— ASI 启示录深度稿(`--articles` / `--search`)

| 字段 | 含义 |
|---|---|
| `id` | WordPress 文章 ID |
| `date` / `time` / `full_date` | 发布时间 |
| `title` / `summary` | 标题与摘要(**摘要就是全部,不取正文**) |
| `url` | **真链接** `asi-post.html?id=` —— 直接给读者 |
| `title_hit` | 仅搜索时有:`true` = 标题真的命中;`false` = **只是正文提到** |

搜索时还有 `total_matched`(全站命中总数)和 `title_hits_in_page`。
⚠️ WordPress 的 search 是**全文搜索 + 按时间倒序**,不是相关度排序。搜「DeepSeek」会命中 500+ 篇正文提过的文章,其中标题真命中的可能一篇都没有。**回答时必须讲清这个区别**,否则读者会以为这就是最相关的几篇。

## 计数字段

- `feed_count` / `board_count` —— 本次实际返回条数(受 `--limit` 影响)
- `feed_total` / `board_total` —— 页面**当前挂载**的总条数。秒追流约覆盖最近 3 天,**不是栏目历史总量**(栏目首页显示的"71 个爆点事件"是另一个口径,别混)

用户想看更多时,用 `--limit` 再取一次,别假装你看过全部。

## 未来(v0.2,官网数据出口上线后)

官网会提供 `/asi/today.json`、`/asi/board.json`、`/asi/coordinates.json`、`/asi/archive/YYYY-MM-DD.json`。
届时只改 `asi_fetch.py` 的 `fetch_live()`,本文件和 SKILL.md 的用法都不变。
