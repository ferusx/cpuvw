# fetcher.py

# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 Markus Johnsson

import subprocess
from typing import List

# Local imports
from models import ProcessInfo

# =========================================================
# Class: ProcessFetcher
# =========================================================
class ProcessFetcher:
    """
    Responsible for retrieving process data from the system.

    Uses the BSD `ps` command to collect raw process information
    and converts each row into a structured ProcessInfo object.

    NOTE: This is the ONLY component that interacts with the system.
    """

    # --------------------------------------------------------------------
    # Method: fetch
    # --------------------------------------------------------------------
    @staticmethod
    def fetch(args) -> List[ProcessInfo]:
        """
        Retrieve live process data from the system using `ps`.

        This function executes a BSD-compatible `ps` command and converts
        its output into structured ProcessInfo objects. It serves as the
        entry point for all live data used by the application.

        The parser relies on fixed column ordering and reconstructs fields
        that may contain spaces, such as the start time (`lstart`) and the
        full command string.

        Behavior:

            - Executes `ps` with extended width (`-ww`) to avoid truncation
            - Skips the header line automatically
            - Parses each row into strongly-typed ProcessInfo objects
            - Silently skips malformed lines to ensure robustness

        Args:
            args:
                Parsed CLI arguments (currently unused, reserved for future use)

        Returns:
            List[ProcessInfo]:
                List of all processes retrieved from the system.

        Notes:

            - Assumes BSD-style `ps` output formatting
            - `comm` provides a short executable name (normalized)
            - `command` contains the full command including arguments
            - Parsing is position-based and therefore sensitive to changes
              in the `ps` output format
        """

        # Use wide output (-ww) and fixed column order for predictable parsing
        cmd = "ps -ww -axo pid,ppid,user,state,%cpu,%mem,rss,lstart,time,nlwp,comm,command"

        output = subprocess.check_output(cmd.split(), text=True)

        # We skip the header line
        lines = output.strip().split("\n")[1:]

        processes = []

        for line in lines:
            try:
                # Split into fields (lstart and command require reconstruction)
                parts = line.split()

                pid = int(parts[0])
                ppid = int(parts[1])
                user = parts[2]
                stat = parts[3]
                cpu = float(parts[4])
                mem = float(parts[5])
                rss_kb = int(parts[6])
                rss_mb = rss_kb / 1024

                # Reconstruct lstart (5 fields: weekday, month, day, time, year)
                started = " ".join(parts[7:12])

                time = parts[12]
                threads = int(parts[13])

                comm = parts[14]

                # Normalize kernel processes (remove surrounding brackets)
                if comm.startswith("[") and comm.endswith("]"):
                    comm = comm[1:-1]

                # Reconstruct full command (may contain spaces and arguments)
                command = " ".join(parts[15:])

                processes.append(
                    ProcessInfo(
                        pid=pid,
                        ppid=ppid,
                        user=user,
                        stat=stat,
                        cpu=cpu,
                        mem=mem,
                        rss_mb=rss_mb,
                        started=started,
                        time=time,
                        threads=threads,
                        comm=comm,
                        command=command
                    )
                )

            except ValueError:
                # Skip malformed lines without interrupting execution
                continue

        return processes

