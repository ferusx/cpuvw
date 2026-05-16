# CPUVw Changelog

## 0.1 - Initial Commit [unreleased]

### Added
- CPU state detection (IDLE, LIGHT, MODERATE, HEAVY)
- Localized vs distributed load detection
- Moderate split via --allow-mod-local-dist
- Dual-column Activity Overview (Dominant Source + Top Contributors)
- --analyze mode with structured system analysis
- Full STAT interpretation (R, S, D, Z, T, N, +, C)
- Analyzer-specific human-readable STAT descriptions
- Color themes (standard + light mode)
- Narrative-style system reporting

### Improved
- Column alignment and spacing in contributor display
- Reduced redundancy in CPU-bound reporting
- Consistent visual hierarchy and formatting

### Notes
- Focus on interpretive output rather than raw metrics
- Foundation laid for future intent detection and multi-core awareness

---

## v0.3.0

## [Unreleased]

### Added
- Live logical CPU monitor (`--show-logical-cpu avg`)
- Real-time per-core sampling with smooth percentage output
- Keyboard controls for live mode:
  - `q`, `Q`, `ESC` to exit
  - graceful `Ctrl+C` handling
- Config generation flag: `--save-config` (safe template output)
- Expanded and structured configuration system:
  - `[cpu]` thresholds
  - `[cores]` sampling settings
  - `[output]` display behavior
  - `[table]` rendering controls
  - `[behavior]` advanced toggles
- Configurable core update frequency (`-F` / `--core-update-frequency`)


### Changed
- Replaced static per-core snapshot with time-based sampling for accurate readings
- Refactored core rendering into dedicated renderer (`_render_core_grid`)
- Unified config loading via `load_config()` (removed duplicate logic)
- Improved CLI flag system with expanded short options (A–Z range)
- Renamed config keys for consistency:
  - `analysis_enabled` → `show_analysis`
  - `tree_view_enabled` → `show_tree_view`
  - `invert_headers` → `invert_header`

### Removed
- Deprecated `cpu_insights` module (unused stubs)
- Removed `--banner` flag and related method
- Eliminated duplicate config loading code paths


### Fixed
- Clean exit from live loop (no duplicate frame on exit)
- Correct handling of `KeyboardInterrupt`
- Stabilized per-core percentage calculations
- Fixed TOML inconsistencies (boolean casing, stray entries)


### Notes
- Config file format has evolved — users are encouraged to regenerate using:
  `cpuvw --save-config`


---

## [0.4.0] - 2026-05-01

## [Unreleased]

### Added
- Full configuration system via `~/.config/cpuvw/config.toml`
- New `[cpu]`, `[table]`, and `[filter]` configuration sections
- Tree view mode (`--tree`) with glyph styling support
- Configurable glyph styles (`--glyph-style {1,2,3}`)
- Extended filtering system:
  - `--filter-command`
  - `--filter-user`
  - `--filter-stat` (multi-character matching, order-independent)
  - `--filter-pid`
  - `--filter-cpu`
- `[configurable]` indicator added to CLI help output
- Help footer referencing CONFIGURATION and FILES sections in the man page


### Changed
- Swapped semantics of:
  - `--cpu-threshold` → now controls CPU **state classification**
  - `--threshold` → now controls **process visibility filtering**
- Renamed internal config keys:
  - `threshold` → `cpu_threshold`
  - Introduced `cpu_state_threshold`
- Refactored threshold resolution logic for correctness and clarity
- Improved STAT filtering behavior to support combinations like:
  - `Is`, `R+`, `Ss`, `RNC`, etc. (order-independent)


### Fixed
- Critical bug where `cpu_state_threshold` from config was ignored
- Scope bug where `threshold` was defined too late in execution flow
- Incorrect fallback usage mixing state threshold and table threshold
- Broken analyzer linkage due to outdated variable references
- Tree view `--prune` not applying correctly
- `--filter-pid` and `--filter-cpu` type mismatch issues
- Case-sensitivity bug in STAT filtering


### Removed
- Deprecated `--top` flag and related logic
- Removed `[advanced]` configuration section
- Redundant threshold aliases and duplicate config handling
- Unsafe variable remapping between analyzer and CLI layer


### Internal
- Restored original execution flow for threshold-based filtering
- Clean separation of:
  - CPU state classification
  - Process visibility filtering

---

## [0.5.0] - 2026-05-03

## [Unreleased]

### Added
- Tree mode now includes a summary line:
  - `[Summary] Nodes displayed: N`
- Implemented accurate visible node counting in tree view
- Introduced robust pruning integration (`--prune`) with correct traversal logic

### Improved
- Tree rendering system fully rebuilt and stabilized:
  - Correct glyph alignment
  - Proper diamond (◆) placement for leaf nodes
  - Fixed branch-to-node connection logic
- Output is now fully pipe-safe:
  - Removed ANSI leakage in non-color output
  - Clean behavior with `less`, `more`, `grep`, and other UNIX tools
