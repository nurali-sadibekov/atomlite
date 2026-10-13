"""GULP execution, energy-volume data handling, and EOS fitting."""

import math
import os
import re
import shlex
import shutil
import subprocess
from decimal import Decimal, InvalidOperation

from .config import (
    APP_ROOT, CATION_SITES, DEFAULT_LATTICE_STEP, FIT_TEMPLATES, GNUPLOT_TEMPLATE,
    GULP_TIMEOUT_SECONDS,
    INPUT_DIR, LIBRARY_PATH, OUTPUT_DIR, OXYGEN_SITES, RESULT_DIR, SNAPSHOT_DIR,
)

def lattice_values(start_lat, end_lat, step=DEFAULT_LATTICE_STEP):
    try:
        start = Decimal(str(start_lat))
        end = Decimal(str(end_lat))
        increment = Decimal(str(step))
    except InvalidOperation as exc:
        raise ValueError("Lattice values and step must be valid numbers.") from exc
    if not all(value.is_finite() for value in (start, end, increment)):
        raise ValueError("Lattice values and step must be finite numbers.")
    if increment <= 0:
        raise ValueError("Step size must be greater than zero.")
    if end <= start:
        raise ValueError("Ending lattice constant must be greater than the beginning value.")
    intervals = (end - start) / increment
    if intervals != intervals.to_integral_value():
        raise ValueError("The range must be evenly divisible by the step size.")
    return [start + increment * index for index in range(int(intervals) + 1)]

def centered_lattice_values(center, count, step=DEFAULT_LATTICE_STEP):
    try:
        center_value = Decimal(str(center))
        increment = Decimal(str(step))
        count_value = Decimal(str(count))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("Center, step, and number of values must be valid numbers.") from exc
    if not center_value.is_finite() or not count_value.is_finite():
        raise ValueError("Center and count must be finite numbers.")
    if not increment.is_finite() or increment <= 0:
        raise ValueError("Step size must be greater than zero.")
    if count_value != count_value.to_integral_value():
        raise ValueError("Count must be a whole number.")
    count = int(count_value)
    if count < 1:
        raise ValueError("Count must be at least 1.")
    if count == 1:
        return [center_value]
    half_count = count // 2
    values = lattice_values(center_value - half_count * increment,
                             center_value + half_count * increment, increment)
    if count % 2 == 0:
        values.remove(center_value)
    return values

def _gp_string(value):
    try:
        return shlex.split(value)[0]
    except (ValueError, IndexError):
        return value.strip("'\"")

def render_plot(template_path, data_path):
    """Read supported plot settings and numeric points for the in-app renderer."""
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Gnuplot command template not found: {template_path}")
    settings = {"title": "", "xlabel": "", "ylabel": "", "grid": False,
                "color": "#126213", "pointsize": 5, "using": (2, 3)}
    with open(template_path, "r", encoding="utf-8") as template:
        for line in template:
            command = line.strip()
            if not command or command.startswith("#"):
                continue
            if command.startswith("set title "):
                settings["title"] = _gp_string(command[len("set title "):])
            elif command.startswith("set xlabel "):
                settings["xlabel"] = _gp_string(command[len("set xlabel "):])
            elif command.startswith("set ylabel "):
                settings["ylabel"] = _gp_string(command[len("set ylabel "):])
            elif command == "set grid":
                settings["grid"] = True
            elif command.startswith("plot "):
                match = re.search(r"using\s+(\d+):(\d+)", command)
                color = re.search(r"linecolor\s+rgb\s+['\"]([^'\"]+)", command)
                size = re.search(r"pointsize\s+([0-9.]+)", command)
                if match:
                    settings["using"] = tuple(map(int, match.groups()))
                if color:
                    settings["color"] = color.group(1)
                if size:
                    settings["pointsize"] = max(2, min(12, float(size.group(1)) * 4))
    x_column, y_column = settings["using"]
    points = []
    with open(data_path, "r", encoding="utf-8") as data:
        next(data, None)
        for row in data:
            fields = row.split()
            try:
                points.append((float(fields[x_column - 1]), float(fields[y_column - 1])))
            except (ValueError, IndexError):
                continue
    if not points:
        raise ValueError("The result file has no numeric points to graph.")
    return settings, points

