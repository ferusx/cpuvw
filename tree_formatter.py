# tree_formatter.py

# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 Markus Johnsson


from typing import List
import shutil


# Local imports
from tree_builder import ProcessTreeBuilder
from models import ProcessInfo
from utils import get_exec_name, visible_len
from constants import (
    GLYPH_STYLES,
    RESET,
    fg
)

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
    - Prune irrelevant or low-value branches
    - Render tree using ASCII/UTF-8 branch glyphs
    - Apply optional color formatting

    Features:
    - Subtree CPU aggregation with caching
    - CPU visibility modes (--cpu-all, --cpu-threshold)
    - Depth limiting (--tree-depth)
    - Intelligent branch pruning
    - Stable and safe recursion (loop protection)

    This class operates purely on in-memory data and does not
    interact with the system or modify process state.
    """

    # --------------------------------------------------------------------
    # Method: format
    # --------------------------------------------------------------------
    @staticmethod
    def format(processes, all_processes, args, use_color=False, visible_pids=None):
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
            - Rendering respects depth limits and pruning rules
        """
        lines = []
        rendered_pids = set()

        # ------------------------------------------
        # Always build full tree structure
        # ------------------------------------------
        tree_source = all_processes if args.with_parents else processes

        roots, children_map = ProcessTreeBuilder.build(tree_source)

        # ------------------------------------------
        # Expand parents if requested
        # ------------------------------------------
        if args.with_parents:
            pid_map = {p.pid: p for p in all_processes}
            expanded = set(visible_pids)

            for p in processes:
                current = p
                while current.ppid in pid_map:
                    parent = pid_map[current.ppid]
                    if parent.pid in expanded:
                        break
                    expanded.add(parent.pid)
                    current = parent

            visible_pids = expanded

        # ------------------------------------------
        # Strict filtering: roots = visible nodes
        # ------------------------------------------
        roots = [p for p in processes if p.pid in visible_pids]

        subtree_cache = {}

        # --------------------------------------------------------------------
        # Method: compute_subtree_cpu
        # --------------------------------------------------------------------
        def compute_subtree_cpu(node, children_map, visited=None):
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

            for child in children_map.get(node.pid, []):
                total += compute_subtree_cpu(child, children_map, visited.copy())

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
                return compute_subtree_cpu(p, children_map)
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
            return compute_subtree_cpu(p, children_map)

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
        # Method: is_boring
        # --------------------------------------------------------------------
        def is_boring(node):
            """
            Determine whether a process should be considered low-value and hidden.

            This helper is used during tree rendering to reduce visual noise by
            filtering out processes that contribute little meaningful information
            to the overall system view.

            A process may be classified as "boring" depending on the active prune
            level, using progressively stricter criteria.

            Prune levels:

                0   No pruning (all processes are shown)

                1   Hide trivial system processes
                    (root-owned, zero CPU and memory, excluding key services)

                2   Hide all processes with no CPU and memory usage

                3   Aggressive pruning
                    (only retain processes showing meaningful activity or importance)

            The intent is not to discard data, but to improve readability by keeping
            the tree focused on relevant activity and structure.

            Args:
                node (ProcessInfo):
                    Process node to evaluate.

            Returns:
                bool:
                    True if the process should be hidden, False otherwise.

            Notes:

                - Executable names are normalized via `get_exec_name()` to ensure
                  consistent matching regardless of path or invocation format.
                - This is a heuristic filter designed for clarity, not strict accuracy.
            """

            level = args.prune or 0

            if level == 0:
                return False

            # Normalize executable name (works for both full path and short name)
            exec_name = get_exec_name(node.command)

            # Level 1 (your current behavior basically)
            if level >= 1:
                if (
                        node.user == "root"
                        and node.cpu == 0.0
                        and node.mem == 0.0
                        and exec_name not in ("Xorg", "sshd", "init", "login")
                ):
                    return True

            # Level 2 (more aggressive)
            if level >= 2:
                if node.cpu == 0.0 and node.mem == 0.0:
                    return True

            # Level 3 (VERY aggressive)
            if level >= 3:
                if exec_name not in ("init", "sshd", "Xorg"):
                    if node.cpu < 0.1:
                        return True

            return False

        # --------------------------------------------------------------------
        # function: count_visible_nodes
        # --------------------------------------------------------------------
        def count_visible_nodes():
            visited = set()

            def walk(node, depth):
                if node.pid in visited:
                    return

                # SAME guards as render
                if not args.with_parents:
                    if node.pid not in visible_pids:
                        return None

                if args.tree_depth is not None and depth > args.tree_depth:
                    return

                visited.add(node.pid)

                prune = args.prune or 0

                for child in children_map.get(node.pid, []):
                    if child.pid not in visible_pids:
                        continue

                    if prune >= 1 and is_boring(child):
                        continue

                    walk(child, depth + 1)

            # IMPORTANT: still loop roots, BUT visited prevents duplicates
            for root in roots:
                walk(root, 1)

            return len(visited)

        # --------------------------------------------------------------------
        # Method: has_visible_descendant
        # --------------------------------------------------------------------
        def has_visible_descendant(node, visited=None):
            """
            Determine whether a node (or any of its descendants) should be shown.

            This function acts as a visibility filter for the tree renderer.
            It ensures that only meaningful branches are displayed by checking
            whether a node — or anything beneath it — contributes useful data.

            A node is considered "visible" if:

                - It is explicitly marked for display (in visible_pids), and
                - It is not classified as "boring"

            If the node itself does not qualify, its children are recursively
            inspected to see if any descendant should be shown. This allows
            parent branches to remain visible when they lead to interesting nodes.

            Args:
                node (ProcessInfo):
                    The process node to evaluate.

                visited (set, optional):
                    Tracks visited PIDs to prevent infinite recursion in case
                    of malformed process graphs.

            Returns:
                bool:
                    True if the node or any descendant should be displayed,
                    False otherwise.

            Notes:

                - Traversal is depth-first.
                - The visited set prevents cycles from causing infinite loops.
                - This function does not render anything — it only decides
                  whether a branch is worth keeping.
            """
            if visited is None:
                visited = set()

            # Cycle protection (defensive guard)
            if node.pid in visited:
                return False

            visited.add(node.pid)

            # Node is directly visible and not filtered out
            if node.pid in visible_pids and not is_boring(node):
                return True

            # Otherwise, check children recursively
            for child in children_map.get(node.pid, []):
                if has_visible_descendant(child, visited):
                    return True

            return False

        # --------------------------------------------------------------------
        # Method: should_render_node
        # --------------------------------------------------------------------
        def should_render_node(node):
            """
            Decide whether a node should be rendered based on mode and prune level.
            """

            # ------------------------------------------
            # STRICT MODE
            # ------------------------------------------
            if not args.with_parents:
                return node.pid in visible_pids

            # ------------------------------------------
            # WITH PARENTS MODE
            # ------------------------------------------

            # Direct match → always show
            if node.pid in visible_pids:
                return True

            # Walk children manually (guaranteed correct)
            stack = list(children_map.get(node.pid, []))

            while stack:
                child = stack.pop()

                if child.pid in visible_pids:
                    return True

                stack.extend(children_map.get(child.pid, []))

            return False

        # --------------------------------------------------------------------
        # Method: format_subtree_cpu
        # --------------------------------------------------------------------
        def format_subtree_cpu(value):
            """
            Format subtree CPU usage for display.

            Converts a floating-point CPU value into a fixed one-decimal
            percentage string, ensuring consistent alignment in tree output.

            Args:
                value (float):
                    Aggregated CPU usage for a node and its descendants.

            Returns:
                str:
                    Formatted CPU string (e.g. "12.3%").
            """
            return f"{value:.1f}%"

        # --------------------------------------------------------------------
        # function: build_tree_structure
        # --------------------------------------------------------------------
        def build_tree_structure():
            visited = set()

            def walk(node, depth):
                if node.pid in visited:
                    return None

                if not args.with_parents:
                    if node.pid not in visible_pids:
                        return

                if args.tree_depth is not None and depth > args.tree_depth:
                    return None

                visited.add(node.pid)

                prune = args.prune or 0

                children_nodes = []
                for child in children_map.get(node.pid, []):
                    if child.pid not in visible_pids:
                        continue

                    if prune >= 1 and is_boring(child):
                        continue

                    child_tree = walk(child, depth + 1)
                    if child_tree:
                        children_nodes.append(child_tree)

                return {
                    "pid": node.pid,
                    "children": children_nodes
                }

            tree = []
            for root in roots:
                node_tree = walk(root, 1)
                if node_tree:
                    tree.append(node_tree)

            return tree

        # --------------------------------------------------------------------
        # function: count_nodes
        # --------------------------------------------------------------------
        def count_nodes(nodes):
            total = 0
            for n in nodes:
                if not n:
                    continue
                total += 1
                total += count_nodes(n.get("children", []))
            return total

        # --------------------------------------------------------------------
        # function: render_tree_node
        # --------------------------------------------------------------------
        def render_tree_node(tree_node, levels, is_last, depth, parent_pid_col):
            node = tree_node["node"]
            children = tree_node["children"]

            # existing render logic for node here

            for idx, child_tree in enumerate(children):
                child_is_last = (idx == len(children) - 1)

                render_tree_node(
                    child_tree,
                    levels + [not child_is_last],
                    child_is_last,
                    depth + 1,
                    parent_pid_col
                )

        # --------------------------------------------------------------------
        # Method: render
        # --------------------------------------------------------------------
        def render(node, levels, is_last, depth, parent_pid_col):

            # ------------------------------------------
            # GUARDS
            # ------------------------------------------

            # HARD FILTER: node must be visible
            if node.pid not in visible_pids:
                return

            # Enforce user-defined depth limit (--tree-depth)
            if args.tree_depth is not None and depth > args.tree_depth:
                return

            if node.pid in printed:
                return

            printed.add(node.pid)

            # ------------------------------------------
            # GLYPH STYLE (ONLY SOURCE OF TRUTH)
            # ------------------------------------------
            glyph = GLYPH_STYLES.get(str(args.glyph_style or "1"), GLYPH_STYLES["1"])

            pipe = glyph["pipe"]
            space = glyph["space"]

            # ------------------------------------------
            # BUILD PREFIX (GRID SYSTEM — FIXES ALIGNMENT)
            # ------------------------------------------
            prefix = ""

            for is_pipe in levels[:-1]:
                prefix += glyph["pipe"] if is_pipe else glyph["space"]

            if levels:
                children = children_map.get(node.pid, [])
                children = [c for c in children if c.pid in visible_pids]

                is_leaf = (len(children) == 0)

                if str(args.glyph_style) == "3" and is_leaf:
                    branch = (glyph["last"] if is_last else glyph["branch"])[:-1] + glyph["leaf"] + " "
                else:
                    branch = glyph["last"] if is_last else glyph["branch"]

                prefix += branch

            # ------------------------------------------
            # RAW VALUES
            # ------------------------------------------
            pid_val = node.pid
            user_val = node.user
            stat_val = getattr(node, "stat", "?")
            cpu_val = getattr(node, "cpu", 0.0)
            if args.show_path:
                cmd_val = (node.command or "").strip("[] ").strip()
            else:
                cmd_val = (node.comm or "").strip("[] ").strip()


            # ------------------------------------------
            # COLOR
            # ------------------------------------------
            pid_str = str(pid_val)

            if use_color:
                pid_txt = f"{fg(0xffffff)}{pid_str}{RESET}"
            else:
                pid_txt = pid_str

            if use_color:
                user_txt = f"{fg(0x777777)}{user_val}{RESET}"
                stat_txt = f"{fg(0xffffff)}{stat_val}{RESET}"

                if cpu_val >= 80:
                    cpu_txt = f"{fg(0xff0000)}{cpu_val:.1f}%{RESET}"
                elif cpu_val >= 40:
                    cpu_txt = f"{fg(0xecbb00)}{cpu_val:.1f}%{RESET}"
                else:
                    cpu_txt = f"{fg(0xaaaaaa)}{cpu_val:.1f}%{RESET}"

                cmd_txt = f"{fg(0x5287d6)}{cmd_val}{RESET}"
            else:
                pid_txt = str(pid_val)
                user_txt = user_val
                stat_txt = stat_val
                cpu_txt = f"{cpu_val:.1f}%"
                cmd_txt = cmd_val

            # ------------------------------------------
            # FINAL LINE
            # ------------------------------------------

            # Build base (everything except command)
            base = f"{prefix}{pid_txt} {user_txt} {stat_txt} (CPU: {cpu_txt}) "

            # Terminal width
            term_width = shutil.get_terminal_size((120, 20)).columns

            # IMPORTANT: visible width (ANSI-safe)
            available = term_width - visible_len(base)
            if available < 10:
                available = 10

            # RAW command (no ANSI)
            raw_cmd = cmd_val

            # --------------------------------------------------
            # WRAP MODE
            # --------------------------------------------------
            if args.line_wrap and args.show_path:
                # Split into chunks of 'available' width
                chunks = [raw_cmd[i:i + available] for i in range(0, len(raw_cmd), available)]

                # First line (with tree prefix)
                first = chunks[0]
                if use_color:
                    first = f"{fg(0x5287d6)}{first}{RESET}"
                line = base + first

                rendered_pids.add(node.pid)
                lines.append(line)

                # Continuation lines (aligned under command start)
                indent = " " * visible_len(base)
                for chunk in chunks[1:]:
                    cont = chunk
                    if use_color:
                        cont = f"{fg(0x5287d6)}{cont}{RESET}"
                    lines.append(indent + cont)

            # --------------------------------------------------
            # DEFAULT (NO WRAP) — what you already had working
            # --------------------------------------------------
            else:
                cmd_cut = raw_cmd[:available]

                if use_color:
                    cmd_final = f"{fg(0x5287d6)}{cmd_cut}{RESET}"
                else:
                    cmd_final = cmd_cut

                line = base + cmd_final

                rendered_pids.add(node.pid)
                lines.append(line)

            # ------------------------------------------
            # CHILDREN
            # ------------------------------------------
            children_nodes = []
            prune = args.prune or 0

            for child in children_map.get(node.pid, []):

                if child.pid not in visible_pids:
                    continue

                if prune == 0:
                    children_nodes.append(child)
                    continue

                if prune >= 1 and is_boring(child):
                    continue

                children_nodes.append(child)

            children_nodes = sorted(
                children_nodes,
                key=lambda p: (
                    get_sort_value(p),
                    (p.command or "").lower()
                ),
                reverse=reverse
            )

            # ------------------------------------------
            # NEW: Filter children BEFORE iterating
            # ------------------------------------------
            if not args.with_parents:
                children_nodes = [c for c in children_nodes if c.pid in visible_pids]

            filtered_children = [
                c for c in children_nodes
                if c.pid in visible_pids
            ]

            for idx, child in enumerate(filtered_children):

                # ------------------------------------------
                # Traversal rule
                # ------------------------------------------
                if not args.with_parents:
                    # Strict mode: do not traverse invisible nodes
                    if child.pid not in visible_pids:
                        continue

                child_is_last = (idx == len(children_nodes) - 1)

                base_prefix = ""
                for is_pipe in levels:
                    base_prefix += pipe if is_pipe else space

                render(
                    child,
                    levels + [not child_is_last],
                    child_is_last,
                    depth + 1,
                    parent_pid_col
                )

        for i, root in enumerate(roots):
            render(root, [], i == len(roots) - 1, 1, 0)

        tree_data = build_tree_structure()
        node_count = count_nodes(tree_data)

        return lines, len(rendered_pids)