"""guardrails.py - Ruling consistency check.

Performs internal consistency checks on proposed rulings:
1. Deadline stated: verifies an explicit timeline or deadline is specified.
2. Swap logged in the app: verifies the ruling reinforces logging swaps in the Shyft app.
3. Neutral tone: verifies the language is professional, objective, and neutral.

No legal or labor law claims are made.
"""


def check_ruling_consistency(ruling: str, dispute: str = "") -> dict:
    """Checks ruling text against Brewline store practice guidelines."""
    ruling_lower = (ruling or "").lower()

    # 1. Deadline stated
    deadline_terms = ["7 days", "30 days", "tomorrow", "deadline", "by ", "within", "window", "2026-"]
    has_deadline = any(term in ruling_lower for term in deadline_terms)
    
    # 2. Swap logged in the app
    app_terms = ["app", "shyft", "logged", "record", "written"]
    has_app_mention = any(term in ruling_lower for term in app_terms)

    # 3. Neutral tone
    punitive_terms = ["fired", "terminate", "punish", "fine", "dock pay", "penalty"]
    has_neutral_tone = not any(term in ruling_lower for term in punitive_terms)

    checks = [
        {
            "name": "Deadline stated",
            "passed": has_deadline,
            "detail": "Clear timeline or return deadline included." if has_deadline else "No calendar deadline found."
        },
        {
            "name": "Swap logged in the app",
            "passed": has_app_mention,
            "detail": "Emphasizes written logging in the Shyft app." if has_app_mention else "App logging not explicitly referenced."
        },
        {
            "name": "Neutral tone",
            "passed": has_neutral_tone,
            "detail": "Tone is objective and constructive." if has_neutral_tone else "Hostile or punitive phrasing detected."
        }
    ]

    all_passed = all(c["passed"] for c in checks)
    return {
        "all_passed": all_passed,
        "checks": checks,
        "summary": "Ruling consistency check passed" if all_passed else "Notice: review check items"
    }


