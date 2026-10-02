"""
Multi-Site Station Registry and Metadata Catalog for Agri Telemetry & Forecasting Platform.
Tracks candidate and evaluated in-situ observation sites with geographical, climatological, and soil characteristics.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class SiteSuitability(str, Enum):
    CANONICAL_BASELINE = "CANONICAL_BASELINE"
    INDEPENDENT_EVALUATION = "INDEPENDENT_EVALUATION"
    EXCLUDED_INCOMPLETE_PROBES = "EXCLUDED_INCOMPLETE_PROBES"
    EXCLUDED_HIGH_MISSINGNESS = "EXCLUDED_HIGH_MISSINGNESS"


class ClimateRegime(str, Enum):
    HUMID_CONTINENTAL_PLAINS = "HUMID_CONTINENTAL_PLAINS"
    MIDWEST_CORN_BELT = "MIDWEST_CORN_BELT"
    ARID_DESERT_SOUTHWEST = "ARID_DESERT_SOUTHWEST"
    HUMID_SUBTROPICAL_SOUTHEAST = "HUMID_SUBTROPICAL_SOUTHEAST"
    SEMI_ARID_HIGH_PLAINS = "SEMI_ARID_HIGH_PLAINS"
    NORTHERN_GREAT_PLAINS = "NORTHERN_GREAT_PLAINS"


@dataclass
class StationMetadata:
    station_id: str
    site_id: str
    station_name: str
    state: str
    latitude: float
    longitude: float
    elevation_m: float
    climate_regime: ClimateRegime
    suitability: SiteSuitability
    soil_texture_class: str
    annual_precip_mm_2023: float
    probe_depths_cm: List[float]
    probe_completeness_pct: float
    weather_completeness_pct: float
    inclusion_rationale: str
    exclusion_reason: Optional[str] = None
    default_fc: float = 0.33
    default_wp: float = 0.13
    default_sat: float = 0.45


STATION_REGISTRY: Dict[str, StationMetadata] = {
    "NE_Lincoln_11_SW": StationMetadata(
        station_id="USCRN_NE_Lincoln_11_SW",
        site_id="FIELD_LINCOLN_01",
        station_name="Lincoln 11 SW",
        state="NE",
        latitude=40.70,
        longitude=-96.85,
        elevation_m=365.0,
        climate_regime=ClimateRegime.HUMID_CONTINENTAL_PLAINS,
        suitability=SiteSuitability.CANONICAL_BASELINE,
        soil_texture_class="Silt Loam",
        annual_precip_mm_2023=611.5,
        probe_depths_cm=[5.0, 10.0, 20.0, 50.0, 100.0],
        probe_completeness_pct=96.2,
        weather_completeness_pct=99.9,
        inclusion_rationale="Canonical baseline development and audit site; Great Plains rainfed transition.",
        default_fc=0.33,
        default_wp=0.13,
        default_sat=0.45,
    ),
    "IL_Champaign_9_SW": StationMetadata(
        station_id="USCRN_IL_Champaign_9_SW",
        site_id="FIELD_CHAMPAIGN_01",
        station_name="Champaign 9 SW",
        state="IL",
        latitude=40.05,
        longitude=-88.37,
        elevation_m=213.0,
        climate_regime=ClimateRegime.MIDWEST_CORN_BELT,
        suitability=SiteSuitability.INDEPENDENT_EVALUATION,
        soil_texture_class="Silt Loam / Drummer Silty Clay",
        annual_precip_mm_2023=832.0,
        probe_depths_cm=[5.0, 10.0, 20.0, 50.0, 100.0],
        probe_completeness_pct=99.1,
        weather_completeness_pct=99.9,
        inclusion_rationale="Core Midwest Corn Belt agricultural region; deep productive prairie soil, high precipitation.",
        default_fc=0.34,
        default_wp=0.14,
        default_sat=0.46,
    ),
    "NM_Las_Cruces_20_N": StationMetadata(
        station_id="USCRN_NM_Las_Cruces_20_N",
        site_id="FIELD_LAS_CRUCES_01",
        station_name="Las Cruces 20 N (Jornada)",
        state="NM",
        latitude=32.61,
        longitude=-106.74,
        elevation_m=1330.0,
        climate_regime=ClimateRegime.ARID_DESERT_SOUTHWEST,
        suitability=SiteSuitability.INDEPENDENT_EVALUATION,
        soil_texture_class="Sandy Loam / Coarse Sand",
        annual_precip_mm_2023=169.8,
        probe_depths_cm=[5.0, 10.0, 20.0, 50.0, 100.0],
        probe_completeness_pct=99.6,
        weather_completeness_pct=99.6,
        inclusion_rationale="Arid desert southwest benchmark (Jornada Basin); low rain, extreme solar radiation, coarse soil.",
        default_fc=0.20,
        default_wp=0.07,
        default_sat=0.38,
    ),
    "GA_Watkinsville_5_SSE": StationMetadata(
        station_id="USCRN_GA_Watkinsville_5_SSE",
        site_id="FIELD_WATKINSVILLE_01",
        station_name="Watkinsville 5 SSE",
        state="GA",
        latitude=33.78,
        longitude=-83.39,
        elevation_m=235.0,
        climate_regime=ClimateRegime.HUMID_SUBTROPICAL_SOUTHEAST,
        suitability=SiteSuitability.INDEPENDENT_EVALUATION,
        soil_texture_class="Cecil Sandy Clay Loam (Ultisol)",
        annual_precip_mm_2023=1339.0,
        probe_depths_cm=[5.0, 10.0, 20.0, 50.0, 100.0],
        probe_completeness_pct=93.0,
        weather_completeness_pct=93.8,
        inclusion_rationale="Humid subtropical southeastern benchmark; high annual rainfall, weathered clay soil, intense summer ET.",
        default_fc=0.28,
        default_wp=0.12,
        default_sat=0.42,
    ),
    "CO_Nunn_7_NNE": StationMetadata(
        station_id="USCRN_CO_Nunn_7_NNE",
        site_id="FIELD_NUNN_01",
        station_name="Nunn 7 NNE (Central Plains)",
        state="CO",
        latitude=40.81,
        longitude=-104.76,
        elevation_m=1661.0,
        climate_regime=ClimateRegime.SEMI_ARID_HIGH_PLAINS,
        suitability=SiteSuitability.INDEPENDENT_EVALUATION,
        soil_texture_class="Sandy Loam / Ascalon Loam",
        annual_precip_mm_2023=344.8,
        probe_depths_cm=[5.0, 10.0, 20.0, 50.0, 100.0],
        probe_completeness_pct=89.8,
        weather_completeness_pct=98.4,
        inclusion_rationale="Semi-arid high plains shortgrass steppe; high elevation, low rainfall, winter freezing.",
        default_fc=0.25,
        default_wp=0.09,
        default_sat=0.40,
    ),
    "SD_Sioux_Falls_14_NNE": StationMetadata(
        station_id="USCRN_SD_Sioux_Falls_14_NNE",
        site_id="FIELD_SIOUX_FALLS_01",
        station_name="Sioux Falls 14 NNE",
        state="SD",
        latitude=43.73,
        longitude=-96.62,
        elevation_m=474.0,
        climate_regime=ClimateRegime.NORTHERN_GREAT_PLAINS,
        suitability=SiteSuitability.INDEPENDENT_EVALUATION,
        soil_texture_class="Silty Clay Loam",
        annual_precip_mm_2023=599.2,
        probe_depths_cm=[5.0, 10.0, 20.0, 50.0, 100.0],
        probe_completeness_pct=99.9,
        weather_completeness_pct=99.9,
        inclusion_rationale="Northern Great Plains cross-validation site; cold winter freezing with summer convective pulses.",
        default_fc=0.33,
        default_wp=0.13,
        default_sat=0.45,
    ),
    "TX_Austin_33_NW": StationMetadata(
        station_id="USCRN_TX_Austin_33_NW",
        site_id="FIELD_AUSTIN_01",
        station_name="Austin 33 NW",
        state="TX",
        latitude=30.62,
        longitude=-98.08,
        elevation_m=387.0,
        climate_regime=ClimateRegime.HUMID_SUBTROPICAL_SOUTHEAST,
        suitability=SiteSuitability.EXCLUDED_INCOMPLETE_PROBES,
        soil_texture_class="Unknown (Shallow)",
        annual_precip_mm_2023=711.2,
        probe_depths_cm=[5.0, 10.0],
        probe_completeness_pct=39.9,
        weather_completeness_pct=99.9,
        inclusion_rationale="Evaluated candidate.",
        exclusion_reason="Probes at 20cm, 50cm, and 100cm are entirely uninstalled/inactive (0% data); root-zone profile state cannot be integrated.",
    ),
    "AL_Selma_13_WNW": StationMetadata(
        station_id="USCRN_AL_Selma_13_WNW",
        site_id="FIELD_SELMA_01",
        station_name="Selma 13 WNW",
        state="AL",
        latitude=32.46,
        longitude=-87.24,
        elevation_m=56.0,
        climate_regime=ClimateRegime.HUMID_SUBTROPICAL_SOUTHEAST,
        suitability=SiteSuitability.EXCLUDED_HIGH_MISSINGNESS,
        soil_texture_class="Heavy Clay",
        annual_precip_mm_2023=1411.7,
        probe_depths_cm=[5.0, 10.0, 20.0, 50.0, 100.0],
        probe_completeness_pct=55.3,
        weather_completeness_pct=99.9,
        inclusion_rationale="Evaluated candidate.",
        exclusion_reason="Severe multi-depth sensor failure (43.1% missing at 10cm, 55.0% missing at 100cm); breaks chronological continuity.",
    ),
    "IA_Des_Moines_17_E": StationMetadata(
        station_id="USCRN_IA_Des_Moines_17_E",
        site_id="FIELD_DES_MOINES_01",
        station_name="Des Moines 17 E",
        state="IA",
        latitude=41.56,
        longitude=-93.29,
        elevation_m=283.0,
        climate_regime=ClimateRegime.MIDWEST_CORN_BELT,
        suitability=SiteSuitability.EXCLUDED_HIGH_MISSINGNESS,
        soil_texture_class="Clarion Loam",
        annual_precip_mm_2023=543.5,
        probe_depths_cm=[5.0, 10.0, 20.0, 50.0, 100.0],
        probe_completeness_pct=64.5,
        weather_completeness_pct=99.6,
        inclusion_rationale="Evaluated candidate.",
        exclusion_reason="35.5% missingness across all soil moisture channels during summer/fall growing season.",
    ),
}


def get_active_evaluation_sites() -> List[StationMetadata]:
    """Returns list of independent external sites suitable for benchmark evaluation."""
    return [
        m for m in STATION_REGISTRY.values()
        if m.suitability == SiteSuitability.INDEPENDENT_EVALUATION
    ]


def get_all_registered_sites() -> List[StationMetadata]:
    """Returns all registered sites including baseline and excluded stations."""
    return list(STATION_REGISTRY.values())


def get_station_metadata(station_key: str) -> Optional[StationMetadata]:
    """Look up station metadata by station key (e.g. 'IL_Champaign_9_SW' or full ID)."""
    if station_key in STATION_REGISTRY:
        return STATION_REGISTRY[station_key]
    for key, meta in STATION_REGISTRY.items():
        if meta.station_id == station_key or key in station_key:
            return meta
    return None
