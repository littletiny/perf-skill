# TC-01: 初始化文档

## 目的
验证 `trace init` 命令能正确创建诊断文档

## 前置条件
- 无（确保 .spear.json 不存在）

## 测试步骤

```bash
# Step 1: 清理环境
rm -f .spear.json

# Step 2: 初始化文档
python ../../scripts/spear trace init --data ./perf.data.txt

# Step 3: 验证文件创建
ls -la .spear.json

# Step 4: 查看内容
cat .spear.json
```

## 预期结果

### Step 2 输出
```
✓ 创建诊断文档: .spear.json
  数据文件: ./perf.data.txt
```

### Step 4 文件内容
```json
{
  "version": "2.0",
  "data_file": "./perf.data.txt",
  "created_at": "2026-02-28T12:00:00Z",
  "updated_at": "2026-02-28T12:00:00Z",
  "timeline": [],
  "issues": {}
}
```

### 验证点
- [ ] 命令返回成功（exit code 0）
- [ ] 输出包含 "✓ 创建诊断文档"
- [ ] JSON 文件包含 version, data_file, created_at, timeline, issues 字段
- [ ] timeline 数组为空
- [ ] issues 对象为空
