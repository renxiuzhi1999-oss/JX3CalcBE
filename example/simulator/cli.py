"""Command line interface for the demo combat simulator.

The real project exposes a Web UI and REST API.  This module provides a
fully offline alternative so that players can run DPS calculations from
the terminal without starting a web server.  The interface intentionally
mirrors the JSON structure consumed by ``api.py`` so that both layers can
share the same ``data`` and ``simulation`` modules.
"""
from __future__ import annotations

from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import Iterable, List, Sequence
import json
import sys

from . import data, simulation


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Local DPS calculator (no web UI required)")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "data",
        help="Directory that contains the JSON resource tables.",
    )
    parser.add_argument(
        "--rotation-id",
        help="Identifier of a preset rotation listed in rotations.json.",
    )
    parser.add_argument(
        "--rotation-sequence",
        help=(
            "Comma or space separated skill IDs that form a custom rotation. "
            "Overrides --rotation-id when provided."
        ),
    )
    parser.add_argument(
        "--target",
        type=int,
        default=1,
        help="ID of the enemy target to fight (defaults to the training dummy).",
    )
    parser.add_argument(
        "--fight-seconds",
        type=float,
        default=180.0,
        help="Duration of the fight in seconds.",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=100,
        help="Number of Monte Carlo iterations to execute for the DPS study.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="Seed for the pseudo-random number generator (omit for random seed).",
    )
    parser.add_argument(
        "--base-attack",
        type=float,
        default=1000.0,
        help="Base attack rating before buffs, talents and equipment.",
    )
    parser.add_argument(
        "--base-crit",
        type=float,
        default=0.15,
        help="Base critical strike chance expressed as a decimal (0.15 = 15%).",
    )
    parser.add_argument(
        "--base-haste",
        type=float,
        default=0.0,
        help="Base haste amount expressed as a decimal (0.10 = 10%).",
    )
    parser.add_argument(
        "--resource",
        type=int,
        default=100,
        help="Maximum resource value available for the rotation.",
    )
    parser.add_argument(
        "--buff",
        dest="buffs",
        action="append",
        type=int,
        default=[],
        help="ID of a buff to activate.  Repeat the flag to add multiple buffs.",
    )
    parser.add_argument(
        "--talent",
        dest="talents",
        action="append",
        type=int,
        default=[],
        help="ID of a talent/奇穴 to activate.  Repeat for multiple entries.",
    )
    parser.add_argument(
        "--equipment",
        dest="equipment",
        action="append",
        type=int,
        default=[],
        help="ID of an equipment piece to equip.  Repeat for multiple slots.",
    )
    parser.add_argument(
        "--list",
        choices=["skills", "buffs", "talents", "equipment", "rotations", "targets", "all"],
        action="append",
        help="Print resource tables and exit.  Repeat to list multiple categories.",
    )
    parser.add_argument(
        "--show-log",
        action="store_true",
        help="Print the detailed combat log for the first iteration.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output the summary as JSON (useful for scripting/integration).",
    )
    return parser


def _parse_rotation_sequence(text: str) -> List[int]:
    tokens: List[str] = []
    for chunk in text.replace("\n", " ").replace(",", " ").split():
        stripped = chunk.strip()
        if stripped:
            tokens.append(stripped)
    if not tokens:
        raise ValueError("Rotation sequence must contain at least one skill ID")
    try:
        return [int(token) for token in tokens]
    except ValueError as exc:  # pragma: no cover - defensive error reporting
        raise ValueError("Rotation sequence may only contain integers") from exc


