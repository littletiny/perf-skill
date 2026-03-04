# Bug Fix TODO - 2026-03-04

> 基于 scenario/ps 下真实错误记录整理的修复任务

---

## 问题列表

### 🔴 P0 - 必须修复

#### 1. get-hotspots 默认排序不一致
**问题**: 参数注册默认 `--sort-by inclusive`，但代码中 `getattr(args, 'sort_by', 'self')` 默认是 'self'，行为和文档不一致。
**预期**: 默认按 `self` 排序（更符合热点分析习惯）
**文件**: `scripts/perf_toolkit/cli/commands/analysis/__init__.py:64`

#### 2. find-callers auto-target bug
**问题**: 使用 `--auto-target` 时，target 为 None，但错误消息显示 "目标函数 'None' 几乎无 CPU 活动"
**预期**: auto-target 应自动选择热点函数作为 target
**文件**: `scripts/perf_toolkit/cli/commands/analysis/callers.py`

#### 3. find-callers 函数名匹配不一致
**问题**: `get-hotspots` 能找到函数 `parameter_server::optimizer::AdamOptimizer::Optimize`，但 `find-callers --target "AdamOptimizer::Optimize"` 找不到
**预期**: 支持部分匹配或文档说明需要完整函数名
**文件**: `scripts/perf_toolkit/cli/commands/analysis/callers.py`

---

### 🟡 P1 - 重要修复

#### 4. find-callers 分叉展示问题
**问题**: 指定 target 遇上调用链分叉时不展示所有分支
**预期**: 展示所有调用路径分支
**文件**: `scripts/perf_toolkit/cli/commands/analysis/callers.py`

#### 5. detect-anomalies 支持 --pid 参数
**问题**: 用户期望使用 `--pid` 过滤，但当前不支持
**预期**: 添加 `--pid` 和 `--comm` 参数支持
**文件**: 
- `scripts/perf_toolkit/cli/commands/analysis/__init__.py:93-114`
- `scripts/perf_toolkit/cli/commands/analysis/anomalies.py`
- `scripts/perf_toolkit/analysis/anomalies.py`

---

### 🟢 P2 - 文档/优化

#### 6. 文档命令不一致
**问题**: `show-cpu-usage` 命令在文档中被提及但实际不存在
**预期**: 移除或替换为实际命令
**文件**: `references/tools.md`, `SKILL.md`

#### 7. bottleneck-trace 信息展示
**问题**: 信息展示格式需要调整（需要更多细节确认）
**文件**: `scripts/perf_toolkit/cli/commands/composite/bottleneck_trace.py`

---

## 修复计划

| 任务 | 优先级 | 负责 | 状态 |
|------|--------|------|------|
| Fix-1: get-hotspots 默认排序 | P0 | agent-1 | pending |
| Fix-2: find-callers auto-target | P0 | agent-2 | pending |
| Fix-3: find-callers 函数名匹配 | P0 | agent-3 | pending |
| Fix-4: find-callers 分叉展示 | P1 | agent-4 | pending |
| Fix-5: detect-anomalies --pid | P1 | agent-5 | pending |
| Fix-6: 文档修复 | P2 | agent-6 | pending |

---

## 测试计划

修复完成后执行：
```bash
# 单元测试
python3 tests/run_tests.py

# 手动验证
python3 scripts/shecr.py get-hotspots --help  # 检查默认sort-by
python3 scripts/shecr.py find-callers --help  # 检查auto-target
python3 scripts/shecr.py detect-anomalies --help  # 检查--pid参数
```

---

## Git 计划

```bash
# 修复完成后
git add -A
git commit -m "fix: 修复scenario/ps下发现的7个问题

- get-hotspots默认--sort-by self
- find-callers auto-target bug修复
- find-callers函数名匹配优化
- find-callers分叉展示修复
- detect-anomalies支持--pid/--comm
- 移除show-cpu-usage文档引用
- bottleneck-trace信息展示优化"

git push
```
