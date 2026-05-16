# temporal_history.py

# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 Markus Johnsson


from collections import deque
from time import time

# Local imports
from utils import get_cpu_topology

# ****************************************************************************
# Class: TemporalHistory
# ****************************************************************************
class TemporalHistory:
    """
    Rolling temporal history buffer for CPU analyzer observations.

    Purpose:
        Stores recent analyzer snapshots so cpuvw can later evaluate:

            - workload stability
            - state persistence
            - contributor churn
            - dominant process continuity
            - CPU variance over time

    Notes:
        This class intentionally performs NO interpretation yet.
        It only stores historical observations safely and consistently.
    """

    # ----------------------------------------------------------------------
    # Method: __init__
    # ----------------------------------------------------------------------
    def __init__(self, max_samples=15):

        self.history = deque(maxlen=max_samples)

    # ----------------------------------------------------------------------
    # Method: add_snapshot
    # ----------------------------------------------------------------------
    def add_snapshot(
        self,
        total_cpu,
        state,
        dominant_pid,
        dominant_cpu,
        top_pids,
        distribution_type,
    ):
        """
        Add a new temporal observation snapshot.
        """

        snapshot = {
            "timestamp": time(),
            "total_cpu": total_cpu,
            "state": state,
            "dominant_pid": dominant_pid,
            "dominant_cpu": dominant_cpu,
            "top_pids": top_pids,
            "distribution_type": distribution_type,
        }

        self.history.append(snapshot)

    # ----------------------------------------------------------------------
    # Method: get_history
    # ----------------------------------------------------------------------
    def get_history(self):
        """
        Return all stored temporal snapshots.
        """

        return list(self.history)

    # ----------------------------------------------------------------------
    # Method: clear
    # ----------------------------------------------------------------------
    def clear(self):
        """
        Clear all temporal history.
        """

        self.history.clear()

    # -----------------------------------------------------------------
    # Method: get_summary
    # -----------------------------------------------------------------
    def get_summary(self):
        """
        Generate a lightweight temporal summary from collected snapshots.
        """

        if not self.history:
            return {}

        total_values = [
            s["total_cpu"]
            for s in self.history
        ]

        dominant_pids = [
            s["dominant_pid"]
            for s in self.history
            if s["dominant_pid"] is not None
        ]

        topology = get_cpu_topology()

        physical_core_count = len(
            topology["physical_cores"]
        )

        normalized_values = [
            value / physical_core_count
            for value in total_values
        ]

        mean_cpu = (
                sum(normalized_values)
                / len(normalized_values)
        )

        min_cpu = min(normalized_values)
        max_cpu = max(normalized_values)

        cpu_delta = max_cpu - min_cpu

        # ---------------------------------------------------------
        # Dominant PID persistence
        # ---------------------------------------------------------
        dominant_persistence = 0.0

        if dominant_pids:

            most_common = max(
                set(dominant_pids),
                key=dominant_pids.count
            )

            persistence_ratio = (
                dominant_pids.count(most_common)
                / len(dominant_pids)
            )

            dominant_persistence = persistence_ratio * 100.0

        return {
            "sample_count": len(self.history),
            "mean_cpu": mean_cpu,
            "min_cpu": min_cpu,
            "max_cpu": max_cpu,
            "cpu_delta": cpu_delta,
            "dominant_persistence": dominant_persistence,
        }