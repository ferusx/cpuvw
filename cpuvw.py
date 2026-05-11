# cpuvw.py

# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 Markus Johnsson

import sys, os
import argparse
import time
import json
import select
import subprocess
import pydoc
from datetime import datetime

# Local imports
from constants import RESET, UNDERLINE, BOLD, fg
from config import load_config, save_config_copy
from fetcher import ProcessFetcher
from tree_formatter import ProcessTreeFormatter
from filters import ProcessFilter, ProcessSorter
from formatter import ProcessFormatter
from telemetry import show_physical_cores_live, show_physical_cores_fast, show_logical_cpu_fast, show_logical_cpu_live
from cpu_analyzer import CPUAnalyzer
from utils import (
    visible_len,
    extract_unique_stats,
    describe_stats,
    expand_with_parents,
    print_summary,
)

# ****************************************************************************
# Class: CustomArgumentParser
# ****************************************************************************
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

    # -------------------------------------------------------------------------------------
    # Method: exit
    # -------------------------------------------------------------------------------------
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

    def error(self, message):
        # Print ONLY the error message (no usage spam)
        self._print_message(f"{self.prog}: error: {message}\n", sys.stderr)
        raise SystemExit(2)

# ****************************************************************************
# Class: CPUVwApp
# ****************************************************************************
class CPUVwApp:

    def __init__(self):
        self.args = self._parse_args()


        # Validate flags and argument combinations
        self._validate_flags()


    # -------------------------------------------------------------------------------------
    # Method: _parse_args()
    # -------------------------------------------------------------------------------------
    # noinspection PyMethodMayBeStatic
    def _parse_args(self):
        parser = CustomArgumentParser(
            prog="CPUVw",
            description=f"{BOLD}BSD CPU inspection Viewer{RESET}",
            formatter_class=argparse.RawTextHelpFormatter,
            epilog=f"{BOLD}NOTE:{RESET} All the above options that are marked with the word {fg(0x5287d6)}[configurable]{RESET} can be configured\n"
                   f"in CPUVw's config file. See the man page's FILES and CONFIGURATION sections for more\n"
                   f"information on the subject.\n\n"
                   f"Please, report bugs to: hedningakjetil@gmail.com or "
                   f"at {UNDERLINE}https://bugs.freebsd.org/bugzilla/\n{RESET}"
            f"This tool's website: {UNDERLINE}https://github.com/ferusx/cpuvw{RESET}\n"
        )


        # This inline function sets a min/max limit for the --threshold flags argument.
        # The allowed interval is 30.0 - 100.0. Error will be printed if not respected.
        def threshold_type(value):
            ivalue = int(value)
            if ivalue < 30 or ivalue > 100:
                raise argparse.ArgumentTypeError(
                    "Threshold must be between 30 and 100"
                )
            return ivalue

        parser.add_argument(
            "-a",
            "--all",
            action="store_true",
            help="Show all processes, including 'idle'"
        )
        parser.add_argument(
            "-b",
            "--bottom",
            action="store_true",
            default=None,
            help="Reverse sort order (show lowest values first). [configurable]"
        )
        parser.add_argument(
            '-c',
            "--color",
            action="store_true",
            help="Show colored output. [configurable]"
        )
        parser.add_argument(
            '-d',
            '--tree-depth',
            type=int,
            default=5,
            help="Maximum depth of process tree. [configurable]"
        )
        parser.add_argument(
            '-f', '--filter',
            nargs=2,
            action="append",
            metavar=("FIELD", "VALUE"),
            help="Filter by field (p=pid, u=user, s=stat, c=cpu, t=threads, m=command)"
        )
        parser.add_argument(
            '-F',
            '--core-update-frequency',
            nargs='+',
            type=float,
            metavar=('DURATION', 'INTERVAL'),
            default=None,
            help="Telemetry sampling duration and optional sampling interval\n"
                 "for logical and physical CPU telemetry modes.\n"
                 "If only one value is provided, it is used as the duration.\n"
                 "[configurable]"
        )
        parser.add_argument(
            '-g',
            "--glyph-style",
            choices=["1", "2", "3"],
            default="1",
            help="Tree glyph style: 1=classic, 2=ascii, 3=fancy. [configurable]"
        )
        parser.add_argument(
            '-H',
            '--high-score',
            action="store_true",
            help="Show highest ever CPU usage for processes and last highest\n"
                 "CPU usage. [configurable]"
        )
        parser.add_argument(
            '-I',
            '--stat-info',
            action="store_true",
            help="Explain process state (STAT) behavior for active processes.\n"
                 "[configurable]"
        )
        parser.add_argument(
            '-l',
            '--show-logical-cpu',
            nargs='?',
            const='auto',  # ← used when flag is present without value
            default=None,  # ← flag not used at all
            choices=['fast', 'avg', 'auto'],
            help="Show per-logical CPU usage (fast or avg). [configurable]"
        )
        parser.add_argument(
            '-L',
            '--show-low-cpu',
            action="store_true",
            help="Show not-so-meaningful processes. [configurable]"
        )
        parser.add_argument(
            "-n",
            "--number",
            type=int,
            default=None,
            help="Limit number of displayed processes (no limit by default)"
        )
        parser.add_argument(
            '--hide-analysis',
            action="store_true",
            default=None,
            help="Hide the deeper CPU insight sections above the process \n"
                 "table. [configurable]"
        )
        parser.add_argument(
            "--hide-header",
            action="store_true",
            help="Show no column headers for the process table. [configurable]"
        )
        parser.add_argument(
            '--hide-table',
            action="store_true",
            default=None,
            help="Don't show process table. [configurable]"
        )
        parser.add_argument(
            '-p',
            '--show-physical-core',
            nargs='?',
            const='auto',  # ← used when flag is present without value
            default=None,  # ← flag not used at all
            choices=['fast', 'avg', 'auto'],
            help="Show per-core CPU usage (fast or avg). [configurable]"
        )
        parser.add_argument(
            '-P',
            "--show-path",
            action="store_true",
            help="Show path of each process. [configurable]"
        )
        parser.add_argument(
            "--prune",
            type=int,
            metavar="LEVEL",
            help="Prune low-value branches (higher = more aggressive, tree \n"
                 "mode only). [configurable]"
        )
        parser.add_argument(
            '-r',
            '--raw',
            action="store_true",
            help="Show raw output"
        )
        parser.add_argument(
            '-R',
            '--pager',
            action="store_true",
            help="Pause the output when it is larger than the terminal size. [configurable] "
        )
        parser.add_argument(
            "-s",
            "--sort",
            choices=["pid", "user", "stat", "cpu", "thr", "cmd"],
            default="cpu",
            help="Sort processes by field (default: cpu). [configurable]"
        )
        parser.add_argument(
            '-S',
            "--save-config",
            action="store_true",
            help="Generate a fresh config file (safe copy)"
        )
        parser.add_argument(
            '-T',
            '--cpu-threshold',
            dest='cpu_state_threshold',
            type=float,
            help="CPU percentage threshold for HEAVY state (30-100). [configurable]"
        )
        parser.add_argument(
            '-t',
            '--threshold',
            dest='table_cpu_threshold',
            type=float,
            help="Minimum CPU percentage required to display a process in the table.\n"
                 "[configurable]"
        )
        parser.add_argument(
            '--tree',
            action="store_true",
            help="Show tree of all processes and their children. [configurable]"
        )
        parser.add_argument(
            '-y',
            '--analyze',
            nargs="?",
            const="standard",
            choices=["standard", "more", "deep"],
            metavar="MODE",
            help="Runs a deeper analysis of the CPU's state and active processes \n"
                 "and reports about it"
        )
        parser.add_argument(
            '-w',
            '--line-wrap',
            action="store_true",
            help="Wrap long lines in table to multiple lines. (i.e. when using \n"
                 "--show-path). [configurable]"
        )
        parser.add_argument(
            '-W',
            '--with-parents',
            action='store_true',
            default=None,
            help='Include parent processes in tree view [configurable]'
        )



        return parser.parse_args()

    # -------------------------------------------------------------------------------------
    # Method: _validate_flags
    # -------------------------------------------------------------------------------------
    def _validate_flags(self):
        args = self.args

        # ------------------------------------------
        # --filter (composite filter validation)
        # ------------------------------------------
        FIELD_MAP = {"pid", "user", "stat", "cpu", "thr", "cmd"}

        if args.filter:

            for field, value in args.filter:

                # Validate field
                if field not in FIELD_MAP:
                    raise SystemExit(
                        f"Invalid filter field: '{field}'. "
                        f"Valid fields are: pid, user, stat, cpu, thr, cmd"
                    )

                # Validate value type
                if field == "pid":
                    if not value.isdigit():
                        raise SystemExit("Filter 'pid' requires an integer value")

                elif field == "cpu":
                    try:
                        float(value)
                    except ValueError:
                        raise SystemExit("Filter 'cpu' requires a numeric value")

                elif field == "thr":
                    if not value.isdigit():
                        raise SystemExit("Filter 'thr' requires an integer value")

        # ------------------------------------------
        # ANALYZE
        # ------------------------------------------
        if args.analyze:
            if args.tree:
                raise SystemExit("--tree cannot be used with --analyze")

            if args.raw:
                raise SystemExit("--raw cannot be used with --analyze")

            if args.show_logical_cpu:
                raise SystemExit("--show-logical-cpu cannot be used with --analyze")

            if args.stat_info:
                raise SystemExit("--stat-info cannot be used with --analyze")

            if args.hide_table:
                raise SystemExit("--hide-table cannot be used with --analyze")

            if args.number:
                raise SystemExit("--number cannot be used with --analyze")

            if args.high_score:
                raise SystemExit("--high-score cannot be used with --analyze")

            if args.show_path:
                raise SystemExit("--show-path cannot be used with --analyze")

            if args.cpu_state_threshold:
                raise SystemExit("--cpu-threshold cannot be used with --analyze")

            if args.table_cpu_threshold:
                raise SystemExit("--threshold cannot be used with --analyze")

            if args.line_wrap:
                raise SystemExit("--line-wrap cannot be used with --analyze")

            if args.bottom:
                raise SystemExit("--bottom cannot be used with --analyze")

            if args.filter:
                raise SystemExit("--filter cannot be used with --analyze")

            if args.core_update_frequency:
                raise SystemExit("--core-update-frequency cannot be used with --analyze")

            if args.show_low_cpu:
                raise SystemExit("--show-low-cpu cannot be used with --analyze")

            if args.hide_analysis:
                raise SystemExit("--hide-analysis cannot be used with --analyze")

            if args.hide_table:
                raise SystemExit("--hide-table cannot be used with --analyze")

            if args.hide_header:
                raise SystemExit("--hide-header cannot be used with --analyze")

        # ------------------------------------------
        # RAW MODE CONFLICTS
        # ------------------------------------------
        if args.raw:
            if args.tree:
                raise SystemExit("--tree cannot be used with --raw")

            if args.analyze:
                raise SystemExit("--analyze cannot be used with --raw")

        # ------------------------------------------
        # LOGICAL CPU MODE (exclusive)
        # ------------------------------------------
        if args.show_logical_cpu:
            forbidden = [
                args.tree,
                args.analyze,
                args.raw,
                args.stat_info,
            ]
            if any(forbidden):
                raise SystemExit("--show-logical-cpu cannot be combined with other modes")

        # ------------------------------------------
        # PHYSICAL CORE MODE (exclusive)
        # ------------------------------------------
        if args.show_physical_core:
            forbidden = [
                args.tree,
                args.analyze,
                args.raw,
                args.stat_info,
            ]
            if any(forbidden):
                raise SystemExit("--show-physical-core cannot be combined with other modes")


        # ------------------------------------------
        # CORE UPDATE FREQUENCY (blocker)
        #
        # TO prohibit users from do nonsense input
        # like -F 0.1 2.0.
        # ------------------------------------------
        if args.core_update_frequency:

            values = args.core_update_frequency

            if len(values) > 2:
                raise SystemExit(
                    "--core-update-frequency accepts at most two values"
                )

            duration = values[0]

            if duration <= 0:
                raise SystemExit(
                    "Telemetry duration must be greater than 0"
                )

            if len(values) == 2:

                interval = values[1]

                if interval <= 0:
                    raise SystemExit(
                        "Telemetry interval must be greater than 0"
                    )

                if interval > duration:
                    raise SystemExit(
                        "Telemetry interval cannot exceed duration"
                    )

        # ------------------------------------------
        # NUMERIC VALIDATION
        # ------------------------------------------
        if args.number is not None and args.number < 1:
            raise SystemExit("--number must be >= 1")

        if args.tree_depth is not None and args.tree_depth < 1:
            raise SystemExit("--tree-depth must be >= 1")

        if args.prune is not None and args.prune not in (0, 1, 2, 3):
            raise SystemExit("--prune must be 0, 1, 2, or 3")

        if args.table_cpu_threshold is not None and args.table_cpu_threshold < 0:
            raise SystemExit("--threshold must be >= 0")

        if args.cpu_state_threshold is not None:
            if not (30 <= args.cpu_state_threshold <= 100):
                raise SystemExit("--cpu-threshold must be between 30 and 100")

        # ------------------------------------------
        # LOGICAL CONSISTENCY
        # ------------------------------------------
        if args.line_wrap and not args.show_path:
            raise SystemExit("--line-wrap requires --show-path")

        if args.core_update_frequency and (
                not args.show_logical_cpu and
                not args.show_physical_core
        ):
            raise SystemExit("--core-update-frequency requires --show-logical-cpu")

        if args.hide_analysis and args.hide_table:
            raise SystemExit("You can only hide one section at a time")

        if args.color and args.raw:
            raise SystemExit("--raw cannot be used with --color")

        # ------------------------------------------
        # TREE - LOGICAL CONSISTENCY
        # ------------------------------------------
        if args.tree:
            if args.hide_header:
                raise SystemExit("--hide-header has no effect in --tree mode")

            if args.table_cpu_threshold:
                raise SystemExit("--threshold has no effect in --tree mode")

            if args.cpu_state_threshold:
                raise SystemExit("--cpu-threshold has no effect in --tree mode")

            if args.show_low_cpu:
                raise SystemExit("--show-low-cpu has no effect in --tree mode")

        # ------------------------------------------
        # TREE MODE VALIDATION
        # ------------------------------------------
        if not args.tree:
            if args.prune is not None:
                raise SystemExit("--prune requires --tree")

            if args.with_parents:
                raise SystemExit("--with-parents requires --tree")

            if args.glyph_style != "1":
                raise SystemExit("--glyph-style requires --tree")

    # -------------------------------------------------------------------------------------
    # Method: _key_pressed
    # -------------------------------------------------------------------------------------
    # noinspection PyMethodMayBeStatic
    def _key_pressed(self):
        dr, _, _ = select.select([sys.stdin], [], [], 0)
        if dr:
            return sys.stdin.read(1)
        return None

    # -------------------------------------------------------------------------------------
    # Method: _parse_core_output
    # -------------------------------------------------------------------------------------
    # noinspection PyMethodMayBeStatic
    def _parse_core_output(self, output):
        cores = []
        for line in output.strip().splitlines():
            _, val = line.split()
            cores.append(float(val))
        return cores

    # -------------------------------------------------------------------------------------
    # Method: _get_cpu_name
    # -------------------------------------------------------------------------------------
    # noinspection PyMethodMayBeStatic
    def _get_cpu_name(self):
        try:
            out = subprocess.check_output(
                ["sysctl", "-n", "hw.model"], text=True
            )
            return out.strip()
        except:
            return "Unknown CPU"


    # -------------------------------------------------------------------------------------
    # Method: run()
    # -------------------------------------------------------------------------------------
    def run(self):

        # -------------------------------------------------------------------------------------
        # Map: Map for flag --filter, -F
        # -------------------------------------------------------------------------------------
        FIELD_MAP = {
            "pid": "pid",
            "user": "user",
            "stat": "stat",
            "cpu": "cpu",
            "thr": "threads",
            "cmd": "command",
        }

        # Time the command's elapsed time
        start_time = time.time()

        args = self.args

        import os
        import shlex
        import sys

        if args.pager and not os.environ.get("CPUVW_PAGER_ACTIVE"):
            env = os.environ.copy()
            env["CPUVW_PAGER_ACTIVE"] = "1"

            filtered_args = [
                shlex.quote(arg)
                for arg in sys.argv[1:]
                if arg != "--pager"
            ]

            cmd = (
                f"{shlex.quote(sys.executable)} "
                f"{shlex.quote(sys.argv[0])} "
                f"{' '.join(filtered_args)} "
                f"| less -R"
            )

            os.execvpe(
                "sh",
                ["sh", "-c", cmd],
                env
            )





        # High score
        use_high_schore = args.high_score


        # ------------------------------------------
        # Handle utility flags EARLY
        # ------------------------------------------
        if args.save_config:
            path = save_config_copy()
            print(f"Config template written to: {path}")
            print("Review and replace your current config if desired.")
            return

        # ------------------------------------------
        # Load config (single source of truth)
        # ------------------------------------------
        config = load_config()

        # ------------------------------------------
        # CONFIG: [output] SECTION
        # ------------------------------------------
        use_color = args.color or config.get("output", {}).get("use_color", False)

        show_low_cpu = (
            args.show_low_cpu
            if args.show_low_cpu
            else config.get("output", {}).get("show_low_cpu", False)
        )

        if not args.hide_header:
            args.hide_header = not config.get("output", {}).get("show_header", True)

        if not args.stat_info:
            args.stat_info = config.get("output", {}).get("show_stat_info", False)

        if args.number is None:
            cfg_limit = config.get("output", {}).get("limit", 0)
            if cfg_limit > 0:
                args.number = cfg_limit

        if args.hide_analysis is None:
            args.hide_analysis = config.get("output", {}).get("hide_analysis", False)

        if args.hide_table is None:
            args.hide_table = config.get("output", {}).get("no_table", False)

        # ------------------------------------------
        # CONFIG [table] SECTION
        # ------------------------------------------
        table_cfg = config.get("table", {})

        # show_path
        if not args.show_path:
            args.show_path = table_cfg.get("show_path", False)

        # wrap_lines
        if not args.line_wrap:
            args.line_wrap = table_cfg.get("wrap_lines", False)

        # default_sort
        if args.sort == "cpu":  # only override if user didn't explicitly choose
            args.sort = table_cfg.get("default_sort", "cpu")

        if args.bottom is None:
            args.bottom = table_cfg.get("bottom_sort", False)

        # Tree view
        if not args.tree:
            args.tree = table_cfg.get("show_tree_view", False)

        # Tree parents (CONFIG → ARGS)
        if not args.with_parents:
            args.with_parents = table_cfg.get("with_parents", False)

        # ------------------------------------------
        # CONFIG [cores] SECTION
        # ------------------------------------------
        cores_cfg = config.get("cores", {})

        if not hasattr(args, "logical_interval"):
            args.logical_interval = cores_cfg.get(
                "logical_interval",
                0.3
            )

        if not hasattr(args, "physical_interval"):
            args.physical_interval = cores_cfg.get(
                "physical_interval",
                0.3
            )

        if not hasattr(args, "logical_duration"):
            args.logical_duration = cores_cfg.get(
                "logical_duration",
                2
            )

        if not hasattr(args, "physical_duration"):
            args.physical_duration = cores_cfg.get(
                "physical_duration",
                2
            )

        # ------------------------------------------
        # ARGS.SHOW_LOGICAL_CPU
        # ------------------------------------------

        if args.show_logical_cpu:

            mode = args.show_logical_cpu

            if mode == "auto":

                if cores_cfg.get("logical_avg", False):
                    mode = "avg"
                else:
                    mode = "fast"

            if mode == "fast":
                show_logical_cpu_fast(args)

            elif mode == "avg":
                show_logical_cpu_live(args)

            return

        # ------------------------------------------
        # ARGS.SHOW_PHYSICAL_CORE
        # ------------------------------------------
        if args.show_physical_core:

            mode = args.show_physical_core

            if mode == "auto":

                if cores_cfg.get("physical_avg", False):
                    mode = "avg"
                else:
                    mode = "fast"

            if mode == "fast":
                show_physical_cores_fast(args)

            elif mode == "avg":
                show_physical_cores_live(args)

            return

        args.cpu_state_threshold = (
            args.cpu_state_threshold
            if args.cpu_state_threshold is not None
            else config.get("cpu", {}).get("cpu_threshold", 70)
        )

        args.moderate_threshold = args.cpu_state_threshold - 30
        args.light_threshold = max(0, args.moderate_threshold - 30)

        # ------------------------------------------
        # FETCH
        # ------------------------------------------
        fetcher = ProcessFetcher()
        processes = fetcher.fetch(args)

        # ------------------------------------------
        # FILTER
        # ------------------------------------------
        processes = ProcessFilter.apply(processes, args)

        if not processes:
            print("No processes matched your filter criteria.")
            return

        # ------------------------------------------
        # SORT
        # ------------------------------------------
        processes = ProcessSorter.apply(processes, args)

        all_processes = ProcessFetcher().fetch(args)
        filtered_processes = ProcessFilter().apply(all_processes, args)

        visible_pids = {p.pid for p in filtered_processes}


        def apply_filters(processes, filters):
            if not filters:
                return processes

            result = processes

            for field_key, value in filters:
                field = FIELD_MAP.get(field_key)

                if not field:
                    raise SystemExit(f"Invalid filter field: '{field}'")

                if field == "pid":
                    result = [p for p in result if str(p.pid) == value]

                elif field == "user":
                    result = [p for p in result if p.user == value]

                elif field == "stat":
                    result = [p for p in result if p.stat == value]

                elif field == "cpu":
                    try:
                        threshold = float(value)
                        result = [p for p in result if p.cpu >= threshold]
                    except ValueError:
                        pass

                elif field == "threads":
                    try:
                        threshold = int(value)
                        result = [p for p in result if getattr(p, "threads", 0) >= threshold]
                    except ValueError:
                        pass

                elif field == "command":
                    result = [p for p in result if value.lower() in p.command.lower()]

            return result

        processes = apply_filters(processes, args.filter)

        # ------------------------------------------
        # TREE MODE (EARLY EXIT — BEFORE ANALYSIS)
        # ------------------------------------------
        if args.tree:

            fetcher = ProcessFetcher()
            all_processes = fetcher.fetch(None)

            # ------------------------------------------
            # Step 1: base list
            # ------------------------------------------
            processes = list(all_processes)

            # ------------------------------------------
            # MAP -f filters into legacy args.*
            # ------------------------------------------
            if getattr(args, "filter", None):
                for field, value in args.filter:

                    if field == "pid":
                        args.filter_pid = int(value)

                    elif field == "user":
                        args.filter_user = value

                    elif field == "cmd":
                        args.filter_command = value

                    elif field == "stat":
                        args.filter_stat = value

                    elif field == "cpu":
                        args.filter_cpu = float(value)

            if not args.all:
                processes = [
                    p for p in processes
                    if not (p.pid == 11 and "idle" in (p.command or "").lower())
                ]

            # ------------------------------------------
            # Step 2: APPLY FILTER (this is the truth)
            # ------------------------------------------
            filtered_processes = ProcessFilter.apply(processes, args)

            # ------------------------------------------
            # Step 3: build visible_pids from filtered
            # ------------------------------------------
            visible_pids = {p.pid for p in filtered_processes}

            # ------------------------------------------
            # Step 4: expand parents ONLY for visibility
            # ------------------------------------------
            if args.with_parents:
                expanded_pids = expand_with_parents(filtered_processes, all_processes)
                visible_pids = set(expanded_pids)

            # ------------------------------------------
            # Step 5: pass filtered list + visible_pids
            # ------------------------------------------
            formatter = ProcessTreeFormatter()
            tree_source = all_processes if args.with_parents else filtered_processes

            lines, node_count = formatter.format(
                filtered_processes,
                tree_source,
                args,
                use_color,
                visible_pids=visible_pids
            )

            # ------------------------------------------
            # Step 6: limit output
            # ------------------------------------------
            table_cfg = config.get("table", {})

            if args.number is not None:
                limit = args.number
            else:
                limit = table_cfg.get("tree_limit", 20)

            lines = lines[:limit]

            for line in lines:
                print(line)

            print()
            print_summary(len(lines), use_color)
            return

        # ------------------------------------------
        # GLOBAL IDLE FILTER (applies to all flows)
        # ------------------------------------------
        if not args.all:
            processes = [
                p for p in processes
                if "idle" not in (p.command or "").lower()
            ]


        # ------------------------------------------
        # RAW MODE (bypass full UI)
        # ------------------------------------------
        if args.raw:
            formatter = ProcessFormatter()

            # Force formatter to ONLY use provided processes
            lines = formatter.format(
                processes[:args.number] if args.number is not None else processes,
                use_color=False,
                args=args,
            )

            for line in lines:
                print(line.rstrip())

            return

        # --------------------------------------------------
        # Resolve CPU STATE threshold (CLI > config)
        # --------------------------------------------------
        analyzer = CPUAnalyzer()
        analysis = analyzer.analyze(
            processes,
            args,
            use_color=use_color,
        )

        # ------------------------------------------
        # ALWAYS extract core analysis data
        # ------------------------------------------
        dominant = analysis["dominant"]
        top = analysis["top"]
        state = analysis["state"]
        analysis_duration = 7.5
        analysis_interval = 0.5

        # ==========================================
        # ANALYZE MODE (dedicated output)
        # ==========================================
        if args.analyze:

            analyzer = CPUAnalyzer()

            observation = analyzer.observe(
                fetcher,
                args,
                duration=7.5,
                interval=0.5,
                mode=args.analyze,
            )

            analysis = analyzer.analyze(
                observation["processes"],
                args,
                use_color=use_color,
                core_usages=observation["core_usages"],
            )

            dominant = analysis["dominant"]
            top = analysis["top"]
            state = analysis["state"]

            # Sort processes by CPU usage (descending)
            sorted_procs = sorted(processes, key=lambda p: p.cpu, reverse=True)

            # Exclude dominant process if present
            dominant_pid = dominant.pid if dominant else None

            visible = [
                p for p in sorted_procs
                if not dominant_pid or p.pid != dominant_pid
            ][:10]  # fixed, clean limit

            # --------------------------------------
            # Generate analysis text
            # --------------------------------------
            report_lines = analyzer.generate_analysis(
                analysis,
                analysis_duration,
                analysis_interval,
                args,
                core_usages=observation["core_usages"],
                visible=visible
            )

            # --------------------------------------
            # CPU STATE (Top indicator)
            # --------------------------------------
            # Use color theme
            if use_color:
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
                # Use color theme
                if use_color:
                    left_lines.append(f"{fg(0x777777)}Dominant Source:{RESET}")
                    left_lines.append(
                        f"{fg(0xaaaaaa)}• {RESET}{fg(0x777777)}{dominant.comm}{RESET} "
                        f"{dominant.cpu:.1f}% "
                        f"{fg(0xaaaaaa)}{dominant.stat} {RESET}"
                        f"{dominant.threads}{fg(0xaaaaaa)}Thr{RESET}"
                    )
                    left_lines.append(f"  {fg(0xaaaaaa)}└─ {RESET}{analysis['dominant_desc']}")
                else:
                    left_lines.append("Dominant Source:")
                    left_lines.append(
                        f"• {dominant.comm} {dominant.cpu:.1f}% {dominant.stat} {dominant.threads}Thr"
                    )
                    left_lines.append(f"  └─ {analysis['dominant_desc']}")
            else:
                left_lines.append("Dominant Source:")
                left_lines.append("  ---")

            # --------------------------------------
            # Build LEFT (Observation Summary)
            # --------------------------------------
            temporal = analysis.get("temporal_summary", {})

            mean_cpu = temporal.get("mean_cpu", 0.0)
            min_cpu  = temporal.get("min_cpu", 0.0)
            max_cpu  = temporal.get("max_cpu", 0.0)
            dominant_persistence = temporal.get("dominant_persistence", 0.0)

            if use_color:
                left_lines.append("")
                left_lines.append("Observation Summary:")

                # Mean CPU
                left_lines.append(f"{fg(0xaaaaaa)}• Mean CPU: {RESET}"
                                  f"{mean_cpu:.0f}"
                                  f"{fg(0xaaaaaa)}%{RESET}")

                # Min/max CPU
                left_lines.append(
                    f"{fg(0xaaaaaa)}• CPU range: min:{RESET} "
                    f"{min_cpu:.0f}"
                    f"{fg(0xaaaaaa)}{RESET}"
                    f"{fg(0xaaaaaa)}% → max:{RESET} "
                    f"{max_cpu:.0f}"
                    f"{fg(0xaaaaaa)}%{RESET}"
                )
                left_lines.append(
                    f"{fg(0xaaaaaa)}• Dominant persistence: {RESET}"
                    f"{dominant_persistence:.0f}"
                    f"{fg(0xaaaaaa)}%{RESET} "
                    f"{fg(0xaaaaaa)}(over {RESET}"
                    f"{analysis_duration:.1f}"
                    f"{fg(0xaaaaaa)}s{RESET})"
                )
            else:
                left_lines.append("")
                left_lines.append("Observation Summary:")

                left_lines.append(f"• Mean CPU: {mean_cpu:.0f}%")
                left_lines.append(
                    f"• CPU range: min: {min_cpu:.0f}% → max: {max_cpu:.0f}%"
                )
                left_lines.append(
                    f"• Dominant persistence: "
                    f"{dominant_persistence:.0f}% "
                    f"(over {analysis_duration:.1f}s)"
                )

            # --------------------------------------
            # Build RIGHT (Top contributors)
            # --------------------------------------
            right_lines = []

            ## PREVIOUS POSITION FOR "visible"

            stat_processes = []

            if dominant:
                stat_processes.append(dominant)

            stat_processes.extend(visible)

            # Header
            if use_color:
                title = "Top contributor:" if len(visible) == 1 else "Top contributors:"
                right_lines.append(f"{fg(0x777777)}{title}{RESET}")
            else:
                right_lines.append("Top contributor:" if len(visible) == 1 else "Top contributors:")

            # Rows
            for p in visible:
                cmd = p.comm[:12].ljust(12)
                pid = str(p.pid).rjust(8)
                stat = p.stat.ljust(4)

                if use_color:
                    cpu = f"{fg(0xaaaaaa)}{p.cpu:.0f}%{RESET}".rjust(4)
                    bullet = f"{fg(0xaaaaaa)}• {RESET}"
                    stat_col = f"{fg(0xaaaaaa)}{stat}{RESET}"
                else:
                    cpu = f"{p.cpu:.0f}%".rjust(4)
                    bullet = "• "
                    stat_col = stat

                right_lines.append(f"{bullet}{cmd}  {pid}    {stat_col}  {cpu}")

            # --------------------------------------
            # Print side-by-side
            # --------------------------------------
            LEFT_W = 50

            rows = max(len(left_lines), len(right_lines))

            for i in range(rows):
                left = left_lines[i] if i < len(left_lines) else ""
                right = right_lines[i] if i < len(right_lines) else ""

                padding = LEFT_W - visible_len(left)
                if padding < 0:
                    padding = 0

                print(f"{left}{' ' * padding}{right}")

            # Use color theme
            if use_color:
                print(f"\n{BOLD}{fg(0xffffff)}System Analysis:{RESET}")
            else:
                print("\nSystem Analysis:")

            report_text = "\n".join(report_lines)

            #for line in report_lines:
            print(report_text.rstrip())

            # Only add spacing when header is hidden AND table will follow
            if args.hide_header and not args.hide_table:
                print()

            print()
            return

        # --- Load previous run data ---
        config_path = os.path.expanduser("~/.config/cpuvw/scores.json")

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
            args.table_cpu_threshold
            if args.table_cpu_threshold is not None
            else config.get("cpu", {}).get("threshold", 1.0)
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
        # SHOW HIGHEST SCORES
        #    - conditional.
        #    - shown with -high-score flag
        #    - show last runs highest CPU%
        #    - show highest CPU% ever measured
        # -------------------------------------------------------------------------------------
        # High score was chosen
        if use_high_schore:
            # Print last run's highest CPU usage

            # Use color theme
            if use_color:
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

            # Use color theme
            if use_color:
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
        # HIDE everything except the table output
        #    - Hide all four analysis sections and display only table
        # -------------------------------------------------------------------------------------
        if not args.hide_analysis:
            # -------------------------------------------------------------------------------------
            # USER FOCUS Section
            #    - displays current highest number of threads for user
            #    - displays command run time in seconds with three decimals
            # -------------------------------------------------------------------------------------
            user_focus = []

            if primary:

                # Use color theme
                if use_color:
                    user_focus.append(f"{fg(0x777777)}{primary.user}{RESET}"
                                      f"{fg(0xaaaaaa)} →{RESET} "
                                      f"{fg(0xffffff)}{primary.threads}"
                                      f"{RESET}{fg(0xaaaaaa)} thread(s){RESET}")
                else:
                    user_focus.append(f"{primary.user} → {primary.threads} thread(s)")

            runtime = time.time() - start_time

            # Use color theme
            if use_color:
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

            # Use color theme
            if use_color:  # Use color theme
                left_lines.append(f"{fg(0x777777)}Misc System Stats:{RESET}")
            else:
                left_lines.append(f"Misc System Stats:")

            # ------------------------------------------
            # Color it
            # ------------------------------------------
            if use_color:  # Use color theme
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
                if use_color:  # Use color theme
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
                if use_color:  # Use color theme
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
                    if use_color:  # Use color theme
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
            if use_color:  # Use color theme
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
            if use_color:  # Use color theme
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
            if use_color:  # Use color theme
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

        # ------------------------------------------
        # If --number is used → disable threshold filtering
        # ------------------------------------------
        if args.number is not None:
            meaningful = processes
            low_cpu = []
        else:
            meaningful = [p for p in processes if p.cpu >= threshold]
            low_cpu = [p for p in processes if p.cpu < threshold]

        count = len(meaningful)

        # Compute dynamic limit
        state_cfg = config.get("states", {}).get(state, {})

        min_procs = state_cfg.get("min", 0)
        max_procs = state_cfg.get("max", 5)

        # ------------------------------------------
        # FINAL LIMIT LOGIC
        # ------------------------------------------
        if args.number is not None:
            limit = args.number
        else:
            limit = min(max(count, min_procs), max_procs)

        # ------------------------------------------
        # REMOVE IDLE (FINAL SANITIZATION)
        # ------------------------------------------
        if not args.all:
            meaningful = [
                p for p in meaningful
                if "idle" not in (p.command or "").lower()
            ]

        # Assemble final list
        if show_low_cpu:
            combined = [p for p in processes if p in meaningful or p in low_cpu]
        else:
            combined = [p for p in processes if p in meaningful]

        if args.number is not None:
            processes = processes[:limit]

        else:
            if combined:
                processes = combined[:limit]
            else:
                if show_low_cpu:
                    processes = processes[:max_procs]
                else:
                    processes = [
                        p for p in processes
                        if p.cpu >= threshold
                    ][:max_procs]


        # ------------------------------------------
        # TABLE OUTPUT (respect --no-table)
        # ------------------------------------------
        if not args.hide_table:

            # ------------------------------------------
            # Call formatter
            # ------------------------------------------
            formatter = ProcessFormatter()

            # ----------------------------------------------------------
            # About the arguments in the "lines" statement:
            #
            #     - processes → processes;
            #     - args.color → use_color;
            #     - args → args
            # ----------------------------------------------------------
            lines = formatter.format(
                processes,
                args.color,
                args
            )


        # ------------------------------------------
        # PRINT TABLE
        # ------------------------------------------
        if not args.hide_table:
            for line in lines:
                print(line.rstrip())

        # ------------------------------------------
        # STAT INFO SECTION
        # ------------------------------------------
        if args.stat_info:
            print()
            right_lines = []

            if use_color:  # Use color theme
                right_lines.append(f"{fg(0xaaaaaa)}STAT Analysis:{RESET}")
            else:
                right_lines.append("STAT Analysis:")

            # Active processes (reuse same threshold logic later if needed)
            threshold = (
                args.table_cpu_threshold
                if args.table_cpu_threshold is not None
                else config.get("cpu", {}).get("threshold", 1.0)
            )

            if args.number is not None:
                # When user forces output, analyze visible processes instead
                active = processes
            else:
                active = [p for p in processes if p.cpu >= threshold]

            right_lines.append(f"• {len(active)} active processes detected")

            # Collect unique stat flags
            stat_chars = sorted(
                extract_unique_stats(active),
                key=lambda x: [
                    # --------------------------------------------------
                    # Primary execution states
                    # --------------------------------------------------
                    "R",
                    "S",
                    "D",
                    "I",

                    # --------------------------------------------------
                    # Stopped / traced
                    # --------------------------------------------------
                    "T",
                    "t",

                    # --------------------------------------------------
                    # Dead / zombie
                    # --------------------------------------------------
                    "Z",
                    "X",

                    # --------------------------------------------------
                    # Paging
                    # --------------------------------------------------
                    "W",

                    # --------------------------------------------------
                    # Scheduling priority
                    # --------------------------------------------------
                    "<",
                    "N",

                    # --------------------------------------------------
                    # Memory / threading
                    # --------------------------------------------------
                    "L",
                    "l",

                    # --------------------------------------------------
                    # Session / interaction
                    # --------------------------------------------------
                    "s",
                    "+",

                    # --------------------------------------------------
                    # Behavioral marker
                    # --------------------------------------------------
                    "C",
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
                print(line.rstrip())

        ## ------------------------------------------
        ## Show when CPUVw was executed at bottom
        ## ------------------------------------------
        # ------------------------------------------
        # color the by-line
        # ------------------------------------------

        if use_color:  # Use color theme
            now = datetime.now().astimezone()
            print(f"\nCPUVw was executed at: "
                + f"{fg(+0xaaaaaa) + now.strftime('%a %b %d %H:%M:%S %Z %Y')}"
            )

        # ------------------------------------------
        # Use no colors
        # ------------------------------------------
        else:
            now = datetime.now().astimezone()
            print(f"\nCPUVw was executed at: "
                  + now.strftime("%a %b %d %H:%M:%S %Z %Y")
                  )

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

