"""Seeded digital twin of India's crude-oil supply chain.

Figures are public, order-of-magnitude-accurate 2024–2026 values used as the
simulation baseline. They are assumptions, deliberately centralised here so they
can be audited or swapped for live data without touching the engine.
"""

from __future__ import annotations

from app.domain.entities import (
    Coast,
    CrudeGrade,
    DemandProfile,
    EnergyNetwork,
    GeoPoint,
    MarketState,
    Port,
    Refinery,
    ShippingCorridor,
    StrategicReserveSite,
    Supplier,
)


def _corridors() -> list[ShippingCorridor]:
    return [
        ShippingCorridor(
            id="hormuz",
            name="Strait of Hormuz",
            chokepoint="Strait of Hormuz",
            import_share=0.46,
            base_transit_days=11,
            # Gulf crude has no maritime bypass — closure forces supplier switch
            reroute_corridor_id=None,
            reroute_added_days=0,
            reroute_cost_premium_pct=0,
            # Gulf load points → Hormuz chokepoint → Arabian Sea → India west coast
            path=[GeoPoint(lat=29.4, lon=48.9), GeoPoint(lat=26.57, lon=56.25),
                  GeoPoint(lat=25.0, lon=57.8), GeoPoint(lat=22.5, lon=61.5),
                  GeoPoint(lat=20.5, lon=66.0), GeoPoint(lat=18.9, lon=71.0)],
            chokepoint_coords=GeoPoint(lat=26.57, lon=56.25),
        ),
        ShippingCorridor(
            id="red_sea",
            name="Red Sea – Suez Corridor",
            chokepoint="Bab-el-Mandeb / Suez",
            import_share=0.34,
            base_transit_days=18,
            reroute_corridor_id="cape",
            reroute_added_days=14,
            reroute_cost_premium_pct=38,
            # Suez → Red Sea → Bab-el-Mandeb → Gulf of Aden → Arabian Sea → India
            path=[GeoPoint(lat=30.0, lon=32.5), GeoPoint(lat=27.0, lon=34.5),
                  GeoPoint(lat=20.0, lon=38.5), GeoPoint(lat=12.6, lon=43.3),
                  GeoPoint(lat=12.5, lon=51.0), GeoPoint(lat=15.0, lon=62.0),
                  GeoPoint(lat=18.9, lon=71.0)],
            chokepoint_coords=GeoPoint(lat=12.6, lon=43.3),
        ),
        ShippingCorridor(
            id="cape",
            name="Cape of Good Hope",
            chokepoint="None (open ocean fallback)",
            import_share=0.15,
            base_transit_days=32,
            reroute_corridor_id=None,
            path=[GeoPoint(lat=6.0, lon=3.5), GeoPoint(lat=-25.0, lon=14.0),
                  GeoPoint(lat=-34.83, lon=19.6), GeoPoint(lat=-30.0, lon=35.0),
                  GeoPoint(lat=-10.0, lon=55.0), GeoPoint(lat=8.0, lon=68.0),
                  GeoPoint(lat=15.0, lon=72.0)],
            chokepoint_coords=GeoPoint(lat=-34.83, lon=19.6),
        ),
        ShippingCorridor(
            id="malacca",
            name="Strait of Malacca",
            chokepoint="Strait of Malacca",
            import_share=0.05,
            base_transit_days=14,
            reroute_corridor_id=None,
            reroute_added_days=6,
            reroute_cost_premium_pct=12,
            path=[GeoPoint(lat=1.4, lon=103.8), GeoPoint(lat=3.0, lon=99.5),
                  GeoPoint(lat=6.0, lon=95.0), GeoPoint(lat=9.0, lon=88.0),
                  GeoPoint(lat=13.0, lon=80.3)],
            chokepoint_coords=GeoPoint(lat=1.9, lon=101.3),
        ),
    ]