def polynomial_fit(points, degree):
    """Fit an order-N polynomial using scaled normal equations."""
    if len(points) < degree + 1:
        raise ValueError(f"At least {degree + 1} valid points are needed for this fit.")
    center = sum(x for x, _ in points) / len(points)
    scale = max(abs(x - center) for x, _ in points) or 1.0
    normalized = [((x - center) / scale, y) for x, y in points]
    size = degree + 1
    sums = [sum(x ** power for x, _ in normalized) for power in range(2 * degree + 1)]
    rhs = [sum(x ** power * y for x, y in normalized) for power in range(size)]
    matrix = [[sums[row + col] for col in range(size)] + [rhs[row]] for row in range(size)]
    for pivot in range(size):
        best = max(range(pivot, size), key=lambda row: abs(matrix[row][pivot]))
        matrix[pivot], matrix[best] = matrix[best], matrix[pivot]
        divisor = matrix[pivot][pivot]
        if abs(divisor) < 1e-14:
            raise ValueError("Could not fit a polynomial to these data points.")
        matrix[pivot] = [value / divisor for value in matrix[pivot]]
        for row in range(size):
            if row != pivot:
                factor = matrix[row][pivot]
                matrix[row] = [matrix[row][col] - factor * matrix[pivot][col]
                               for col in range(size + 1)]
    normalized_coefficients = [matrix[row][-1] for row in range(size)]

    # Convert from powers of t=(V-center)/scale to powers of V.
    ascending_coefficients = [0.0] * size
    import math
    for power, coefficient in enumerate(normalized_coefficients):
        for original_power in range(power + 1):
            ascending_coefficients[original_power] += (
                coefficient * math.comb(power, original_power)
                * (-center) ** (power - original_power) / scale ** power
            )
    return tuple(reversed(ascending_coefficients))

def read_initial_values(template_path, fit_path):
    values = {}
    for path in (template_path, fit_path):
        if not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8") as source:
            for line in source:
                match = re.match(r"\s*#?\s*([A-Za-z][A-Za-z0-9_]*)\s*=\s*(-?[0-9.eE+]+)", line)
                if match:
                    try:
                        values[match.group(1)] = float(match.group(2))
                    except ValueError:
                        pass
                elif line.strip().startswith("initial_values ="):
                    for name, raw in re.findall(r"([A-Za-z][A-Za-z0-9_]*):\s*(-?[0-9.eE+]+)", line):
                        values[name] = float(raw)
    return values

def _format_decimal(value, signed=False):
    """Format the full floating-point value as a decimal, never in e notation."""
    formatted = format(value, "+f" if signed else "f")
    if "." in formatted:
        formatted = formatted.rstrip("0").rstrip(".")
    return formatted

def _format_graph_math(text):
    """Use readable Unicode math glyphs in the Tk graph annotations."""
    for raw, pretty in (("V^3", "V³"), ("V^2", "V²"),
                        ("Angstrom^3", "Å³"), ("A^3", "Å³"),
                        ("E0", "E₀"), ("V0", "V₀"), ("B0", "B₀"), ("Bp", "B′")):
        text = text.replace(raw, pretty)
    return text

def _murnaghan_energy(volume, e0, v0, b0, bp):
    if abs(bp - 1.0) < 1e-8 or volume <= 0 or v0 <= 0:
        return float("inf")
    try:
        return e0 + (b0 * volume / bp) * (((v0 / volume) ** bp) / (bp - 1.0) + 1.0) - (v0 * b0) / (bp - 1.0)
    except (OverflowError, ZeroDivisionError):
        return float("inf")

def _birch_murnaghan_energy(volume, e0, v0, b0, bp):
    if volume <= 0 or v0 <= 0:
        return float("inf")
    try:
        eta = (v0 / volume) ** (2.0 / 3.0)
        strain = eta - 1.0
        return e0 + (9.0 / 16.0) * b0 * v0 * (
            strain**3 * bp + strain**2 * (6.0 - 4.0 * eta)
        )
    except (OverflowError, ZeroDivisionError):
        return float("inf")

