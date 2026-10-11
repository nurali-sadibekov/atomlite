"""CustomTkinter interface for AtomLite."""

import math
import logging
import os
import re
import sys
import threading
import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox

try:
    import customtkinter as ctk
except ImportError:
    ctk = None

from .config import (
    APP_ROOT, ASSETS_DIR, DEFAULT_LATTICE_STEP, FIT_TEMPLATES,
    FONT_DIR, GNUPLOT_TEMPLATE, INPUT_DIR, LIBRARY_PATH, OUTPUT_DIR,
    RESULT_DIR, SNAPSHOT_DIR, resolve_gulp_executable,
)
from .engine import (
    _format_graph_math, centered_lattice_values, fit_model, generate_results,
    get_template_initial_values, lattice_values, render_plot,
)

BASE_DIR = APP_ROOT
REGULAR_FONT = "IBM Plex Sans"
LIGHT_FONT = "IBM Plex Sans Light"
SEMIBOLD_FONT = "IBM Plex Sans SemiBold"


def _font_path(filename):
    return os.fspath(FONT_DIR / filename)


def _register_windows_font(font_path):
    """Register a bundled font for this process on Windows."""
    if sys.platform != "win32" or not os.path.isfile(font_path):
        return
    try:
        import ctypes
        add_font = ctypes.windll.gdi32.AddFontResourceExW
        add_font.argtypes = (ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_void_p)
        add_font.restype = ctypes.c_int
        add_font(os.path.abspath(font_path), 0x10, None)
    except Exception:
        # Font registration is optional; leave startup working if Windows rejects it.
        pass

def _load_app_fonts():
    """Register the bundled font faces before any Tk widgets are created."""
    for filename in ("IBMPlexSans-Regular.ttf", "IBMPlexSans-Light.ttf",
                     "IBMPlexSans-SemiBold.ttf"):
        _register_windows_font(_font_path(filename))

def _set_default_tk_font(root):
    """Use the bundled regular face while preserving Tk's platform font sizes."""
    for font_name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont",
                      "TkCaptionFont", "TkSmallCaptionFont", "TkIconFont", "TkTooltipFont"):
        try:
            tkfont.nametofont(font_name, root=root).configure(family=REGULAR_FONT)
        except tk.TclError:
            pass

