# perf-hunter 测试项目

本项目用于验证 SPEAR-perf-hunter 工具集的输入格式兼容性。

## 目录结构

```
.
├── doc_testcases/        # livedoc 功能测试用例
├── perfdata/             # 工具接受的输入格式数据集
└── scenario/             # 功能测试（验证整套方法论在 agent 中的表现）
```

## perfdata 验证工具使用

**详细使用说明请参考**：[perfdata/README.md](perfdata/README.md)

## scenario 功能测试（按需使用）

**注意**: scenario 目录包含完整的功能测试场景，用于验证整套 SPEAR 方法论在 agent 中的表现。这些测试需要调用完整的分析流程，仅在需要验证端到端场景时使用。
