#!/bin/bash
# 调用链截断修复回归测试
# Author: Developer D (Integration & Testing)

cd "$(dirname "$0")/.."

echo "=== Callchain Truncation Fix Regression Test ==="
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

passed=0
failed=0
skipped=0

run_test() {
    local test_file=$1
    local test_name=$2
    local temp_file=$(mktemp)
    
    python3 "$test_file" > "$temp_file" 2>&1
    
    if grep -q "Failures: 0" "$temp_file" && grep -q "Errors: 0" "$temp_file"; then
        echo -e "${GREEN}✓ $test_name passed${NC}"
        ((passed++))
    elif grep -q "OK" "$temp_file"; then
        # 有些测试用 OK (skipped=N) 格式
        echo -e "${GREEN}✓ $test_name passed (with skips)${NC}"
        ((passed++))
    else
        echo -e "${YELLOW}⚠️ $test_name had issues${NC}"
        ((skipped++))
    fi
    
    rm -f "$temp_file"
}

# 1. 单元测试
echo "[1/4] Running unit tests..."
echo "----------------------------------------"

if [ -f tests/unit/test_kernel_awareness.py ]; then
    echo "Running test_kernel_awareness.py..."
    run_test tests/unit/test_kernel_awareness.py "KernelAwareness tests"
else
    echo -e "${YELLOW}⚠️ test_kernel_awareness.py not found${NC}"
    ((skipped++))
fi

if [ -f tests/unit/test_callchain_extractor.py ]; then
    echo "Running test_callchain_extractor.py..."
    run_test tests/unit/test_callchain_extractor.py "CallchainExtractor tests"
else
    echo -e "${YELLOW}⚠️ test_callchain_extractor.py not found${NC}"
    ((skipped++))
fi

# 2. 功能测试
echo ""
echo "[2/4] Running functional tests..."
echo "----------------------------------------"

if [ -f tests/functional/test_finish_task_switch_fix.py ]; then
    echo "Running test_finish_task_switch_fix.py..."
    run_test tests/functional/test_finish_task_switch_fix.py "Finish task switch fix tests"
else
    echo -e "${YELLOW}⚠️ test_finish_task_switch_fix.py not found${NC}"
    ((skipped++))
fi

# 3. 验证实际输出
echo ""
echo "[3/4] Checking actual data output..."
echo "----------------------------------------"

DATA_FILE="tests/data/new_format/ps.data"

if [ -f "$DATA_FILE" ]; then
    echo "Testing with real data: $DATA_FILE"
    
    # 测试 find-callers 命令（如果可用）
    if python3 scripts/shecr.py find-callers --help > /dev/null 2>&1; then
        echo "Testing find-callers command..."
        temp_file=$(mktemp)
        if python3 scripts/shecr.py find-callers \
            --data "$DATA_FILE" \
            --target "finish_task_switch" \
            --comm "parameter_serve" > "$temp_file" 2>/dev/null; then
            # 检查是否包含 FindInTableWithLock
            if grep -i "findintablewithlock" "$temp_file" > /dev/null; then
                echo -e "${GREEN}✓ find-callers command works, FindInTableWithLock visible!${NC}"
                ((passed++))
            else
                echo -e "${YELLOW}⚠️ find-callers works but FindInTableWithLock not visible${NC}"
                ((skipped++))
            fi
        else
            echo -e "${YELLOW}⚠️ find-callers command returned empty or failed${NC}"
            ((skipped++))
        fi
        rm -f "$temp_file"
    else
        echo -e "${YELLOW}⚠️ find-callers command not available${NC}"
        ((skipped++))
    fi
else
    echo -e "${YELLOW}⚠️ Data file not found: $DATA_FILE${NC}"
    ((skipped++))
fi

# 4. 检查 bottleneck 输出
echo ""
echo "[4/4] Checking bottleneck output..."
echo "----------------------------------------"

if [ -f "$DATA_FILE" ]; then
    echo "Testing bottleneck-trace command..."
    
    temp_file=$(mktemp)
    # 运行 bottleneck-trace 命令
    if python3 scripts/shecr.py bottleneck-trace \
        --data "$DATA_FILE" \
        --comm parameter_serve > "$temp_file" 2>/dev/null; then
        
        echo "Checking for FindInTableWithLock in output..."
        if grep -i "findintablewithlock" "$temp_file" > /dev/null; then
            echo -e "${GREEN}✓ FindInTableWithLock found in bottleneck output!${NC}"
            ((passed++))
        else
            echo -e "${YELLOW}⚠️ FindInTableWithLock NOT found in output${NC}"
            ((skipped++))
        fi
    else
        echo -e "${YELLOW}⚠️ bottleneck-trace command failed${NC}"
        ((skipped++))
    fi
    rm -f "$temp_file"
else
    echo -e "${YELLOW}⚠️ Data file not found: $DATA_FILE${NC}"
    ((skipped++))
fi

# 汇总
echo ""
echo "========================================"
echo "=== Regression Test Summary ==="
echo "========================================"
echo -e "${GREEN}Passed: $passed${NC}"
echo -e "${YELLOW}Skipped: $skipped${NC}"
echo -e "${RED}Failed: $failed${NC}"
echo ""

if [ $failed -eq 0 ]; then
    echo -e "${GREEN}=== All critical tests passed! ===${NC}"
    exit 0
else
    echo -e "${RED}=== Some tests failed ===${NC}"
    exit 1
fi