class GulpChatApp:
    def __init__(self, root):
        self.root = root
        self.root.title("AtomLite")
        self.root.geometry("1100x760")
        self.root.minsize(900, 620)
        self.root.configure(fg_color="#ffffff")
        _set_default_tk_font(root)
        self.latest_plot = None
        self.selected_model = "Quadratic"
        self.progress_bar = ctk.CTkProgressBar(
            root, mode="indeterminate", progress_color="#126213"
        )
        self.progress_bar.pack_forget()
        self.header = ctk.CTkFrame(root, fg_color="#ffffff")
        self.header.pack(fill="x", padx=20, pady=(20, 10))
        brand = ctk.CTkFrame(self.header, fg_color="transparent")
        brand.pack(fill="x", padx=(15, 0), pady=12)
        self.logo_image = None
        logo_path = ASSETS_DIR / "logo-small.png"
        try:
            if logo_path.is_file():
                self.logo_image = tk.PhotoImage(file=os.fspath(logo_path))
                ctk.CTkLabel(brand, image=self.logo_image, text="").pack(side="left", padx=(0, 10))
        except tk.TclError:
            pass
        ctk.CTkLabel(brand, text="Atom", text_color="#000000",
                     font=ctk.CTkFont(family=SEMIBOLD_FONT, size=28)).pack(side="left")
        ctk.CTkLabel(brand, text="Lite", text_color="#000000",
                     font=ctk.CTkFont(family=LIGHT_FONT, size=28)).pack(side="left")
        header_actions = ctk.CTkFrame(brand, fg_color="transparent")
        header_actions.pack(side="right")
        self.run_button = ctk.CTkButton(
            header_actions, text="Run", command=self.run,
            font=ctk.CTkFont(family=SEMIBOLD_FONT),
        )
        self.run_button.pack(side="left", padx=(0, 10))
        self.inputs = {}
        self.input_vars = {}
        controls = ctk.CTkFrame(root, fg_color="#ffffff")
        controls.pack(fill="x", padx=20, pady=(0, 12))
        controls.grid_columnconfigure((0, 1, 2, 3, 4, 5), weight=1)

        def add_header_entry(key, label, value, column):
            field_group = ctk.CTkFrame(controls, fg_color="transparent")
            field_group.grid(row=0, column=column, sticky="ew", padx=10, pady=12)
            ctk.CTkLabel(field_group, text=label).pack(anchor="w", pady=(0, 5))
            variable = tk.StringVar(value=value)
            entry = ctk.CTkEntry(field_group, textvariable=variable)
            entry.pack(fill="x")
            self.inputs[key] = entry
            self.input_vars[key] = variable
            variable.trace_add("write", self.mark_options_changed)

        add_header_entry("Cation", "Cation", "Mg", 0)

        mode_group = ctk.CTkFrame(controls, fg_color="transparent")
        mode_group.grid(row=0, column=1, sticky="ew", padx=10, pady=12)
        ctk.CTkLabel(mode_group, text="Range mode").pack(anchor="w", pady=(0, 5))
        self.range_mode = tk.StringVar(value="From start to end")
        self.range_mode_selector = ctk.CTkComboBox(
            mode_group, state="readonly", values=("From start to end", "From center"),
            variable=self.range_mode, command=self._range_mode_changed,
        )
        self.range_mode_selector.pack(fill="x")
        self._set_combo_arrow_white(self.range_mode_selector)

        self.primary_group = ctk.CTkFrame(controls, fg_color="transparent")
        self.primary_group.grid(row=0, column=2, sticky="ew", padx=10, pady=12)
        self.primary_label = ctk.CTkLabel(self.primary_group, text="From")
        self.primary_label.pack(anchor="w", pady=(0, 5))
        self._add_range_entry("Beginning lattice constant", "4.17", self.primary_group)
        self._add_range_entry("Center lattice constant", "4.20", self.primary_group)

        self.secondary_group = ctk.CTkFrame(controls, fg_color="transparent")
        self.secondary_group.grid(row=0, column=3, sticky="ew", padx=10, pady=12)
        self.secondary_label = ctk.CTkLabel(self.secondary_group, text="To")
        self.secondary_label.pack(anchor="w", pady=(0, 5))
        self._add_range_entry("Ending lattice constant", "4.24", self.secondary_group)
        self._add_range_entry("Count", "10", self.secondary_group)
        self._range_mode_changed(self.range_mode.get(), invalidate=False)

        add_header_entry("Step size", "Step", f"{DEFAULT_LATTICE_STEP:g}", 4)

        model_group = ctk.CTkFrame(controls, fg_color="transparent")
        model_group.grid(row=0, column=5, sticky="ew", padx=10, pady=12)
        ctk.CTkLabel(model_group, text="Fit model").pack(anchor="w", pady=(0, 5))
        self.algorithm_selector = ctk.CTkComboBox(
            model_group, state="readonly", values=tuple(FIT_TEMPLATES), command=self.select_model,
        )
        self.algorithm_selector.set(self.selected_model)
        self.algorithm_selector.pack(fill="x")
        self._set_combo_arrow_white(self.algorithm_selector)

        self.status = tk.StringVar(value="")
        self.status_label = ctk.CTkLabel(controls, textvariable=self.status, anchor="w")
        self.status_label.grid(row=1, column=0, columnspan=6, sticky="ew", padx=20, pady=(0, 12))
        self.status.trace_add("write", self._sync_status_visibility)
        self.status_label.grid_remove()

        self.plot_frame = ctk.CTkFrame(root, fg_color="#ffffff")
        self.plot_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self.plot_frame.columnconfigure(0, weight=1)
        self.plot_frame.columnconfigure(1, weight=0, minsize=300)
        self.plot_frame.rowconfigure(0, weight=1)
        self.graph = tk.Canvas(self.plot_frame, bg="white", highlightthickness=0, bd=0)
        self.graph.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)
        self.plot_sidebar = ctk.CTkFrame(self.plot_frame, width=300, fg_color="#ffffff")
        self.plot_sidebar.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=10)
        self.plot_sidebar.grid_propagate(False)
        self.structure_frame = ctk.CTkFrame(self.plot_sidebar, fg_color="#ffffff")
        self.structure_frame.pack(side="bottom", fill="both", expand=True, padx=10, pady=(10, 0))
        self.structure_canvas = tk.Canvas(self.structure_frame, bg="white", highlightthickness=0, bd=0)
        self.structure_canvas.pack(fill="both", expand=True, padx=5, pady=(5, 0))
        self.structure_atoms = []
        self.structure_cell_length = 1.0
        self.structure_radii = {}
        self.structure_element = None
        self.structure_rotation = [0.65, 0.45]
        self.structure_pan = [0.0, 0.0]
        self._structure_drag = None
        self._structure_pan_drag = None
        self._structure_atom_screen = []
        self.structure_canvas.bind("<Motion>", self._show_structure_coordinates)
        self.structure_canvas.bind("<Configure>", lambda _event: self.draw_structure())
        self.structure_canvas.bind("<ButtonPress-1>", self._start_structure_rotation)
        self.structure_canvas.bind("<B1-Motion>", self._rotate_structure)
        self.structure_canvas.bind("<ButtonPress-2>", self._start_structure_pan)
        self.structure_canvas.bind("<B2-Motion>", self._pan_structure)
        self.structure_canvas.configure(cursor="fleur")
        self.draw_structure()

        self.graph.bind("<Configure>", lambda _event: self.redraw_graph())

    def _sync_status_visibility(self, *_args):
        if self.status.get():
            self.status_label.grid()
        else:
            self.status_label.grid_remove()

    def _set_combo_arrow_white(self, combo):
        def recolor(_event=None):
            try:
                combo._canvas.itemconfigure("dropdown_arrow", fill="#ffffff")
            except tk.TclError:
                pass

        combo.bind("<Configure>", lambda _event: combo.after_idle(recolor), add="+")
        combo.after_idle(recolor)

    def _add_range_entry(self, key, value, parent):
        variable = tk.StringVar(value=value)
        entry = ctk.CTkEntry(parent, textvariable=variable)
        entry.pack(fill="x")
        self.inputs[key] = entry
        self.input_vars[key] = variable
        variable.trace_add("write", self.mark_options_changed)

    def _range_mode_changed(self, mode, invalidate=True):
        center_mode = mode == "From center"
        if center_mode:
            self.inputs["Beginning lattice constant"].pack_forget()
            self.inputs["Center lattice constant"].pack(fill="x")
            self.inputs["Ending lattice constant"].pack_forget()
            self.inputs["Count"].pack(fill="x")
            self.primary_label.configure(text="Center")
            self.secondary_label.configure(text="Count")
        else:
            self.inputs["Center lattice constant"].pack_forget()
            self.inputs["Beginning lattice constant"].pack(fill="x")
            self.inputs["Count"].pack_forget()
            self.inputs["Ending lattice constant"].pack(fill="x")
            self.primary_label.configure(text="From")
            self.secondary_label.configure(text="To")
        if invalidate:
            self.mark_options_changed()

    def _start_progress(self):
        self.progress_bar.place(relx=0.02, rely=0.01, relwidth=0.96, anchor="nw")
        self.progress_bar.start()

    def _stop_progress(self):
        self.progress_bar.stop()
        self.progress_bar.place_forget()

    @staticmethod
    def _load_cif_atoms(cif_path):
        atoms = []
        try:
            with open(cif_path, "r", encoding="utf-8") as cif:
                lines = iter(cif)
                for line in lines:
                    if line.strip().lower() != "loop_":
                        continue
                    headers = []
                    for header_line in lines:
                        header = header_line.strip()
                        if not header.startswith("_"):
                            first_row = header
                            break
                        headers.append(header.split()[0])
                    else:
                        break
                    required = ("_atom_site_label", "_atom_site_fract_x",
                                "_atom_site_fract_y", "_atom_site_fract_z")
                    if not all(name in headers for name in required):
                        continue
                    indices = [headers.index(name) for name in required]
                    row = first_row
                    while row and not row.startswith("_") and row.lower() != "loop_":
                        values = row.split()
                        if len(values) > max(indices):
                            label, *coords = (values[index] for index in indices)
                            atoms.append((label, *(float(value) for value in coords)))
                        try:
                            row = next(lines).strip()
                        except StopIteration:
                            row = ""
                    if atoms:
                        break
        except (OSError, ValueError):
            return []
        return atoms

    @staticmethod
    def _load_cif_cell_length(cif_path):
        try:
            with open(cif_path, "r", encoding="utf-8") as cif:
                for line in cif:
                    match = re.match(r"\s*_cell_length_a\s+([0-9.eE+-]+)", line)
                    if match:
                        return float(match.group(1))
        except (OSError, ValueError):
            pass
        return 1.0

    @staticmethod
    def _load_gulp_covalent_radii(got_path):
        radii = {}
        try:
            with open(got_path, "r", encoding="utf-8", errors="replace") as output:
                for line in output:
                    match = re.match(
                        r"\s*([A-Za-z]{1,2})\s+Core\s+\d+\s+\S+\s+\S+\s+([0-9.]+)",
                        line,
                    )
                    if match:
                        radii[match.group(1).lower()] = float(match.group(2))
        except OSError:
            pass
        return radii

    def draw_structure(self):
        canvas = self.structure_canvas
        canvas.delete("all")
        self._structure_atom_screen = []
        width, height = canvas.winfo_width(), canvas.winfo_height()
        if width < 20 or height < 20:
            return
        if not self.structure_atoms:
            return

        # Build a periodic 3x3x3 neighborhood, then retain complete octahedra
        # around the central region (14 centers, 43 O sites, 84 bonds for MgO).
        atoms = []
        for tx in range(3):
            for ty in range(3):
                for tz in range(3):
                    atoms.extend((label, x + tx, y + ty, z + tz)
                                 for label, x, y, z in self.structure_atoms)
        oxygen_atoms = [atom for atom in atoms
                        if re.sub(r"\d+$", "", atom[0]).lower() == "o"]
        cation_atoms = [atom for atom in atoms
                        if re.sub(r"\d+$", "", atom[0]).lower() != "o"]
        polyhedra = []
        visible = {}
        for metal in cation_atoms:
            label, mx, my, mz = metal
            neighbors = []
            for oxygen in oxygen_atoms:
                _olabel, ox, oy, oz = oxygen
                distance_sq = (mx - ox) ** 2 + (my - oy) ** 2 + (mz - oz) ** 2
                if 0.24 <= distance_sq <= 0.26:
                    neighbors.append(oxygen)
            central_distance_sq = sum((value - 1.5) ** 2 for value in (mx, my, mz))
            if len(neighbors) == 6 and central_distance_sq <= 1.000001:
                polyhedra.append((metal, neighbors))
                visible[metal] = metal
                for oxygen in neighbors:
                    visible[oxygen] = oxygen

        # Standard isometric projection, centered and fitted around the cluster.
        iso = ((0.7071, -0.4082), (-0.7071, -0.4082), (0.0, 0.8165))
        yaw, pitch = self.structure_rotation
        view_center = 1.5

        def rotate(coords):
            x, y, z = (value - view_center for value in coords)
            cy, sy = math.cos(yaw), math.sin(yaw)
            cp, sp_ = math.cos(pitch), math.sin(pitch)
            x, y = cy * x - sy * y, sy * x + cy * y
            y, z = cp * y - sp_ * z, sp_ * y + cp * z
            return x, y, z

        def project_raw(coords):
            x, y, z = rotate(coords)
            return (x * iso[0][0] + y * iso[1][0] + z * iso[2][0],
                    x * iso[0][1] + y * iso[1][1] + z * iso[2][1])

        projected = [project_raw(atom[1:]) for atom in visible.values()]
        if not projected:
            return
        min_x, max_x = min(p[0] for p in projected), max(p[0] for p in projected)
        min_y, max_y = min(p[1] for p in projected), max(p[1] for p in projected)
        margin = 24
        scale = min((width - 2 * margin) / max(max_x - min_x, 1e-6),
                    (height - 2 * margin - 24) / max(max_y - min_y, 1e-6))
        center_x, center_y = width / 2, (height + 20) / 2

        def point3d(coords):
            x, y = project_raw(coords)
            return (center_x + scale * (x - (min_x + max_x) / 2) + self.structure_pan[0],
                    center_y - scale * (y - (min_y + max_y) / 2) + self.structure_pan[1])

        cation_color = "#126213"
        oxygen_color = "#4A4A4A"
        colors = {"mg": cation_color, "sr": cation_color, "o": oxygen_color}
        for metal, neighbors in polyhedra:
            center = point3d(metal[1:])
            projected_neighbors = [point3d(site[1:]) for site in neighbors]
            for first in range(6):
                for second in range(first + 1, 6):
                    a, b = neighbors[first][1:], neighbors[second][1:]
                    if sum((a[i] - b[i]) ** 2 for i in range(3)) <= 0.51:
                        canvas.create_polygon(
                            *center, *projected_neighbors[first], *projected_neighbors[second],
                            fill="#e7f2e7", outline=cation_color, width=1,
                        )
            for oxygen in neighbors:
                canvas.create_line(*center, *point3d(oxygen[1:]), fill=cation_color,
                                   width=3, capstyle=tk.ROUND)

        atom_draw_data = []
        for label, x, y, z in visible.values():
            _rx, _ry, rz = rotate((x, y, z))
            atom_draw_data.append((rz, label, x, y, z))
        for _depth, label, x, y, z in sorted(atom_draw_data):
            px, py = point3d((x, y, z))
            self._structure_atom_screen.append((px, py, label, x % 1.0, y % 1.0, z % 1.0))
            element = re.sub(r"\d+$", "", label).lower()
            covalent_radius = self.structure_radii.get(element, 0.8)
            radius = max(2, scale * covalent_radius / self.structure_cell_length)
            color = colors.get(element, cation_color if element != "o" else oxygen_color)
            canvas.create_oval(px-radius, py-radius, px+radius, py+radius,
                               fill=color, outline="#ffffff", width=1.2)
            canvas.create_oval(px-radius * 0.58, py-radius * 0.67,
                               px-radius * 0.12, py-radius * 0.22,
                               fill="#ffffff", outline="")
        legend_y = height - 15
        legend_x = 12
        for element in dict.fromkeys(re.sub(r"\d+$", "", atom[0]) for atom in self.structure_atoms):
            color = colors.get(element.lower(), cation_color if element.lower() != "o" else oxygen_color)
            canvas.create_oval(legend_x, legend_y - 7, legend_x + 14, legend_y + 7,
                               fill=color, outline="")
            canvas.create_text(legend_x + 21, legend_y, text=element, anchor="w",
                               fill="#000000", font=(REGULAR_FONT, 13))
            legend_x += 76

        # Orientation triad follows the current rotation.
        axis_origin = (width - 42, height - 34)
        axis_length = 24
        for axis, coords, color in (("X", (2.0, 1.5, 1.5), "#dc2626"),
                                    ("Y", (1.5, 2.0, 1.5), "#16a34a"),
                                    ("Z", (1.5, 1.5, 2.0), "#2563eb")):
            endpoint = point3d(coords)
            dx, dy = endpoint[0] - point3d((1.5, 1.5, 1.5))[0], endpoint[1] - point3d((1.5, 1.5, 1.5))[1]
            norm = max(math.hypot(dx, dy), 1e-6)
            ex = axis_origin[0] + axis_length * dx / norm
            ey = axis_origin[1] + axis_length * dy / norm
            canvas.create_line(*axis_origin, ex, ey, fill=color, width=2.5, arrow=tk.LAST)
            canvas.create_text(ex, ey, text=axis, fill=color, font=(SEMIBOLD_FONT, 11))

    def _show_structure_coordinates(self, event):
        nearest = min(self._structure_atom_screen,
                      key=lambda atom: (atom[0] - event.x) ** 2 + (atom[1] - event.y) ** 2,
                      default=None)
        self.structure_canvas.delete("coordinate_readout")
        if nearest and (nearest[0] - event.x) ** 2 + (nearest[1] - event.y) ** 2 <= 18 ** 2:
            _px, _py, label, x, y, z = nearest
            self.structure_canvas.create_text(
                12, 12, text=f"{label}: ({x:.3f}, {y:.3f}, {z:.3f})", anchor="nw",
                fill="#000000", font=(REGULAR_FONT, 12), tags="coordinate_readout",
            )

    def _start_structure_pan(self, event):
        self._structure_pan_drag = (event.x, event.y, *self.structure_pan)

    def _pan_structure(self, event):
        if self._structure_pan_drag is None:
            return
        start_x, start_y, start_pan_x, start_pan_y = self._structure_pan_drag
        self.structure_pan[0] = start_pan_x + event.x - start_x
        self.structure_pan[1] = start_pan_y + event.y - start_y
        self.draw_structure()

    def _start_structure_rotation(self, event):
        self._structure_drag = (event.x, event.y, *self.structure_rotation)

    def _rotate_structure(self, event):
        if self._structure_drag is None:
            return
        start_x, start_y, start_yaw, start_pitch = self._structure_drag
        self.structure_rotation[0] = start_yaw + (event.x - start_x) * 0.012
        self.structure_rotation[1] = max(-1.45, min(1.45, start_pitch + (event.y - start_y) * 0.012))
        self.draw_structure()

    def select_model(self, model):
        if model == self.selected_model:
            return
        self.selected_model = model
        self.update_algorithm_buttons()
        self.mark_options_changed()

    def mark_options_changed(self, *_args):
        """Clear previous run status when inputs change."""
        self.status.set("")

    def update_algorithm_buttons(self):
        self.algorithm_selector.set(self.selected_model)

    def run(self):
        try:
            gulp_executable = resolve_gulp_executable()
            raw_element = self.inputs["Cation"].get().strip()
            if not re.fullmatch(r"[A-Za-z]{1,2}", raw_element):
                raise ValueError("Enter an element symbol, such as Mg, Sr, or Ca.")
            element = raw_element[0].upper() + raw_element[1:].lower()
            if element not in self._library_cations():
                raise ValueError(f"{element} is not listed in the GULP potential library.")
            step = float(self.inputs["Step size"].get())
            model = self.selected_model
            mode = self.range_mode.get()
            if mode == "From center":
                center = float(self.inputs["Center lattice constant"].get())
                latitudes = centered_lattice_values(
                    center, self.inputs["Count"].get(), step
                )
            else:
                start_lat = float(self.inputs["Beginning lattice constant"].get())
                end_lat = float(self.inputs["Ending lattice constant"].get())
                latitudes = lattice_values(start_lat, end_lat, step)
            start_lat, end_lat = latitudes[0], latitudes[-1]
            minimum = {"Linear": 2, "Quadratic": 3, "Third order": 4, "Murnaghan EOS": 4}[model]
            count = len(latitudes)
            if count < minimum:
                raise ValueError(f"This range produces {count} points; {model} needs at least {minimum}.")
        except ValueError as exc:
            self.status.set(f"Invalid input: {exc}")
            return
        self.run_button.configure(state="disabled")
        run_inputs = (element, mode)
        uv_path = os.path.join(RESULT_DIR, f"{element.lower()}o-uv.txt")
        signature_path = f"{uv_path}.settings"
        values_signature = ",".join(format(value.normalize(), "f") for value in latitudes)
        expected_signature = f"{element}|{mode}|{step:.12g}|{values_signature}"
        try:
            with open(signature_path, "r", encoding="utf-8") as signature_file:
                saved_signature = signature_file.read().strip()
            with open(uv_path, "r", encoding="utf-8") as existing:
                actual_rows = sum(1 for line in existing if line.strip()) - 1
            regenerate = saved_signature != expected_signature or actual_rows != count
        except OSError:
            regenerate = True
        self.status.set("")
        self._start_progress()
        threading.Thread(target=self.work,
                         args=(element, start_lat, end_lat, step, latitudes, count, model,
                               regenerate, expected_signature, gulp_executable),
                         daemon=True).start()

    @staticmethod
    def _library_cations():
        symbols = set()
        in_species = False
        try:
            with open(LIBRARY_PATH, "r", encoding="utf-8") as library:
                for line in library:
                    fields = line.split()
                    if not fields or fields[0].startswith("#"):
                        continue
                    if fields[0].lower() == "species":
                        in_species = True
                        continue
                    if in_species:
                        if fields[0].lower() in {"buckingham", "spring", "morse", "threebody"}:
                            break
                        if len(fields) >= 2 and fields[1].lower() in {"core", "shel", "shell"}:
                            symbols.add(fields[0])
        except OSError:
            pass
        return symbols

    def work(self, element, start_lat, end_lat, step, latitudes, count, model,
             regenerate, signature, gulp_executable):
        try:
            stem = f"{element.lower()}o"
            gin_path = os.path.join(INPUT_DIR, stem + ".gin")
            uv_path = os.path.join(RESULT_DIR, f"{stem}-uv.txt")
            if regenerate:
                gin_path, uv_path, _ = generate_results(
                    element, start_lat, end_lat, gulp_executable,
                    step=step, lattice_points=latitudes,
                )
                with open(f"{uv_path}.settings", "w", encoding="utf-8") as signature_file:
                    signature_file.write(signature + "\n")
            elif not os.path.exists(gin_path):
                raise FileNotFoundError(f"Input file not found: {gin_path}")
            template_path = GNUPLOT_TEMPLATE
            settings, points = render_plot(GNUPLOT_TEMPLATE, uv_path)
            selected_fit_template = FIT_TEMPLATES[model]
            fit_path = os.path.join(OUTPUT_DIR, f"{stem}-fit.txt")
            initial_values, _resolved_template = get_template_initial_values(
                selected_fit_template, uv_path, model
            )
            evaluate, equation, parameters = fit_model(points, model, selected_fit_template, fit_path)
            with open(fit_path, "w", encoding="utf-8") as saved:
                saved.write(f"model = {model}\n")
                for name, value in parameters.items():
                    saved.write(f"{name} = {value:.12g}\n")
            self.root.after(0, self.finished, gin_path, uv_path, selected_fit_template,
                            settings, points, evaluate, equation, fit_path, initial_values, parameters,
                            (element, start_lat, end_lat, step, count))
        except Exception as exc:
            logging.exception("Calculation failed for element %s", element)
            self.root.after(0, self.failed, str(exc))

    def finished(self, gin_path, uv_path, template_path, settings, points, evaluate, equation, fit_path, initial_values, parameters, run_inputs):
        self._stop_progress()
        element = run_inputs[0]
        bulk_modulus = self.bulk_modulus_gpa(self.selected_model, parameters, points)
        self.latest_plot = (settings, points, evaluate, equation, bulk_modulus)
        self.draw_graph(settings, points, evaluate, equation, bulk_modulus)
        self.structure_element = element
        cif_path = SNAPSHOT_DIR / f"{element.lower()}o.cif"
        got_path = OUTPUT_DIR / f"{element.lower()}o.got"
        self.structure_atoms = self._load_cif_atoms(cif_path)
        self.structure_cell_length = self._load_cif_cell_length(cif_path)
        self.structure_radii = self._load_gulp_covalent_radii(got_path)
        self.draw_structure()
        self.status.set("")
        self.run_button.configure(state="normal")

    @staticmethod
    def bulk_modulus_gpa(model, fitted, points):
        """Return bulk modulus in GPa when the fitted model has a stable minimum."""
        conversion = 160.21766208  # eV/Angstrom^3 to GPa
        if model == "Murnaghan EOS":
            return fitted["B0"] * conversion if fitted["B0"] > 0 else None
        if model == "Quadratic" and fitted["a2"] > 0:
            v0 = -fitted["a1"] / (2 * fitted["a2"])
            return v0 * 2 * fitted["a2"] * conversion if v0 > 0 else None
        if model == "Third order":
            a, b, c = fitted["A"], fitted["B"], fitted["C"]
            volumes = [volume for volume, _energy in points]
            if not volumes:
                return None
            minimum_volume, maximum_volume = min(volumes), max(volumes)
            # Stationary volumes solve dE/dV = 3 A V^2 + 2 B V + C = 0.
            qa, qb, qc = 3 * a, 2 * b, c
            tolerance = 1e-12 * max(abs(qa), abs(qb), abs(qc), 1.0)
            if abs(qa) <= tolerance:
                roots = [-qc / qb] if abs(qb) > tolerance else []
            else:
                discriminant = qb * qb - 4 * qa * qc
                if discriminant < 0:
                    roots = []
                else:
                    root_discriminant = math.sqrt(discriminant)
                    q = -0.5 * (qb + math.copysign(root_discriminant, qb))
                    roots = ([q / qa, qc / q] if q else [-qb / (2 * qa)])
            for v0 in sorted(set(roots)):
                curvature = 6 * a * v0 + 2 * b
                if minimum_volume <= v0 <= maximum_volume and v0 > 0 and curvature > 0:
                    return v0 * curvature * conversion
        return None

    def draw_graph(self, settings, points, evaluate, equation, bulk_modulus=None):
        canvas = self.graph
        canvas.delete("all")
        canvas.update_idletasks()
        width, height = max(canvas.winfo_width(), 500), max(canvas.winfo_height(), 330)
        left_margin, right_margin = 125, 35
        top_margin, bottom_margin = 96, 80
        available_width = max(100, width - left_margin - right_margin)
        available_height = max(100, height - top_margin - bottom_margin)
        plot_width = min(available_width, available_height * 1.45)
        plot_height = plot_width / 1.45
        left = left_margin + (available_width - plot_width) / 2
        right = left + plot_width
        top = top_margin + (available_height - plot_height) / 2
        bottom = top + plot_height
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        xmin, xmax = min(xs), max(xs)
        if xmin == xmax:
            xmin, xmax = xmin - 0.5, xmax + 0.5
        fitted = [evaluate(x) for x in xs]
        ymin, ymax = min(min(ys), min(fitted)), max(max(ys), max(fitted))
        if ymin == ymax:
            ymin, ymax = ymin - 0.5, ymax + 0.5
        padx, pady = (xmax - xmin) * 0.05, (ymax - ymin) * 0.12
        xmin, xmax, ymin, ymax = xmin - padx, xmax + padx, ymin - pady, ymax + pady
        xmap = lambda x: left + (x - xmin) / (xmax - xmin) * (right - left)
        ymap = lambda y: bottom - (y - ymin) / (ymax - ymin) * (bottom - top)
        if settings["grid"]:
            for index in range(6):
                x = left + index * (right - left) / 5
                y = top + index * (bottom - top) / 5
                canvas.create_line(x, top, x, bottom, fill="#dbeafe")
                canvas.create_line(left, y, right, y, fill="#dbeafe")
        canvas.create_line(left, top, left, bottom, fill="#000000")
        canvas.create_line(left, bottom, right, bottom, fill="#000000")
        for index in range(6):
            xv = xmin + index * (xmax - xmin) / 5
            yv = ymin + index * (ymax - ymin) / 5
            x = left + index * (right - left) / 5
            y = bottom - index * (bottom - top) / 5
            canvas.create_text(x, bottom + 20, text=f"{xv:.3g}", fill="#000000", font=(REGULAR_FONT, 13))
            canvas.create_text(left - 16, y, text=f"{yv:.5g}", fill="#000000", anchor="e", font=(REGULAR_FONT, 13))
        radius = settings["pointsize"]
        for x, y in points:
            px, py = xmap(x), ymap(y)
            canvas.create_oval(px-radius, py-radius, px+radius, py+radius,
                               fill=settings["color"], outline=settings["color"])
        curve = []
        for index in range(101):
            x = xmin + index * (xmax - xmin) / 100
            curve.extend((xmap(x), ymap(evaluate(x))))
        canvas.create_line(*curve, fill="#dc2626", width=2, smooth=True)
        legend_x = right - 112
        legend_y = top + 18
        canvas.create_oval(legend_x, legend_y - 5, legend_x + 10, legend_y + 5,
                           fill=settings["color"], outline=settings["color"])
        canvas.create_text(legend_x + 17, legend_y, text="Data", anchor="w",
                           fill="#000000", font=(REGULAR_FONT, 12))
        fit_y = legend_y + 22
        canvas.create_line(legend_x - 1, fit_y, legend_x + 12, fit_y,
                           fill="#dc2626", width=2.5)
        canvas.create_text(legend_x + 17, fit_y, text="Fit", anchor="w",
                           fill="#000000", font=(REGULAR_FONT, 12))
        canvas.create_text((left + right) / 2, 18, text=settings["title"],
                           fill="#000000", font=(SEMIBOLD_FONT, 15))
        xlabel = _format_graph_math(settings["xlabel"])
        canvas.create_text((left + right) / 2, height - 15, text=xlabel,
                           fill="#000000", font=(REGULAR_FONT, 14))
        canvas.create_text(20, (top + bottom) / 2, text=settings["ylabel"],
                           fill="#000000", font=(REGULAR_FONT, 14), angle=90)
        canvas.create_text((left + right) / 2, 49, text=_format_graph_math(equation),
                           fill="#000000", font=(REGULAR_FONT, 13))
        if bulk_modulus is not None:
            canvas.create_text((left + right) / 2, 78,
                               text=f"Bulk modulus = {bulk_modulus:.8g} GPa",
                               fill="#000000", font=(REGULAR_FONT, 13))

    def redraw_graph(self):
        if self.latest_plot:
            self.draw_graph(*self.latest_plot)

    def failed(self, message):
        self._stop_progress()
        self.status.set(f"Run failed: {message}")
        self.run_button.configure(state="normal")

