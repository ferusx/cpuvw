# CPUVw Changelog

## [0.1] - Initial Release

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