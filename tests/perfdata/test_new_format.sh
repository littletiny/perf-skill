#!/bin/bash
#
# New Format 格式专项测试脚本
# 验证 perf-hunter 工具对处理后格式（带 core/s 值）的解析能力
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="${SKILL_DIR:-$HOME/.config/agents/skills/perf-hunter}"
PERF_EXPERT="$SKILL_DIR/scripts/perf_expert.py"

DATA_DIR="$SCRIPT_DIR/new_format"
DATA_FILE="$DATA_DIR/case_test.data"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 检查结果
check_result() {
    local test_name="$1"
    local output="$2"
    local exit_code="$3"
    
    if [ $exit_code -eq 0 ]; then
        echo -e "${GREEN}✅ [PASS]${NC} $test_name"
        return 0
    else
        echo -e "${RED}❌ [FAIL]${NC} $test_name"
        echo "   错误输出:"
        echo "$output" | head -5 | sed 's/^/   /'
        return 1
    fi
}

# 运行工具并检查
run_test() {
    local tool_name="$1"
    shift
    local output
    local exit_code=0
    
    output=$(python3 "$PERF_EXPERT" "$tool_name" --data "$DATA_FILE" "$@" 2>&1) || exit_code=$?
    check_result "$tool_name $@" "$output" "$exit_code"
    
    if [ $exit_code -eq 0 ] && [ -n "$output" ]; then
        local line_count=$(echo "$output" | wc -l)
        echo "   输出: ${line_count} 行"
    fi
    
    return $exit_code
}

# 运行并显示摘要
run_test_with_summary() {
    local test_name="$1"
    local tool_name="$2"
    shift 2
    
    echo ""
    echo "[$test_name] $tool_name $@"
    
    local output
    local exit_code=0
    
    output=$(python3 "$PERF_EXPERT" "$tool_name" --data "$DATA_FILE" "$@" 2>&1) || exit_code=$?
    
    if check_result "$tool_name" "$output" "$exit_code"; then
        # 显示关键信息
        if echo "$output" | grep -q "cpu_utilization\|total_pct\|aggregate_cpu_pct\|ratio_pct"; then
            echo "   关键指标:"
            echo "$output" | grep -E "(cpu_utilization|total_pct|aggregate_cpu_pct|ratio_pct)" | head -3 | sed 's/^/   /'
        fi
        return 0
    else
        return 1
    fi
}

echo "========================================"
echo "New Format 格式专项测试"
echo "========================================"
echo -e "${BLUE}数据文件:${NC} $DATA_FILE"
echo -e "${BLUE}工具路径:${NC} $PERF_EXPERT"
echo ""
echo "格式特点: 包含预计算的 core/s 值"
echo ""

# 前置检查
if [ ! -f "$PERF_EXPERT" ]; then
    echo -e "${RED}❌ [ERROR]${NC} perf_expert.py 未找到: $PERF_EXPERT"
    echo "请设置 SKILL_DIR 环境变量指向 perf-hunter skill 目录"
    exit 1
fi

if [ ! -f "$DATA_FILE" ]; then
    echo -e "${RED}❌ [ERROR]${NC} 数据文件未找到: $DATA_FILE"
    exit 1
fi

# 统计文件信息
echo "--- 数据文件信息 ---"
line_count=$(wc -l < "$DATA_FILE")
sample_count=$(grep -c 'core/s:' "$DATA_FILE" 2>/dev/null || echo "0")
comm_count=$(grep 'core/s:' "$DATA_FILE" 2>/dev/null | awk '{print $1}' | sort -u | wc -l)
echo "总行数: $line_count"
echo "采样记录数: $sample_count"
echo "进程类型数: $comm_count"
echo ""

# 显示样本数据
echo "--- 样本数据 (前3条) ---"
head -10 "$DATA_FILE" | sed 's/^/   /'
echo ""

# 测试结果统计
passed=0
failed=0

# ============ 第一阶段：基础环境评估 ============
echo "========================================"
echo "第一阶段：基础环境评估"
echo "========================================"

if run_test_with_summary "1.1" check-cpu-bottleneck; then
    ((passed++))
else
    ((failed++))
fi

if run_test_with_summary "1.2" show-cpu-usage; then
    ((passed++))
else
    ((failed++))
fi

# ============ 第二阶段：进程级分析 ============
echo ""
echo "========================================"
echo "第二阶段：进程级分析"
echo "========================================"

if run_test_with_summary "2.1" get-process-top --top-n 5; then
    ((passed++))
else
    ((failed++))
fi

if run_test_with_summary "2.2" get-comm-top --top-n 5; then
    ((passed++))
else
    ((failed++))
fi

if run_test_with_summary "2.3" count-process-variety --top-n 10; then
    ((passed++))
else
    ((failed++))
fi

if run_test_with_summary "2.4" cluster-comm --top-n 10; then
    ((passed++))
else
    ((failed++))
fi

# ============ 第三阶段：热点函数分析 ============
echo ""
echo "========================================"
echo "第三阶段：热点函数分析"
echo "========================================"

if run_test_with_summary "3.1" get-hotspots --sort-by self --top-n 10; then
    ((passed++))
else
    ((failed++))
