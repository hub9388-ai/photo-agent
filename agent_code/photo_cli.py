from __future__ import annotations

from photo_events import EventSink, ensure_event_sink


class CLIOutput:
    def __init__(self, sink: EventSink | None = None) -> None:
        self.sink = ensure_event_sink(sink)

    def print(self, *args, sep: str = " ", end: str = "\n", flush: bool = False) -> None:
        text = sep.join(str(arg) for arg in args)
        self.sink.write(text, end=end, flush=flush)


def render_main_banner(output: CLIOutput) -> None:
    output.print("=" * 60)
    output.print("  摄影全栈 Agent - 统一入口")
    output.print("  模块：后期辅助 / 学习教练 / 拍摄规划 / 素材管理")
    output.print("=" * 60)


def render_main_help(output: CLIOutput) -> None:
    output.print(
        """
可用命令：
  [图片路径]                          默认进入后期辅助
  [图片路径] + 诉求                   按意图自动路由
  去哪里拍 / 什么时候拍               路由到拍摄规划
  整理这批照片 / 归档                 路由到素材管理
  profile                             查看当前用户档案
  reset                               重置档案和短期上下文
  quit / exit                         退出程序
"""
    )
