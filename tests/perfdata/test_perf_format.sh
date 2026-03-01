#!/bin/bash
#
# Perf Format 格式专项测试脚本
# 验证 perf-hunter 工具对原始 perf script 格式的解析能力
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="${SKILL_DIR:-$HOME/.config/agents/skills/perf-hunter}"
SPEAR="$SKILL_DIR/scripts/spear"

DATA_DIR="$SCRIPT_DIR/perf_format"
DATA_FILE="$DATA_DIR/case_test.data"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查结果
# 参数: $1=测试名, $2=命令输出, $3=退出码
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
    
    output=$(SPEAR_DATA="$DATA_FILE" "$SPEAR" "$tool_name" "$@" 2>&1) || exit_code=$?
    check_result "$tool_name $@" "$output" "$exit_code"
    
    # 如果有输出且成功，显示摘要
    if [ $exit_code -eq 0 ] && [ -n "$output" ]; then
        local line_count=$(echo "$output" | wc -l)
        echo "   输出: ${line_count} 行"
    fi
    
    return $exit_code
}

echo "========================================"
echo "Perf Format 格式专项测试"
echo "========================================"
echo "数据文件: $DATA_FILE"
echo "工具路径: $PERF_EXPERT"
echo ""

# 前置检查
if [ ! -f "$SPEAR" ]; then
    echo -e "${RED}❌ [ERROR]${NC} spear 脚本未找到: $SPEAR"
    echo "请设置 SKILL_DIR 环境变量指向 perf-hunter skill 目录"
    exit 1
fi

if [ ! -f "$DATA_FILE" ]; then
    echo -e "${RED}❌ [ERROR]${NC} 数据文件未找到: $DATA_FILE"
    exit 1
fi

# 切换到临时目录执行测试，避免污染源码目录
TMP_DIR=$(mktemp -d)
cd "$TMP_DIR"

# 初始化 spear 环境
$SPEAR init --data-path "$DATA_FILE"

# 统计文件信息
echo "--- 数据文件信息 ---"
line_count=$(wc -l < "$DATA_FILE")
proc_count=$(grep -c '^[a-zA-Z]' "$DATA_FILE" 2>/dev/null || echo "0")
echo "总行数: $line_count"
echo "采样记录数: $proc_count"
echo ""

# 测试结果统计
passed=0
failed=0

# ============ 第一阶段：基础环境评估 ============
echo "========================================"
echo "第一阶段：基础环境评估"
echo "========================================"

# 1.1 CPU瓶颈检查
echo ""
echo "[1.1] 检查 CPU 瓶颈..."
if run_test check-cpu-bottleneck; then
    ((passed++))
else
    ((failed++))
fi

# 1.2 CPU使用率概览
echo ""
echo "[1.2] 显示 CPU 使用率..."
if run_test show-cpu-usage; then
    ((passed++))
else
    ((failed++))
fi

# ============ 第二阶段：进程级分析 ============
echo ""
echo "========================================"
echo "第二阶段：进程级分析"
echo "========================================"

# 2.1 TOP进程
echo ""
echo "[2.1] 获取 TOP 进程..."
if run_test get-process-top --top-n 5; then
    ((passed++))
else
    ((failed++))
fi

# 2.2 进程组分析
echo ""
echo "[2.2] 获取进程组 TOP..."
if run_test get-comm-top --top-n 5; then
    ((passed++))
else
    ((failed++))
fi

# 2.3 进程多样性检测
echo ""
echo "[2.3] 检测进程风暴..."
if run_test count-process-variety --top-n 10; then
    ((passed++))
else
    ((failed++))
fi

# 2.4 进程名聚类
echo ""
echo "[2.4] 进程名聚类分析..."
if run_test cluster-comm --top-n 10; then
    ((passed++))
else
    ((failed++))
fi

# ============ 第三阶段：热点函数分析 ============
echo ""
echo "========================================"
echo "第三阶段：热点函数分析"
echo "========================================"

# 3.1 获取热点函数
echo ""
echo "[3.1] 获取热点函数 (self)..."
if run_test get-hotspots --sort-by self --top-n 10; then
    ((passed++))
else
    ((failed++))
fi

echo ""
echo "[3.2] 获取热点函数 (inclusive)..."
if run_test get-hotspots --sort-by inclusive --top-n 10; then
    ((passed++))
else
    ((failed++))
fi

# 3.2 查找调用者 (选择第一个热点函数)
echo ""
echo "[3.3] 查找热点调用者..."
# 获取第一个热点函数
first_hotspot=$(SPEAR_DATA="$DATA_FILE" "$SPEAR" get-hotspots --sort-by self --top-n 1 2>/dev/null | grep -E '^\s+[a-zA-Z_]' | head -1 | awk '{print $1}')
if [ -n "$first_hotspot" ] && [ "$first_hotspot" != "symbol" ]; then
    echo "   目标函数: $first_hotspot"
    if run_test find-callers --target "$first_hotspot" --min-ratio 1.0; then
        ((passed++))
    else
        ((failed++))
    fi
else
    echo -e "${YELLOW}⚠️ [SKIP]${NC} 未找到有效热点函数进行调用者分析"
fi

# ============ 第四阶段：语义聚类分析 ============
echo ""
echo "========================================"
echo "第四阶段：语义聚类分析"
echo "========================================"

# 4.1 符号语义聚类
echo ""
echo "[4.1] 符号语义聚类..."
if run_test cluster-symbols; then
    ((passed++))
else
    ((failed++))
fi

# 4.2 调用路径聚类
echo ""
echo "[4.2] 调用路径聚类..."
if run_test cluster-paths --min-depth 3 --top-n 5; then
    ((passed++))
else
    ((failed++))
fi

# ============ 第五阶段：负载分布分析 ============
echo ""
echo "========================================"
echo "第五阶段：负载分布分析"
echo "========================================"

# 5.1 核心负载分布
echo ""
echo "[5.1] 分析核心负载分布..."
if run_test analyze-core-distribution; then
    ((passed++))
else
    ((failed++))
fi

# ============ 第六阶段：可视化工具 ============
echo ""
echo "========================================"
echo "第六阶段：可视化工具"
echo "========================================"

# 6.1 生成火焰图数据
echo ""
echo "[6.1] 生成火焰图格式数据..."
if run_test generate-flamegraph; then
    ((passed++))
else
    ((failed++))
fi

# 6.2 生成调用图
echo ""
echo "[6.2] 生成调用图..."
if run_test generate-callgraph --format json; then
    ((passed++))
else
    ((failed++))
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

# 清理临时目录
cd "$SCRIPT_DIR"
rm -rf "$TMP_DIR"

if [ $failed -eq 0 ]; then
    echo -e "${GREEN}🎉 所有测试通过！${NC}"
    echo "perf_format 格式数据与工具集完全兼容。"
    exit 0
else
    echo -e "${RED}⚠️ 部分测试失败${NC}"
    echo "请检查工具输出和数据格式。"
    exit 1
fi
