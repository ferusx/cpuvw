# tree_formatter.py

# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 Markus Johnsson

from typing import List

from constants import RESET, GLYPH_STYLES, fg
# Local imports
from tree_builder import ProcessTreeBuilder
from models import ProcessInfo


# =========================================================
# Class: ProcessTreeFormatter
# =========================================================
class ProcessTreeFormatter:
    """
    Responsible for rendering processes in a hierarchical tree structure.

    This formatter takes a filtered/sorted process list and builds a visual
    tree representation using parent-child relationships.

    Core responsibilities:
    - Build process tree structure via ProcessTreeBuilder
    - Compute subtree CPU usage (including descendants)
    - Sort nodes based on selected criteria
    - Render tree using ASCII/UTF-8 branch glyphs
    - Apply optional color formatting

    Features:
    - Subtree CPU aggregation with caching
    - CPU visibility modes (--cpu-all, --cpu-threshold)
    - Depth limiting (--tree-depth)
    - Stable and safe recursion (loop protection)

    This class operates purely on in-memory data and does not
    interact with the system or modify process state.
    """

    # --------------------------------------------------------------------
    # Method: format
    # --------------------------------------------------------------------
    @staticmethod
    def format(processes: List[ProcessInfo],  all_processes, args, use_color: bool):
        """
        Render the process tree as a list of formatted strings.

        Args:
            processes (List[ProcessInfo]):
                Filtered process list (visible nodes).

            all_processes:
                Full process list used to build complete tree structure.

            args:
                Parsed CLI arguments controlling sorting, depth,
                CPU visibility, and output behavior.

            use_color (bool):
                Enable or disable ANSI color formatting.

        Returns:
            List[str]: Rendered tree lines ready for printing.

        Notes:
            - Tree structure is built from all_processes to preserve hierarchy
            - Only processes in `processes` are considered visible
            - Rendering respects depth limits
        """

        visible_pids = {p.pid for p in processes}

        roots, children = ProcessTreeBuilder.build(all_processes)

        subtree_cache = {}

        # --------------------------------------------------------------------
        # Method: compute_subtree_cpu
        # --------------------------------------------------------------------
        def compute_subtree_cpu(node, visited=None):
            """
            Compute total CPU usage for a process subtree.

            This function walks the process tree starting from the given node
            and sums CPU usage for the node itself and all of its descendants.
            The result represents the "weight" of an entire branch, not just
            a single process.

            To keep performance reasonable, results are cached per PID so that
            repeated calculations on the same subtree are avoided.

            Safety features:

                - Cycle protection:
                    A visited set is used to prevent infinite recursion in case
                    of malformed or unexpected process graphs.

                - Memoization:
                    Previously computed subtree totals are stored in
                    `subtree_cache` and reused when possible.

            Args:
                node (ProcessInfo):
                    The process node to evaluate.

                visited (set, optional):
                    Tracks visited PIDs during recursion to prevent cycles.
                    A copy is passed to child calls to isolate recursion paths.

            Returns:
                float:
                    Total CPU usage for this node and all its descendants.

            Notes:

                - The traversal is depth-first.
                - Each recursion branch operates on its own copy of the visited set
                  to avoid cross-branch interference.
                - This function is performance-sensitive and called frequently
                  during tree rendering.
            """

            if visited is None:
                visited = set()

            if node.pid in visited:
                return 0  # break cycle safely

            visited.add(node.pid)

            if node.pid in subtree_cache:
                return subtree_cache[node.pid]

            total = node.cpu

            for child in children.get(node.pid, []):
                total += compute_subtree_cpu(child, visited.copy())

            subtree_cache[node.pid] = total
            return total

        sort_key_outer = args.sort

        # If sort by command, descend on --bottom
        if sort_key_outer == "cmd":
            reverse = args.bottom  # default ascending, -b reverses
        else:
            reverse = not args.bottom  # default descending, -b flips

        # --------------------------------------------------------------------
        # Method: get_sort_value
        # --------------------------------------------------------------------
        def get_sort_value(p):
            """
            Determine the sorting value for a process node.

            The selected sort key controls which attribute is used to order
            processes. For CPU-based sorting, the total subtree CPU is used
            instead of per-process CPU, allowing entire branches to be ranked
            by their overall activity.

            Supported sort modes:

                - cpu → total subtree CPU (node + descendants)
                - mem → memory usage percentage
                - pid → process ID
                - cmd → command name (alphabetical, case-insensitive)

            Args:
                p (ProcessInfo):
                    Process node to evaluate.

            Returns:
                Any:
                    Value used as sorting key (numeric or string).
            """

            # Use subtree CPU so entire branches are ranked by total activity
            if sort_key_outer == "cpu":
                return compute_subtree_cpu(p)
            elif sort_key_outer == "mem":
                return p.mem
            elif sort_key_outer == "pid":
                return p.pid
            elif sort_key_outer == "cmd":
                return (p.command or "").lower()
            elif sort_key_outer == "stat":
                state = (p.stat or "")[:1]  # first char only

                priority = {
                    "R": 0,  # Running
                    "D": 1,  # Uninterruptible sleep
                    "S": 2,  # Sleeping
                    "I": 3,  # Idle
                    "T": 4,  # Stopped
                    "Z": 5  # Zombie
                }

                return priority.get(state, 99)
            return compute_subtree_cpu(p)

        # Apply sorting to root nodes.
        # Command sorting is handled separately to ensure consistent
        # alphabetical behavior, while other modes use get_sort_value().
        if sort_key_outer == "cmd":
            roots = sorted(
                roots,
                key=lambda p: (p.comm or "").lower(),
                reverse=reverse
            )
        else:
            roots = sorted(
                roots,
                key=lambda p: (
                    get_sort_value(p),
                    (p.command or "").lower()
                ),
                reverse=reverse
            )

        # lines → final rendered output
        # printed → track emitted PIDs to prevent duplicates
        lines = []
        printed = set()


        # --------------------------------------------------------------------
        # Method: render
        # --------------------------------------------------------------------
        def render(node, prefix="", is_last=True, visited=None, depth=1):
            """
            Render a process node and its subtree in a tree structure.

            This function is the core of the tree view. It walks the process
            hierarchy recursively and constructs formatted output lines with:

                - Tree glyphs (branches, connectors)
                - Optional CPU annotations (subtree-based)
                - Colorized fields (PID, USER, COMMAND)
                - Depth limiting safeguards

            Behavior:

                - Traverses nodes depth-first
                - Stops recursion when --tree-depth is exceeded
                - Avoids duplicate rendering via `printed`
                - Prevents infinite loops via `visited`
                - Adapts output based on flags like --show-path,
                  --cpu-all, and --cpu-threshold

            Args:
                node (ProcessInfo):
                    Current process node to render.

                prefix (str):
                    Accumulated tree prefix used to draw structure.

                is_last (bool):
                    Whether this node is the last child in its branch.

                visited (set, optional):
                    Tracks visited nodes to prevent recursion loops.

                depth (int):
                    Current recursion depth.

            Notes:

                - Rendering is stateful: relies on shared structures like
                  `printed`, `visible_pids`, and `children`.
                - CPU display is based on subtree aggregation, not per-process CPU.
                - This function only builds lines — it does not print directly.
            """

            # Enforce user-defined depth limit (--tree-depth)
            if args.tree_depth is not None and depth > args.tree_depth:
                return

            if node.pid in printed:
                return

            # Prevent rendering the same PID multiple times (global safeguard)
            printed.add(node.pid)
            if visited is None:
                visited = set()

            # Prevent infinite recursion in malformed process graphs
            if node.pid in visited:
                return

            visited.add(node.pid)

            # Select glyph style for tree branches (ASCII / UTF-8 variants)
            glyph = GLYPH_STYLES.get(str(args.glyph_style or "1"), GLYPH_STYLES["1"])

            branch = glyph["last"] if is_last else glyph["branch"]

            line_prefix = prefix + (branch if prefix else "")

            pid_str = str(node.pid)
            if args.show_path:
                cmd_str = node.command
            else:
                cmd_str = node.comm
            cpu_part = ""

            if use_color:
                pid_str = f"{fg(15)}{pid_str}{RESET}"
                cmd_str = f"{RESET}{fg(6)}{cmd_str}{RESET}"

            user_str = node.user

            # Select glyph style for tree branches (ASCII / UTF-8 variants)
            if use_color:
                user_str = f"{fg(2)}{user_str}{RESET}"

            pipe = glyph["pipe"]
            space = glyph["space"]

            # Extend prefix for next level (pipe continues, space ends branch)
            new_prefix = prefix + (space if is_last else pipe)

            # Sort children according to selected key.
            # Command sorting uses short names (comm) for human-friendly ordering.
            sort_key = args.sort

            children_nodes = sorted(
                children.get(node.pid, []),
                key=lambda p: (
                    get_sort_value(p),
                    (p.command or "").lower()  # tie-breaker for stability
                ),
                reverse=reverse
            )

            filtered_children = children_nodes

            # Determine if node has no children (used for leaf marker glyph)
            is_leaf = len(children.get(node.pid, [])) == 0
            leaf_marker = glyph.get("leaf", "") if is_leaf else ""

            if leaf_marker:
                # Attach optional leaf marker for visual clarity
                line_prefix_clean = line_prefix.rstrip()
                prefix_with_marker = f"{line_prefix_clean}{leaf_marker} "
            else:
                prefix_with_marker = line_prefix

            # Colorize tree structure separately from content
            if use_color:
                prefix_with_marker = f"{fg(15)}{prefix_with_marker}{RESET}"

            # Build left part
            stat_str = node.stat if hasattr(node, "stat") else "?"

            left_part = (
                f"{prefix_with_marker}"
                f"{pid_str:<4} "
                f"{user_str:<6} "
                f"{stat_str:<1} "
                f"{cpu_part}"
            )

            # Combine left-aligned fields with (possibly truncated) command
            line = f"{left_part}{cmd_str}"
            lines.append(line)

            # Stop recursion once maximum depth is reached
            if args.tree_depth is not None and depth >= args.tree_depth:
                return

            # Recursively render children with updated prefix and depth
            for idx, child in enumerate(filtered_children):

                if child.pid == node.pid:
                    continue

                render(child, new_prefix, idx == len(filtered_children) - 1, visited, depth + 1)

        # Render each root only if it contributes visible content
        for i, root in enumerate(roots):
            render(root, "", i == len(roots) - 1, None, 1)

        if args.number:
            # Apply global output limit after full rendering
            return lines[:args.number]

        return lines
