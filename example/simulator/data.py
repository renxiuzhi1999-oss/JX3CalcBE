"""High level data loading utilities for the demo combat simulator.

The real C++ project reads data from GDI and Lua scripts.  For the
self-contained example we expose a pythonic data access layer that
returns strongly typed objects.  Each function contains generous
comments explaining the motivation so that the file doubles as
executable documentation for people who are inspecting the sample.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional
import json


@dataclass(frozen=True)
class Skill:
    """Representation of a single skill read from ``skills.json``.

    The structure is intentionally close to the C++ ``Skill`` type so
    that the simulation code can reuse the same naming conventions.
    ``cooldown`` and ``gcd`` are expressed in seconds, ``coefficient``
    is the multiplier that is applied on top of the player's attack
    rating when computing raw damage, and ``tags`` list the special
    behaviours an UI could use for filtering.
    """

    id: int
    name: str
    icon: str
    school: str
    base_damage: float
    coefficient: float
    cooldown: float
    gcd: float
    resource_cost: int
    script: str
    tags: List[str]


@dataclass(frozen=True)
class Buff:
    """A passive or active effect that modifies the player's stats."""

    id: int
    name: str
    icon: str
    duration: float
    tick_interval: Optional[float]
    effects: Dict[str, float]


@dataclass(frozen=True)
class Equipment:
    """Simplified representation of an equippable item."""

    id: int
    name: str
    slot: str
    rarity: str
    stats: Dict[str, float]
    attached_skill: Optional[int]


@dataclass(frozen=True)
class Talent:
    """Passive modifiers that emulate in-game talents/奇穴."""

    id: int
    name: str
    description: str
    effects: Dict[str, float]


@dataclass(frozen=True)
class RotationPreset:
    """Sequence of skill IDs used as a macro-like loop."""

    id: str
    name: str
    school: str
    sequence: List[int]


@dataclass(frozen=True)
class Target:
    """Enemy configuration used as the simulation target."""

    id: int
    name: str
    level: int
    defense: float
    resistance: float
    max_health: float


class DataRepository:
    """Loader for JSON based resource tables.

    ``DataRepository`` mimics the behaviour of the production system by
    exposing ``get_*`` helpers that raise a ``KeyError`` when a record
    is missing.  This mirrors the expectation that the caller has to
    validate input from the frontend before starting a simulation.
    """

    def __init__(self, root: Path):
        self._root = root
        self._skills: Dict[int, Skill] = {}
        self._buffs: Dict[int, Buff] = {}
        self._equipment: Dict[int, Equipment] = {}
        self._talents: Dict[int, Talent] = {}
        self._rotations: Dict[str, RotationPreset] = {}
        self._targets: Dict[int, Target] = {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _load_json(self, filename: str) -> Iterable[dict]:
        path = self._root / filename
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, list):
            raise ValueError(f"File {path} must contain a JSON array")
        return data

    def _ensure_loaded(self) -> None:
        if self._skills:
            return
        self._skills = {
            entry["id"]: Skill(**entry) for entry in self._load_json("skills.json")
        }
        self._buffs = {
            entry["id"]: Buff(**entry) for entry in self._load_json("buffs.json")
        }
        self._equipment = {
            entry["id"]: Equipment(**entry)
            for entry in self._load_json("equipment.json")
        }
        self._talents = {
            entry["id"]: Talent(**entry) for entry in self._load_json("talents.json")
        }
        self._rotations = {
            entry["id"]: RotationPreset(**entry)
            for entry in self._load_json("rotations.json")
        }
        self._targets = {
            entry["id"]: Target(**entry) for entry in self._load_json("targets.json")
        }

    # ------------------------------------------------------------------
    # Public API used by the simulator and the REST layer
    # ------------------------------------------------------------------
    def skills(self) -> List[Skill]:
        self._ensure_loaded()
        return list(self._skills.values())

    def buffs(self) -> List[Buff]:
        self._ensure_loaded()
        return list(self._buffs.values())

    def equipment(self) -> List[Equipment]:
        self._ensure_loaded()
        return list(self._equipment.values())

    def talents(self) -> List[Talent]:
        self._ensure_loaded()
        return list(self._talents.values())

    def rotations(self) -> List[RotationPreset]:
        self._ensure_loaded()
        return list(self._rotations.values())

    def targets(self) -> List[Target]:
        self._ensure_loaded()
        return list(self._targets.values())

    def get_skill(self, skill_id: int) -> Skill:
        self._ensure_loaded()
        return self._skills[skill_id]

    def get_buff(self, buff_id: int) -> Buff:
        self._ensure_loaded()
        return self._buffs[buff_id]

    def get_equipment(self, item_id: int) -> Equipment:
        self._ensure_loaded()
        return self._equipment[item_id]

    def get_talent(self, talent_id: int) -> Talent:
        self._ensure_loaded()
        return self._talents[talent_id]

    def get_rotation(self, rotation_id: str) -> RotationPreset:
        self._ensure_loaded()
        return self._rotations[rotation_id]

    def get_target(self, target_id: int) -> Target:
        self._ensure_loaded()
        return self._targets[target_id]


# ``create_repository`` is a convenience for dependency injection in
# the FastAPI app.  By exposing it here we keep the application code
# free from filesystem details and make testing easier.
def create_repository(data_dir: Path) -> DataRepository:
    return DataRepository(data_dir)