def _solve_linear(matrix, rhs):
    matrix = [row[:] + [value] for row, value in zip(matrix, rhs)]
    size = len(rhs)
    for pivot in range(size):
        best = max(range(pivot, size), key=lambda row: abs(matrix[row][pivot]))
        matrix[pivot], matrix[best] = matrix[best], matrix[pivot]
        divisor = matrix[pivot][pivot]
        if abs(divisor) < 1e-25:
            return [0.0] * size
        matrix[pivot] = [value / divisor for value in matrix[pivot]]
        for row in range(size):
            if row != pivot:
                factor = matrix[row][pivot]
                matrix[row] = [matrix[row][col] - factor * matrix[pivot][col] for col in range(size + 1)]
    return [matrix[row][-1] for row in range(size)]

def _fit_eos(points, initial, energy_function, avoid_unit_pressure_derivative=False):
    params = list(initial)
    for _ in range(120):
        residual = [y - energy_function(x, *params) for x, y in points]
        jacobian = []
        for x, _ in points:
            row = []
            for index, value in enumerate(params):
                delta = max(abs(value) * 1e-5, 1e-6)
                plus, minus = params.copy(), params.copy()
                plus[index] += delta
                minus[index] -= delta
                row.append((energy_function(x, *plus) - energy_function(x, *minus)) / (2 * delta))
            jacobian.append(row)
        normal = [[sum(row[i] * row[j] for row in jacobian) for j in range(4)] for i in range(4)]
        rhs = [sum(row[i] * r for row, r in zip(jacobian, residual)) for i in range(4)]
        damping = 1e-8
        for i in range(4):
            normal[i][i] += damping * max(normal[i][i], 1.0)
        delta = _solve_linear(normal, rhs)
        old_error = sum(r*r for r in residual)
        factor = 1.0
        for _attempt in range(16):
            candidate = [p + factor*d for p, d in zip(params, delta)]
            valid = (candidate[1] > 0 and candidate[2] > 0 and candidate[3] > 0)
            if avoid_unit_pressure_derivative:
                valid = valid and abs(candidate[3] - 1) > 1e-5
            if valid:
                error = sum((y - energy_function(x, *candidate))**2 for x, y in points)
                if error < old_error:
                    params = candidate
                    break
            factor *= 0.5
        else:
            break
        if max(abs(factor*d) for d in delta) < 1e-8:
            break
    return params

def data_initial_guesses(points):
    """Estimate EOS starting parameters from the current volume-energy data."""
    quadratic = polynomial_fit(points, 2)
    a, b, c = quadratic
    if a > 0:
        v0 = max(min(-b / (2 * a), max(x for x, _ in points)), min(x for x, _ in points))
        e0 = a * v0 * v0 + b * v0 + c
        # E and V are cell quantities; V0*d2E/dV2 is B in eV/A^3.
        b0 = max(v0 * (2 * a), 1e-8)
    else:
        v0, e0 = min(points, key=lambda point: point[1])
        b0 = 0.5
    return e0, v0, b0, 4.0

