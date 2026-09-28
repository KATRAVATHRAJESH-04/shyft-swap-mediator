"""policy_engine.py - Institutional Policy Lifecycle, Versioning & Conflict Resolution.

Solves the append-only memory drawback:
- Tracks active vs superseded policies.
- Automatically detects if a new manager ruling supersedes an older rule.
- Maintains version history (e.g. Policy v1.0 -> v1.1).
"""

from typing import Any


class PolicyRegistry:
    def __init__(self):
        self.policies = [
            {
                "id": "POL-001",
                "name": "App-Logging Requirement",
                "rule": "Verbal-only swaps are non-binding. Every swap must be logged in the Shyft app.",
                "established_by": "Priya Nair",
                "effective_date": "2026-06-14",
                "version": "1.0",
                "status": "ACTIVE",
                "category": "Documentation",
            },
            {
                "id": "POL-002",
                "name": "Festival-Day Multiplier",
                "rule": "Festival-day shift coverage counts as two regular shifts (standing policy for all staff).",
                "established_by": "Priya Nair",
                "effective_date": "2026-07-20",
                "version": "1.0",
                "status": "ACTIVE",
                "category": "Shift Accounting",
            },
            {
                "id": "POL-003",
                "name": "Window Expiration & Debt Preservation",
                "rule": "Expired 30-day return windows do NOT erase shift debt. 7-day repayment deadline is issued.",
                "established_by": "Priya Nair",
                "effective_date": "2026-07-26",
                "version": "1.0",
                "status": "ACTIVE",
                "category": "Debt Enforcement",
            },
            {
                "id": "POL-004",
                "name": "Default 30-Day Window",
                "rule": "A covered shift must be returned within 30 days of cover date unless otherwise specified.",
                "established_by": "Brewline Policy",
                "effective_date": "2026-06-01",
                "version": "1.0",
                "status": "ACTIVE",
                "category": "Timeline",
            },
            {
                "id": "POL-005",
                "name": "Emergency Exemption",
                "rule": "Genuine emergencies are the only valid exception to shift swap policy.",
                "established_by": "Brewline Policy",
                "effective_date": "2026-06-01",
                "version": "1.0",
                "status": "ACTIVE",
                "category": "Exceptions",
            },
        ]

    def get_active_policies(self) -> list[dict]:
        return [p for p in self.policies if p["status"] == "ACTIVE"]

    def get_all_policies(self) -> list[dict]:
        return self.policies

    def register_or_supersede(self, ruling: str, dispute: str, when: str = "2026-09-28") -> dict:
        """Detects whether this ruling establishes a new rule or supersedes an older one."""
        ruling_lower = ruling.lower()

        # Check if this is a half-shift policy
        if "half" in ruling_lower or "4 hours" in ruling_lower:
            existing = next((p for p in self.policies if "half-shift" in p["name"].lower() or "partial" in p["name"].lower()), None)
            if existing:
                existing["status"] = "SUPERSEDED"
                existing["superseded_by"] = f"POL-{len(self.policies)+1:03d}"
                new_v = "1.1"
            else:
                new_v = "1.0"

            new_pol = {
                "id": f"POL-{len(self.policies)+1:03d}",
                "name": "Partial / Half-Shift Pro-Rata Coverage",
                "rule": ruling,
                "established_by": "Priya Nair",
                "effective_date": when,
                "version": new_v,
                "status": "ACTIVE",
                "category": "Shift Accounting",
            }
            self.policies.append(new_pol)
            return {"action": "ESTABLISHED", "policy": new_pol, "is_superseding": existing is not None}

        # General ruling registration
        new_pol = {
            "id": f"POL-{len(self.policies)+1:03d}",
            "name": f"Manager Ruling ({when})",
            "rule": ruling,
            "established_by": "Priya Nair",
            "effective_date": when,
            "version": "1.0",
            "status": "ACTIVE",
            "category": "Precedent",
        }
        self.policies.append(new_pol)
        return {"action": "RECORDED", "policy": new_pol, "is_superseding": False}
