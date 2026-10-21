# DC paper, August 2026 model configs (frozen)

Snapshot of the configs behind the August 2026 DC-paper runs (128 nodes,
overnight 2030, electricity-only), saved on 2026-10-21 before the upgrade
to PyPSA-Eur v2026.09.0 (vault T-12, DEC-18).

- `config.yaml`: the user config that was active (gitignored upstream).
- `config.full.yaml`: passed with `--configfile` for the 128-node build.
- `config.yaml.bak`: an older copy of the user config found next to it.

The demand patch in `scripts/build_electricity_demand.py` (NaN assert after
slicing to the output snapshots) is committed on this branch as well.
