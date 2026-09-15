#!/usr/bin/env python3
"""取新智元 ASI 爆点数据,输出 JSON 到 stdout。

数据目前内嵌在首页的 JS 数组里(var FEED / var BOARD / var STORIES),
官网 /asi/*.json 出口上线后,把 fetch_live() 换成直接取 JSON 即可,其余不动。

用法:
    python3 asi_fetch.py                    # 秒追流 + 爆点榜,各 10 条
    python3 asi_fetch.py --feed             # 只要秒追流
    python3 asi_fetch.py --board            # 只要爆点榜
    python3 asi_fetch.py --feed --limit 30  # 要更多条
    python3 asi_fetch.py --articles         # ASI 启示录深度稿(有真链接)
    python3 asi_fetch.py --search DeepSeek  # 在全站 6000+ 篇里搜(默认最近的在前)
    python3 asi_fetch.py --search AlphaGo --oldest         # 翻最早的 —— 十一年从这儿拿
    python3 asi_fetch.py --search OpenAI --from 2023-11-15 --to 2023-11-25   # 某一周
    python3 asi_fetch.py --search IPO,减速,越狱  # 一次搜多个词(逗号分隔),结果合并去重
    python3 asi_fetch.py --self-update       # 比对线上版本,落后就覆盖文件(不跑任何远程脚本)
    python3 asi_fetch.py --feedback "他的原话"   # 读者说这条不对/不像你 —— 记进本机 feedback.jsonl
    python3 asi_fetch.py --stats             # 这个读者用了几次、追了什么 —— 读 me.json 的 log
    python3 asi_fetch.py --export            # 把存档打印出来(换机器时用)
    python3 asi_fetch.py --import 文件.json  # 把另一台机器的存档合并进来

默认只取 10 条:全量 60 条约 14K tokens,日常问答不需要那么多。
"""
import json, os, re, sys, time, urllib.request
from datetime import datetime, timedelta, timezone

TZ_CST = timezone(timedelta(hours=8))

HOME = "https://www.aiera.com.cn/"
COLUMN_URL = "https://www.aiera.com.cn/#secBaodian"
RSS = "https://www.aiera.com.cn/feed"
WP = "https://aiera.com.cn/wp-json/wp/v2/posts"
POST_URL = "https://www.aiera.com.cn/asi-post.html?id="
ITEM_URL = "https://www.aiera.com.cn/asi-item.html?id="   # 秒追单条详情页
TRACK = "&from=yuanyuan"   # 导流可追踪:官网后台按这个参数分流量。页面 JS 只读 id,多这个参数不影响(已实测)


CACHE = os.path.join(os.path.expanduser("~"), ".aiera-asi", ".cache-home.html")
CACHE_TTL = 300   # 同一会话里多轮追问,5 分钟内不重复下 108KB 首页


def fetch_live():
    try:
        if time.time() - os.path.getmtime(CACHE) < CACHE_TTL:
            return open(CACHE, encoding="utf-8").read()
    except OSError:
        pass
    req = urllib.request.Request(HOME, headers={"User-Agent": "Mozilla/5.0"})
    html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
    try:
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        open(CACHE, "w", encoding="utf-8").write(html)
    except OSError:
        pass
    return html


def grab_array(html, name):
    """抓 var NAME=[...] —— 括号配平,别用贪婪正则(标题里有 [ ] 会咬穿)"""
    m = re.search(r"\bvar\s+%s\s*=\s*" % name, html)
    if not m or html[m.end()] != "[":
        return None
    i = m.end()
    depth, j, instr, esc = 0, m.end(), None, False
    while j < len(html):
        c = html[j]
        if instr:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == instr:
                instr = None
        elif c in "\"'":
            instr = c
        elif c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                return json.loads(html[i:j + 1])
        j += 1
    return None


def norm_feed(rows):
    """FEED 是七元组: [时间, 日期, 标题, 摘要, 来源, 内部id, 权重]"""
    out = []
    for r in rows or []:
        if len(r) < 6:
            continue
        out.append({
            "time": r[0], "date": r[1], "title": r[2], "summary": r[3],
            "source": r[4], "id": r[5], "weight": r[6] if len(r) > 6 else None,
            # 每条都有详情页(页面用 JS 渲染成 <a href="asi-item.html?id=...">)
            "url": ITEM_URL + str(r[5]) + TRACK, "column_url": COLUMN_URL,
        })
    return out


