import sys, os

sys.path = [os.path.abspath(".")] + sys.path

import argparse
import time
import json
import tomllib
import subprocess
from datetime import datetime

# Local imports
from constants import RESET, UNDERLINE, BOLD, fg, STAT_MEANINGS
from config import CONFIG_PATH, DEFAULT_TOML
from fetcher import ProcessFetcher
from filters import ProcessFilter, ProcessSorter
from formatter import ProcessFormatter
from cpu_analyzer import CPUAnalyzer
from utils import visible_len, extract_unique_stats, describe_stats




class CustomArgumentParser(argparse.ArgumentParser):
    """
    Custom argument parser that overrides the default exit behavior.

    Purpose:
        Prevent argparse from terminating the program abruptly with sys.exit()
        when encountering errors or help messages.

    Behavior:
        - Prints the error/help message to stderr (if present)
        - Raises SystemExit manually instead of exiting internally

    Why:
        This allows better control over program flow and makes it possible
        to handle argument parsing errors more cleanly, especially in tools
        where you may want to intercept or customize exit behavior.
    """

    def exit(self, status=0, message=None):
        """
        Override of argparse.ArgumentParser.exit().

        Instead of calling sys.exit() directly, this method:
        - Prints the message (if any)
        - Raises SystemExit with the given status

        Args:
            status (int): Exit status code
            message (str, optional): Message to print before exiting
        """
        if message:
            self._print_message(message, sys.stderr)

        raise SystemExit(status)



