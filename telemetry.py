# telemetry.py

# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 Markus Johnsson

import math
import select
import sys
import termios

import tty

from constants import fg, RESET
# Local imports
from utils import (
    get_cpu_topology,
    get_per_core_usage,
)

# -------------------------------------------------------------------------------------
# Function: get_physical_core_usage
# -------------------------------------------------------------------------------------
def get_physical_core_usage(duration=1.0, interval=0.3):

    topology = get_cpu_topology()

    logical_usages = get_per_core_usage(
        duration=duration,
        interval=interval,
    )

    physical_cores = []

    p_index = 0
    e_index = 0

    for core_group in topology["physical_cores"]:

        # --------------------------------------------------
        # SMT performance core
        # --------------------------------------------------
        if len(core_group) > 1:

            usage = max(
                logical_usages[cpu]
                for cpu in core_group
            )

            label = f"P{p_index}"
            p_index += 1

        # --------------------------------------------------
        # Single-thread efficiency core
        # --------------------------------------------------
        else:

            usage = logical_usages[core_group[0]]

            label = f"E{e_index}"
            e_index += 1

        physical_cores.append(
            (label, usage)
        )

    return physical_cores

# -------------------------------------------------------------------------------------
# Function: render_core_meter
# -------------------------------------------------------------------------------------
# -------------------------------------------------------------------------------------
# Function: render_core_meter
# -------------------------------------------------------------------------------------
def render_core_meter(label, args, usage, width=15):

    usage = max(0.0, min(usage, 100.0))

    # --------------------------------------------------
    # Filled width
    # --------------------------------------------------
    filled = math.floor(
        (usage / 100) * width
    )

    chars = []

    for i in range(width):

        # --------------------------------------------------
        # Filled section
        # --------------------------------------------------
        if i < filled:
            if args.color:
                chars.append(f"{fg(0x5287d6)}▒{RESET}")
            else:
                chars.append(f"▒")

        # --------------------------------------------------
        # Background track
        # --------------------------------------------------
        else:
            chars.append("¨")

    meter = "".join(chars)

    # --------------------------------------------------
    # Fixed-width percentage field
    # --------------------------------------------------
    if args.color:

        # ------------------------------------------
        # Usage color thresholds
        # ------------------------------------------
        if usage < 5:
            usage_color = fg(0xffffff)

        elif usage < 25:
            usage_color = fg(0x009400)

        elif usage < 70:
            usage_color = fg(0xecbb00)

        else:
            usage_color = fg(0xff0000)

        percent_text = (
            f"{usage_color}"
            f"{int(round(usage)):>3}{fg(0x5287d6)}%{RESET}"
            f"{RESET}"
        )
    else:
        percent_text = f"{int(round(usage)):>3}%"

    # --------------------------------------------------
    # Core-type coloring
    # --------------------------------------------------
    if args.color:
        if label.startswith("P"):
            label_color = fg(0x777777)

        elif label.startswith("E"):
            label_color = fg(0xaaaaaa)

        elif label.startswith("C"):
            label_color = fg(0xaaaaaa)

        else:
            label_color = fg(0xffffff)

        return (
            f"{label_color}{label:<3}{RESET}"
            f"{meter} "
            f"{percent_text}"
        )
    else:
        return (
            f"{label:<3}"
            f"{meter} "
            f"{percent_text}"
        )

# -------------------------------------------------------------------------------------
# Function: render_core_grid
# -------------------------------------------------------------------------------------
def render_telemetry_grid(core_data, args, rows=5):

    if not core_data:
        return []

    cols = math.ceil(len(core_data) / rows)

    grid = [
        [""] * cols
        for _ in range(rows)
    ]

    # --------------------------------------------------
    # Fill vertically first
    # --------------------------------------------------
    index = 0

    for col in range(cols):

        for row in range(rows):

            if index >= len(core_data):
                break

            label, usage = core_data[index]

            grid[row][col] = render_core_meter(
                label,
                args,
                usage
            )

            index += 1

    # --------------------------------------------------
    # Build final lines
    # --------------------------------------------------
    lines = []

    for row in grid:

        rendered = [
            cell
            for cell in row
            if cell
        ]

        lines.append(
            "   ".join(rendered)
        )

    return lines