def _suppliers() -> list[Supplier]:
    return [
        # spare_capacity = volume genuinely redirectable to India within the
        # disruption window (short-notice deliverable, not headline spare).
        Supplier(id="russia", country="Russia", import_share=0.36,
                 grade=CrudeGrade.MEDIUM_SOUR, corridor_id="red_sea",
                 reliability=58, spare_capacity_kbpd=220, spot_premium_usd=3.5,
                 coords=GeoPoint(lat=61.5, lon=105.3)),
        Supplier(id="iraq", country="Iraq", import_share=0.20,
                 grade=CrudeGrade.MEDIUM_SOUR, corridor_id="hormuz",
                 reliability=64, spare_capacity_kbpd=140, spot_premium_usd=2.1,
                 coords=GeoPoint(lat=33.2, lon=43.7)),
        Supplier(id="saudi", country="Saudi Arabia", import_share=0.13,
                 grade=CrudeGrade.HEAVY_SOUR, corridor_id="hormuz",
                 reliability=78, spare_capacity_kbpd=900, spot_premium_usd=1.8,
                 coords=GeoPoint(lat=24.0, lon=45.0)),
        Supplier(id="uae", country="United Arab Emirates", import_share=0.09,
                 grade=CrudeGrade.LIGHT_SWEET, corridor_id="hormuz",
                 reliability=80, spare_capacity_kbpd=350, spot_premium_usd=1.9,
                 coords=GeoPoint(lat=24.0, lon=54.0)),
        Supplier(id="usa", country="United States", import_share=0.06,
                 grade=CrudeGrade.LIGHT_SWEET, corridor_id="cape",
                 reliability=82, spare_capacity_kbpd=260, spot_premium_usd=2.8,
                 coords=GeoPoint(lat=29.0, lon=-93.5)),
        Supplier(id="nigeria", country="Nigeria", import_share=0.05,
                 grade=CrudeGrade.LIGHT_SWEET, corridor_id="cape",
                 reliability=61, spare_capacity_kbpd=90, spot_premium_usd=2.4,
                 coords=GeoPoint(lat=5.5, lon=6.5)),
        Supplier(id="kuwait", country="Kuwait", import_share=0.04,
                 grade=CrudeGrade.MEDIUM_SOUR, corridor_id="hormuz",
                 reliability=76, spare_capacity_kbpd=120, spot_premium_usd=1.7,
                 coords=GeoPoint(lat=29.3, lon=47.7)),
        Supplier(id="brazil", country="Brazil", import_share=0.04,
                 grade=CrudeGrade.MEDIUM_SOUR, corridor_id="cape",
                 reliability=74, spare_capacity_kbpd=110, spot_premium_usd=2.6,
                 coords=GeoPoint(lat=-14.2, lon=-45.0)),
        Supplier(id="others", country="Other / Spot", import_share=0.03,
                 grade=CrudeGrade.MEDIUM_SOUR, corridor_id="malacca",
                 reliability=55, spare_capacity_kbpd=80, spot_premium_usd=4.0,
                 coords=GeoPoint(lat=10.0, lon=95.0)),
    ]


def _ports() -> list[Port]:
    return [
        Port(id="vadinar", name="Vadinar / Sikka (Gujarat)", coast=Coast.WEST,
             coords=GeoPoint(lat=22.28, lon=69.72), crude_capacity_kbpd=1600),
        Port(id="mumbai", name="Mumbai / JNPT", coast=Coast.WEST,
             coords=GeoPoint(lat=18.95, lon=72.85), crude_capacity_kbpd=600),
        Port(id="mangalore", name="New Mangalore", coast=Coast.WEST,
             coords=GeoPoint(lat=12.92, lon=74.80), crude_capacity_kbpd=500),
        Port(id="kochi", name="Kochi", coast=Coast.WEST,
             coords=GeoPoint(lat=9.97, lon=76.24), crude_capacity_kbpd=400),
        Port(id="paradip", name="Paradip", coast=Coast.EAST,
             coords=GeoPoint(lat=20.27, lon=86.67), crude_capacity_kbpd=450),
        Port(id="vizag", name="Visakhapatnam", coast=Coast.EAST,
             coords=GeoPoint(lat=17.69, lon=83.22), crude_capacity_kbpd=350),
        Port(id="chennai", name="Chennai", coast=Coast.EAST,
             coords=GeoPoint(lat=13.08, lon=80.29), crude_capacity_kbpd=300),
    ]


