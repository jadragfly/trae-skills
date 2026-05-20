# -*- coding: utf-8 -*-
r"""
智能Python环境检测与修复工具
Smart Python Environment Detection and Fix Tool

功能：
1. 智能检测系统中所有Python环境
2. 自动检测常见问题（netrc编码、conda TOS等）
3. 提供绕过问题的解决方案
4. 创建虚拟环境并安装依赖

使用方法：
    python smart_run.py --diagnose                    # 诊断环境
    python smart_run.py --install numpy pandas         # 安装包
    python smart_run.py --create-venv myenv            # 创建虚拟环境
    python smart_run.py --use "C:\python.exe" script.py # 使用指定Python
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import argparse
import json

# ============================================================
# 全局配置
# ============================================================

# 全局调试开关（通过 /debug on 命令开启）
DEBUG = False

def debug_print(*args, **kwargs):
    """调试输出函数"""
    if DEBUG:
        print("[DEBUG]", *args, **kwargs)

# 常见Python安装路径
COMMON_PYTHON_PATHS = [
    "C:\\Python312",
    "C:\\Python311",
    "C:\\Python310",
    "C:\\Python39",
    "C:\\Program Files\\Python312",
    "C:\\Program Files\\Python311",
    "C:\\Program Files\\Python310",
    "C:\\Program Files (x86)\\Python312",
    "C:\\Program Files (x86)\\Python311",
]

# Conda常见路径
CONDA_PATHS = [
    "C:\\Users\\{username}\\miniconda3",
    "C:\\Users\\{username}\\anaconda3",
    "C:\\miniconda3",
    "C:\\anaconda3",
    "D:\\miniconda3",
    "D:\\anaconda3",
]

# ============================================================
# 环境检测模块
# ============================================================

class PythonEnvironment:
    """Python环境信息类"""
    def __init__(self, path: str, version: str = "", is_conda: bool = False, 
                 is_venv: bool = False, description: str = ""):
        self.path = Path(path)
        self.version = version
        self.is_conda = is_conda
        self.is_venv = is_venv
        self.description = description
        self.is_valid = False
        
    def verify(self) -> bool:
        """验证Python环境是否可用"""
        try:
            if not self.path.exists():
                return False
            
            # 确定python可执行文件路径
            if self.path.is_dir():
                if sys.platform == "win32":
                    python_exe = self.path / "python.exe"
                    if not python_exe.exists():
                        python_exe = self.path / "Scripts" / "python.exe"
                else:
                    python_exe = self.path / "bin" / "python"
            else:
                python_exe = self.path
                
            if not python_exe.exists():
                return False
                
            # 获取版本信息
            result = subprocess.run(
                [str(python_exe), "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                self.version = result.stdout.strip() or result.stderr.strip()
                self.is_valid = True
                return True
                
        except Exception as e:
            debug_print(f"验证环境 {self.path} 时出错: {e}")
            
        return False

class EnvironmentDetector:
    """环境检测器"""
    
    def __init__(self):
        self.environments: List[PythonEnvironment] = []
        self.problems: List[Dict[str, str]] = []
        self.username = os.path.expanduser("~").split("\\")[-1]
        
    def detect_all(self) -> List[PythonEnvironment]:
        """检测所有Python环境"""
        print("正在扫描系统中的Python环境...")
        
        # 1. 检查PATH中的Python
        self._check_path_python()
        
        # 2. 检查常见安装路径
        self._check_common_paths()
        
        # 3. 检查Conda环境
        self._check_conda_environments()
        
        # 4. 检查当前目录下的虚拟环境
        self._check_local_venvs()
        
        # 过滤有效的环境
        valid_envs = []
        for env in self.environments:
            if env.verify():
                valid_envs.append(env)
                debug_print(f"发现有效环境: {env.path} ({env.version})")
        
        self.environments = valid_envs
        return valid_envs
    
    def _check_path_python(self):
        """检查PATH中的Python"""
        python_path = shutil.which("python")
        if python_path:
            # 避免重复添加
            if not any(str(env.path) == python_path for env in self.environments):
                self.environments.append(
                    PythonEnvironment(python_path, description="PATH中的Python")
                )
    
    def _check_common_paths(self):
        """检查常见安装路径"""
        for path_str in COMMON_PYTHON_PATHS:
            path = Path(path_str)
            if path.exists():
                python_exe = path / "python.exe"
                if python_exe.exists():
                    if not any(str(env.path) == str(python_exe) for env in self.environments):
                        self.environments.append(
                            PythonEnvironment(python_exe, description="标准安装")
                        )
    
    def _check_conda_environments(self):
        """检查Conda环境"""
        for path_str in CONDA_PATHS:
            path_str = path_str.format(username=self.username)
            path = Path(path_str)
            if path.exists():
                # 主Conda Python
                python_exe = path / "python.exe"
                if python_exe.exists():
                    if not any(str(env.path) == str(python_exe) for env in self.environments):
                        self.environments.append(
                            PythonEnvironment(python_exe, is_conda=True, 
                                            description="Conda安装")
                        )
                
                # 检查Conda环境
                envs_dir = path / "envs"
                if envs_dir.exists():
                    for env_path in envs_dir.iterdir():
                        if env_path.is_dir():
                            if sys.platform == "win32":
                                python_exe = env_path / "python.exe"
                            else:
                                python_exe = env_path / "bin" / "python"
                            
                            if python_exe.exists():
                                if not any(str(env.path) == str(python_exe) for env in self.environments):
                                    self.environments.append(
                                        PythonEnvironment(python_exe, is_conda=True,
                                                        description=f"Conda环境: {env_path.name}")
                                    )
    
    def _check_local_venvs(self):
        """检查当前目录下的虚拟环境"""
        current_dir = Path.cwd()
        
        # 常见的虚拟环境目录名
        venv_names = [".venv", "venv", "env", ".env", "virtualenv"]
        
        for venv_name in venv_names:
            venv_path = current_dir / venv_name
            if venv_path.exists():
                if sys.platform == "win32":
                    python_exe = venv_path / "Scripts" / "python.exe"
                else:
                    python_exe = venv_path / "bin" / "python"
                
                if python_exe.exists():
                    if not any(str(env.path) == str(python_exe) for env in self.environments):
                        self.environments.append(
                            PythonEnvironment(python_exe, is_venv=True,
                                            description=f"本地虚拟环境: {venv_name}")
                        )

# ============================================================
# 问题检测模块
# ============================================================

class ProblemDetector:
    """问题检测器"""
    
    def __init__(self):
        self.problems: List[Dict[str, str]] = []
        
    def detect_all(self) -> List[Dict[str, str]]:
        """检测所有常见问题"""
        print("正在检测常见问题...")
        
        # 1. 检测netrc文件编码问题
        self._check_netrc_issue()
        
        # 2. 检测conda TOS问题
        self._check_conda_tos_issue()
        
        # 3. 检测PATH配置问题
        self._check_path_issue()
        
        # 4. 检测pip可用性
        self._check_pip_availability()
        
        return self.problems
    
    def _check_netrc_issue(self):
        """检测netrc文件编码问题"""
        netrc_path = Path.home() / "_netrc"
        
        if netrc_path.exists():
            try:
                # 尝试以UTF-8编码读取
                with open(netrc_path, 'r', encoding='utf-8') as f:
                    f.read()
            except UnicodeDecodeError as e:
                self.problems.append({
                    "type": "netrc_encoding",
                    "severity": "high",
                    "title": "netrc文件编码错误",
                    "description": f"文件 {netrc_path} 存在编码问题",
                    "error": str(e),
                    "solution": "$env:NETRC = \"\"",
                    "solution_description": "在安装命令前设置此环境变量"
                })
                debug_print(f"检测到netrc编码问题: {netrc_path}")
    
    def _check_conda_tos_issue(self):
        """检测conda TOS协议问题"""
        conda_exe = shutil.which("conda")
        
        if conda_exe:
            try:
                result = subprocess.run(
                    ["conda", "info"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode != 0 or "AnacondaTOS" in result.stderr:
                    self.problems.append({
                        "type": "conda_tos",
                        "severity": "medium",
                        "title": "Conda TOS协议问题",
                        "description": "Conda可能要求接受TOS协议",
                        "solution": "conda --no-plugins install <package>",
                        "solution_description": "使用 --no-plugins 参数禁用插件"
                    })
                    debug_print("检测到conda TOS问题")
                    
            except Exception as e:
                debug_print(f"检查conda时出错: {e}")
    
    def _check_path_issue(self):
        """检测PATH配置问题"""
        python_in_path = shutil.which("python")
        
        if not python_in_path:
            self.problems.append({
                "type": "path_missing",
                "severity": "medium",
                "title": "Python未在PATH中",
                "description": "系统中找不到python命令",
                "solution": "将Python安装目录添加到PATH环境变量",
                "solution_description": "右键'此电脑' -> 属性 -> 高级系统设置 -> 环境变量"
            })
            debug_print("检测到PATH配置问题")
    
    def _check_pip_availability(self):
        """检测pip可用性"""
        python_exe = shutil.which("python")
        
        if not python_exe:
            return
            
        try:
            result = subprocess.run(
                [python_exe, "-m", "pip", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
                env={**os.environ, "NETRC": ""}  # 临时禁用netrc
            )
            
            if result.returncode != 0:
                self.problems.append({
                    "type": "pip_unavailable",
                    "severity": "high",
                    "title": "pip不可用",
                    "description": "pip模块未安装或不可用",
                    "solution": "python -m ensurepip",
                    "solution_description": "使用此命令安装pip"
                })
                debug_print("检测到pip不可用")
                
        except Exception as e:
            debug_print(f"检查pip时出错: {e}")

# ============================================================
# 环境修复模块
# ============================================================

class EnvironmentFixer:
    """环境修复工具"""
    
    @staticmethod
    def get_fixed_env() -> Dict[str, str]:
        """获取修复后的环境变量"""
        env = os.environ.copy()
        
        # 禁用netrc文件
        env["NETRC"] = ""
        
        # 禁用conda插件
        env["CONDA_NO_PLUGINS"] = "true"
        
        return env
    
    @staticmethod
    def create_venv(venv_path: str, python_version: Optional[str] = None,
                   use_conda: bool = False) -> Tuple[bool, str]:
        """
        创建虚拟环境
        
        Args:
            venv_path: 虚拟环境路径
            python_version: Python版本（如"3.12"）
            use_conda: 是否使用conda
            
        Returns:
            (是否成功, 消息)
        """
        try:
            venv_path = Path(venv_path)
            
            if use_conda:
                # 使用conda创建环境
                cmd = ["conda", "create", "-y", "-p", str(venv_path)]
                if python_version:
                    cmd.extend([f"python={python_version}"])
                else:
                    cmd.append("python=3.12")
                    
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=600,
                    env={**os.environ, "CONDA_NO_PLUGINS": "true"}
                )
            else:
                # 使用venv创建环境
                cmd = [sys.executable, "-m", "venv", str(venv_path)]
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=300,
                    env=EnvironmentFixer.get_fixed_env()
                )
            
            if result.returncode == 0:
                return True, f"虚拟环境创建成功: {venv_path}"
            else:
                return False, f"创建失败: {result.stderr}"
                
        except Exception as e:
            return False, f"创建失败: {str(e)}"
    
    @staticmethod
    def install_packages(packages: List[str], 
                        python_path: Optional[str] = None,
                        use_conda: bool = False) -> Tuple[bool, str]:
        """
        安装Python包
        
        Args:
            packages: 包列表
            python_path: Python解释器路径（如果为None则使用当前Python）
            use_conda: 是否使用conda安装
            
        Returns:
            (是否成功, 消息)
        """
        try:
            if python_path:
                python_exe = Path(python_path)
                if not python_exe.exists():
                    python_exe = shutil.which(python_path)
            else:
                python_exe = sys.executable
                
            if use_conda:
                cmd = ["conda", "install", "-y"] + packages
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=600,
                    env={**os.environ, "CONDA_NO_PLUGINS": "true"}
                )
            else:
                cmd = [str(python_exe), "-m", "pip", "install"] + packages
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=600,
                    env=EnvironmentFixer.get_fixed_env()
                )
            
            if result.returncode == 0:
                return True, f"安装成功: {', '.join(packages)}"
            else:
                return False, f"安装失败: {result.stderr}"
                
        except Exception as e:
            return False, f"安装失败: {str(e)}"
    
    @staticmethod
    def run_with_python(python_path: str, script_path: str,
                       fix_netrc: bool = True) -> Tuple[bool, str]:
        """
        使用指定Python运行脚本
        
        Args:
            python_path: Python解释器路径
            script_path: 脚本路径
            fix_netrc: 是否修复netrc问题
            
        Returns:
            (是否成功, 消息)
        """
        try:
            python_exe = Path(python_path)
            if not python_exe.exists():
                python_exe = shutil.which(python_path)
                
            if not python_exe or not python_exe.exists():
                return False, f"Python不存在: {python_path}"
            
            cmd = [str(python_exe), str(script_path)]
            
            env = os.environ.copy()
            if fix_netrc:
                env["NETRC"] = ""
            
            result = subprocess.run(
                cmd,
                capture_output=False,
                cwd=os.getcwd(),
                env=env
            )
            
            return result.returncode == 0, f"脚本执行{'成功' if result.returncode == 0 else '失败'}"
            
        except Exception as e:
            return False, f"执行失败: {str(e)}"

# ============================================================
# 输出格式化模块
# ============================================================

class OutputFormatter:
    """输出格式化工具"""
    
    @staticmethod
    def print_diagnosis(environs: List[PythonEnvironment], 
                       problems: List[Dict[str, str]]):
        """打印诊断结果"""
        print("=" * 60)
        print("Windows Python 环境诊断")
        print("=" * 60)
        print()
        
        # 打印检测到的环境
        if environs:
            print(f"[✓] 检测到的Python环境 ({len(environs)}个):")
            for i, env in enumerate(environs, 1):
                env_type = []
                if env.is_conda:
                    env_type.append("Conda")
                if env.is_venv:
                    env_type.append("虚拟环境")
                if not env_type:
                    env_type.append("标准")
                
                type_str = " + ".join(env_type)
                print(f"  {i}. {env.path}")
                print(f"     版本: {env.version} | 类型: {type_str}")
                if env.description:
                    print(f"     说明: {env.description}")
                print()
        else:
            print("[✗] 未检测到任何Python环境")
            print()
        
        # 打印检测到的问题
        if problems:
            print(f"[✗] 检测到 {len(problems)} 个问题:")
            print()
            for problem in problems:
                severity_emoji = {
                    "high": "🔴",
                    "medium": "🟡",
                    "low": "🟢"
                }.get(problem.get("severity", "low"), "⚪")
                
                print(f"{severity_emoji} {problem['title']}")
                print(f"   问题: {problem['description']}")
                print(f"   修复: {problem['solution']}")
                print(f"   说明: {problem.get('solution_description', '')}")
                print()
        else:
            print("[✓] 未检测到常见问题")
            print()
        
        # 打印修复建议
        if problems:
            print("[💡] 快速修复建议:")
            for problem in problems:
                print(f"  • {problem['solution']}")
            print()
    
    @staticmethod
    def print_success(message: str):
        """打印成功消息"""
        print(f"[✓] {message}")
    
    @staticmethod
    def print_error(message: str):
        """打印错误消息"""
        print(f"[✗] {message}")
    
    @staticmethod
    def print_info(message: str):
        """打印信息消息"""
        print(f"[ℹ] {message}")

# ============================================================
# 主程序
# ============================================================

def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="智能Python环境检测与修复工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=r"""
示例:
  python smart_run.py --diagnose
  python smart_run.py --install numpy pandas
  python smart_run.py --create-venv myenv
  python smart_run.py --use "C:\Python312\python.exe" script.py
        """
    )
    
    # 诊断参数
    parser.add_argument("--diagnose", "-d", action="store_true",
                       help="诊断当前Python环境")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="显示详细信息（调试模式）")
    
    # 安装参数
    parser.add_argument("--install", "-i", nargs="+",
                       help="安装Python包")
    parser.add_argument("--use-conda", action="store_true",
                       help="使用conda安装")
    
    # 虚拟环境参数
    parser.add_argument("--create-venv", "-c", metavar="NAME",
                       help="创建虚拟环境")
    parser.add_argument("--python", metavar="VERSION",
                       help="指定Python版本（如3.12）")
    
    # 使用指定Python
    parser.add_argument("--use", "-u", metavar="PYTHON_PATH",
                       help="使用指定的Python运行脚本")
    parser.add_argument("--fix-netrc", action="store_true", default=True,
                       help="修复netrc问题（默认启用）")
    
    args = parser.parse_args()
    
    # 设置调试模式
    global DEBUG
    DEBUG = args.verbose
    
    # 如果没有参数，显示帮助
    if len(sys.argv) == 1:
        parser.print_help()
        return
    
    # 执行诊断
    if args.diagnose:
        print()
        
        # 检测环境
        detector = EnvironmentDetector()
        environs = detector.detect_all()
        
        # 检测问题
        problem_detector = ProblemDetector()
        problems = problem_detector.detect_all()
        
        # 打印结果
        OutputFormatter.print_diagnosis(environs, problems)
        return
    
    # 安装包
    if args.install:
        print()
        OutputFormatter.print_info("正在安装包...")
        
        # 优先使用指定的Python环境
        python_path = None
        if args.use:
            python_path = args.use
        
        success, message = EnvironmentFixer.install_packages(
            args.install,
            python_path=python_path,
            use_conda=args.use_conda
        )
        
        if success:
            OutputFormatter.print_success(message)
        else:
            OutputFormatter.print_error(message)
        return
    
    # 创建虚拟环境
    if args.create_venv:
        print()
        OutputFormatter.print_info(f"正在创建虚拟环境: {args.create_venv}")
        
        # 确定路径
        venv_path = Path(args.create_venv)
        if not venv_path.is_absolute():
            venv_path = Path.cwd() / venv_path
        
        success, message = EnvironmentFixer.create_venv(
            str(venv_path),
            python_version=args.python,
            use_conda=args.use_conda
        )
        
        if success:
            OutputFormatter.print_success(message)
            print()
            print(f"激活虚拟环境:")
            if sys.platform == "win32":
                print(f"  {venv_path}\\Scripts\\activate")
            else:
                print(f"  source {venv_path}/bin/activate")
        else:
            OutputFormatter.print_error(message)
        return
    
    # 使用指定Python运行脚本
    if args.use:
        if len(sys.argv) < 3:
            OutputFormatter.print_error("请指定要运行的脚本")
            parser.print_help()
            return
        
        # 获取脚本路径（应该是--use之后的下一个参数）
        script_path = None
        for i, arg in enumerate(sys.argv):
            if arg == "--use" or arg == "-u":
                if i + 2 < len(sys.argv) and not sys.argv[i + 2].startswith("-"):
                    script_path = sys.argv[i + 2]
                    break
        
        if not script_path:
            OutputFormatter.print_error("请指定要运行的脚本")
            return
        
        print()
        OutputFormatter.print_info(f"使用 {args.use} 运行 {script_path}")
        
        success, message = EnvironmentFixer.run_with_python(
            args.use,
            script_path,
            fix_netrc=args.fix_netrc
        )
        
        if success:
            OutputFormatter.print_success(message)
        else:
            OutputFormatter.print_error(message)
        return

if __name__ == "__main__":
    main()
