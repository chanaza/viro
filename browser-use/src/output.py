import os
import re
from urllib.parse import unquote

from src.config import CSV_HEADERS
from src.models import BranchList


def save_outputs(result, branch_list: BranchList | None, subject: str, output_dir: str) -> None:
    _print_log(branch_list)
    _save_branches_csv(branch_list, subject, output_dir)
    _save_log_csv(branch_list, subject, output_dir)
    _save_history(result, subject, output_dir)


# ─── חילוץ BranchList מתוצאת הריצה ──────────────────────────────────────────

def extract_branch_list(result) -> BranchList | None:
    from src.models import BranchList

    # נסיון 1: structured output ישיר
    try:
        return result.get_structured_output(BranchList)
    except Exception:
        pass

    # נסיון 2: parse מהטקסט הסופי
    final_text = result.final_result() or ""
    match = re.search(r'\{[\s\S]*"items"[\s\S]*\}', final_text)
    if match:
        try:
            return BranchList.model_validate_json(match.group())
        except Exception:
            pass

    return None


# ─── לוג מקורות (הדפסה) ──────────────────────────────────────────────────────

def _print_log(branch_list: BranchList | None) -> None:
    if not branch_list or not branch_list.log:
        return
    print("\n📋 לוג מקורות:")
    for entry in branch_list.log:
        if not entry.visited:
            icon, status = "⬛", "לא הגיע"
        elif entry.found:
            icon, status = "✅", f"נמצאו {entry.count} פריטים"
        else:
            icon, status = "❌", "לא נמצאו תוצאות"
        notes = f" — {entry.notes}" if entry.notes else ""
        print(f"  {icon} {entry.source:<35} {status}{notes}")


# ─── שמירת סניפים ─────────────────────────────────────────────────────────────

def _save_branches_csv(branch_list: BranchList | None, subject: str, output_dir: str) -> None:
    if not branch_list or not branch_list.items:
        print("\n⚠️  לא הצלחנו לחלץ נתונים מובנים")
        return

    csv_path = os.path.join(output_dir, f"{subject}.csv")
    with open(csv_path, "w", encoding="utf-8-sig") as f:
        f.write(CSV_HEADERS + "\n")
        for item in branch_list.items:
            name    = item.name.replace('"', '""')
            address = item.address.replace('"', '""')
            city    = item.city.replace('"', '""')
            source  = item.source.replace('"', '""')
            f.write(f'"{name}","{address}","{city}","{source}"\n')
    print(f"\n✅ נשמר: {csv_path} ({len(branch_list.items)} פריטים)")


# ─── שמירת לוג (LLM) ─────────────────────────────────────────────────────────

def _save_log_csv(branch_list: BranchList | None, subject: str, output_dir: str) -> None:
    if not branch_list or not branch_list.log:
        return

    log_path = os.path.join(output_dir, f"{subject}_log.csv")
    with open(log_path, "w", encoding="utf-8-sig") as f:
        f.write("source,visited,found,count,notes\n")
        for entry in branch_list.log:
            source = entry.source.replace('"', '""')
            notes  = entry.notes.replace('"', '""')
            f.write(f'"{source}",{entry.visited},{entry.found},{entry.count},"{notes}"\n')
    print(f"✅ לוג נשמר: {log_path}")


# ─── שמירת היסטוריה אמיתית (מחוץ ל-LLM) ─────────────────────────────────────

def _save_history(result, subject: str, output_dir: str) -> None:
    try:
        history_path = os.path.join(output_dir, f"{subject}_history.csv")
        with open(history_path, "w", encoding="utf-8-sig") as f:
            f.write("step,action,details,error,extracted\n")
            for step_i, step in enumerate(result.history, start=1):
                actions = step.model_output.action if step.model_output else []
                results = step.result or []
                for act_i, (action, res) in enumerate(zip(actions, results)):
                    action_dict = action.model_dump(exclude_none=True)
                    action_name = next(iter(action_dict), "unknown")
                    details     = str(list(action_dict.values())[0]) if action_dict else ""
                    error       = (res.error or "").replace('"', '""')[:200]
                    extracted   = (res.extracted_content or "").replace('"', '""')[:300]
                    details_esc = details.replace('"', '""')[:200]
                    f.write(f'{step_i}.{act_i+1},"{action_name}","{details_esc}","{error}","{extracted}"\n')

        # URLs ייחודיים שנוסו
        all_urls = [u for u in (result.urls() or []) if u]
        seen, unique_urls = set(), []
        for u in all_urls:
            if u not in seen:
                seen.add(u)
                unique_urls.append(u)

        urls_path = os.path.join(output_dir, f"{subject}_urls.txt")
        with open(urls_path, "w", encoding="utf-8-sig") as f:
            f.write("\n".join(unquote(u) for u in unique_urls))

        print(f"✅ היסטוריה נשמרה: {history_path} ({len(result.history)} שלבים, {len(unique_urls)} URLs ייחודיים)")
    except Exception as e:
        print(f"⚠️  שגיאה בשמירת היסטוריה: {e}")
