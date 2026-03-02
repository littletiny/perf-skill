#!/usr/bin/env python3
"""
SPEAR Pipeline 使用示例

展示如何使用多轮 Agent 流水线进行诊断-审计-复查。
"""

import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import PipelineController, PipelineConfig
from pipeline.agents import DiagnoseAgent, AuditAgent, RecheckAgent


def example_basic():
    """基础示例：运行完整流水线"""
    print("=" * 60)
    print("示例 1: 基础用法 - 运行完整流水线")
    print("=" * 60)
    
    # 配置
    config = PipelineConfig(
        max_rounds=2,
        strict_audit=True,
        auto_recheck=True
    )
    
    # 创建控制器
    controller = PipelineController(config)
    controller.init(
        perf_data="/path/to/perf.data",  # 替换为实际路径
        symptom="系统响应慢，CPU使用率100%",
        work_dir="./example_case_001"
    )
    
    # 创建 Agents
    diagnose_agent = DiagnoseAgent()
    audit_agent = AuditAgent()
    recheck_agent = RecheckAgent()
    
    # 运行流水线
    try:
        result = controller.run(
            diagnose_agent=diagnose_agent,
            audit_agent=audit_agent,
            recheck_agent=recheck_agent
        )
        
        print(f"\n✅ 流水线完成!")
        print(f"   状态: {result['final_status']}")
        print(f"   审计通过: {result['audit']['passed']}")
        print(f"   工作目录: {result['context']['work_dir']}")
        
    except Exception as e:
        print(f"\n❌ 流水线失败: {e}")


def example_step_by_step():
    """分步执行示例"""
    print("\n" + "=" * 60)
    print("示例 2: 分步执行")
    print("=" * 60)
    
    controller = PipelineController()
    controller.init(
        perf_data="/path/to/perf.data",
        symptom="MySQL 响应延迟高",
        work_dir="./example_case_002"
    )
    
    # Round 1: 诊断
    print("\n▶️  Round 1: 诊断...")
    diagnose_agent = DiagnoseAgent()
    round1_result = controller.run_round1_diagnose(diagnose_agent)
    print(f"   发现 {round1_result['issues_count']} 个 issues")
    print(f"   解决 {round1_result['completed_count']} 个 issues")
    
    # Round 2: 审计
    print("\n▶️  Round 2: 审计...")
    audit_agent = AuditAgent()
    audit_result = controller.run_round2_audit(audit_agent)
    print(f"   审计结果: {audit_result['overall_status']}")
    print(f"   通过: {audit_result['summary']['passed']}")
    print(f"   失败: {audit_result['summary']['failed']}")
    
    # Round 3: 复查（如果需要）
    if audit_result['overall_status'] == 'failed':
        print("\n▶️  Round 3: 复查...")
        recheck_agent = RecheckAgent()
        recheck_result = controller.run_round3_recheck(recheck_agent)
        print(f"   修复 {len(recheck_result['enhancements'])} 个问题")
    else:
        print("\n✅ 审计通过，无需复查")
    
    # 生成最终报告
    final_report = controller._generate_final_report()
    print(f"\n✅ 最终报告: {final_report.get('context', {}).get('work_dir')}/pipeline_report.json")


def example_custom_agent():
    """自定义 Agent 示例"""
    print("\n" + "=" * 60)
    print("示例 3: 自定义 Agent")
    print("=" * 60)
    
    class MyDiagnoseAgent(DiagnoseAgent):
        """自定义诊断 Agent，添加额外检查"""
        
        def _execute_diagnosis(self, perf_data, symptom):
            findings = super()._execute_diagnosis(perf_data, symptom)
            
            # 添加自定义分析
            print("   [Custom] 添加核心分布分析...")
            # 这里可以调用自定义的 spear 命令
            
            return findings
    
    class StrictAuditAgent(AuditAgent):
        """更严格的审计 Agent"""
        
        def _check_depth(self, issues, debug_dir):
            result = super()._check_depth(issues, debug_dir)
            
            # 额外检查：要求必须有溯源分析
            for issue_id, issue in issues.items():
                result_text = issue.get('result', '')
                has_trace = any(kw in result_text for kw in 
                               ['调用链', 'caller', 'trace', '溯源', 'find-callers'])
                if not has_trace:
                    result['failed_issues'].append({
                        'id': issue_id,
                        'check': 'missing_trace',
                        'reason': 'Result must include trace-to-source analysis',
                        'severity': 'critical'
                    })
            
            return result
    
    controller = PipelineController()
    controller.init(
        perf_data="/path/to/perf.data",
        symptom="自定义分析场景",
        work_dir="./example_case_003"
    )
    
    print("\n使用自定义 Agents...")
    result = controller.run(
        diagnose_agent=MyDiagnoseAgent(),
        audit_agent=StrictAuditAgent(),
        recheck_agent=RecheckAgent()
    )
    
    print(f"\n✅ 完成: {result['final_status']}")


