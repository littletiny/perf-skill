# scripts/ - 工具脚本目录

## 目录简介

此目录包含 perf-hunter 的命令行工具和性能分析工具包。

## 子目录说明

### perf_toolkit/
核心性能分析模块，按分层架构组织：

- **core/** - Core Layer: 数据模型、解析器、基础类型
- **analysis/** - Analysis Layer: 性能指标计算、问题检测
- **composite/** - Composite Layer: 多维度分析组合
- **cli/** - CLI Layer: 命令行接口实现

### 主要脚本

- **shecr** - SHECR 主命令入口
- **shecr.py** - SHECR CLI 实现
- **shecr_wrap.py** - 带 Trace 和 Audit 的包装器
- **demo_symbol_processor.py** - 符号处理演示脚本

## 开发注意

- 遵循分层架构，禁止层间传递裸 dict
- 使用 dataclass 进行类型定义
- CLI 命令修改需同步更新 references/cli-commands.md