- Consistent `.rstrip()` handling applied at output boundaries
- Analyzer output formatting cleaned and stabilized
- Side-by-side layout (Activity Overview) no longer produces trailing whitespace
- Column headers simplified (removed inverted header system)
- All `--filter-pid`, `--filter-user`, etc, flags, were consolidated into one flag `--filter subcategory arg` with sub commands instead, i.e. `--filter pid PID`, and `--filter user USER`, etc

### Removed
- Removed `--invert-header` feature and all related ANSI background logic
- Removed partially implemented `--top` flag and all dependent logic
- Removed duplicate and unused rendering variables (`branch_width`, `base_len`, etc.)
- Removed redundant ANSI formatting in colorless mode
- Removed all the obsolete `--filter-*` flags

### Fixed
- Fixed double-diamond (◆◆) rendering bug in tree mode
- Fixed misplaced diamond glyph (`◆──` → `──◆`)
- Fixed incorrect glyph spacing and alignment issues
- Fixed `--prune` having no effect due to missing render logic
- Fixed `--with-parents` filtering inconsistencies
- Fixed incorrect node count in summary (was counting hidden nodes)
- Fixed ANSI escape sequences leaking into piped output
- Fixed wrapping issues in pagers (`less` / `more`) caused by trailing spaces
- Fixed analyzer crash due to leftover `args.top` reference
- Fixed inconsistent color application in analysis output

### Internal
- Restored critical guard logic in `render()`:
  - user filtering
  - depth limiting
  - recursion safety
- Reintroduced proper child filtering pipeline with pruning
- Standardized color handling via `use_color` checks
- Improved separation between formatting and output layers

---

## [0.6.0] - 2026-05-11

## [Unreleased]

## Analyzer & Topology Overhaul

### Major Additions

- Added CPU topology awareness
  - Physical cores and logical CPUs are now treated as separate analytical layers
  - SMT sibling threads are grouped into real physical-core interpretations
  - Analyzer terminology and telemetry were upgraded to reflect actual hardware structures

- Added `--show-physical-core`
  - Introduced dedicated physical-core telemetry view
  - Added topology-aware physical utilization analysis
  - Physical core utilization now derives from grouped logical siblings

- Added multi-depth analyzer modes
  - `--analyze`
  - `--analyze more`
  - `--analyze deep`
  - Observation windows and report depth now scale cleanly with analysis mode

- Added `TemporalHistory`
  - Introduced longitudinal observation tracking across analyzer samples
  - Added:
    - mean CPU
    - min/max CPU
    - CPU delta
    - dominant persistence
    - workload continuity tracking

- Added `--pager`
  - Analyzer reports can now be viewed through `less -R`
  - ANSI colors preserved
  - Fully functional over SSH and local terminals
  - Uses true shell pipeline execution for native UNIX pager behavior


### Analyzer Improvements

- Reworked analyzer synchronization model
  - CPU state classification now occurs AFTER the observation window completes
  - Eliminated stale analyzer states during active workloads

- Upgraded analyzer hardware interpretation
  - Physical cores are now the primary hardware interpretation layer
  - Logical CPUs are now treated as advanced scheduler telemetry

- Added Observation Summary section
  - Introduced compact temporal summary metrics:
    - mean CPU
    - CPU range
    - CPU delta
    - dominant persistence

- Added Temporal Observations section
  - Analyzer now performs restrained temporal workload interpretation
  - Added stability and fluctuation observations derived from longitudinal telemetry

- Upgraded STAT interpretation system
  - Analyzer now extracts STAT flags from both dominant source and top contributors
  - Added support for:
    - upper-case and lower-case BSD/Linux STAT flags
    - scheduler and session indicators
    - multithreading and memory-lock indicators
  - Expanded explanations for:
    - `I`
    - `L`
    - `W`
    - `X`
    - `s`
    - `l`
    - `t`
    - `<`
    - and others

- Upgraded `--stat-info`
  - Unified STAT descriptions with analyzer terminology
  - Expanded visible state interpretation coverage

- Reworked logical CPU presentation
  - Analyzer now presents physical-core interpretation instead of misleading logical-thread terminology
  - Logical CPU telemetry remains available as a deeper scheduler-level analysis layer


### Telemetry & Core View Improvements

- Reworked `--show-logical-cpu`
  - Improved topology handling
  - Improved inactive-core rendering
  - Added cleaner utilization presentation
  - Improved physical/logical distinction

- Improved core activity classification
  - Saturated
  - Active
  - Low
  - Idle

- Added topology-aware core grouping logic


### UX & Output Improvements

- Added pager-friendly analyzer behavior
- Improved analyzer visual hierarchy
- Improved section ordering and report flow
- Improved contributor/stat synchronization
- Reduced stale telemetry effects
- Improved ANSI pager compatibility
- Improved SSH analyzer usability


### Documentation

- Updated manual page
- Expanded analyzer mode documentation
- Expanded STAT documentation
- Added topology-related terminology clarification
- Added pager usage documentation


### Internal Architecture

- Introduced layered analyzer composition model
- Improved separation between:
  - temporal telemetry
  - topology interpretation
  - process attribution
  - report rendering
