#!/bin/bash
# OutputBuilder 重命名验证脚本
# 验证 OutputBuilderV2 -> OutputBuilder 重构后所有功能正常

set -e

# 默认输出文件
OUTPUT_FILE="output.txt"
SHOW_HELP=false

# 解析参数
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            SHOW_HELP=true
            shift
            ;;
        -o|--output)
            OUTPUT_FILE="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use -h or --help for usage information"
            exit 1
            ;;
    esac
done

# 显示帮助信息
if [ "$SHOW_HELP" = true ]; then
    cat << 'EOF'
Usage: ./verify_output_builder.sh [OPTIONS]

验证 OutputBuilder 重构后功能的测试脚本。

OPTIONS:
    -h, --help              显示此帮助信息
    -o, --output FILE       指定输出文件路径 (默认: output.txt)

DESCRIPTION:
    本脚本测试 perf_expert.py 的各项功能，包括：
    - check-cpu-bottleneck: 检查 CPU 瓶颈
    - get-hotspots: 获取热点函数
    - cluster-symbols: 聚类符号
    - get-process-top: 获取进程 Top N
    - cluster-comm: 聚类通信
    - cluster-paths: 聚类调用路径
    - count-process-variety: 统计进程种类
    - analyze-core-distribution: 分析核心分布
    - get-comm-top: 获取通信 Top N
    - show-cpu-usage: 显示 CPU 使用率
    - find-callers: 查找调用者
    - detect-anomalies: 检测异常
    - Python imports: 验证 Python 模块导入

EXAMPLES:
    ./verify_output_builder.sh                  # 默认输出到 output.txt
    ./verify_output_builder.sh -o result.txt    # 输出到 result.txt
    ./verify_output_builder.sh --help           # 显示帮助信息

EOF
    exit 0
fi

SKILL_DIR="${SKILL_DIR:-$HOME/.config/agents/skills/perf-hunter}"
PERF_EXPERT="$SKILL_DIR/scripts/perf_expert.py"
TEST_DATA="$SKILL_DIR/tests/perfdata/perf_format/case_test.data"

if [ ! -f "$PERF_EXPERT" ]; then
    echo "Error: perf_expert.py not found at $PERF_EXPERT"
    exit 1
fi

if [ ! -f "$TEST_DATA" ]; then
    echo "Error: Test data not found at $TEST_DATA"
    exit 1
fi

# 将输出同时显示在终端并写入文件
exec > >(tee "$OUTPUT_FILE") 2>&1

echo "========================================"
echo "OutputBuilder 验证测试"
echo "========================================"
echo "PERF_EXPERT: $PERF_EXPERT"
echo "TEST_DATA: $TEST_DATA"
echo "OUTPUT_FILE: $OUTPUT_FILE"
echo ""

PASSED=0
FAILED=0

run_test() {
    local name="$1"
    local cmd="$2"
    
    echo ""
    echo "========================================"
    echo "Testing: $name"
    echo "Command: $cmd"
    echo "========================================"
    
    if eval "$cmd" 2>&1; then
        echo ""
        echo "[✓ PASS] $name"
        PASSED=$((PASSED + 1))
    else
        echo ""
        echo "[✗ FAIL] $name"
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
echo "输出已保存到: $OUTPUT_FILE"

if [ $FAILED -eq 0 ]; then
    echo "✓ 所有测试通过！"
    exit 0
else
    echo "✗ 有测试失败"
    exit 1
fi
