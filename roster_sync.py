"""roster_sync.py - Simulated roster payload generator.

Generates a simulated payload for IT inspection, showing what an operational
event schema would look like if exported to an external scheduling system.
No external systems are contacted.
"""

from datetime import datetime
import uuid


def generate_roster_payload(dispute: str, ruling: str, store_id: str = "brewline-01") -> dict:
    """Generates a simulated scheduling roster payload."""
    event_id = f"evt_{uuid.uuid4().hex[:10]}"
    today_str = datetime.now().strftime("%Y-%m-%d")

    # Detect employees involved
    all_names = ["Arjun", "Meera", "Rohan", "Kavya", "Sana", "Aisha", "Tariq"]
    involved = [name for name in all_names if name.lower() in dispute.lower()]

    # Determine shift resolution
    if "two shift" in ruling.lower() or "2 shift" in ruling.lower():
        shift_count = 2.0
    elif "half" in ruling.lower() or "4 hours" in ruling.lower():
        shift_count = 0.5
    else:
        shift_count = 1.0

    payload = {
        "version": "v1.2",
        "event_id": event_id,
        "event_type": "SHIFT_SWAP_RESOLVED",
        "timestamp": f"{today_str}T18:00:00Z",
        "store_id": store_id,
        "manager": {
            "id": "mgr_priya_01",
            "name": "Priya Nair",
            "role": "Shift Manager"
        },
        "dispute_summary": dispute[:120],
        "ruling_text": ruling,
        "parties_involved": involved,
        "roster_actions": [
            {
                "action_type": "CREDIT_DEBIT_BALANCE",
                "shift_units": shift_count,
                "source": "Hindsight Memory Precedent",
                "example_targets": ["scheduling system", "point of sale"],
                "status": "SIMULATED"
            }
        ],
        "audit": {
            "precedent_grounded": True,
            "consistency_checked": True
        }
    }
    return payload
