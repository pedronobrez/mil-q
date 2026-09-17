"""Matching a method component to the acquisition channel that carries it."""

from __future__ import annotations

from .components import Component

#: largest gap, in Da, between a component precursor and a channel precursor
#: that still counts as the same target
PRECURSOR_MATCH_DA = 0.7


def covers_rt(channel, rt: float | None) -> bool:
    """Was the channel acquired at that time? With no RT given, accept any."""
    if rt is None:
        return True
    times = channel.rt
    return bool(times.size and times[0] <= rt <= times[-1])


def match_channel(sample, component: Component, tolerance: float = PRECURSOR_MATCH_DA):
    """
    Pick the acquisition channel that corresponds to a component.

    Scheduled methods repeat the same precursor in different periods — on a
    TripleTOF running MRM-HR, 313.24 can appear in one experiment covering
    0-13 min and another covering 13-21.5 min. That is why the expected
    retention time is part of the criterion: matching on precursor alone would
    pick the wrong channel, one that was not even acquired at that time.

    Falls back to a full-scan channel whose mass range contains the target, and
    returns None when nothing fits.
    """
    target = component.target_mz
    if target <= 0:
        return None

    def candidates(require_rt: bool):
        found = []
        for channel in sample.channels:
            precursor = channel.info.precursor
            if precursor is None:
                continue
            if abs(precursor - component.precursor) > tolerance:
                continue
            if not (channel.info.start_mass <= target <= channel.info.end_mass):
                continue
            if require_rt and not covers_rt(channel, component.rt):
                continue
            found.append((abs(precursor - component.precursor), channel.index, channel))
        return sorted(found)

    matches = candidates(require_rt=True) or candidates(require_rt=False)
    if matches:
        return matches[0][2]

    survey = [
        c for c in sample.channels
        if c.info.is_ms1 and c.info.start_mass <= target <= c.info.end_mass
    ]
    for channel in survey:
        if covers_rt(channel, component.rt):
            return channel
    return survey[0] if survey else None


def components_from_sample(sample, adduct: str = "") -> list[Component]:
    """
    Build a component table from the acquisition method itself.

    Every product-ion channel becomes one component named after its precursor,
    with the retention time left blank so the first processing run can find it.
    Saves transcribing an 80-transition method by hand; names and fragments are
    meant to be edited afterwards.
    """
    components: list[Component] = []
    seen: set[tuple[float, int]] = set()
    for channel in sample.channels:
        info = channel.info
        if info.precursor is None:
            continue
        times = channel.rt
        period = int(round(float(times[0]))) if times.size else 0
        key = (round(info.precursor, 4), period)
        if key in seen:
            continue
        seen.add(key)
        components.append(
            Component(
                name=f"{info.precursor:.2f}",
                precursor=float(info.precursor),
                fragment=None,
                rt=None,
                adduct=adduct,
                group="",
            )
        )
    return components
