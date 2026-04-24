# CPUVw

**CPUVw** is a command-line CPU analysis tool focused on understanding system behavior — not just displaying raw metrics.

## Status

This project is currently under active development.

Features are being added and refined continuously. Output format and functionality may change as the tool evolves.

## Purpose

Unlike traditional tools such as `top` or `htop`, CPUVw aims to:

- Interpret CPU activity
- Explain system behavior
- Provide human-readable analysis
- Detect workload patterns

## Current Features

- CPU state detection (IDLE, LIGHT, MODERATE, HEAVY)
- Localized vs distributed load analysis
- `--analyze` mode with narrative system insights
- STAT interpretation (R, S, D, Z, T, N, +, C)
- Dual-column activity overview
- Truecolor terminal output

## Planned Features

- Workload intent detection (e.g. stress test, compilation, etc.)
- Multi-core awareness and saturation reporting
- Historical comparison and trend analysis

## Usage

```bash
python cpuvw.py --analyze
```

## Notes
This tool is designed primarily for UNIX-like systems (FreeBSD focus).
