# constants.py

# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 Markus Johnsson


# ---------------------------------------------------------------------
# Column Width Constants
# ---------------------------------------------------------------------
#
# These constants define the fixed-width layout of the table output.
# Each value represents the number of characters allocated to a column.
#
# The goal is to:
#   - Ensure consistent alignment across all rows
#   - Prevent shifting when values change in length
#   - Maintain readability in typical terminal widths
#
# NOTE:
#   - These widths are tuned for standard terminal sizes (~80–120 columns)
#   - The COMMAND column is dynamic and consumes remaining space
#   - Adjust carefully — small changes ripple through the entire layout
#

PID_W   = 7   # Process ID
USER_W  = 8  # Username (owner of process)
STAT_W  = 5  # State
CPU_W   = 6   # CPU usage percentage
TOT_W   = 7   # Total CPU percentage
THR_W   = 5   # Number of threads
CMD_W   = 40  # Command name



THRESHOLD_LIGHT = 1.0  # process table threshold


# ---------------------------------------------------------------------
# STAT_MEANINGS
# ---------------------------------------------------------------------
STAT_MEANINGS = {
    "R": "Running or ready to run",
    "S": "Sleeping (waiting for event)",
    "D": "Waiting on I/O (uninterruptible)",
    "Z": "Zombie process (terminated, not reaped)",
    "T": "Stopped (job control or debug)",

    "N": "Low priority (nice)",
    "+": "Foreground process",
    "C": "CPU-bound (actively consuming CPU)",
}


# ---------------------------------------------------------------------
# TRUECOLOR (24-BIT) SYSTEM
# ---------------------------------------------------------------------
#
# Supports full RGB colors using hex strings (#RRGGBB)
#
# Usage:
#   fg("#ffaa00")
#   bg("#0011cc")
#   color("#ff0000", "#000000")
#
# Terminal must support truecolor (most modern ones do)
#

RESET = "\033[0m"


# -------------------------
# Internal helper
# -------------------------

def _hex_to_rgb(value):
    if isinstance(value, int):
        r = (value >> 16) & 0xFF
        g = (value >> 8) & 0xFF
        b = value & 0xFF
        return r, g, b

    if isinstance(value, str):
        value = value.strip()

        if value.startswith("#"):
            value = value[1:]

        if len(value) != 6:
            raise ValueError(f"Invalid hex color: {value}")

        r = int(value[0:2], 16)
        g = int(value[2:4], 16)
        b = int(value[4:6], 16)
        return r, g, b

    raise TypeError("Color must be int or hex string")

# -------------------------
# Foreground
# -------------------------

def fg(value):
    r, g, b = _hex_to_rgb(value)
    return f"\033[38;2;{r};{g};{b}m"

# -------------------------
# Background
# -------------------------

def bg(value):
    r, g, b = _hex_to_rgb(value)
    return f"\033[48;2;{r};{g};{b}m"

# -------------------------
# Combined
# -------------------------

def color(fg_val=None, bg_val=None):
    seq = ""

    if fg_val is not None:
        r, g, b = _hex_to_rgb(fg_val)
        seq += f"\033[38;2;{r};{g};{b}m"

    if bg_val is not None:
        r, g, b = _hex_to_rgb(bg_val)
        seq += f"\033[48;2;{r};{g};{b}m"

    return seq

# SOME ANSI CONSTANTS FOR FORMATTING
UNDERLINE   = "\033[4m"  # Underline the text
BLINK       = "\033[5m"  # Make text blink
BOLD        = "\033[1m"  # Make text bold


# ---------------------------------------------------------------------
# CPU Threshold Constant
# ---------------------------------------------------------------------
#
# Default threshold used to determine whether subtree CPU usage should
# be displayed in tree mode when no explicit flags are provided.
#
# Behavior:
#   - Nodes with subtree CPU above this value will show CPU usage
#   - Nodes below this threshold will hide CPU info (unless --cpu-all)
#
# Purpose:
#   - Reduce visual noise in large trees
#   - Highlight only meaningful CPU activity by default
#
# Notes:
#   - Overridden by:
#       --cpu-all        → always show CPU
#       --cpu-threshold  → user-defined threshold
#

DEFAULT_CPU_THRESHOLD = 1.0  # Minimum CPU (%) required to display subtree usage

# ---------------------------------------------------------------------
# Tree Glyph Styles
# ---------------------------------------------------------------------
#
# Defines visual styles for rendering the process tree structure.
# Each style controls how branches, connectors, and optional markers
# appear in tree mode.
#
# Styles:
#
#   "1" → Classic (default)
#          Clean UTF-8 box-drawing style, similar to `tree` or `pstree`
#
#   "2" → ASCII
#          Compatible fallback for terminals without Unicode support
#
#   "3" → Fancy
#          Enhanced visual style with a leaf marker for terminal nodes
#
# Elements:
#
#   branch → Connector for intermediate child nodes
#   last   → Connector for the final child in a branch
#   pipe   → Vertical continuation for nested levels
#   space  → Padding where no pipe is drawn
#   leaf   → Optional marker for leaf nodes (style-dependent)
#
# Notes:
#
#   - Selected via the --glyph-style flag
#   - Defaults to style "1" if not specified
#   - Styles may override spacing for visual alignment
#   - "leaf" is optional and only used if defined
#
GLYPH_STYLES = {
    "1": {  # classic
        "branch": "├─ ",
        "last": "└─ ",
        "pipe": "│  ",
        "space": "   ",
    },
    "2": {  # ascii
        "branch": "|- ",
        "last": "`- ",
        "pipe": "|  ",
        "space": "   ",
    },
    "3": {  # fancy
        "branch": "├─ ",
        "last": "└─ ",
        "leaf": "◆ ",
        "pipe": "│   ",
        "space": "    ",
    }
}