def _refineries() -> list[Refinery]:
    return [
        Refinery(id="jamnagar", name="Jamnagar", operator="Reliance Industries",
                 coords=GeoPoint(lat=22.35, lon=70.05), coast=Coast.WEST,
                 nameplate_kbpd=1240, throughput_kbpd=1190,
                 preferred_grade=CrudeGrade.HEAVY_SOUR, port_ids=["vadinar"],
                 inventory_days=12),
        Refinery(id="vadinar_ref", name="Vadinar", operator="Nayara Energy",
                 coords=GeoPoint(lat=22.24, lon=69.75), coast=Coast.WEST,
                 nameplate_kbpd=405, throughput_kbpd=390,
                 preferred_grade=CrudeGrade.MEDIUM_SOUR, port_ids=["vadinar"],
                 inventory_days=10),
        Refinery(id="mangalore_ref", name="Mangalore (MRPL)", operator="MRPL / ONGC",
                 coords=GeoPoint(lat=12.95, lon=74.86), coast=Coast.WEST,
                 nameplate_kbpd=300, throughput_kbpd=282,
                 preferred_grade=CrudeGrade.MEDIUM_SOUR, port_ids=["mangalore"],
                 inventory_days=9),
        Refinery(id="kochi_ref", name="Kochi", operator="BPCL",
                 coords=GeoPoint(lat=9.97, lon=76.28), coast=Coast.WEST,
                 nameplate_kbpd=310, throughput_kbpd=298,
                 preferred_grade=CrudeGrade.MEDIUM_SOUR, port_ids=["kochi"],
                 inventory_days=11),
        Refinery(id="mumbai_ref", name="Mumbai (BPCL+HPCL)", operator="BPCL / HPCL",
                 coords=GeoPoint(lat=19.00, lon=72.86), coast=Coast.WEST,
                 nameplate_kbpd=250, throughput_kbpd=240,
                 preferred_grade=CrudeGrade.MEDIUM_SOUR, port_ids=["mumbai"],
                 inventory_days=8),
        Refinery(id="paradip_ref", name="Paradip", operator="IOCL",
                 coords=GeoPoint(lat=20.29, lon=86.61), coast=Coast.EAST,
                 nameplate_kbpd=300, throughput_kbpd=285,
                 preferred_grade=CrudeGrade.HEAVY_SOUR, port_ids=["paradip"],
                 inventory_days=10),
        Refinery(id="vizag_ref", name="Visakhapatnam", operator="HPCL",
                 coords=GeoPoint(lat=17.68, lon=83.20), coast=Coast.EAST,
                 nameplate_kbpd=300, throughput_kbpd=250,
                 preferred_grade=CrudeGrade.MEDIUM_SOUR, port_ids=["vizag"],
                 inventory_days=9),
        Refinery(id="chennai_ref", name="Chennai (CPCL)", operator="CPCL / IOCL",
                 coords=GeoPoint(lat=13.12, lon=80.24), coast=Coast.EAST,
                 nameplate_kbpd=230, throughput_kbpd=215,
                 preferred_grade=CrudeGrade.MEDIUM_SOUR, port_ids=["chennai"],
                 inventory_days=8),
        # Inland refineries — fed by pipeline from western terminals.
        Refinery(id="panipat_ref", name="Panipat", operator="IOCL",
                 coords=GeoPoint(lat=29.39, lon=76.97), coast=Coast.WEST,
                 nameplate_kbpd=300, throughput_kbpd=288,
                 preferred_grade=CrudeGrade.MEDIUM_SOUR, port_ids=["vadinar"],
                 inventory_days=7),
        Refinery(id="koyali_ref", name="Koyali (Gujarat)", operator="IOCL",
                 coords=GeoPoint(lat=22.42, lon=73.13), coast=Coast.WEST,
                 nameplate_kbpd=275, throughput_kbpd=262,
                 preferred_grade=CrudeGrade.MEDIUM_SOUR, port_ids=["vadinar"],
                 inventory_days=8),
        Refinery(id="bina_ref", name="Bina (BORL)", operator="BPCL",
                 coords=GeoPoint(lat=24.18, lon=78.20), coast=Coast.WEST,
                 nameplate_kbpd=156, throughput_kbpd=148,
                 preferred_grade=CrudeGrade.MEDIUM_SOUR, port_ids=["vadinar"],
                 inventory_days=7),
        Refinery(id="mathura_ref", name="Mathura", operator="IOCL",
                 coords=GeoPoint(lat=27.49, lon=77.67), coast=Coast.WEST,
                 nameplate_kbpd=168, throughput_kbpd=160,
                 preferred_grade=CrudeGrade.MEDIUM_SOUR, port_ids=["vadinar"],
                 inventory_days=7),
        Refinery(id="bathinda_ref", name="Bathinda (HMEL)", operator="HMEL",
                 coords=GeoPoint(lat=30.21, lon=74.94), coast=Coast.WEST,
                 nameplate_kbpd=230, throughput_kbpd=220,
                 preferred_grade=CrudeGrade.MEDIUM_SOUR, port_ids=["mumbai"],
                 inventory_days=7),
        Refinery(id="haldia_ref", name="Haldia", operator="IOCL",
                 coords=GeoPoint(lat=22.03, lon=88.10), coast=Coast.EAST,
                 nameplate_kbpd=150, throughput_kbpd=142,
                 preferred_grade=CrudeGrade.MEDIUM_SOUR, port_ids=["paradip"],
                 inventory_days=8),
        Refinery(id="barauni_ref", name="Barauni", operator="IOCL",
                 coords=GeoPoint(lat=25.46, lon=85.97), coast=Coast.EAST,
                 nameplate_kbpd=120, throughput_kbpd=114,
                 preferred_grade=CrudeGrade.MEDIUM_SOUR, port_ids=["paradip"],
                 inventory_days=8),
    ]


def _reserves() -> list[StrategicReserveSite]:
    return [
        StrategicReserveSite(id="spr_vizag", name="Visakhapatnam SPR",
                             coords=GeoPoint(lat=17.73, lon=83.30),
                             capacity_mmt=1.33, fill_pct=98),
        StrategicReserveSite(id="spr_mangalore", name="Mangalore SPR",
                             coords=GeoPoint(lat=12.87, lon=74.88),
                             capacity_mmt=1.5, fill_pct=95),
        StrategicReserveSite(id="spr_padur", name="Padur SPR",
                             coords=GeoPoint(lat=13.42, lon=74.73),
                             capacity_mmt=2.5, fill_pct=96),
    ]


def build_energy_network() -> EnergyNetwork:
    """Construct the baseline digital twin of India's energy supply chain."""
    return EnergyNetwork(
        suppliers=_suppliers(),
        corridors=_corridors(),
        ports=_ports(),
        refineries=_refineries(),
        reserves=_reserves(),
        market=MarketState(),
        demand=DemandProfile(refinery_demand_kbpd=4900, import_dependence_pct=88.0),
    )