# -------------------------------------------------------------------------------------
# Function: render_physical_summary
# -------------------------------------------------------------------------------------
def render_physical_summary(core_data, args):

    lines = []

    # --------------------------------------------------
    # Core counts
    # --------------------------------------------------
    performance_cores = [
        item for item in core_data
        if item[0].startswith("P")
    ]

    efficiency_cores = [
        item for item in core_data
        if item[0].startswith("E")
    ]

    total_cores = len(core_data)

    # --------------------------------------------------
    # Activity states
    # --------------------------------------------------
    saturated = sum(
        1 for _, usage in core_data
        if usage >= 80
    )

    active = sum(
        1 for _, usage in core_data
        if 40 <= usage < 80
    )

    low = sum(
        1 for _, usage in core_data
        if 1 <= usage < 40
    )

    idle = sum(
        1 for _, usage in core_data
        if usage < 1
    )

    # --------------------------------------------------
    # Total utilization
    # --------------------------------------------------
    total_utilization = round(
        sum(usage for _, usage in core_data),
        1
    )

    total_capacity = total_cores * 100

    # --------------------------------------------------
    # Summary block
    # --------------------------------------------------
    if args.color:
        lines.append("")
        lines.append(f"{fg(0xaaaaaa)}Physical cores:{RESET} {total_cores}")
        lines.append(f"{fg(0xaaaaaa)}Performance cores:{RESET} {len(performance_cores)}")
        lines.append(f"{fg(0xaaaaaa)}Efficiency cores:{RESET} {len(efficiency_cores)}")
        lines.append("")
        lines.append(f"{fg(0xaaaaaa)}Saturated cores:{RESET} {saturated}")
        lines.append(f"{fg(0xaaaaaa)}Active cores:{RESET} {active}")
        lines.append(f"{fg(0xaaaaaa)}Low activity cores:{RESET} {low}")
        lines.append(f"{fg(0xaaaaaa)}Idle cores:{RESET} {idle}")
        lines.append("")
        lines.append(
            f"Observed physical utilization: "
            f"{total_utilization}{fg(0x5287d6)}%{RESET}"
        )

        lines.append(
            f"Total physical capacity: "
            f"{total_capacity}{fg(0x5287d6)}%{RESET} "
            f"({total_cores} × 100{fg(0x5287d6)}%{RESET})"
        )
    else:
        lines.append("")
        lines.append(f"Physical cores: {total_cores}")
        lines.append(f"Performance cores: {len(performance_cores)}")
        lines.append(f"Efficiency cores: {len(efficiency_cores)}")
        lines.append("")
        lines.append(f"Saturated cores: {saturated}")
        lines.append(f"Active cores: {active}")
        lines.append(f"Low activity cores: {low}")
        lines.append(f"Idle cores: {idle}")
        lines.append("")
        lines.append(
            f"Observed physical utilization: "
            f"{total_utilization}%"
        )

        lines.append(
            f"Total physical capacity: "
            f"{total_capacity}% "
            f"({total_cores} × 100%)"
        )

    return lines

# -------------------------------------------------------------------------------------
# Function: render_logical_summary
# -------------------------------------------------------------------------------------
def render_logical_summary(cpu_usages, args):

    lines = []

    logical_cpus = len(cpu_usages)

    # --------------------------------------------------
    # Activity states
    # --------------------------------------------------
    saturated = sum(
        1 for usage in cpu_usages
        if usage >= 80
    )

    active = sum(
        1 for usage in cpu_usages
        if 40 <= usage < 80
    )

    low = sum(
        1 for usage in cpu_usages
        if 1 <= usage < 40
    )

    idle = sum(
        1 for usage in cpu_usages
        if usage < 1
    )

    # --------------------------------------------------
    # Utilization
    # --------------------------------------------------
    total_utilization = round(
        sum(cpu_usages),
        1
    )

    total_capacity = logical_cpus * 100

    # --------------------------------------------------
    # Summary block
    # --------------------------------------------------
    if args.color:
        lines.append("")
        lines.append(f"{fg(0xaaaaaa)}Logical CPUs:{RESET} {logical_cpus}")
        lines.append("")
        lines.append(f"{fg(0xaaaaaa)}Saturated logical CPUs:{RESET} {saturated}")
        lines.append(f"{fg(0xaaaaaa)}Active logical CPUs:{RESET} {active}")
        lines.append(f"{fg(0xaaaaaa)}Low activity logical CPUs:{RESET} {low}")
        lines.append(f"{fg(0xaaaaaa)}Idle logical CPUs:{RESET} {idle}")
        lines.append("")
        lines.append(
            f"Observed logical utilization:{RESET} "
            f"{total_utilization}{fg(0x5287d6)}%{RESET}"
        )

        lines.append(
            f"Total logical capacity: "
            f"{total_capacity}{fg(0x5287d6)}%{RESET} "
            f"({logical_cpus} × 100{fg(0x5287d6)}%{RESET})"
        )
    else:
        lines.append("")
        lines.append(f"Logical CPUs: {logical_cpus}")
        lines.append("")
        lines.append(f"Saturated logical CPUs: {saturated}")
        lines.append(f"Active logical CPUs: {active}")
        lines.append(f"Low activity logical CPUs: {low}")
        lines.append(f"Idle logical CPUs: {idle}")
        lines.append("")
        lines.append(
            f"Observed logical utilization: "
            f"{total_utilization}%"
        )

        lines.append(
            f"Total logical capacity: "
            f"{total_capacity}% "
            f"({logical_cpus} × 100%)"
        )

    return lines

# -------------------------------------------------------------------------------------
# Function: _key_pressed
# -------------------------------------------------------------------------------------
def _key_pressed():

    dr, _, _ = select.select(
        [sys.stdin],
        [],
        [],
        0
    )

    if dr:
        return sys.stdin.read(1)

    return None

