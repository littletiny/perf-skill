# perf-doc 测试用例集

> 测试 Live Document 机制的各项功能

## 测试环境准备

```bash
# 进入测试目录
cd tests/doc_testcases

# 清理之前的测试数据
rm -f .perf-doc.json *.md
```

## 测试用例清单

| 编号 | 测试场景 | 文件 | 优先级 |
|------|---------|------|--------|
| TC-01 | 初始化文档 | tc_01_init.md | P0 |
| TC-02 | 添加单个问题 | tc_02_add_single.md | P0 |
| TC-03 | 添加多个问题 | tc_03_add_multiple.md | P0 |
| TC-04 | 标记问题完成 | tc_04_complete.md | P0 |
| TC-05 | 列出所有问题 | tc_05_list.md | P0 |
| TC-06 | 最终审计 - 全部完成 | tc_06_finalize_ready.md | P0 |
| TC-07 | 最终审计 - 有遗留问题 | tc_07_finalize_blocked.md | P0 |
| TC-08 | 导出 Markdown 报告 | tc_08_export_md.md | P1 |
| TC-09 | 重复 ID 检测 | tc_09_duplicate_id.md | P1 |
| TC-10 | netstat/containerd-shim 完整场景 | tc_10_full_scenario.md | P0 |

## 快速执行

```bash
# 运行单个测试
./run_test.sh tc_01

# 运行全部测试
./run_test.sh all
```