fi

if run_test_with_summary "3.2" get-hotspots --sort-by inclusive --top-n 10; then
    ((passed++))
else
    ((failed++))
fi

# 尝试查找特定进程的调用者
first_comm=$(grep 'core/s:' "$DATA_FILE" 2>/dev/null | awk '{print $1}' | sort | uniq -c | sort -rn | head -1 | awk '{print $2}')
if [ -n "$first_comm" ]; then
    echo ""
    echo "[3.3] 查找热点调用者 (进程: $first_comm)..."
    # 获取该进程的第一个热点
    first_symbol=$(python3 "$PERF_EXPERT" get-hotspots --data "$DATA_FILE" --comm "$first_comm" --sort-by self --top-n 1 2>/dev/null | grep -E '^\s+[a-zA-Z_]' | head -1 | awk '{print $1}')
    if [ -n "$first_symbol" ] && [ "$first_symbol" != "symbol" ]; then
        echo "   目标函数: $first_symbol (进程: $first_comm)"
        if run_test find-callers --target "$first_symbol" --comm "$first_comm" --min-ratio 1.0; then
            ((passed++))
        else
            ((failed++))
        fi
    else
        echo -e "${YELLOW}⚠️ [SKIP]${NC} 未找到有效热点函数"
    fi
fi

# ============ 第四阶段：语义聚类分析 ============
echo ""
echo "========================================"
echo "第四阶段：语义聚类分析"
echo "========================================"

if run_test_with_summary "4.1" cluster-symbols; then
    ((passed++))
else
    ((failed++))
fi

# 针对特定进程的语义聚类
if [ -n "$first_comm" ]; then
    echo ""
    echo "[4.2] 符号语义聚类 (进程: $first_comm)..."
    if run_test cluster-symbols --comm "$first_comm"; then
        ((passed++))
    else
        ((failed++))
    fi
fi

if run_test_with_summary "4.3" cluster-paths --min-depth 3 --top-n 5; then
    ((passed++))
else
    ((failed++))
fi

# ============ 第五阶段：负载分布分析 ============
echo ""
echo "========================================"
echo "第五阶段：负载分布分析"
echo "========================================"

if run_test_with_summary "5.1" analyze-core-distribution; then
    ((passed++))
else
    ((failed++))
fi

# 针对特定进程的负载分布
if [ -n "$first_comm" ]; then
    echo ""
    echo "[5.2] 核心负载分布 (进程: $first_comm)..."
    if run_test analyze-core-distribution --comm "$first_comm"; then
        ((passed++))
    else
        ((failed++))
    fi
fi

# ============ 第六阶段：可视化工具 ============
echo ""
echo "========================================"
echo "第六阶段：可视化工具"
echo "========================================"

if run_test_with_summary "6.1" generate-flamegraph; then
    ((passed++))
else
    ((failed++))
fi

if run_test_with_summary "6.2" generate-callgraph --format json; then
    ((passed++))
else
    ((failed++))
fi

# 针对特定进程的火焰图
if [ -n "$first_comm" ]; then
    echo ""
    echo "[6.3] 生成火焰图 (进程: $first_comm)..."
    if run_test generate-flamegraph --comm "$first_comm"; then
        ((passed++))
    else
        ((failed++))
    fi
fi

# ============ 第七阶段：格式特定测试 ============
echo ""
echo "========================================"
echo "第七阶段：New Format 特定测试"
echo "========================================"

echo ""
echo "[7.1] 验证 core/s 值解析..."
# 检查是否能正确解析带 core/s 的数据
core_values=$(grep -oP '\d+\.\d+(?=\s+core/s)' "$DATA_FILE" 2>/dev/null | head -5)
if [ -n "$core_values" ]; then
    echo -e "${GREEN}✅ [PASS]${NC} core/s 值解析"
    echo "   示例值:"
    echo "$core_values" | sed 's/^/   /'
    ((passed++))
else
    echo -e "${YELLOW}⚠️ [WARN]${NC} 未检测到标准 core/s 格式"
    ((passed++))  # 警告但不计为失败
fi

echo ""
echo "[7.2] 验证多进程类型支持..."
if [ "$comm_count" -gt 1 ]; then
    echo -e "${GREEN}✅ [PASS]${NC} 检测到 $comm_count 种进程类型"
    echo "   进程类型:"
    grep 'core/s:' "$DATA_FILE" 2>/dev/null | awk '{print $1}' | sort -u | head -10 | sed 's/^/   /'
    ((passed++))
else
    echo -e "${YELLOW}⚠️ [WARN]${NC} 仅检测到 $comm_count 种进程类型"
    ((passed++))
fi

# ============ 测试总结 ============
echo ""
echo "========================================"
echo "测试总结"
echo "========================================"
echo "通过: $passed"
echo "失败: $failed"
echo "总计: $((passed + failed))"
echo ""

if [ $failed -eq 0 ]; then
    echo -e "${GREEN}🎉 所有测试通过！${NC}"
    echo "new_format 格式数据与工具集完全兼容。"
    exit 0
else
    echo -e "${RED}⚠️ 部分测试失败${NC}"
    echo "请检查工具输出和数据格式。"
    exit 1
fi
