---
title: 智能体把工作区改坏了？一个不碰 git 的撤销办法
description: 编码智能体会改文件、删文件，连 git 没跟踪的文件也不放过。agentckpt 把整个工作区快照进一个私有的影子仓库，恢复时不动你的分支和暂存区。
---

# 智能体把工作区改坏了？一个不碰 git 的撤销办法

*2026 年 10 月 · [English](agent-undo-without-touching-git.md)*

让 Codex、Claude Code、Gemini CLI、OpenCode 或者 Cursor 的智能体跑一个任务，几分钟后它改了十几个文件，删了两个，又新建了几个。结果不对，你想让工作区回到这一轮开始之前的样子。

按理说这是 git 的活。真做起来，常常没那么顺。

## 现有办法为什么不够用

**自带的 `/undo` 要么没有，要么靠不住。** Codex 已经把 `/undo` 去掉了，要求恢复可靠回滚的 [openai/codex#9203](https://github.com/openai/codex/issues/9203) 有 522 个 👍，到现在还开着。V2EX 上也有不少人吐槽同样的事，比如 [1218209](https://www.v2ex.com/t/1218209) 和 [1220282](https://www.v2ex.com/t/1220282)。

**没被跟踪的文件，git 根本管不着。** 智能体经常动一些 git 从没见过的文件：随手记的笔记、还没 `git add` 的新模块、正在调的配置。`git checkout -- .`、`git restore` 只认已跟踪的内容。智能体要是把一个未跟踪文件删了，git 里压根没有它的副本。

**`git stash` 和 WIP 提交会碰到你在意的东西。** 它们要经过你的暂存区、reflog，很多时候还有当前分支。每轮之前提交一个 "wip before agent"，最后得花时间清理历史；而一个改到一半、跑不起来的工作区，本来就不该进分支。

真正需要的其实很朴素：在智能体动手之前（或者干活的过程中），把整个工作区连同未跟踪文件一起存一份，需要时原样写回磁盘，而且 git 那边什么都不知道。

## agentckpt 怎么做

agentckpt 是一个小命令行工具，在项目里的 `.agentckpt/` 下维护一个**私有的影子 git 仓库**。它调用 git 的方式都是这样的：

```bash
git --git-dir=.agentckpt/git --work-tree=<项目根目录> ...
```

也就是说，快照用的还是 git 那一套（按内容寻址、自动去重、能 diff），但它是一个**独立**的仓库，有自己的暂存区和历史。你真正的 `.git` 从来不会被 `add`、`commit`、`checkout`，分支也不会被移动。

具体来说：

- **`init`**：创建 `.agentckpt/`，并在 `.gitignore` 末尾加上 `.agentckpt/`，保证这个目录不会被提交进你的仓库。影子仓库内部也会排除 `.agentckpt/` 和 `.git/`。
- **`snap`**：把工作区里的所有文件放进影子仓库的暂存区（已跟踪、未跟踪都算，遵守你的 `.gitignore`），默认跳过超过 10 MiB 的文件，然后在影子仓库里提交。如果和上一个快照相比没有变化，就直接返回上一个，不会产生空快照。
- **`restore <id>`**：从快照里逐个读出文件，把字节直接写回工作区，不做任何 checkout。如果磁盘上已有的文件和快照里的不一样，默认**跳过它并以退出码 1 结束**，加 `--force` 才会覆盖。`.git/` 和 `.agentckpt/` 里的路径永远不会被写入。
- **`watch`**：用标准库轮询工作区（不依赖 watchdog），文件列表、修改时间或大小一变就自动拍一张，智能体干活的过程中也有恢复点。
- **`diff`**、**`ls`**、**`prune`**、**`doctor`** 的作用顾名思义。大部分命令支持 `--json`；退出码 `0` 成功，`1` 部分失败（比如有冲突被跳过），`2` 硬错误。

整个包是纯 Python（3.9+），没有任何运行时依赖，只要 `PATH` 里有 `git`。CI 覆盖 Linux（Python 3.9 到 3.13）、macOS 和 Windows。

## 安装

agentckpt **目前还没有发布到 PyPI**。v0.1.0 的 wheel 和 sdist 放在 [GitHub Releases](https://github.com/Blackman99/agentckpt/releases/tag/v0.1.0) 上，可以直接装 wheel：

```bash
pipx install https://github.com/Blackman99/agentckpt/releases/download/v0.1.0/agentckpt-0.1.0-py3-none-any.whl
# 或者：pip install <同一个链接>
agentckpt --version   # agentckpt 0.1.0
```

不想装的话，也可以直接从仓库跑：

```bash
uvx --from git+https://github.com/Blackman99/agentckpt agentckpt demo
```

`agentckpt demo` 会在临时目录里建一个小项目，拍快照、故意改坏、再恢复，顺便验证冲突规则、prune 和 `doctor`。CI 里跑的也是这一套。

## 上手

```bash
cd your-project
agentckpt init
agentckpt snap -m "before agent"

# ……智能体改文件、删文件、加文件……

agentckpt ls                       # 列出快照，最新的在前
agentckpt diff <id>                # 看看从那个快照之后改了什么
agentckpt restore <id>             # 写回文件，跳过现在内容不同的
agentckpt restore <id> --force     # 写回文件，内容不同的也覆盖
agentckpt restore <id> --path src/ # 只恢复某个子目录
```

下面是一个小仓库里的实际输出：智能体改了 `a.txt`，还删掉了一个未跟踪的 `untracked.md`：

```text
$ agentckpt restore b66469f
Skipped 1 conflict(s) (working tree differs; re-run with --force to overwrite):
  ! a.txt
Restored 2 file(s) from b66469f
  + .gitignore
  + untracked.md

$ agentckpt restore b66469f --force
Restored 3 file(s) from b66469f
  + .gitignore
  + a.txt
  + untracked.md
```

被删的未跟踪文件回来了，真实仓库的 `git log` 一条没变。

跑得比较久的任务，可以在另一个终端开着 `agentckpt watch`（`--debounce` 默认 800 毫秒轮询一次）。快照多了用 `agentckpt prune --keep 50` 清一清。

## 目前的局限（v0.1.0）

有些事它现在不做，先说清楚：

- **恢复不会删文件。** 它只把快照里有的写回去。快照之后智能体**新建**的文件还会留在磁盘上，可以用 `agentckpt diff <id>` 找出来自己删。
- **快照里没有的，恢复不了。** 被 `.gitignore` 忽略的文件、超过 10 MiB 的文件（可用 `--max-bytes` 调整）都不会存。这是故意的（不想把 `node_modules`、构建产物塞进去），但也意味着它们没法恢复。
- **`watch` 是轮询，不是钩子。** 它在发现变化时拍快照，可能正好拍到写了一半的状态。最干净的恢复点还是每轮开始前手动 `snap` 一次。给 Codex、Claude Code、OpenCode、Gemini CLI 用的钩子配置在 [路线图](https://github.com/Blackman99/agentckpt/blob/main/ROADMAP.md) 的 v0.2 里。
- **快照存在项目目录里。** `.agentckpt/` 是被 gitignore 的，所以 `git clean -fdx` 这类命令（或者直接删掉项目目录）会把快照一起清掉。它是撤销缓冲，不是备份。
- **会改一行 `.gitignore`。** `init` 会追加 `.agentckpt/`。这是它对你的文件唯一的改动，目的是防止影子仓库被误提交。
- **还没有交互式/选择性恢复界面、存储配额和 MCP 服务。** 这些分别排在路线图的 v0.3 和 v0.4；发布到 PyPI、冻结 JSON 格式计划在 v1.0。

## 试一下

```bash
uvx --from git+https://github.com/Blackman99/agentckpt agentckpt demo
```

文档：[blackman99.github.io/agentckpt/docs](https://blackman99.github.io/agentckpt/docs/) · 源码（MIT）：[github.com/Blackman99/agentckpt](https://github.com/Blackman99/agentckpt)。欢迎提 issue，也欢迎分享你给各家智能体配的钩子。
