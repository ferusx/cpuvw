# formatter.py

# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 Markus Johnsson


from typing import List
from constants import (
    PID_W, USER_W, CPU_W,
    THR_W, TOT_W, CMD_W,
    RESET, fg, STAT_W, color, bg
)
# Local imports
from models import ProcessInfo
from utils import visible_len

# =========================================================
# Class: ProcessFormatter
# =========================================================
class ProcessFormatter:
    """
    Formats process data into a clean, aligned table for terminal output.

    This class takes a list of ProcessInfo objects and turns them into
    fixed-width rows designed to be easy to scan in a CLI environment.
    The goal is simple: present useful information clearly, without
    distractions or surprises.

    It is responsible for shaping the final look of the default view,
    handling everything from column alignment to subtle visual cues
    like color and spacing.

    Responsibilities:
        - Define column layout and alignment
        - Format numeric values (CPU, memory, RSS, time)
        - Apply optional ANSI color styling
        - Respect display-related flags (wrapping, headers, etc.)

    Boundaries:
        - Does NOT fetch, filter, or sort data
        - Does NOT construct or render process trees
        - Assumes all input is already prepared for display

    Context:

        This formatter powers the standard table view — the first thing
        most users see when running procvw.py. Because of that, it aims to
        feel familiar, stable, and consistent with traditional UNIX tools
        like ps and top.
    """

    # --------------------------------------------------------------------
    # Method: format
    # --------------------------------------------------------------------
    @staticmethod
    def format(
            processes: List[ProcessInfo],
            use_color: bool,
            use_light_color:bool,
            invert_headers:str,
            args
    ) -> List[str]:
        """
        Format a list of processes into aligned table rows.

        This method transforms ProcessInfo objects into a visual
        representation suitable for terminal output. It handles layout,
        truncation, and optional color styling while respecting user flags.

        Flow:

            1. Determine terminal width
                Used to dynamically size the COMMAND column.

            2. Build header (optional)
                Skipped when --no-header or --raw is used.

            3. Iterate over processes
                - Apply internal filtering (idle/system noise)
                - Handle raw output mode (bypasses formatting)
                - Prepare and align all fields

            4. Width-aware truncation
                COMMAND field is truncated only when necessary,
                based on actual rendered width (excluding colors).

            5. Apply color (optional)
                ANSI colors are added after alignment to avoid
                breaking width calculations.

            6. Assemble final lines
                Fully formatted rows are appended to output.

        Args:
            processes (List[ProcessInfo]):
                Processes to format.

            use_color (bool):
                Whether ANSI color styling should be applied.

            use_light_color (bool):
                Whether a more light color styling should be applied.

            args:
                Parsed CLI arguments controlling formatting behavior.

            invert_headers (bool):
                Whether the inverse colors of the column headers should be applied.

        Returns:
            List[str]:
                Fully formatted lines ready for printing.

        Notes:

            - Padding is always applied before color to keep alignment stable.
            - Width calculations are performed on uncolored text to avoid
              ANSI escape sequence interference.
            - The COMMAND column adapts to terminal width unless
              --line-wrap is enabled.
        """


        lines = []
        # Fallback ensures sane width in non-interactive environments (e.g. pipes/SSH)

        # Format column headers (width)
        columns = [
            ("PID", PID_W),
            ("USER", USER_W),
            ("STAT", STAT_W),
            ("CPU%", CPU_W),
            ("TOTAL%", TOT_W),
            ("THR", THR_W),
            ("COMMAND", None),
        ]

        # Inverted colors for the column headers
        INVERT_HEADER_COLORS = {
            "white": (0xffffff, 0x000000),
            "gray": (0xaaaaaa, 0x000000),
            "blue": (0x5287d6, 0x000000),
            "green": (0x00c900, 0x000000),
            "purple": (0xa96aec, 0x000000),
            "teal": (0x6da179, 0x000000),
            "maroon": (0x6a496d, 0x000000),
            "orange": (0xec9c00, 0x000000),
        }

        parts = []

        # Inverted headers is used
        if invert_headers:
            bg_color, fg_color = INVERT_HEADER_COLORS.get(
                invert_headers, (0xffffff, 0x000000)
            )

            for name, width in columns:

                # padded INSIDE the block
                if width:
                    padded = name.ljust(width)
                else:
                    padded = name

                block = f"{bg(bg_color)}{fg(fg_color)}{padded}{RESET}"

                parts.append(block)

            header = "".join(parts)

        # No inverted headers
        else:
            for name, width in columns:
                if width:
                    padded = name.ljust(width)

                    if use_color:
                        parts.append(f"{padded}")
                    else:
                        parts.append(padded)
                else:
                    # COMMAND column (no fixed width)
                    if use_color:
                        parts.append(f"{name}")
                    else:
                        parts.append(name)

            header = "".join(parts)

        if not args.no_header:
            lines.append("")
            lines.append(header)
            total_width = (
                    PID_W +
                    USER_W +
                    STAT_W +
                    CPU_W +
                    TOT_W +
                    THR_W +
                    CMD_W
            )

            if use_light_color:
                lines.append(f"{fg(0x777777)}-{RESET}" * visible_len(header))
            else:
                lines.append("-" * visible_len(header))

        processes = processes[:args.number]

        # Handle empty process list (IDLE view)
        if not processes:
            empty_row = (
                f"{'--':<{PID_W}}"
                f"{'--':<{USER_W}}"
                f"{'--':<{STAT_W}}"
                f"{'--':<{CPU_W}}"
                f"{'--':<{TOT_W}}"
                f"{'--':<{THR_W}}"
                f"{'--'}"
            )
            lines.append(empty_row)
            return lines

        # List and format processes (width)
        for p in processes:

            # Filter out the idle kernel process unless explicitly requested
            cmd = p.command.strip().lower()

            total = getattr(p, "total_cpu", p.cpu)

            if not args.all:
                if cmd == "idle":
                    continue

            # Hide internal ps command used for fetch
            cmd = p.command.lower()

            if cmd.startswith("ps ") and "-axo" in cmd:
                continue

            # Raw mode bypasses all formatting for simple, script-friendly output
            if args.raw:
                lines.append(
                    f"{p.pid} {p.user} {p.cpu:.1f} {p.mem:.1f} {p.command}"
                )
                continue


            # Apply padding BEFORE color
            pid_str = f"{p.pid:<{PID_W}}"
            user_str = f"{p.user:<{USER_W}}"
            stat_str = f"{p.stat:<{STAT_W}}"
            cpu_str = f"{p.cpu:<{CPU_W}.1f}"
            tot_str = f"{total:<{TOT_W}.1f}"
            thr_str = f"{p.threads:<{THR_W}}"


            if args.show_path:
                cmd_val = (p.command or "").strip("[]")
            else:
                cmd_val = (p.comm or "").strip("[]")

            cmd_str = f"{cmd_val:<{CMD_W}}"

            # Apply colors AFTER padding to preserve column alignment
            if use_color:

                pid_str = f"{fg(0x00ffff)}{pid_str}{RESET}"
                user_str = f"{fg(0xffffff)}{user_str}{RESET}"
                stat_str = f"{fg(0x888888)}{stat_str}{RESET}"  # Gray

                # CPU special logic (override base gray)
                if p.cpu >= 70:
                    cpu_str = f"{fg(0xff0000)}{cpu_str}{RESET}"  # Red
                elif p.cpu >= 40:
                    cpu_str = f"{fg(0xecbb00)}{cpu_str}{RESET}"  # Orange
                elif p.cpu >= 10:
                    cpu_str = f"{fg(0x00bf00)}{cpu_str}{RESET}"  # Green
                else:
                    cpu_str = f"{fg(0x888888)}{cpu_str}{RESET}"  # Gray

                thr_str = f"{fg(0xffffff)}{thr_str}{RESET}"
                cmd_str = f"{fg(0x009400)}{cmd_str}{RESET}"  # Green

            elif use_light_color:

                pid_str = f"{pid_str}"
                user_str = f"{fg(0xffffff)}{user_str}{RESET}"
                stat_str = f"{fg(0x888888)}{stat_str}{RESET}"  # Gray

                # CPU special logic (override base gray)
                if p.cpu >= 70:
                    cpu_str = f"{fg(0xff0000)}{cpu_str}{RESET}"  # red
                elif p.cpu >= 40:
                    cpu_str = f"{fg(0xffffff)}{cpu_str}{RESET}"  # white
                elif p.cpu >= 10:
                    cpu_str = f"{fg(0xffffff)}{cpu_str}{RESET}"  # White
                else:
                    cpu_str = f"{fg(0xffffff)}{cpu_str}{RESET}"  # White

                thr_str = f"{fg(0xffffff)}{thr_str}{RESET}"
                cmd_str = f"{cmd_str}"

            # Final line (NO formatting here anymore!)
            line = (
                f"{pid_str}"
                f"{user_str}"
                f"{stat_str}"
                f"{cpu_str}"
                f"{tot_str}"
                f"{thr_str}"
                f"{cmd_str}"
            )

            lines.append(line)

        return lines
