# utils.py

# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 Markus Johnsson

from datetime import datetime
import re
import json
import time
import subprocess
from typing import Optional

# Local imports
from models import ProcessInfo, ProcessNode
from constants import RESET, fg, STAT_MEANINGS


# =========================================================
# Function: format_time
# =========================================================
def format_time(raw_time: str) -> str:
    """
    Normalize the ps(1) TIME field into a consistent HH:MM:SS format.

    The TIME column from ps can appear in several slightly different
    formats depending on system state and process lifetime. This helper
    smooths out those differences so the rest of the application can
    rely on a stable representation.

    Supported input formats:

        - MM:SS        → interpreted as 00:MM:SS
        - H:MM:SS      → normalized to HH:MM:SS
        - M:SS.xx      → fractional seconds are discarded

    Any malformed or unexpected input is safely converted to "00:00:00"
    to avoid breaking output formatting.

    Args:
        raw_time (str):
            Raw TIME value as returned by ps.

    Returns:
        str:
            Normalized time string in HH:MM:SS format.
    """
    if not raw_time:
        return "00:00:00"

    # Strip fractional seconds (e.g. "12:34.56" → "12:34")
    raw_time = raw_time.split(".")[0]

    parts = raw_time.split(":")

    try:
        if len(parts) == 2:
            # MM:SS → assume zero hours
            minutes, seconds = map(int, parts)
            return f"00:{minutes:02}:{seconds:02}"

        elif len(parts) == 3:
            # H:MM:SS → normalize to two-digit hours
            hours, minutes, seconds = map(int, parts)
            return f"{hours:02}:{minutes:02}:{seconds:02}"

    except ValueError:
        # Gracefully handle unexpected formats
        pass

    return "00:00:00"

# =========================================================
# Function: format_started_time
# =========================================================
def format_started_time(started_str):
    """
    Format the ps(1) start time into a compact, human-friendly form.

    The raw start time from ps is verbose and not always easy to scan
    in a table. This helper reduces it to a shorter representation
    depending on how recent the process is.

    Behavior:

        - If the process started today:
            → return time as HH:MM

        - If the process started earlier:
            → return weekday and day (e.g. "Mon 06")

        - If parsing fails:
            → return the original string unchanged

    This mirrors how many system tools prioritize recent activity
    while still preserving useful context for older processes.

    Args:
        started_str (str):
            Raw start time string from ps
            (e.g. "Thu Apr  2 17:06:03 2026").

    Returns:
        str:
            Condensed, display-friendly time string.
    """
    try:
        dt = datetime.strptime(started_str, "%a %b %d %H:%M:%S %Y")
        now = datetime.now()

        # Same day → show only time
        if dt.date() == now.date():
            return dt.strftime("%H:%M")

        # Older → show weekday + day
        return dt.strftime("%a %d")

    except ValueError:
        # Fallback: return original string if parsing fails
        return started_str


# =========================================================
# Function: format_started
# =========================================================
def format_started(started: str) -> str:
    """
    Format the ps(1) start time into a compact, ps-like representation.

    The raw start time provided by ps is detailed but not always ideal
    for quick scanning in a table. This helper condenses it into a form
    that mirrors traditional UNIX tools.

    Behavior:

        - If the process started today:
            → return time as HH:MM

        - If the process started earlier:
            → return weekday and day (e.g. "Thu 02")

        - If parsing fails:
            → return the original string unchanged

    Notes:

        - The output intentionally omits the month for older processes
          to keep the column width compact and consistent.
        - An alternative format using month + day (e.g. "Apr 02") can
          be used if a broader time context is preferred.

    Args:
        started (str):
            Raw start time string from ps
            (e.g. "Thu Apr  2 17:06:03 2026").

    Returns:
        str:
            Condensed, display-friendly time string.
    """
    try:
        dt = datetime.strptime(started, "%a %b %d %H:%M:%S %Y")
        now = datetime.now()

        # Same day → show only time
        if dt.date() == now.date():
            return dt.strftime("%H:%M")

        # Older → show weekday + day
        return dt.strftime("%a %d")

    except ValueError:
        # Fallback: return original string if parsing fails
        return started

# =========================================================
# Function: visible_len
# =========================================================
ANSI_ESCAPE = re.compile(r'\x1b\[[0-9;]*m')

