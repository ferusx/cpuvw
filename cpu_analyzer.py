# cpu_analyzer.py

# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 Markus Johnsson

# Local imports
from constants import color, RESET, BOLD, fg, STAT_MEANINGS
from utils import (
    extract_unique_stats,
    get_cpu_count,
    estimate_active_cores,
    get_per_core_usage,
    classify_cores
)

class CPUAnalyzer:
    """
    Analyzes process CPU usage and produces a structured summary
    for the default cpuvw output.

    This is the intelligence layer of cpuvw.
    """

    # ------------------------------------------------------------
    # Method: analyze()
    # ------------------------------------------------------------
    def analyze(self, processes, args, use_color=False):
        """
        Analyze CPU behavior from process list.

        Returns:
            dict with:
                state
                message
                dominant (ProcessInfo or None)
                dominant_desc (str)
                top (list[ProcessInfo])
        """

        if not processes:
            state = "IDLE"
            message = self._build_message(state, use_color)

            return {
                "state": state,
                "message": message,
                "dominant": None,
                "dominant_desc": "",
                "top": []
            }

        # Remove idle from analytical model (not from raw data)
        real_processes = [
            p for p in processes
            if (p.comm or "").lower() != "idle"
        ]

        if not real_processes:
            state = "IDLE"
            message = self._build_message(state, use_color)

            return {
                "state": state,
                "message": message,
                "dominant": None,
                "dominant_desc": "",
                "top": []
            }

        total_cpu = sum(p.cpu for p in real_processes)
        dominant_list = sorted(real_processes, key=lambda p: p.cpu, reverse=True)[:3]
        primary = dominant_list[0] if dominant_list else None

        if primary is not None:
            top_cpu = primary.cpu
        else:
            top_cpu = 0

        state = self._determine_state(real_processes, args)

        message = self._build_message(state, use_color)

        # ------------------------------------------------------------
        # Process visibility based on state (UX-driven)
        # ------------------------------------------------------------
        if state == "IDLE":
            top_n = 0

        elif state == "LIGHT":
            top_n = 2

        elif state == "MODERATE":
            top_n = 3

        elif state == "HEAVY_LOCALIZED":
            top_n = 1

        elif state == "HEAVY_DISTRIBUTED":
            top_n = 8

        else:
            top_n = 3  # fallback safety

        # ------------------------------------------------------------
        # Build top contributors (state-aware filtering)
        # ------------------------------------------------------------
        sorted_procs = sorted(real_processes, key=lambda p: p.cpu, reverse=True)

        top = []

        # -------------------------
        # IDLE
        # -------------------------
        if state == "IDLE":
            top = []

        # -------------------------
        # LIGHT
        # -------------------------
        elif state == "LIGHT":
            threshold = 1.0

            for i, p in enumerate(sorted_procs):
                if i == 0:
                    top.append(p)  # always include dominant
                elif p.cpu >= threshold:
                    top.append(p)

            top = top[:3]

        # -------------------------
        # MODERATE
        # -------------------------
        elif state == "MODERATE_DISTRIBUTED":
            threshold = 1.5

            for i, p in enumerate(sorted_procs):
                if i == 0:
                    top.append(p)
                elif p.cpu >= threshold:
                    top.append(p)

            top = top[:5]


        elif state == "MODERATE_LOCALIZED":
            threshold = 3.0

            for i, p in enumerate(sorted_procs):
                if i == 0:
                    top.append(p)
                elif p.cpu >= threshold:
                    top.append(p)

            top = top[:3]


        elif state == "MODERATE":
            threshold = 2.0

            for i, p in enumerate(sorted_procs):
                if i == 0:
                    top.append(p)
                elif p.cpu >= threshold:
                    top.append(p)

            top = top[:4]

        # -------------------------
        # HEAVY LOCALIZED
        # -------------------------
        elif state == "HEAVY_LOCALIZED":
            threshold = 5.0  # only meaningful contributors

            for i, p in enumerate(sorted_procs):
                if i == 0:
                    top.append(p)  # always include dominant
                elif p.cpu >= threshold:
                    top.append(p)

            top = top[:3]  # cap it

        # -------------------------
        # HEAVY DISTRIBUTED
        # -------------------------
        elif state == "HEAVY_DISTRIBUTED":
            threshold = 1.0

            for i, p in enumerate(sorted_procs):
                if i == 0:
                    top.append(p)
                elif p.cpu >= threshold:
                    top.append(p)

            top = top[:8]

        # -------------------------
        # Fallback safety
        # -------------------------
        else:
            top = sorted_procs[:3]

        if primary:
            dominant_desc = self._describe_process(primary)
        else:
            dominant_desc = ""

        return {
            "state": state,
            "message": message,
            "dominant": primary,
            "dominant_list": dominant_list,
            "dominant_desc": dominant_desc,
            "top": top,
            "filtered": real_processes
        }

    # ------------------------------------------------------------
    # Method: _determine_state()
    # ------------------------------------------------------------
    def _determine_state(self, processes, args):
        """
        Determine CPU state based on intensity and distribution.
        """

        if not processes:
            return "IDLE"

        max_cpu = max((p.cpu for p in processes), default=0.0)

        active_processes = [p for p in processes if p.cpu >= 10.0]
        active_count = len(active_processes)

        # ------------------------------------------
        # Threshold handling (safe + centralized)
        # ------------------------------------------
        heavy_threshold = args.cpu_state_threshold
        moderate_threshold = args.moderate_threshold
        light_threshold = args.light_threshold

        if max_cpu < light_threshold:
            return "IDLE"

        elif max_cpu < moderate_threshold:
            return "LIGHT"

        elif max_cpu < heavy_threshold:

            # Sort processes by CPU descending
            sorted_procs = sorted(processes, key=lambda p: p.cpu, reverse=True)

            # Rule 1: Many active processes → distributed
            if active_count >= 3:
                return "MODERATE_DISTRIBUTED"

            # Rule 2: Two strong processes sharing load → distributed
            if len(sorted_procs) >= 2:
                top_two_sum = sorted_procs[0].cpu + sorted_procs[1].cpu

                if top_two_sum >= 60:
                    return "MODERATE_DISTRIBUTED"

            # Default → localized moderate load
            return "MODERATE_LOCALIZED"

        else:
            if active_count >= 3:
                return "HEAVY_DISTRIBUTED"
            else:
                return "HEAVY_LOCALIZED"

    # ------------------------------------------------------------
    # Method: _build_message()
    # ------------------------------------------------------------
    def _build_message(self, state, use_color=False):

        # -----------------------------------
        # IDLE (System is idle)
        # -----------------------------------
        if state == "IDLE":
            if use_color:  # Use color theme
                return (
                    f"No dominant workload detected. "
                    f"\n{fg(0xaaaaaa)}Your system is largely {RESET}{fg(0x5287d6)}idle.{RESET}"
                )
            else:
                return (
                    f"No dominant workload detected."
                    f"\nYour system is largely idle."
                )

        # --------------------------------------------------------
        # HEAVY (system is under localized or distributed workload
        # --------------------------------------------------------
        if state == "HEAVY_LOCALIZED":
            if use_color:
                return (
                    f"{BOLD}{fg(0xffffff)}High CPU activity{RESET} {fg(0xffffff)}detected from a {RESET}{BOLD}{fg(0xffffff)}single dominant process.{RESET}\n"
                    f"{fg(0xaaaaaa)}Your system is now under {RESET}{fg(0xff0000)}heavy localized load.{RESET}"
                )
            else:
                return (
                    "High CPU activity detected from a single dominant process.\n"
                    "Your system is now under heavy localized load."
                )

        if state == "HEAVY_DISTRIBUTED":
            if use_color:
                return (
                    f"{BOLD}{fg(0xffffff)}High CPU activity{RESET} {fg(0xffffff)}detected across {RESET}{BOLD}{fg(0xffffff)}multiple processes.{RESET}\n"
                    f"{fg(0xaaaaaa)}Your system is now under {RESET}{fg(0xff0000)}heavy distributed load.{RESET}"
                )
            else:
                return (
                    "High CPU activity detected across multiple processes.\n"
                    "Your system is now under heavy distributed load."
                )

        # --------------------------------------
        # MODERATE (System under moderate load)
        # --------------------------------------
        if state == "MODERATE_DISTRIBUTED":
            # Use color
            if use_color:
                return (
                    f"{BOLD}{fg(0xffffff)}Moderate CPU activity {RESET}{fg(0xffffff)}is spread across {RESET}{BOLD}{fg(0xffffff)}multiple processes.\n{RESET}"
                    f"{fg(0xaaaaaa)}Your system is under a {RESET}{fg(0xecbb00)}balanced yet noticeable workload.{RESET}"
                )
            # No coloring
            else:
                return (
                    "Moderate CPU activity is spread across multiple processes.\n"
                    "You system is under a balanced yet noticeable workload."
                )

        elif state == "MODERATE_LOCALIZED":
            # Use colors
            if use_color:
                return (
                    f"{BOLD}{fg(0xffffff)}Moderate CPU activity{RESET}{fg(0xffffff)} is driven by a {RESET}{BOLD}{fg(0xffffff)}limited number of processes.\n{RESET}"
                    f"{fg(0xaaaaaa)}Your system is under a {RESET}{fg(0xecbb00)}focused workload.{RESET}"
                )

            # No coloring
            else:
                return (
                    "Moderate CPU activity is driven by a limited number of processes.\n"
                    "Your system is under a focused workload."
                )


        # --------------------------------------
        # LIGHT (System under light load)
        # --------------------------------------
        if use_color:
            return (
                f"{fg(0xffffff)}Light CPU activity detected.\n{RESET}"
                f"{fg(0xaaaaaa)}Your system is now under {RESET}{fg(0x009400)}light load.{RESET}"
            )
        else:
            return (
                f"Light CPU activity detected.\n"
                f"Your system is now under light load."
            )

    # ------------------------------------------------------------
    # Method: _describe_process()
    # ------------------------------------------------------------
    def _describe_process(self, process):
        cmd = (process.comm or process.command or "").lower()

        # --- Layer 1: Known processes ---
        known = {
            "firefox": "Web content rendering dominating CPU time",
            "chrome": "Web browser workload (tabs, scripts, rendering)",
            "xorg": "Display server handling graphical output",
            "python": "Python script execution",
            "gcc": "Compilation workload",
            "clang": "Compilation workload",
            "make": "Build system activity",
            "ffmpeg": "Media encoding/decoding workload",
            "zfs": "Filesystem operations (ZFS)",
            "postgres": "Database workload",
            "mysqld": "Database workload",
            "node": "JavaScript runtime workload",
            "java": "JVM-based application workload",
        }

        for key, desc in known.items():
            if key in cmd:
                return desc

        # --- Layer 2: Pattern matching ---
        if "python" in cmd:
            return "Python workload (script or service)"

        if "dbus" in cmd:
            return "System message bus activity"

        if "ssh" in cmd:
            return "Remote session activity"

        if "daemon" in cmd:
            return "Background service process"

        if "worker" in cmd:
            return "Worker thread/process activity"

        # --- Layer 3: Fallback ---
        return "Active process consuming CPU time"

    # ------------------------------------------------------------
    # Method: generate_analysis()
    # ------------------------------------------------------------
    def generate_analysis(self, analysis, args):
        """
        Generate human-style analytical report (for --analyze mode).
        """

        state = analysis["state"]
        processes = analysis.get("filtered", analysis.get("processes", []))
        dominant = analysis["dominant"]
        top = analysis["top"]
        cpu_count = get_cpu_count()
        estimated_active_cores = estimate_active_cores(processes)
        used = round(estimated_active_cores)
        core_usages = get_per_core_usage()
        core_saturated = sum(1 for u in core_usages if u >= 80)
        core_active = sum(1 for u in core_usages if 40 <= u < 80)
        core_low = sum(1 for u in core_usages if 20 <= u < 40)
        core_idle = sum(1 for u in core_usages if u < 20)

        lines = []

        # --------------------------------------------------
        # 1. System behavior (distribution)
        # --------------------------------------------------
        active_processes = [p for p in processes if p.cpu >= 5.0]
        total_cpu_usage = round(sum(p.cpu for p in active_processes), 1)

        if "DISTRIBUTED" in state:

            # Use color
            if args.color:
                lines.append(f"{fg(0xaaaaaa)}• CPU load is distributed across multiple processes{RESET}")
                text = f"└─ {len(active_processes)} processes are actively consuming {total_cpu_usage}% of total CPU resources"

                lines.append(
                    f"{fg(0xaaaaaa)}└─ {RESET}"
                    f"{fg(0xffffff)}{len(active_processes)}{RESET}"
                    f"{fg(0xaaaaaa)} processes are actively consuming {RESET}"
                    f"{fg(0xffffff)}{total_cpu_usage}{RESET}"
                    f"{fg(0xaaaaaa)}% of total CPU resources{RESET}"
                )

                # First: capacity view
                lines.append(f"  {fg(0xaaaaaa)}└─ {RESET}"
                    f"{fg(0xffffff)}{used} {RESET}"
                    f"{fg(0xaaaaaa)}/ {RESET}"
                    f"{fg(0xffffff)}{cpu_count} {RESET}"
                    f"{fg(0xaaaaaa)}CPU cores are actively utilized{RESET}")

                # Second: distribution view
                lines.append(
                    f"  {fg(0xaaaaaa)}└─ {RESET}"
                    f"{fg(0xffffff)}{core_saturated} {RESET}"
                    f"{fg(0xaaaaaa)}core{'s' if core_saturated != 1 else ''} saturated, {RESET}"
                    f"{fg(0xffffff)}{core_active} {RESET}"
                    f"{fg(0xaaaaaa)}active, {RESET}"
                    f"{fg(0xffffff)}{core_low} {RESET}"
                    f"{fg(0xaaaaaa)}low activity, {RESET}"
                    f"{fg(0xffffff)}{core_idle} {RESET}"
                    f"{fg(0xaaaaaa)}idle{RESET}"
                )
            # No color
            else:
                lines.append("• CPU load is distributed across multiple processes")
                lines.append(f"  └─ {len(active_processes)} processes are actively consuming {total_cpu_usage}% of total CPU resources")
                # First: capacity view
                lines.append(f"  └─ {used} / {cpu_count} CPU cores effectively utilized (estimated from processes)")

                # Second: distribution view
                lines.append(
                    f"  └─ {core_saturated} core{'s' if core_saturated != 1 else ''} saturated, "
                    f"{core_active} active, {core_low} low activity, {core_idle} idle"
                )

            # ------------------------------------------
            # Imbalance detection (proper model)
            # ------------------------------------------

            total_cores = cpu_count

            if args.color:

                if core_saturated == total_cores:
                    lines.append(f"{fg(0xaaaaaa)}  └─ CPU load is fully distributed across all cores{RESET}")

                elif core_saturated >= total_cores * 0.7:
                    lines.append(f"{fg(0xaaaaaa)}  └─ CPU load is well distributed across cores{RESET}")

                elif core_saturated <= max(1, int(total_cores * 0.3)):
                    lines.append(f"{fg(0xaaaaaa)}  └─ CPU load is unevenly distributed across cores{RESET}")
                    lines.append(f"{fg(0xaaaaaa)}  └─ Workload may be limited by single-thread performance{RESET}")

            else:

                if core_saturated == total_cores:
                    lines.append("  └─ CPU load is fully distributed across all cores")

                elif core_saturated >= total_cores * 0.7:
                    lines.append("  └─ CPU load is well distributed across cores")

                elif core_saturated <= max(1, int(total_cores * 0.3)):
                    lines.append("  └─ CPU load is unevenly distributed across cores")
                    lines.append("  └─ Workload may be limited by single-thread performance")

        elif "LOCALIZED" in state:

            # Use color
            if args.color:
                lines.append(f"{fg(0xaaaaaa)}• CPU load is concentrated in a small number of processes{RESET}")
                # First: capacity view
                lines.append(f"{fg(0xaaaaaa)}  └─ {RESET}"
                             f"{fg(0xffffff)}{used} {RESET}"
                             f"{fg(0xaaaaaa)}/ {RESET}"
                             f"{fg(0xffffff)}{cpu_count} "
                             f"{fg(0xaaaaaa)}CPU cores are actively utilized{RESET}")

                # Second: distribution view
                lines.append(
                            f"{fg(0xaaaaaa)}  └─ {RESET}"
                            f"{fg(0xffffff)}{core_saturated} {RESET}"
                            f"{fg(0xaaaaaa)}core{'s' if core_saturated != 1 else ''} saturated, {RESET}"
                            f"{fg(0xffffff)}{core_active} {RESET}"
                            f"{fg(0xaaaaaa)}active, {RESET}"
                            f"{fg(0xffffff)}{core_low} {RESET}"
                            f"{fg(0xaaaaaa)}low activity, {RESET}"
                            f"{fg(0xffffff)}{core_idle} {RESET}"
                            f"{fg(0xaaaaaa)}idle{RESET}"
                )

            # No color
            else:
                lines.append(f"• CPU load is concentrated in a small number of processes")
                # First: capacity view
                lines.append(f"  └─ {used} / {cpu_count} CPU cores effectively utilized (estimated from processes)")

                # Second: distribution view
                lines.append(
                    f"  └─ {core_saturated} core{'s' if core_saturated != 1 else ''} saturated, "
                    f"{core_active} active, {core_low} low activity, {core_idle} idle"
                )

            # ------------------------------------------
            # Imbalance detection (proper model)
            # ------------------------------------------
            total_cores = cpu_count

            if args.color:

                if core_saturated == total_cores:
                    lines.append(f"{fg(0xaaaaaa)}  └─ CPU load is fully distributed across all cores{RESET}")

                elif core_saturated >= total_cores * 0.7:
                    lines.append(f"{fg(0xaaaaaa)}  └─ CPU load is well distributed across cores{RESET}")

                elif core_saturated <= max(1, int(total_cores * 0.3)):
                    lines.append(f"{fg(0xaaaaaa)}  └─ CPU load is unevenly distributed across cores{RESET}")
                    lines.append(f"{fg(0xaaaaaa)}  └─ Workload may be limited by single-thread performance{RESET}")

            else:

                if core_saturated == total_cores:
                    lines.append("  └─ CPU load is fully distributed across all cores")

                elif core_saturated >= total_cores * 0.7:
                    lines.append("  └─ CPU load is well distributed across cores")

                elif core_saturated <= max(1, int(total_cores * 0.3)):
                    lines.append("  └─ CPU load is unevenly distributed across cores")
                    lines.append("  └─ Workload may be limited by single-thread performance")

        else:
            # Use color
            if args.color:
                lines.append(f"{fg(0xaaaaaa)}• CPU activity is present but not strongly concentrated{RESET}")
                # First: capacity view
                lines.append(f"  {fg(0xaaaaaa)}└─ {RESET}"
                             f"{fg(0xffffff)}{used} {RESET}"
                             f"/ {fg(0xffffff)}{cpu_count} {RESET}"
                             f"{fg(0xaaaaaa)}CPU cores are actively utilized{RESET}")

                # Second: distribution view
                lines.append(
                    f"  {fg(0xaaaaaa)}└─ {RESET}"
                    f"{fg(0xffffff)}{core_saturated} {RESET}"
                    f"{fg(0xaaaaaa)}core{'s' if core_saturated != 1 else ''} saturated, {RESET}"
                    f"{fg(0xffffff)}{core_active} {RESET}"
                    f"{fg(0xaaaaaa)}active, {RESET}"
                    f"{fg(0xffffff)}{core_low} {RESET}"
                    f"{fg(0xaaaaaa)}low activity, {RESET}"
                    f"{fg(0xffffff)}{core_idle} {RESET}"
                    f"{fg(0xaaaaaa)}idle{RESET}"
                )

            # No color
            else:
                lines.append("• CPU activity is present but not strongly concentrated")
                # First: capacity view
                lines.append(f"  └─ {used} / {cpu_count} CPU cores are actively utilized")

                # Second: distribution view
                lines.append(
                    f"  └─ {core_saturated} core{'s' if core_saturated != 1 else ''} saturated, "
                    f"{core_active} active, {core_low} low activity, {core_idle} idle"
                )

            # ------------------------------------------
            # Imbalance detection (proper model)
            # ------------------------------------------

            total_cores = cpu_count

            if args.color:

                if core_saturated == total_cores:
                    lines.append(f"{fg(0xaaaaaa)}  └─ CPU load is fully distributed across all cores{RESET}")

                elif core_saturated >= total_cores * 0.7:
                    lines.append(f"{fg(0xaaaaaa)}  └─ CPU load is well distributed across cores{RESET}")

                elif core_saturated <= max(1, int(total_cores * 0.3)):
                    lines.append(f"{fg(0xaaaaaa)}  └─ CPU load is unevenly distributed across cores{RESET}")
                    lines.append(f"{fg(0xaaaaaa)}  └─ Workload may be limited by single-thread performance{RESET}")

            else:

                if core_saturated == total_cores:
                    lines.append("  └─ CPU load is fully distributed across all cores")

                elif core_saturated >= total_cores * 0.7:
                    lines.append("  └─ CPU load is well distributed across cores")

                elif core_saturated <= max(1, int(total_cores * 0.3)):
                    lines.append("  └─ CPU load is unevenly distributed across cores")
                    lines.append("  └─ Workload may be limited by single-thread performance")

        # --------------------------------------------------
        # 2. Dominant process insight
        # --------------------------------------------------
        if dominant:

            if args.color:
                if state == "IDLE":
                    lines.append(f"{fg(0xaaaaaa)}• {RESET}"
                                 f"{fg(0xffffff)}Most active process: {RESET}"
                                 f"{fg(0x777777)}{dominant.comm} {RESET}"
                                 f"{fg(0xaaaaaa)}({RESET}"
                                 f"{fg(0xffffff)}{dominant.cpu:.1f}{RESET}"
                                 f"{fg(0xaaaaaa)}%){RESET}")
                else:
                    lines.append(f"{fg(0xaaaaaa)}• {RESET}"
                                 f"{fg(0xffffff)}Dominant workload: {RESET}"
                                 f"{fg(0x777777)}{dominant.comm} {RESET}"
                                 f"{fg(0xaaaaaa)}({RESET}"
                                 f"{fg(0xffffff)}{dominant.cpu:.1f}{RESET}"
                                 f"{fg(0xaaaaaa)}%){RESET}")
            else:
                if state == "IDLE":
                    lines.append(f"• Most active process: {dominant.comm} ({dominant.cpu:.1f}%)")
                else:
                    lines.append(f"• Dominant workload: {dominant.comm} ({dominant.cpu:.1f}%)")

        # --------------------------------------------------
        # STAT interpretation (FULL, no shortcuts)
        # --------------------------------------------------
        stat_chars = sorted(
            extract_unique_stats(active_processes),
            key=lambda x: ["R", "S", "D", "Z", "T", "N", "+", "C"].index(x)
            if x in ["R", "S", "D", "Z", "T", "N", "+", "C"] else 99
        )

        if stat_chars:
            if args.color:
                lines.append(f"{fg(0xaaaaaa)}• {RESET}"
                             f"{fg(0xffffff)}STAT indicates:{RESET}"
                             f"{fg(0xffffff)} {', '.join(stat_chars)}{RESET}")
            else:
                lines.append(f"• STAT indicates: {', '.join(stat_chars)}")

            if args.color:
                for key in stat_chars:
                    desc = STAT_MEANINGS.get(key, f"{fg(0xaaaaaa)}Unknown state{RESET}")

                    # --------------------------------------------------
                    # Analyzer-specific richer descriptions (ONE LINE)
                    # --------------------------------------------------
                    if key == "R":
                        desc = f"{fg(0xaaaaaa)}Running or ready to run — actively competing for CPU time{RESET}"

                    elif key == "S":
                        desc = f"{fg(0xaaaaaa)}Sleeping (waiting for event) — currently idle, awaiting work{RESET}"

                    elif key == "D":
                        desc = f"{fg(0xaaaaaa)}Waiting on I/O — blocked on disk or network operations{RESET}"

                    elif key == "Z":
                        desc = f"{fg(0xaaaaaa)}Zombie process — terminated but not yet reaped by parent{RESET}"

                    elif key == "T":
                        desc = f"{fg(0xaaaaaa)}Stopped — paused or under debugging control{RESET}"

                    elif key == "N":
                        desc = f"{fg(0xaaaaaa)}Low priority (nice) — intentionally deprioritized workload{RESET}"

                    elif key == "+":
                        desc = f"{fg(0xaaaaaa)}Foreground process — interacting directly with the user{RESET}"

                    elif key == "C":
                        desc = f"{fg(0xaaaaaa)}CPU-bound — continuously consuming CPU without waiting{RESET}"

                    lines.append(f"  {fg(0xaaaaaa)}└─ {RESET}{fg(0xffffff)}{key} {RESET}{fg(0xaaaaaa)}→ {RESET}{fg(0xffffff)}{desc}{RESET}")
            else:
                for key in stat_chars:
                    desc = STAT_MEANINGS.get(key, f"{fg(0xaaaaaa)}Unknown state{RESET}")

                    # --------------------------------------------------
                    # Analyzer-specific richer descriptions (ONE LINE)
                    # --------------------------------------------------
                    if key == "R":
                        desc = f"Running or ready to run — actively competing for CPU time"

                    elif key == "S":
                        desc = f"Sleeping (waiting for event) — currently idle, awaiting work"

                    elif key == "D":
                        desc = f"Waiting on I/O — blocked on disk or network operations"

                    elif key == "Z":
                        desc = f"Zombie process — terminated but not yet reaped by parent"

                    elif key == "T":
                        desc = f"Stopped — paused or under debugging control"

                    elif key == "N":
                        desc = f"Low priority (nice) — intentionally deprioritized workload"

                    elif key == "+":
                        desc = f"Foreground process — interacting directly with the user"

                    elif key == "C":
                        desc = f"CPU-bound — continuously consuming CPU without waiting"

                    lines.append(
                        f"  └─ {key} → {desc}")

        # --------------------------------------------------
        # 4. Load intensity
        # --------------------------------------------------
        if args.color:
            if "HEAVY" in state:
                lines.append(f"{fg(0xaaaaaa)}• {RESET}{fg(0xffffff)}System is under sustained computational pressure{RESET}")

            elif "MODERATE" in state:
                lines.append(f"{fg(0xaaaaaa)}• {RESET}{fg(0xffffff)}Workload is noticeable but not saturating the system{RESET}")

            elif state == "LIGHT":
                lines.append(f"{fg(0xaaaaaa)}• {RESET}{fg(0xffffff)}System is responsive with light activity{RESET}")

            elif state == "IDLE":
                lines.append(f"{fg(0xaaaaaa)}• {RESET}{fg(0xffffff)}System is mostly idle{RESET}")

        else:
            if "HEAVY" in state:
                lines.append(
                    f"• System is under sustained computational pressure")

            elif "MODERATE" in state:
                lines.append(
                    f"• Workload is noticeable but not saturating the system")

            elif state == "LIGHT":
                lines.append(f"• System is responsive with light activity")

            elif state == "IDLE":
                lines.append(f"• System is mostly idle")

        # ------------------------------------------------------------------
        # NOTE: line to mention the percentage that the total cores make out
        # ------------------------------------------------------------------
        lines.append("")
        if args.color:
            lines.append(f"NOTE: {fg(0xffffff)}CPU usage is cumulative across cores (100% per core on multi-core systems){RESET}")
        else:
            lines.append("NOTE: CPU usage is cumulative across cores (100% per core on multi-core systems)")
        # 5. Conclusion
        # --------------------------------------------------
        intent = self.detect_intent(processes, state, args)

        confidence_level, confidence_reason, confidence_score = self.compute_confidence(
            processes,
            state,
            used,
            cpu_count,
            core_saturated
        )

        if "DISTRIBUTED" in state:

            lines.append("")

            if args.color:
                lines.append(f"{BOLD}{fg(0xffffff)}Conclusion:{RESET}")
            else:
                lines.append("Conclusion:")

            # --------------------------------------
            # Intent
            # --------------------------------------
            if intent:
                if args.color:
                    lines.append(f"{fg(0xaaaaaa)}→ {intent}{RESET}")
                else:
                    lines.append(f"→ {intent}")
            else:
                fallback = "Likely a parallel or multi-process workload"
                if args.color:
                    lines.append(f"{fg(0xaaaaaa)}→ {fallback}{RESET}")
                else:
                    lines.append(f"→ {fallback}")

            # --------------------------------------
            # Confidence (clean, unified)
            # --------------------------------------
            if args.color:
                lines.append(
                    f"{fg(0xaaaaaa)}→ Confidence: {RESET}"
                    f"{fg(0xffffff)}{confidence_level}{RESET} "
                    f"{fg(0x777777)}({confidence_reason}){RESET}"
                    f"{fg(0xaaaaaa)}[{RESET}"
                    f"{fg(0xffffff)}{confidence_score}{RESET}"
                    f"{fg(0xaaaaaa)}%]{RESET}"
                )
            else:
                lines.append(
                    f"→ Confidence: {confidence_level} ({confidence_reason})  [{confidence_score}%]"
                )

        elif "LOCALIZED" in state:

            lines.append("")

            if args.color:
                lines.append(f"{BOLD}{fg(0xffffff)}Conclusion:{RESET}")
            else:
                lines.append("Conclusion:")

            # --------------------------------------
            # Intent
            # --------------------------------------
            if intent:
                if args.color:
                    lines.append(f"{fg(0xaaaaaa)}→ {intent}{RESET}")
                else:
                    lines.append(f"→ {intent}")
            else:
                fallback = "Likely a single dominant workload"
                if args.color:
                    lines.append(f"{fg(0xaaaaaa)}→ {fallback}{RESET}")
                else:
                    lines.append(f"→ {fallback}")

            # --------------------------------------
            # Confidence
            # --------------------------------------
            if args.color:
                lines.append(
                    f"{fg(0xaaaaaa)}→ Confidence: {RESET}"
                    f"{fg(0xffffff)}{confidence_level}{RESET} "
                    f"{fg(0x777777)}({confidence_reason}){RESET}"
                    f"{fg(0xaaaaaa)}[{RESET}"
                    f"{fg(0xffffff)}{confidence_score}{RESET}"
                    f"{fg(0xaaaaaa)}%]{RESET}"
                )
            else:
                lines.append(
                    f"→ Confidence: {confidence_level} ({confidence_reason}) [{confidence_score}%]"
                )


        else:

            lines.append("")

            if args.color:
                lines.append(f"{BOLD}{fg(0xffffff)}Conclusion:{RESET}")
            else:
                lines.append("Conclusion:")

            # --------------------------------------
            # Intent
            # --------------------------------------
            if intent:
                if args.color:
                    lines.append(f"{fg(0xaaaaaa)}→ {intent}{RESET}")
                else:
                    lines.append(f"→ {intent}")
            else:
                fallback = "No strong workload pattern detected"
                if args.color:
                    lines.append(f"{fg(0xaaaaaa)}→ {fallback}{RESET}")
                else:
                    lines.append(f"→ {fallback}")

            # --------------------------------------
            # Confidence
            # --------------------------------------
            if args.color:
                lines.append(
                    f"{fg(0xaaaaaa)}→ Confidence: {RESET}"
                    f"{fg(0xffffff)}{confidence_level}{RESET} "
                    f"{fg(0x777777)}({confidence_reason}){RESET}"
                    f"{fg(0xaaaaaa)}[{RESET}"
                    f"{fg(0xffffff)}{confidence_score}{RESET}"
                    f"{fg(0xaaaaaa)}%]{RESET}"
                )
            else:
                lines.append(
                    f"→ Confidence: {confidence_level} ({confidence_reason}) [{confidence_score}%]"
                )

        return lines

    # ------------------------------------------------------------
    # Method: detect_intent()
    # ------------------------------------------------------------
    def detect_intent(self, processes, state, args):
        """
        Detect likely workload intent based on process patterns.
        """

        if not processes:
            return None

        commands = [p.comm.lower() for p in processes]

        # --------------------------------------------------
        # Stress testing / synthetic load
        # --------------------------------------------------
        # --------------------------------------------------
        # Stress testing / synthetic load (weighted)
        # --------------------------------------------------
        yes_count = commands.count("yes")

        # Use lower() consistently to match earlier normalization
        yes_cpu = sum(p.cpu for p in processes if p.comm.lower() == "yes")
        total_cpu = round(sum(p.cpu for p in processes), 1)  # avoid div by zero

        # Require both repetition AND dominance
        if yes_count >= 2 and (yes_cpu / total_cpu) >= 0.6:
            if args.color:
                if state == "LIGHT":
                    return f"{fg(0xaaaaaa)}Early signs of a stress-testing workload (repeated CPU-bound processes){RESET}"

                return f"{fg(0xaaaaaa)}This resembles a stress-testing workload (dominant repeated CPU-bound processes){RESET}"
            else:
                if state == "LIGHT":
                    return "Early signs of a stress-testing workload (repeated CPU-bound processes)"

                return "This resembles a stress-testing workload (dominant repeated CPU-bound processes)"

        # --------------------------------------------------
        # Compilation / build systems
        # --------------------------------------------------
        build_tools = {"cc", "gcc", "clang", "make", "ld"}
        if any(cmd in build_tools for cmd in commands):
            if args.color:
                return f"{fg(0xaaaaaa)}This resembles a compilation workload (parallel build processes){RESET}"
            else:
                return "This resembles a compilation workload (parallel build processes)"

        # --------------------------------------------------
        # Cryptographic / benchmarking
        # --------------------------------------------------
        if any(cmd.startswith("openssl") for cmd in commands):
            if args.color:
                return f"{fg(0xaaaaaa)}This resembles a cryptographic or benchmarking workload{RESET}"
            else:
                return "This resembles a cryptographic or benchmarking workload"

        # --------------------------------------------------
        # Interactive / user-driven
        # --------------------------------------------------
        if state == "LIGHT":
            if any("+" in p.stat for p in processes):
                if args.color:
                    return f"{fg(0xaaaaaa)}This appears to be an interactive user-driven workload{RESET}"
                else:
                    return "This appears to be an interactive user-driven workload"

        # --------------------------------------------------
        # Idle fallback
        # --------------------------------------------------
        if state == "IDLE":
            if args.color:
                return f"{fg(0xaaaaaa)}System appears idle with no significant workload{RESET}"
            else:
                return "System appears idle with no significant workload"

        return None

    # ------------------------------------------------------------
    # Method: compute_confidence()
    # ------------------------------------------------------------
    def compute_confidence(self, processes, state, used, cpu_count, core_saturated):

        if not processes:
            return "LOW", "no strong workload pattern", 10

        util_ratio = used / max(cpu_count, 1)

        # ------------------------------------------
        # IDLE
        # ------------------------------------------
        if state == "IDLE":
            return "HIGH", "clear absence of CPU activity", 95

        # ------------------------------------------
        # LIGHT
        # ------------------------------------------
        if state == "LIGHT":
            return "MEDIUM", "activity present but not dominant", 50

        # ------------------------------------------
        # HEAVY DISTRIBUTED
        # ------------------------------------------
        if state == "HEAVY_DISTRIBUTED":
            return "HIGH", "clear CPU saturation across multiple cores", 90

        # ------------------------------------------
        # HEAVY LOCALIZED
        # ------------------------------------------
        if state == "HEAVY_LOCALIZED":
            top = max(processes, key=lambda p: p.cpu)
            if top.cpu >= 60:
                return "HIGH", "single process strongly saturating CPU", 88
            return "HIGH", "strong localized workload", 80

        # ------------------------------------------
        # MODERATE
        # ------------------------------------------
        if "MODERATE" in state:

            if core_saturated == cpu_count:
                if "LOCALIZED" in state:
                    return "HIGH", "single process driving full CPU utilization", 85
                return "HIGH", "workload fully utilizing all CPU cores", 85

            if util_ratio >= 0.5 and len(processes) >= 3:
                return "HIGH", "consistent workload across multiple processes", 78

            return "MEDIUM", "moderate but stable activity", 60

        # ------------------------------------------
        # Fallback
        # ------------------------------------------
        return "LOW", "no strong workload pattern", 20