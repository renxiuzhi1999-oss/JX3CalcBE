"""Tkinter-based desktop UI for the demo combat simulator.

This module provides a lightweight graphical interface that reuses the
``simulation`` and ``data`` helpers from the sample backend.  The goal is
to give Windows users (and anyone who prefers a native app) a quick way
to configure builds, run DPS studies, and inspect the combat log without
starting the FastAPI service or the HTML front-end.

The implementation intentionally favours readability over flashy widgets
so new contributors can expand the UI with minimal prior Tkinter
experience.
"""
from __future__ import annotations

import re
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Sequence

from . import data, simulation


@dataclass
class _ListEntry:
    """Helper structure used to map Tk listbox rows back to record IDs."""

    id: int
    label: str


class SimulatorGUI:
    """Encapsulates the Tkinter widgets and simulation workflow."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("JX3 Demo DPS Calculator")
        self.root.geometry("960x720")

        default_data_dir = Path(__file__).resolve().parent / "data"
        self.data_path_var = tk.StringVar(value=str(default_data_dir))
        self.rotation_var = tk.StringVar()
        self.target_var = tk.StringVar()
        self.custom_rotation_var = tk.StringVar()
        self.fight_seconds_var = tk.StringVar(value="180")
        self.iterations_var = tk.StringVar(value="100")
        self.seed_var = tk.StringVar(value="")
        self.attack_var = tk.StringVar(value="1000")
        self.crit_var = tk.StringVar(value="0.15")
        self.haste_var = tk.StringVar(value="0.0")
        self.resource_var = tk.StringVar(value="100")

        self.repo: data.DataRepository | None = None
        self.simulator: simulation.SimpleSimulator | None = None
        self.rotation_lookup: Dict[str, str] = {}
        self.target_lookup: Dict[str, int] = {}

        self.buff_entries: List[_ListEntry] = []
        self.talent_entries: List[_ListEntry] = []
        self.equipment_entries: List[_ListEntry] = []

        self._build_layout()
        self._refresh_repository(default_data_dir)

    # ------------------------------------------------------------------
    # UI construction helpers
    # ------------------------------------------------------------------
    def _build_layout(self) -> None:
        container = ttk.Frame(self.root, padding=12)
        container.pack(fill=tk.BOTH, expand=True)

        config_frame = ttk.LabelFrame(container, text="Simulation Settings", padding=12)
        config_frame.pack(fill=tk.X, anchor=tk.N)

        # Data directory selection -------------------------------------------------
        ttk.Label(config_frame, text="Data directory:").grid(row=0, column=0, sticky=tk.W)
        data_entry = ttk.Entry(config_frame, textvariable=self.data_path_var, width=80)
        data_entry.grid(row=0, column=1, sticky=tk.W, padx=(4, 4))
        ttk.Button(config_frame, text="Browse", command=self._choose_data_dir).grid(
            row=0, column=2, padx=(4, 0)
        )
        ttk.Button(config_frame, text="Reload", command=self._reload_clicked).grid(
            row=0, column=3, padx=(4, 0)
        )

        # Rotation selection -------------------------------------------------------
        ttk.Label(config_frame, text="Rotation preset:").grid(row=1, column=0, sticky=tk.W, pady=(8, 0))
        self.rotation_combo = ttk.Combobox(config_frame, textvariable=self.rotation_var, width=60)
        self.rotation_combo.grid(row=1, column=1, columnspan=3, sticky=tk.W, padx=(4, 0), pady=(8, 0))

        ttk.Label(config_frame, text="Custom rotation (IDs):").grid(row=2, column=0, sticky=tk.W)
        ttk.Entry(
            config_frame,
            textvariable=self.custom_rotation_var,
            width=60,
        ).grid(row=2, column=1, columnspan=3, sticky=tk.W, padx=(4, 0))

        # Target and runtime options ----------------------------------------------
        ttk.Label(config_frame, text="Target:").grid(row=3, column=0, sticky=tk.W, pady=(8, 0))
        self.target_combo = ttk.Combobox(config_frame, textvariable=self.target_var, width=60)
        self.target_combo.grid(row=3, column=1, columnspan=3, sticky=tk.W, padx=(4, 0), pady=(8, 0))

        ttk.Label(config_frame, text="Fight length (s):").grid(row=4, column=0, sticky=tk.W)
        ttk.Entry(config_frame, textvariable=self.fight_seconds_var, width=10).grid(
            row=4, column=1, sticky=tk.W
        )
        ttk.Label(config_frame, text="Iterations:").grid(row=4, column=2, sticky=tk.E)
        ttk.Entry(config_frame, textvariable=self.iterations_var, width=10).grid(
            row=4, column=3, sticky=tk.W
        )

        ttk.Label(config_frame, text="Random seed (optional):").grid(row=5, column=0, sticky=tk.W)
        ttk.Entry(config_frame, textvariable=self.seed_var, width=10).grid(row=5, column=1, sticky=tk.W)

        # Player stats -------------------------------------------------------------
        stats_frame = ttk.LabelFrame(container, text="Player Build", padding=12)
        stats_frame.pack(fill=tk.X, pady=(12, 0))

        ttk.Label(stats_frame, text="Base attack:").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(stats_frame, textvariable=self.attack_var, width=10).grid(row=0, column=1, sticky=tk.W)

        ttk.Label(stats_frame, text="Base crit (0-1):").grid(row=0, column=2, sticky=tk.W)
        ttk.Entry(stats_frame, textvariable=self.crit_var, width=10).grid(row=0, column=3, sticky=tk.W)

        ttk.Label(stats_frame, text="Base haste (0-1):").grid(row=0, column=4, sticky=tk.W)
        ttk.Entry(stats_frame, textvariable=self.haste_var, width=10).grid(row=0, column=5, sticky=tk.W)

        ttk.Label(stats_frame, text="Resource max:").grid(row=0, column=6, sticky=tk.W)
        ttk.Entry(stats_frame, textvariable=self.resource_var, width=10).grid(
            row=0, column=7, sticky=tk.W
        )

        # Multi-select lists -------------------------------------------------------
        selection_frame = ttk.Frame(container)
        selection_frame.pack(fill=tk.BOTH, expand=True, pady=(12, 0))

        self.buff_list = self._create_listbox(selection_frame, "Buffs", 0)
        self.talent_list = self._create_listbox(selection_frame, "Talents", 1)
        self.equipment_list = self._create_listbox(selection_frame, "Equipment", 2)

        # Run button and output ----------------------------------------------------
        ttk.Button(container, text="Run simulation", command=self._run_clicked).pack(
            pady=(12, 4)
        )

        output_frame = ttk.LabelFrame(container, text="Results", padding=12)
        output_frame.pack(fill=tk.BOTH, expand=True)

        self.output_text = tk.Text(output_frame, height=16, wrap=tk.NONE)
        self.output_text.pack(fill=tk.BOTH, expand=True)
        self._set_output("Select options and click 'Run simulation' to begin.\n")

    def _create_listbox(self, parent: ttk.Frame, title: str, column: int) -> tk.Listbox:
        frame = ttk.LabelFrame(parent, text=title, padding=8)
        frame.grid(row=0, column=column, padx=8, sticky=tk.N + tk.S + tk.E + tk.W)
        parent.columnconfigure(column, weight=1)
        parent.rowconfigure(0, weight=1)
        listbox = tk.Listbox(frame, selectmode=tk.MULTIPLE, exportselection=False, height=10)
        listbox.pack(fill=tk.BOTH, expand=True)
        return listbox

    # ------------------------------------------------------------------
    # Data loading helpers
    # ------------------------------------------------------------------
    def _choose_data_dir(self) -> None:
        current = Path(self.data_path_var.get())
        initialdir = current if current.exists() else Path.home()
        selection = filedialog.askdirectory(parent=self.root, initialdir=initialdir)
        if selection:
            self.data_path_var.set(selection)

    def _reload_clicked(self) -> None:
        path = Path(self.data_path_var.get())
        self._refresh_repository(path)

    def _refresh_repository(self, path: Path) -> None:
        try:
            repo = data.DataRepository(path)
            # Force eager loading so we can surface errors immediately.
            repo.skills()
            repo.buffs()
            repo.equipment()
            repo.talents()
            repo.rotations()
            repo.targets()
        except Exception as exc:  # pragma: no cover - UI feedback only
            messagebox.showerror("Failed to load data", str(exc))
            return

        self.repo = repo
        self.simulator = simulation.SimpleSimulator(repo)
        self._populate_from_repo(repo)
        self._set_output(
            "Data loaded successfully. Select options and click 'Run simulation' to begin.\n"
        )

    def _populate_from_repo(self, repo: data.DataRepository) -> None:
        rotations = sorted(repo.rotations(), key=lambda entry: entry.id)
        self.rotation_lookup = {
            f"{preset.name} ({preset.id})": preset.id for preset in rotations
        }
        rotation_labels = list(self.rotation_lookup.keys())
        self.rotation_combo["values"] = rotation_labels
        if rotation_labels:
            self.rotation_combo.current(0)

        targets = sorted(repo.targets(), key=lambda entry: entry.id)
        self.target_lookup = {
            f"{target.name} (ID {target.id})": target.id for target in targets
        }
        target_labels = list(self.target_lookup.keys())
        self.target_combo["values"] = target_labels
        if target_labels:
            self.target_combo.current(0)

        self.buff_entries = [
            _ListEntry(id=buff.id, label=f"{buff.id:4d} | {buff.name}")
            for buff in sorted(repo.buffs(), key=lambda entry: entry.id)
        ]
        self._load_listbox(self.buff_list, self.buff_entries)

        self.talent_entries = [
            _ListEntry(id=talent.id, label=f"{talent.id:4d} | {talent.name}")
            for talent in sorted(repo.talents(), key=lambda entry: entry.id)
        ]
        self._load_listbox(self.talent_list, self.talent_entries)

        self.equipment_entries = [
            _ListEntry(id=item.id, label=f"{item.id:4d} | {item.name}")
            for item in sorted(repo.equipment(), key=lambda entry: entry.id)
        ]
        self._load_listbox(self.equipment_list, self.equipment_entries)

    def _load_listbox(self, widget: tk.Listbox, entries: Sequence[_ListEntry]) -> None:
        widget.delete(0, tk.END)
        for entry in entries:
            widget.insert(tk.END, entry.label)

    # ------------------------------------------------------------------
    # Simulation entry point
    # ------------------------------------------------------------------
    def _run_clicked(self) -> None:
        if not self.repo or not self.simulator:
            messagebox.showwarning("Data not loaded", "Please load a data directory first.")
            return

        try:
            rotation = self._resolve_rotation()
            target_id = self._resolve_target()
            fight_seconds = float(self.fight_seconds_var.get())
            iterations = int(self.iterations_var.get())
            seed_text = self.seed_var.get().strip()
            seed = int(seed_text) if seed_text else None
            build = simulation.PlayerBuild(
                base_attack=float(self.attack_var.get()),
                base_crit=float(self.crit_var.get()),
                base_haste=float(self.haste_var.get()),
                base_resource=int(self.resource_var.get()),
                active_buffs=self._selected_ids(self.buff_list, self.buff_entries),
                talents=self._selected_ids(self.talent_list, self.talent_entries),
                equipment=self._selected_ids(self.equipment_list, self.equipment_entries),
            )
        except ValueError as exc:
            messagebox.showerror("Invalid input", str(exc))
            return

        config = simulation.SimulationConfig(
            rotation=rotation,
            target_id=target_id,
            fight_seconds=fight_seconds,
            iterations=iterations,
            seed=seed,
        )

        summary = self.simulator.run(build, config)
        output_lines = self._render_summary(summary)
        self._set_output("\n".join(output_lines))

    def _resolve_rotation(self) -> Sequence[int]:
        custom = self.custom_rotation_var.get().strip()
        if custom:
            return self._parse_rotation_sequence(custom)

        selected = self.rotation_var.get()
        if not selected:
            raise ValueError("Please choose a rotation preset or enter a custom sequence.")
        preset_id = self.rotation_lookup.get(selected)
        if preset_id is None:
            raise ValueError("Rotation preset could not be resolved. Please reload data.")
        preset = self.repo.get_rotation(preset_id)  # type: ignore[union-attr]
        return preset.sequence

    def _resolve_target(self) -> int:
        selected = self.target_var.get()
        if not selected:
            raise ValueError("Please select a target.")
        target_id = self.target_lookup.get(selected)
        if target_id is None:
            raise ValueError("Target entry could not be resolved. Please reload data.")
        return target_id

    def _selected_ids(self, widget: tk.Listbox, entries: Sequence[_ListEntry]) -> List[int]:
        return [entries[index].id for index in widget.curselection()]

    def _parse_rotation_sequence(self, text: str) -> List[int]:
        tokens = [token for token in re.split(r"[\s,]+", text.strip()) if token]
        if not tokens:
            raise ValueError("Custom rotation must contain at least one skill ID.")
        try:
            return [int(token) for token in tokens]
        except ValueError as exc:
            raise ValueError("Rotation sequence may only contain integers.") from exc

    def _render_summary(self, summary: simulation.SimulationSummary) -> List[str]:
        lines = [
            "Simulation finished.",
            f"Iterations: {len(summary.iterations)}",
            f"Average DPS: {summary.average_dps:.2f}",
            f"Std deviation: {summary.stdev_dps:.2f}",
            f"Best DPS: {summary.max_dps:.2f}",
            f"Worst DPS: {summary.min_dps:.2f}",
            "",
            "First iteration log:",
        ]

        first = summary.iterations[0]
        for usage in first.log:
            skill = self.repo.get_skill(usage.skill_id)  # type: ignore[union-attr]
            crit_flag = "CRIT" if usage.is_crit else "hit"
            lines.append(
                f"  {usage.timestamp:6.2f}s | {skill.name:<16} | {usage.damage:8.1f} | {crit_flag}"
            )
        return lines

    def _set_output(self, text: str) -> None:
        self.output_text.configure(state=tk.NORMAL)
        self.output_text.delete("1.0", tk.END)
        self.output_text.insert(tk.END, text)
        self.output_text.configure(state=tk.NORMAL)


def main() -> None:
    root = tk.Tk()
    SimulatorGUI(root)
    root.mainloop()


if __name__ == "__main__":  # pragma: no cover - manual entry point
    main()