def visible_len(s: str) -> int:
    """
    Compute the visible length of a string by ignoring ANSI color codes.

    Terminal output often includes ANSI escape sequences for coloring,
    which increase the string length but do not occupy visible space.
    This helper strips those sequences before measuring length, making
    it safe to use for alignment and width calculations.

    Args:
        s (str):
            Input string, possibly containing ANSI color codes.

    Returns:
        int:
            Length of the string as it would appear in the terminal.
    """
    return len(ANSI_ESCAPE.sub('', s))

# =========================================================
# Function: get_exec_name
# =========================================================
def get_exec_name(cmd: str) -> str:
    """
    Extract the executable name from a command string.

    This helper normalizes both short command names ("comm") and full
    command paths ("command") into a consistent, display-friendly form.

    Examples:

        "/usr/sbin/sshd"           → "sshd"
        "/usr/bin/python script.py" → "python"
        "zsh"                      → "zsh"

    Only the executable portion is returned — any arguments or path
    components are stripped away.

    Args:
        cmd (str):
            Raw command string, possibly including path and arguments.

    Returns:
        str:
            The extracted executable name, or an empty string if input
            is missing.
    """
    if not cmd:
        return ""

    # First token → executable (ignore arguments),
    # then strip any path components
    return cmd.split()[0].split("/")[-1]

# =========================================================
# Function: build_tree_json
# =========================================================
def build_tree_json(roots, children, args):
    """
    Convert a process tree into a JSON-serializable structure.

    This function takes a hierarchical process representation and
    transforms it into a nested dictionary format suitable for JSON
    output or storage. Each process becomes a node containing both
    its own metrics and its relationship to child processes.

    The resulting structure mirrors the tree view used in the CLI,
    but is fully self-contained and safe to serialize.

    Key features:

        - Recursive tree construction
            Builds a nested structure starting from root processes.

        - Subtree CPU aggregation
            Each node includes total CPU usage across all descendants,
            allowing consumers to identify heavy branches.

        - Cycle and duplication protection
            Guards against malformed or unexpected process graphs by:
                * preventing infinite recursion (visited set)
                * ensuring nodes are only emitted once (printed set)

        - Depth limiting
            Respects --tree-depth to restrict how deep the structure
            is expanded.

    Args:
        roots:
            Root processes of the tree (typically PID 1 or top-level entries).

        children:
            Mapping of parent PID → list of child processes.

        args:
            Parsed CLI arguments controlling behavior (e.g. tree depth).

    Returns:
        List[ProcessNode]:
            A list of root nodes, each containing recursively nested children.

    Notes:

        - The structure is fully self-contained and does not rely on
          external references, making it safe for JSON export/import.
        - Subtree CPU values are cached to avoid redundant computation.
        - The function is intentionally defensive, prioritizing stability
          over strict assumptions about process data integrity.
    """

    # Cache prevents recalculating subtree CPU for already visited nodes
    subtree_cache = {}

    # Ensure each PID is only emitted once globally (prevents duplicates)
    printed = set()

    # --------------------------------------------------------------------
    # Method: compute_subtree_cpu
    # --------------------------------------------------------------------
    def compute_subtree_cpu(node, visited):
        if node.pid in visited:
            return 0

        visited.add(node.pid)

        if node.pid in subtree_cache:
            return subtree_cache[node.pid]

        total = node.cpu

        for child in children.get(node.pid, []):
            if child.pid == node.pid:
                continue

            # Use a copy to isolate recursion paths and avoid cross-branch contamination
            total += compute_subtree_cpu(child, visited.copy())

        subtree_cache[node.pid] = total
        return total

    # --------------------------------------------------------------------
    # Method: build_node
    # --------------------------------------------------------------------
    def build_node(node, depth=1, visited=None) -> Optional[ProcessNode]:
        if visited is None:
            visited = set()

        # GLOBAL protection (like tree renderer)
        if node.pid in printed:
            return None

        printed.add(node.pid)

        # Protect against cycles in malformed process graphs
        if node.pid in visited:
            return None

        visited.add(node.pid)

        # Enforce user-defined depth limit (--tree-depth)
        if args.tree_depth is not None and depth > args.tree_depth:
            return None

        cpu_total = compute_subtree_cpu(node, set())

        node_data: ProcessNode = {
            "pid": node.pid,
            "ppid": node.ppid,
            "user": node.user,
            "stat": node.stat,
            "command": node.command,
            "comm": node.comm,
            "cpu": node.cpu,
            "subtree_cpu": cpu_total,
            "mem": node.mem,
            "threads": node.threads,
            "rss_mb": node.rss_mb,
            "started": node.started,
            "time": node.time,
            "children": []
        }

        for child in children.get(node.pid, []):
            if child.pid == node.pid:
                continue  # safety guard

            child_node = build_node(child, depth + 1, visited.copy())
            if child_node:
                node_data["children"].append(child_node)

        return node_data

    return [
        node
        for root in roots
        if root
        for node in [build_node(root, 1, set())]
        if node is not None
    ]


