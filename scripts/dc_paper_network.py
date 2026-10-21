# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT
"""
DC paper patches applied in ``compose_network``, configured under ``dc_paper:``.

Grid build years (``dc_paper: grid:``): upstream PyPSA-Eur filters planned
transmission projects by status only, so a project commissioned in 2037
enters a 2030 network. Lines and HVDC links whose ``build_year`` lies after
the current horizon are deactivated, and endogenous grid expansion can be
frozen, following PyPSA-DE (``deactivate_early_transmission_expansion`` in
``scripts/pypsa-de/modify_prenetwork.py``).

Country load scaling (``dc_paper: demand:``): scales the electricity load of
one country by a factor, e.g. for electrification up to the horizon on top of
the load of a recent year (``load: fixed_year``). Placeholder until the load
is split by sector.

Example::

    dc_paper:
      grid:
        enable: true
        freeze_expansion: true
      demand:
        country: DE
        scaling_factor: 1.12
"""

import logging

import pypsa

logger = logging.getLogger(__name__)


def apply_grid_build_years(n: pypsa.Network, horizon: int, cfg: dict) -> None:
    if not cfg.get("enable", False):
        return

    future_lines = n.lines.index[n.lines.build_year > horizon]
    n.lines.loc[future_lines, "active"] = False

    dc = n.links.carrier == "DC"
    future_links = n.links.index[dc & (n.links.build_year > horizon)]
    n.links.loc[future_links, "active"] = False

    logger.info(
        f"DC paper grid rules, horizon {horizon}: deactivated {len(future_lines)} "
        f"lines and {len(future_links)} DC links with build_year > {horizon}."
    )

    if cfg.get("freeze_expansion", False):
        n.lines["s_nom_extendable"] = False
        n.links.loc[dc, "p_nom_extendable"] = False
        logger.info("DC paper grid rules: endogenous AC and DC expansion frozen.")


def scale_country_load(n: pypsa.Network, cfg: dict) -> None:
    factor = cfg.get("scaling_factor", 1.0)
    if factor == 1.0:
        return
    country = cfg["country"]
    loads = n.loads.index[n.loads.bus.map(n.buses.country) == country]
    loads = loads.intersection(n.loads_t.p_set.columns)
    w = n.snapshot_weightings.generators
    before = n.loads_t.p_set[loads].mul(w, axis=0).sum().sum() / 1e6
    n.loads_t.p_set[loads] *= factor
    logger.info(
        f"DC paper demand: {country} load scaled by {factor} "
        f"({before:.1f} -> {before * factor:.1f} TWh over the modelled period)."
    )


def cap_country_fleet(n: pypsa.Network, cfg: dict) -> None:
    """Scale down existing plants of a carrier to a total capacity (e.g. KVBG path)."""
    country = cfg["country"]
    in_c = n.generators.bus.map(n.buses.country) == country
    for carrier, gw in cfg.get("capacity_gw", {}).items():
        gens = n.generators.index[in_c & (n.generators.carrier == carrier)]
        total = n.generators.loc[gens, "p_nom"].sum()
        if total <= gw * 1e3 or total == 0:
            logger.info(
                f"DC paper fleet: {country} {carrier} {total / 1e3:.1f} GW <= cap {gw} GW."
            )
            continue
        factor = gw * 1e3 / total
        for attr in ["p_nom", "p_nom_min", "p_nom_max"]:
            n.generators.loc[gens, attr] *= factor
        logger.info(
            f"DC paper fleet: {country} {carrier} scaled from {total / 1e3:.1f} GW "
            f"to {gw} GW."
        )


def apply_dc_paper_network_rules(n: pypsa.Network, horizon: int, cfg: dict) -> None:
    apply_grid_build_years(n, horizon, cfg.get("grid", {}))
    if cfg.get("demand"):
        scale_country_load(n, cfg["demand"])
    if cfg.get("fleet"):
        cap_country_fleet(n, cfg["fleet"])
