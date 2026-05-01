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
# cpu_threshold {number}:
#         Sets the minimum % for CPU usage for processes
#         to be shown.
# cpu_state_threshold {number}:
#         Sets min % for when CPU STATE triggers HEAVY
#         mode. I.e. a setting of 50, would trigger the
#         HEAVY_X state at 50 CPU% rather than at 70%,
#         which is the default limit. 
# heavy/active/low {number}: 
#         Thresholds for CPU state classification (%). 
#         These values determine when the system is 
#         considered:
#           - HEAVY (>= heavy)
#           - MODERATE (>= active)
#           - LIGHT (>= low)
#           - IDLE (< low)
# ----------------------------------------------------

[cpu]
cpu_threshold = 1.0      # Min CPU% for procs to show
cpu_state_threshold = 70 # Min CPU% to trigger heavy state
heavy = 80               # Min value for HEAVY state
active = 40              # Min value for MODERATE state
low = 20                 # Min value for LIGHT state

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
# show_low_cpu {true|false}: 
#         Shows processes below 'threshold' (see 'thres-
#         hold' above).
# show_header: 
#         Show/hide the column header for table.
# show_stat_info {true|false}:
#         Will display explanations about the STAT column
#         below the process table.
# hide_analysis {true|false}:
#         Enable/disable analysis sections above the 
#         table. When false, only the process table is 
#         shown.
# no_table {true|false}:
#         Show/hide the process table section at the
#         bottom of the output. This will hide the ent-
#         ire analysis section at the top. 
# use_color {true|false}: 
#         Applies colored output by default. There is no
#         longer a need to use --color flag.
# limit {number}:  
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
# show_path {true|false}:
#         Show full path in COMMAND column (table).
# wrap_lines {true|false}: 
#         Line wrap the paths when show_path is enabled. 
# default_sort {pid|user|cpu|thread|cmd}: 
#         Default sorting order.
# bottom_sort {true|false}:
#         Sort the table in descending order.
# invert_header {default,white,gray,blue,green,orange,
#                purple,teal,maroon}: 
#         Inverts the colors in the column header 
#         and applies a color instead of the regular 
#         white color. 
# show_tree_view {true|false}:
#         Enable/disable tree view for processes inst-
#         ead of table view.
# tree_limit {number}
#         default number of processes in tree view.
# ----------------------------------------------------

[table]
show_path = false          # Show/hide full path (CMD)
wrap_lines = false         # Line wrap long paths (CMD)
default_sort = "cpu"       # Default sorting order
bottom_sort = false        # Descending sort for table
invert_header = "default"  # Invert and set column hea-
                           # der colors.
show_tree_view = false     # View process output in tree
tree_limit = 20            # default number of processes

# ====================================================
# FILTER section
# ====================================================
# ----------------------------------------------------
# This section manages filtering in the table's columns
#
# pid {number}
#         Sorts the PID column for the specified number
# user {username}
#         SOrts the user column for the specified name
# stat {abbreviation}
#         Sorts the stat column for given abbreviation
# cpu {float}
#         Searches the CPU% column for processes
#
# ----------------------------------------------------

[filter]
pid = 0
user = ""
stat = ""
cpu = 0.0
command = ""
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