def main():
    if ctk is None:
        messagebox.showerror(
            "CustomTkinter is required",
            "Install the app dependencies with:\n"
            f'"{sys.executable}" -m pip install -r "{os.path.join(BASE_DIR, "requirements.txt")}"',
        )
        return
    _load_app_fonts()
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")
    ctk.ThemeManager.theme["CTkFont"]["family"] = REGULAR_FONT
    ctk.ThemeManager.theme["CTkButton"]["fg_color"] = ["#126213", "#126213"]
    ctk.ThemeManager.theme["CTkButton"]["hover_color"] = ["#0F5110", "#0F5110"]
    ctk.ThemeManager.theme["CTkComboBox"]["button_color"] = ["#126213", "#126213"]
    ctk.ThemeManager.theme["CTkComboBox"]["button_hover_color"] = ["#0F5110", "#0F5110"]
    try:
        root = ctk.CTk()
    except tk.TclError as exc:
        message = (
            "Tk could not start because this Python installation has mismatched Tcl/Tk files.\n\n"
            f"{exc}\n\n"
            "Install or repair Python with its Tcl/Tk (Tkinter) component, then launch again."
        )
        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.user32.MessageBoxW(
                    None, message, "AtomLite could not start", 0x10 | 0x10000 | 0x40000
                )
            except Exception:
                print(message, file=sys.stderr)
        else:
            print(message, file=sys.stderr)
        return
    try:
        icon_path = ASSETS_DIR / "app.ico"
        if icon_path.is_file():
            root.iconbitmap(default=os.fspath(icon_path))
        else:
            icon_path = ASSETS_DIR / "logo-small.png"
            if not icon_path.is_file():
                raise FileNotFoundError(icon_path)
            icon = tk.PhotoImage(file=os.fspath(icon_path))
            root.iconphoto(True, icon)
            root._app_icon = icon
    except (OSError, tk.TclError):
        # Window decoration support varies by Tk platform; branding is optional.
        pass
    GulpChatApp(root)
    root.mainloop()
