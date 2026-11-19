"""Print the maintained backlog summary tables without making an AI request."""

from pathlib import Path
import shutil
import sys
import textwrap


def summary(markdown: str, section: str) -> str:
    lines = markdown.splitlines()
    heading = f"## {section}"
    start = lines.index(heading) + 1
    table = []
    for line in lines[start:]:
        if line.startswith("|"):
            table.append(line)
        elif table or line.startswith("#"):
            break
    if len(table) < 3 or table[0] != "| ID | Short summary |":
        raise ValueError(f"Missing {section} summary table")
    return "\n".join(table)


def pretty_table(markdown: str, width: int) -> str:
    rows = [tuple(cell.strip() for cell in line.strip("|").split("|", 1))
            for line in markdown.splitlines()]
    rows = [rows[0], *rows[2:]]  # Omit the Markdown separator row.
    id_width = max(len(row[0]) for row in rows)
    summary_width = max(1, min(
        max(len(row[1]) for row in rows), width - id_width - 7,
    ))

    def border(left: str, middle: str, right: str) -> str:
        return left + "─" * (id_width + 2) + middle + "─" * (summary_width + 2) + right

    output = [border("┌", "┬", "┐")]
    for index, (identifier, description) in enumerate(rows):
        wrapped = textwrap.wrap(description, width=summary_width) or [""]
        for line_index, line in enumerate(wrapped):
            label = identifier if line_index == 0 else ""
            output.append(f"│ {label:<{id_width}} │ {line:<{summary_width}} │")
        if index == 0:
            output.append(border("├", "┼", "┤"))
    output.append(border("└", "┴", "┘"))
    return "\n".join(output)


def main() -> None:
    backlog = Path(__file__).resolve().parents[1] / "BACKLOG.md"
    try:
        markdown = backlog.read_text(encoding="utf-8")
        width = shutil.get_terminal_size(fallback=(100, 24)).columns
        message = (
            "Features to do\n\n" + pretty_table(summary(markdown, "Features"), width)
            + "\n\nBugs to fix\n\n" + pretty_table(summary(markdown, "Bugs"), width)
        )
    except (OSError, ValueError):
        print("Cannot read BACKLOG.md summary tables; check the repository backlog.", file=sys.stderr)
        raise SystemExit(1)
    print(message + "\n", flush=True)


if __name__ == "__main__":
    main()
