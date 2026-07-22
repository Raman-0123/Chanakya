"""Satellite imagery layer config — NASA GIBS (keyless).

Serves Leaflet-ready XYZ tile templates for NASA's Global Imagery Browse
Services: daily true-colour Earth imagery plus a thermal/active-fire overlay,
all free and key-less. The frontend map renders these directly over the digital
twin so corridors, ports and FIRMS detections sit on real satellite imagery.

GIBS "best" imagery is ~1 day latent, so the default date is yesterday (UTC); a
`?date=YYYY-MM-DD` query overrides it for time-slider / playback use.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query

router = APIRouter(prefix="/satellite", tags=["satellite"])

_GIBS = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best"
_ATTR = "Imagery courtesy NASA EOSDIS GIBS"

# id, GIBS layer, TileMatrixSet, ext, role, native zoom, temporal?, label
_LAYERS = [
    # --- base imagery (mutually exclusive) ---
    {"id": "viirs_snpp_truecolor", "gibs": "VIIRS_SNPP_CorrectedReflectance_TrueColor",
     "matrix": "GoogleMapsCompatible_Level9", "ext": "jpg", "kind": "base",
     "max_native_zoom": 9, "temporal": True, "label": "VIIRS SNPP — True Color (daily)"},
    {"id": "viirs_noaa20_truecolor", "gibs": "VIIRS_NOAA20_CorrectedReflectance_TrueColor",
     "matrix": "GoogleMapsCompatible_Level9", "ext": "jpg", "kind": "base",
     "max_native_zoom": 9, "temporal": True, "label": "VIIRS NOAA-20 — True Color (daily)"},
    {"id": "modis_terra_truecolor", "gibs": "MODIS_Terra_CorrectedReflectance_TrueColor",
     "matrix": "GoogleMapsCompatible_Level9", "ext": "jpg", "kind": "base",
     "max_native_zoom": 9, "temporal": True, "label": "MODIS Terra — True Color (daily, AM)"},
    {"id": "modis_aqua_truecolor", "gibs": "MODIS_Aqua_CorrectedReflectance_TrueColor",
     "matrix": "GoogleMapsCompatible_Level9", "ext": "jpg", "kind": "base",
     "max_native_zoom": 9, "temporal": True, "label": "MODIS Aqua — True Color (daily, PM)"},
    {"id": "viirs_bands721", "gibs": "VIIRS_SNPP_CorrectedReflectance_BandsM11-I2-I1",
     "matrix": "GoogleMapsCompatible_Level9", "ext": "jpg", "kind": "base",
     "max_native_zoom": 9, "temporal": True,
     "label": "VIIRS — False Color (M11-I2-I1: fire/veg)"},
    {"id": "blue_marble", "gibs": "BlueMarble_ShadedRelief_Bathymetry",
     "matrix": "GoogleMapsCompatible_Level8", "ext": "jpeg", "kind": "base",
     "max_native_zoom": 8, "temporal": False, "label": "Blue Marble (cloud-free relief)"},
    {"id": "night_lights", "gibs": "VIIRS_Black_Marble",
     "matrix": "GoogleMapsCompatible_Level8", "ext": "png", "kind": "base",
     "max_native_zoom": 8, "temporal": False, "label": "Night Lights (Black Marble)"},
    # --- overlays (toggleable; active-fire is served separately as FIRMS points) ---
    {"id": "coastlines", "gibs": "Coastlines_15m",
     "matrix": "GoogleMapsCompatible_Level13", "ext": "png", "kind": "overlay",
     "max_native_zoom": 13, "temporal": False, "label": "Coastlines"},
    {"id": "reference_labels", "gibs": "Reference_Labels_15m",
     "matrix": "GoogleMapsCompatible_Level13", "ext": "png", "kind": "overlay",
     "max_native_zoom": 13, "temporal": False, "label": "Place Labels"},
]


def _url(layer: dict, date: str) -> str:
    # {z}/{y}/{x} stay as Leaflet placeholders; layer/date/matrix are baked in.
    # Static (non-temporal) layers have no {time} segment in the GIBS path.
    time_seg = f"default/{date}" if layer.get("temporal") else "default"
    return (f"{_GIBS}/{layer['gibs']}/{time_seg}/{layer['matrix']}"
            "/{z}/{y}/{x}." + layer["ext"])


@router.get("/layers")
async def satellite_layers(
    date: str | None = Query(default=None, description="Imagery date YYYY-MM-DD (default: yesterday UTC)"),
) -> dict:
    """Leaflet-ready NASA GIBS tile layers over the region of interest."""
    d = date or (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
    return {
        "provider": "NASA EOSDIS GIBS",
        "keyless": True,
        "date": d,
        "attribution": _ATTR,
        "layers": [
            {"id": layer["id"], "label": layer["label"], "kind": layer["kind"],
             "max_native_zoom": layer["max_native_zoom"], "ext": layer["ext"],
             "temporal": layer.get("temporal", True),
             "url_template": _url(layer, d)}
            for layer in _LAYERS
        ],
    }
