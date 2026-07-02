"""
Slot allocation optimizer (project plan, section 2.2): the core mixed-integer
program that jointly assigns waitlist demand to available slots, maximizing
fill rate and preferring urgent/long-waiting demand and earlier slots within
each demand's time-window preferences.

Deliberately decoupled from Django: no ORM/model imports here, only plain
data in and plain data out, so this stays swappable as the math matures (see
apps/optimization/models.py's OptimizationRun docstring and CLAUDE.md's
architecture note). Callers translate Django querysets into Demand/SlotOption
and translate AllocationResult back into model writes.

Overtime risk (the third term in the plan's stated objective) is not modeled
here -- it only has honest mathematical meaning once true overbooking exists
(deliberately assigning two demands to one slot), which this round doesn't
implement.
"""

from dataclasses import dataclass
from datetime import datetime

from ortools.sat.python import cp_model


@dataclass(frozen=True)
class Demand:
    """One thing waiting for a slot -- typically a WaitlistEntry."""

    id: str
    urgency: int
    wait_hours: float
    preferred_windows: list[tuple[datetime, datetime]] | None = None  # None = any slot fits


@dataclass(frozen=True)
class SlotOption:
    """One assignable slot -- typically one get_available_slots() result."""

    id: str
    start: datetime
    end: datetime


@dataclass(frozen=True)
class Assignment:
    demand_id: str
    slot_id: str


@dataclass(frozen=True)
class AllocationResult:
    assignments: list[Assignment]
    objective_value: float
    status: str  # "optimal" | "feasible" | "infeasible" | "no_demand" | "no_slots"


def _fits_preference(slot, windows):
    if windows is None:
        return True
    return any(start <= slot.start < end for start, end in windows)


def allocate_slots(
    demands,
    slots,
    *,
    urgency_weight=50.0,
    wait_weight=1.0,
    fill_weight=1000.0,
    time_limit_seconds=10,
):
    """
    Jointly assigns demands to slots. Each demand gets at most one slot, each
    slot goes to at most one demand, and a (demand, slot) pair is only
    eligible if the slot falls inside the demand's preferred_windows (or the
    demand has none). Maximizes a weighted score: filling any slot at all
    dominates (fill_weight), then higher urgency and longer wait are
    preferred, then earlier slots are preferred among otherwise-equal
    candidates.
    """
    if not demands:
        return AllocationResult(assignments=[], objective_value=0.0, status="no_demand")
    if not slots:
        return AllocationResult(assignments=[], objective_value=0.0, status="no_slots")

    earliest = min(slot.start for slot in slots)

    model = cp_model.CpModel()
    x = {}
    pair_score = {}
    for demand in demands:
        for slot in slots:
            if not _fits_preference(slot, demand.preferred_windows):
                continue
            days_out = (slot.start - earliest).total_seconds() / 3600 / 24
            score = (
                fill_weight
                + urgency_weight * demand.urgency
                + wait_weight * demand.wait_hours
                # Tie-breaker, scaled by urgency: when several demands are
                # filled at once (the fill/urgency terms above are additive
                # and don't otherwise care *which* demand gets *which* of
                # the chosen slots), this makes more urgent demands
                # preferentially land on the earlier ones instead of the
                # assignment being arbitrary among equally-good totals.
                - days_out * demand.urgency
            )
            var = model.NewBoolVar(f"x_{demand.id}_{slot.id}")
            x[(demand.id, slot.id)] = var
            pair_score[(demand.id, slot.id)] = round(score * 100)  # CP-SAT needs integers

    if not x:
        return AllocationResult(assignments=[], objective_value=0.0, status="infeasible")

    for demand in demands:
        pairs = [x[(demand.id, slot.id)] for slot in slots if (demand.id, slot.id) in x]
        if pairs:
            model.Add(sum(pairs) <= 1)

    for slot in slots:
        pairs = [x[(demand.id, slot.id)] for demand in demands if (demand.id, slot.id) in x]
        if pairs:
            model.Add(sum(pairs) <= 1)

    model.Maximize(sum(pair_score[key] * var for key, var in x.items()))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_seconds
    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return AllocationResult(assignments=[], objective_value=0.0, status="infeasible")

    assignments = [
        Assignment(demand_id=demand_id, slot_id=slot_id)
        for (demand_id, slot_id), var in x.items()
        if solver.Value(var)
    ]
    status_str = "optimal" if status == cp_model.OPTIMAL else "feasible"
    return AllocationResult(
        assignments=assignments,
        objective_value=solver.ObjectiveValue() / 100,
        status=status_str,
    )
