#!/bin/bash
# Live Document 测试执行脚本

# 注意：不使用 set -e，因为需要处理预期的失败情况（如 TC-07）

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PERF_EXPERT="../../scripts/perf_expert.py"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 打印函数
print_header() {
    echo ""
    echo "========================================"
    echo "$1"
    echo "========================================"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# 清理环境
cleanup() {
    rm -f .perf-doc.json report.md report.json diagnosis_report.md
}

# 运行单个测试用例
run_single_test() {
    local tc_name=$1
    local tc_file="${tc_name}.md"
    
    if [[ ! -f "$tc_file" ]]; then
        print_error "测试用例不存在: $tc_file"
        return 1
    fi
    
    print_header "执行测试: $tc_name"
    
    case $tc_name in
        tc_01_init)
            run_tc_01
            ;;
        tc_02_add_single)
            run_tc_02
            ;;
        tc_03_add_multiple)
            run_tc_03
            ;;
        tc_04_complete)
            run_tc_04
            ;;
        tc_05_list)
            run_tc_05
            ;;
        tc_06_finalize_ready)
            run_tc_06
            ;;
        tc_07_finalize_blocked)
            run_tc_07
            ;;
        tc_08_export)
            run_tc_08
            ;;
        tc_09_duplicate_id)
            run_tc_09
            ;;
        tc_10_full_scenario)
            run_tc_10
            ;;
        *)
            print_error "未知的测试用例: $tc_name"
            return 1
            ;;
    esac
}

# TC-01: 初始化文档
run_tc_01() {
    print_warning "清理环境"
    cleanup
    
    print_warning "执行: doc init"
    python "$PERF_EXPERT" doc init --data ./perf.data.txt
    
    if [[ -f ".perf-doc.json" ]]; then
        print_success "文档文件已创建"
        cat .perf-doc.json
    else
        print_error "文档文件未创建"
        return 1
    fi
}

# TC-02: 添加单个问题
run_tc_02() {
    cleanup
    python "$PERF_EXPERT" doc init --data perf.data.txt
    
    print_warning "执行: doc add ISS-001"
    python "$PERF_EXPERT" doc add \
        --id ISS-001 \
        --desc "netstat 高内核态 94.7%" \
        --risk "可能比表面看起来更严重" \
        --hint "cluster-symbols --comm netstat"
    
    print_warning "验证列表"
    python "$PERF_EXPERT" doc list
}

# TC-03: 添加多个问题
run_tc_03() {
    cleanup
    python "$PERF_EXPERT" doc init --data netstat_perf.data
    
    print_warning "添加 4 个问题（模拟 get-comm-top 输出）"
    
    python "$PERF_EXPERT" doc add \
        --id ISS-001 \
        --desc "netstat: 2623 PIDs, 243.87% CPU, 94.7% kernel" \
        --risk "进程风暴" \
        --hint "cluster-symbols --comm netstat"
    
    python "$PERF_EXPERT" doc add \
        --id ISS-002 \
        --desc "containerd-shim: 240 PIDs, 96.01% CPU, 89.9% kernel" \
        --risk "可能比 netstat 更严重，单进程影响大" \
        --hint "cluster-symbols --comm containerd-shim"
    
    python "$PERF_EXPERT" doc add \
        --id ISS-003 \
        --desc "python3: 826 PIDs, 207.17% CPU, 35.2% kernel" \
        --risk "worker pool 可能过度扩容" \
        --hint "cluster-symbols --comm python3"
    
    python "$PERF_EXPERT" doc list
}

# TC-04: 标记问题完成
run_tc_04() {
    # 先执行 TC-03 的准备
    cleanup
    python "$PERF_EXPERT" doc init --data netstat_perf.data
    python "$PERF_EXPERT" doc add --id ISS-001 --desc "问题A" --risk "高"
    python "$PERF_EXPERT" doc add --id ISS-002 --desc "问题B" --risk "中"
    
    print_warning "标记 ISS-001 完成"
    python "$PERF_EXPERT" doc complete \
        --id ISS-001 \
        --result "LOCK_CONTENTION 38.36%, 锁竞争已定位"
    
    print_warning "当前状态"
    python "$PERF_EXPERT" doc list
}

