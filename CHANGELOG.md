# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.1.0] — 2026-03-16

### Added
- Main menu with 3 separate flows: split credits, year-end estimate, or both
- Year-end refund / underpayment estimator based on YTD figures from ros.ie
- Option 2 skips hours/rate inputs — only name and YTD needed for refund
- Input validation with clear WARNING messages for invalid entries
- 44 unit tests covering all calculation logic, validated against real P21 data
- `0` option to quit without being asked to run again
- Press Enter confirmation before showing results

### Changed
- `calculate_tax_summary()` split into `calculate_split()` and `calculate_refund()`
- `TaxSummary` split into `SplitResult` and `RefundSummary`

---

## [1.0.0] — 2025-05-24

### Added
- Initial release
- Proportional split of PAYE rate band, tax credits and USC bands across multiple jobs
- Proportion based on estimated annual income (hours/week × hourly rate × 52)