def example_resume():
    """恢复流水线示例"""
    print("\n" + "=" * 60)
    print("示例 4: 保存和恢复流水线状态")
    print("=" * 60)
    
    # 第一次运行
    controller = PipelineController()
    controller.init(
        perf_data="/path/to/perf.data",
        symptom="恢复测试",
        work_dir="./example_case_004"
    )
    
    # 只运行诊断轮
    diagnose_agent = DiagnoseAgent()
    controller.run_round1_diagnose(diagnose_agent)
    
    # 保存状态
    state_file = controller.save()
    print(f"\n状态已保存: {state_file}")
    
    # 模拟中断后恢复
    print("\n模拟中断后恢复...")
    new_controller = PipelineController()
    new_controller.load(state_file)
    
    # 查看状态
    status = new_controller.get_status()
    print(f"恢复后的状态: {status['status']}")
    print(f"当前轮次: {status['round']}")
    print(f"可用产物: {', '.join(status['artifacts'])}")
    
    # 继续运行
    print("\n继续运行审计轮...")
    audit_agent = AuditAgent()
    new_controller.run_round2_audit(audit_agent)
    
    print("\n✅ 流水线继续完成")


def print_documentation():
    """打印文档链接"""
    print("\n" + "=" * 60)
    print("相关文档")
    print("=" * 60)
    print("""
架构设计: docs/agent-pipeline-design.md
使用指南: docs/agent-pipeline-usage.md
审计流程: docs/audit-process.md
Trace设计: docs/design-rationale-trace-v2.md

Python API:
  from pipeline import PipelineController, PipelineConfig
  from pipeline.agents import DiagnoseAgent, AuditAgent, RecheckAgent

CLI 用法:
  python -m pipeline.cli run --data perf.data --symptom "CPU高"
  python -m pipeline.cli diagnose --data perf.data --output ./case
  python -m pipeline.cli audit --spear-json ./case/.spear.json
  python -m pipeline.cli recheck --audit-report ./case/audit_report.json
""")


if __name__ == '__main__':
    print("SPEAR Agent Pipeline 使用示例")
    print("=" * 60)
    print()
    print("说明：")
    print("- 这些示例展示了 Pipeline 的各种用法")
    print("- 请将 '/path/to/perf.data' 替换为实际的 perf 数据文件路径")
    print("- 运行示例前确保已安装 SPEAR 工具链")
    print()
    
    # 显示示例列表
    examples = [
        ("基础用法", example_basic),
        ("分步执行", example_step_by_step),
        ("自定义 Agent", example_custom_agent),
        ("保存和恢复", example_resume),
    ]
    
    print("可用示例:")
    for i, (name, _) in enumerate(examples, 1):
        print(f"  {i}. {name}")
    print("  5. 显示文档链接")
    print("  0. 退出")
    print()
    
    # 交互式选择
    try:
        while True:
            choice = input("选择示例 (0-5): ").strip()
            
            if choice == '0':
                break
            elif choice == '5':
                print_documentation()
            elif choice in ['1', '2', '3', '4']:
                examples[int(choice) - 1][1]()
            else:
                print("无效选择，请重试")
                
    except KeyboardInterrupt:
        print("\n\n已退出")
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n示例运行完成!")
