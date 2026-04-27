"""
library.transplant — copy real IFC geometry from library files into target builds.

Ported from BIM Studio's extractor/geometry_transplant.py. The port includes
fixes that BIM Studio shipped without:

  1. Axis-convention normalization. Source IFCs may store geometry y-up
     instead of z-up. We detect the source's WorldCoordinateSystem and
     bake a normalization rotation into the MappingTarget so transplanted
     geometry arrives consistently z-up.

  2. No more hardcoded fixture-rotation hacks. BIM Studio had a literal
     `if "toilet" in name: rotate -90 around X` in generate.py that
     papered over inconsistent source files. With axis-convention fix
     in place, those hacks are unnecessary and would actually be wrong
     for files that store toilets correctly oriented.

  3. Best-effort behavior. The transplant returns None on failure rather
     than raising — the renderer falls back to procedural primitives,
     consistent with the platform's "always try" philosophy.
"""
from __future__ import annotations
import os
import logging
import math
from typing import Any

import psycopg2.extras
import ifcopenshell
import ifcopenshell.util.element
import ifcopenshell.util.unit
import ifcopenshell.util.placement

from .db import get_db_connection

logger = logging.getLogger(__name__)


# Synonym tables — extends the user's "Sofa" or "Stove" to the actual
# IFC family names the source files use.
SEARCH_SYNONYMS: dict[str, list[str]] = {
    "toilet":        ["toilet","wc","water closet","sanitary","lavatory","commode"],
    "sink":          ["sink","basin","washbasin","lavatory","wash hand"],
    "shower":        ["shower","shower tray"],
    "bath":          ["bath","bathtub","tub"],
    "fridge":        ["fridge","refrigerator","refrigeration"],
    "refrigerator":  ["refrigerator","fridge"],
    "sofa":          ["sofa","couch","settee"],
    "couch":         ["couch","sofa","settee"],
    "coffee table":  ["coffee table","center table","cocktail table"],
    "dining table":  ["dining table","table - dining","dining"],
    "table":         ["table","desk","worktop","counter"],
    "chair":         ["chair","seat","stool"],
    "bed":           ["bed","bed-standard","bunk","mattress"],
    "wardrobe":      ["wardrobe","closet","cupboard","cabinet","armoire"],
    "nightstand":    ["nightstand","night stand","bedside","side table"],
    "door":          ["door","single-flush","doors_intsgl","doors_extdbl"],
    "window":        ["window","glazing","glass"],
    "light":         ["light","lamp","luminaire","fixture","downlight"],
    "stove":         ["stove","oven","cooker","hob","range"],
    "washer":        ["washer","washing machine","laundry"],
    "tv unit":       ["tv","television","media","cabinet 1"],
    "lower cabinets":["cabinet","base cabinet","lower cabinet","kitchen island"],
    "upper cabinets":["cabinet","upper cabinet","wall cabinet"],
    "desk":          ["desk","work table","writing table"],
    "water heater":  ["water heater","boiler","hot water","geyser"],
    # Commercial additions
    "workstation":   ["workstation","desk","cubicle","systems furniture"],
    "conference table": ["conference table","meeting table","table - conference"],
    "filing cabinet":["filing cabinet","file cabinet","lateral file"],
    "elevator":      ["elevator","lift"],
}

RELATED_CATEGORIES: dict[str, set[str]] = {
    "IfcFurniture":          {"IfcFurniture", "IfcFurnishingElement"},
    "IfcFurnishingElement":  {"IfcFurniture", "IfcFurnishingElement"},
    "IfcSanitaryTerminal":   {"IfcSanitaryTerminal", "IfcFurnishingElement", "IfcFlowTerminal"},
    "IfcElectricAppliance":  {"IfcElectricAppliance", "IfcFurnishingElement", "IfcFlowTerminal"},
    "IfcLightFixture":       {"IfcLightFixture", "IfcFlowTerminal"},
    "IfcDoor":               {"IfcDoor"},
    "IfcWindow":             {"IfcWindow"},
    "IfcCurtainWall":        {"IfcCurtainWall"},
    "IfcStair":              {"IfcStair", "IfcStairFlight"},
    "IfcAirTerminal":        {"IfcAirTerminal", "IfcFlowTerminal"},
}


