# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT
"""
DC paper: extra constraints, hooked in via
``solving: options: custom_extra_functionality``.

Currently: renewable capacity floors for one country (vault ANNAHMEN rows A5
and B3, policy targets as minimum installed capacity). The data-centre layer
will be added here later.

Configured under ``dc_paper: res_floors:`` in the run config::

    dc_paper:
      res_floors:
        enable: true
        country: DE
        targets_gw:          # minimum total installed capacity in GW
          solar: 215
          onwind: 115
          offwind: 14
"""

import logging

logger = logging.getLogger(__name__)

CARRIER_GROUPS = {
    "solar": ["solar", "solar-hsat", "solar rooftop"],
    "onwind": ["onwind"],
    "offwind": ["offwind-ac", "offwind-dc", "offwind-float"],
}


def add_res_floors(n, cfg):
    country = cfg.get("country", "DE")
    gens = n.generators[n.generators.bus.map(n.buses.country) == country]
    if "active" in gens:
        gens = gens[gens.active]
    p_nom = n.model["Generator-p_nom"]
    dim = p_nom.dims[0]

    for group, target_gw in cfg.get("targets_gw", {}).items():
        g = gens[gens.carrier.isin(CARRIER_GROUPS[group])]
        ext = g.index[g.p_nom_extendable]
        fixed = g.loc[~g.p_nom_extendable, "p_nom"].sum()
        potential = fixed + g.loc[ext, "p_nom_max"].sum()
        target = target_gw * 1e3
        if target > potential:
            logger.warning(
                f"RES floor {country} {group}: target {target_gw} GW exceeds the "
                f"potential {potential / 1e3:.1f} GW; floor set to the potential."
            )
            target = potential
        if ext.empty or target <= fixed:
            logger.info(
                f"RES floor {country} {group}: existing {fixed / 1e3:.1f} GW already "
                f"meets {target / 1e3:.1f} GW, no constraint added."
            )
            continue
        n.model.add_constraints(
            p_nom.sel({dim: ext}).sum() >= target - fixed,
            name=f"dc_paper_res_floor_{country}_{group}",
        )
        logger.info(
            f"RES floor {country} {group}: >= {target / 1e3:.1f} GW "
            f"(existing {fixed / 1e3:.1f} GW)."
        )


def custom_extra_functionality(n, snapshots, snakemake):
    cfg = snakemake.config.get("dc_paper", {})
    if cfg.get("res_floors", {}).get("enable", False):
        add_res_floors(n, cfg["res_floors"])
