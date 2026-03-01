#!/bin/bash
#
# Perfdata 验证工具测试脚本
# 使用 SPEAR perf-hunter 工具集验证 perfdata 下各个目录的数据格式
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="${SKILL_DIR:-$HOME/.config/agents/skills/perf-hunter}"
SPEAR="$SKILL_DIR/scripts/spear"

# 检查结果并输出
# 参数: $1=测试名, $2=退出码, $3=输出内容
check_result() {
    local test_name="$1"
    local exit_code="$2"
    local output="$3"
    
    if [ $exit_code -eq 0 ]; then
        echo "✅ [PASS] $test_name"
        return 0
    else
        echo "❌ [FAIL] $test_name (exit code: $exit_code)"
        echo "   Output: $output"
        return 1
    fi
}

# 运行单个工具测试
# 参数: $1=数据文件, $2=工具名, $3+=工具参数
run_tool_test() {
    local data_file="$1"
    local tool_name="$2"
    shift 2
    
    local output
    local exit_code
    
    output=$(SPEAR_DATA="$data_file" "$SPEAR" "$tool_name" "$@" 2>&1) || exit_code=$?
    exit_code=${exit_code:-0}
    
    echo "$output"
    return $exit_code
}

# 测试单个数据目录
# 参数: $1=目录名, $2=数据文件名
test_data_directory() {
    local dir_name="$1"
    local data_file="$2"
    local full_path="$SCRIPT_DIR/$dir_name/$data_file"
    
    echo ""
    echo "========================================"
    echo "Testing: $dir_name ($data_file)"
    echo "========================================"
    
    if [ ! -f "$full_path" ]; then
        echo "❌ [FAIL] Data file not found: $full_path"
        return 1
    fi
    
    local passed=0
    local failed=0
    
    # 1. 基础工具测试 - 环境评估
    echo ""
    echo "--- 1. 环境评估工具测试 ---"
    
    echo "Testing: check-cpu-bottleneck"
    if run_tool_test "$full_path" check-cpu-bottleneck > /dev/null 2>&1; then
        echo "✅ [PASS] check-cpu-bottleneck"
        ((passed++))
    else
        echo "❌ [FAIL] check-cpu-bottleneck"
        ((failed++))
    fi
    
    echo "Testing: show-cpu-usage"
    if run_tool_test "$full_path" show-cpu-usage > /dev/null 2>&1; then
        echo "✅ [PASS] show-cpu-usage"
        ((passed++))
    else
        echo "❌ [FAIL] show-cpu-usage"
        ((failed++))
    fi
    
    # 2. 进程分析工具
    echo ""
    echo "--- 2. 进程分析工具测试 ---"
    
    echo "Testing: get-process-top"
    if run_tool_test "$full_path" get-process-top --top-n 5 > /dev/null 2>&1; then
        echo "✅ [PASS] get-process-top"
        ((passed++))
    else
        echo "❌ [FAIL] get-process-top"
        ((failed++))
    fi
    
    echo "Testing: get-comm-top"
    if run_tool_test "$full_path" get-comm-top --top-n 5 > /dev/null 2>&1; then
        echo "✅ [PASS] get-comm-top"
        ((passed++))
    else
        echo "❌ [FAIL] get-comm-top"
        ((failed++))
    fi
    
    # 3. 热点分析工具
    echo ""
    echo "--- 3. 热点分析工具测试 ---"
    
    echo "Testing: get-hotspots"
    if run_tool_test "$full_path" get-hotspots --top-n 10 --sort-by self > /dev/null 2>&1; then
        echo "✅ [PASS] get-hotspots"
        ((passed++))
    else
        echo "❌ [FAIL] get-hotspots"
        ((failed++))
    fi
    
    echo "Testing: cluster-symbols"
    if run_tool_test "$full_path" cluster-symbols > /dev/null 2>&1; then
        echo "✅ [PASS] cluster-symbols"
        ((passed++))
    else
        echo "❌ [FAIL] cluster-symbols"
        ((failed++))
    fi
    
    # 4. 领域定位工具
    echo ""
    echo "--- 4. 领域定位工具测试 ---"
    
    echo "Testing: count-process-variety"
    if run_tool_test "$full_path" count-process-variety --top-n 10 > /dev/null 2>&1; then
        echo "✅ [PASS] count-process-variety"
        ((passed++))
    else
        echo "❌ [FAIL] count-process-variety"
        ((failed++))
    fi
    
    echo "Testing: cluster-comm"
    if run_tool_test "$full_path" cluster-comm --top-n 10 > /dev/null 2>&1; then
        echo "✅ [PASS] cluster-comm"
        ((passed++))
    else
        echo "❌ [FAIL] cluster-comm"
        ((failed++))
    fi
    
    # 5. 负载分布工具
    echo ""
    echo "--- 5. 负载分布工具测试 ---"
    
    echo "Testing: analyze-core-distribution"
    if run_tool_test "$full_path" analyze-core-distribution > /dev/null 2>&1; then
        echo "✅ [PASS] analyze-core-distribution"
        ((passed++))
    else
        echo "❌ [FAIL] analyze-core-distribution"
        ((failed++))
    fi
    
    # 6. 可视化工具
    echo ""
    echo "--- 6. 可视化工具测试 ---"
    
    echo "Testing: generate-flamegraph"
    if run_tool_test "$full_path" generate-flamegraph > /dev/null 2>&1; then
        echo "✅ [PASS] generate-flamegraph"
        ((passed++))
    else
        echo "❌ [FAIL] generate-flamegraph"
        ((failed++))
    fi
    
    # 汇总
    echo ""
    echo "--- 测试结果汇总 ($dir_name) ---"
    echo "通过: $passed, 失败: $failed"
    
    return $failed
}

# 主函数
main() {
    echo "========================================"
    echo "Perfdata 验证工具测试"
    echo "========================================"
    echo "SKILL_DIR: $SKILL_DIR"
    echo "SPEAR: $SPEAR"
    echo ""
    
    # 检查工具是否存在
    if [ ! -f "$SPEAR" ]; then
        echo "❌ [ERROR] spear script not found: $SPEAR"
        echo "请设置 SKILL_DIR 环境变量指向 perf-hunter skill 目录"
        echo "或者使用 'spear init' 初始化环境"
        exit 1
    fi
    
    local total_passed=0
    local total_failed=0
    local total_dirs=0
    
    # 遍历 perfdata 下的所有子目录
    for data_dir in "$SCRIPT_DIR"/*/; do
        [ -d "$data_dir" ] || continue
        
        dir_name=$(basename "$data_dir")
        [[ "$dir_name" == .* ]] && continue
        
        ((total_dirs++))
        
        # 查找该目录下的 .data 文件
        data_file=$(find "$data_dir" -maxdepth 1 -name "*.data" -type f | head -1)
        
        if [ -z "$data_file" ]; then
            echo "⚠️  [SKIP] No .data file found in $dir_name"
            continue
        fi
        
        data_filename=$(basename "$data_file")
        
        if test_data_directory "$dir_name" "$data_filename"; then
            ((total_passed++))
        else
            ((total_failed++))
        fi
    done
    
    # 最终汇总
    echo ""
    echo "========================================"
    echo "最终测试结果"
    echo "========================================"
    echo "测试目录数: $total_dirs"
    echo "通过: $total_passed"
    echo "失败: $total_failed"
    
    if [ $total_failed -eq 0 ]; then
        echo ""
        echo "🎉 所有测试通过！"
        exit 0
    else
        echo ""
        echo "⚠️  部分测试失败，请检查输出"
        exit 1
    fi
}

# 运行主函数
main "$@"