# TC-05: 列出过滤
run_tc_05() {
    # 准备数据
    cleanup
    python "$PERF_EXPERT" doc init --data test.data
    python "$PERF_EXPERT" doc add --id ISS-001 --desc "问题A"
    python "$PERF_EXPERT" doc add --id ISS-002 --desc "问题B"
    python "$PERF_EXPERT" doc complete --id ISS-001 --result "已解决"
    
    print_warning "列出所有 (--status all)"
    python "$PERF_EXPERT" doc list --status all
    
    print_warning "列出 pending (--status pending)"
    python "$PERF_EXPERT" doc list --status pending
    
    print_warning "列出 completed (--status completed)"
    python "$PERF_EXPERT" doc list --status completed
    
    print_warning "JSON 格式 (--format json)"
    python "$PERF_EXPERT" doc list --format json | head -30
}

# TC-06: 最终审计 - 全部完成
run_tc_06() {
    cleanup
    python "$PERF_EXPERT" doc init --data test.data
    python "$PERF_EXPERT" doc add --id ISS-001 --desc "问题A"
    python "$PERF_EXPERT" doc add --id ISS-002 --desc "问题B"
    python "$PERF_EXPERT" doc complete --id ISS-001 --result "已解决"
    python "$PERF_EXPERT" doc complete --id ISS-002 --result "已解决"
    
    print_warning "执行 finalize（应该通过）"
    python "$PERF_EXPERT" doc finalize
}

# TC-07: 最终审计 - 被阻止
run_tc_07() {
    cleanup
    python "$PERF_EXPERT" doc init --data test.data
    python "$PERF_EXPERT" doc add --id ISS-001 --desc "问题A"
    python "$PERF_EXPERT" doc add --id ISS-002 --desc "问题B（关键）"
    python "$PERF_EXPERT" doc complete --id ISS-001 --result "已解决"
    # ISS-002 保持 pending
    
    print_warning "执行 finalize（应该有剩余风险警告）"
    python "$PERF_EXPERT" doc finalize || true  # 允许失败
    
    print_warning "使用 --accept-risk 强制通过"
    python "$PERF_EXPERT" doc finalize --accept-risk "问题B影响范围小，可接受"
}

# TC-08: 导出报告
run_tc_08() {
    cleanup
    python "$PERF_EXPERT" doc init --data test.data
    python "$PERF_EXPERT" doc add --id ISS-001 --desc "netstat 高内核态" --risk "高" --hint "cluster-symbols"
    python "$PERF_EXPERT" doc complete --id ISS-001 --result "LOCK_CONTENTION 38.36%"
    
    print_warning "导出 Markdown"
    python "$PERF_EXPERT" doc export --format markdown --output report.md
    cat report.md
    
    print_warning "导出 JSON"
    python "$PERF_EXPERT" doc export --format json --output report.json
    cat report.json
}

# TC-09: 重复 ID 检测
run_tc_09() {
    cleanup
    python "$PERF_EXPERT" doc init --data test.data
    python "$PERF_EXPERT" doc add --id ISS-001 --desc "第一个问题"
    
    print_warning "尝试添加重复 ID（应该失败）"
    python "$PERF_EXPERT" doc add --id ISS-001 --desc "重复的问题" || print_success "正确拒绝了重复 ID"
    
    print_warning "验证只有 1 个问题"
    python "$PERF_EXPERT" doc list
}

