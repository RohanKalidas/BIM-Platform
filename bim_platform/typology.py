"""
bim_platform.typology — the ontology of building types.

A typology identifies what kind of building the user is asking for, and
gates which prompts, primitives, and library queries the build phase uses.
Typology-specific knowledge lives in PROMPTS (and primitive shapes), never
in agent code branches.

Categories (top-level):
  residential   — places people sleep
  commercial    — places people work or buy things
  institutional — places people learn, heal, gather civically
  hospitality   — places people stay short-term or eat
  industrial    — places people make or store things
  recreation    — places people exercise, watch, perform
  mixed_use     — combinations

Naming convention: "<category>.<subtype>" e.g. "residential.single_family".
The subtype string is what's looked up in the prompt directory.

Adding a new typology:
  1. Add an entry below
  2. Create build/prompts/<category>/<subtype>.md with style/feature minima
  3. Optionally add primitives in build/render/primitives/
  4. Optionally upload IFC files containing typical components
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class Typology:
    """A building type the system can generate."""
    key: str                    # canonical key, e.g. "office.class_a"
    category: str               # one of the top-level categories
    subtype: str                # second half of key
    display_name: str           # human-facing name
    aliases: list[str]          # alternate phrasings users might type
    description: str            # one-line description for prompt context
    typical_program: list[str]  # space types this typology usually contains
    code_refs: list[str]        # codes the Compliance Agent should consult
    structural_hint: str        # default structural system
    mep_hint: str               # default MEP system family
    primitive_libraries: list[str]  # which primitive modules apply
    component_categories: list[str] # IFC categories the library should have


# ── Residential ─────────────────────────────────────────────────────────
RESIDENTIAL_SINGLE_FAMILY = Typology(
    key="residential.single_family",
    category="residential",
    subtype="single_family",
    display_name="Single-family home",
    aliases=["house", "home", "cottage", "bungalow", "ranch", "single family"],
    description=(
        "Detached single-family residence. Typical program: living, dining, "
        "kitchen, bedrooms, bathrooms, optional garage, optional home office."
    ),
    typical_program=[
        "living_room", "dining_room", "kitchen", "bedroom", "bathroom",
        "hallway", "entry", "garage", "laundry", "home_office",
    ],
    code_refs=["IRC", "ADA-residential", "local-zoning"],
    structural_hint="wood_frame_platform",
    mep_hint="residential_split_or_heat_pump",
    primitive_libraries=["walls", "openings", "roofs", "residential"],
    component_categories=[
        "IfcFurniture", "IfcSanitaryTerminal", "IfcElectricAppliance",
        "IfcWindow", "IfcDoor",
    ],
)

RESIDENTIAL_MULTI_FAMILY = Typology(
    key="residential.multi_family",
    category="residential",
    subtype="multi_family",
    display_name="Multi-family residence",
    aliases=["apartment building", "condo", "duplex", "triplex", "townhouse", "apartments"],
    description=(
        "Multiple residential units sharing structure or party walls. May "
        "include shared circulation, lobbies, amenities."
    ),
    typical_program=[
        "unit", "lobby", "corridor", "stair", "elevator_lobby",
        "amenity", "trash_room", "mechanical_room", "parking",
    ],
    code_refs=["IBC", "IRC", "ADA", "fair-housing", "local-zoning"],
    structural_hint="wood_frame_or_concrete_podium",
    mep_hint="central_or_per_unit",
    primitive_libraries=["walls", "openings", "roofs", "residential", "commercial"],
    component_categories=[
        "IfcFurniture", "IfcSanitaryTerminal", "IfcElectricAppliance",
        "IfcWindow", "IfcDoor", "IfcStair", "IfcElevator",
    ],
)

# ── Commercial ──────────────────────────────────────────────────────────
OFFICE_CLASS_A = Typology(
    key="office.class_a",
    category="commercial",
    subtype="class_a",
    display_name="Class A office tower",
    aliases=["office tower", "highrise office", "corporate headquarters", "office complex"],
    description=(
        "High-rise commercial office building. Center-core typology with "
        "elevator banks, restrooms, services in the core; open floorplate "
        "perimeter for tenant fitout. Curtain wall facade typical."
    ),
    typical_program=[
        "core", "open_office", "conference_room", "executive_office",
        "breakroom", "elevator_lobby", "restroom", "stair", "mep_room",
        "it_closet", "loading_dock", "parking",
    ],
    code_refs=["IBC", "ADA", "ASHRAE-90.1", "NFPA-13", "local-zoning"],
    structural_hint="steel_or_concrete_frame_with_lateral_system",
    mep_hint="central_chilled_water_vav",
    primitive_libraries=["walls", "openings", "roofs", "commercial"],
    component_categories=[
        "IfcFurniture", "IfcWindow", "IfcDoor", "IfcCurtainWall",
        "IfcStair", "IfcColumn", "IfcBeam", "IfcSlab",
        "IfcAirTerminal", "IfcFlowTerminal",
    ],
)

OFFICE_SUBURBAN = Typology(
    key="office.suburban",
    category="commercial",
    subtype="suburban",
    display_name="Suburban office building",
    aliases=["office park", "suburban office", "low rise office"],
    description=(
        "Low-rise (1-5 story) office building in a suburban site. Side-core "
        "or distributed-core layout common. Punched window or strip-glazed "
        "facade, brick or panel cladding."
    ),
    typical_program=[
        "lobby", "open_office", "private_office", "conference_room",
        "breakroom", "restroom", "stair", "mep_room", "parking",
    ],
    code_refs=["IBC", "ADA", "ASHRAE-90.1", "local-zoning"],
    structural_hint="steel_frame_with_braced_bays",
    mep_hint="rooftop_units_with_vav",
    primitive_libraries=["walls", "openings", "roofs", "commercial"],
    component_categories=[
        "IfcFurniture", "IfcWindow", "IfcDoor", "IfcStair",
        "IfcAirTerminal", "IfcFlowTerminal",
    ],
)

RETAIL_STANDALONE = Typology(
    key="retail.standalone",
    category="commercial",
    subtype="standalone",
    display_name="Standalone retail",
    aliases=["store", "shop", "boutique", "big box", "retail store"],
    description=(
        "Single-tenant retail building. Open sales floor, back-of-house "
        "stockroom, single restroom or two."
    ),
    typical_program=[
        "sales_floor", "stockroom", "restroom", "office", "loading_dock",
    ],
    code_refs=["IBC", "ADA", "local-zoning"],
    structural_hint="steel_frame_or_tilt_up",
    mep_hint="rooftop_units",
    primitive_libraries=["walls", "openings", "roofs", "commercial"],
    component_categories=[
        "IfcFurniture", "IfcWindow", "IfcDoor", "IfcAirTerminal",
    ],
)

RETAIL_MIXED_USE_GROUND = Typology(
    key="retail.mixed_use_ground",
    category="commercial",
    subtype="mixed_use_ground",
    display_name="Mixed-use retail (ground floor)",
    aliases=["mixed use", "live work", "ground floor retail"],
    description=(
        "Ground-floor retail under residential or office above. Storefront "
        "glazing, ceiling height usually 14-18 ft."
    ),
    typical_program=[
        "sales_floor", "stockroom", "restroom", "service_entry",
    ],
    code_refs=["IBC", "ADA", "local-zoning"],
    structural_hint="concrete_transfer_slab_above",
    mep_hint="dedicated_rooftop_or_split",
    primitive_libraries=["walls", "openings", "roofs", "commercial"],
    component_categories=[
        "IfcFurniture", "IfcWindow", "IfcDoor", "IfcCurtainWall",
    ],
)

# ── Institutional ───────────────────────────────────────────────────────
EDUCATION_K12 = Typology(
    key="education.k12",
    category="institutional",
    subtype="k12",
    display_name="K-12 school",
    aliases=["elementary school", "middle school", "high school", "school"],
    description=(
        "Educational facility for grades K-12. Classroom wings, shared "
        "spaces (cafeteria, gym, library, auditorium), administration."
    ),
    typical_program=[
        "classroom", "lab", "cafeteria", "kitchen", "gymnasium",
        "library", "auditorium", "administration", "nurse",
        "restroom", "corridor", "stair", "mechanical_room",
    ],
    code_refs=["IBC", "ADA", "ASHRAE-90.1", "state-education-code"],
    structural_hint="steel_or_masonry_frame",
    mep_hint="central_with_classroom_unit_ventilators",
    primitive_libraries=["walls", "openings", "roofs", "commercial", "institutional"],
    component_categories=[
        "IfcFurniture", "IfcWindow", "IfcDoor", "IfcStair",
        "IfcAirTerminal", "IfcSanitaryTerminal",
    ],
)

EDUCATION_HIGHER_ED = Typology(
    key="education.higher_ed",
    category="institutional",
    subtype="higher_ed",
    display_name="Higher-education building",
    aliases=["university building", "college building", "lecture hall"],
    description=(
        "University or college building. Lecture halls, seminar rooms, "
        "labs, faculty offices, study spaces."
    ),
    typical_program=[
        "lecture_hall", "seminar_room", "lab", "office", "study_lounge",
        "restroom", "corridor", "stair", "elevator_lobby", "mep_room",
    ],
    code_refs=["IBC", "ADA", "ASHRAE-90.1", "campus-standards"],
    structural_hint="concrete_or_steel_frame",
    mep_hint="central_chilled_water",
    primitive_libraries=["walls", "openings", "roofs", "commercial", "institutional"],
    component_categories=[
        "IfcFurniture", "IfcWindow", "IfcDoor", "IfcStair",
        "IfcAirTerminal", "IfcSanitaryTerminal",
    ],
)

HEALTHCARE_CLINIC = Typology(
    key="healthcare.clinic",
    category="institutional",
    subtype="clinic",
    display_name="Outpatient clinic",
    aliases=["clinic", "doctor's office", "medical office", "outpatient"],
    description=(
        "Outpatient medical facility. Exam rooms, procedure rooms, waiting, "
        "reception, lab/imaging, staff areas."
    ),
    typical_program=[
        "exam_room", "procedure_room", "waiting_room", "reception",
        "lab", "imaging", "consultation", "nurse_station",
        "restroom", "soiled_utility", "clean_utility",
    ],
    code_refs=["IBC", "FGI-guidelines", "ADA", "HIPAA-physical"],
    structural_hint="steel_frame",
    mep_hint="medical_grade_with_pressure_zones",
    primitive_libraries=["walls", "openings", "roofs", "commercial", "healthcare"],
    component_categories=[
        "IfcFurniture", "IfcWindow", "IfcDoor", "IfcSanitaryTerminal",
        "IfcMedicalDevice", "IfcAirTerminal",
    ],
)

HEALTHCARE_HOSPITAL = Typology(
    key="healthcare.hospital",
    category="institutional",
    subtype="hospital",
    display_name="Hospital",
    aliases=["hospital", "medical center", "inpatient"],
    description=(
        "Acute-care hospital. Patient rooms, operating rooms, ICU, ED, "
        "imaging, lab, administration, support."
    ),
    typical_program=[
        "patient_room", "icu_bay", "or", "ed_bay", "imaging",
        "lab", "pharmacy", "nurse_station", "waiting", "lobby",
        "cafeteria", "kitchen", "restroom", "mechanical_room",
        "soiled_utility", "clean_utility", "med_gas",
    ],
    code_refs=["IBC", "FGI-guidelines", "ADA", "NFPA-99", "Joint-Commission"],
    structural_hint="concrete_or_steel_frame_with_seismic",
    mep_hint="central_redundant_with_medical_grade_air",
    primitive_libraries=["walls", "openings", "roofs", "commercial", "healthcare"],
    component_categories=[
        "IfcFurniture", "IfcWindow", "IfcDoor", "IfcSanitaryTerminal",
        "IfcMedicalDevice", "IfcAirTerminal", "IfcStair", "IfcElevator",
    ],
)

# ── Hospitality ─────────────────────────────────────────────────────────
HOSPITALITY_HOTEL = Typology(
    key="hospitality.hotel",
    category="hospitality",
    subtype="hotel",
    display_name="Hotel",
    aliases=["hotel", "motel", "inn", "resort"],
    description=(
        "Lodging facility. Guest rooms (mix of types), lobby, food service, "
        "meeting rooms, back-of-house, often pool/fitness."
    ),
    typical_program=[
        "guest_room", "suite", "lobby", "front_desk", "restaurant",
        "kitchen", "ballroom", "meeting_room", "fitness", "pool",
        "back_of_house", "stair", "elevator_lobby", "mechanical_room",
    ],
    code_refs=["IBC", "ADA", "fair-housing", "local-zoning"],
    structural_hint="concrete_or_wood_podium",
    mep_hint="ptac_or_fan_coil_per_room",
    primitive_libraries=["walls", "openings", "roofs", "commercial", "residential"],
    component_categories=[
        "IfcFurniture", "IfcSanitaryTerminal", "IfcWindow", "IfcDoor",
        "IfcStair", "IfcElevator", "IfcAirTerminal",
    ],
)

HOSPITALITY_RESTAURANT = Typology(
    key="hospitality.restaurant",
    category="hospitality",
    subtype="restaurant",
    display_name="Restaurant",
    aliases=["restaurant", "cafe", "bar", "diner"],
    description=(
        "Food-service establishment. Dining area, bar, kitchen, prep, "
        "storage, restrooms."
    ),
    typical_program=[
        "dining_room", "bar", "kitchen", "prep", "dishwash",
        "walk_in_cooler", "dry_storage", "restroom", "office",
    ],
    code_refs=["IBC", "ADA", "health-department", "local-zoning"],
    structural_hint="steel_frame_or_existing_shell",
    mep_hint="commercial_kitchen_hood_with_make_up_air",
    primitive_libraries=["walls", "openings", "roofs", "commercial"],
    component_categories=[
        "IfcFurniture", "IfcSanitaryTerminal", "IfcWindow", "IfcDoor",
        "IfcAirTerminal",
    ],
)

# ── Industrial ──────────────────────────────────────────────────────────
INDUSTRIAL_WAREHOUSE = Typology(
    key="industrial.warehouse",
    category="industrial",
    subtype="warehouse",
    display_name="Warehouse",
    aliases=["warehouse", "distribution center", "fulfillment center", "logistics"],
    description=(
        "Storage and distribution facility. Large clear-span main space, "
        "loading docks, small office, restrooms."
    ),
    typical_program=[
        "warehouse_floor", "loading_dock", "office", "restroom",
        "break_room", "battery_charging",
    ],
    code_refs=["IBC", "ADA", "OSHA", "local-zoning"],
    structural_hint="tilt_up_or_pemb_with_long_spans",
    mep_hint="unit_heaters_and_dock_doors",
    primitive_libraries=["walls", "openings", "roofs", "commercial", "industrial"],
    component_categories=[
        "IfcWindow", "IfcDoor", "IfcStair", "IfcAirTerminal",
    ],
)

INDUSTRIAL_MANUFACTURING = Typology(
    key="industrial.manufacturing",
    category="industrial",
    subtype="manufacturing",
    display_name="Manufacturing facility",
    aliases=["factory", "plant", "manufacturing", "production"],
    description=(
        "Light or heavy manufacturing facility. Production floor, "
        "process equipment areas, support spaces, MEP-intensive."
    ),
    typical_program=[
        "production_floor", "tool_room", "warehouse", "qa_lab",
        "office", "lunch_room", "locker_room", "restroom",
        "mep_room", "loading_dock",
    ],
    code_refs=["IBC", "ADA", "OSHA", "local-zoning", "EPA"],
    structural_hint="steel_frame_with_heavy_load_capacity",
    mep_hint="process_specific",
    primitive_libraries=["walls", "openings", "roofs", "commercial", "industrial"],
    component_categories=[
        "IfcWindow", "IfcDoor", "IfcStair", "IfcAirTerminal",
    ],
)

# ── Recreation ──────────────────────────────────────────────────────────
RECREATION_GYM = Typology(
    key="recreation.gym",
    category="recreation",
    subtype="gym",
    display_name="Gym / fitness center",
    aliases=["gym", "fitness center", "health club", "recreation center"],
    description=(
        "Fitness facility. Equipment floor, group exercise rooms, locker "
        "rooms, optional pool, optional courts (basketball, racquetball)."
    ),
    typical_program=[
        "equipment_floor", "group_fitness", "locker_room", "restroom",
        "pool", "basketball_court", "racquetball", "office", "reception",
    ],
    code_refs=["IBC", "ADA", "ASHRAE-90.1"],
    structural_hint="long_span_steel_for_courts",
    mep_hint="high_ventilation_with_pool_dehumidification",
    primitive_libraries=["walls", "openings", "roofs", "commercial", "recreation"],
    component_categories=[
        "IfcFurniture", "IfcSanitaryTerminal", "IfcWindow", "IfcDoor",
        "IfcAirTerminal",
    ],
)

# ── Mixed-use ───────────────────────────────────────────────────────────
MIXED_USE_GENERIC = Typology(
    key="mixed_use.generic",
    category="mixed_use",
    subtype="generic",
    display_name="Mixed-use building",
    aliases=["mixed use", "live work", "vertical mixed use"],
    description=(
        "Building with multiple program types stacked vertically or "
        "horizontally. Typical: retail/restaurant ground floor, office or "
        "residential above."
    ),
    typical_program=[
        # Mixed-use program is whatever the user describes; this is a hint list.
        "sales_floor", "lobby", "open_office", "unit",
        "stair", "elevator_lobby", "mechanical_room", "parking",
    ],
    code_refs=["IBC", "ADA", "local-zoning"],
    structural_hint="podium_concrete_with_wood_or_steel_above",
    mep_hint="separated_systems_per_use",
    primitive_libraries=["walls", "openings", "roofs", "commercial", "residential"],
    component_categories=[
        "IfcFurniture", "IfcSanitaryTerminal", "IfcWindow", "IfcDoor",
        "IfcCurtainWall", "IfcStair", "IfcElevator",
    ],
)


# ── Registry ────────────────────────────────────────────────────────────
ALL_TYPOLOGIES: list[Typology] = [
    RESIDENTIAL_SINGLE_FAMILY,
    RESIDENTIAL_MULTI_FAMILY,
    OFFICE_CLASS_A,
    OFFICE_SUBURBAN,
    RETAIL_STANDALONE,
    RETAIL_MIXED_USE_GROUND,
    EDUCATION_K12,
    EDUCATION_HIGHER_ED,
    HEALTHCARE_CLINIC,
    HEALTHCARE_HOSPITAL,
    HOSPITALITY_HOTEL,
    HOSPITALITY_RESTAURANT,
    INDUSTRIAL_WAREHOUSE,
    INDUSTRIAL_MANUFACTURING,
    RECREATION_GYM,
    MIXED_USE_GENERIC,
]

BY_KEY: dict[str, Typology] = {t.key: t for t in ALL_TYPOLOGIES}


def get(key: str) -> Optional[Typology]:
    """Look up a typology by canonical key. Returns None if unknown."""
    return BY_KEY.get(key)


def find_by_alias(text: str) -> Optional[Typology]:
    """
    Match user-provided text against typology aliases.

    This is a simple substring match — the Brief Agent does the real
    classification (LLM-driven). This function exists for tests and CLI
    invocation where you want a quick literal lookup.
    """
    text_lower = text.lower()
    for t in ALL_TYPOLOGIES:
        if text_lower == t.key:
            return t
        for alias in t.aliases:
            if alias in text_lower:
                return t
    return None
