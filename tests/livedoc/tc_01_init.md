# TC-01: 初始化文档

## 目的
验证 `doc init` 命令能正确创建诊断文档

## 前置条件
- 无（确保 .perf-doc.json 不存在）

## 测试步骤

```bash
# Step 1: 清理环境
rm -f .perf-doc.json

# Step 2: 初始化文档
python ../../scripts/spear.py doc init --data ./perf.data.txt

# Step 3: 验证文件创建
ls -la .perf-doc.json

# Step 4: 查看内容
cat .perf-doc.json
```

## 预期结果

### Step 2 输出
```
✓ 创建诊断文档: .perf-doc.json
  数据文件: ./perf.data.txt
```

### Step 4 文件内容
```json
{
  "version": "1.0",
  "data_file": "./perf.data.txt",
  "created_at": "2026-02-28T12:00:00Z",
  "updated_at": "2026-02-28T12:00:00Z",
  "issues": []
}
```

### 验证点
- [ ] 命令返回成功（exit code 0）
- [ ] 输出包含 "✓ 创建诊断文档"
- [ ] JSON 文件包含 version, data_file, created_at, issues 字段
- [ ] issues 数组为空