# -------------------------------------------------------------------------------------
# Function: show_physical_cores_fast
# -------------------------------------------------------------------------------------
def show_physical_cores_fast(args):



    if args.core_update_frequency:

        duration = args.core_update_frequency[0]

        if len(args.core_update_frequency) > 1:
            interval = args.core_update_frequency[1]
        else:
            interval = args.physical_interval

    else:
        duration = args.physical_duration
        interval = args.physical_interval

    core_data = get_physical_core_usage(
        duration=duration,
        interval=interval,
    )

    print("Physical Core Telemetry")
    print("")

    lines = render_telemetry_grid(core_data, args)

    summary_lines = render_physical_summary(
        core_data,
        args
    )

    # Print the grid
    for line in lines:
        print(line)

    # Print summary for physical cores
    for line in summary_lines:
        print(line)


# -------------------------------------------------------------------------------------
# Function: show_physical_cores_live
# -------------------------------------------------------------------------------------
def show_physical_cores_live(args):
    # Save terminal state
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    try:
        first_pass = True

        tty.setcbreak(fd)

        if args.core_update_frequency:

            duration = args.core_update_frequency[0]

            if len(args.core_update_frequency) > 1:
                interval = args.core_update_frequency[1]
            else:
                interval = args.physical_interval

        else:
            duration = args.physical_duration
            interval = args.physical_interval

        while True:

            # --------------------------------------------------
            # Key handling
            # --------------------------------------------------
            key = _key_pressed()

            if key:
                if key in ("q", "Q", "\x1b"):
                    print()
                    break

            # --------------------------------------------------
            # Clear screen
            # --------------------------------------------------
            print("\033[H\033[J", end="")

            # --------------------------------------------------
            # Gather telemetry
            # --------------------------------------------------
            if first_pass:

                sample_duration = 0.05
                first_pass = False

            else:
                sample_duration = duration

            core_data = get_physical_core_usage(
                duration=sample_duration,
                interval=interval,
            )

            # --------------------------------------------------
            # Render grid
            # --------------------------------------------------
            lines = render_telemetry_grid(core_data, args)

            summary_lines = render_physical_summary(
                core_data,
                args
            )

            print("Physical Core Telemetry")
            print("")

            # Print the grid
            for line in lines:
                print(line)

            # Print summary for physical cores
            for line in summary_lines:
                print(line)

    except KeyboardInterrupt:
        print()

    finally:
        termios.tcsetattr(
            fd,
            termios.TCSADRAIN,
            old_settings
        )



# -------------------------------------------------------------------------------------
# Function: get_logical_cpu_usage
# -------------------------------------------------------------------------------------
def get_logical_cpu_usage(
    duration=1.0,
    interval=0.3,
):

    usages = get_per_core_usage(
        duration=duration,
        interval=interval,
    )

    result = []

    for i, usage in enumerate(usages):

        result.append(
            (f"C{i}", usage)
        )

    return result

# -------------------------------------------------------------------------------------
# Function: show_logical_cpu_fast
# -------------------------------------------------------------------------------------
def show_logical_cpu_fast(args):

    if args.core_update_frequency:

        duration = args.core_update_frequency[0]

        if len(args.core_update_frequency) > 1:
            interval = args.core_update_frequency[1]
        else:
            interval = args.logical_interval

    else:
        duration = args.logical_duration
        interval = args.logical_interval

    core_data = get_logical_cpu_usage(
        duration=duration,
        interval=interval,
    )

    print("Logical CPU Telemetry")
    print("")

    lines = render_telemetry_grid(core_data, args)

    summary_lines = render_logical_summary(
        [usage for _, usage in core_data],
        args
    )

    # Print the grid
    for line in lines:
        print(line)

    # Print the logical CPU summary
    for line in summary_lines:
        print(line)

# -------------------------------------------------------------------------------------
# Function: show_logical_cpu_live
# -------------------------------------------------------------------------------------
def show_logical_cpu_live(args):

    fd = sys.stdin.fileno()

    old_settings = termios.tcgetattr(fd)

    try:
        first_pass = True

        tty.setcbreak(fd)

        if args.core_update_frequency:

            duration = args.core_update_frequency[0]

            if len(args.core_update_frequency) > 1:
                interval = args.core_update_frequency[1]
            else:
                interval = args.logical_interval

        else:
            duration = args.logical_duration
            interval = args.logical_interval

        while True:

            key = _key_pressed()

            if key:
                if key in ("q", "Q", "\x1b"):
                    print()
                    break

            print("\033[H\033[J", end="")

            if first_pass:

                sample_duration = 0.05
                first_pass = False

            else:
                sample_duration = duration

            core_data = get_logical_cpu_usage(
                duration=sample_duration,
                interval=interval,
            )

            print("Logical CPU Telemetry")
            print("")

            lines = render_telemetry_grid(core_data, args)

            summary_lines = render_logical_summary(
                [usage for _, usage in core_data],
                args
            )

            # Print the grid
            for line in lines:
                print(line)

            # Print the logical CPU data
            for line in summary_lines:
                print(line)


    except KeyboardInterrupt:
        print()

    finally:

        termios.tcsetattr(
            fd,
            termios.TCSADRAIN,
            old_settings
        )