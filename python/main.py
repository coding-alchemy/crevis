import argparse
import sys
from pathlib import Path
from typing import Optional

from config_manager import ConfigManager
from input_manager import InputManager
from output_manager import OutputManager
from storage import Storage
from task_submitter import TaskSubmitter
from task_listener import TaskListener
from models import SUCCEEDED, FAILED, COMPLETED, PENDING, RUNNING


def load_config() -> ConfigManager:
    """加载配置"""
    try:
        return ConfigManager()
    except FileNotFoundError as e:
        print(f"错误: {e}")
        sys.exit(1)


def init_managers(config: ConfigManager):
    """初始化所有管理器"""
    input_mgr = InputManager()
    output_mgr = OutputManager(config.local_output_path)
    storage = Storage(config.local_output_path)
    return input_mgr, output_mgr, storage


def cmd_submit(args):
    """提交任务命令"""
    config = load_config()
    
    # 验证配置
    errors = config.validate()
    if errors:
        print("配置验证失败:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)
    
    # 初始化管理器
    input_mgr, output_mgr, storage = init_managers(config)
    
    # 构建生成参数
    generation_params = {
        "generate_audio": args.generate_audio,
        "ratio": args.ratio,
        "watermark": args.watermark,
    }
    
    # 收集输入文件
    input_files = []
    if args.files:
        for file_path in args.files:
            path = Path(file_path)
            if not path.exists() and not str(path).startswith(("http://", "https://")):
                print(f"警告: 文件不存在: {path}")
                continue
            input_files.append(path)
    
    if not input_files:
        print("错误: 未提供有效输入文件")
        sys.exit(1)
    
    # 提交任务
    submitter = TaskSubmitter(config, input_mgr, output_mgr, storage)
    
    try:
        task = submitter.submit(
            prompt=args.prompt,
            input_files=input_files,
            generation_params=generation_params,
        )
        print(f"\n任务提交成功!")
        print(f"  任务 ID: {task.task_id}")
        print(f"  版本号: {task.version}")
        print(f"  模型: {task.model_id}")
        print(f"  提示词: {args.prompt}")
        print(f"  输入文件: {len(input_files)} 个")
        print(f"  输出目录: {task.output_path}")
        
        # 启动监听
        listener = TaskListener(config, output_mgr, storage)
        listener.start_listening(task)
        print(f"\n已启动任务监听，每 {TaskListener.POLL_INTERVAL} 秒轮询一次")
        print("按 Ctrl+C 退出（任务将在后台继续运行）")
        
        # 保持主线程运行
        import time
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n用户退出")
            
    except Exception as e:
        print(f"提交失败: {e}")
        sys.exit(1)


def cmd_list(args):
    """列出任务命令"""
    config = load_config()
    _, output_mgr, storage = init_managers(config)
    
    tasks = storage.list_tasks(status=args.status)
    
    if not tasks:
        print("暂无任务")
        return
    
    print(f"\n{'任务 ID':<20} {'版本':<18} {'状态':<12} {'创建时间'}")
    print("-" * 70)
    for task in tasks:
        print(f"{task.task_id:<20} {task.version:<18} {task.status:<12} {task.created_at}")
    
    print(f"\n共 {len(tasks)} 个任务")


def cmd_status(args):
    """查询任务状态命令"""
    config = load_config()
    _, output_mgr, storage = init_managers(config)
    
    task = storage.get_task(args.task_id)
    if not task:
        print(f"未找到任务: {args.task_id}")
        sys.exit(1)
    
    print(f"\n任务信息:")
    print(f"  任务 ID: {task.task_id}")
    print(f"  版本号: {task.version}")
    print(f"  模型: {task.model_id}")
    print(f"  状态: {task.status}")
    print(f"  提示词: {task.request_params.get('content', [{}])[0].get('text', 'N/A')}")
    print(f"  输出路径: {task.output_path}")
    print(f"  创建时间: {task.created_at}")
    
    if task.completed_at:
        print(f"  完成时间: {task.completed_at}")
    
    if task.error_message:
        print(f"  错误信息: {task.error_message}")
    
    print(f"  输入文件:")
    for item in task.input_list:
        print(f"    - {item.type}: {item.remote_url or item.local_path}")


def main():
    """主入口"""
    parser = argparse.ArgumentParser(
        description="Crevis 视频生成工作流",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s submit --prompt "生成一个5秒的猫视频" --files cat.jpg
  %(prog)s list
  %(prog)s status task_abc123
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # submit 命令
    submit_parser = subparsers.add_parser("submit", help="提交视频生成任务")
    submit_parser.add_argument("--prompt", "-p", required=True, help="提示词（可包含 duration 信息）")
    submit_parser.add_argument("--files", "-f", nargs="+", required=True, help="输入文件路径列表")
    submit_parser.add_argument("--generate-audio", action="store_true", default=True, help="生成音频（默认开启）")
    submit_parser.add_argument("--no-generate-audio", action="store_false", dest="generate_audio", help="不生成音频")
    submit_parser.add_argument("--ratio", default="16:9", choices=["16:9", "9:16", "1:1", "4:3", "3:4"], help="视频比例（默认 16:9）")
    submit_parser.add_argument("--watermark", action="store_true", default=False, help="添加水印（默认不开启）")
    submit_parser.set_defaults(func=cmd_submit)
    
    # list 命令
    list_parser = subparsers.add_parser("list", help="列出所有任务")
    list_parser.add_argument("--status", choices=[PENDING, RUNNING, SUCCEEDED, FAILED, COMPLETED], help="按状态过滤")
    list_parser.set_defaults(func=cmd_list)
    
    # status 命令
    status_parser = subparsers.add_parser("status", help="查询任务状态")
    status_parser.add_argument("task_id", help="任务 ID")
    status_parser.set_defaults(func=cmd_status)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    args.func(args)


if __name__ == "__main__":
    main()
