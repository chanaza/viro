"""ArtifactsSaver — persists structured run artifacts to disk (CSV, history, URLs)."""

import re
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote

CSV_ENCODING = "utf-8-sig"
TIMESTAMP_FORMAT = "%Y-%m-%d_%H-%M-%S"
HISTORY_HEADERS = ["step", "action", "details", "error", "extracted"]
SOURCE_LOG_HEADERS = ["source", "visited", "found", "count", "notes"]


class ArtifactsSaver:
    @staticmethod
    def _ensure_dir(output_dir: Path) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _get_prefix() -> str:
        return datetime.now().strftime(TIMESTAMP_FORMAT)

    @staticmethod
    def _escape_csv(value: str) -> str:
        return value.replace('"', '""')

    @staticmethod
    def _write_csv(path: Path, headers: list[str], rows: list[list[str]]) -> bool:
        try:
            with open(path, "w", encoding=CSV_ENCODING) as f:
                f.write(",".join(headers) + "\n")
                for row in rows:
                    f.write(",".join(f'"{ArtifactsSaver._escape_csv(cell)}"' for cell in row) + "\n")
            return True
        except Exception:
            return False

    @staticmethod
    def save(history, output_dir: Path, result: str, schema_class=None) -> dict[str, Any]:
        ArtifactsSaver._ensure_dir(output_dir)
        prefix = ArtifactsSaver._get_prefix()
        saved: dict[str, Any] = {}

        saved.update(ArtifactsSaver._save_history(history, output_dir, prefix))
        saved.update(ArtifactsSaver._save_urls(history, output_dir, prefix))

        if schema_class:
            structured = ArtifactsSaver._extract_structured(history, schema_class)
            saved.update(ArtifactsSaver._save_items(structured, output_dir, prefix))
            saved.update(ArtifactsSaver._save_source_log(structured, output_dir, prefix))
        else:
            saved.update(ArtifactsSaver._save_text_result(result, output_dir, prefix))

        return saved

    @staticmethod
    def _save_history(history, output_dir: Path, prefix: str) -> dict[str, str]:
        path = output_dir / f"{prefix}_history.csv"
        rows = []
        for step_i, step in enumerate(history.history, start=1):
            actions = step.model_output.action if step.model_output else []
            results = step.result or []
            for act_i, (action, res) in enumerate(zip(actions, results)):
                action_dict = action.model_dump(exclude_none=True)
                action_name = next(iter(action_dict), "unknown")
                details = str(list(action_dict.values())[0]) if action_dict else ""
                error = (res.error or "")[:200]
                extracted = (res.extracted_content or "")[:300]
                rows.append([f"{step_i}.{act_i + 1}", action_name, details[:200], error, extracted])

        if ArtifactsSaver._write_csv(path, HISTORY_HEADERS, rows):
            return {"history_path": str(path)}
        return {}

    @staticmethod
    def _save_urls(history, output_dir: Path, prefix: str) -> dict[str, str]:
        path = output_dir / f"{prefix}_urls.txt"
        try:
            all_urls = [u for u in (history.urls() or []) if u]
            unique = list(dict.fromkeys(all_urls))
            path.write_text("\n".join(unquote(u) for u in unique), encoding=CSV_ENCODING)
            return {"urls_path": str(path)}
        except Exception:
            return {}

    @staticmethod
    def _save_items(structured, output_dir: Path, prefix: str) -> dict[str, Any]:
        if not structured or not hasattr(structured, "items") or not structured.items:
            return {}
        path = output_dir / f"{prefix}_result.csv"
        try:
            headers = list(structured.items[0].model_fields.keys())
            rows = [
                [str(getattr(item, header, "")) for header in headers]
                for item in structured.items
            ]
            if ArtifactsSaver._write_csv(path, headers, rows):
                return {"csv_path": str(path), "count": len(structured.items)}
        except Exception:
            pass
        return {}

    @staticmethod
    def _save_source_log(structured, output_dir: Path, prefix: str) -> dict[str, str]:
        if not structured or not hasattr(structured, "log") or not structured.log:
            return {}
        path = output_dir / f"{prefix}_sources.csv"
        rows = [
            [entry.source, str(entry.visited), str(entry.found), str(entry.count), entry.notes]
            for entry in structured.log
        ]
        if ArtifactsSaver._write_csv(path, SOURCE_LOG_HEADERS, rows):
            return {"log_csv_path": str(path)}
        return {}

    @staticmethod
    def _save_text_result(result: str, output_dir: Path, prefix: str) -> dict[str, str]:
        if not result:
            return {}
        path = output_dir / f"{prefix}_result.txt"
        try:
            path.write_text(result, encoding=CSV_ENCODING)
            return {"result_path": str(path)}
        except Exception:
            return {}

    @staticmethod
    def _extract_structured(history, schema_class):
        try:
            output = history.get_structured_output(schema_class)
            if output:
                return output
        except Exception:
            pass
        final_text = history.final_result() or ""
        match = re.search(r"\{[\s\S]*\}", final_text)
        if match:
            try:
                return schema_class.model_validate_json(match.group())
            except Exception:
                pass
        return None
