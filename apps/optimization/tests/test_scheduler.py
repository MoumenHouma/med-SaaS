"""
Pure unit tests for apps.optimization.services.scheduler -- no Django DB
needed, matching the module's own no-ORM design.
"""

from datetime import datetime, timedelta, timezone

from apps.optimization.services.scheduler import Assignment, Demand, SlotOption, allocate_slots


def _dt(days=0, hours=9.0):
    base = datetime(2026, 8, 3, tzinfo=timezone.utc)  # a Monday
    return base + timedelta(days=days, hours=hours - 9)


def test_no_demand_returns_no_demand_status():
    result = allocate_slots([], [SlotOption(id="s1", start=_dt(), end=_dt(hours=9.5))])
    assert result.status == "no_demand"
    assert result.assignments == []


def test_no_slots_returns_no_slots_status():
    result = allocate_slots([Demand(id="d1", urgency=1, wait_hours=1)], [])
    assert result.status == "no_slots"
    assert result.assignments == []


def test_single_demand_single_slot_gets_assigned():
    demand = Demand(id="d1", urgency=1, wait_hours=1)
    slot = SlotOption(id="s1", start=_dt(), end=_dt(hours=9.5))
    result = allocate_slots([demand], [slot])
    assert result.status == "optimal"
    assert result.assignments == [Assignment(demand_id="d1", slot_id="s1")]


def test_capacity_one_slot_goes_to_only_one_demand():
    d1 = Demand(id="d1", urgency=1, wait_hours=1)
    d2 = Demand(id="d2", urgency=1, wait_hours=1)
    slot = SlotOption(id="s1", start=_dt(), end=_dt(hours=9.5))
    result = allocate_slots([d1, d2], [slot])
    assert len(result.assignments) == 1


def test_one_demand_does_not_consume_two_slots():
    demand = Demand(id="d1", urgency=1, wait_hours=1)
    s1 = SlotOption(id="s1", start=_dt(hours=9), end=_dt(hours=9.5))
    s2 = SlotOption(id="s2", start=_dt(hours=10), end=_dt(hours=10.5))
    result = allocate_slots([demand], [s1, s2])
    assert len(result.assignments) == 1


def test_higher_urgency_wins_the_only_slot():
    low = Demand(id="low", urgency=1, wait_hours=1)
    high = Demand(id="high", urgency=3, wait_hours=1)
    slot = SlotOption(id="s1", start=_dt(), end=_dt(hours=9.5))
    result = allocate_slots([low, high], [slot])
    assert result.assignments == [Assignment(demand_id="high", slot_id="s1")]


def test_earlier_slot_preferred_among_equal_demand():
    demand = Demand(id="d1", urgency=1, wait_hours=1)
    early = SlotOption(id="early", start=_dt(hours=9), end=_dt(hours=9.5))
    late = SlotOption(id="late", start=_dt(hours=16), end=_dt(hours=16.5))
    result = allocate_slots([demand], [early, late])
    assert result.assignments == [Assignment(demand_id="d1", slot_id="early")]


def test_preferred_window_restricts_eligible_slots():
    morning_only = Demand(
        id="d1", urgency=1, wait_hours=1,
        preferred_windows=[(_dt(hours=8), _dt(hours=12))],
    )
    afternoon_slot = SlotOption(id="afternoon", start=_dt(hours=14), end=_dt(hours=14.5))
    morning_slot = SlotOption(id="morning", start=_dt(hours=9), end=_dt(hours=9.5))
    result = allocate_slots([morning_only], [afternoon_slot, morning_slot])
    assert result.assignments == [Assignment(demand_id="d1", slot_id="morning")]


def test_demand_with_no_matching_slot_is_left_unassigned_not_infeasible():
    """A demand whose preference excludes every slot just doesn't get one --
    other demands with eligible slots are still assigned normally."""
    morning_only = Demand(
        id="picky", urgency=1, wait_hours=1,
        preferred_windows=[(_dt(hours=8), _dt(hours=9))],
    )
    flexible = Demand(id="flexible", urgency=1, wait_hours=1)
    afternoon_slot = SlotOption(id="s1", start=_dt(hours=14), end=_dt(hours=14.5))
    result = allocate_slots([morning_only, flexible], [afternoon_slot])
    assert result.status in ("optimal", "feasible")
    assert result.assignments == [Assignment(demand_id="flexible", slot_id="s1")]


def test_fully_infeasible_when_no_pair_is_eligible_at_all():
    morning_only = Demand(
        id="d1", urgency=1, wait_hours=1,
        preferred_windows=[(_dt(hours=8), _dt(hours=9))],
    )
    afternoon_slot = SlotOption(id="s1", start=_dt(hours=14), end=_dt(hours=14.5))
    result = allocate_slots([morning_only], [afternoon_slot])
    assert result.status == "infeasible"
    assert result.assignments == []


def test_objective_value_is_positive_when_assignments_made():
    demand = Demand(id="d1", urgency=2, wait_hours=5)
    slot = SlotOption(id="s1", start=_dt(), end=_dt(hours=9.5))
    result = allocate_slots([demand], [slot])
    assert result.objective_value > 0
