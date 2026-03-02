#!/bin/bash
#
# 三层架构一键测试脚本
# 
# 使用方法:
#   chmod +x tests/three_tier/test.sh
#   ./tests/three_tier/test.sh
#

set -e  # 遇到错误立即退出

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# 脚本目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

echo ""
echo -e "${BOLD}========================================${NC}"
echo -e "${BOLD}  三层架构测试套件${NC}"
echo -e "${BOLD}========================================${NC}"
echo ""
echo "项目路径: ${PROJECT_ROOT}"
echo ""

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}错误: 未找到 python3${NC}"
    exit 1
fi

cd "${PROJECT_ROOT}"

# ========================================
# Step 1: 接口验证
# ========================================
echo -e "${BOLD}[Step 1/3] 验证接口状态...${NC}"
echo "----------------------------------------"
python3 tests/three_tier/verify_interfaces.py 2>&1 | grep -E "^(  ✅|  ❌|  ⚠️|Layer|Core|Layer 2|Layer 3|输出模型|Trace)" || true
echo ""

# ========================================
# Step 2: 快速测试
# ========================================
echo -e "${BOLD}[Step 2/3] 运行快速测试...${NC}"
echo "----------------------------------------"
python3 tests/three_tier/quick_test.py
echo ""

# ========================================
# Step 3: 完整测试
# ========================================
echo -e "${BOLD}[Step 3/3] 运行完整测试...${NC}"
echo "----------------------------------------"
python3 tests/three_tier/run_all_tests.py -v
echo ""

echo -e "${BOLD}========================================${NC}"
echo -e "${BOLD}  测试完成${NC}"
echo -e "${BOLD}========================================${NC}"
echo ""

# 显示帮助
echo "其他命令:"
echo "  接口验证    : python3 tests/three_tier/verify_interfaces.py"
echo "  快速测试    : python3 tests/three_tier/quick_test.py"
echo "  完整测试    : python3 tests/three_tier/run_all_tests.py -v"
echo "  Core测试    : python3 tests/three_tier/test_core_interfaces.py -v"
echo "  Facade测试  : python3 tests/three_tier/test_facade_interfaces.py -v"
echo "  Composite测试: python3 tests/three_tier/test_composite_commands.py -v"
echo ""
