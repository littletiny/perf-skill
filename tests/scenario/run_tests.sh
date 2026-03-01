#!/bin/bash
#
# Test runner script for SPEAR perf-hunter testcases
# 使用 kimi CLI 一次性完成分析和对比
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RESULT_FILE="$SCRIPT_DIR/result.md"

echo "========================================"
echo "SPEAR Perf-Hunter Test Runner"
echo "========================================"
echo ""

# 初始化 result.md
cat > "$RESULT_FILE" << 'EOF'
# SPEAR Perf-Hunter Test Results

| Test Case | Result | Analysis |
|-----------|--------|----------|
EOF

TOTAL=0
PASSED=0
FAILED=0

# 遍历每个子目录
for case_dir in "$SCRIPT_DIR"/*/; do
    [ -d "$case_dir" ] || continue

    case_name=$(basename "$case_dir")
    [[ "$case_name" == .* ]] && continue

    echo "----------------------------------------"
    echo "Test Case: $case_name"
    echo "----------------------------------------"

    input_file="$case_dir/input.txt"
    data_file="$case_dir/case.data"
    expect_file="$case_dir/DONOT_READ_IT/expect.md"
    output_file="$case_dir/output.md"

    if [ ! -f "$input_file" ]; then
        echo "SKIP: Missing input.txt"
        echo "| $case_name | SKIP | Missing input.txt |" >> "$RESULT_FILE"
        continue
    fi

    if [ ! -f "$data_file" ]; then
        echo "SKIP: Missing case.data"
        echo "| $case_name | SKIP | Missing case.data |" >> "$RESULT_FILE"
        continue
    fi

    TOTAL=$((TOTAL + 1))

    # 检查是否有 expect.md
    has_expect="false"
    if [ -f "$expect_file" ]; then
        has_expect="true"
    fi

    # 构造 prompt
    cat > "$case_dir/prompt.txt" << PROMEof
$(cat "$input_file")

数据文件路径: $data_file

请完成以下任务：

1. **分析阶段**: 使用 SPEAR skill 分析上述性能数据
   - 识别应用类型和异常信号
   - 构建竞争性假设
   - 验证假设并得出根因结论
   - 将完整诊断报告保存到: $output_file
   - **⚠️ 重要约束**: 在完成分析并保存 output.md 之前，不允许读取 expect.md

2. **验证阶段**: $(if [ "$has_expect" = "true" ]; then echo "分析完成后，读取 $expect_file 中的预期结论，与你的分析结果进行对比"; else echo "（无预期结论文件，跳过对比）"; fi)

$(if [ "$has_expect" = "true" ]; then echo "3. **输出对比结果到文件**: 将对比结果以如下格式写入到 $case_dir/result.txt：

\`\`\`
RESULT: [YES/NO/PARTIAL]
\`\`\`

- YES: 你的根因结论与预期一致
- NO: 存在重大差异（根因定位错误或关键证据遗漏）
- PARTIAL: 部分正确但有偏差

然后简要说明对比结论（1-2句话）

**重要**: 不要在你的输出中返回对比结果，而是必须将结果写入到 $case_dir/result.txt 文件"; else echo "3. **创建结果文件**: 创建一个空的结果文件 $case_dir/result.txt，内容为：\n\nRESULT: N/A\n\n无预期文件"; fi)
PROMEof

    echo "Running kimi CLI..."
    echo "Has expect.md: $has_expect"

    # 运行 kimi CLI

    if kimi --print --yolo \
        --work-dir "$case_dir" \
        --add-dir "$case_dir" \
        -p "$(cat "$case_dir/prompt.txt")" 2>&1; then

        # 从 result.txt 读取结果
        if [ -f "$case_dir/result.txt" ] && grep -q "RESULT:" "$case_dir/result.txt"; then
            result=$(grep "RESULT:" "$case_dir/result.txt" | head -1 | sed 's/.*RESULT:\s*//' | tr -d '\n\r' | awk '{print $1}')
            # 清理结果（只保留 YES/NO/PARTIAL/N/A）
            result=$(echo "$result" | grep -oE '^(YES|NO|PARTIAL|N/A)' || echo "UNKNOWN")
        else
            result="UNKNOWN"
        fi

        # 提取分析说明
        analysis=$(sed -n '/RESULT:/,$p' "$case_dir/result.txt" 2>/dev/null | tail -n +2 | tr '\n' ' ' | sed 's/|//g' | cut -c1-150)
        if [ -z "$analysis" ]; then
            analysis="Completed"
        fi

        echo "Result: $result"

        # 记录到 result.md
        echo "| $case_name | $result | $analysis |" >> "$RESULT_FILE"

        # 统计
        case "$result" in
            YES) PASSED=$((PASSED + 1)) ;;
            N/A) PASSED=$((PASSED + 1)) ;;
            PARTIAL) PASSED=$((PASSED + 1)) ;;
            *)
                if [ "$has_expect" = "false" ]; then
                    PASSED=$((PASSED + 1))
                else
                    FAILED=$((FAILED + 1))
                fi
                ;;
        esac
    else
        echo "ERROR: kimi CLI failed"
        echo "| $case_name | ERROR | CLI execution failed |" >> "$RESULT_FILE"
        FAILED=$((FAILED + 1))
    fi
    echo ""
done

# 生成总结
cat >> "$RESULT_FILE" << EOF

## Summary

| Metric | Count |
|--------|-------|
| Total | $TOTAL |
| Passed | $PASSED |
| Failed | $FAILED |
| Success Rate | $(awk "BEGIN {printf \"%.1f%%\", ($PASSED/$TOTAL)*100}") |

## Legend

- **YES**: Analysis matches expected conclusion
- **NO**: Significant differences detected
- **PARTIAL**: Partial match with deviations
- **N/A**: No expect.md available
- **SKIP/ERROR**: Test execution issue

## Output Files

Each test case contains:
- \`output.md\`: Generated diagnosis report
- \`result.txt\`: Full kimi CLI output
- \`prompt.txt\`: The constructed prompt used
EOF

echo "========================================"
echo "Summary: Total=$TOTAL Passed=$PASSED Failed=$FAILED"
echo "Results: $RESULT_FILE"
echo "========================================"

[ $FAILED -eq 0 ] && exit 0 || exit 1
