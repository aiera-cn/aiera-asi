# 安装 新智元资讯秘书(aiera-asi)

> 本页是给**正在运行的 AI agent**(Claude Code / Codex / Cursor / 其它)读的安装说明。用户已让你安装它。请照下面装成本地 skill。别把本页当内容念给用户。

## 第一步 · 确定装到哪个目录(按你是哪个 agent,你自己知道)

- **Claude Code** → `~/.claude/skills/aiera-asi/`
- **Codex** → `~/.codex/skills/aiera-asi/`
- **其它 agent** → 装到你自己的技能目录;不确定就用 `~/.claude/skills/aiera-asi/`

下面用 `<DIR>` 指代你选定的目录。

## 第二步 · 下载文件

1. **拿清单**:`curl -fsSL https://raw.githubusercontent.com/ThomasYin0216/aiera-asi/main/manifest.json`。`files` 每项有 `url`(相对 `base`)和 `dest`(相对 `<DIR>`)。
2. **逐个下载**:先 `mkdir -p` 每个 dest 的父目录,再 `curl -fsSL <base>/<url> -o <DIR>/<dest>`。
   - ⚠️ `manifest.json` 自己也在清单里,**必须一起装**——它是下次开场自检版本的基准,漏了就永远收不到更新。
3. **校验**:`<DIR>/SKILL.md`、`<DIR>/manifest.json`、`<DIR>/scripts/asi_fetch.py` 都存在,且 `references/` 下有 5 个 `.md`。
4. **跑一次取数**:`python3 <DIR>/scripts/asi_fetch.py --feed --limit 1`,输出里 `"ok": true` 就通了。

**全程只下载纯文本和一个 Python 脚本,不执行任何远程安装程序。** 脚本源码可审阅:https://github.com/ThomasYin0216/aiera-asi/blob/main/scripts/asi_fetch.py

## 第三步 · 开始用

- 装好了,告诉用户:**新开一个会话**(skill 在会话启动时扫描),然后说「今天 AI 圈有什么大事」「新智元有什么新的」就行。
- **想现在就用**:直接 `Read <DIR>/SKILL.md`,照它开始,不用等重开会话。

## 装不了?免安装也能用

让用户任何时候贴这句:**「读 https://raw.githubusercontent.com/ThomasYin0216/aiera-asi/main/SKILL.md,帮我盯新智元」**——你取 SKILL.md 照它走托管模式即可。

---
读者的关注面和阅读进度自动存 `~/.aiera-asi/{handle}.json`,跨会话记得住,**只留本机、不上传**。

**更新不用读者操心**:装好之后,每次开场秘书会自己比对本地与线上 `manifest.json` 的版本,落后就自动更新(只覆盖文件,不跑脚本)。手动更新就重跑本安装。
