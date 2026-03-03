#!/usr/bin/env python3
"""Simplified Agent Pipeline - 使用 code agent 作为 stage

变量语法: {{var}} 或 {{stage.output.key}}
条件语法: when: "{{var}} == 'value'" / "exists({{file}})" / "A and B"
"""

import yaml
import subprocess
import sys
import argparse
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
import operator


@dataclass
class AgentConfig:
    """Agent 配置"""
    system_prompt: Optional[str] = None
    allowed_dirs: List[str] = field(default_factory=list)
    default_permissions: str = "read-write"  # read-only | read-write | write-only
    timeout: int = 300
    model: str = "kimi"
    working_dir: Optional[str] = None
    # 其他自定义参数
    extra_args: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StageConfig:
    """Stage 配置"""
    name: str
    agent: AgentConfig
    vars: Dict[str, str] = field(default_factory=dict)
    when: Optional[str] = None  # 执行条件


@dataclass
class StageResult:
    """Stage 执行结果"""
    status: str  # success / failed / skipped
    exit_code: int
    outputs: Dict[str, str] = field(default_factory=dict)
    error_message: Optional[str] = None


class ConditionEvaluator:
    """条件表达式求值器"""
    
    def __init__(self, context: Dict[str, StageResult], vars_dict: Dict[str, str]):
        self.context = context
        self.vars_dict = vars_dict
    
    def evaluate(self, condition: str) -> bool:
        """评估条件表达式"""
        if not condition:
            return True
        
        condition = condition.strip()
        
        # 解析 and/or
        if ' and ' in condition.lower():
            parts = self._split_logical(condition, 'and')
            return all(self.evaluate(p.strip()) for p in parts)
        
        if ' or ' in condition.lower():
            parts = self._split_logical(condition, 'or')
            return any(self.evaluate(p.strip()) for p in parts)
        
        # 解析括号
        if condition.startswith('(') and condition.endswith(')'):
            return self.evaluate(condition[1:-1])
        
        # 解析 not()
        if condition.lower().startswith('not(') and condition.endswith(')'):
            inner = condition[4:-1]
            return not self.evaluate(inner)
        
        # 解析 exists()
        if condition.lower().startswith('exists(') and condition.endswith(')'):
            path = condition[7:-1].strip().strip('"\'')
            resolved_path = self._resolve_vars_in_string(path)
            return Path(resolved_path).exists()
        
        # 解析比较操作
        return self._evaluate_comparison(condition)
    
    def _split_logical(self, condition: str, operator: str) -> List[str]:
        """分割逻辑表达式，注意括号嵌套"""
        parts = []
        current = []
        depth = 0
        
        i = 0
        while i < len(condition):
            char = condition[i]
            
            if char == '(':
                depth += 1
            elif char == ')':
                depth -= 1
            
            if depth == 0:
                # 检查是否是指定的操作符
                op_lower = operator.lower()
                cond_lower = condition[i:].lower()
                if cond_lower.startswith(f' {op_lower} '):
                    parts.append(''.join(current))
                    current = []
                    i += len(op_lower) + 2
                    continue
            
            current.append(char)
            i += 1
        
        if current:
            parts.append(''.join(current))
        
        return parts
    
    def _evaluate_comparison(self, condition: str) -> bool:
        """评估比较表达式"""
        # 支持的比较操作符
        operators = {
            '==': operator.eq,
            '!=': operator.ne,
            '>': operator.gt,
            '<': operator.lt,
            '>=': operator.ge,
            '<=': operator.le,
        }
        
        for op_str, op_func in operators.items():
            if op_str in condition:
                parts = condition.split(op_str, 1)
                if len(parts) == 2:
                    left = self._resolve_value(parts[0].strip())
                    right = self._resolve_value(parts[1].strip())
                    
                    # 尝试数值比较
                    try:
                        left_num = float(left)
                        right_num = float(right)
                        return op_func(left_num, right_num)
                    except (ValueError, TypeError):
                        pass
                    
                    # 字符串比较
                    return op_func(str(left), str(right))
        
        # 没有比较操作符，检查是否为真值
        resolved = self._resolve_value(condition)
        return bool(resolved) and str(resolved).lower() not in ('false', '0', '', 'none')
    
    def _resolve_value(self, value: str) -> Any:
        """解析值（变量或字面量）"""
        value = value.strip()
        
        # 字符串字面量
        if (value.startswith('"') and value.endswith('"')) or \
           (value.startswith("'") and value.endswith("'")):
            return value[1:-1]
        
        # 变量引用
        if value.startswith('{{') and value.endswith('}}'):
            return self._resolve_var(value[2:-2].strip())
        
        # 尝试作为数字
        try:
            if '.' in value:
                return float(value)
            return int(value)
        except ValueError:
            pass
        
        return value
    
    def _resolve_var(self, var_path: str) -> Any:
        """解析变量路径"""
        var_path = var_path.strip()
        
        # 检查是否是 stage 结果引用 (stageName.status 或 stageName.exit_code)
        parts = var_path.split('.')
        if len(parts) >= 2 and parts[0] in self.context:
            stage_name = parts[0]
            result = self.context[stage_name]
            
            if parts[1] == 'status':
                return result.status
            elif parts[1] == 'exit_code':
                return result.exit_code
            elif parts[1] == 'output' and len(parts) >= 3:
                output_key = '.'.join(parts[2:])
                return result.outputs.get(output_key, '')
        
        # 检查普通变量
        return self.vars_dict.get(var_path, '')
    
    def _resolve_vars_in_string(self, content: str) -> str:
        """解析字符串中的所有 {{var}} 变量"""
        result = content
        start = 0
        
        while True:
            var_start = result.find('{{', start)
            if var_start == -1:
                break
            
            var_end = result.find('}}', var_start)
            if var_end == -1:
                break
            
            var_name = result[var_start + 2:var_end].strip()
            var_value = self._resolve_var(var_name)
            
            result = result[:var_start] + str(var_value) + result[var_end + 2:]
            start = var_start + len(str(var_value))
        
        return result


