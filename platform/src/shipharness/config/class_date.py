"""SHIPHARNESS_CLASS_DATE: the class day that class runs need.

Class runs (PURPOSE=class, the make default) trace to the LangSmith project
shipharness-class-<date> and share that day's cost session, so `make warm` and `make doctor` check
the date before class. PURPOSE=pilot and PURPOSE=assignment need no date.
"""

from __future__ import annotations

import re
from datetime import date

PURPOSES = ("class", "pilot", "assignment")
PURPOSE_CHOICES = "class, pilot, or assignment"
VARIABLE = "SHIPHARNESS_CLASS_DATE"
_FORM = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def class_project(day: str) -> str:
    """The LangSmith project of the class runs on `day`."""
    return f"shipharness-class-{day}"


def class_date_problem(day: str) -> str | None:
    """None when `day` is a real date written YYYY-MM-DD; otherwise what is wrong with it."""
    if not day:
        return f"{VARIABLE} is not set"
    if _FORM.match(day):
        try:
            date.fromisoformat(day)
        except ValueError:
            pass
        else:
            return None
    return f"{VARIABLE}={day[:40]!r} is not a date in the form YYYY-MM-DD"


def class_date_fix() -> list[str]:
    """How to set the date, and where class runs trace once it is set."""
    return [
        f"add this line to .env at the repository root: {VARIABLE}=YYYY-MM-DD",
        f"or, for this terminal only: export {VARIABLE}=YYYY-MM-DD",
        "(write the class day in place of YYYY-MM-DD)",
        f"class runs trace to the LangSmith project {class_project('<date>')}",
        "not a class run? use PURPOSE=pilot with make, or --purpose pilot",
    ]
