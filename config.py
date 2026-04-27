# config.py

# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 Markus Johnsson

import os

try:
    import tomllib  # Python 3.11+
except ImportError:
    import tomli as tomllib



CONFIG_PATH = os.path.expanduser("~/.config/cpuvw/config.toml")

DEFAULT_TOML = """\
# ****************************************************
# CPUVW Configuration File
# ****************************************************

# ----------------------------------------------------
# This section contains general settings for the CPU 
# output. 
#
# threshold {n}:
#         Sets the minimum % for CPU usage for processes
#         to be shown.
# heavy/active/low {n}: 
#         Thresholds for CPU state classification (%). 
#         These values determine when the system is 
#         considered:
#           - HEAVY (>= heavy)
#           - MODERATE (>= active)
#           - LIGHT (>= low)
#           - IDLE (< low)
# ----------------------------------------------------

[cpu]
threshold = 1.0         # Min CPU% for procs to show
heavy = 80              # Min value to ...
active = 40             # Min value to ...
low = 20                # Min value to ...

# ----------------------------------------------------
# This section contains special settings that relates
# to the CPU's logical processors.
#
# mode {fast|avg}:
#         fast → instant snapshot (may appear spiky.)
#         avg → sampled over time for smoother values.
# interval {seconds}: 
#         Update frequency for live sampling mode.
# avg_duration {seconds}: 
#         Total duration for averaged sampling
# ----------------------------------------------------

[cores]
mode = "fast"           # Display mode for logical CPUs        
interval = 0.5          # Logical CPU update frequency
avg_duration = 3.0      # Avg duration for ...

# ====================================================
# State display limits
# ====================================================

# ----------------------------------------------------
# The following sections are settings for CPU states.
#
# When the state is at STATE, the table will show between
# min and max processes. E.g. when CPU STATE → MODERATE,
# the table will show 0 to 6 processes, depending on the 
# CPU% load at time. The more CPU% among processes, the 
# greater the chance to see 6 processes in the table.
# ---------------------------------------------------- 
 
[states.IDLE]            # IDLE CPU STATE
min = 0                  # Min value for procs to show
max = 3                  # Max value for procs to show

[states.LIGHT]           # LIGHT CPU STATE
min = 0                  # Min value for procs to show
max = 4                  # Max value for procs to show

[states.MODERATE]        # MODERATE CPU STATE
min = 0                  # Min value for procs to show
max = 6                  # Max value for procs to show

[states.HEAVY_LOCALIZED] # HEAVY_LOCALIZED CPU STATE
min = 0                  # Min value for procs to show
max = 6                  # Max value for procs to show

[states.HEAVY_DISTRIBUTED] # HEAVY_DISTRIBUTED CPU STATE
min = 0                    # Min value for procs to show
max = 10                   # Max value for procs to show

# ====================================================
# Output behavior
# ====================================================

# ---------------------------------------------------- 
# This section contains general settings for the output.
#
# show_low_cpu: 
#         Shows processes below 'threshold' (see 'thres-
#         hold' above)
# use_color: 
#         Applies colored output by default. There is no
#         longer a need to use --color flag.
# show_header: 
#         Show/hide the column header for table.
# show_summary: 
#         Show/hide the summary section below the table 
#         (e.g. "X / Y cores saturated")
# limit:  
#         Maximum number of processes to display in the
#         table. 0 = no limit (show all eligible proc-
#         esses)
# ---------------------------------------------------- 

[output]
show_low_cpu = false       # Show CPU % below 'threshold'
use_color = true           # Apply colored output
show_header = true         # Show/hide column header
show_summary = true        # 
limit = 0                  # 0 = no limit

# ====================================================
# Table Behavior
# ====================================================

# ----------------------------------------------------
# show_path:
#         show full path in COMMAND column (table).
# wrap_lines: 
#         line wrap the paths when show_path is enabled. 
# default_sort {pid|user|cpu|thr|cmd}: 
#         Default sorting order.
# invert_header {white,gray,blue,green,orange,purple,
#                 teal,maroon}: 
#         Inverts the the colors in the column header 
#         and applies a color instead of the regular 
#         white color. 
# show_tree_view {true|false}:
#         Enable/disable tree view for processes inst-
#         ead of table view.
# ----------------------------------------------------

[table]
show_path = false          # Show/hide full path (CMD)
wrap_lines = false         # Line wrap long paths (CMD)
default_sort = "cpu"       # Default sorting order
invert_header = "white"   # Colod invert column header
show_tree_view = false   # View process output in tree

# ====================================================
# Advanced behavior
# ====================================================

[advanced]
# ---------------------------------------------------- 
# This section allows for advanced behavior settings.
#
# allow_moderate_local_dist {true|false}:
#         Splits the MODERATE CPU state into localized
#         and distributed, just like the heavy state.
#         Default, false, is localized only. Like LIGHT.
# show_analysis {true|false}:
#         Enable/disable analysis sections above the 
#         table. When false, only the process table is 
#         shown.
# ---------------------------------------------------- 

allow_moderate_local_dist = true # split MODERATE states
analysis_enabled = true          # Show/hide top sections
"""

# -------------------------------------------------------------------------
# Function: load_config
# -------------------------------------------------------------------------
def load_config():
    # Ensure config directory exists
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)

    # If file doesn't exist → create it
    if not os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "w") as f:
            f.write(DEFAULT_TOML)

    # Load TOML into dict
    with open(CONFIG_PATH, "rb") as f:
        return tomllib.load(f)


# -------------------------------------------------------------------------
# Function: save_config_copy
# -------------------------------------------------------------------------
def save_config_copy():
    generated_path = CONFIG_PATH + ".generated"

    with open(generated_path, "w") as f:
        f.write(DEFAULT_TOML)

    return generated_path