"""FinalResponseSaver — persists the human-readable session summary to disk."""

from datetime import datetime
from pathlib import Path


class FinalResponseSaver:
    @staticmethod
    def save(
        task: str,
        result: str,
        steps_log: list[dict],
        output_dir: Path,
        prefix: str,
    ) -> dict[str, str]:
        output_dir.mkdir(parents=True, exist_ok=True)
        saved: dict[str, str] = {}
        saved.update(FinalResponseSaver._save_answer(result, output_dir, prefix))
        saved.update(FinalResponseSaver._save_log(task, steps_log, output_dir, prefix))
        return saved

    @staticmethod
    def _save_answer(result: str, output_dir: Path, prefix: str) -> dict[str, str]:
        path = output_dir / f"{prefix}_answer.md"
        try:
            path.write_text(result or "(no result)", encoding="utf-8-sig")
            return {"answer_path": str(path)}
        except Exception:
            return {}

    @staticmethod
    def _save_log(
        task: str,
        steps_log: list[dict],
        output_dir: Path,
        prefix: str,
    ) -> dict[str, str]:
        path = output_dir / f"{prefix}_log.md"
        try:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            lines = [f"# Log - {ts}", "", "## Task", task, ""]
            if steps_log:
                lines += ["## Steps", ""]
                for event in steps_log:
                    formatted = FinalResponseSaver._format_event(event)
                    if formatted:
                        lines.append(formatted)
                lines.append("")
            path.write_text("\n".join(lines), encoding="utf-8-sig")
            return {"log_path": str(path)}
        except Exception:
            return {}

    @staticmethod
    def _format_event(event: dict) -> str:
        t = event.get("type", "")
        if t == "step":
            action = f" -> `{event['action']}`" if event.get("action") else ""
            return f"{event['step']}. {event['goal']}{action}"
        if t == "security_warning":
            return f"  SECURITY WARNING: {event['reason']} - goal: {event['goal']}, action: {event['action']}"
        if t == "security_approved":
            return f"  Security warning APPROVED - goal: {event['goal']}, action: {event['action']}"
        if t == "security_rejected":
            return f"  Security warning REJECTED - goal: {event['goal']}, action: {event['action']}"
        if t == "security_stop":
            return f"  SECURITY STOP: {event['reason']} - goal: {event['goal']}, action: {event['action']}"
        if t == "done":
            return "  Completed."
        if t == "stopped":
            return "  Agent stopped by user."
        if t == "error":
            return f"  Error: {event.get('message', 'unknown error')}"
        return ""