def fit_model(points, model, template_path, fit_path):
    """Return fit curve coefficients, equation text, and saved parameters."""
    if model == "Linear":
        coefficients = polynomial_fit(points, 1)
        a, b = coefficients
        params = {"slope": a, "intercept": b}
        equation = f"E(V) = {_format_decimal(a)} V {_format_decimal(b, signed=True)}"
        evaluate = lambda x: a*x + b
    elif model in ("Quadratic", "Cubic"):
        degree = 2 if model == "Quadratic" else 3
        coefficients = polynomial_fit(points, degree)
        if model == "Quadratic":
            params = {"a0": coefficients[2], "a1": coefficients[1], "a2": coefficients[0]}
        else:
            params = dict(zip(("A", "B", "C", "D"), coefficients))
        terms = [f"{_format_decimal(coefficient)} V^{degree-index}" if degree-index > 1
                 else f"{_format_decimal(coefficient)} V" for index, coefficient in enumerate(coefficients[:-1])]
        terms.append(_format_decimal(coefficients[-1], signed=True))
        equation = "E(V) = " + " ".join(terms)
        evaluate = lambda x: sum(coefficient * x ** (degree-index)
                                 for index, coefficient in enumerate(coefficients))
    elif model in ("Murnaghan EOS", "Third-Order Birch-Murnaghan EOS"):
        e0, v0, b0, bp = data_initial_guesses(points)
        energy_function = (_murnaghan_energy if model == "Murnaghan EOS"
                           else _birch_murnaghan_energy)
        numeric_params = _fit_eos(
            points, [e0, v0, b0, bp], energy_function,
            avoid_unit_pressure_derivative=(model == "Murnaghan EOS"),
        )
        e0, v0, b0, bp = numeric_params
        equation = (f"E0={_format_decimal(e0)}, V0={_format_decimal(v0)}, "
                    f"B0={_format_decimal(b0)}, Bp={_format_decimal(bp)}")
        evaluate = lambda x: energy_function(x, *numeric_params)
        params = dict(zip(("E0", "V0", "B0", "Bp"), numeric_params))
    else:
        raise ValueError(f"Unsupported fit model: {model}")
    return evaluate, equation, params

def get_template_initial_values(template_path, data_path, model):
    """Read the selected Gnuplot template after deriving guesses from its UV data."""
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Fit template not found: {template_path}")
    _, points = render_plot(GNUPLOT_TEMPLATE, data_path)
    if model in ("Murnaghan EOS", "Third-Order Birch-Murnaghan EOS"):
        values = dict(zip(("E0", "V0", "B0", "Bp"), data_initial_guesses(points)))
    else:
        _, _, fitted = fit_model(points, model, template_path, "")
        names = {
            "Linear": ("M", "C"),
            "Quadratic": ("A", "B", "C"),
            "Cubic": ("A", "B", "C", "D"),
        }[model]
        if model == "Quadratic":
            values = {"A": fitted["a2"], "B": fitted["a1"], "C": fitted["a0"]}
        else:
            values = dict(zip(names, fitted.values()))

    # Resolve INITIAL_* placeholders in memory; keep the reusable source template intact.
    with open(template_path, "r", encoding="utf-8") as template:
        commands = template.read()
    for name, value in values.items():
        commands = commands.replace(f"INITIAL_{name.upper()}", f"{value:.12g}")
    return values, commands

def make_gin(element, gin_path):
    """Create a rock salt MO input file if one does not already exist."""
    # Keep the directive space-free: GULP splits unquoted library filenames.
    # Stage the bundled library under the app's working directory so this works
    # even when the installation path (or username) contains spaces.
    gulp_library = APP_ROOT / "assets" / "bush.lib"
    if LIBRARY_PATH.resolve() != gulp_library.resolve():
        gulp_library.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(LIBRARY_PATH, gulp_library)
    library_path = "assets/bush.lib"
    snapshot_path = (SNAPSHOT_DIR / f"{element.lower()}o.cif").relative_to(APP_ROOT).as_posix()
    if os.path.exists(gin_path):
        with open(gin_path, "r", encoding="utf-8") as existing:
            lines = existing.readlines()
        updated = []
        saw_library = saw_snapshot = False
        for line in lines:
            directive = line.strip().lower()
            if directive.startswith("library "):
                line = f"library {library_path}\n"
                saw_library = True
            elif directive.startswith("output cif "):
                line = f"output cif {snapshot_path}\n"
                saw_snapshot = True
            updated.append(line)
        if not saw_library:
            updated.append(f"library {library_path}\n")
        if not saw_snapshot:
            updated.append(f"output cif {snapshot_path}\n")
        with open(gin_path, "w", encoding="utf-8") as existing:
            existing.writelines(updated)
        return
    lines = [
        "single\n", "title\n",
        f"{element}O--rock salt structure (cubic): to investigate the\n",
        "total energy (U) as a function of volume (V)\n", "end\n", "cell\n",
        "  4.20 4.20 4.20 90.0 90.0 90.0\n", "fractional\n",
    ]
    for site in CATION_SITES:
        lines.append(f"{element}   core  {site}\n")
    for site in OXYGEN_SITES:
        lines.append(f"O    core  {site}\n")
    for site in CATION_SITES:
        lines.append(f"{element}   shel  {site}\n")
    for site in OXYGEN_SITES:
        lines.append(f"O    shel  {site}\n")
    lines.extend((f"library {library_path}\n", f"output cif {snapshot_path}\n"))
    with open(gin_path, "w", encoding="utf-8") as gin:
        gin.writelines(lines)

