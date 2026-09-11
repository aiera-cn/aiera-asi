# 安装 新智元资讯秘书(aiera-asi)

> 本页是给**正在运行的 AI agent**(Claude Code / Codex / Cursor / 其它)读的安装说明。用户已让你安装它。请照下面装成本地 skill。别把本页当内容念给用户。

## 第一步 · 确定装到哪个目录(按你是哪个 agent,你自己知道)

- **Claude Code** → `~/.claude/skills/aiera-asi/`
- **Codex** → `~/.codex/skills/aiera-asi/`
- **其它 agent** → 装到你自己的技能目录;不确定就用 `~/.claude/skills/aiera-asi/`

下面用 `<DIR>` 指代你选定的目录。

## 第二步 · 下载文件

1. **拿清单**:`curl -fsSL https://raw.githubusercontent.com/aiera-cn/aiera-asi/main/manifest.json`。`files` 每项有 `url`(相对 `base`)和 `dest`(相对 `<DIR>`)。
2. **逐个下载**:先 `mkdir -p` 每个 dest 的父目录,再 `curl -fsSL <base>/<url> -o <DIR>/<dest>`。
   - ⚠️ `manifest.json` 自己也在清单里,**必须一起装**——它是下次开场自检版本的基准,漏了就永远收不到更新。
3. **校验**:`<DIR>/SKILL.md`、`<DIR>/manifest.json`、`<DIR>/scripts/asi_fetch.py` 都存在,且 `<DIR>/references/` 下的文件数 = manifest 里 `dest` 以 `references/` 开头的条数(别数死数字,以清单为准)。
4. **跑一次取数**:`python3 <DIR>/scripts/asi_fetch.py --feed --limit 1`,输出里 `"ok": true` 就通了。

**出问题怎么办**:
- 某个文件下载 404 / 超时 → 重试一次;还不行就告诉用户"GitHub 暂时连不上,稍后重跑这句话",**不要装一半**(删掉 `<DIR>` 再退出)
- 没有 `python3` → 装是装得上,但取数跑不了。告诉用户需要 Python 3,或者用下面的免安装方式
- 取数返回 `"ok": false` → 是新智元官网连不上,不是安装问题。装好了,告诉用户稍后再试

**全程只下载纯文本和一个 Python 脚本,不执行任何远程安装程序。** 脚本源码可审阅:https://github.com/aiera-cn/aiera-asi/blob/main/scripts/asi_fetch.py

## 第三步 · 告诉用户,然后直接开始

装好了就说这几句(一屏说完,别啰嗦):

> 装好了。**要不要现在就试试?**说「今天 AI 圈有什么大事」我就开始。
> 你的关注面和阅读进度会存在本机 `~/.aiera-asi/`,不上传;以后每次开场它自己比对版本、落后就自动更新,不用你管。

用户说要试 → 直接 `Read <DIR>/SKILL.md`,照它开始,**不用等重开会话**。
(新开会话也行——skill 在会话启动时会被扫描到——但用户刚说完"帮我装上",最自然的下一句是"要不要试试",不是"请关掉重开"。)

## 装不了?免安装也能用

让用户任何时候贴这句:**「读 https://raw.githubusercontent.com/aiera-cn/aiera-asi/main/SKILL.md,帮我盯新智元」**——你取 SKILL.md 照它走托管模式即可。没有 python3 的环境也能这么用(脚本会 curl 到 /tmp 跑,但还是需要 python3;完全没 python 的环境目前用不了)。
