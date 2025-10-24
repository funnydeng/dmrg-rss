# 双文件缓存策略

## 概述

DMRG RSS生成器现在采用**双文件缓存策略**，以便更好地管理和备份条目数据。

## 缓存文件说明

### 1. `entries_latest.json` (最新缓存)
- **用途**: 当前工作缓存，存储所有已处理的条目
- **更新频率**: 每次运行 `generate_rss.py` 时更新
- **路径**: `docs/entries_latest.json`
- **用法**: 
  - 每次运行时首先检查是否存在此文件
  - 如果存在，与爬虫获取的条目对比
  - 缺失的条目从arXiv API爬取完整信息
  - 运行完成后更新此文件

### 2. `entries_YYYY.json` (年份备份)
- **用途**: 按年份备份当年的完整缓存
- **更新频率**: 每次运行时都会更新（年份相同时覆盖）
- **路径**: `docs/entries_2025.json`, `docs/entries_2024.json` 等
- **用法**: 长期保留历年数据用于对比和备份

## 执行流程

```
python generate_rss.py
    ↓
1. 初始化 CacheManager
    ↓
2. 检查 entries_latest.json 是否存在
    ├─ 存在 → 加载其中的条目
    └─ 不存在 → 尝试加载 entries_2025.json 作为fallback
    ↓
3. 从DMRG网站爬取最新条目
    ↓
4. 对比爬取的条目与缓存中的条目
    ├─ 新增条目 → 从arXiv API获取完整信息
    ├─ 已有条目 → 保留缓存中的信息
    └─ 已删除条目 → 从缓存中移除
    ↓
5. 生成RSS和HTML文件
    ↓
6. 保存更新后的条目到两个缓存文件
    ├─ 更新 entries_latest.json
    └─ 更新 entries_2025.json (按当前年份)
```

## 代码示例

### CacheManager初始化
```python
from src.utils.cache_manager import CacheManager

cache_manager = CacheManager("docs/entries_cache.json")
# 内部会自动设置：
# - cache_path = "docs/entries_latest.json"
# - yearly_cache_path = "docs/entries_2025.json" (基于当前年份)
```

### 加载缓存
```python
# 自动优先加载 entries_latest.json
# 如果不存在，则从 entries_2025.json 加载
cached_entries = cache_manager.load_cache()
```

### 保存缓存
```python
# 同时保存到两个文件
updated_entries = {...}  # 已更新的条目
cache_manager.save_cache(updated_entries)
# 结果：
# - docs/entries_latest.json (更新)
# - docs/entries_2025.json (更新)
```

### 获取缓存统计
```python
stats = cache_manager.get_cache_stats()
# 结果示例：
# {
#     "latest": {
#         "exists": True,
#         "path": "docs/entries_latest.json",
#         "file_size": 12345,
#         "entry_count": 42,
#         "last_updated": "2025-10-24T12:34:56..."
#     },
#     "yearly": {
#         "exists": True,
#         "path": "docs/entries_2025.json",
#         "file_size": 12345,
#         "entry_count": 42,
#         "last_updated": "2025-10-24T12:34:56..."
#     }
# }
```

## 优势

1. **容错性更强**
   - `entries_latest.json` 损坏时可从 `entries_2025.json` 恢复
   - 自动fallback机制

2. **数据备份**
   - 每年自动生成备份 `entries_YYYY.json`
   - 便于长期数据对比和分析

3. **清晰的数据管理**
   - `_latest` 用于当前运行
   - `_YYYY` 用于历史归档
   - 一目了然

4. **易于扩展**
   - 未来可轻松添加月度或其他时间粒度的备份

## 文件位置

所有缓存文件都存储在 `docs/` 目录下：

```bash
docs/
├── rss.xml                    # RSS输出
├── rss.html                   # HTML输出
├── entries_latest.json        # 当前缓存
├── entries_2025.json          # 2025年备份
├── entries_2024.json          # 2024年备份 (如存在)
├── entries_cache.json         # 兼容性符号链接(可选)
└── ...
```

## 注意事项

- 每次运行都会自动保存到当年的备份文件 `entries_YYYY.json`
- 跨年时（如1月1日首次运行），会自动创建新年份文件（如 `entries_2026.json`）
- 旧年份的文件（如 `entries_2024.json`、`entries_2025.json`）自动保留不动
- 如需清除所有缓存，删除 `entries_latest.json` 即可（会从当年备份自动恢复）
- 配置中的 `CACHE_PATH` 仍然指向 `docs/entries_cache.json`，但实际会自动转换为 `entries_latest.json`