- Reduced ambiguity between logical CPUs and physical cores
- Improved analyzer extensibility for future deep telemetry features

---

## [0.7.0] - 2026-05-16

## [Unreleased]

### Added
- Introduced **CPUForge**, a dedicated CPU workload generation and behavioral stress-testing utility for CPUVw
- Added multiple workload generation profiles to CPUForge:
  - `stable`
  - `bursty`
  - `random`
  - `localized`
  - `distributed`
  - `rotating`
  - `oscillating`
  - `microspikes`
  - `decay`
  - `chaotic`
- Added `--workers` support in CPUForge for spawning configurable multi-process workloads
- Added configurable workload percentages via `--load`
- Added infinite and timed execution support
- Added `--list` option for displaying available workload profiles
- Added distributed execution pressure scheduling
- Added rotating CPU pressure behavior
- Added oscillating/ramping workload behavior
- Added microspike burst scheduling
- Added workload decay simulation
- Added chaotic instability scheduling
- Added reusable timing helpers for workload scheduling
- Added scheduler abstraction layer for future workload expansion
- Added machine-relative `SYS%` CPU metric across analyzer and process tables
- Added system-relative CPU usage display to:
  - Dominant Source
  - Top Contributors
  - regular process table
- Added contextual workload interpretation improvements in analyzer conclusions
- Added new conditional workload distribution entries based on actual physical core utilization ratios
- Added active physical core spread analysis (`spread_ratio`)
- Added dynamic execution pressure interpretation:
  - concentrated execution
  - moderate distribution
  - broad distribution
  - near full-core pressure distribution

### Improved
- Analyzer semantic consistency significantly improved
- CPUVw now separates:
  - execution occupancy (`CPU%`)
  - machine-relative utilization (`SYS%`)
- Dominant Source presentation redesigned:
  - execution occupancy now shown directly beside process name
  - machine-relative usage moved into contextual sub-line
- Top Contributors table redesigned for semantic consistency:
  - `CPU%` restored as primary execution metric
  - `SYS%` added as contextual machine-relative metric
- Regular process table redesigned:
  - replaced redundant `TOTAL%` column with meaningful `SYS%`
- Analyzer output now aligns visually and semantically across:
  - Dominant Source
  - Top Contributors
  - process table
  - behavioral observations
- Distributed workload analysis wording improved substantially
- Physical core distribution logic now reacts dynamically to actual spread conditions
- Deep mode temporal observations became more responsive to unstable workloads
- Contributor stability testing dramatically improved using CPUForge stress scenarios
- Analyzer workload testing capabilities massively expanded through controlled synthetic CPU behavior
- CPUForge shutdown behavior stabilized and cleaned up
- Internal analyzer semantics clarified:
  - `CPU%` now treated as execution pressure
  - `SYS%` treated as machine-relative contextual usage

### Changed
- Replaced `TOTAL%` process table column with `SYS%`
- Reworked analyzer CPU interpretation philosophy:
  - `CPU%` remains primary scheduler/execution metric
  - `SYS%` acts as contextualized machine impact metric
- Adjusted Top Contributors column ordering:
  - `CPU%` now visually prioritized over `SYS%`
- Reworked Dominant Source output structure for improved readability and semantic hierarchy
- Temporal observation wording updated:
  - unstable workloads no longer described with misleading “high consistency” phrasing
- Reworked physical core distribution descriptions to avoid falsely negative wording
- Analyzer behavior now reacts more naturally to distributed synthetic workloads

### Fixed
- Fixed multiple CPU analyzer semantic inconsistencies exposed through synthetic workload testing
- Fixed misleading “unevenly distributed” analysis appearing during broad multi-core utilization
- Fixed analyzer contradictions between:
  - Dominant Source
  - Observation Summary
  - Top Contributors
- Fixed incorrect visual hierarchy between `CPU%` and machine-relative usage metrics
- Fixed CPUForge multiprocessing shutdown deadlocks
- Fixed CPUForge worker shutdown race conditions
- Fixed repeated multiprocessing join assertion failures:
  - `can only join a child process`
- Fixed hanging worker processes during Ctrl+C shutdown
- Fixed atexit multiprocessing shutdown issues
- Fixed inconsistent workload interpretation under bursty workloads
- Fixed several analyzer conditional paths that produced repetitive output across unrelated workload behaviors
- Fixed semantic mismatch between analyzer conclusions and observed physical core utilization

### Internal
- Introduced physical-core-aware workload interpretation model
- Introduced spread-ratio-based execution analysis
- Improved analyzer behavioral categorization architecture
- Expanded conditional analysis branching significantly
- Refined analyzer semantic layering:
  - immediate execution behavior
  - machine-relative impact
  - temporal behavior
- CPUForge architecture modularized into:
  - scheduler
  - timing
  - workers
  - utilities
- Improved workload simulation framework for future expansion and benchmarking
- Established CPUForge as a long-term analyzer validation framework for CPUVw
- Large-scale analyzer validation effort initiated using controlled synthetic workloads

---