def norm_board(rows):
    """BOARD 是对象数组: t=标题 p=摘要 rd=阅读数 ago=多久前 cat=分类"""
    out = []
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        q = r.get("q") or {}
        out.append({
            "title": r.get("t"), "summary": r.get("p"), "reads": r.get("rd"),
            "ago": r.get("ago"), "category": r.get("cat"), "source": r.get("src") or "新智元",
            "bullets": r.get("b") or [],          # 要点列表
            "quote": {"who": q.get("a"), "role": q.get("r"), "said": q.get("x")} if q else None,
            "tag": r.get("nt") or None,           # 热度标记
            "story": r.get("story") or None,      # 所属故事线
            # 爆点榜在页面上是 <details> 折叠块,原地展开不跳转 —— 没有独立网址
            "url": None, "column_url": COLUMN_URL,
        })
    return out


def fetch_articles(limit=10, query=None, oldest=False, date_from=None, date_to=None):
    """ASI 启示录(深度稿)。来自 WordPress,每篇有干净链接 asi-post.html?id=

    只取摘要,不取全文 —— 深度稿是核心资产,引导读者回官网看。
    oldest=True 按时间正序(翻最早的);date_from/date_to 限定日期范围(YYYY-MM-DD)。
    这两个是元元"十一年"能不能拿出来的关键 —— 默认只返回最近的,2016 年的稿子永远翻不到。
    """
    import html as _html
    from urllib.parse import quote

    url = f"{WP}?per_page={min(limit, 50)}&_fields=id,date,title,excerpt"
    if query:
        url += f"&search={quote(query)}"
    if oldest:
        url += "&order=asc&orderby=date"
    if date_from:
        url += f"&after={date_from}T00:00:00"
    if date_to:
        url += f"&before={date_to}T23:59:59"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        total = int(r.headers.get("X-WP-Total") or 0)
        rows = json.loads(r.read())

    def clean(x):
        return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", "", x or ""))).strip()

    out = []
    for p_ in rows:
        title = clean(p_["title"]["rendered"])
        d = p_["date"]
        out.append({
            "id": p_["id"],
            # 深度稿 date 直接带年份 —— 翻档案时"2016/01/31"和"09/11"是两个世界
            "date": d[:10].replace("-", "/"), "time": d[11:16],
            "year": d[:4], "title": title,
            "summary": clean(p_["excerpt"]["rendered"]),
            "url": POST_URL + str(p_["id"]) + TRACK,
            # WP 是全文搜索,标题没命中的是"正文提到" —— 必须让读者分得清
            "title_hit": bool(query) and query.lower() in title.lower(),
        })
    if query:
        out.sort(key=lambda x: not x["title_hit"])   # 标题命中的排前面
    return out, total


def rss_fallback():
    """首页结构变了就退回 RSS。

    注意:RSS 是**全站文章流**(深度稿/论文稿/会议稿),不是 ASI 爆点快讯。
    栏目不同,署名和链接都得跟着换 —— 详见 main() 里降级分支的 note。
    """
    import xml.etree.ElementTree as ET
    from email.utils import parsedate_to_datetime

    req = urllib.request.Request(RSS, headers={"User-Agent": "Mozilla/5.0"})
    ch = ET.fromstring(urllib.request.urlopen(req, timeout=30).read()).find("channel")

    items = []
    for it in ch.findall("item"):
        raw = it.findtext("pubDate")
        # RSS 的 pubDate 是 +0000,爆点流是北京时间。不归一就会把凌晨讲成早上。
        try:
            cst = parsedate_to_datetime(raw).astimezone(TZ_CST)
            date, time_ = cst.strftime("%m/%d"), cst.strftime("%H:%M")
        except Exception:
            date, time_ = None, None
        items.append({
            "title": it.findtext("title"), "summary": (it.findtext("description") or "").strip(),
            "date": date, "time": time_, "tz": "Asia/Shanghai (已从 RSS 的 +0000 换算)",
            "pub_date_raw": raw, "url": (it.findtext("link") or "") + ("&" if "?" in (it.findtext("link") or "") else "?") + TRACK.lstrip("&"),
            "source": "新智元(官网 RSS · 全站文章流)",
        })
    return items


def _get(url, tries=3):
    """GitHub 在国内时不时 30 秒超时,重试三次"""
    last = None
    for _ in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            return urllib.request.urlopen(req, timeout=30).read()
        except Exception as e:
            last = e; time.sleep(2)
    raise last


