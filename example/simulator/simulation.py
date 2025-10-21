"""Core battle simulation loop for the demo backend.

The real project executes a precise event queue in C++.  Here we
implement a simplified-yet-illustrative simulator that still supports
cooldowns, GCD, haste and buff effects.  The goal is to make the code
approachable so new contributors can understand the data flow before
jumping into the production engine.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple
import math
import random

from . import data


@dataclass
class PlayerBuild:
    """Configuration describing the player's starting stats."""

    base_attack: float = 1000.0
    base_crit: float = 0.15
    base_haste: float = 0.0
    base_resource: int = 100
    active_buffs: Sequence[int] = field(default_factory=list)
    talents: Sequence[int] = field(default_factory=list)
    equipment: Sequence[int] = field(default_factory=list)


@dataclass
class SimulationConfig:
    """Runtime options supplied by the REST API."""

    rotation: Sequence[int]
    target_id: int
    fight_seconds: float
    iterations: int
    seed: Optional[int] = None


@dataclass
class SkillUsage:
    """Entry in the combat log representing a single skill cast."""

    timestamp: float
    skill_id: int
    damage: float
    is_crit: bool


@dataclass
class IterationResult:
    """Detailed breakdown for a single simulated fight."""

    total_damage: float
    dps: float
    log: List[SkillUsage]


@dataclass
class SimulationSummary:
    """Aggregated statistics across multiple iterations."""

    iterations: List[IterationResult]

    @property
    def average_dps(self) -> float:
        return sum(run.dps for run in self.iterations) / len(self.iterations)

    @property
    def stdev_dps(self) -> float:
        mean = self.average_dps
        variance = sum((run.dps - mean) ** 2 for run in self.iterations) / max(
            1, len(self.iterations) - 1
        )
        return math.sqrt(variance)

    @property
    def max_dps(self) -> float:
        return max(run.dps for run in self.iterations)

    @property
    def min_dps(self) -> float:
        return min(run.dps for run in self.iterations)


class SimpleSimulator:
    """Small deterministic simulator that focuses on clarity.

    The implementation is intentionally verbose and heavily commented
    to help readers follow the internal calculations.  Every helper is
    split into its own method so that the unit tests (and the REST API)
    can reuse individual pieces if desired.
    """

    MIN_GCD = 0.7  # Keep the demo grounded in reality

    def __init__(self, repository: data.DataRepository):
        self._repository = repository

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    def run(self, build: PlayerBuild, config: SimulationConfig) -> SimulationSummary:
        rng = random.Random(config.seed)
        iterations: List[IterationResult] = []
        for _ in range(config.iterations):
            iterations.append(self._simulate_single_iteration(build, config, rng))
        return SimulationSummary(iterations=iterations)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _simulate_single_iteration(
        self, build: PlayerBuild, config: SimulationConfig, rng: random.Random
    ) -> IterationResult:
        rotation = list(config.rotation)
        if not rotation:
            raise ValueError("Rotation sequence may not be empty")

        target = self._repository.get_target(config.target_id)
        stats = self._compute_player_stats(build)

        clock = 0.0
        total_damage = 0.0
        log: List[SkillUsage] = []
        cooldowns: Dict[int, float] = {}
        gcd_ready_time = 0.0
        resource = stats["resource_pool"]

        while clock < config.fight_seconds:
            skill_id = rotation[int(clock) % len(rotation)]
            skill = self._repository.get_skill(skill_id)

            # Skip the skill if the player cannot afford it or if the cooldown
            # has not yet finished.  Instead of idling we advance time by a
            # small step, simulating a wait.
            if resource < skill.resource_cost or cooldowns.get(skill.id, 0.0) > clock:
                clock += 0.1
                continue

            # Respect the global cooldown.  The production game has a complex
            # event queue; here we simply fast-forward the clock.
            if clock < gcd_ready_time:
                clock = gcd_ready_time

            effective_gcd = max(self.MIN_GCD, skill.gcd - stats["gcd_reduction"])
            cast_end = clock + effective_gcd

            damage, is_crit = self._compute_damage(skill, stats, rng, target)

            log.append(
                SkillUsage(timestamp=clock, skill_id=skill.id, damage=damage, is_crit=is_crit)
            )
            total_damage += damage

            resource = min(stats["resource_pool"], resource - skill.resource_cost + 5)
            cooldowns[skill.id] = cast_end + skill.cooldown
            gcd_ready_time = cast_end
            clock = cast_end

        dps = total_damage / config.fight_seconds
        return IterationResult(total_damage=total_damage, dps=dps, log=log)

    def _compute_player_stats(self, build: PlayerBuild) -> Dict[str, float]:
        """Aggregate the base stats with buffs, talents and equipment."""

        attack = build.base_attack
        crit = build.base_crit
        haste = build.base_haste
        resource_pool = build.base_resource
        damage_bonus = 0.0
        gcd_reduction = 0.0

        for item_id in build.equipment:
            item = self._repository.get_equipment(item_id)
            attack += item.stats.get("attack", 0.0)
            crit += item.stats.get("crit", 0.0)
            haste += item.stats.get("haste", 0.0)

        for buff_id in build.active_buffs:
            buff = self._repository.get_buff(buff_id)
            damage_bonus += buff.effects.get("attack_percent", 0.0)
            crit += buff.effects.get("crit_chance", 0.0)
            haste += buff.effects.get("haste", 0.0)

        for talent_id in build.talents:
            talent = self._repository.get_talent(talent_id)
            damage_bonus += talent.effects.get("damage_percent", 0.0)
            gcd_reduction += talent.effects.get("gcd_reduction", 0.0)

        return {
            "attack": attack,
            "crit": min(0.95, crit),
            "haste": min(1.0, haste),
            "damage_bonus": damage_bonus,
            "gcd_reduction": gcd_reduction,
            "resource_pool": resource_pool,
        }

    def _compute_damage(
        self,
        skill: data.Skill,
        stats: Dict[str, float],
        rng: random.Random,
        target: data.Target,
    ) -> Tuple[float, bool]:
        """Return the damage for a single skill use."""

        attack = stats["attack"] * (1.0 + stats["damage_bonus"])
        base = skill.base_damage + stats["haste"] * 10
        non_crit = (base + stats["attack"] * skill.coefficient) * (1 - target.resistance)
        crit_chance = stats["crit"]
        is_crit = rng.random() < crit_chance
        damage = non_crit * (1.75 if is_crit else 1.0)
        return max(0.0, damage), is_crit

