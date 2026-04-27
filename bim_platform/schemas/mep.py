"""
schemas.mep — mechanical, electrical, plumbing strategy.

The MEP Agent picks systems and equipment locations. The IFC writer turns
those into actual ducts, pipes, panels, and fixtures during render.

Strategy fields are typology-aware via free-text values rather than rigid
enums. A residential heat-pump system and a commercial chilled-water VAV
system are both valid hvac_type strings; the renderer dispatches on them.
"""
from __future__ import annotations
from typing import Optional, Literal
from pydantic import BaseModel, Field


class MEPZone(BaseModel):
    """One thermal/control zone in the building."""
    name: str
    floors: list[str] = Field(default_factory=list)   # which floors this zone serves (by Floor.name)
    spaces: list[str] = Field(default_factory=list)   # specific spaces (empty = all on the floors)
    setpoint_heat_c: float = 21.0
    setpoint_cool_c: float = 24.0

class MEPStrategy(BaseModel):
    """The MEP Agent's output — system selections + equipment locations."""

    # HVAC
    hvac_type: str = "heat_pump_central"
        # residential: heat_pump_central, heat_pump_split, gas_furnace_ac, hydronic
        # commercial:  vav_with_chilled_water, vrf, packaged_rtu, fan_coil_with_doas
    hvac_zones: int = 1
    zones: list[MEPZone] = Field(default_factory=list)
    equipment_location: str = "utility_room"
        # residential: utility_room, garage, attic, basement
        # commercial:  mep_room, rooftop, basement_mech, mezzanine_mech

    # Plumbing
    hot_water: str = "tank_electric"
        # tank_electric, tank_gas, tankless_electric, tankless_gas, central_heat_pump
    plumbing_chase_locations: list[str] = Field(default_factory=list)
        # space names where plumbing risers run; "core" for commercial center-core

    # Electrical
    electrical_panel_amps: int = 200
    electrical_panel_location: Optional[str] = None
    secondary_panels: int = 0  # for larger buildings

    # Ventilation
    ventilation: str = "mechanical_exhaust"
        # mechanical_exhaust, balanced_with_hrv, balanced_with_erv,
        # 100pct_outside_air, demand_controlled
    fresh_air_cfm_per_person: float = 7.5  # ASHRAE 62.1 baseline

    # Life safety
    sprinklers: bool = False
    smoke_detectors: bool = True
    standpipes: bool = False  # required for taller buildings
    fire_pump: bool = False

    # Heating fuel (for buildings using fuel)
    heating_fuel: str = "heat_pump"
        # heat_pump, gas, electric_resistance, oil, district

    rationale: Optional[str] = None
