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
- Standalone命令行计算器，可在本地终端直接运行 DPS 模拟，无需网页前端。
- Tkinter 图形界面程序，直接在桌面应用里配置循环并查看模拟结果。

## Getting Started

1. **Create a virtual environment**

   ```bash
   cd example/simulator
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install fastapi uvicorn[standard]
   ```

2. **Run the API (choose your local port)**

   ```bash
   python -m example.simulator.main --host 0.0.0.0 --port 18080
   ```

   The command uses ``uvicorn`` to start the FastAPI application defined in
   ``api.py`` on your chosen port (``18080`` in this example).  You can point the
   UI at any local port that you prefer for running the backend.  By default the
   simulator loads the JSON files from the ``data`` directory shipped in this
   example.

3. **Open the UI**

   Navigate to <http://localhost:18080/ui/index.html>.  The single-page UI will
   load metadata from the API, let you pick buffs/talents/equipment, and submit a
   simulation.  If you serve the UI from a different origin, use the new *Server
   Endpoint* field at the top of the page to enter the API base URL (for example,
   ``http://localhost:18080``).  Results are displayed in real time once the task
   finishes.

## 在本地终端运行命令行计算器

如果你不需要 Web 界面，可以直接运行 ``example.simulator.cli`` 中的命令行程序。
它使用与 REST API 相同的资源与模拟器，支持列出资源、指定轮换、装备、奇穴
等配置项，并在终端输出 DPS 统计结果。

1. **安装依赖（仅需标准库 + JSON 数据）**

   基础模拟器不依赖 FastAPI/Uvicorn，因此只要激活虚拟环境即可：

   ```bash
   cd example/simulator
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   ```

2. **查看可用资源**

   ```bash
   python -m example.simulator.cli --list all
   ```

   该命令会列出 ``data`` 目录中的技能、Buff、奇穴、装备、轮换与目标的编号，
   方便后续在命令行参数中引用。

3. **执行一次模拟**

   ```bash
   python -m example.simulator.cli --rotation-id basic --iterations 50 --buff 2001 --talent 3001
   ```

   - ``--rotation-id`` 或 ``--rotation-sequence``：指定循环。
   - ``--buff`` / ``--talent`` / ``--equipment``：重复该参数可以叠加多个配置。
   - ``--show-log``：打印首轮的详细战斗记录。
   - ``--json``：以 JSON 格式输出统计结果，便于脚本读取。

   运行结束后会显示平均 DPS、标准差以及每轮 DPS。可以结合 ``--seed`` 固定
   随机数，或调整 ``--fight-seconds``、``--iterations`` 进行更长时间或更多次
   的 Monte Carlo 迭代。

## 启动桌面版图形界面

当你希望以“原生应用”的方式体验模拟器时，可以运行新增的 Tkinter GUI。
它与命令行/REST 接口共享同一套 JSON 数据与核心模拟代码，因此无需额
外的后端服务。

1. **准备依赖**

   Tkinter 属于 Python 标准库的一部分，但部分 Linux 发行版需要额外
   安装 ``python3-tk`` 软件包。Windows 与 macOS 通常默认自带。

2. **启动应用**

   ```bash
   python -m example.simulator.gui
   ```

   程序会弹出一个窗口，顶部可以选择数据目录（默认使用 ``data``
   文件夹）。左侧提供轮换、目标、Buff、奇穴、装备等选择器，右下角
   的 *Run simulation* 按钮会执行多次迭代并在“Results”区域展示平均
   DPS、标准差以及首轮的详细战斗记录。

3. **自定义循环与数据目录**

   - 在 *Custom rotation (IDs)* 输入框中填入以空格或逗号分隔的技能
     ID，即可覆盖预设轮换。
   - 如果你有自制的 JSON 数据表，点击 *Browse → Reload* 选择目录后
     即可加载新的资源。

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

## Running from Visual Studio 2022

If you prefer to launch the Python demo directly inside Visual Studio, follow
these steps to avoid the common "无法配置项目" / "CMake 可执行文件错误" dialogs
that appear when Visual Studio tries to configure the root ``CMakeLists.txt``.

1. **Install the required workloads**

   - From *Visual Studio Installer*, enable the **Python 开发** workload so the
     IDE recognises Python projects.
   - Enable **使用 C++ 的桌面开发** (or install standalone
     [CMake](https://cmake.org/download/)) so Visual Studio ships with a CMake
     binary.  Without this component the IDE will show the "CMake 可执行文件错误"
     message whenever it scans the repository.

2. **Open the repository**

   Use *File ▸ Open ▸ Folder…* and pick the repository root.  When the CMake
   notification pops up you can either click *Install CMake* (recommended) or
   temporarily disable automatic configuration via *Tools ▸ Options ▸ CMake ▸
   General ▸ Enable project configuration on opening a folder* → set to
   **False**.  Disabling auto-configuration keeps Visual Studio from blocking
   you with the error dialog while you work with the Python files.

3. **Configure the Python environment**

   - Open *View ▸ Other Windows ▸ Python Environments* and create/attach a
     virtual environment.
   - With the environment selected, install the demo dependencies by running

     ```powershell
     pip install fastapi uvicorn[standard]
     ```

4. **Set the startup script**

   In *Solution Explorer* locate ``example/simulator/main.py``, right-click it
   and choose **Set as Startup File**.  This tells the debugger to run the demo
   backend instead of attempting a CMake build.

5. **Pass the desired host/port arguments**

   Open the project properties (**Debug ▸ Debug and Launch Settings**) and add
   the following script arguments so the server listens on your preferred local
   port:

   ```text
   --host 0.0.0.0 --port 18080
   ```

6. **Start debugging**

   Press **F5** (or click *Start Debugging*).  Visual Studio will launch
   ``uvicorn`` and show the server logs in the *Output* window.  Once the app is
   running you can open <http://localhost:18080/ui/index.html> in a browser to
   interact with the UI.  If you bound the server to another port, update the
   *Server Endpoint* field in the UI accordingly.

### Troubleshooting

- **Still seeing the CMake error** – Verify that CMake is installed.  You can
  add it via *Tools ▸ Get Tools and Features… ▸ 使用 C++ 的桌面开发*.  After the
  installation, restart Visual Studio so it detects the new toolchain.
- **Python debugger starts the wrong target** – Double-check that
  ``example/simulator/main.py`` is marked as the startup file and that the
  *Script Arguments* contain the `--host/--port` options.
- **`ModuleNotFoundError` for FastAPI/Uvicorn** – Ensure the selected Python
  environment has ``fastapi`` and ``uvicorn[standard]`` installed.  Installing
  them in another environment (for example, the global interpreter) will not
  automatically make them available to Visual Studio’s active environment.