def self_update():
    """第〇步:比对本地/线上 manifest,落后就按清单逐个覆盖。只覆盖文件,不执行任何远程程序。"""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        local = json.load(open(os.path.join(root, "manifest.json"), encoding="utf-8"))
        lv = local["version"]
    except Exception:
        local, lv = {"base": "https://raw.githubusercontent.com/aiera-cn/aiera-asi/main"}, "0.0.0"
    try:
        remote = json.loads(_get(f"{local['base']}/manifest.json?t={int(time.time())}"))
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"取线上 manifest 失败: {e}", "hint": "静默跳过,照常服务"}, ensure_ascii=False))
        return 1
    rv = remote["version"]
    ver = lambda v: tuple(int(x) for x in v.split("."))
    if ver(lv) >= ver(rv):
        print(json.dumps({"ok": True, "updated": False, "version": lv}, ensure_ascii=False))
        return 0
    done = []
    for f in remote["files"]:
        dest = os.path.join(root, f["dest"])
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        try:
            open(dest, "wb").write(_get(f"{remote['base']}/{f['url']}"))
            done.append(f["dest"])
        except Exception as e:
            print(json.dumps({"ok": False, "error": f"下载 {f['dest']} 失败: {e}", "partial": done,
                              "hint": "更新了一半,本次照旧服务,下次开场再试"}, ensure_ascii=False))
            return 1
    print(json.dumps({"ok": True, "updated": True, "from": lv, "to": rv,
                      "whats_new": remote.get("whats_new", ""), "files": len(done)}, ensure_ascii=False))
    return 0


KNOWN = {"--feed", "--board", "--all", "--articles", "--search", "--oldest",
         "--from", "--to", "--limit", "--self-update",
         "--feedback", "--stats", "--export", "--import"}

STATE_DIR = os.path.join(os.path.expanduser("~"), ".aiera-asi")
STATE = os.path.join(STATE_DIR, "me.json")
FEEDBACK = os.path.join(STATE_DIR, "feedback.jsonl")


def _load_state():
    try:
        return json.load(open(STATE, encoding="utf-8"))
    except Exception:
        return None


