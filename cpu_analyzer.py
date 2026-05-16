# cpu_analyzer.py

# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 Markus Johnsson

import time
import sys

# Local imports
from constants import RESET, BOLD, fg, STAT_MEANINGS
from random_tip import random_tip
from utils import (
    extract_unique_stats,
    get_cpu_count,
    get_per_core_usage,
    compute_per_core_usage,
    read_cp_times,
    get_cpu_topology,
)
from temporal_history import TemporalHistory

class CPUAnalyzer:
    """
    Analyzes process CPU usage and produces a structured summary
    for the default cpuvw output.

    This is the intelligence layer of cpuvw.
    """

    # ----------------------------------------------------------------------
    # Method: __init__
    # ----------------------------------------------------------------------
    def __init__(self):

        self.temporal_history = TemporalHistory()

    # -----------------------------------------------------------------
    # Method: observe
    # -----------------------------------------------------------------
    def observe(
        self,
        fetcher,
        args,
        duration=7.5,
        interval=0.5,
        use_color=True,
        mode="standard",
        tips_enabled=True
    ):

        # Clear previous history
        self.temporal_history.history.clear()

        start_time = time.time()
        core_samples = []

        # Print which type of analysis is being performed
        if mode == "standard":
            msg = "Running standard analysis. Please wait..."

        elif mode == "more":
            msg = "Running extended analysis. Please wait..."

        elif mode == "deep":
            msg = "Running extended behavioral analysis. Please wait..."

        else:
            msg = "Running analysis. Please wait..."

        print(msg,file=sys.stderr)

        # Add a random tip while waiting for analysis...
        if tips_enabled and args.analyze:
            tip = random_tip()

            print("")
            if args.color:
                print(f"{fg(0x5287d6)}{'\n' + tip}{RESET}", file=sys.stderr)
            else:
                print('\n' + tip, file=sys.stderr)

        # ---------------------------------------------------------
        # Temporal observation window
        # ---------------------------------------------------------
        while time.time() - start_time < duration:

            processes = fetcher.fetch(args)

            # Remove idle process from temporal cognition
            processes = [
                p for p in processes
                if (p.comm or "").lower() != "idle"
            ]

            # -------------------------------------------------
            # Lightweight temporal snapshot
            # -------------------------------------------------
            total_cpu = sum(p.cpu for p in processes)

            dominant = max(
                processes,
                key=lambda p: p.cpu,
                default=None,
            )

            top = sorted(
                processes,
                key=lambda p: p.cpu,
                reverse=True,
            )[:5]

            self.temporal_history.add_snapshot(
                total_cpu=total_cpu,
                state="UNKNOWN",
                dominant_pid=dominant.pid if dominant else None,
                dominant_cpu=dominant.cpu if dominant else 0.0,
                top_pids=[p.pid for p in top],
                distribution_type="UNKNOWN",
            )

            # -------------------------------------------------
            # Collect synchronized core telemetry
            # -------------------------------------------------
            core_samples.append(
                read_cp_times()
            )

            time.sleep(interval)

        core_usages = compute_per_core_usage(
            core_samples
        )

        # ---------------------------------------------------------
        # Calculate logical CPU info
        # ---------------------------------------------------------
        logical_saturated = sum(
            1 for u in core_usages if u >= 80
        )

        logical_active = sum(
            1 for u in core_usages if 40 <= u < 80
        )

        logical_low = sum(
            1 for u in core_usages if 20 <= u < 40
        )

        logical_used = (
                logical_saturated +
                logical_active +
                logical_low
        )

        # ---------------------------------------------------------
        # FINAL synchronized snapshot
        # ---------------------------------------------------------
        final_processes = fetcher.fetch(args)

        final_processes = [
            p for p in final_processes
            if (p.comm or "").lower() != "idle"
        ]

        summary = self.temporal_history.get_summary()
        summary["logical_active_count"] = logical_used
        summary["logical_total_count"] = len(core_usages)

        return {
            "processes": final_processes,
            "core_usages": core_usages,
            "temporal_summary": summary,
        }

    # ------------------------------------------------------------
    # Method: analyze()
    # ------------------------------------------------------------
    def analyze(self,
        processes,
        args,
        use_color=False,
        core_usages=None,
        temporal_summary=None
    ):
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

        ## --- Temporal history ---
        total_cpu = sum(p.cpu for p in processes)

        if processes:

            dominant_proc = max(
                processes,
                key=lambda p: p.cpu
            )

            dominant_pid = dominant_proc.pid
            dominant_cpu = dominant_proc.cpu

        else:

            dominant_pid = None
            dominant_cpu = 0.0

        top_pids = [p.pid for p in top[:5]]

        distribution_type = (
            "DISTRIBUTED"
            if "DISTRIBUTED" in state
            else "LOCALIZED"
        )

        self.temporal_history.add_snapshot(
            total_cpu=total_cpu,
            state=state,
            dominant_pid=dominant_pid,
            dominant_cpu=dominant_cpu,
            top_pids=top_pids,
            distribution_type=distribution_type,
        )

        if temporal_summary is None:
            temporal_summary = (
                self.temporal_history.get_summary()
            )

        # --------------------------------------------------
        # Contributor stability analysis
        # --------------------------------------------------
        top_pid_sets = [
            set(snapshot.get("top_pids", []))
            for snapshot in self.temporal_history.history
        ]

        stable_samples = 0

        for i in range(1, len(top_pid_sets)):

            overlap = len(
                top_pid_sets[i] &
                top_pid_sets[i - 1]
            )

            if overlap >= 3:
                stable_samples += 1

        if len(top_pid_sets) > 1:

            contributor_stability = (
                                            stable_samples /
                                            (len(top_pid_sets) - 1)
                                    ) * 100

        else:
            contributor_stability = 0.0

        # --------------------------------------------------
        # Observation consistency
        # --------------------------------------------------
        dominant_persistence = temporal_summary.get(
            "dominant_persistence",
            0.0
        )

        cpu_delta = temporal_summary.get(
            "cpu_delta",
            0.0
        )

        consistency_score = (
                (dominant_persistence * 0.5) +
                (contributor_stability * 0.5)
        )

        if cpu_delta < 10:
            consistency_score += 10

        elif cpu_delta > 30:
            consistency_score -= 10

        consistency_score = max(
            0,
            min(consistency_score, 100)
        )

        return {
            "state": state,
            "message": message,
            "dominant": primary,
            "dominant_list": dominant_list,
            "dominant_desc": dominant_desc,
            "top": top,
            "filtered": real_processes,
            "temporal_summary": temporal_summary,
            "contributor_stability": contributor_stability,
            "consistency_score": consistency_score,
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
    def generate_analysis(self,
                          analysis,
                          analysis_duration,
                          analysis_interval,
                          args,
                          core_usages=None,
                          visible=None
        ):
        """
        Generate human-style analytical report (for --analyze mode).
        """

        # Normalize
        logical_usages = core_usages

        state = analysis["state"]
        processes = analysis.get("filtered", analysis.get("processes", []))
        dominant = analysis["dominant"]
        temporal = analysis.get("temporal_summary", {})

        contributor_stability = analysis.get(
            "contributor_stability",
            0.0
        )

        consistency_score = analysis.get(
            "consistency_score",
            0.0
        )

        # --------------------------------------------------
        # Logical CPU topology
        # --------------------------------------------------
        if logical_usages is None:
            logical_usages = get_per_core_usage(
                duration=analysis_duration,
                interval=analysis_interval,
            )

        logical_saturated = sum(
            1 for u in logical_usages if u >= 80
        )
        logical_active = sum(
            1 for u in logical_usages if 40 <= u < 80
        )
        logical_low = sum(
            1 for u in logical_usages if 20 <= u < 40
        )
        logical_idle = sum(
            1 for u in logical_usages if u < 20
        )
        logical_total = len(logical_usages)

        logical_used = (
                logical_saturated +
                logical_active +
                logical_low
        )

        # --------------------------------------------------
        # Physical core topology
        # --------------------------------------------------
        topology = get_cpu_topology()

        physical_cores = topology["physical_cores"]

        # --------------------------------------------------
        # Compute physical core utilization
        # --------------------------------------------------
        physical_usages = []

        for core_group in physical_cores:

            usage = max(
                logical_usages[cpu]
                for cpu in core_group
                if cpu < len(logical_usages)
            )

            physical_usages.append(usage)

        physical_saturated = sum(
            1 for u in physical_usages if u >= 80
        )

        physical_active = sum(
            1 for u in physical_usages if 40 <= u < 80
        )

        physical_low = sum(
            1 for u in physical_usages if 20 <= u < 40
        )

        physical_idle = sum(
            1 for u in physical_usages if u < 20
        )

        physical_used = (
                physical_saturated +
                physical_active +
                physical_low
        )

        physical_core_count = len(physical_cores)

        # --------------------------------------------------
        # Observed actively utilized logical CPU's
        # --------------------------------------------------
        used = (
                logical_saturated +
                logical_active +
                logical_low
        )

        lines = []

        # --------------------------------------------------
        # 1. System behavior (distribution)
        # --------------------------------------------------
        active_processes = [p for p in processes if p.cpu >= 5.0]
        total_cpu_usage = round(sum(p.cpu for p in active_processes), 1)
        physical_cpu_capacity = physical_core_count * 100

        # Extract some needed data
        mean_cpu = temporal.get("mean_cpu", 0.0)
        cpu_delta = temporal.get("cpu_delta", 0.0)
        dominant_persistence = temporal.get("dominant_persistence", 0.0)
        spread_ratio = (
                physical_used / physical_core_count
        )

        top_pid_sets = [
            set(snapshot.get("top_pids", []))
            for snapshot in self.temporal_history.history
        ]

        stable_samples = 0

        for i in range(1, len(top_pid_sets)):

            overlap = len(
                top_pid_sets[i] &
                top_pid_sets[i - 1]
            )

            if overlap >= 3:
                stable_samples += 1

        if len(top_pid_sets) > 1:
            contributor_stability = (
                                            stable_samples / (len(top_pid_sets) - 1)
                                    ) * 100
        else:
            contributor_stability = 0.0


        if "DISTRIBUTED" in state:

            # Use color
            if args.color:
                lines.append(f"{fg(0xaaaaaa)}• {RESET}"
                             f"{fg(0xffffff)}Core Observations:{RESET}")

                lines.append(f"{fg(0xaaaaaa)}  • CPU activity is being shared across multiple active workloads{RESET}")

                lines.append(
                    f"{fg(0xaaaaaa)}    └─ {RESET}"
                    f"{fg(0xffffff)}{len(active_processes)}{RESET}"
                    f"{fg(0xaaaaaa)} processes are actively consuming {RESET}"
                    f"{fg(0xffffff)}{total_cpu_usage}{RESET}"
                    f"{fg(0xaaaaaa)}% of total CPU resources{RESET} "
                    f"({RESET}"
                    f"{fg(0xffffff)}{physical_cpu_capacity}{RESET}"
                    f"{fg(0xaaaaaa)}% → {RESET}"
                    f"{fg(0xffffff)}{physical_core_count}{RESET}"
                    f"{fg(0xaaaaaa)} x "
                    f"{fg(0xffffff)}100{RESET}"
                    f"{fg(0xaaaaaa)}%){RESET}"
                )

                # First: capacity view
                lines.append(f"{fg(0xaaaaaa)}    └─ {RESET}"
                    f"{fg(0xffffff)}{physical_used}{RESET}"
                    f"{fg(0xaaaaaa)} / {RESET}"
                    f"{fg(0xffffff)}{physical_core_count}{RESET}"
                    f"{fg(0xaaaaaa)} physical cores actively utilized during the observation window{RESET}"
                )

                # Second: distribution view
                lines.append(
                    f"{fg(0xaaaaaa)}    └─ {RESET}"
                    f"{fg(0xffffff)}{physical_saturated} {RESET}"
                    f"{fg(0xaaaaaa)}physical core{'s' if physical_saturated != 1 else ''} saturated, {RESET}"
                    f"{fg(0xffffff)}{physical_active} {RESET}"
                    f"{fg(0xaaaaaa)}active, {RESET}"
                    f"{fg(0xffffff)}{physical_low} {RESET}"
                    f"{fg(0xaaaaaa)}low activity, {RESET}"
                    f"{fg(0xffffff)}{physical_idle} {RESET}"
                    f"{fg(0xaaaaaa)}idle{RESET}"
                )
            # No color
            else:
                lines.append("  Core Observations:")

                lines.append("  • CPU activity is being shared across multiple active workloads")
                lines.append(f"    └─ {len(active_processes)} processes are actively consuming "
                     f"{total_cpu_usage}% of total CPU resources "
                     f"({physical_cpu_capacity}% → {physical_core_count} x 100%)"
                )

                # First: capacity view
                lines.append(f"    └─ {physical_used} / {physical_core_count} "
                    f"physical cores actively utilized during the observation window"
                )

                # Second: distribution view
                lines.append(
                    f"    └─ {physical_saturated} physical core{'s' if physical_saturated != 1 else ''} saturated, "
                    f"{physical_active} active, {physical_low} low activity, {physical_idle} idle"
                )

            # ------------------------------------------
            # Distribution interpretation
            # ------------------------------------------
            if args.color:

                if spread_ratio >= 0.90:

                    if physical_saturated >= (
                            physical_core_count * 0.7
                    ):

                        lines.append(
                            f"{fg(0xaaaaaa)}    └─ High execution pressure is distributed "
                            f"across nearly all physical cores{RESET}"
                        )

                    else:

                        lines.append(
                            f"{fg(0xaaaaaa)}    └─ CPU activity is broadly distributed "
                            f"across most physical cores{RESET}"
                        )

                elif spread_ratio >= 0.50:

                    lines.append(
                        f"{fg(0xaaaaaa)}    └─ Execution pressure is moderately "
                        f"distributed across active physical cores{RESET}"
                    )

                else:

                    lines.append(
                        f"{fg(0xaaaaaa)}    └─ CPU activity is concentrated on "
                        f"a limited number of physical cores{RESET}"
                    )

                    if (
                            spread_ratio < 0.20 and
                            physical_saturated <= 2
                    ):
                        lines.append(
                            f"{fg(0xaaaaaa)}    └─ Workload characteristics resemble "
                            f"single-thread constrained execution{RESET}"
                        )

            else:

                if spread_ratio >= 0.90:

                    if physical_saturated >= (
                            physical_core_count * 0.7
                    ):

                        lines.append(
                            "    └─ High execution pressure is distributed "
                            "across nearly all physical cores"
                        )

                    else:

                        lines.append(
                            "    └─ CPU activity is broadly distributed "
                            "across most physical cores"
                        )

                elif spread_ratio >= 0.50:

                    lines.append(
                        "    └─ Execution pressure is moderately "
                        "distributed across active physical cores"
                    )

                else:

                    lines.append(
                        "    └─ CPU activity is concentrated on "
                        "a limited number of physical cores"
                    )

                    if (
                            spread_ratio < 0.20 and
                            physical_saturated <= 2
                    ):
                        lines.append(
                            "    └─ Workload characteristics resemble "
                            "single-thread constrained execution"
                        )

        elif "LOCALIZED" in state:

            # Use color
            if args.color:
                lines.append(f"{fg(0xaaaaaa)}• {RESET}"
                             f"{fg(0xffffff)}Core Observations:{RESET}")

                lines.append(f"{fg(0xaaaaaa)}  • CPU load is concentrated in a small number of processes{RESET}")
                # First: capacity view
                lines.append(f"{fg(0xaaaaaa)}    └─ {RESET}"
                             f"{fg(0xffffff)}{physical_used}{RESET} "
                             f"{fg(0xaaaaaa)} / {RESET} "
                             f"{fg(0xffffff)}{physical_core_count}{RESET} "
                             f"{fg(0xaaaaaa)}physical cores actively utilized during the observation window{RESET}"
                             )

                # Second: distribution view
                lines.append(
                            f"{fg(0xaaaaaa)}    └─ {RESET}"
                            f"{fg(0xffffff)}{physical_saturated} {RESET}"
                            f"{fg(0xaaaaaa)}physical core{'s' if physical_saturated != 1 else ''} saturated, {RESET}"
                            f"{fg(0xffffff)}{physical_active} {RESET}"
                            f"{fg(0xaaaaaa)}active, {RESET}"
                            f"{fg(0xffffff)}{physical_low} {RESET}"
                            f"{fg(0xaaaaaa)}low activity, {RESET}"
                            f"{fg(0xffffff)}{physical_idle} {RESET}"
                            f"{fg(0xaaaaaa)}idle{RESET}"
                )

            # No color
            else:
                lines.append("• Core Observations:")

                lines.append(f"  • CPU load is concentrated in a small number of processes")
                # First: capacity view
                lines.append(f"    └─ {physical_used} / {physical_core_count} physical cores actively utilized during the observation window")

                # Second: distribution view
                lines.append(
                    f"    └─ {physical_saturated} physical core{'s' if physical_saturated != 1 else ''} saturated, "
                    f"{physical_active} active, {physical_low} low activity, {physical_idle} idle"
                )

            # ------------------------------------------
            # Imbalance detection (proper model)
            # ------------------------------------------
            total_physical = physical_core_count

            if args.color:

                if physical_saturated == total_physical:
                    lines.append(f"{fg(0xaaaaaa)}    └─ CPU load is fully distributed across all physical cores{RESET}")

                elif physical_saturated >= total_physical * 0.7:
                    lines.append(f"{fg(0xaaaaaa)}    └─ CPU load is well distributed across all physical cores{RESET}")

                elif physical_saturated <= max(1, int(total_physical * 0.3)):
                    lines.append(f"{fg(0xaaaaaa)}    └─ CPU load is unevenly distributed across all physical cores{RESET}")
                    lines.append(f"{fg(0xaaaaaa)}    └─ Workload may be limited by single-thread performance{RESET}")

            else:

                if physical_saturated == total_physical:
                    lines.append("    └─ CPU load is fully distributed across all physical cores")

                elif physical_saturated >= total_physical * 0.7:
                    lines.append("    └─ CPU load is well distributed across all physical cores")

                elif physical_saturated <= max(1, int(total_physical * 0.3)):
                    lines.append("    └─ CPU load is unevenly distributed across all physical cores")
                    lines.append("    └─ Workload may be limited by single-thread performance")

        else:
            # Use color
            if args.color:
                lines.append(f"{fg(0xaaaaaa)}• {RESET}"
                             f"{fg(0xffffff)}Core Observations:{RESET}")

                lines.append(f"{fg(0xaaaaaa)}  • CPU activity is present but not strongly concentrated{RESET}")
                # First: capacity view
                lines.append(f"{fg(0xaaaaaa)}    └─ {RESET}"
                             f"{fg(0xffffff)}{physical_used} {RESET}"
                             f"/ {fg(0xffffff)}{physical_core_count} {RESET}"
                             f"{fg(0xaaaaaa)}physical cores are actively utilized{RESET}")

                # Second: distribution view
                lines.append(
                    f"{fg(0xaaaaaa)}    └─ {RESET}"
                    f"{fg(0xffffff)}{physical_saturated} {RESET}"
                    f"{fg(0xaaaaaa)}physical core{'s' if physical_saturated != 1 else ''} saturated, {RESET}"
                    f"{fg(0xffffff)}{physical_active} {RESET}"
                    f"{fg(0xaaaaaa)}active, {RESET}"
                    f"{fg(0xffffff)}{physical_low} {RESET}"
                    f"{fg(0xaaaaaa)}low activity, {RESET}"
                    f"{fg(0xffffff)}{physical_idle} {RESET}"
                    f"{fg(0xaaaaaa)}idle{RESET}"
                )

            # No color
            else:
                lines.append("• Core Observations:")

                lines.append("  • CPU activity is present but not strongly concentrated")
                # First: capacity view
                lines.append(f"    └─ {physical_used} / {physical_core_count} physical cores are actively utilized")

                # Second: distribution view
                lines.append(
                    f"    └─ {physical_saturated} physical core{'s' if physical_saturated != 1 else ''} saturated, "
                    f"{physical_active} active, {physical_low} low activity, {physical_idle} idle"
                )

            # ------------------------------------------
            # Imbalance detection (proper model)
            # ------------------------------------------

            total_physical = physical_core_count

            if args.color:

                if physical_saturated == total_physical:
                    lines.append(f"{fg(0xaaaaaa)}    └─ CPU load is fully distributed across all physical cores{RESET}")

                elif physical_saturated >= total_physical * 0.7:
                    lines.append(f"{fg(0xaaaaaa)}    └─ CPU load is well distributed across all physical cores{RESET}")

                elif physical_saturated <= max(1, int(total_physical * 0.3)):
                    lines.append(f"{fg(0xaaaaaa)}    └─ CPU load is unevenly distributed across all physical cores{RESET}")
                    lines.append(f"{fg(0xaaaaaa)}    └─ Workload may be limited by single-thread performance{RESET}")

            else:

                if physical_saturated == total_physical:
                    lines.append("    └─ CPU load is fully distributed across all physical cores")

                elif physical_saturated >= total_physical * 0.7:
                    lines.append("    └─ CPU load is well distributed across all physical cores")

                elif physical_saturated <= max(1, int(total_physical * 0.3)):
                    lines.append("    └─ CPU load is unevenly distributed across all physical cores")
                    lines.append("    └─ Workload may be limited by single-thread performance")


        # --------------------------------------------------
        # Logical CPU insight
        # --------------------------------------------------
        if logical_saturated:

            # Using colors
            if args.color:

                if args.analyze in ("more", "deep"):
                    lines.append(f"{fg(0xaaaaaa)}•{RESET} Logical CPU observations:")

                    # ------------------------------------------
                    # Saturated logical CPUs
                    # ------------------------------------------
                    if logical_saturated >= 1:

                        if logical_saturated == 1:
                            lines.append(
                                f"  {fg(0xaaaaaa)}• {RESET}"
                                f"{logical_saturated}"
                                f"{fg(0xaaaaaa)} logical CPU is saturated {RESET}"
                                f"{fg(0xaaaaaa)}({RESET}"
                                f"{fg(0xffffff)}≥80{RESET}"
                                f"{fg(0xaaaaaa)}% {RESET}"
                                f"{fg(0xaaaaaa)}utilization){RESET}"
                            )

                        else:
                            lines.append(
                                f"  {fg(0xaaaaaa)}• {RESET}"
                                f"{logical_saturated} "
                                f"{fg(0xaaaaaa)}logical CPUs are saturated {RESET}"
                                f"{fg(0xaaaaaa)}({RESET}"
                                f"{fg(0xffffff)}≥80{RESET}"
                                f"{fg(0xaaaaaa)}% {RESET}"
                                f"{fg(0xaaaaaa)}utilization){RESET}"
                            )

                        # ------------------------------------------
                        # Interpretation layer
                        # ------------------------------------------
                        if logical_saturated >= logical_total * 0.5:

                            lines.append(
                                f"{fg(0xaaaaaa)}    └─ Sustained execution pressure is affecting a large portion of logical CPUs{RESET}"
                            )

                        elif logical_saturated >= 2:

                            lines.append(
                                f"{fg(0xaaaaaa)}    └─ Multiple logical CPUs are under sustained execution pressure{RESET}"
                            )

                        else:

                            lines.append(
                                f"{fg(0xaaaaaa)}    └─ Localized execution pressure is concentrated on a single logical CPU{RESET}"
                            )

                # --------------------------------------------------
                # Limited logical CPU utilization efficiency
                # --------------------------------------------------
                if (
                        args.analyze == "deep"
                        and ("MODERATE" in state or "HEAVY" in state)
                        and logical_used <= logical_total * 0.3
                ):
                    lines.append(
                        f"{fg(0xaaaaaa)}  • CPU activity is concentrated on a limited number of logical CPUs{RESET}"
                    )

                    lines.append(
                        f"{fg(0xaaaaaa)}     └─ Significant logical CPU capacity remains available{RESET}"
                    )

            # No colors
            else:
                if args.analyze in ("more", "deep"):
                    lines.append("• Logical CPU observations:")

                    # ------------------------------------------
                    # Saturated logical CPUs
                    # ------------------------------------------
                    if logical_saturated >= 1:

                        if logical_saturated == 1:
                            lines.append(
                                f"  • {logical_saturated} logical CPU is saturated "
                                f"(≥80% utilization)"
                            )

                        else:
                            lines.append(
                                f"  • {logical_saturated} logical CPUs are saturated "
                                f"(≥80% utilization)"
                            )

                        # ------------------------------------------
                        # Interpretation layer
                        # ------------------------------------------
                        if logical_saturated >= logical_total * 0.5:

                            lines.append(
                                "    └─ Sustained execution pressure is affecting a large portion of logical CPUs"
                            )

                        elif logical_saturated >= 2:

                            lines.append(
                                "    └─ Multiple logical CPUs are under sustained execution pressure"
                            )

                        else:

                            lines.append(
                                "    └─ Localized execution pressure is concentrated on a single logical CPU"
                            )

                # --------------------------------------------------
                # Limited logical CPU utilization efficiency
                # --------------------------------------------------
                if (
                        args.analyze == "deep"
                        and ("MODERATE" in state or "HEAVY" in state)
                        and logical_used <= logical_total * 0.3
                ):
                    lines.append(
                        "  • CPU activity is concentrated on a limited number of logical CPUs"
                    )

                    lines.append(
                        "     └─ Significant logical CPU capacity remains available"
                    )

        # --------------------------------------------------
        # Temporal history insight
        # --------------------------------------------------
        if temporal:

            # --------------------------------------------------
            # Deep behavioral observations
            # --------------------------------------------------
            if args.analyze in ("more", "deep"):

                # Use colors
                if args.color:
                    lines.append(f"{fg(0xaaaaaa)}• {RESET}"
                                 f"{fg(0xffffff)}Temporal observations:{RESET}")

                    if cpu_delta < 10:

                        lines.append(
                            f"{fg(0xaaaaaa)}  • System behavior remained highly consistent across the extended observation window{RESET}"
                        )

                    elif cpu_delta < 30:

                        lines.append(
                            f"{fg(0xaaaaaa)}  • Workload behavior evolved moderately during the observation period{RESET}"
                        )

                    else:

                        lines.append(
                            f"{fg(0xaaaaaa)}  • Workload characteristics shifted noticeably during the observation period{RESET}"
                        )

                    # ------------------------------------------
                    # Contributor stability
                    # ------------------------------------------
                    if contributor_stability >= 80:
                        lines.append(
                            f"{fg(0xaaaaaa)}  • Workload activity remained highly consistent during observation ({RESET}"
                            f"{contributor_stability:.0f}"
                            f"{fg(0xaaaaaa)})%{RESET}"
                        )

                        # ------------------------------------------
                        # Dominant persistence
                        # ------------------------------------------
                        if dominant_persistence >= 80:
                            lines.append(
                                f"{fg(0xaaaaaa)}     └─ The same workload remained dominant throughout most observation samples ({RESET}"
                                f"{dominant_persistence:.0f}"
                                f"{fg(0xaaaaaa)})%{RESET}"
                            )

                            lines.append(
                                f"{fg(0xaaaaaa)}     └─ The workload pattern remained stable throughout the extended observation period{RESET}"
                            )


                    elif contributor_stability >= 50:
                        lines.append(
                            f"{fg(0xaaaaaa)}  • Workload activity shifted moderately during observation ({RESET}"
                            f"{contributor_stability:.0f}"
                            f"{fg(0xaaaaaa)})%{RESET}"
                        )

                    else:
                        lines.append(
                            f"{fg(0xaaaaaa)}  • Workload activity changed frequently during observation ({RESET}"
                            f"{contributor_stability:.0f}"
                            f"{fg(0xaaaaaa)})%{RESET}"
                        )

                # No colors
                else:
                    if args.analyze in ("more", "deep"):

                        lines.append("• Temporal observations:")

                        if cpu_delta < 10:

                            lines.append(
                                "  • System behavior remained highly consistent across the extended observation window"
                            )

                        elif cpu_delta < 30:

                            lines.append(
                                "  • Workload behavior evolved moderately during the observation period"
                            )

                        else:

                            lines.append(
                                "  • Workload characteristics shifted noticeably during the observation period"
                            )

                        # ------------------------------------------
                        # Contributor stability
                        # ------------------------------------------
                        if contributor_stability >= 80:
                            lines.append(
                                f"  • Workload activity remained highly consistent during observation"
                                f" ({contributor_stability:.0f})%"
                            )

                            # ------------------------------------------
                            # Dominant persistence
                            # ------------------------------------------
                            if dominant_persistence >= 80:
                                lines.append(
                                    f"     └─ The same workload remained dominant throughout most observation samples"
                                    f" ({dominant_persistence:.0f})%"
                                )

                                lines.append(
                                    f"     └─ The workload pattern remained stable throughout the extended observation period"
                                )

                        elif contributor_stability >= 50:
                            lines.append(
                                f"  • Workload activity shifted moderately during observation"
                                f" ({contributor_stability:.0f})%"
                            )

                        else:
                            lines.append(
                                f"  • Workload activity changed frequently during observation"
                                f" ({contributor_stability:.0f})%"
                            )


        # --------------------------------------------------
        # Behavioral Observations & load intensity
        # --------------------------------------------------

        # Using colors
        if args.color:

            lines.append(f"{fg(0xaaaaaa)}• {RESET}"
                         f"{fg(0xffffff)}Behavioral Observations:{RESET}")

            # --------------------------------------------------
            # Dominant process insight
            # --------------------------------------------------
            if dominant:

                # Using colors
                if args.color:
                    if state == "IDLE":
                        lines.append(f"{fg(0xaaaaaa)}  • Most active process: {RESET}"
                                     f"{fg(0x5287d6)}{dominant.comm} {RESET}"
                                     f"{fg(0xaaaaaa)}({RESET}"
                                     f"{fg(0xffffff)}{dominant.cpu:.1f}{RESET}"
                                     f"{fg(0xaaaaaa)}%){RESET}")

                    else:
                        lines.append(f"{fg(0xaaaaaa)}  • Dominant workload: {RESET}"
                                     f"{fg(0x5287d6)}{dominant.comm} {RESET}"
                                     f"{fg(0xaaaaaa)}({RESET}"
                                     f"{fg(0xffffff)}{dominant.cpu:.1f}{RESET}"
                                     f"{fg(0xaaaaaa)}%){RESET}")

                # No colors
                else:
                    if state == "IDLE":
                        lines.append(f"  • Most active process: {dominant.comm} ({dominant.cpu:.1f}%)")
                    else:
                        lines.append(f"  • Dominant workload: {dominant.comm} ({dominant.cpu:.1f}%)")

            # --------------------------------------------------
            # Load Intensity
            # --------------------------------------------------

            if "HEAVY" in state:
                lines.append(f"{fg(0xaaaaaa)}  • System is under sustained computational pressure{RESET}")

            elif "MODERATE" in state:
                lines.append(f"{fg(0xaaaaaa)}  • Workload is noticeable but not saturating the system{RESET}")

            elif state == "LIGHT":
                lines.append(f"{fg(0xaaaaaa)}  • System is responsive with light activity{RESET}")

            elif state == "IDLE":
                lines.append(f"{fg(0xaaaaaa)}  • System is mostly idle{RESET}")

        # No colors.
        else:
            lines.append("• Behavioral Observations:")

            if "HEAVY" in state:
                lines.append(
                    f"  • System is under sustained computational pressure")

            elif "MODERATE" in state:
                lines.append(
                    f"  • Workload is noticeable but not saturating the system")

            elif state == "LIGHT":
                lines.append(f"  • System is responsive with light activity")

            elif state == "IDLE":
                lines.append(f"  • System is mostly idle")


        # ------------------------------------------------------------------------------------------
        # STAT interpretation (FULL, no shortcuts)
        # ------------------------------------------------------------------------------------------
        stat_processes = []

        if dominant:
            stat_processes.append(dominant)

        if visible:
            stat_processes.extend(visible)

        stat_chars = sorted(
            extract_unique_stats(stat_processes),
            key=lambda x: [
                # --------------------------------------------------
                # Primary execution states
                # --------------------------------------------------
                "R",  # running
                "S",  # sleeping
                "D",  # uninterruptible sleep
                "I",  # idle kernel thread

                # --------------------------------------------------
                # Stopped / traced
                # --------------------------------------------------
                "T",  # stopped
                "t",  # traced/debugged

                # --------------------------------------------------
                # Dead / zombie
                # --------------------------------------------------
                "Z",  # zombie
                "X",  # dead

                # --------------------------------------------------
                # Legacy / paging
                # --------------------------------------------------
                "W",  # paging

                # --------------------------------------------------
                # Scheduling priority
                # --------------------------------------------------
                "<",  # high priority
                "N",  # low priority

                # --------------------------------------------------
                # Memory / threading
                # --------------------------------------------------
                "L",  # locked pages
                "l",  # multithreaded

                # --------------------------------------------------
                # Session / interaction
                # --------------------------------------------------
                "s",  # session leader
                "+",  # foreground group

                # --------------------------------------------------
                # Analyzer-specific behavioral marker
                # --------------------------------------------------
                "C",  # CPU-bound
            ].index(x)
            if x in [
                "R", "S", "D", "I",
                "T", "t",
                "Z", "X",
                "W",
                "<", "N",
                "L", "l",
                "s", "+",
                "C",
            ] else 99
        )

        # Output section
        if args.analyze != "deep":
            if stat_chars:

                # Use colors
                if args.color:
                    lines.append("")
                    lines.append("STAT Explanation")
                    lines.append(
                        f"{fg(0xaaaaaa)}• {RESET}"
                        f"{fg(0xffffff)}STAT indicates:{RESET}"
                    )

                    # Print the stat explanations
                    for key in stat_chars:
                        desc = STAT_MEANINGS.get(key, "Unknown state")

                        lines.append(
                            f"  {fg(0xaaaaaa)}└─ {RESET}"
                            f"{fg(0xffffff)}{key} {RESET}"
                            f"{fg(0xaaaaaa)}→ {RESET}"
                            f"{fg(0xaaaaaa)}{desc}{RESET}"
                        )

                # No color
                else:
                    lines.append("")
                    lines.append("STAT Explanation")
                    lines.append(
                        f"• STAT indicates:"
                    )

                    # Print the stat explanations
                    for key in stat_chars:
                        desc = STAT_MEANINGS.get(key, "Unknown state")

                        lines.append(
                            f"  └─ {key} → {desc}"
                        )

        # ------------------------------------------------------------------
        # NOTE: line to mention the percentage that the total cores make out
        # ------------------------------------------------------------------
        lines.append("")
        if args.color:
            lines.append(f"NOTE: {fg(0xffffff)}CPU usage is cumulative across cores ("
            f"{fg(0xffffff)}100{RESET}"
            f"% per core on multi-core systems){RESET}")
        else:
            lines.append("NOTE: CPU usage is cumulative across cores (100% per core on multi-core systems)")
        # 5. Conclusion
        # --------------------------------------------------
        intent = self.detect_intent(processes, state, args)

        confidence_level, confidence_reason, confidence_score = self.compute_confidence(
            processes,
            state,
            physical_used,
            physical_core_count,
            physical_saturated
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