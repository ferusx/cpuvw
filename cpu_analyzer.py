from constants import color, RESET, BOLD, fg, THRESHOLD_LIGHT
from utils import extract_unique_stats, describe_stats

class CPUAnalyzer:
    """
    Analyzes process CPU usage and produces a structured summary
    for the default cpuvw output.

    This is the intelligence layer of cpuvw.
    """

    # ------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------
    def analyze(self, processes, args, use_color=False, use_light_color=False):
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
            message = self._build_message(state, use_color, use_light_color)

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
            message = self._build_message(state, use_color, use_light_color)

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

        message = self._build_message(state, use_color, use_light_color)

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
    # CPU State Logic
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

        # Flag: --allow-mod-local-dist condition
        allow_moderate = args.allow_mod_local_dist

        if max_cpu < 10:
            return "IDLE"

        elif max_cpu < 40:
            return "LIGHT"


        elif max_cpu < 70:

            if allow_moderate:

                # Sort processes by CPU descending
                sorted_procs = sorted(processes, key=lambda p: p.cpu, reverse=True)

                # Default fallback
                state = "MODERATE_LOCALIZED"

                # Rule 1: Many active processes → distributed
                if active_count >= 3:
                    return "MODERATE_DISTRIBUTED"

                # Rule 2: Two strong processes sharing load → distributed
                if len(sorted_procs) >= 2:
                    top_two_sum = sorted_procs[0].cpu + sorted_procs[1].cpu

                    if top_two_sum >= 60:
                        return "MODERATE_DISTRIBUTED"

                return state

            else:

                return "MODERATE"
        else:
            if active_count >= 3:
                return "HEAVY_DISTRIBUTED"
            else:
                return "HEAVY_LOCALIZED"

    # ------------------------------------------------------------
    # Human-readable state message
    # ------------------------------------------------------------
    def _build_message(self, state, use_color=False, use_light_color=False):

        # -----------------------------------
        # IDLE (System is idle)
        # -----------------------------------
        if state == "IDLE":
            if use_color:
                return (
                    f"No dominant workload detected. "
                    f"\n{fg(0x009400)}Your system is largely idle.{RESET}"
                )
            elif use_light_color:
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
                    f"{BOLD}High CPU activity{RESET} detected from a {BOLD}single dominant process.{RESET}\n"
                    f"{fg(0xff0000)}Your system is now under{RESET} {color(0x000000, 0xff0000)}heavy localized load.{RESET}"
                )
            elif use_light_color:
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
                    f"{BOLD}High CPU activity{RESET} detected across {BOLD}multiple processes.{RESET}\n"
                    f"{fg(0xff0000)}Your system is now under {RESET}{color(0x000000, 0xff0000)}heavy distributed load.{RESET}"
                )
            elif use_light_color:
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
        if "MODERATE" in state:

            if state == "MODERATE_DISTRIBUTED":
                # Use color
                if use_color:
                    return (
                        f"{BOLD}Moderate CPU activity{RESET} is spread across {BOLD}multiple processes.{RESET}\n"
                        f"{fg(0xecbb00)}Your system is under a {RESET}{color(0x000000,0xecbb00)}balanced yet noticeable workload.{RESET}"
                    )

                # Use light color theme
                elif use_light_color:
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
                        f"{BOLD}Moderate CPU activity {RESET}is driven by a {BOLD}limited number of processes.\n{RESET}"
                        f"Your system is under a focused workload."
                    )

                # Use light color theme
                if use_light_color:
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

            else:
                if use_color:
                    return (
                        f"Moderate CPU activity detected.\n"
                        f"{fg(0xecbb00)}Your system is under {RESET}{color(0x000000,0xecbb00)}moderate load.{RESET}"
                    )
                elif use_light_color:
                    return (
                        f"{fg(0xffffff)}Moderate CPU activity detected.\n{RESET}"
                        f"{fg(0xaaaaaa)}Your system is under {RESET}{fg(0xecbb00)}moderate load.{RESET}"
                    )
                else:
                    return (
                        "Active workload detected. \n"
                    "Your system is under moderate load."
                    )

        # --------------------------------------
        # LIGHT (System under light load)
        # --------------------------------------
        if use_color:
            return (
                f"Light CPU activity detected.\n"
                f"{fg(0x009400)}Your system is now under{RESET} {color(0x000000, 0x00bf00)}light load.{RESET}"
            )
        elif use_light_color:
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
    # Process description engine
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

    def generate_analysis(self, analysis, args):
        """
        Generate human-style analytical report (for --analyze mode).
        """

        state = analysis["state"]
        processes = analysis["filtered"]
        dominant = analysis["dominant"]
        top = analysis["top"]

        lines = []

        # --------------------------------------------------
        # 1. System behavior (distribution)
        # --------------------------------------------------
        active = [p for p in processes if p.cpu >= 5.0]

        if "DISTRIBUTED" in state:
            lines.append("• CPU load is distributed across multiple processes")
            lines.append(f"  └─ {len(active)} processes are actively consuming CPU time")

        elif "LOCALIZED" in state:
            lines.append("• CPU load is concentrated in a small set of active processes")
            if dominant:
                lines.append(f"  └─ {dominant.comm} is the primary consumer")

        else:
            lines.append("• CPU activity is present but not strongly concentrated")

        # --------------------------------------------------
        # 2. Dominant process insight
        # --------------------------------------------------
        if dominant:
            lines.append(f"• Dominant workload: {dominant.comm} ({dominant.cpu:.1f}%)")

        # --------------------------------------------------
        # STAT interpretation (FULL, no shortcuts)
        # --------------------------------------------------

        from utils import extract_unique_stats, describe_stats

        stat_chars = sorted(
            extract_unique_stats(active),
            key=lambda x: ["R", "S", "D", "Z", "T", "N", "+", "C"].index(x)
            if x in ["R", "S", "D", "Z", "T", "N", "+", "C"] else 99
        )

        if stat_chars:
            lines.append(f"• STAT indicates: {', '.join(stat_chars)}")

            from constants import STAT_MEANINGS

            for key in stat_chars:
                desc = STAT_MEANINGS.get(key, "Unknown state")

                # --------------------------------------------------
                # Analyzer-specific richer descriptions (ONE LINE)
                # --------------------------------------------------
                if key == "R":
                    desc = "Running or ready to run — actively competing for CPU time"

                elif key == "S":
                    desc = "Sleeping (waiting for event) — currently idle, awaiting work"

                elif key == "D":
                    desc = "Waiting on I/O — blocked on disk or network operations"

                elif key == "Z":
                    desc = "Zombie process — terminated but not yet reaped by parent"

                elif key == "T":
                    desc = "Stopped — paused or under debugging control"

                elif key == "N":
                    desc = "Low priority (nice) — intentionally deprioritized workload"

                elif key == "+":
                    desc = "Foreground process — interacting directly with the user"

                elif key == "C":
                    desc = "CPU-bound — continuously consuming CPU without waiting"

                lines.append(f"  └─ {key} → {desc}")

        # --------------------------------------------------
        # 4. Load intensity
        # --------------------------------------------------
        if "HEAVY" in state:
            lines.append("• System is under sustained computational pressure")

        elif "MODERATE" in state:
            lines.append("• Workload is noticeable but not saturating the system")

        elif state == "LIGHT":
            lines.append("• System is responsive with light activity")

        elif state == "IDLE":
            lines.append("• System is mostly idle")

        # --------------------------------------------------
        # 5. Conclusion
        # --------------------------------------------------
        if "DISTRIBUTED" in state:
            lines.append("")
            lines.append("Conclusion:")
            lines.append("→ Likely a parallel or multi-process workload")

        elif "LOCALIZED" in state:
            lines.append("")
            lines.append("Conclusion:")
            lines.append("→ Likely a single dominant workload")

        else:
            lines.append("")
            lines.append("Conclusion:")
            lines.append("→ No strong workload pattern detected")

        return lines



