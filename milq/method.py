"""The processing method: the component table plus project-wide defaults."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field

from .components import (
    AcceptanceLimits,
    Component,
    IntegrationParams,
    load_components,
    save_components,
)


@dataclass
class ProcessingMethod:
    """Everything needed to turn raw samples into results."""

    components: list[Component] = field(default_factory=list)
    #: default XIC half window when a component does not override it
    tolerance: float = 0.02
    unit: str = "Da"
    concentration_unit: str = "ng/mL"
    #: integration settings every component inherits unless it overrides them
    defaults: IntegrationParams = field(default_factory=IntegrationParams)
    #: acceptance criteria every component inherits unless it overrides them
    acceptance: AcceptanceLimits = field(default_factory=AcceptanceLimits)
    #: relative deviation from the expected ion ratio that still passes, and
    #: the wider band that is only flagged as marginal, both in percent
    ion_ratio_tolerance: float = 20.0
    ion_ratio_marginal: float = 30.0

    # -- lookups --------------------------------------------------------------- #
    def by_name(self, name: str) -> Component | None:
        for component in self.components:
            if component.name == name:
                return component
        return None

    @property
    def internal_standards(self) -> list[Component]:
        return [c for c in self.components if c.is_internal_standard]

    @property
    def analytes(self) -> list[Component]:
        return [c for c in self.components if not c.is_internal_standard]

    def internal_standard_for(self, component: Component) -> Component | None:
        """The internal standard a component is quantified against, if any."""
        if not component.internal_standard:
            return None
        target = self.by_name(component.internal_standard)
        return target if target is not None and target is not component else None

    def integration_for(self, component: Component) -> IntegrationParams:
        """The settings actually used for a component."""
        return component.integration or self.defaults

    def set_integration(self, component: Component,
                        params: IntegrationParams | None) -> None:
        component.integration = params.copy() if params is not None else None

    def apply_integration_to_group(self, group: str,
                                   params: IntegrationParams) -> int:
        """Give every component of a group the same settings."""
        touched = 0
        for component in self.components:
            if component.group == group:
                component.integration = params.copy()
                touched += 1
        return touched

    def acceptance_for(self, component: Component) -> AcceptanceLimits:
        """The acceptance criteria actually used for a component."""
        return component.acceptance or self.acceptance

    def qualifiers_for(self, component: Component) -> list[Component]:
        """The qualifier transitions that confirm a given quantifier."""
        return [c for c in self.components if c.qualifier_of == component.name]

    def quantifier_for(self, component: Component) -> Component | None:
        """The quantifier a qualifier belongs to."""
        if not component.qualifier_of:
            return None
        target = self.by_name(component.qualifier_of)
        return target if target is not None and target is not component else None

    def ion_ratio_limits(self, component: Component) -> tuple[float, float]:
        """Pass and marginal deviations for a component, in percent."""
        tolerance = component.ion_ratio_tolerance or self.ion_ratio_tolerance
        marginal = max(self.ion_ratio_marginal, tolerance)
        return tolerance, marginal

    def groups(self) -> list[str]:
        seen = []
        for component in self.components:
            if component.group and component.group not in seen:
                seen.append(component.group)
        return seen

    # -- editing ---------------------------------------------------------------- #
    def add(self, component: Component) -> None:
        self.components.append(component)

    def replace_all(self, components: list[Component]) -> None:
        self.components = list(components)

    def clear(self) -> None:
        self.components = []

    # -- persistence -------------------------------------------------------------#
    def to_dict(self) -> dict:
        data = asdict(self)
        data["components"] = [asdict(c) for c in self.components]
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "ProcessingMethod":
        raw = dict(data or {})
        components = [
            Component(**{k: v for k, v in row.items()
                         if k in Component.__dataclass_fields__})
            for row in raw.pop("components", [])
        ]
        defaults = raw.pop("defaults", None)
        acceptance = raw.pop("acceptance", None)
        known = {k: v for k, v in raw.items() if k in cls.__dataclass_fields__}
        method = cls(**known)
        if isinstance(defaults, dict):
            method.defaults = IntegrationParams(
                **{k: v for k, v in defaults.items()
                   if k in IntegrationParams.__dataclass_fields__})
        if isinstance(acceptance, dict):
            method.acceptance = AcceptanceLimits(
                **{k: v for k, v in acceptance.items()
                   if k in AcceptanceLimits.__dataclass_fields__})
        method.components = components
        return method

    def save(self, path: str | os.PathLike) -> None:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(self.to_dict(), handle, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, path: str | os.PathLike) -> "ProcessingMethod":
        with open(path, encoding="utf-8") as handle:
            return cls.from_dict(json.load(handle))

    # -- CSV of the component table only ---------------------------------------- #
    def import_components(self, path: str | os.PathLike) -> int:
        self.components = load_components(path)
        return len(self.components)

    def export_components(self, path: str | os.PathLike) -> None:
        save_components(path, self.components)