# =========================================================
# Function: load_json_processes
# =========================================================
def load_json_processes(path):
    """
    Load process data from a JSON snapshot and reconstruct ProcessInfo objects.

    This function bridges stored data back into the live processing pipeline.
    It supports both flat and hierarchical (tree-based) JSON formats, allowing
    procvw.py to seamlessly reload previously captured process states.

    Behavior:

        - Accepts JSON generated via --save
        - Supports both:
            * flat lists of processes
            * nested tree structures with children

        - Validates structure before processing
        - Reconstructs ProcessInfo objects for downstream use

    Processing flow:

        1. Load and parse JSON file
        2. Validate structure and required fields
        3. Detect whether data represents a tree or flat list
        4. Walk through entries (recursively if needed)
        5. Rebuild ProcessInfo objects with safe defaults

    Command handling:

        - If --show-path is enabled:
            → use full command path

        - Otherwise:
            → prefer short command name (comm), with fallback
              to extracting from command if missing

    Error handling:

        - Missing file → immediate exit with message
        - Invalid JSON → immediate exit with message
        - Invalid structure → rejected before processing

    Args:
        path (str):
            Path to the JSON snapshot file.

    Returns:
        List[ProcessInfo]:
            Reconstructed list of process objects ready for filtering,
            sorting, and formatting.

    Notes:

        - Tree structures are flattened during loading; hierarchy is
          reconstructed later when needed.
        - The loader is intentionally defensive to support older or
          partially compatible snapshot formats.
    """

    try:
        with open(path, "r") as f:
            data = json.load(f)

    except FileNotFoundError:
        raise SystemExit("Error: File not found")
    except json.JSONDecodeError:
        raise SystemExit("Error: Invalid JSON file")
    except Exception as e:
        raise SystemExit(f"Error loading file: {e}")

    if not isinstance(data, list):
        raise SystemExit("Error: Invalid snapshot format")

    if not data:
        raise SystemExit("Error: Snapshot file is empty")

    required_keys = {
        "pid", "ppid", "user", "command",
        "cpu", "mem", "threads"
    }

    for entry in data:
        validate_node(entry, required_keys)

    is_tree = (
            isinstance(data[0], dict)
            and isinstance(data[0].get("children", []), list)
    )

    processes = []

    def walk(node, parent_pid=None):
        if not node:
            return

        pid = node.get("pid")
        ppid = node.get("ppid", parent_pid or 0)

        command = node.get("command", "")
        comm = node.get("comm", get_exec_name(command))

        processes.append(
            ProcessInfo(
                pid=pid,
                ppid=ppid,
                user=node.get("user", ""),
                stat=node.get("stat", "?"),
                cpu=node.get("cpu", 0.0),
                mem=node.get("mem", 0.0),
                rss_mb=node.get("rss_mb", 0.0),
                started=node.get("started", "N/A"),
                time=node.get("time", "N/A"),
                threads=node.get("threads", 0),
                command=command,
                comm=node.get("comm", get_exec_name(command))
            )
        )

        # Only recurse if tree structure exists
        if is_tree:
            for child in node.get("children", []):
                walk(child, pid)

    #
    if is_tree:
        for root in data:
            walk(root)
    else:
        # flat JSON → no recursion
        for item in data:
            walk(item)

    return processes

