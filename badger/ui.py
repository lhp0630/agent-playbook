from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from .engine import StepResult

console = Console()


def print_step(step: StepResult) -> None:
    console.print(
        Panel(
            Markdown(step.content),
            title=f"[bold]{step.role}[/bold] — {step.stage}",
            border_style="blue",
        )
    )
    console.print()
