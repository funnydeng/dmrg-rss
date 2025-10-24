# 文件路径和GitHub Actions配置说明

## 📁 文件路径分析

### 生成的XML和HTML文件使用的是相对路径

```python
# src/config.py
OUTPUT_RSS_PATH = "docs/rss.xml"
OUTPUT_HTML_PATH = "docs/rss.html"
CACHE_PATH = "docs/entries_cache.json"
```

**这些都是相对路径**，相对于脚本运行的**当前工作目录**（CWD）。

### 文件生成时的实际路径

当运行 `python generate_rss.py` 时：
- **CWD** = `/home/fenglindeng/bin/dmrg-rss/` (仓库根目录)
- 生成的文件：
  - `./docs/rss.xml` → `/home/fenglindeng/bin/dmrg-rss/docs/rss.xml`
  - `./docs/rss.html` → `/home/fenglindeng/bin/dmrg-rss/docs/rss.html`
  - `./docs/entries_cache.json` → `/home/fenglindeng/bin/dmrg-rss/docs/entries_cache.json`
  - `./logs/sync.log` → `/home/fenglindeng/bin/dmrg-rss/logs/sync.log`

## ✅ GitHub Actions是否需要修改？

**答案：不需要修改**

### 原因：

1. **relative paths are portable** - 相对路径在任何机器上都能工作
2. **CWD context is consistent** - GitHub Actions在仓库根目录运行
3. **generate_rss.py still at root** - 保持向后兼容

### GitHub Actions Workflow流程：

```yaml
- name: Run RSS update
  run: python generate_rss.py
```

执行流程：
```
CWD = /home/runner/work/dmrg-rss/dmrg-rss/  (Actions中的仓库根目录)
  ↓
执行: python generate_rss.py
  ↓
导入: from src.main import main
  ↓
生成文件：
  - docs/rss.xml
  - docs/rss.html
  - docs/entries_cache.json
  (都相对于CWD生成)
  ↓
提交文件到git：
  git add docs/rss.xml docs/rss.html docs/entries_cache.json
```

## 📝 新的项目结构

```
dmrg-rss/
├── generate_rss.py           ← 根目录wrapper（GitHub Actions调用这个）
├── src/                       ← 新的源代码包
│   ├── __init__.py
│   ├── config.py
│   ├── main.py
│   ├── utils/
│   │   ├── text_utils.py
│   │   ├── cache_manager.py
│   │   ├── arxiv_processor.py
│   │   └── entry_sync.py
│   └── generators/
│       ├── latex_renderer.py
│       ├── rss_generator.py
│       └── html_generator.py
├── docs/                      ← 输出目录（生成的文件）
│   ├── rss.xml
│   ├── rss.html
│   ├── entries_cache.json
│   └── index.html
├── logs/
│   └── sync.log
└── .github/
    └── workflows/
        └── update-rss.yml     ← 无需修改
```

## 🔄 相对路径工作原理示例

```bash
# 本地运行
$ cd ~/dmrg-rss
$ python generate_rss.py
✅ 文件生成在 ~/dmrg-rss/docs/

# GitHub Actions上运行
$ cd /home/runner/work/dmrg-rss/dmrg-rss
$ python generate_rss.py
✅ 文件生成在 /home/runner/work/dmrg-rss/dmrg-rss/docs/
```

## ⚙️ 配置更改（如需自定义）

如果想要改变输出路径，只需修改 `src/config.py`：

```python
# 绝对路径示例（不推荐用于GitHub Actions）
OUTPUT_RSS_PATH = "/tmp/rss.xml"

# 相对路径示例（推荐）
OUTPUT_RSS_PATH = "docs/rss.xml"
OUTPUT_RSS_PATH = "../other_location/rss.xml"
```

## 总结

| 项目 | 状态 | 备注 |
|-----|------|------|
| 文件路径类型 | ✅ 相对路径 | 可跨环境使用 |
| GitHub Actions需要修改 | ❌ 不需要 | 向后兼容 |
| generate_rss.py位置 | ✅ 根目录 | Actions可直接调用 |
| 源代码位置 | ✅ src/包 | 组织清晰 |
| workflow命令 | ✅ 无需改 | `python generate_rss.py` 保持不变 |