class GeometryLibrary:
    """
    Search + transplant interface over the postgres component index.

    Construct with a path to the uploaded-IFCs folder. Methods are stateful
    (the postgres index is loaded lazily, IFC files are cached after first
    open) but the class is safe for single-threaded use.
    """

    def __init__(self, upload_folder: str):
        self._upload_folder = upload_folder
        self._ifc_cache: dict[str, Any] = {}           # filename -> ifcopenshell model
        self._unit_scale_cache: dict[str, float] = {}  # filename -> unit scale
        self._axis_conv_cache: dict[str, str] = {}     # filename -> "z_up" | "y_up"
        self._match_cache: dict[tuple, dict | None] = {}
        self._component_index: list[dict] | None = None

    # ── component search ────────────────────────────────────────────────

    def _load_component_index(self) -> None:
        if self._component_index is not None:
            return
        with get_db_connection(cursor_factory=psycopg2.extras.RealDictCursor) as (conn, cur):
            cur.execute("""
                SELECT c.id, c.category, c.family_name, c.type_name, c.revit_id,
                       c.width_mm, c.height_mm, c.length_mm, c.quality_score,
                       c.parameters,
                       p.filename
                FROM components c
                JOIN projects p ON p.id = c.project_id
                WHERE p.status = 'done'
                  AND c.revit_id IS NOT NULL
                  AND p.filename NOT LIKE 'generated_%%'
                ORDER BY c.quality_score DESC NULLS LAST
            """)
            self._component_index = cur.fetchall()
        logger.info("Loaded %d real components", len(self._component_index))

    def find_component(
        self, name: str, category: str | None = None,
        target_w: float | None = None, target_d: float | None = None,
        target_h: float | None = None,
    ) -> dict | None:
        """
        Best-effort match for the named component. Returns None if no match
        — caller should fall back to procedural primitives.
        """
        cache_key = (name.lower(), category)
        if cache_key in self._match_cache:
            return self._match_cache[cache_key]

        self._load_component_index()

        name_lower = name.lower()
        terms = {name_lower}
        for key, syns in SEARCH_SYNONYMS.items():
            if name_lower == key or name_lower in syns:
                terms.update(syns)
                terms.add(key)

        allowed_cats = RELATED_CATEGORIES.get(category, {category} if category else None)

        best: dict | None = None
        best_score = -1.0

        for comp in self._component_index or []:
            if allowed_cats and comp["category"] not in allowed_cats:
                continue

            comp_name = (comp["family_name"] or "").lower()
            comp_type = (comp["type_name"] or "").lower()

            score = 0.0
            name_matched = False
            for term in terms:
                if term in comp_name or term in comp_type:
                    score += 10
                    if term == comp_name or term == comp_type:
                        score += 5
                    score += min(len(term), 5)
                    name_matched = True
                    break
            if not name_matched:
                continue

            if comp.get("quality_score"):
                score += float(comp["quality_score"]) * 3
            if target_w and comp.get("width_mm"):
                ratio = min(target_w * 1000, comp["width_mm"]) / max(target_w * 1000, comp["width_mm"])
                score += ratio * 2
            if target_h and comp.get("height_mm"):
                ratio = min(target_h * 1000, comp["height_mm"]) / max(target_h * 1000, comp["height_mm"])
                score += ratio * 2

            filepath = os.path.join(self._upload_folder, comp["filename"])
            if not os.path.exists(filepath):
                continue

            if score > best_score:
                best_score = score
                best = comp

        self._match_cache[cache_key] = best
        if best:
            logger.info(
                "MATCH '%s' -> %s [%s] from %s (score=%.0f)",
                name, (best["family_name"] or "?")[:50], best["category"],
                best["filename"], best_score,
            )
        else:
            logger.info("NO MATCH for '%s' (category=%s)", name, category)
        return best

    # ── source IFC access ───────────────────────────────────────────────

    def _open_ifc(self, filename: str):
        if filename in self._ifc_cache:
            return self._ifc_cache[filename]
        filepath = os.path.join(self._upload_folder, filename)
        if not os.path.exists(filepath):
            return None
        try:
            model = ifcopenshell.open(filepath)
            self._ifc_cache[filename] = model
            try:
                self._unit_scale_cache[filename] = ifcopenshell.util.unit.calculate_unit_scale(model)
            except Exception:
                self._unit_scale_cache[filename] = 1.0
            self._axis_conv_cache[filename] = self._detect_axis_convention(model)
            return model
        except Exception as e:
            logger.error("Failed to open %s: %s", filename, e)
            return None

    def _detect_axis_convention(self, model) -> str:
        """
        Detect z-up vs y-up convention. Most IFC4 files are z-up; older or
        Maya-exported files may be y-up.
        """
        try:
            for ctx in model.by_type("IfcGeometricRepresentationContext"):
                if ctx.is_a("IfcGeometricRepresentationSubContext"):
                    continue
                wcs = getattr(ctx, "WorldCoordinateSystem", None)
                if wcs and getattr(wcs, "Axis", None):
                    axis_dir = wcs.Axis.DirectionRatios
                    if abs(axis_dir[2]) < 0.5:
                        return "y_up"
        except Exception:
            pass
        return "z_up"

    def _get_unit_factor(self, source_filename: str, target_model) -> float:
        src_scale = self._unit_scale_cache.get(source_filename, 1.0)
        try:
            tgt_scale = ifcopenshell.util.unit.calculate_unit_scale(target_model)
        except Exception:
            tgt_scale = 1.0
        if tgt_scale == 0:
            tgt_scale = 1.0
        return src_scale / tgt_scale

    def _find_element(self, model, revit_id: str, category: str):
        try:
            return model.by_guid(revit_id)
        except Exception:
            pass
        try:
            for el in model.by_type(category):
                if el.GlobalId == revit_id:
                    return el
        except Exception:
            pass
        return None

    # ── transplant ──────────────────────────────────────────────────────

    def transplant_geometry(self, target_model, source_component: dict, body_ctx):
        """
        Copy source component's geometry into target_model. Returns an
        IfcProductDefinitionShape, or None if anything goes wrong (caller
        should fall back to procedural primitive).
        """
        if not source_component:
            return None

        source_model = self._open_ifc(source_component["filename"])
        if not source_model:
            return None

        source_element = self._find_element(
            source_model, source_component["revit_id"], source_component["category"],
        )
        if not source_element or not source_element.Representation:
            return None

        unit_factor = self._get_unit_factor(source_component["filename"], target_model)
        axis_conv = self._axis_conv_cache.get(source_component["filename"], "z_up")

        try:
            return self._copy_geometry(
                target_model, source_element, body_ctx,
                unit_factor=unit_factor, axis_conv=axis_conv,
            )
        except Exception as e:
            logger.warning(
                "Transplant failed for %s: %s",
                source_component.get("family_name", "?"), e,
            )
            return None

    def _copy_geometry(
        self, target, source_element, body_ctx,
        unit_factor: float = 1.0, axis_conv: str = "z_up",
    ):
        """
        1. copy_deep each Body representation item (excluding context refs)
        2. Remap dangling context references
        3. Wrap in MappedItem with:
           - axis-convention rotation (y_up → z_up if needed)
           - unit scale factor
        """
        source_rep = source_element.Representation
        copied_items = []

        for rep in source_rep.Representations:
            rep_id = rep.RepresentationIdentifier or ""
            if rep_id not in ("Body", "body", ""):
                continue
            for item in rep.Items:
                try:
                    copied = ifcopenshell.util.element.copy_deep(
                        target, item,
                        exclude=["IfcGeometricRepresentationContext",
                                 "IfcGeometricRepresentationSubContext"],
                    )
                    self._remap_contexts(copied, body_ctx)
                    copied_items.append(copied)
                except Exception as e:
                    logger.debug("Failed copy %s: %s", item.is_a(), e)

        if not copied_items:
            return None

        inner_rep = target.createIfcShapeRepresentation(
            body_ctx, "Body", "SweptSolid", copied_items,
        )

        origin = target.createIfcCartesianPoint((0.0, 0.0, 0.0))
        map_origin = target.createIfcAxis2Placement3D(origin, None, None)
        rep_map = target.createIfcRepresentationMap(map_origin, inner_rep)

        # Build the MappingTarget transform.
        # If source is y-up, rotate so that Y_source becomes Z_target.
        needs_rotation = axis_conv == "y_up"
        needs_scale = abs(unit_factor - 1.0) > 1e-6

        if needs_rotation:
            # Y becomes Z, Z becomes -Y. Right-handed.
            axis1 = target.createIfcDirection((1.0, 0.0, 0.0))
            axis2 = target.createIfcDirection((0.0, 0.0, 1.0))
            mapping_target = target.createIfcCartesianTransformationOperator3D(
                axis1, axis2, origin, unit_factor, None,
            )
        elif needs_scale:
            mapping_target = target.createIfcCartesianTransformationOperator3D(
                None, None, origin, unit_factor, None,
            )
        else:
            mapping_target = target.createIfcCartesianTransformationOperator3D(
                None, None, origin, 1.0, None,
            )

        mapped_item = target.createIfcMappedItem(rep_map, mapping_target)
        outer_rep = target.createIfcShapeRepresentation(
            body_ctx, "Body", "MappedRepresentation", [mapped_item],
        )
        return target.createIfcProductDefinitionShape(None, None, [outer_rep])

    def _remap_contexts(self, entity, body_ctx) -> None:
        if entity is None:
            return
        if entity.is_a("IfcMappedItem"):
            try:
                mapped_rep = entity.MappingSource.MappedRepresentation
                if mapped_rep and hasattr(mapped_rep, "ContextOfItems"):
                    mapped_rep.ContextOfItems = body_ctx
            except Exception:
                pass
        if hasattr(entity, "ContextOfItems"):
            try:
                entity.ContextOfItems = body_ctx
            except Exception:
                pass

    def transplant_materials(
        self, target_model, ifcopenshell_api, target_element, source_component,
    ) -> None:
        """
        Copy material associations from source to target. Best-effort; a
        material-less element renders with the default color from palette.
        """
        if not source_component:
            return
        source_model = self._open_ifc(source_component["filename"])
        if not source_model:
            return
        source_element = self._find_element(
            source_model, source_component["revit_id"], source_component["category"],
        )
        if not source_element:
            return
        try:
            for rel in getattr(source_element, "HasAssociations", []) or []:
                if rel.is_a("IfcRelAssociatesMaterial"):
                    try:
                        copied_mat = ifcopenshell.util.element.copy_deep(
                            target_model, rel.RelatingMaterial,
                            exclude=["IfcGeometricRepresentationContext",
                                     "IfcGeometricRepresentationSubContext"],
                        )
                        target_model.createIfcRelAssociatesMaterial(
                            ifcopenshell.guid.new(), ifcopenshell_api, None, None,
                            [target_element], copied_mat,
                        )
                    except Exception:
                        pass
                    return
        except Exception:
            pass

    def clear_cache(self) -> None:
        """Free cached IFC models. Call between large batch operations."""
        self._ifc_cache.clear()
        self._unit_scale_cache.clear()
        self._axis_conv_cache.clear()
        self._match_cache.clear()
        self._component_index = None
