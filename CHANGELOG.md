# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/2.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.3] - 2026-07-27

## Added

- Added Spark tab
  - Contains extra analysis completed with a Scala/Apache Spark batch pipeline
  - Instructions to build Spark data available on the readme.md

## [0.1.2] - 2026-07-27

## Added

- Dataset analysis with Spark + Scala

## [0.1.1] - 2026-07-27

## Added

- Anomalies
  - Flags lines that are currently disrupted more than their historical reliability.
- Patterns
  - Shows the historical rates of unplanned disruptions, excluding scheduled closures.

## Removed

- Footfall
  - TfL data is not as consistently available for Footfall compared to other indicators.

## [0.1.0] - 2026-07-24

### Added

- Improved Journey Planner
  - Includes interactive map showing all lines
  - Clicking stations shows data for its line and lets you set a journey
- Reliability page to view historical line data
- New sidebar implemented

### Changed

- Planned journeys now estimate time taken to complete