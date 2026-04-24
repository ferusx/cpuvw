# tree_builder.py

# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 Markus Johnsson


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

        children = {}
        lookup = {}

        # Build PID → Process lookup for fast parent checks
        for p in processes:
            lookup[p.pid] = p
            children.setdefault(p.pid, [])

        # Build parent → children mapping
        for p in processes:
            children.setdefault(p.ppid, [])
            children[p.ppid].append(p)

        # Identify root processes (no valid parent)
        roots = []

        for p in processes:
            if p.ppid == 0 or p.ppid == 1 or p.ppid not in lookup:
                roots.append(p)

        return roots, children