class CPUVwApp:

    def __init__(self):
        self.args = self._parse_args()

    # -------------------------------------------------------------------------------------
    # Method: _parse_args()
    # -------------------------------------------------------------------------------------
    def _parse_args(self):

        parser = CustomArgumentParser(
            prog="cpuvw",
            description=f"{fg(0x00c900)}BSD CPU inspection Viewer{RESET}",
            formatter_class=argparse.RawTextHelpFormatter,
            epilog=f"{BOLD}{fg(0xff0000)}Please, report bugs to:{RESET} hedningakjetil@gmail.com or "
                   f"at {UNDERLINE}https://bugs.freebsd.org/bugzilla/\n{RESET}"
            f"This tool's website: {fg(0x5287d6)}{UNDERLINE}https://github.com/ferusx/cpuvw{RESET}\n"
            "\n"
        )

        parser.add_argument(
            "-s",
            "--sort",
            choices=["cpu", "mem", "pid"],
            default="cpu",
            help="Sort processes by field (default: cpu)"
        )
        parser.add_argument(
            "--no-header",
            action="store_true",
            help="Show no column headers for the process table"
        )
        parser.add_argument(
            "-a",
            "--all",
            action="store_true",
            help="Show all processes, including 'idle'"
        )
        parser.add_argument(
            "--show-path",
            action="store_true",
            help="Show path of each process"
        )
        parser.add_argument(

            "--color",
            action="store_true",
            help="Show colored output"
        )
        parser.add_argument(
            '-l',
            "--light-color",
            action="store_true",
            help="Show a lightly colored, more comfortable, output"
        )
        parser.add_argument(
            "-u",
            "--user",
            help="Show only processes for specified user"
        )
        parser.add_argument(
            "-p",
            "--pid",
            type=int,
            help="Show only specified process ID"
        )
        parser.add_argument(
            "-f",
            "--filter",
            help="Filter processes by command substring"
        )
        parser.add_argument(
            "-b",
            "--bottom",
            action="store_true",
            help="Reverse sort order (show lowest values first)"
        )
        parser.add_argument(
            "-n",
            "--number",
            type=int,
            default=20,
            help="Limit number of displayed processes (default: 20)"
        )
        parser.add_argument(
            "--banner",
            action="store_true",
            help="Show program banner with today's date"
        )
        parser.add_argument(
            '-r',
            '--raw',
            action="store_true",
            help="Show raw output"
        )
        parser.add_argument(
            '-i',
            "--invert-headers",
            choices=["white", "gray", "blue", "green", "orange", "purple", "teal", "maroon"],
            default=None,
            help="Invert the colors of the column headers"
        )
        parser.add_argument(
            '--high-score',
            action="store_true",
            help="Show highest ever CPU for processes and last process' CPU"
        )
        parser.add_argument(
            '-t',
            '--cpu-threshold',
            type=float,
            help="Threshold for CPU in the table, e.g. 2.0 percent will not show processes \n"
                 "with <2.0 percent usage (Can be configured in cpuvwrc.json)"
        )
        parser.add_argument(
            '-c',
            '--show-low-cpu',
            action="store_true",
            help="Show not-so-meaningful processes. (Can be configured in cpuvwrc.json)"
        )
        parser.add_argument(
            '-m',
            '--allow-mod-local-dist',
            action="store_true",
            help="Enable LOCALIZED/DISTRIBUTED modes for the MODERATE CPU state"
        )
        parser.add_argument(
            '-o',
            '--stat-info',
            action="store_true",
            help="Explain process state (STAT) behavior for active processes"
        )
        parser.add_argument(
            '--analyze',
            action="store_true",
            help="Runs a deeper analysis of the CPU's state and active processes \n"
                 "and reports about it"
        )

        return parser.parse_args()

    # -------------------------------------------------------------------------------------
    # Method: _parse_core_output
    # -------------------------------------------------------------------------------------
    def _parse_core_output(self, output):
        cores = []
        for line in output.strip().splitlines():
            _, val = line.split()
            cores.append(float(val))
        return cores

    # -------------------------------------------------------------------------------------
    # Method: _get_cpu_name
    # -------------------------------------------------------------------------------------
    def _get_cpu_name(self):
        try:
            out = subprocess.check_output(
                ["sysctl", "-n", "hw.model"], text=True
            )
            return out.strip()
        except:
            return "Unknown CPU"

    # -------------------------------------------------------------------------------------
    # Method: show_banner
    # -------------------------------------------------------------------------------------
    def show_banner(self, args):
        use_color = args.color

        # Add the top banner line
        if use_color:
            print(f"{fg(0x808080)}*{RESET}" * 84)
        else:
            print(f"*" * 84)

        # --- DATE AND TIME ---
        if use_color:
            now = datetime.now().astimezone()
            print(
                "                   "  ## 18 characters
                + now.strftime(
                    f"{fg(0x808080)}%a{RESET} "
                    f"{fg(0xbbbbbb)}%b %d{RESET} "
                    f"{fg(0x808080)}%H:%M:%S %Z{RESET} "
                    f"{fg(0xbbbbbb)}%Y{RESET}"
                )
                + f" {fg(0x808080)}—{RESET} {BOLD}{fg(0xffffff)}CPUVw v0.21{RESET}"
            )
        else:
            now = datetime.now().astimezone()
            print(
                "                   "  ## 18 characters
                + now.strftime("%a %b %d %H:%M:%S %Z %Y")
                + f" — CPUVw v0.21"
            )

        # Add the bottom banner line
        if use_color:
            print(f"{fg(0x808080)}*{RESET}" * 84)
        else:
            print(f"*" * 84)

    # -------------------------------------------------------------------------------------
    # Method: run()
    # -------------------------------------------------------------------------------------
    def run(self):

        # Time the command's elapsed time
        start_time = time.time()

        args = self.args

        # Use colors
        use_color = args.color

        # Light color theme
        use_light_color = args.light_color

        # High score
        use_high_schore = args.high_score

        # ------------------------------------------
        # Ensure config directory + file exists
        # ------------------------------------------
        config_dir = os.path.dirname(CONFIG_PATH)
        os.makedirs(config_dir, exist_ok=True)

        if not os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "w") as f:
                    f.write(DEFAULT_TOML)
            except Exception as ex:
                pass  # fail silently but safely


        # Load config (with fallback)
        try:
            with open(CONFIG_PATH, "rb") as f:
                config = tomllib.load(f)
        except Exception:
            config = {}

        # ------------------------------------------
        # FETCH
        # ------------------------------------------
        fetcher = ProcessFetcher()
        processes = fetcher.fetch(args)

        processes = [
            p for p in processes
            if (p.comm or "").lower() != "idle"
        ]

        # ------------------------------------------
        # FILTER
        # ------------------------------------------
        processes = ProcessFilter.apply(processes, args)

        # ------------------------------------------
        # SORT
        # ------------------------------------------
        processes = ProcessSorter.apply(processes, args)

        # ------------------------------------------
        # RAW MODE (bypass full UI)
        # ------------------------------------------
        if args.raw:
            formatter = ProcessFormatter()
            lines = formatter.format(
                processes,
                use_color=False,
                args=args,
                use_light_color=args.light_color,
                invert_headers=args.invert_headers
            )

            for line in lines:
                print(line)

            return

        analyzer = CPUAnalyzer()
        analysis = analyzer.analyze(
            processes,
            args,
            use_color=use_color,
            use_light_color=use_light_color
        )

        # ==========================================
        # ANALYZE MODE (dedicated output)
        # ==========================================
        if args.analyze:

            dominant = analysis["dominant"]
            top = analysis["top"]
            state = analysis["state"]

            # --------------------------------------
            # CPU STATE (Top indicator)
            # --------------------------------------
            if use_color:
                if state == "IDLE":
                    state_col = fg(0x5287d6)
                elif state == "LIGHT":
                    state_col = fg(0x009400)
                elif state in ("MODERATE", "MODERATE_LOCALIZED", "MODERATE_DISTRIBUTED"):
                    state_col = fg(0xecbb00)
                else:
                    state_col = fg(0xff0000)

                print(f"\nCPU STATE → {BOLD}{state_col}{state}{RESET}")

            elif use_light_color:
                if state == "IDLE":
                    state_col = fg(0x5287d6)
                elif state == "LIGHT":
                    state_col = fg(0x009400)
                elif state in ("MODERATE", "MODERATE_LOCALIZED", "MODERATE_DISTRIBUTED"):
                    state_col = fg(0xecbb00)
                else:
                    state_col = fg(0xff0000)

                print(f"\n{fg(0x777777)}CPU STATE → {RESET}{BOLD}{state_col}{state}{RESET}")

            else:
                print(f"\nCPU STATE → {state}")

            print()  # spacing

            # --------------------------------------
            # Build LEFT (Dominant)
            # --------------------------------------
            left_lines = []

            if dominant:
                left_lines.append("Dominant Source:")
                left_lines.append(
                    f"• {dominant.comm} {dominant.cpu:.1f}% {dominant.stat} {dominant.threads}Thr"
                )
                left_lines.append(f"  └─ {analysis['dominant_desc']}")
            else:
                left_lines.append("Dominant Source:")
                left_lines.append("  ---")

            # --------------------------------------
            # Build RIGHT (Top contributors)
            # --------------------------------------
            right_lines = []

            visible = [p for p in top if not dominant or p.pid != dominant.pid]

            if len(visible) == 1:
                right_lines.append("Top contributor:")
            else:
                right_lines.append("Top contributors:")

            dominant_pid = dominant.pid if dominant else None

            for p in top:
                if dominant_pid and p.pid == dominant_pid:
                    continue

                cmd = p.comm[:12].ljust(12)
                pid = str(p.pid).rjust(8)
                stat = p.stat.ljust(4)
                cpu = f"{p.cpu:.0f}%".rjust(4)

                right_lines.append(f"• {cmd}  {pid}    {stat}  {cpu}")

            # --------------------------------------
            # Print side-by-side
            # --------------------------------------
            LEFT_W = 50

            print("Activity Overview:\n")

            rows = max(len(left_lines), len(right_lines))

            for i in range(rows):
                left = left_lines[i] if i < len(left_lines) else ""
                right = right_lines[i] if i < len(right_lines) else ""

                padding = LEFT_W - visible_len(left)
                if padding < 0:
                    padding = 0

                print(f"{left}{' ' * padding}{right}")

            print("System Analysis:\n")

            # --------------------------------------
            # Generate analysis text
            # --------------------------------------
            report_lines = analyzer.generate_analysis(analysis, args)

            for line in report_lines:
                print(line)

            print()
            return

        # --- Load previous run data ---
        config_path = os.path.expanduser("~/.cpuvw.json")

        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                try:
                    history = json.load(f)
                except:
                    history = {}
        else:
            history = {}

        # Important Variables
        last = history.get("last_run", None)
        high = history.get("high_score", None)
        state = analysis["state"]
        message = analysis["message"]
        primary = analysis["dominant"]
        dominant = analysis["dominant"]
        desc = analysis["dominant_desc"]
        top = analysis["top"]

        # ------------------------------------------
        # Threshold resolution (CLI overrides config)
        # ------------------------------------------
        threshold = (
            args.cpu_threshold
            if args.cpu_threshold is not None
            else config.get("cpu_threshold", 1.0)
        )

        show_low_cpu = args.show_low_cpu if hasattr(args, "show_low_cpu") else False

        # -------------------------------------------------------------------------------------
        # PRE-COMPUTE MISC STATS (needed for layout)
        #    - Highset memory in %
        #    - Highest RSS in M
        # -------------------------------------------------------------------------------------
        max_mem = 0.0
        max_rss = 0.0

        for p in processes:
            if p.mem > max_mem:
                max_mem = p.mem
            if p.rss_mb > max_rss:
                max_rss = p.rss_mb

        # -------------------------------------------------------------------------------------
        # SHOW BANNER
        #    - conditional.
        #    - shown with --banner flag.
        # -------------------------------------------------------------------------------------
        if args.banner:
            self.show_banner(args)

        # -------------------------------------------------------------------------------------
        # SHOW HIGHEST SCORES
        #    - conditional.
        #    - shown with -high-score flag
        #    - show last runs highest CPU%
        #    - show highest CPU% ever measured
        # -------------------------------------------------------------------------------------
        # High score was chosen
        if use_high_schore:
            # Print last run's highest CPU usage
            if use_color:
                if last:
                    print(
                        f"\nLast run's highest ranked CPU process: "
                        f"{fg(0x00ffff)}{high['comm']}{RESET} → PID: {fg(0x00ffff)}{last['pid']}{RESET}, user: {fg(0x888888)}{last['user']}{RESET}, "
                        f"CPU load: {fg(0x00ffff)}{last['cpu']:.1f}%{RESET}"
                    )
            elif use_light_color:
                if last:
                    print(
                        f"\n{fg(0xaaaaaa)}Last run's highest ranked CPU process:{RESET} "
                        f"{fg(0x777777)}{high['comm']}{RESET}{fg(0xaaaaaa)} → PID: {RESET}{fg(0xffffff)}{last['pid']}{RESET}, user: {fg(0x777777)}{last['user']}{RESET}, "
                        f"{fg(0xaaaaaa)}CPU load: {RESET}{fg(0xffffff)}{last['cpu']:.1f}%{RESET}"
                    )
            else:
                if last:
                    print(
                        f"\nLast run's highest ranked CPU process: "
                        f"{high['comm']} → PID: {last['pid']}, user: {last['user']}, "
                        f"CPU load: {last['cpu']:.1f}%"
                    )

            # Print all-time highest CPU usage.
            if use_color:
                if high:
                    print(
                        f"Highest ever ranked CPU process: "
                        f"{fg(0x00ffff)}{high['comm']}{RESET}, "
                        f"user: {fg(0x888888)}{high['user']}{RESET}, CPU load: {fg(0x00ffff)}{high['cpu']:.1f}%{RESET}"
                    )
            elif use_light_color:
                if high:
                    print(
                        f"{fg(0xaaaaaa)}Highest ever ranked CPU process:{RESET} "
                        f"{fg(0xffffff)}{high['comm']}{RESET}, "
                        f"{fg(0xaaaaaa)}user: {RESET}{fg(0x777777)}{high['user']}{RESET}{fg(0xaaaaaa)}, CPU load: {RESET}{fg(0xffffff)}{high['cpu']:.1f}%{RESET}"
                    )
            else:
                if high:
                    print(
                        f"Highest ever ranked CPU process: "
                        f"{high['comm']}, "
                        f"user: {high['user']}, CPU load: {high['cpu']:.1f}%"
                    )

        ## Newline
        print()

        # =====================================================================================
        # TWO-COLUMN PANEL (columnal layout)
        #     - Left:
        #         - User Focus
        #         - Misc System Stats
        #     - Right:
        #         - Dominant Source
        #         - Top contributors
        # =====================================================================================

        # -------------------------------------------------------------------------------------
        # USER FOCUS Section
        #    - displays current highest number of threads for user
        #    - displays command run time in seconds with three decimals
        # -------------------------------------------------------------------------------------
        user_focus = []

        if primary:
            if use_color:
                user_focus.append(f"{fg(0x888888)}{primary.user} → {fg(0x00ffff)}{primary.threads}{RESET} thread(s)")
            elif use_light_color:
                user_focus.append(f"{fg(0x777777)}{primary.user}{RESET}{fg(0xaaaaaa)} →{RESET} "
                                f"{fg(0xffffff)}{primary.threads}{RESET}{fg(0xaaaaaa)} thread(s){RESET}")
            else:
                user_focus.append(f"{primary.user} → {primary.threads} thread(s)")

        runtime = time.time() - start_time
        if use_color:
            user_focus.append(f"Run time: {fg(0x00ffff)}{runtime:.3f}{RESET} s")
        elif use_light_color:
            user_focus.append(f"{fg(0xaaaaaa)}Run time: {RESET}{fg(0xffffff)}{runtime:.3f}{RESET}{fg(0xaaaaaa)} s{RESET}")
        else:
            user_focus.append(f"Run time: {runtime:.3f} s")

        # -----------------------------------------
        # Titles
        # -----------------------------------------
        left_title = "User Focus:"
        right_title = "Activity:"  # umbrella title

        # ==========================================
        # Left Side (User Focus + Misc System Stats)
        # ==========================================
        left_lines = []

        # ------------------------------------------
        # "User Focus" section
        # ------------------------------------------
        for entry in user_focus:
            left_lines.append(entry)

        # ------------------------------------------
        # Spacer
        # ------------------------------------------
        left_lines.append("")

        # ------------------------------------------
        # "Misc System Stats" section
        # ------------------------------------------
        if use_light_color:
            left_lines.append(f"{fg(0x777777)}Misc System Stats:{RESET}")
        else:
            left_lines.append(f"Misc System Stats:")

        # ------------------------------------------
        # Color it
        # ------------------------------------------
        if use_color:
            left_lines.append(f"Highest Mem: {fg(0x00ffff)}{max_mem:.1f}%{RESET}")
            left_lines.append(f"Highest RSS: {fg(0x00ffff)}{max_rss:.0f}M{RESET}")

        # ------------------------------------------
        # Light color theme
        # ------------------------------------------
        elif use_light_color:
            left_lines.append(f"{fg(0xaaaaaa)}Highest Mem: {RESET}{fg(0xffffff)}{max_mem:.1f}%{RESET}")
            left_lines.append(f"{fg(0xaaaaaa)}Highest RSS: {RESET}{fg(0xffffff)}{max_rss:.0f}M{RESET}")

        # ------------------------------------------
        # No colors
        # ------------------------------------------
        else:
            left_lines.append(f"Highest Mem: {max_mem:.1f}%")
            left_lines.append(f"Highest RSS: {max_rss:.0f}M")

        # ==========================================
        # Right Side (Dominant + contributors)
        # ==========================================
        right_lines = []

        # ------------------------------------------
        # "Dominant Source" section
        # ------------------------------------------
        if dominant and state != "IDLE":

            # ------------------------------------------
            # Apply color
            # ------------------------------------------
            if use_color:
                if state == "HEAVY_LOCALIZED":
                    right_lines.append(f"{fg(0xa06ba0)}Dominant Source:{RESET}")  # red
                elif state == "HEAVY_DISTRIBUTED":
                    right_lines.append(f"{fg(0xa06ba0)}Dominant Source:{RESET}")  # red
                elif state in ("MODERATE", "MODERATE_LOCALIZED", "MODERATE_DISTRIBUTED"):
                    right_lines.append(f"{fg(0xcdb114)}Dominant Source:{RESET}")  # orange
                elif state == "LIGHT":
                    right_lines.append(f"{fg(0x7aa933)}Dominant Source:{RESET}")  # green
                else:
                    right_lines.append(f"{fg(0x888888)}Dominant Source:{RESET}")  # gray
                right_lines.append(
                    f"• {fg(0x00bf00)}{dominant.comm}{RESET} "
                    f"{fg(0x00ffff)}{dominant.cpu:.1f}%{RESET} "
                    f"{fg(0xffffff)}{dominant.stat}{RESET} "
                    f"{fg(0x888888)}{dominant.threads}Thr{RESET}"
                )
                right_lines.append(f"  └─ {desc}")

            # ------------------------------------------
            # Light color theme
            # ------------------------------------------
            elif use_light_color:
                right_lines.append(f"{fg(0xaaaaaa)}Dominant Source:{RESET}")  # Gray

                right_lines.append(
                    f"• {fg(0x777777)}{dominant.comm}{RESET} "  # Gray
                    f"{fg(0xffffff)}{dominant.cpu:.1f}%{RESET} "  # White
                    f"{fg(0xaaaaaa)}{dominant.stat} "  # Gray
                    f"{fg(0xffffff)}{dominant.threads}{RESET}{fg(0xaaaaaa)}Thr{RESET}"  # Gray
                )
                right_lines.append(f"  └─ {desc}")

            # ------------------------------------------
            # No colors
            # ------------------------------------------
            else:
                right_lines.append("Dominant Source:")
                right_lines.append(
                    f"• {dominant.comm} "
                    f"{dominant.cpu:.1f}% "
                    f"{dominant.stat} "
                    f"{dominant.threads}Thr"
                )
                right_lines.append(f"  └─ {desc}")

            right_lines.append("")  # spacer

        # ------------------------------------------
        # "Top Contributors" section
        # ------------------------------------------
        if state == "IDLE":
            right_lines.append("Top activity:")
            right_lines.append("     ---")

        elif state != "IDLE":
            if use_light_color:
                right_lines.append(f"{fg(0x777777)}Top contributors:{RESET}")
            else:
                right_lines.append("Top contributors:")

            # Remove dominant from contributors
            dominant_pid = dominant.pid if dominant else None

            # ------------------------------------------
            # Separate contributor list (NOT table-limited)
            # ------------------------------------------
            all_contributors = analysis["top"]  # original full list

            # Contributor limit (decoupled)
            contributors_limit = max(len(processes) + 2, 5)

            top_contributors = all_contributors[:contributors_limit]

            for p in top_contributors:
                if p.pid == dominant_pid:
                    continue

                # ------------------------------------------
                # Prepare fields (aligned)
                # ------------------------------------------
                cmd = p.comm[:12].ljust(12)
                pid = str(p.pid).rjust(6)
                stat = p.stat.ljust(4)
                cpu = f"{p.cpu:.0f}%".rjust(4)

                # ------------------------------------------
                # Color it (full color theme)
                # ------------------------------------------
                if use_color:
                    right_lines.append(
                        f"• "
                        f"{fg(0x00bf00)}{cmd}{RESET} "
                        f"{fg(0x00ffff)}{pid}{RESET} "
                        f"{fg(0xffffff)}{stat}{RESET} "
                        f"{fg(0xffaa00)}{cpu}{RESET}"
                    )

                # ------------------------------------------
                # Light color theme
                # ------------------------------------------
                elif use_light_color:
                    right_lines.append(
                        f"• "
                        f"{fg(0x777777)}{cmd}{RESET} "
                        f"{fg(0xffffff)}{pid}{RESET} "
                        f"{fg(0x777777)}{stat}{RESET} "
                        f"{fg(0xffffff)}{cpu}{RESET}"
                    )

                # ------------------------------------------
                # No color
                # ------------------------------------------
                else:
                    right_lines.append(
                        f"• {cmd} {pid} {stat} {cpu}"
                    )

        # ------------------------------------------
        # Print left section + right section
        # - left_title → "User Focus:"
        # - right_tile → "Activity:"
        # ------------------------------------------
        LEFT_W = 30

        left_part = left_title.ljust(LEFT_W)
        right_part = right_title

        # ------------------------------------------
        # Light color theme
        # ------------------------------------------
        if use_light_color:
            print(f"{fg(0x777777)}{left_part}{right_part}{RESET}")
        else:
            print(f"{left_part}{right_part}")

        # -------------------------
        # Unified row
        # -------------------------
        rows = max(len(left_lines), len(right_lines))

        for i in range(rows):
            left = left_lines[i] if i < len(left_lines) else ""
            right = right_lines[i] if i < len(right_lines) else ""

            padding = 30 - visible_len(left)
            if padding < 0:
                padding = 0

            print(f"{left}{' ' * padding}{right}")

        print("")

        # ------------------------------------------
        # "CPU STATE → STATE" section
        # ------------------------------------------

        # ------------------------------------------
        # Color it
        # ------------------------------------------
        if use_color:
            if state == "IDLE":
                state_col = fg(0x5287d6)  # gray
            elif state == "LIGHT":
                state_col = fg(0x009400)  # green
            elif state in ("MODERATE", "MODERATE_LOCALIZED", "MODERATE_DISTRIBUTED"):
                state_col = fg(0xecbb00)  # yellow
            else:  # HEAVY_*
                state_col = fg(0xff0000)  # red

            print(f"CPU STATE → {BOLD}{state_col}{state}{RESET}")

        # ------------------------------------------
        # Light color theme
        # ------------------------------------------
        elif use_light_color:
            if state == "IDLE":
                state_col = fg(0x5287d6)  # Bright blue
            elif state == "LIGHT":
                state_col = fg(0x009400)  # green
            elif state in ("MODERATE", "MODERATE_LOCALIZED", "MODERATE_DISTRIBUTED"):
                state_col = fg(0xecbb00)  # orange
            else:  # HEAVY_*
                state_col = fg(0xff0000)  # red

            print(f"{fg(0x777777)}CPU STATE → {RESET}{BOLD}{state_col}{state}{RESET}")

        # ------------------------------------------
        # No color
        # ------------------------------------------
        else:
            print(f"CPU STATE → {state}")

        print()  # Newline

        # ------------------------------------------
        # "Currently Reporting:" section
        #
        #  STATES are:
        #    - IDLE: little or no activity
        #    - LIGHT: Light activity
        #    - MODERATE: Moderate activity
        #    - HEAVY LOCALIZED: Heavy load on one
        #      process
        #    - HEAVY DISTRIBUTED: Heavy load spread
        #      out across multiple processes
        # ------------------------------------------

        # ------------------------------------------
        # Color it
        # ------------------------------------------
        if use_color:
            if state == "IDLE":
                print(f"{fg(0x5287d6)}Currently Reporting:{RESET}") # Bright blue
            elif state == "LIGHT":
                print(f"{fg(0x009400)}Currently Reporting:{RESET}") # Green
            elif state in ("MODERATE", "MODERATE_LOCALIZED", "MODERATE_DISTRIBUTED"):
                print(f"{fg(0xecbb00)}Currently Reporting:{RESET}") # Orange-yellowish
            elif state == "HEAVY_LOCALIZED":
                print(f"{fg(0xff0000)}Currently Reporting:{RESET}") # Red
            elif state == "HEAVY_DISTRIBUTED":
                print(f"{fg(0xff0000)}Currently Reporting:{RESET}") # Red

        # ------------------------------------------
        # light color theme
        # ------------------------------------------
        elif use_light_color:
            print(f"{fg(0x777777)}Currently Reporting:{RESET}") # Gray

        # ------------------------------------------
        # No color
        # ------------------------------------------
        else:
            print("Currently Reporting:")

        print(message)  # Newline

        # ------------------------------------------
        # Dynamic scaling (state-aware, threshold-driven)
        # ------------------------------------------

        # Split meaningful vs low CPU
        meaningful = [p for p in processes if p.cpu >= threshold]
        low_cpu = [p for p in processes if p.cpu < threshold]

        count = len(meaningful)

        # Compute dynamic limit
        caps = config.get("caps", {})
        bias = config.get("bias", {})

        cap = caps.get(state, 5)
        bias_val = bias.get(state, 0)

        if count == 0:
            limit = 0
        else:
            limit = min(count + bias_val, cap)

        # Assemble final list
        if show_low_cpu:
            combined = meaningful + low_cpu
        else:
            combined = meaningful

        # ------------------------------------------
        # CLI override: --number (table only)
        # ------------------------------------------
        if args.number is not None:
            limit = args.number

        processes = combined[:limit]

        # ------------------------------------------
        # Call formatter
        # ------------------------------------------
        formatter = ProcessFormatter()

        # ----------------------------------------------------------
        # About the arguments in the "lines" statement:
        #
        #     - processes → processes;
        #     - args.color → use_color;
        #     - args.light_color → use_light_color;
        #     - args.invert_headers → invert_headers;
        #     - args → args
        # ----------------------------------------------------------
        lines = formatter.format(processes, args.color, args.light_color, args.invert_headers, args)

        # ------------------------------------------
        # Print the table
        # ------------------------------------------
        try:
            for line in lines:
                print(line)
        except BrokenPipeError:
            sys.exit(0)

        print(" ")  # Newline

        # ------------------------------------------
        # STAT INFO SECTION
        # ------------------------------------------
        if args.stat_info:
            right_lines = []
            right_lines.append("")  # spacer

            if use_light_color:
                right_lines.append(f"{fg(0xaaaaaa)}STAT Analysis:{RESET}")
            else:
                right_lines.append("STAT Analysis:")

            # Active processes (reuse same threshold logic later if needed)
            active = [p for p in processes if p.cpu >= config.get("cpu_threshold", 1.0)]

            right_lines.append(f"• {len(active)} active processes detected")

            # Collect unique stat flags
            stat_chars = sorted(
                extract_unique_stats(active),
                key=lambda x: ["R", "S", "D", "N", "C", "+"].index(x) if x in ["R", "S", "D", "N", "C", "+"] else 99
            )

            if stat_chars:
                right_lines.append(f"• Observed states: {', '.join(stat_chars)}")

                right_lines.append("")  # spacer

                # Explain each
                explanations = describe_stats(stat_chars)
                for line in explanations:
                    right_lines.append(line)

            else:
                right_lines.append("• No significant state activity detected")

            for line in right_lines:
                print(line)

        else:
            ## ------------------------------------------
            ## Show when CPUVw was executed at bottom
            ## ------------------------------------------
            # ------------------------------------------
            # color the by-line
            # ------------------------------------------
            if use_color:
                now = datetime.now().astimezone()
                print(f"{BOLD}CPUVw{RESET} was executed at: "
                    + f"{fg(0x5287d6) + now.strftime("%a %b %d %H:%M:%S %Z %Y")}"
                )
            # ------------------------------------------
            # use light color theme
            # ------------------------------------------
            elif use_light_color:
                now = datetime.now().astimezone()
                print(f"{BOLD}{fg(0xffffff)}CPUVw{RESET}{fg(0xaaaaaa)} was executed at: {RESET}"
                    + f"{fg(+0xaaaaaa) + now.strftime("%a %b %d %H:%M:%S %Z %Y")}"
                )
            # ------------------------------------------
            # Use no colors
            # ------------------------------------------
            else:
                now = datetime.now().astimezone()
                print(f"{BOLD}CPUVw{RESET} was executed at: "
                      + now.strftime("%a %b %d %H:%M:%S %Z %Y")
                      )

        print(" ")  # Newline

        # ------------------------------------------
        # High Score: Save current run to JSON file
        # ------------------------------------------
        top_proc = analysis["dominant"]

        if top_proc:
            # ------------------------------------------
            # Update last run
            # ------------------------------------------
            history["last_run"] = {
                "pid": top_proc.pid,
                "user": top_proc.user,
                "cpu": top_proc.cpu,
                "comm": top_proc.comm
            }

            # ------------------------------------------
            # Update high score
            # ------------------------------------------
            if not high or top_proc.cpu > high.get("cpu", 0):
                history["high_score"] = {
                    "pid": top_proc.pid,
                    "user": top_proc.user,
                    "cpu": top_proc.cpu,
                    "comm": top_proc.comm
                }

            # ------------------------------------------
            # Write to the file
            # ------------------------------------------
            with open(config_path, "w") as f:
                json.dump(history, f)

# ------------------------------------------
# Main entry point of the program
# ------------------------------------------
if __name__ == "__main__":
    app = CPUVwApp()
    app.run()

