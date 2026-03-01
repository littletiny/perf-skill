# Risk 显示配置测试

本目录包含 Risk 显示配置的单元测试，验证 Risk 消息格式化、配置加载和模式应用等功能。

---

## 测试文件

| 文件 | 用途 |
|------|------|
| `test_risk_display_config.py` | RiskDisplayConfig 配置加载、模式应用、格式化输出测试 |

---

## 运行测试

```bash
# 从项目根目录运行
python3 tests/risk/test_risk_display_config.py

# 详细输出
python3 tests/risk/test_risk_display_config.py -v
```

---

## 测试覆盖

### RiskDisplayConfig 测试

1. **默认配置结构** - 验证默认颜色、模板、显示标志
2. **模板无 emoji** - 确保默认模板不包含 emoji 字符
3. **模板格式** - 验证 issue_open/issue_resolved/hint 格式正确
4. **配置文件加载** - 测试从 JSON 文件加载和合并配置
5. **模式应用** - 测试 ci/compact 模式的应用
6. **全局缓存** - 验证配置缓存机制
7. **格式化模拟** - 模拟 issue 格式化输出
8. **错误处理** - JSON 解析错误、缺失 risk 段的处理
9. **环境变量** - SPEAR_RISK_CONFIG 环境变量支持

### Trace 格式化测试

1. **issue 格式化** - Trace.format_issue 与 config 集成
2. **已解决 issue** - 已解决 issue 的格式化
3. **时间线格式化** - Trace.format_timeline 输出格式

---

## 添加新测试

如需添加新的 Risk 相关测试，直接编辑 `test_risk_display_config.py`，在对应 TestCase 类中添加测试方法。

命名规范：
- 测试方法：`test_<序号>_<描述>`（如 `test_14_new_feature`）
- 测试类：`Test<功能>`（如 `TestRiskDisplayConfig`）
