# TC-02: 添加单个问题

## 目的
验证 `trace add` 命令能正确添加问题到文档（自动生成 ID）

## 前置条件
- 已完成 TC-01（文档已初始化）

## 测试步骤

```bash
# Step 1: 确保文档已初始化
python ../../scripts/spear trace init --data perf.data.txt

# Step 2: 添加单个问题（自动生成 ID）
python ../../scripts/spear trace add \
  --desc "netstat 高内核态 94.7%" \
  --hint "cluster-symbols --comm netstat"

# Step 3: 验证内容
python ../../scripts/spear trace issues
```

## 预期结果

### Step 2 输出
```
✓ 已添加问题: ISS-001
  描述: netstat 高内核态 94.7%
  建议: cluster-symbols --comm netstat
```

### Step 3 输出
```
⚠️  OPEN ISSUES (待处理)
-----------------------------------------------------------------
🟡 [ISS-001] netstat 高内核态 94.7%
   └─ 建议: cluster-symbols --comm netstat

用法: spear trace complete --id ISS-001 --result '分析结果'
```

### JSON 文件内容
```json
{
  "version": "2.0",
  "data_file": "perf.data.txt",
  "issues": {
    "ISS-001": {
      "id": "ISS-001",
      "desc": "netstat 高内核态 94.7%",
      "status": "open",
      "hint": "cluster-symbols --comm netstat",
      ...
    }
  }
}
```

### 验证点
- [ ] 添加成功，自动生成 ISS-001
- [ ] 状态为 open
- [ ] hint 字段正确保存
- [ ] issues 命令显示建议和用法提示
