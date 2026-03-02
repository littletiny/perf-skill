# shecr_wrap 测试文档

## 概述

本文档描述 `shecr_wrap.py` 的回归测试套件，用于验证多数据文件管理、变量跟随逻辑等核心功能。

## 测试文件

| 文件 | 说明 |
|------|------|
| `test_shecr_wrap.py` | 回归测试套件（纯 Python 标准库实现） |
| `README.md` | 本文件 |

## 运行测试

```bash
# 运行所有测试
python3 tests/test_shecr_wrap.py

# 详细输出
python3 tests/test_shecr_wrap.py -v

# 失败时立即停止
python3 tests/test_shecr_wrap.py -f
```

## 测试覆盖范围

### 1. 环境配置管理

| 测试用例 | 描述 | 验证点 |
|---------|------|--------|
| `test_load_save_env` | 配置加载和保存 | `.shecr_env` JSON 格式正确读写 |
| `test_migrate_old_env` | 旧格式迁移 | KEY=VALUE 格式自动迁移到 JSON |

### 2. 多数据文件管理

| 测试用例 | 描述 | 验证点 |
|---------|------|--------|
| `test_init_new_profile` | 初始化新数据文件 | 创建 profile，设为默认，创建 trace |
| `test_init_with_freq` | 初始化带频率 | freq 正确保存到 profile |
| `test_init_multiple_profiles` | 多个数据文件 | profiles_used 记录所有文件 |
| `test_use_switch_profile` | 切换数据文件 | default 正确切换 |
| `test_use_by_index` | 通过索引切换 | 支持数字索引切换 |
| `test_re_init_updates_profile` | 重复 init | 更新现有 profile 而非创建新 |

### 3. 变量跟随逻辑

| 测试用例 | 描述 | 验证点 |
|---------|------|--------|
| `test_freq_follows_data` | freq 跟随 data | 切换 profile 时 freq 正确跟随 |
| `test_get_active_config_priority` | 配置优先级 | SPEAR_DATA > default |
| `test_cmd_build_no_freq` | 命令构建（无 freq） | 不添加 --freq 参数 |
| `test_cmd_build_with_freq` | 命令构建（有 freq） | 正确添加 --freq 参数 |
| `test_cmd_build_trace_no_freq` | trace 命令 | trace 子命令不添加 --freq |

### 4. 全局 Trace 管理

| 测试用例 | 描述 | 验证点 |
|---------|------|--------|
| `test_global_trace_profiles_used` | profiles_used 记录 | 所有 init 的数据文件都记录 |

## 数据结构验证

### .shecr_env 格式

```json
{
  "profiles": {
    "/path/to/data1.data": {
      "init_time": "2026-03-02T10:00:00",
      "script_path": "/path/shecr.py",
      "freq": null
    },
    "/path/to/data2.data": {
      "init_time": "2026-03-02T10:01:00",
      "script_path": "/path/shecr.py",
      "freq": "99"
    }
  },
  "default": "/path/to/data2.data"
}
```

### .shecr.json 格式

```json
{
  "version": "2.0",
  "data_file": "/path/to/first.data",
  "created_at": "2026-03-02T10:00:00",
  "updated_at": "2026-03-02T10:05:00",
  "timeline": [...],
  "issues": {...},
  "profiles_used": [
    "/path/to/data1.data",
    "/path/to/data2.data"
  ]
}
```

## 关键行为验证

### 1. freq 跟随逻辑

```python
# 场景: 两个数据文件，一个有 freq，一个无
# data1: freq=null
# data2: freq="99"

# 默认 data1 -> 无 --freq
shecr get-hotspots --data data1 --top-n 10

# 切换到 data2 -> 有 --freq
shecr use data2
shecr get-hotspots --data data2 --freq 99 --top-n 10

# SHECR_DATA 覆盖到 data1 -> 无 --freq
SHECR_DATA=data1 shecr get-hotspots --top-n 10
```

### 2. 配置优先级

```
1. SHECR_DATA 环境变量（最高）
2. .shecr_env 中的 default
3. 未配置（报错）
```

### 3. Trace 命令特殊处理

```python
# trace 子命令不添加 --data 和 --freq
# 无论当前 profile 的 freq 是什么

shecr trace timeline       # 正确
shecr trace --data x --freq 99 timeline  # 错误，trace 不需要这些
```

## 回归测试场景

### 场景 1: 初始化流程

```bash
# 1. 初始化第一个数据文件
shecr init --data-path ./perf1.data
# 验证: .shecr_env 创建，default=perf1，trace 创建

# 2. 初始化第二个（带 freq）
shecr init --data-path ./perf2.data --freq 99
# 验证: default=perf2，profiles 包含两个，profiles_used 包含两个

# 3. 重复 init 第一个（修改 freq）
shecr init --data-path ./perf1.data --freq 199
# 验证: perf1 的 freq 更新，profile 数量仍为 2
```

### 场景 2: 切换流程

```bash
# 1. 列出所有
shecr list
# 验证: 显示所有 profile，标记当前 default

# 2. 切换
shecr use ./perf1.data
shecr status
# 验证: default 已切换，status 显示正确

# 3. 通过索引切换
shecr use 2
# 验证: 切换到第二个 profile
```

### 场景 3: 命令执行

```bash
# 1. 无 freq 的 profile
shecr use 1
shecr get-hotspots --top-n 10
# 验证: 命令不包含 --freq

# 2. 有 freq 的 profile
shecr use 2
shecr get-hotspots --top-n 10
# 验证: 命令包含 --freq 99

# 3. SHECR_DATA 覆盖
SHECR_DATA=./perf1.data shecr get-hotspots --top-n 10
# 验证: 使用 perf1 的配置（无 freq）
```

## 常见问题

### Q: 测试失败怎么办？

1. 检查是否修改了 `shecr_wrap.py` 的核心逻辑
2. 使用 `-v` 查看详细输出
3. 使用 `-f` 在第一个失败处停止，便于调试

### Q: 如何添加新测试？

1. 在 `TEST_CASES` 列表中添加测试函数
2. 使用 `TestEnv` 作为上下文管理器隔离测试环境
3. 使用 `assert` 进行验证

```python
def test_new_feature():
    """测试: 新功能描述"""
    with TestEnv() as te:
        # 测试逻辑
        assert condition, "失败消息"
```

### Q: 测试是否依赖外部工具？

否。所有测试使用纯 Python 标准库，不依赖：
- pytest/unittest 等测试框架
- 真实的 shecr.py 执行
- 真实的 perf 数据文件

测试使用模拟数据和临时目录，完全自包含。