def _list_resources(repo: data.DataRepository, categories: Sequence[str]) -> None:
    to_list = set(categories)
    if "all" in to_list:
        to_list = {"skills", "buffs", "talents", "equipment", "rotations", "targets"}

    if "skills" in to_list:
        print("Skills:")
        for skill in sorted(repo.skills(), key=lambda entry: entry.id):
            print(f"  {skill.id:4d} | {skill.name:<18} | {skill.school:<10} | CD {skill.cooldown:>4.1f}s")
        print()

    if "buffs" in to_list:
        print("Buffs:")
        for buff in sorted(repo.buffs(), key=lambda entry: entry.id):
            print(f"  {buff.id:4d} | {buff.name:<20} | +{buff.effects}")
        print()

    if "talents" in to_list:
        print("Talents:")
        for talent in sorted(repo.talents(), key=lambda entry: entry.id):
            print(f"  {talent.id:4d} | {talent.name:<22} | {talent.effects}")
        print()

    if "equipment" in to_list:
        print("Equipment:")
        for item in sorted(repo.equipment(), key=lambda entry: entry.id):
            print(f"  {item.id:4d} | {item.name:<22} | {item.slot:<8} | {item.stats}")
        print()

    if "rotations" in to_list:
        print("Rotations:")
        for preset in sorted(repo.rotations(), key=lambda entry: entry.id):
            seq = ", ".join(str(skill_id) for skill_id in preset.sequence)
            print(f"  {preset.id:<10} | {preset.name:<20} | {seq}")
        print()

    if "targets" in to_list:
        print("Targets:")
        for target in sorted(repo.targets(), key=lambda entry: entry.id):
            print(
                f"  {target.id:4d} | {target.name:<18} | level {target.level} | "
                f"resist {target.resistance:.2f}"
            )
        print()


def _build_player(args: Namespace) -> simulation.PlayerBuild:
    return simulation.PlayerBuild(
        base_attack=args.base_attack,
        base_crit=args.base_crit,
        base_haste=args.base_haste,
        base_resource=args.resource,
        active_buffs=args.buffs,
        talents=args.talents,
        equipment=args.equipment,
    )


def _resolve_rotation(args: Namespace, repo: data.DataRepository) -> Sequence[int]:
    if args.rotation_sequence:
        return _parse_rotation_sequence(args.rotation_sequence)
    if args.rotation_id:
        preset = repo.get_rotation(args.rotation_id)
        return preset.sequence
    raise SystemExit("You must provide either --rotation-id or --rotation-sequence")


def _summarise(summary: simulation.SimulationSummary, args: Namespace) -> None:
    if args.json:
        payload = {
            "iterations": [
                {
                    "total_damage": run.total_damage,
                    "dps": run.dps,
                    "log": [
                        {
                            "timestamp": entry.timestamp,
                            "skill_id": entry.skill_id,
                            "damage": entry.damage,
                            "is_crit": entry.is_crit,
                        }
                        for entry in run.log
                    ],
                }
                for run in summary.iterations
            ],
            "average_dps": summary.average_dps,
            "stdev_dps": summary.stdev_dps,
            "min_dps": summary.min_dps,
            "max_dps": summary.max_dps,
        }
        json.dump(payload, sys.stdout, indent=2)
        print()
        return

    print("=== DPS Summary ===")
    print(f"Iterations       : {len(summary.iterations)}")
    print(f"Average DPS      : {summary.average_dps:,.2f}")
    print(f"Std Dev DPS      : {summary.stdev_dps:,.2f}")
    print(f"Maximum DPS      : {summary.max_dps:,.2f}")
    print(f"Minimum DPS      : {summary.min_dps:,.2f}")

    print("\nPer Iteration:")
    for idx, run in enumerate(summary.iterations, start=1):
        print(f"  #{idx:03d} -> DPS {run.dps:,.2f} (total damage {run.total_damage:,.0f})")

    if args.show_log and summary.iterations:
        first = summary.iterations[0]
        print("\nDetailed combat log for iteration #1:")
        for entry in first.log:
            crit_flag = "CRIT" if entry.is_crit else "----"
            print(
                f"  t={entry.timestamp:6.2f}s | skill {entry.skill_id:4d} | "
                f"damage {entry.damage:8.1f} | {crit_flag}"
            )


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.iterations <= 0:
        parser.error("--iterations must be a positive integer")
    if args.fight_seconds <= 0:
        parser.error("--fight-seconds must be greater than zero")

    repository = data.DataRepository(args.data_dir)

    if args.list:
        _list_resources(repository, args.list)
        return 0

    rotation = _resolve_rotation(args, repository)
    build = _build_player(args)
    config = simulation.SimulationConfig(
        rotation=rotation,
        target_id=args.target,
        fight_seconds=args.fight_seconds,
        iterations=args.iterations,
        seed=args.seed,
    )

    simulator = simulation.SimpleSimulator(repository)
    summary = simulator.run(build, config)

    _summarise(summary, args)
    return 0


if __name__ == "__main__":  # pragma: no cover - manual invocation only
    raise SystemExit(main())
