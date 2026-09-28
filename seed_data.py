"""Synthetic history for Brewline Cafe, written backwards from the three demo beats.

Beat 1 (festival-shift math)  -> needs RECORDS on the 2026-07-20 standing exception
Beat 2 (expired swap window)   -> needs the Aug 8/22 covers + the 2026-07-26 precedent
Beat 3 (Arjun pattern)         -> needs the Jun 14 + Jul 26 disputes (+ beat 2's own ruling)
"""
from datetime import datetime

import memory

D = lambda s: datetime.strptime(s, "%Y-%m-%d")

# (date, context, text)
RECORDS = [
    ("2026-06-01", "policy",
     "Brewline Cafe policy: every shift swap must be approved by manager Priya Nair in the Shyft app. "
     "Verbal-only swaps are not binding on either employee unless Priya confirms them. "
     "The only exception is a genuine emergency."),
    ("2026-06-01", "policy",
     "Brewline Cafe policy: a covered shift must be returned within 30 days of the cover date, "
     "unless Priya sets a different date when approving the swap."),
    ("2026-06-02", "employee profile",
     "Meera Iyer is a full-time barista at Brewline Cafe. She covers shifts for colleagues often and "
     "has never missed a shift she committed to."),
    ("2026-06-02", "employee profile",
     "Arjun Rao is an evening barista at Brewline Cafe. He frequently asks colleagues to cover his "
     "Friday closing shifts and Saturday evening shifts."),
    ("2026-06-02", "employee profile",
     "Sana Khan is a part-time barista. She insists on written confirmation in the Shyft app before "
     "agreeing to any shift swap."),
    ("2026-06-02", "employee profile",
     "Rohan Shah is a reliable barista who was late twice in July 2026 but has never missed a shift."),
    ("2026-06-21", "swap",
     "On 2026-06-21 (Sunday) Rohan Shah covered Arjun Rao's shift. Terms logged in the Shyft app: "
     "Arjun returns one Sunday within 30 days."),
    ("2026-06-14", "dispute ruling",
     "Dispute on 2026-06-14: Arjun Rao claimed Sana Khan had verbally agreed to take his Friday "
     "closing shift on 2026-06-12. Sana denied it and nothing was logged in the Shyft app. "
     "Priya ruled the verbal swap was not binding, Arjun had to work the shift, and reminded "
     "everyone to post swaps in the app."),
    ("2026-07-19", "swap",
     "On 2026-07-19 (Sunday, a festival day) Sana Khan covered Rohan Shah's shift, approved in the "
     "Shyft app."),
    ("2026-07-20", "dispute ruling",
     "Dispute on 2026-07-20: Sana Khan and Rohan Shah disagreed about how many shifts Rohan owed "
     "after Sana covered his festival-day Sunday. Priya ruled that a festival-day shift counts as two "
     "regular shifts when swapped, and made this a standing exception for all staff."),
    ("2026-07-26", "dispute ruling",
     "Dispute on 2026-07-26: Arjun Rao had not returned the Sunday Rohan Shah covered on 2026-06-21, "
     "and argued the 30-day window had expired so he owed nothing. Priya ruled that an expired window "
     "does not cancel the debt: Arjun had to return the shift within 7 days. He returned it on 2026-08-01."),
    ("2026-08-05", "staff meeting",
     "At the staff meeting on 2026-08-05 Priya told the team: the written record in the Shyft app "
     "decides disputes first, verbal claims are not binding, and debts do not expire, they get a new "
     "short deadline."),
    ("2026-08-08", "swap",
     "On 2026-08-08 (Saturday) Meera Iyer covered Arjun Rao's evening shift. Priya approved the swap "
     "in the Shyft app. Terms: Arjun returns one Saturday within 30 days."),
    ("2026-08-22", "swap",
     "On 2026-08-22 (Saturday) Meera Iyer covered Arjun Rao's evening shift a second time. Priya "
     "approved it in the Shyft app. Terms: Arjun returns one Saturday within 30 days."),
    ("2026-08-30", "swap",
     "On 2026-08-30 (Sunday, a festival day) Kavya Reddy covered Rohan Shah's shift. Priya approved "
     "it in the Shyft app with no return terms specified."),
    ("2026-09-03", "scheduling",
     "Meera Iyer requested Sunday 2026-09-13 off for a family event; Priya approved it."),
    ("2026-09-10", "scheduling",
     "Kavya Reddy's opening shift was moved to 7:30am for a supplier delivery."),
    ("2026-09-27", "shyft record",
     "As of 2026-09-27 the Shyft app shows no return Saturday logged by Arjun Rao for the covers "
     "Meera Iyer worked on 2026-08-08 and 2026-08-22."),
]


def seed() -> int:
    memory.ensure_bank()
    for date, context, text in RECORDS:
        memory.retain(text, context=context, when=D(date))
    return len(RECORDS)


if __name__ == "__main__":
    print(f"Retained {seed()} records into bank '{memory.BANK_ID}'.")
