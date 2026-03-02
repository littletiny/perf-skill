#!/usr/bin/env python3
"""Simple Agent Pipeline"""

import yaml
import re
import subprocess
import sys
import argparse
from pathlib import Path


class PipelineRunner:
    def __init__(self, pipeline_file: str, agents_file: str = "agents.yaml"):
        self.pipeline = yaml.safe_load(open(pipeline_file))
        self.agents = yaml.safe_load(open(agents_file)) if Path(agents_file).exists() else {}
        self.context = {}
        
    def run(self):
        default_agent = self.pipeline.get("agent_default", "kimi")
        
        for stage in self.pipeline.get("stages", []):
            print(f"\n[STAGE] {stage['name']}")
            self._run_stage(stage, default_agent)
        
        print(f"\n[COMPLETE] Pipeline '{self.pipeline['name']}' finished")
    
    def _run_stage(self, stage: dict, default_agent: str):
        name = stage["name"]
        agent_name = stage.get("agent", default_agent)
        prompt_template = stage["prompt"]
        vars_dict = stage.get("vars", {})
        
        # 解析变量（包括 ${stage.output} 引用）
        vars_dict = {k: self._resolve_vars(v, vars_dict) for k, v in vars_dict.items()}
        output = vars_dict["output"]
        
        # 1. 读取并渲染prompt模板
        with open(prompt_template, "r") as f:
            prompt_content = f.read()
        prompt_content = self._replace_vars(prompt_content, vars_dict)
        
        # 2. 写入临时prompt文件
        prompt_file = f".pipeline_tmp/{name}_prompt.txt"
        Path(prompt_file).parent.mkdir(exist_ok=True)
        with open(prompt_file, "w") as f:
            f.write(prompt_content)
        
        # 3. 创建输出目录
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        
        # 4. 构建并执行命令
        agent = self.agents.get("agents", {}).get(agent_name, {})
        cmd = f"{agent.get('cmd', agent_name)} {agent.get('args', '')}"
        cmd = cmd.replace("${prompt}", prompt_file)
        
        print(f"  CMD: {cmd}")
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"  ERROR: {result.stderr}")
            sys.exit(1)
        
        # 5. 写入输出文件
        with open(output, "w") as f:
            f.write(result.stdout)
        
        # 6. 记录结果
        self.context[name] = {"output": str(Path(output).absolute())}
        print(f"  -> {output}")
    
    def _resolve_vars(self, value: str, vars_dict: dict) -> str:
        """解析变量值（包括 ${stage.output} 引用）"""
        if not isinstance(value, str):
            return value
        if value.startswith("${") and value.endswith("}"):
            expr = value[2:-1]  # stage.output
            parts = expr.split(".")
            ctx = self.context
            for p in parts:
                ctx = ctx[p]
            return ctx
        return value
    
    def _replace_vars(self, content: str, vars_dict: dict) -> str:
        """替换 ${var} 变量"""
        def replacer(match):
            key = match.group(1)
            return vars_dict.get(key, match.group(0))
        return re.sub(r"\$\{([^}]+)\}", replacer, content)


def main():
    parser = argparse.ArgumentParser(description="Simple Agent Pipeline")
    parser.add_argument("pipeline", help="pipeline.yaml path")
    parser.add_argument("--agents", default="agents.yaml", help="agents config file")
    args = parser.parse_args()
    
    PipelineRunner(args.pipeline, args.agents).run()


if __name__ == "__main__":
    main()
