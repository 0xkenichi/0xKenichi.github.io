"""Floor regimes as full UTC days. Days on which the floor was moving are left out of every regime.

Boundaries come from data/floor_changes.csv (floor.py): each regime starts on the first full UTC day
after a transition ended and stops on the last full UTC day before the next one started.
"""
REGIMES = [
    # key,        label,                                                  first day,     last day
    ("pre_aug",   "Before Helicon, Aug (floor 1 wei)",                    "2026-08-01", "2026-08-31"),
    ("pre_sep",   "Before Helicon, 1-21 Sep (floor 1 wei)",               "2026-09-01", "2026-09-21"),
    ("pre_last10", "Last 10 days before Helicon (12-21 Sep)",              "2026-09-12", "2026-09-21"),
    # Helicon activated 22 Sep 15:00 UTC; the floor ramped 1 wei -> 5 nAVAX until 27 Sep 06:06 UTC
    # (it passed the ~0.07 nAVAX market base fee on 26 Sep). 22-27 Sep are left out.
    ("f5",        "Floor 5 nAVAX",                                        "2026-09-28", "2026-10-18"),
    # 5 -> 2.5 on 19 Oct 15:16-19:10 UTC (19 Oct left out)
    ("f2_5",      "Floor 2.5 nAVAX",                                      "2026-10-20", "2026-11-08"),
    # 2.5 -> 7.5 from 9 Nov 23:14 to 10 Nov 05:14 UTC (9-10 Nov left out)
    ("f7_5",      "Floor 7.5 nAVAX (to 25 Nov, last complete day)",      "2026-11-11", "2026-11-25"),
]


def regime_of(day):
    """Primary regime of a day (the overlapping 'pre_last10' comparison window is not used here)."""
    for key, _, a, b in REGIMES:
        if key != "pre_last10" and a <= day <= b:
            return key
    return None
