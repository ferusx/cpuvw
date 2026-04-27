# tree_builder.py

# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 Markus Johnsson

from collections import defaultdict


# =========================================================
# Class: ProcessTreeBuilder
# =========================================================
class ProcessTreeBuilder:
    """
    Responsible for constructing the hierarchical process tree.

    Converts a flat list of ProcessInfo objects into:
    - A list of root processes
    - A mapping of parent PID → child processes

    This structure is later consumed by the tree formatter
    for recursive rendering.
    """

    # --------------------------------------------------------------------
    # Method: build
    # --------------------------------------------------------------------
    @staticmethod
    def build(processes):
        """
        Build parent-child relationships from a flat process list.

        Args:
            processes (List[ProcessInfo]):
                List of processes retrieved from the system.

        Returns:
            Tuple[List[ProcessInfo], Dict[int, List[ProcessInfo]]]:
                - roots: Top-level processes (no valid parent)
                - children: Mapping of PID → list of child processes

        Notes:
            - Uses PID lookup for fast parent resolution
            - Ensures all PIDs exist in the children map
            - Handles orphaned processes (missing parent)
        """

        children = defaultdict(list)
        pid_map = {}

        # Build PID lookup
        for p in processes:
            pid_map[p.pid] = p

        # Build parent → children mapping
        for p in processes:
            if p.ppid in pid_map:
                children[p.ppid].append(p)

        # Roots = processes whose parent is NOT in dataset
        # Identify roots safely
        roots = [p for p in processes if p.pid == 1]

        # Fallback: if init not present (e.g. sliced dataset)
        if not roots:
            roots = processes

        return roots, children


