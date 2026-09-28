"""policy_engine.py - Policy index derived from seed records.

NOTE: The LLM does NOT query this registry. The LLM's knowledge and citations
come 100% from Hindsight Cloud memory recall. This registry is solely an
operational UI display derived directly from historical seed records in seed_data.py:

- POL-001 (App Logging Requirement):
  Derived from seed_data.py 2026-06-01 policy & 2026-06-14 ruling ("verbal swaps non-binding").
- POL-002 (Festival-Day Multiplier):
  Derived from seed_data.py 2026-07-20 dispute ruling (festival shift = 2 regular shifts).
- POL-003 (Debt Preservation & Window Expiration):
  Derived from seed_data.py 2026-07-26 dispute ruling (expired windows do not cancel debt).
- POL-004 (Default 30-Day Window):
  Derived from seed_data.py 2026-06-01 policy (covered shifts must be returned within 30 days).
- POL-005 (Emergency Exemption):
  Derived from seed_data.py 2026-06-01 policy (genuine emergencies are the only exception).
"""

from typing import Any


class PolicyRegistry:
    def __init__(self):
        self.source = "Policy index derived from seed records"
        self.policies = [
            {
                "id": "POL-001",
                "name": "App-Logging Requirement",
                "rule": "Verbal-only swaps are non-binding. Every swap must be logged in the Shyft app.",
                "established_by": "Priya Nair",
                "effective_date": "2026-06-14",
                "version": "1.0",
                "status": "ACTIVE",
                "derived_from": "seed_data.py (2026-06-01 & 2026-06-14)",
            },
            {
                "id": "POL-002",
                "name": "Festival-Day Multiplier",
                "rule": "Festival-day shift coverage counts as two regular shifts (standing policy for all staff).",
                "established_by": "Priya Nair",
                "effective_date": "2026-07-20",
                "version": "1.0",
                "status": "ACTIVE",
                "derived_from": "seed_data.py (2026-07-20)",
            },
            {
                "id": "POL-003",
                "name": "Window Expiration & Debt Preservation",
                "rule": "Expired 30-day return windows do NOT erase shift debt. 7-day repayment deadline is issued.",
                "established_by": "Priya Nair",
                "effective_date": "2026-07-26",
                "version": "1.0",
                "status": "ACTIVE",
                "derived_from": "seed_data.py (2026-07-26)",
            },
            {
                "id": "POL-004",
                "name": "Default 30-Day Window",
                "rule": "A covered shift must be returned within 30 days of cover date unless otherwise specified.",
                "established_by": "Brewline Policy",
                "effective_date": "2026-06-01",
                "version": "1.0",
                "status": "ACTIVE",
                "derived_from": "seed_data.py (2026-06-01)",
            },
            {
                "id": "POL-005",
                "name": "Emergency Exemption",
                "rule": "Genuine emergencies are the only valid exception to shift swap policy.",
                "established_by": "Brewline Policy",
                "effective_date": "2026-06-01",
                "version": "1.0",
                "status": "ACTIVE",
                "derived_from": "seed_data.py (2026-06-01)",
            },
        ]

    def get_active_policies(self) -> list[dict]:
        return [p for p in self.policies if p["status"] == "ACTIVE"]

    def get_all_policies(self) -> list[dict]:
        return self.policies

    def register_or_supersede(self, ruling: str, dispute: str, when: str = "2026-09-28") -> dict:
        """Tracks dynamically added manager rulings into the index."""
        ruling_lower = ruling.lower()

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
                "derived_from": "Live Manager Ruling in Hindsight",
            }
            self.policies.append(new_pol)
            return {"action": "ESTABLISHED", "policy": new_pol, "is_superseding": existing is not None}

        new_pol = {
            "id": f"POL-{len(self.policies)+1:03d}",
            "name": f"Manager Ruling ({when})",
            "rule": ruling,
            "established_by": "Priya Nair",
            "effective_date": when,
            "version": "1.0",
            "status": "ACTIVE",
            "derived_from": "Live Manager Ruling in Hindsight",
        }
        self.policies.append(new_pol)
        return {"action": "RECORDED", "policy": new_pol, "is_superseding": False}
