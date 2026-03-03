#!/usr/bin/env python3
"""Simplified Agent Pipeline - 使用 code agent 作为 stage"""

import yaml
import subprocess
import sys
import argparse
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


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


class PipelineRunner:
    """简化版 Pipeline 运行器"""
    
    def __init__(self, config_file: str):
        self.config_file = Path(config_file)
        self.config = self._load_config()
        self.context: Dict[str, Dict[str, str]] = {}  # stage 输出上下文
        
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
        """解析变量值，支持 ${var} 和 ${stage.output} 引用"""
        if not isinstance(value, str):
            return str(value)
        
        # 处理 ${stage.output.xxx} 引用
        if value.startswith('${') and value.endswith('}'):
            expr = value[2:-1]  # 去掉 ${ 和 }
            
            # 检查是否是 stage 引用 (stageName.output.xxx)
            if '.output.' in expr:
                parts = expr.split('.')
                if len(parts) >= 3 and parts[1] == 'output':
                    stage_name = parts[0]
                    output_key = '.'.join(parts[2:])
                    if stage_name in self.context:
                        return self.context[stage_name].get(output_key, value)
            
            # 普通变量
            return vars_dict.get(expr, value)
        
        return value
    
    def _replace_vars(self, content: str, vars_dict: Dict[str, str]) -> str:
        """替换内容中的所有 ${var} 变量"""
        pattern = re.compile(r'\$\{([^}]+)\}')
        
        def replacer(match):
            var_name = match.group(1)
            
            # 检查是否是 stage 引用
            if '.output.' in var_name:
                parts = var_name.split('.')
                if len(parts) >= 3 and parts[1] == 'output':
                    stage_name = parts[0]
                    output_key = '.'.join(parts[2:])
                    if stage_name in self.context:
                        return self.context[stage_name].get(output_key, match.group(0))
            
            # 普通变量
            return vars_dict.get(var_name, match.group(0))
        
        return pattern.sub(replacer, content)
    
    def _resolve_all_vars(self, vars_dict: Dict[str, str]) -> Dict[str, str]:
        """递归解析所有变量（处理变量引用链）"""
        resolved = {}
        
        # 先复制所有变量
        for key, value in vars_dict.items():
            resolved[key] = value
        
        # 循环解析直到没有变化
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
    
    def _build_agent_command(self, agent: AgentConfig, 
                            input_file: str,
                            stage_name: str) -> List[str]:
        """构建 agent 启动命令
        
        使用 Task 工具调用 coder subagent
        """
        # 读取 input.txt 内容作为任务描述
        with open(input_file, 'r') as f:
            task_content = f.read()
        
        # 这里返回的是用于 Task 工具的参数，而不是 shell 命令
        # 实际执行时会调用 Task 工具
        return {
            'subagent_name': 'coder',
            'description': f'Pipeline stage: {stage_name}',
            'prompt': self._build_agent_prompt(agent, task_content)
        }
    
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
    
    def _run_stage(self, stage_name: str, stage_config: StageConfig):
        """执行单个 stage"""
        print(f"\n[STAGE] {stage_name}")
        print(f"  Agent: {stage_config.agent.model}")
        print(f"  Permissions: {stage_config.agent.default_permissions}")
        
        # 1. 获取 input.template 路径
        template_file = stage_config.vars.get('input.template')
        if not template_file:
            print(f"  ERROR: input.template not defined for stage {stage_name}")
            sys.exit(1)
        
        template_path = self.config_file.parent / template_file
        if not template_path.exists():
            print(f"  ERROR: Template file not found: {template_path}")
            sys.exit(1)
        
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
        
        # 4. 构建并执行 agent
        agent_cmd = self._build_agent_command(stage_config.agent, str(task_file), stage_name)
        
        # 5. 执行（实际调用 Task 工具）
        print(f"  Running agent...")
        try:
            result = self._execute_agent(agent_cmd, stage_config.agent)
            print(f"  Agent completed")
            
            # 6. 记录输出到上下文
            output_vars = {k: v for k, v in stage_config.vars.items() if k.startswith('output.')}
            self.context[stage_name] = output_vars
            
            for key, value in output_vars.items():
                print(f"  Output: {key} -> {value}")
                
        except Exception as e:
            print(f"  ERROR: Agent execution failed: {e}")
            sys.exit(1)
    
    def _execute_agent(self, agent_cmd: dict, agent_config: AgentConfig) -> str:
        """执行 agent 命令
        
        这里我们使用 shell 调用 kimi CLI 作为示例
        实际使用时可以通过 Task 工具调用 coder subagent
        """
        # 构建 kimi CLI 命令
        cmd_parts = ['kimi', '--yolo', '--print']
        
        # 添加 allowed_dirs 参数
        for d in agent_config.allowed_dirs:
            # 解析变量
            resolved_d = self._replace_vars(d, self._get_global_vars())
            cmd_parts.extend(['--allowed-dir', resolved_d])
        
        # 添加权限参数
        if agent_config.default_permissions == 'read-only':
            cmd_parts.append('--read-only')
        elif agent_config.default_permissions == 'write-only':
            cmd_parts.append('--write-only')
        
        # 添加 working_dir
        if agent_config.working_dir:
            resolved_wd = self._replace_vars(agent_config.workoking_dir, self._get_global_vars())
            cmd_parts.extend(['--working-dir', resolved_wd])
        
        # 添加 prompt
        prompt = agent_cmd['prompt']
        cmd_parts.extend(['-p', prompt])
        
        cmd_str = ' '.join(cmd_parts)
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
            
            stage_config = StageConfig(
                name=stage_name,
                agent=merged_agent,
                vars=stage_vars
            )
            
            self._run_stage(stage_name, stage_config)
        
        print(f"\n[COMPLETE] Pipeline '{pipeline_def}' finished successfully")


def main():
    parser = argparse.ArgumentParser(description="Simplified Agent Pipeline")
    parser.add_argument("config", help="config.yaml path")
    args = parser.parse_args()
    
    runner = PipelineRunner(args.config)
    runner.run()


if __name__ == "__main__":
    main()