def cmd_feedback(text):
    """A2:读者的反馈落本机,不上传。老尹定期收。"""
    os.makedirs(STATE_DIR, exist_ok=True)
    try:
        ver = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "manifest.json")))["version"]
    except Exception:
        ver = "?"
    rec = {"at": datetime.now(TZ_CST).strftime("%Y-%m-%d %H:%M"), "version": ver, "text": text}
    with open(FEEDBACK, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    n = sum(1 for _ in open(FEEDBACK, encoding="utf-8"))
    print(json.dumps({"ok": True, "saved": FEEDBACK, "count": n}, ensure_ascii=False))
    return 0


def cmd_stats():
    """A3:这个读者的使用统计,读 me.json 和 feedback.jsonl。"""
    st = _load_state()
    if not st:
        print(json.dumps({"ok": True, "sessions": 0, "note": "还没有存档,新读者"}, ensure_ascii=False))
        return 0
    try:
        fb = sum(1 for _ in open(FEEDBACK, encoding="utf-8"))
    except Exception:
        fb = 0
    out = {"ok": True, "first_seen": st.get("first_seen"), "last_seen": st.get("last_seen"),
           "sessions": len(st.get("log", [])), "focus": st.get("focus"),
           "interests": len(st.get("interests", [])), "asked": len(st.get("asked", [])),
           "last_briefed": st.get("last_briefed"), "feedback_count": fb}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def cmd_export():
    """A4:打印存档,换机器时贴过去。"""
    st = _load_state()
    if not st:
        print(json.dumps({"ok": False, "error": "没有存档"}, ensure_ascii=False)); return 1
    print(json.dumps(st, ensure_ascii=False, indent=2))
    return 0


def cmd_import(path):
    """A4:把另一台机器的存档合并进来。取并集,时间取新的,原存档备份。"""
    try:
        new = json.load(open(path, encoding="utf-8"))
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"读不了 {path}: {e}"}, ensure_ascii=False)); return 1
    old = _load_state() or {}
    if old:
        import shutil
        shutil.copy(STATE, STATE + ".bak-" + datetime.now(TZ_CST).strftime("%Y%m%d-%H%M"))
    def union(a, b):
        return list(dict.fromkeys((a or []) + (b or [])))
    def later(a, b):
        if not a: return b
        if not b: return a
        return b if (b.get("date",""), b.get("time","")) > (a.get("date",""), a.get("time","")) else a
    merged = {
        "handle": old.get("handle") or new.get("handle") or "me",
        "context": max([old.get("context",""), new.get("context","")], key=len),
        "first_seen": min(x for x in [old.get("first_seen"), new.get("first_seen")] if x) if (old.get("first_seen") or new.get("first_seen")) else None,
        "last_seen": max(x for x in [old.get("last_seen"), new.get("last_seen")] if x) if (old.get("last_seen") or new.get("last_seen")) else None,
        "focus": union(old.get("focus"), new.get("focus")),
        "focus_official": union(old.get("focus_official"), new.get("focus_official")),
        "interests": union(old.get("interests"), new.get("interests")),
        "not_interested": union(old.get("not_interested"), new.get("not_interested")),
        "last_briefed": later(old.get("last_briefed"), new.get("last_briefed")),
        "asked": list({a["q"]: a for a in (old.get("asked",[]) + new.get("asked",[]))}.values()),
        "log": sorted(union(old.get("log"), new.get("log"))),
    }
    os.makedirs(STATE_DIR, exist_ok=True)
    json.dump(merged, open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(json.dumps({"ok": True, "merged_into": STATE, "interests": len(merged["interests"]),
                      "log": len(merged["log"]), "backup": bool(old)}, ensure_ascii=False))
    return 0


def main():
    args = sys.argv[1:]
    bad = [a for a in args if a.startswith("--") and a not in KNOWN]
    if bad:
        # 未知参数不能静默落到默认输出 —— agent 打错一个字会拿到一整屏 feed 还以为对了
        print(json.dumps({"ok": False, "error": f"不认识的参数: {' '.join(bad)}",
                          "known": sorted(KNOWN)}, ensure_ascii=False))
        return 1
    if "--self-update" in args:
        return self_update()
    if "--stats" in args:
        return cmd_stats()
    if "--export" in args:
        return cmd_export()
    for flag, fn in (("--feedback", cmd_feedback), ("--import", cmd_import)):
        if flag in args:
            try:
                return fn(args[args.index(flag) + 1])
            except IndexError:
                print(json.dumps({"ok": False, "error": f"{flag} 后面要跟内容"}, ensure_ascii=False)); return 1
    want = next((a for a in args if a in ("--feed", "--board", "--all", "--articles")), "--all")
    query = None
    if "--search" in args:
        try:
            query = args[args.index("--search") + 1]
            want = "--articles"
        except IndexError:
            print(json.dumps({"ok": False, "error": "--search 后面要跟关键词"}, ensure_ascii=False))
            return 1
    oldest = "--oldest" in args
    date_from = date_to = None
    for flag, var in (("--from", "date_from"), ("--to", "date_to")):
        if flag in args:
            try:
                v = args[args.index(flag) + 1]
                if not re.match(r"^\d{4}-\d{2}-\d{2}$", v):
                    raise ValueError
                if var == "date_from": date_from = v
                else: date_to = v
                want = "--articles"
            except (IndexError, ValueError):
                print(json.dumps({"ok": False, "error": f"{flag} 后面要跟 YYYY-MM-DD"}, ensure_ascii=False))
                return 1
    if oldest:
        want = "--articles"
    limit = 10
    if "--limit" in args:
        try:
            limit = int(args[args.index("--limit") + 1])
        except (IndexError, ValueError):
            print(json.dumps({"ok": False, "error": "--limit 后面要跟一个数字"},
                             ensure_ascii=False))
            return 1
    if want == "--articles":
        now = datetime.now(TZ_CST)
        # A1:逗号分隔多个词,各搜一次,合并去重 —— 老读者开场搜 interests 里几个词不用跑几趟
        queries = [q.strip() for q in query.split(",") if q.strip()] if query else [None]
        arts, totals, seen = [], {}, set()
        try:
            for q in queries:
                part, total = fetch_articles(limit, q, oldest, date_from, date_to)
                totals[q or "_"] = total
                for a in part:
                    if a["id"] in seen:
                        continue
                    seen.add(a["id"])
                    if q:
                        a["matched_query"] = q
                    arts.append(a)
        except Exception as e:
            print(json.dumps({"ok": False, "error": f"取深度稿失败: {e}",
                              "hint": "如实告诉用户连不上,不要用模型记忆代替。"},
                             ensure_ascii=False))
            return 1
        if query:
            arts.sort(key=lambda x: not x["title_hit"])
        res = {"ok": True, "source": "新智元 ASI 启示录(深度稿)",
               "fetched_at": now.strftime("%Y-%m-%d %H:%M:%S %z"),
               "today": now.strftime("%m/%d"),
               "articles": arts, "articles_count": len(arts),
               "note": "深度稿**只给摘要 + 链接,不给全文** —— 想看全文引导读者点链接回官网。"}
        if oldest:
            res["order"] = "最早在前(--oldest)"
        if date_from or date_to:
            res["date_range"] = f"{date_from or '…'} ~ {date_to or '…'}"
        if query:
            hits = sum(1 for a in arts if a["title_hit"])
            res["query"] = query
            res["queries"] = queries
            res["total_matched"] = totals if len(queries) > 1 else totals[queries[0]]
            res["title_hits_in_page"] = hits
            res["note"] += (
                f" ⚠️ 这是**全文搜索**不是标题搜索:本页 {len(arts)} 篇里只有 {hits} 篇标题真的命中(已排在前面),"
                "其余只是正文提到。**按发布时间倒序,不是相关度排序**——"
                "回答时要说清这个区别,别让读者以为这就是最相关的几篇。"
                + (f" 多个词分别搜、合并去重,每篇的 matched_query 是它命中的那个词。" if len(queries) > 1 else ""))
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0

    try:
        html = fetch_live()
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"取首页失败: {e}",
                          "hint": "取数失败。如实告诉用户连不上新智元,然后停止。"
                          "不要用模型记忆,也不要绕过本脚本自行抓取——"
                          "curl / WebFetch / requests / import 本脚本的函数,全都不行。"
                          "如果是脚本本身有 bug,只报告 bug,不要代替脚本取数。"},
                         ensure_ascii=False))
        return 1

    feed = norm_feed(grab_array(html, "FEED"))
    board = norm_board(grab_array(html, "BOARD"))

    if not feed and not board:
        try:
            items = rss_fallback()
            now = datetime.now(TZ_CST)
            print(json.dumps({
                "ok": True, "degraded": "rss",
                "source": "新智元(官网 RSS · 全站文章流)",
                "fetched_at": now.strftime("%Y-%m-%d %H:%M:%S %z"),
                "today": now.strftime("%m/%d"),
                "board_available": False,
                "items_total": len(items),
                "items": items[:limit],
                "note": (
                    "首页数据结构已变,退回全站 RSS。必须在答复正文开头声明这是降级数据。"
                    "⚠️ 这批**不是 ASI 爆点快讯**,是全站文章流(含深度稿/论文稿/会议稿)。"
                    "所以:署名写「来源:新智元(官网 RSS)」,不要写「ASI 爆点」;"
                    "链接给每条自己的 url,不要挂 #secBaodian。"
                    "爆点榜本次不可用(board_available=false)。用户问「什么最火」时,"
                    "禁止给出任何暗示重要性/热度/传播量高低的排列,包括标注为「我的判断」的个人排序。"
                    "可以按发布时间列,也可以按主题归类——但必须写明排列依据,并声明它不代表热度。"
                    "另外:这批只有 15 条,正常秒追流约 60 条,要告诉用户这次能看到的比平时少得多。"
                    "整个回答里不要用「爆点」指代这批内容——它们不是爆点快讯。"
                ),
            }, ensure_ascii=False, indent=2))
            return 0
        except Exception as e:
            print(json.dumps({"ok": False, "error": f"首页结构已变且 RSS 也取不到: {e}"},
                             ensure_ascii=False))
            return 1

    now = datetime.now(TZ_CST)   # 统一北京时间 —— GitHub Actions 跑在 UTC 机器上,用本机时区 today 会错一天
    result = {"ok": True, "source": "新智元 ASI 爆点", "home": HOME,
              "column_url": COLUMN_URL,
              # date 字段只有 09/10 没有年份,agent 靠这个判断哪天算"今天"
              "fetched_at": now.strftime("%Y-%m-%d %H:%M:%S %z"),
              "today": now.strftime("%m/%d"),
              "note": "秒追流每条都有详情页 url,直接给。爆点榜是页面上的折叠块、无独立网址(url=null),引用时给栏目链接并说明在榜第几位。"
                      "*_total 是页面当前挂载的总条数(秒追流约覆盖最近 3 天),不是栏目历史总量。"}
    if want in ("--all", "--feed"):
        result["feed"] = feed[:limit]
        result["feed_count"] = len(feed[:limit])
        result["feed_total"] = len(feed)
    if want in ("--all", "--board"):
        result["board"] = board[:limit]
        result["board_count"] = len(board[:limit])
        result["board_total"] = len(board)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