# =========================================================
# Function: validate_node
# =========================================================
def validate_node(entry, required_keys):
    """
        Validate the structure of a JSON process node.

        This function ensures that each entry in a loaded snapshot matches
        the expected format before it is converted into ProcessInfo objects.
        It acts as a safety barrier, catching malformed or incomplete data
        early and preventing subtle errors later in the pipeline.

        Validation includes:

            - Ensuring the node is a dictionary
            - Verifying that all required fields are present
            - Recursively validating child nodes (if any)

        If any check fails, execution is immediately stopped with a clear
        error message, as continuing with invalid data would lead to
        unpredictable behavior.

        Args:
            entry (dict):
                A single JSON node representing a process.

            required_keys (set):
                Set of keys that must be present in every node.

        Raises:
            SystemExit:
                If the structure is invalid or required fields are missing.

        Notes:

            - Validation is recursive to support tree-based snapshots.
            - The function is intentionally strict — it prefers to fail fast
              rather than attempt to recover from corrupted input.
    """
    if not isinstance(entry, dict):
        raise SystemExit("Error: Invalid snapshot structure")

    if not required_keys.issubset(entry.keys()):
        raise SystemExit("Error: Snapshot missing required fields")

    # Validate children recursively (if present)
    children = entry.get("children", [])
    if children:
        if not isinstance(children, list):
            raise SystemExit("Error: Invalid children structure")

        for child in children:
            validate_node(child, required_keys)


# =========================================================
# Function: limit_tree_nodes
# =========================================================
def limit_tree_nodes(nodes, limit):
    """
    Limit the total number of nodes in a tree structure.

    This function performs a depth-first traversal of the process tree,
    copying nodes into a new structure until the specified limit is
    reached. Once the limit is hit, traversal stops immediately.

    The goal is to reduce output size while preserving as much of the
    original hierarchy as possible within the constraint.

    Behavior:

        - Traverses nodes depth-first (top-down)
        - Stops as soon as the global node limit is reached
        - Preserves parent-child relationships within the truncated tree

    Args:
        nodes (List[ProcessNode]):
            Root nodes of the process tree.

        limit (int):
            Maximum number of nodes to include in the result.

    Returns:
        List[ProcessNode]:
            A new tree structure containing at most `limit` nodes.

    Notes:

        - The traversal is global, not per-branch — once the limit is
          reached, no further nodes are included anywhere in the tree.
        - Nodes are shallow-copied to avoid mutating the original data.
        - This function is primarily used for JSON output limiting.
    """

    count = 0

    def _walk(node_list):
        nonlocal count
        result = []

        for node in node_list:
            if count >= limit:
                break

            count += 1

            # Continue traversal into children (depth-first)
            new_node = dict(node)
            children = node.get("children", [])

            # Continue traversal into children (depth-first)
            new_node["children"] = _walk(children)
            result.append(new_node)

        return result

    return _walk(nodes)

# =========================================================
# Function: print_summary
# =========================================================
def print_summary(count, use_color, mode="tree"):
    """
    Print a concise summary of the displayed output.

    This function reports how many entries were rendered in the current
    view (tree or table), providing quick feedback when working with
    large or truncated outputs.

    Args:
        count (int): Number of entries displayed.
        use_color (bool): Enable colored output if True.
        mode (str): Output mode ("tree" or "table") to adjust wording.
    """

    if mode == "tree":
        text = f"\n[Summary] Nodes displayed: {count}\n"
    else:
        text = f"\n[Summary] Processes displayed: {count}\n"

    if use_color:
        text = f"{fg(6)}{text}{RESET}"

    print(text)



# -------------------------------------------------------------------------------------
# Function: extract_unique_stats
# -------------------------------------------------------------------------------------
def extract_unique_stats(processes):
    stats = set()

    for p in processes:
        for ch in p.stat:
            if ch.isalpha() or ch in "+":  # include '+'
                stats.add(ch)

    return sorted(stats)

# -------------------------------------------------------------------------------------
# Function: describe_stats
# -------------------------------------------------------------------------------------
def describe_stats(stat_chars):
    lines = []

    for ch in stat_chars:
        meaning = STAT_MEANINGS.get(ch)
        if meaning:
            lines.append(f"{ch} → {meaning}")

    return lines

# -------------------------------------------------------------------------------------
# Function: get_cpu_count
# -------------------------------------------------------------------------------------
def get_cpu_count():
    try:
        result = subprocess.run(
            ["sysctl", "-n", "hw.ncpu"],
            capture_output=True,
            text=True
        )
        return int(result.stdout.strip())
    except:
        return 1

# -------------------------------------------------------------------------------------
# Function: estimate_active_cores
# -------------------------------------------------------------------------------------
def estimate_active_cores(processes):
    """
    Estimate how many cores are actively saturated based on process CPU usage.
    """

    total_cpu = sum(p.cpu for p in processes)

    # Each 100% ≈ 1 core
    active_cores = total_cpu / 100.0

    return active_cores

