# config.py

# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 Markus Johnsson

import os

try:
    import tomllib
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
# threshold {number}
#         Sets the minimum % for CPU usage for processes
#         to be shown.
# cpu_threshold {number}
#         Sets min % for when CPU STATE triggers one of
#         the HEAVY_* modes, i.e. a setting of 50, would
#         trigger a HEAVY_* state at 50 CPU% rather than
#         at 70%, which is the default limit. 
# heavy/active/low {number}
#         Thresholds for CPU state classification (%). 
#         These values determine when the system is 
#         considered:
#           - HEAVY (>= heavy)
#           - MODERATE (>= active)
#           - LIGHT (>= low)
#           - IDLE (< low)
# ----------------------------------------------------

[cpu]
threshold = 1.0          # Min CPU% for procs to show
cpu_threshold = 70       # Min CPU% to trigger heavy state
heavy = 70               # Min value for HEAVY state
active = 40              # Min value for MODERATE state
low = 20                 # Min value for LIGHT state

# ----------------------------------------------------
# This section contains special settings that relates
# to the CPU's logical processors.
#
# logical_avg {true|false}
#         Always run in avg mode for --show-logical-cpu
# physical_avg {true|false}
#         Always run in avg mode for --show-physical-core
# logical_interval {seconds}
#         Sampling interval for --show-logical-cpu
# physical interval {seconds}
#         Sampling interval for --show-physical-core
# logical_duration {seconds}
#         Duration for --show-logical-cpu in fast mode
# physical_duration {seconds}
#         Duration for --show-physical-core in fast mode
# ----------------------------------------------------

[cores]
logical_avg = false      # Always run in average mode (logical CPU)
physical_avg = false     # Always run in average mode (physical core)
logical_interval = 0.3   # Sampling interval for logical CPU
physical_interval = 0.3  # Sampling interval for physical core
logical_duration = 2.5   # Duration for logical in fast mode
physical_duration = 2.5  # Duration for physical in fast mode

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

[states.MODERATE_LOCALIZED] # MOD FOCUSED WORKLOAD
min = 0                  # Min value for procs to show
max = 5                  # Max value for procs to show

[states.MODERATE_DISTRIBUTED] # MOD SPREAD WORKLOAD
min = 0                  # Min value for procs to show
max = 8                  # Max value for procs to show

[states.HEAVY_LOCALIZED] # HEAVY FOCUSED WORKLOAD
min = 0                  # Min value for procs to show
max = 6                  # Max value for procs to show

[states.HEAVY_DISTRIBUTED] # HEAVY SPREAD WORKLOAD
min = 0                  # Min value for procs to show
max = 10                 # Max value for procs to show

# ====================================================
# Output behavior
# ====================================================

# ---------------------------------------------------- 
# This section contains general settings for the output.
#
# show_low_cpu {true|false} 
#         Shows processes below 'threshold' (see 'thres-
#         hold' above).
# show_header {true|false}
#         Show/hide the column header for table.
# show_stat_info {true|false}
#         Will display explanations about the STAT column
#         below the process table.
# hide_analysis {true|false}
#         Enable/disable analysis sections above the 
#         table. When false, only the process table is 
#         shown.
# no_table {true|false}
#         Show/hide the process table section at the
#         bottom of the output. This will hide the ent-
#         ire analysis section at the top. 
# use_color {true|false}: 
#         Applies colored output by default. There is no
#         longer a need to use --color flag.
# limit {number}
#         Maximum number of processes to display in the
#         table. 0 = no limit (show all eligible proc-
#         esses). 
#         
#         NOTE: the 0 setting, does not show all proces-
#         ses anyway. If set to 0, the number of proces-
#         ses will follow the  "State display limits" 
#         section just above this one. In order to temp-
#         orarily show a certain number of processes,
#         use the --number option.
# ---------------------------------------------------- 

[output]
show_low_cpu = false       # Show CPU % below 'threshold'
show_header = true         # Show/hide column header
show_stat_info = false     # Info about STAT below table
hide_analysis = false      # Show/hide top sections
no_table = false           # Show/hide process table 
use_color = false          # Apply colored output
limit = 0                  # 0 = no limit

# ====================================================
# Table Behavior
# ====================================================

# ----------------------------------------------------
# show_path {true|false}
#         Show full path in COMMAND column (table).
# wrap_lines {true|false} 
#         Line wrap the paths when show_path is enabled. 
# default_sort {pid|user|cpu|thread|cmd}: 
#         Default sorting order.
# bottom_sort {true|false}
#         Sort the table in descending order.
# show_tree_view {true|false}
#         Enable/disable tree view for processes inst-
#         ead of table view.
# tree_limit {number}
#         default number of processes in tree view.
# with_parents {true|false}
#         Include parents in tree view.
# ----------------------------------------------------

[table]
show_path = false          # Show/hide full path (CMD)
wrap_lines = false         # Line wrap long paths (CMD)
default_sort = "cpu"       # Default sorting order
bottom_sort = false        # Descending sort for table
show_tree_view = false     # View process output in tree
tree_limit = 20            # default number of processes
with_parents = false       # Include parents in tree view
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