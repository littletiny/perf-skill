# cluster-symbols / Rules 测试

本目录包含 cluster-symbols 命令的 rules 文件加载、缓存机制和集成测试。

---

## 测试文件

| 文件 | 用途 |
|------|------|
| `test_rules_loading.py` | Rules 文件加载、缓存、优先级合并测试 |
| `test_external_rules_integration.py` | 外部规则文件与真实数据集成测试 |

---

## 运行测试

```bash
# 从项目根目录运行

# Rules 加载测试
python3 tests/clusters/test_rules_loading.py
python3 tests/clusters/test_rules_loading.py -v
python3 tests/clusters/test_rules_loading.py -f  # 失败时停止

# 外部规则集成测试
python3 tests/clusters/test_external_rules_integration.py
python3 tests/clusters/test_external_rules_integration.py -v
python3 tests/clusters/test_external_rules_integration.py -f
```

---

## 测试覆盖

### test_rules_loading.py

1. **默认规则路径** - 验证从 `config/default-rules.json` 加载
2. **默认规则加载** - 验证内置规则正确解析
3. **外部文件加载** - 从自定义 JSON 文件加载规则
4. **缓存机制** - 模块级缓存，相同文件只加载一次
5. **规则优先级** - 内置 < 外部文件 < 命令行的合并逻辑
6. **文件不存在** - FileNotFoundError 异常处理
7. **禁用内置规则** - `--no-include-experts` 选项
8. **空规则文件** - 空配置返回空字典
9. **模块级变量** - EXPERT_RULES 全局变量已加载

### test_external_rules_integration.py

1. **配置加载** - 从 config/default-rules.json 加载验证
2. **外部规则覆盖** - 外部规则覆盖内置规则
3. **CLI 最高优先级** - 命令行规则覆盖外部文件
4. **缓存机制** - 相对/绝对路径缓存命中
5. **禁用专家规则** - `--no-include-experts` 验证
6. **空规则处理** - 空外部规则文件
7. **元数据过滤** - `_comment`、`_version` 等键过滤
8. **列表格式** - 规则值支持列表格式
9. **文件不存在** - 错误处理
10. **真实数据集成** - 与 `tests/perfdata/new_format/case_test.data` 集成
11. **Trace 记录** - 统一入口正确记录 Trace
12. **wrap 脚本集成** - 通过 `spear_wrap.py` 使用外部规则

---

## 添加新测试

如需添加新的 Rules 相关测试，编辑对应文件或创建新测试文件。

命名规范：
- 测试函数：`test_<描述>`（如 `test_new_feature`）
- 辅助函数：`test_<前缀>_<描述>`

注意事项：
- 测试使用临时文件，确保在 `finally` 块中清理
- 测试后清空 `clusters._rules_cache` 避免影响其他测试
