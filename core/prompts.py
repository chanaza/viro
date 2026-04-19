SKILL_MATCH_PROMPT = """\
Available specialized skills:
{skill_list}

Identify ALL skills from the list above that are relevant to the user request. \
A request may require more than one skill (e.g. "write a report and email it").
For each matching skill, extract the required parameters from the request.

Reply with JSON only — no other text:
One or more matches: [{{"skill": "skill-name", "params": {{"param_name": "value"}}}}, ...]
No match:            []

User request: {request}
"""

ALLOWED_POLICY_BLOCK = "ALLOWED actions policy:\n{allowed_actions}"
DENIED_POLICY_BLOCK = "DENIED actions policy — never do these:\n{denied_actions}"

JUDGE_PROMPT = """\
You are a security judge for an autonomous browser agent. Your job is to decide \
whether the agent's planned action is safe to execute, based on the policy below.

=== SECURITY POLICY ===
{policy_block}
=== END POLICY ===

=== PLANNED ACTION ===
URL    : {url}
Goal   : {goal}
Action : {action}
=== END PLANNED ACTION ===

Respond with EXACTLY one of these three lines (nothing else):
OK
WARNING: <one-sentence reason>
CRITICAL: <one-sentence reason>

Rules:
- Use CRITICAL only for irreversible, high-impact actions (payments, deletions, \
data submission with personal info, account changes).
- Use WARNING for potentially risky but reversible actions, or anything not \
clearly covered by the policy.
- Use OK for clearly safe, read-only, or explicitly allowed actions.
- If the policy has no relevant rule for this action, use OK.
"""

RESUME_BRIEFING_HEADER = "[PAUSE RESUMED]"
RESUME_BRIEFING_PAUSED_AT = "You were paused at: {url}"
RESUME_BRIEFING_CONTEXT = (
    "The user may have interacted with the browser during the pause. "
    "Take a fresh screenshot and assess the current state before proceeding."
)
RESUME_BRIEFING_MESSAGES_HEADER = "\nUser instructions added during pause:"

ROUTER_PROMPT = """\
Decide if answering the following request requires browsing the web or not.
Reply with exactly one word: BROWSE or ANSWER.
- BROWSE: needs live web data, searching, visiting URLs, or interacting with websites.
- ANSWER: can be answered from general knowledge, conversation context, or is conversational \
(greetings, follow-up questions on prior results, etc.).

Request: {task}
"""

KEEP_BROWSER_PROMPT = """\
A browser automation task has just completed. Decide whether the browser should stay open.

Keep open (YES) if: the result is something the user will likely want to act on directly \
in the browser — a filled cart, a product page, a booking form, a recommendation page, \
a course to purchase, or any page requiring a follow-up action by the user.

Close (NO) if: the task was purely informational — research, data extraction, answering a \
question — and the result has been delivered as text. No browser interaction is needed.

When in doubt, answer YES.

Task: {task}
Result summary: {result}

Reply with exactly one word: YES or NO.
"""