class PipelineRunner:
    """简化版 Pipeline 运行器"""
    
    def __init__(self, config_file: str):
        self.config_file = Path(config_file)
        self.config = self._load_config()
        self.results: Dict[str, StageResult] = {}  # stage 执行结果
        
    def _load_config(self) -> dict:
        """加载 YAML 配置文件"""
        with open(self.config_file, 'r') as f:
            return yaml.safe_load(f)
    
    def _get_global_vars(self) -> Dict[str, str]:
        """获取全局变量"""
        return self.config.get('vars', {})
    
    def _parse_agent_config(self, agent_dict: dict) -> AgentConfig:
        """解析 agent 配置字典"""
        return AgentConfig(
            system_prompt=agent_dict.get('system_prompt'),
            allowed_dirs=agent_dict.get('allowed_dirs', []),
            default_permissions=agent_dict.get('default_permissions', 'read-write'),
            timeout=agent_dict.get('timeout', 300),
            model=agent_dict.get('model', 'kimi'),
            working_dir=agent_dict.get('working_dir'),
            extra_args={k: v for k, v in agent_dict.items() 
                       if k not in ['system_prompt', 'allowed_dirs', 'default_permissions', 
                                   'timeout', 'model', 'working_dir']}
        )
    
    def _merge_agent_config(self, global_config: AgentConfig, 
                           stage_config: Optional[AgentConfig]) -> AgentConfig:
        """合并全局和 stage 级 agent 配置（stage 优先）"""
        if stage_config is None:
            return global_config
        
        return AgentConfig(
            system_prompt=stage_config.system_prompt or global_config.system_prompt,
            allowed_dirs=stage_config.allowed_dirs if stage_config.allowed_dirs else global_config.allowed_dirs,
            default_permissions=stage_config.default_permissions or global_config.default_permissions,
            timeout=stage_config.timeout or global_config.timeout,
            model=stage_config.model or global_config.model,
            working_dir=stage_config.working_dir or global_config.working_dir,
            extra_args={**global_config.extra_args, **stage_config.extra_args}
        )
    
    def _resolve_var(self, value: str, vars_dict: Dict[str, str]) -> str:
        """解析变量值，支持 {{var}} 和 {{stage.output.xxx}} 引用"""
        if not isinstance(value, str):
            return str(value)
        
        # 处理 {{stage.output.xxx}} 或 {{stage.status}} 引用
        if value.startswith('{{') and value.endswith('}}'):
            expr = value[2:-2].strip()  # 去掉 {{ 和 }}
            
            parts = expr.split('.')
            
            # 检查是否是 stage 结果引用
            if len(parts) >= 2 and parts[0] in self.results:
                stage_name = parts[0]
                result = self.results[stage_name]
                
                if parts[1] == 'status':
                    return result.status
                elif parts[1] == 'exit_code':
                    return str(result.exit_code)
                elif parts[1] == 'output' and len(parts) >= 3:
                    output_key = '.'.join(parts[2:])
                    return result.outputs.get(output_key, value)
            
            # 普通变量
            return vars_dict.get(expr, value)
        
        return value
    
    def _replace_vars(self, content: str, vars_dict: Dict[str, str]) -> str:
        """替换内容中的所有 {{var}} 变量"""
        result = content
        start = 0
        
        while True:
            var_start = result.find('{{', start)
            if var_start == -1:
                break
            
            var_end = result.find('}}', var_start)
            if var_end == -1:
                break
            
            var_name = result[var_start + 2:var_end].strip()
            
            # 检查是否是 stage 引用
            var_value = self._resolve_var(f'{{{{{var_name}}}}}', vars_dict)
            
            result = result[:var_start] + str(var_value) + result[var_end + 2:]
            start = var_start + len(str(var_value))
        
        return result
    
    def _resolve_all_vars(self, vars_dict: Dict[str, str]) -> Dict[str, str]:
        """递归解析所有变量（处理变量引用链）"""
        resolved = dict(vars_dict)
        
        max_iterations = 10
        for _ in range(max_iterations):
            changed = False
            new_resolved = {}
            for key, value in resolved.items():
                new_value = self._resolve_var(value, resolved)
                if new_value != value:
                    changed = True
                new_resolved[key] = new_value
            resolved = new_resolved
            if not changed:
                break
        
        return resolved
    
    def _check_condition(self, condition: str, vars_dict: Dict[str, str]) -> bool:
        """检查 stage 执行条件"""
        evaluator = ConditionEvaluator(self.results, vars_dict)
        return evaluator.evaluate(condition)
    
    def _build_agent_prompt(self, agent: AgentConfig, task_content: str) -> str:
        """构建发送给 agent 的完整 prompt"""
        lines = []
        
        # System prompt
        if agent.system_prompt and Path(agent.system_prompt).exists():
            with open(agent.system_prompt, 'r') as f:
                system_content = f.read()
            lines.append("# System Instructions")
            lines.append(system_content)
            lines.append("")
        
        # 权限说明
        lines.append("# Execution Environment")
        lines.append(f"Permissions: {agent.default_permissions}")
        
        if agent.allowed_dirs:
            lines.append("Allowed directories:")
            for d in agent.allowed_dirs:
                lines.append(f"  - {d}")
        
        if agent.working_dir:
            lines.append(f"Working directory: {agent.working_dir}")
        
        lines.append("")
        
        # 任务内容
        lines.append("# Task")
        lines.append(task_content)
        
        return "\n".join(lines)
    
    def _run_stage(self, stage_name: str, stage_config: StageConfig) -> StageResult:
        """执行单个 stage"""
        print(f"\n[STAGE] {stage_name}")
        
        # 检查执行条件
        if stage_config.when:
            evaluator = ConditionEvaluator(self.results, stage_config.vars)
            should_run = evaluator.evaluate(stage_config.when)
            if not should_run:
                print(f"  SKIPPED (condition: {stage_config.when})")
                return StageResult(
                    status='skipped',
                    exit_code=0,
                    outputs={}
                )
        
        print(f"  Agent: {stage_config.agent.model}")
        print(f"  Permissions: {stage_config.agent.default_permissions}")
        
        # 1. 获取 input.template 路径
        template_file = stage_config.vars.get('input.template')
        if not template_file:
            error = f"input.template not defined for stage {stage_name}"
            print(f"  ERROR: {error}")
            return StageResult(
                status='failed',
                exit_code=1,
                outputs={},
                error_message=error
            )
        
        template_path = self.config_file.parent / template_file
        if not template_path.exists():
            error = f"Template file not found: {template_path}"
            print(f"  ERROR: {error}")
            return StageResult(
                status='failed',
                exit_code=1,
                outputs={},
                error_message=error
            )
        
        # 2. 读取并渲染模板
        with open(template_path, 'r') as f:
            template_content = f.read()
        
        rendered_content = self._replace_vars(template_content, stage_config.vars)
        
        # 3. 写入临时任务文件
        work_dir = Path(stage_config.agent.working_dir or '.')
        work_dir.mkdir(parents=True, exist_ok=True)
        
        task_file = work_dir / f".pipeline_{stage_name}_task.txt"
        with open(task_file, 'w') as f:
            f.write(rendered_content)
        
        print(f"  Task file: {task_file}")
        
        # 4. 执行 agent
        print(f"  Running agent...")
        try:
            self._execute_agent(stage_config.agent, str(task_file), stage_name)
            print(f"  Agent completed")
            
            # 5. 收集输出变量
            output_vars = {k: v for k, v in stage_config.vars.items() if k.startswith('output.')}
            outputs = {}
            for key, value in output_vars.items():
                resolved_value = self._replace_vars(value, stage_config.vars)
                outputs[key] = resolved_value
                print(f"  Output: {key} -> {resolved_value}")
            
            return StageResult(
                status='success',
                exit_code=0,
                outputs=outputs
            )
                
        except Exception as e:
            error_msg = str(e)
            print(f"  ERROR: {error_msg}")
            return StageResult(
                status='failed',
                exit_code=1,
                outputs={},
                error_message=error_msg
            )
    
    def _execute_agent(self, agent: AgentConfig, input_file: str, stage_name: str):
        """执行 agent
        
        这里使用 shell 调用 kimi CLI 作为示例
        """
        # 读取任务内容
        with open(input_file, 'r') as f:
            task_content = f.read()
        
        # 构建完整 prompt
        full_prompt = self._build_agent_prompt(agent, task_content)
        
        # 构建 kimi CLI 命令
        cmd_parts = ['kimi', '--yolo', '--print']
        
        # 添加 allowed_dirs 参数
        for d in agent.allowed_dirs:
            resolved_d = self._replace_vars(d, self._get_global_vars())
            cmd_parts.extend(['--allowed-dir', resolved_d])
        
        # 添加权限参数
        if agent.default_permissions == 'read-only':
            cmd_parts.append('--read-only')
        elif agent.default_permissions == 'write-only':
            cmd_parts.append('--write-only')
        
        # 添加 working_dir
        if agent.working_dir:
            resolved_wd = self._replace_vars(agent.working_dir, self._get_global_vars())
            cmd_parts.extend(['--working-dir', resolved_wd])
        
        # 添加 prompt
        cmd_parts.extend(['-p', full_prompt])
        
        cmd_str = ' '.join(f'"{p}"' if ' ' in p else p for p in cmd_parts)
        print(f"  CMD: {cmd_str[:200]}...")
        
        result = subprocess.run(cmd_str, shell=True, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise RuntimeError(f"Agent failed: {result.stderr}")
        
        return result.stdout
    
    def run(self):
        """运行完整 pipeline"""
        # 解析 pipeline 定义
        pipeline_def = self.config.get('pipeline', '')
        if not pipeline_def:
            print("ERROR: 'pipeline' field not defined in config")
            sys.exit(1)
        
        stage_names = [s.strip() for s in pipeline_def.split('-')]
        print(f"Pipeline: {' -> '.join(stage_names)}")
        
        # 获取全局 agent 配置
        global_agent_dict = self.config.get('agent', {})
        global_agent = self._parse_agent_config(global_agent_dict)
        
        # 获取全局变量
        global_vars = self._get_global_vars()
        
        # 依次执行每个 stage
        all_success = True
        for stage_name in stage_names:
            # 获取 stage 配置
            stage_dict = self.config.get(stage_name, {})
            
            # 合并 agent 配置
            stage_agent_dict = stage_dict.get('agent', {})
            stage_agent = self._parse_agent_config(stage_agent_dict)
            merged_agent = self._merge_agent_config(global_agent, stage_agent)
            
            # 合并变量（stage 覆盖全局）
            stage_vars = {**global_vars, **stage_dict.get('vars', {})}
            
            # 解析所有变量
            stage_vars = self._resolve_all_vars(stage_vars)
            
            # 获取执行条件
            when_condition = stage_dict.get('when')
            
            stage_config = StageConfig(
                name=stage_name,
                agent=merged_agent,
                vars=stage_vars,
                when=when_condition
            )
            
            result = self._run_stage(stage_name, stage_config)
            self.results[stage_name] = result
            
            if result.status == 'failed':
                all_success = False
                print(f"\n[FAILED] Stage '{stage_name}' failed, stopping pipeline")
                break
        
        # 输出汇总
        print(f"\n{'='*60}")
        print("Pipeline Summary:")
        for name, result in self.results.items():
            status_icon = "✓" if result.status == 'success' else "○" if result.status == 'skipped' else "✗"
            print(f"  {status_icon} {name}: {result.status}")
        
        if all_success:
            print(f"\n[COMPLETE] Pipeline '{pipeline_def}' finished successfully")
        else:
            print(f"\n[INCOMPLETE] Pipeline '{pipeline_def}' failed")
            sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Simplified Agent Pipeline")
    parser.add_argument("config", help="config.yaml path")
    args = parser.parse_args()
    
    runner = PipelineRunner(args.config)
    runner.run()


if __name__ == "__main__":
    main()