def run_single_gulp(lat, gin_path, got_path, gulp_executable):
    with open(gin_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    for index, line in enumerate(lines[:-1]):
        if line.strip().lower() == "cell":
            lines[index + 1] = f"  {lat} {lat} {lat} 90.0 90.0 90.0\n"
            break
    else:
        raise ValueError(f"Could not find 'cell' keyword in {gin_path}.")
    with open(gin_path, "w", encoding="utf-8") as f:
        f.writelines(lines)

    got_path = os.fspath(got_path)
    with open(gin_path, "r", encoding="utf-8") as gulp_input, \
            open(got_path, "w", encoding="utf-8", errors="replace") as gulp_output:
        try:
            completed = subprocess.run(
                [os.fspath(gulp_executable)], stdin=gulp_input, stdout=gulp_output,
                stderr=subprocess.STDOUT, cwd=APP_ROOT, check=False,
                timeout=GULP_TIMEOUT_SECONDS,
                creationflags=(getattr(subprocess, "CREATE_NO_WINDOW", 0)
                               if os.name == "nt" else 0),
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"GULP exceeded the {GULP_TIMEOUT_SECONDS}-second limit for lattice {lat}."
            ) from exc
    if completed.returncode != 0:
        raise RuntimeError(f"GULP failed with exit code {completed.returncode} at lattice {lat}. "
                           f"See {got_path} for details.")

    with open(got_path, "r", encoding="utf-8", errors="replace") as output:
        content = output.read()
    volume_match = re.search(r"Initial cell volume\s*=\s*([0-9.]+)", content)
    energy_matches = re.findall(r"Total lattice energy\s*=\s*(-?[0-9.]+)\s*eV", content,
                                re.IGNORECASE)
    if not volume_match or not energy_matches:
        raise RuntimeError(f"GULP did not return a cell volume and lattice energy at {lat}. "
                           f"See {got_path} for details.")
    return volume_match.group(1), energy_matches[-1]

def generate_results(element, start_lat, end_lat, gulp_executable,
                     step=DEFAULT_LATTICE_STEP, lattice_points=None):
    for directory in (INPUT_DIR, OUTPUT_DIR, RESULT_DIR, SNAPSHOT_DIR):
        os.makedirs(directory, exist_ok=True)
    stem = f"{element.lower()}o"
    gin_path = os.path.join(INPUT_DIR, stem + ".gin")
    got_path = os.path.join(OUTPUT_DIR, stem + ".got")
    uv_path = os.path.join(RESULT_DIR, f"{stem}-uv.txt")
    make_gin(element, gin_path)

    latitudes = list(lattice_points) if lattice_points is not None else lattice_values(start_lat, end_lat, step)
    with open(uv_path, "w", encoding="utf-8") as result_file:
        result_file.write("a(Angs)    V(Angs^3)    U(eV/unit cell)\n")
    for index, lattice in enumerate(latitudes, start=1):
        lattice_text = format(lattice.normalize(), "f")
        volume, energy = run_single_gulp(lattice_text, gin_path, got_path, gulp_executable)
        with open(uv_path, "a", encoding="utf-8") as result_file:
            result_file.write(f"{lattice_text}    {volume}    {energy}\n")
    return gin_path, uv_path, GNUPLOT_TEMPLATE
