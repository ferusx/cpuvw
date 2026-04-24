# config.py

# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 Markus Johnsson

import os


CONFIG_PATH = os.path.expanduser("~/.config/cpuvw/config.toml")

DEFAULT_TOML = """\
# ==========================================
# CPUVW Configuration File
# ==========================================

# Minimum CPU% required to consider a process active
# Example:
#   1.0  → very sensitive
#   5.0  → stricter filtering
cpu_threshold = 1.0

# ------------------------------------------
# State display limits
# ------------------------------------------

[states.IDLE]
min = 0
max = 3

[states.LIGHT]
min = 0
max = 4

[states.MODERATE]
min = 0
max = 6

[states.HEAVY_LOCALIZED]
min = 0
max = 6

[states.HEAVY_DISTRIBUTED]
min = 0
max = 10

# ------------------------------------------
# Behavior toggles
# ------------------------------------------

# Include low CPU processes to fill the table
show_low_cpu = false
"""