# TC-10: 完整场景
run_tc_10() {
    cleanup
    print_header "TC-10: netstat/containerd-shim 完整场景"
    
    python "$PERF_EXPERT" doc init --data netstat_perf.data
    
    print_warning "记录所有 4 个问题"
    python "$PERF_EXPERT" doc add --id ISS-001 --desc "netstat: 2623 PIDs, 94.7% kernel" --risk "进程风暴" --hint "cluster-symbols --comm netstat"
    python "$PERF_EXPERT" doc add --id ISS-002 --desc "python3: 826 PIDs, 35.2% kernel" --risk "worker pool" --hint "cluster-symbols --comm python3"
    python "$PERF_EXPERT" doc add --id ISS-003 --desc "dbatman: 311 PIDs, 26.4% kernel" --risk "中等" --hint "cluster-symbols --comm dbatman"
    python "$PERF_EXPERT" doc add --id ISS-004 --desc "containerd-shim: 240 PIDs, 89.9% kernel" --risk "⚠️ 可能比netstat更严重" --hint "cluster-symbols --comm containerd-shim"
    
    echo ""
    print_warning "=== 所有待办问题 ==="
    python "$PERF_EXPERT" doc list
    
    echo ""
    print_warning "=== 完成 netstat 分析 ==="
    python "$PERF_EXPERT" doc complete --id ISS-001 --result "LOCK_CONTENTION 38.36%"
    
    echo ""
    print_warning "=== 关键：此时应提示还有 3 个 pending，包括 containerd-shim ==="
    python "$PERF_EXPERT" doc list
    
    echo ""
    print_warning "=== 完成其他问题 ==="
    python "$PERF_EXPERT" doc complete --id ISS-004 --result "LOCK_CONTENTION 79.84% !!! 是netstat的2倍"
    python "$PERF_EXPERT" doc complete --id ISS-002 --result "NORMAL"
    python "$PERF_EXPERT" doc complete --id ISS-003 --result "LOW_PRIORITY"
    
    echo ""
    print_warning "=== 最终审计 ==="
    python "$PERF_EXPERT" doc finalize
    
    echo ""
    print_warning "=== 生成报告 ==="
    python "$PERF_EXPERT" doc export --format markdown --output diagnosis_report.md
    cat diagnosis_report.md
}

# 运行所有测试
run_all_tests() {
    local tests=("tc_01_init" "tc_02_add_single" "tc_03_add_multiple" "tc_04_complete" "tc_05_list" "tc_06_finalize_ready" "tc_07_finalize_blocked" "tc_08_export" "tc_09_duplicate_id" "tc_10_full_scenario")
    
    local passed=0
    local failed=0
    
    for tc in "${tests[@]}"; do
        if run_single_test "$tc"; then
            ((passed++))
            print_success "$tc 通过"
        else
            ((failed++))
            print_error "$tc 失败"
        fi
        cleanup
    done
    
    echo ""
    print_header "测试结果汇总"
    echo "通过: $passed"
    echo "失败: $failed"
    echo "总计: ${#tests[@]}"
    
    if [[ $failed -eq 0 ]]; then
        print_success "所有测试通过！"
        return 0
    else
        print_error "有测试失败"
        return 1
    fi
}

# 主入口
main() {
    if [[ $# -eq 0 ]]; then
        echo "用法: $0 <test_name|all>"
        echo ""
        echo "可用测试:"
        echo "  tc_01_init           - 初始化文档"
        echo "  tc_02_add_single     - 添加单个问题"
        echo "  tc_03_add_multiple   - 添加多个问题"
        echo "  tc_04_complete       - 标记完成"
        echo "  tc_05_list           - 列出过滤"
        echo "  tc_06_finalize_ready - 最终审计（通过）"
        echo "  tc_07_finalize_blocked - 最终审计（阻止）"
        echo "  tc_08_export         - 导出报告"
        echo "  tc_09_duplicate_id   - 重复ID检测"
        echo "  tc_10_full_scenario  - 完整场景"
        echo "  all                  - 运行所有测试"
        exit 1
    fi
    
    local cmd=$1
    
    if [[ "$cmd" == "all" ]]; then
        run_all_tests
    else
        run_single_test "$cmd"
    fi
}

main "$@"
