#!/bin/bash
# OutputBuilder 重命名验证脚本
# 验证 OutputBuilderV2 -> OutputBuilder 重构后所有功能正常

set -e

SKILL_DIR="${SKILL_DIR:-$HOME/.config/agents/skills/perf-hunter}"
PERF_EXPERT="$SKILL_DIR/scripts/perf_expert.py"
TEST_DATA="$SKILL_DIR/tests/perfdata/new_format/case_test.data"

if [ ! -f "$PERF_EXPERT" ]; then
    echo "Error: perf_expert.py not found at $PERF_EXPERT"
    exit 1
fi

if [ ! -f "$TEST_DATA" ]; then
    echo "Error: Test data not found at $TEST_DATA"
    exit 1
fi

echo "========================================"
echo "OutputBuilder 验证测试"
echo "========================================"
echo "PERF_EXPERT: $PERF_EXPERT"
echo "TEST_DATA: $TEST_DATA"
echo ""

PASSED=0
FAILED=0

run_test() {
    local name="$1"
    local cmd="$2"
    
    echo -n "Testing $name... "
    if eval "$cmd" > /tmp/test_output.txt 2>&1; then
        echo "✓ PASS"
        PASSED=$((PASSED + 1))
    else
        echo "✗ FAIL"
        echo "  Command: $cmd"
        echo "  Output:"
        head -5 /tmp/test_output.txt | sed 's/^/    /'
        FAILED=$((FAILED + 1))
    fi
}

# 基础命令测试
run_test "check-cpu-bottleneck" \
    "python3 $PERF_EXPERT check-cpu-bottleneck --data $TEST_DATA"

run_test "get-hotspots" \
    "python3 $PERF_EXPERT get-hotspots --data $TEST_DATA --top-n 5"

run_test "cluster-symbols" \
    "python3 $PERF_EXPERT cluster-symbols --data $TEST_DATA"

run_test "get-process-top" \
    "python3 $PERF_EXPERT get-process-top --data $TEST_DATA --top-n 5"

run_test "cluster-comm" \
    "python3 $PERF_EXPERT cluster-comm --data $TEST_DATA"

run_test "cluster-paths" \
    "python3 $PERF_EXPERT cluster-paths --data $TEST_DATA"

run_test "count-process-variety" \
    "python3 $PERF_EXPERT count-process-variety --data $TEST_DATA"

run_test "analyze-core-distribution" \
    "python3 $PERF_EXPERT analyze-core-distribution --data $TEST_DATA"

run_test "get-comm-top" \
    "python3 $PERF_EXPERT get-comm-top --data $TEST_DATA --top-n 5"

run_test "show-cpu-usage" \
    "python3 $PERF_EXPERT show-cpu-usage --data $TEST_DATA"

run_test "find-callers (auto)" \
    "python3 $PERF_EXPERT find-callers --data $TEST_DATA --auto-target"

run_test "detect-anomalies" \
    "python3 $PERF_EXPERT detect-anomalies --data $TEST_DATA"

# Python 导入测试
run_test "Python imports" \
    "python3 -c 'import sys; sys.path.insert(0, \"$SKILL_DIR/scripts\"); from perf_toolkit.core import OutputBuilder, create_risk_info; from perf_toolkit.analysis.hotspots import cmd_get_hotspots'"

echo ""
echo "========================================"
echo "测试完成: $PASSED 通过, $FAILED 失败"
echo "========================================"

if [ $FAILED -eq 0 ]; then
    echo "✓ 所有测试通过！"
    exit 0
else
    echo "✗ 有测试失败"
    exit 1
fi