# -------------------------------------------------------------------------------------
# Function: read_cp_times
# -------------------------------------------------------------------------------------
def read_cp_times():
    result = subprocess.run(
        ["sysctl", "-n", "kern.cp_times"],
        capture_output=True,
        text=True
    )

    values = list(map(int, result.stdout.strip().split()))

    # FreeBSD: 5 values per core
    cores = []
    for i in range(0, len(values), 5):
        cores.append(values[i:i + 5])

    return cores

# -------------------------------------------------------------------------------------
# Function: get_per_core_usage
# -------------------------------------------------------------------------------------
def get_per_core_usage():
    def read_cp_times():
        result = subprocess.run(
            ["sysctl", "-n", "kern.cp_times"],
            capture_output=True,
            text=True
        )

        values = list(map(int, result.stdout.strip().split()))

        # FreeBSD: 5 values per core
        cores = []
        for i in range(0, len(values), 5):
            cores.append(values[i:i + 5])

        return cores

    t1 = read_cp_times()
    time.sleep(1.0)
    t2 = read_cp_times()

    core_usages = []

    for c1, c2 in zip(t1, t2):
        delta = [b - a for a, b in zip(c1, c2)]
        total = sum(delta)

        if total == 0:
            usage = 0.0
        else:
            idle = delta[4]
            usage = (1 - idle / total) * 100

        # SAFE CLAMP (always after assignment)
        usage = max(0.0, min(usage, 100.0))

        core_usages.append(usage)

    return core_usages

# -------------------------------------------------------------------------------------
# Function: classify_cores
# -------------------------------------------------------------------------------------
def classify_cores(usages):
    saturated = sum(1 for u in usages if u >= 80)
    active = sum(1 for u in usages if 40 <= u < 80)
    idle = sum(1 for u in usages if u < 40)

    return saturated, active, idle


# -------------------------------------------------------------------------------------
# Function: print_tree
# -------------------------------------------------------------------------------------
def print_tree(nodes, indent=""):
    for node in nodes:
        print(f"{indent}{node['comm']} ({node['pid']}) [{node['cpu']:.1f}%]")

        if node["children"]:
            print_tree(node["children"], indent + "    ")


# -------------------------------------------------------------------------------------
# Function: is_hidden_process
# -------------------------------------------------------------------------------------
def is_hidden_process(p):
    cmd = (p.comm or "").lower()

    return (
            cmd == "idle"
            or cmd.startswith("[") and "idle" in cmd
            or p.cpu < 0.1
    )

def expand_with_parents(processes, all_processes):
    pid_map = {p.pid: p for p in all_processes}
    expanded = {p.pid for p in processes}

    for p in processes:
        current = p
        while current.ppid in pid_map:
            parent = pid_map[current.ppid]
            if parent.pid in expanded:
                break
            expanded.add(parent.pid)
            current = parent

    return expanded

# -------------------------------------------------------------------------------------
# Function: get_per_core_usage_avg
# -------------------------------------------------------------------------------------
def get_per_core_usage_avg(duration=2.0, interval=0.3):
    start = time.time()

    prev = read_cp_times()
    samples = []

    while time.time() - start < duration:
        time.sleep(interval)
        curr = read_cp_times()

        core_sample = []

        for c1, c2 in zip(prev, curr):
            delta = [b - a for a, b in zip(c1, c2)]
            total = sum(delta)

            if total == 0:
                usage = 0.0
            else:
                idle = delta[4]
                usage = (1 - idle / total) * 100

            usage = max(0.0, min(usage, 100.0))
            core_sample.append(usage)

        samples.append(core_sample)
        prev = curr  # 🔥 CRITICAL

    # average per core
    return [
        sum(sample[i] for sample in samples) / len(samples)
        for i in range(len(samples[0]))
    ]

# -------------------------------------------------------------------------------------
# Function: compute_usage
# -------------------------------------------------------------------------------------
def compute_usage(prev, curr):
    core_usages = []

    for c1, c2 in zip(prev, curr):
        delta = [b - a for a, b in zip(c1, c2)]
        total = sum(delta)

        if total == 0:
            usage = 0.0
        else:
            idle = delta[4]
            usage = (1 - idle / total) * 100

        usage = max(0.0, min(usage, 100.0))
        core_usages.append(usage)

    return core_usages