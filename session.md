# Wetterdienst: Fast, Unified Access to Open Weather Data with Polars

**2026-04-15 · 10:15 (Europe/Berlin) · Titanium [2nd Floor]**

---

## Problem

Accessing weather data means wrestling with inconsistent APIs, formats, and units—slowing down
data engineering and making pipelines hard to reproduce.

## Solution

Wetterdienst is a Python library providing a unified, Polars-first interface to multiple open
weather services (DWD, ECCC, EA, NOAA/NWS, Geosphere Austria, IMGW, Eaufrance, WSV, and more).
It standardizes request patterns, returns tidy long-format data in SI units, and handles caching,
timezones, and retries—so teams can focus on analysis instead of plumbing.

## Core Concepts

- **Polars-first** — All data operations use Polars (v1.15+); pandas supported for some I/O
- **Declarative request pattern** — Provider → stations → values; tidy/long output by default
- **Sensible defaults** — UTC timestamps, SI units, humanized parameter names
- **Reliability** — Disk-based caching via diskcache, stamina-based retries, timezone handling
- **Provider architecture** — Consistent interfaces across DWD, ECCC, EA, NOAA/NWS, Geosphere, IMGW, Eaufrance, WSV, and
  more
- **Multiple interfaces** — Python API, CLI, and REST

---

## Outline

1. **Introduction**
2. **Journey** — How Wetterdienst came to life
3. **Wetterdienst** — Architecture, concepts, and request patterns
4. **Value** — What wetterdienst offers you, me and everyone else
5. **Demo** — Live: station discovery, timeseries retrieval, station metadata, climate stripes and more via app

---

## Target Audience

Data engineers, scientists, and platform teams who need reliable weather data for analytics,
ML, and operations.

## Prerequisites

Basic Python and DataFrame experience (Polars or pandas); familiarity with ETL/ML pipelines helpful.

## Key Takeaways

- A unified, Polars-first workflow to access and normalize open weather data
- Practical patterns for station discovery, timeseries retrieval, unit conversion, and caching
- How to integrate Wetterdienst via Python, CLI, and REST, and export to common formats and databases

---

## Links

|                 |                                                                      |
|-----------------|----------------------------------------------------------------------|
| 📦 **Repo**     | https://github.com/earthobservations/wetterdienst                    |
| 📖 **Docs**     | https://wetterdienst.readthedocs.io/                                 |
| 🌐 **App**      | https://wetterdienst.eobs.org/                                       |
| 💡 **Examples** | https://github.com/earthobservations/wetterdienst/tree/main/examples |