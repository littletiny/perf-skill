# AGENTS.md - perf-hunter 开发入口

perf-hunter 是基于 **SHECR** 方法论的性能诊断工具集。

---

## 🚀 快速开始

```bash
# 运行所有测试
python3 tests/run_tests.py
```

---

## 📍 开发导航

**所有查找需求请从此开始**: [`docs/meta/navigation.md`](docs/meta/navigation.md)

**多人协同开发流程**: [`docs/meta/development-process.md`](docs/meta/development-process.md) - 从需求到代码的七步流程

> 原则：模糊正确 > 精确过时

---

## 📁 目录速览

| 目录 | 用途 | 详细文档 |
|------|------|----------|
| `scripts/` | 工具脚本和核心模块 | [scripts/AGENTS.md](scripts/AGENTS.md) |
| `tests/` | 测试套件 | [tests/AGENTS.md](tests/AGENTS.md) |
| `docs/` | 内部文档 | [docs/AGENTS.md](docs/AGENTS.md) |
| `references/` | 用户参考文档 | [references/AGENTS.md](references/AGENTS.md) |
| `pipeline/` | Agent 流水线 | [pipeline/AGENTS.md](pipeline/AGENTS.md) |

---

## ⚡ 核心约定

- **静态类型**: 禁用裸 `dict`，使用 `dataclass`
- **禁止硬编码**: 配置优先
- **修改前确认**: 方案说明 → 人工确认 → 修改
- **简单优先**: let it crash

### 本文档约定

> AGENTS.md 只放"必须立即知道"的内容，其他外链到 `docs/`。
> 
> 详见: [docs/meta/documentation-architecture.md](docs/meta/documentation-architecture.md)

---

## 📎 快速链接

- 接口规范: `docs/interface/`
- CLI 命令参考: `references/cli-commands.md`
- 数据格式: `references/data-format.md`
