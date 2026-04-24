# filters.py

# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 Markus Johnsson

from typing import List
from models import ProcessInfo

# =========================================================
# Class: ProcessFilter
# =========================================================
class ProcessFilter:
    """
    Responsible for filtering process data based on user-provided criteria.

    Applies optional filters such as:
    - User ownership
    - Specific PID
    - Command substring matching

    This stage operates on already fetched data and does not modify
    the original list structure beyond filtering.
    """

    # --------------------------------------------------------------------
    # Method: apply
    # --------------------------------------------------------------------
    @staticmethod
    def apply(processes: List[ProcessInfo], args) -> List[ProcessInfo]:
        """
        Filter a list of ProcessInfo objects according to CLI arguments.

        Args:
            processes (List[ProcessInfo]):
                The full list of processes to filter.

            args:
                Parsed command-line arguments containing optional filters.

        Returns:
            List[ProcessInfo]: Filtered list of processes

        Notes:
            - Filters are applied sequentially (user → pid → command)
            - Each filter reduces the current result set
            - String matching for command is case-insensitive
        """

        result = processes

        # User
        if args.user:
            result = [p for p in result if p.user == args.user]

        # PID
        if getattr(args, "user", None):
            result = [p for p in result if p.pid == args.pid]

        # Filter
        if getattr(args, "filter", None):
            result = [
                p for p in result
                if args.filter.lower() in p.command.lower()
            ]


        return result

# =========================================================
# Class: ProcessSorter
# =========================================================
class ProcessSorter:
    """
    Responsible for ordering processes based on user-defined criteria.

    Supports sorting by: (default → descending)
    - CPU usage
    - Memory usage
    - Process ID
    - Resident Set Size in megabytes (physical memory usage).
    - Threads
    - Command (default → ascending, in lower-case)

    Sorting direction can be reversed using the -b, --bottom flag.
    """

    # --------------------------------------------------------------------
    # Method: apply
    # --------------------------------------------------------------------
    @staticmethod
    def apply(processes, args):
        """
        Sort processes based on selected field.

        Default: CPU (descending)
        """

        key_map = {
            "cpu": lambda p: p.cpu,
            "mem": lambda p: p.mem,
            "pid": lambda p: p.pid,
            "thr": lambda p: p.threads,
            "cmd": lambda p: (p.command or "").lower(),
        }

        key_func = key_map.get(args.sort, key_map["cpu"])

        # Default descending except for cmd
        if args.sort == "cmd":
            reverse = False
        else:
            reverse = True

        # Apply --bottom override
        if getattr(args, "bottom", False):
            reverse = not reverse

        return sorted(processes, key=key_func, reverse=reverse)