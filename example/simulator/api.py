"""FastAPI application exposing the simulation services."""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import data, simulation, tasks


class SkillModel(BaseModel):
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

    @classmethod
    def from_domain(cls, skill: data.Skill) -> "SkillModel":
        return cls(**asdict(skill))


class BuffModel(BaseModel):
    id: int
    name: str
    icon: str
    duration: float
    tick_interval: Optional[float]
    effects: dict

    @classmethod
    def from_domain(cls, buff: data.Buff) -> "BuffModel":
        return cls(**asdict(buff))


class EquipmentModel(BaseModel):
    id: int
    name: str
    slot: str
    rarity: str
    stats: dict
    attached_skill: Optional[int]

    @classmethod
    def from_domain(cls, item: data.Equipment) -> "EquipmentModel":
        return cls(**asdict(item))


class TalentModel(BaseModel):
    id: int
    name: str
    description: str
    effects: dict

    @classmethod
    def from_domain(cls, talent: data.Talent) -> "TalentModel":
        return cls(**asdict(talent))


class RotationModel(BaseModel):
    id: str
    name: str
    school: str
    sequence: List[int]

    @classmethod
    def from_domain(cls, rotation: data.RotationPreset) -> "RotationModel":
        return cls(**asdict(rotation))


class TargetModel(BaseModel):
    id: int
    name: str
    level: int
    defense: float
    resistance: float
    max_health: float

    @classmethod
    def from_domain(cls, target: data.Target) -> "TargetModel":
        return cls(**asdict(target))


class BuildModel(BaseModel):
    base_attack: float = 1000.0
    base_crit: float = 0.15
    base_haste: float = 0.0
    base_resource: int = 100
    active_buffs: List[int] = Field(default_factory=list)
    talents: List[int] = Field(default_factory=list)
    equipment: List[int] = Field(default_factory=list)

    def to_domain(self) -> simulation.PlayerBuild:
        return simulation.PlayerBuild(
            base_attack=self.base_attack,
            base_crit=self.base_crit,
            base_haste=self.base_haste,
            base_resource=self.base_resource,
            active_buffs=self.active_buffs,
            talents=self.talents,
            equipment=self.equipment,
        )


class SimulationRequest(BaseModel):
    build: BuildModel
    target_id: int
    fight_seconds: float = Field(gt=0)
    iterations: int = Field(gt=0, le=500)
    rotation_id: Optional[str] = None
    rotation_sequence: Optional[List[int]] = None
    seed: Optional[int] = None


class TaskResponse(BaseModel):
    task_id: str
    status: str
    error: Optional[str] = None
    average_dps: Optional[float] = None
    max_dps: Optional[float] = None
    min_dps: Optional[float] = None
    stdev_dps: Optional[float] = None
    iterations: Optional[List[dict]] = None


# Dependency wiring -----------------------------------------------------

def create_app(data_dir: Path) -> FastAPI:
    repository = data.create_repository(data_dir)
    manager = tasks.TaskManager(repository)
    app = FastAPI(title="JX3 Combat Simulator Demo", version="1.0.0")

    ui_dir = (Path(__file__).resolve().parent / "ui")
    app.mount("/ui", StaticFiles(directory=str(ui_dir)), name="ui")

    def get_repository() -> data.DataRepository:
        return repository

    def get_manager() -> tasks.TaskManager:
        return manager

    @app.get("/")
    async def root() -> RedirectResponse:
        return RedirectResponse(url="/ui/index.html")

    @app.get("/metadata/skills", response_model=List[SkillModel])
    async def list_skills(repo: data.DataRepository = Depends(get_repository)):
        return [SkillModel.from_domain(skill) for skill in repo.skills()]

    @app.get("/metadata/buffs", response_model=List[BuffModel])
    async def list_buffs(repo: data.DataRepository = Depends(get_repository)):
        return [BuffModel.from_domain(buff) for buff in repo.buffs()]

    @app.get("/metadata/equipment", response_model=List[EquipmentModel])
    async def list_equipment(repo: data.DataRepository = Depends(get_repository)):
        return [EquipmentModel.from_domain(item) for item in repo.equipment()]

    @app.get("/metadata/talents", response_model=List[TalentModel])
    async def list_talents(repo: data.DataRepository = Depends(get_repository)):
        return [TalentModel.from_domain(talent) for talent in repo.talents()]

    @app.get("/metadata/rotations", response_model=List[RotationModel])
    async def list_rotations(repo: data.DataRepository = Depends(get_repository)):
        return [RotationModel.from_domain(rotation) for rotation in repo.rotations()]

    @app.get("/metadata/targets", response_model=List[TargetModel])
    async def list_targets(repo: data.DataRepository = Depends(get_repository)):
        return [TargetModel.from_domain(target) for target in repo.targets()]

    @app.post("/simulate", response_model=TaskResponse, status_code=202)
    async def trigger_simulation(
        request: SimulationRequest,
        repo: data.DataRepository = Depends(get_repository),
        manager: tasks.TaskManager = Depends(get_manager),
    ) -> TaskResponse:
        if request.rotation_id and request.rotation_sequence:
            raise HTTPException(status_code=400, detail="Specify either rotation_id or rotation_sequence, not both")

        if request.rotation_id:
            try:
                rotation = repo.get_rotation(request.rotation_id)
                rotation_sequence = rotation.sequence
            except KeyError as exc:
                raise HTTPException(status_code=404, detail=f"Unknown rotation {request.rotation_id}") from exc
        elif request.rotation_sequence:
            rotation_sequence = request.rotation_sequence
        else:
            raise HTTPException(status_code=400, detail="A rotation must be provided")

        build = request.build.to_domain()
        config = simulation.SimulationConfig(
            rotation=rotation_sequence,
            target_id=request.target_id,
            fight_seconds=request.fight_seconds,
            iterations=request.iterations,
            seed=request.seed,
        )

        state = await manager.create_task(build, config)
        return TaskResponse(task_id=state.task_id, status=state.status)

    @app.get("/tasks/{task_id}", response_model=TaskResponse)
    async def get_task_status(
        task_id: str, manager: tasks.TaskManager = Depends(get_manager)
    ) -> TaskResponse:
        try:
            state = await manager.get_task(task_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Task not found") from exc

        response = TaskResponse(task_id=state.task_id, status=state.status, error=state.error)
        if state.result:
            summary = state.result.summary
            response.average_dps = summary.average_dps
            response.max_dps = summary.max_dps
            response.min_dps = summary.min_dps
            response.stdev_dps = summary.stdev_dps
            response.iterations = [
                {
                    "total_damage": it.total_damage,
                    "dps": it.dps,
                    "log": [
                        {
                            "timestamp": entry.timestamp,
                            "skill_id": entry.skill_id,
                            "damage": entry.damage,
                            "is_crit": entry.is_crit,
                        }
                        for entry in it.log
                    ],
                }
                for it in summary.iterations
            ]
        return response

    return app


def build_app() -> FastAPI:
    """Convenience entry point for ``uvicorn example.simulator.api:build_app``."""

    data_dir = Path(__file__).resolve().parent / "data"
    return create_app(data_dir)

