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