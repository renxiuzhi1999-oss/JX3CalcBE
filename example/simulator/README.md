# Demo Combat Simulator

This directory contains a self-contained Python implementation that mirrors the
architecture of the C++ backend.  It demonstrates how skill/奇穴/装备数据 are
loaded, how循环 simulation works, and how a前端 UI consumes the REST API.

## Features

- JSON-based resource loader for skills, buffs, equipment, talents, rotations, and targets.
- Deterministic combat simulator with cooldowns, GCD, haste, crit and damage bonuses.
- Async task manager that runs multiple iterations in the background and exposes
  aggregated DPS statistics.
- FastAPI service that serves both the JSON API and a lightweight UI for manual testing.

## Getting Started

1. **Create a virtual environment**

   ```bash
   cd example/simulator
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install fastapi uvicorn[standard]
   ```

2. **Run the API**

   ```bash
   python -m example.simulator.main --host 0.0.0.0 --port 8000
   ```

   The command uses ``uvicorn`` to start the FastAPI application defined in
   ``api.py``.  By default the simulator loads the JSON files from the ``data``
   directory shipped in this example.

3. **Open the UI**

   Navigate to <http://localhost:8000/ui/index.html>.  The single-page UI will
   load metadata from the API, let you pick buffs/talents/equipment, and submit a
   simulation.  Results are displayed in real time once the task finishes.

## API Overview

- ``GET /metadata/*`` – Enumerates skills, buffs, equipment, talents, rotations
  and targets so that the front-end can render selectors.
- ``POST /simulate`` – Starts a new simulation task.  The request accepts either
  a ``rotation_id`` referencing one of the presets or ``rotation_sequence`` for
  a custom循环.
- ``GET /tasks/{task_id}`` – Retrieves the status of a running task along with
  DPS statistics and the detailed combat log.

## UI Layout

The UI focuses on clarity and mirrors the categories used in the production
simulator:

- **Build Configuration card**: rotation preset dropdown, multi-selects for buffs,
  talents and equipment, and numeric inputs for战斗时间/iteration count.
- **Results card**: once the task completes, the summary card highlights
  平均DPS/最高/最低/标准差 followed by collapsible combat logs per iteration.
- The dark theme uses蓝紫色渐变 that matches the original tool’s aesthetic.

## Extending the Demo

- Add more JSON records to the ``data`` folder to test额外技能/奇穴.
- Modify ``simulation.py`` if you want to explore different damage formulas or
  implement高级事件队列.
- Swap the UI for a framework of your choice by pointing the ``/ui`` mount to
  another build output.

