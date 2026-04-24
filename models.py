# models.py

# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 Markus Johnsson

from dataclasses import dataclass
from typing import List, TypedDict

# =========================================================
# Data class: ProcessInfo
# =========================================================
@dataclass
class ProcessInfo:
    """
    Represents a single process as seen by procvw.py.

    Think of this as the “snapshot” of a process at the moment it was
    observed. Each instance holds everything the application needs to
    understand, organize, and display that process — nothing more,
    nothing less.

    The data is collected from ps(1) and then carried unchanged through
    the pipeline, where it may be filtered, sorted, or rendered in
    different ways depending on user input.

    Fields:

        pid (int):
            Process ID.

        ppid (int):
            Parent Process ID, used to reconstruct process hierarchy.

        user (str):
            The user that owns the process.

        stat (str):
            Process state flags as reported by ps (e.g. "S", "Ss", "R+").
            These give a quick glimpse into what the process is doing.

        cpu (float):
            CPU usage percentage.
            On BSD systems, this may exceed 100% on multicore machines.

        mem (float):
            Memory usage percentage.

        rss_mb (float):
            Resident Set Size in megabytes — the actual physical memory
            currently used by the process.

        started (str):
            Full start time string as returned by ps
            (e.g. "Thu Apr  2 17:06:03 2026").
            This is later formatted for display.

        time (str):
            Total CPU time consumed by the process (raw ps format),
            later adapted for readability.

        threads (int):
            Number of threads associated with the process.

        comm (str):
            Short command name (e.g. "sshd", "zsh", "clock").
            This is the default display value in standard views.

        command (str):
            Full executable path (e.g. "/usr/sbin/sshd").
            Used when --show-path is enabled.

    Role in the system:

        - Created by ProcessFetcher
        - Passed through ProcessFilter and ProcessSorter
        - Consumed by formatters for display (table/tree/JSON)

    This class deliberately contains no logic. It simply carries data
    cleanly through the system, allowing each stage of the pipeline to
    do its job without side effects or hidden behavior.
    """
    pid: int
    ppid: int
    user: str
    stat: str
    cpu: float
    mem: float
    rss_mb: float
    started: str
    time: str
    threads: int
    command: str
    comm: str

# =========================================================
# TypedDict: ProcessNode
# =========================================================
class ProcessNode(TypedDict):
    """
    Represents a node in the process tree.

    While ProcessInfo describes a process in isolation, ProcessNode
    captures how that process fits into the bigger picture — its
    position in the hierarchy and its relationship to other processes.

    Each node mirrors a ProcessInfo entry but adds structural context,
    allowing procvw.py to build and traverse a full parent/child tree.

    This structure is primarily used for:
        - Tree rendering (ProcessTreeFormatter)
        - JSON export/import of hierarchical data

    Fields:

        pid (int):
            Process ID.

        ppid (int):
            Parent Process ID.

        user (str):
            Owner of the process.

        stat (str):
            Process state flags (as reported by ps).

        comm (str):
            Short command name (default display value).

        command (str):
            Full executable path (used with --show-path).

        cpu (float):
            CPU usage for this process alone.

        subtree_cpu (float):
            Aggregated CPU usage including all descendant processes.
            This is what makes it possible to identify “heavy branches”
            in the process tree.

        mem (float):
            Memory usage percentage.

        threads (int):
            Number of threads associated with the process.

        started (str):
            Raw start time string from ps.

        time (str):
            Total CPU time consumed by the process.

        rss_mb (float):
            Resident memory usage in megabytes.

        children (List[ProcessNode]):
            Child processes belonging to this node.
            This is what turns a flat list into a recursive tree.

    Notes:

        - This is a recursive structure: each node may contain a list
          of child nodes, each of which is itself a ProcessNode.
        - The structure is intentionally explicit (no hidden links),
          making it easy to serialize, inspect, and debug.
        - Unlike ProcessInfo, this structure is used only after
          hierarchy has been constructed.
    """
    pid: int
    ppid: int
    user: str
    stat: str
    command: str
    comm: str
    cpu: float
    subtree_cpu: float
    mem: float
    threads: int
    started: str
    time: str
    rss_mb: float
    children: List["ProcessNode"]

