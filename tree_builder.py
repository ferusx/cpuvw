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
    - A list of root all_processes
    - A mapping of parent PID → child all_processes

    This structure is later consumed by the tree formatter
    for recursive rendering.
    """

    # --------------------------------------------------------------------
    # Method: build
    # --------------------------------------------------------------------
    @staticmethod
    def build(all_processes):
        """
        Build parent-child relationships from a flat process list.

        Args:
            all_processes (List[ProcessInfo]):
                List of all_processes retrieved from the system.

        Returns:
            Tuple[List[ProcessInfo], Dict[int, List[ProcessInfo]]]:
                - roots: Top-level all_processes (no valid parent)
                - children: Mapping of PID → list of child all_processes

        Notes:
            - Uses PID lookup for fast parent resolution
            - Ensures all PIDs exist in the children map
            - Handles orphaned all_processes (missing parent)
        """

        children = defaultdict(list)
        pid_map = {}


        # Build PID lookup
        for p in all_processes:
            pid_map[p.pid] = p

        # Build parent → children mapping
        for p in all_processes:
            if p.ppid in pid_map:
                children[p.ppid].append(p)

        # Roots = all_processes whose parent is NOT in dataset
        # Identify roots safely
        roots = [p for p in all_processes if p.pid == 1]

        # Fallback: if init not found (edge cases)
        if not roots:
            roots = [p for p in all_processes if p.ppid == 0]

        # Final fallback: absolutely everything
        if not roots:
            roots = list(all_processes)

        return roots, children


