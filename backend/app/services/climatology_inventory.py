"""Read-only metadata inventory for locally supplied IMD climatology NetCDFs."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

MONTHS = {name: number for number, name in enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1
)}
PATTERN = re.compile(r"^(rf_1deg|rf_p25|tmax_p5|tmin_p5|tmean_p5)_([a-z]{3})_clm(?: \(\d+\))?\.nc$", re.I)


def _value(value: Any) -> Any:
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace").rstrip("\x00")
    return value


def inspect_climatology_file(path: str | Path, root: str | Path) -> dict[str, Any]:
    """Inspect a classic NetCDF file without reading/copying its data arrays."""
    try:
        from scipy.io import netcdf_file
    except ImportError as exc:
        raise RuntimeError("Climatology inventory requires scipy") from exc
    path, root = Path(path), Path(root)
    match = PATTERN.match(path.name)
    if not match:
        raise ValueError(f"unrecognized IMD climatology filename: {path.name}")
    product, month_name = match.groups()
    with netcdf_file(path, "r", mmap=False) as nc:
        variables = {}
        for name, variable in nc.variables.items():
            attrs = {key: _value(value) for key, value in variable._attributes.items()}
            variables[name] = {"dimensions": list(variable.dimensions), "shape": list(variable.shape),
                               "dtype": variable.typecode(), "attributes": attrs}
        lat = nc.variables.get("lat")
        lon = nc.variables.get("lon")
        if lat is None or lon is None:
            raise ValueError(f"{path.name} has no lat/lon coordinate variables")
        latitudes, longitudes = lat[:].copy(), lon[:].copy()
        from app.services.historical_data import select_nearest_grid_point
        dhule_point = select_nearest_grid_point(20.90, 74.80,
            ((float(y), float(x)) for y in latitudes for x in longitudes))
        data_names = [n for n in variables if n.casefold() not in {"lat", "lon", "time"}]
        if len(data_names) != 1:
            raise ValueError(f"{path.name} expected one data variable; found {data_names}")
        name = data_names[0]
        attrs = variables[name]["attributes"]
        coordinate_info = lambda values: {
            "minimum": float(values.min()), "maximum": float(values.max()), "count": int(values.size),
            "step_degrees": float(abs(values[1] - values[0])) if values.size > 1 else None,
            "ordering": "ascending" if values.size < 2 or values[-1] > values[0] else "descending",
        }
        dims = {str(key): (None if value is None else int(value)) for key, value in nc.dimensions.items()}
        global_attrs = {key: _value(value) for key, value in nc._attributes.items()}
    source_attrs = {key: value for key, value in attrs.items()
                    if key in {"history", "info", "NCL_tag", "time_op_ncl"}}
    reported_month = attrs.get("month")
    return {
        "filename": path.name, "path": path.relative_to(root).as_posix(), "size_bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "parameter": {"rf": "rainfall", "tmax": "maximum_temperature", "tmin": "minimum_temperature",
                      "tmean": "mean_temperature"}[name.casefold()],
        "product_code": product, "month": month_name.lower(), "month_number": MONTHS[month_name.lower()],
        "file_month_attribute_zero_based": reported_month,
        "month_attribute_matches_filename": reported_month == MONTHS[month_name.lower()] - 1,
        "climatology_period": "30 years (exact start/end years not encoded)",
        "resolution_degrees": coordinate_info(longitudes).get("step_degrees"),
        "units": attrs.get("units"), "variable_names": list(variables), "data_variable": name,
        "data_dimensions": variables[name]["dimensions"], "data_shape": variables[name]["shape"],
        "netcdf_dimensions": dims, "latitude": coordinate_info(latitudes), "longitude": coordinate_info(longitudes),
        "missing_value": attrs.get("missing_value", attrs.get("_FillValue")),
        "fill_value": attrs.get("_FillValue"), "variable_attributes": attrs,
        "global_attributes": global_attrs, "source_provenance_attributes": source_attrs,
        "source_provenance": source_attrs.get("history", "No source/provenance string encoded in file"),
        "dhule_reference_selection": {"requested_latitude": 20.90, "requested_longitude": 74.80,
            "grid_latitude": dhule_point.grid_latitude, "grid_longitude": dhule_point.grid_longitude,
            "distance_km": round(dhule_point.distance_km, 3)},
        "format": "NetCDF classic (CDF-1)" if path.read_bytes()[:4] == b"CDF\x01" else "NetCDF (signature not CDF-1)",
    }


def build_climatology_inventory(root: str | Path) -> dict[str, Any]:
    """Inventory all recognized NetCDF files and report month completeness."""
    root = Path(root)
    entries = [inspect_climatology_file(path, root) for path in sorted(root.rglob("*.nc"))]
    groups: dict[str, set[str]] = {}
    for row in entries:
        key = f"{row['parameter']} ({row['resolution_degrees']} degree)"
        groups.setdefault(key, set()).add(row["month"])
    completeness = {key: {"available_months": sorted(months, key=MONTHS.get),
                          "missing_months": [m for m in MONTHS if m not in months],
                          "unique_month_count": len(months)} for key, months in sorted(groups.items())}
    return {"catalog_title": "Locally supplied IMD gridded climatology metadata inventory",
            "inspection_is_metadata_only": True,
            "period_note": "The files declare a 30-year climatology; exact baseline years are not encoded in inspected metadata.",
            "file_count": len(entries), "month_completeness": completeness, "files": entries}


def write_climatology_catalog(root: str | Path, output: str | Path) -> dict[str, Any]:
    inventory = build_climatology_inventory(root)
    Path(output).write_text(json.dumps(inventory, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return inventory
