# Security Policy

## Supported Versions

Only the latest release receives security fixes. We do not backport patches to older versions.

## Reporting a Vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities.

Report vulnerabilities privately via [GitHub Security Advisories](https://github.com/earthobservations/wetterdienst/security/advisories/new) or by emailing **benjamin.gutzmann@pm.me**.

Include as much detail as possible:

- Description of the vulnerability and potential impact
- Steps to reproduce or proof-of-concept
- Affected version(s)

We aim to acknowledge reports within **72 hours** and provide a resolution timeline within **7 days**.

## Scope

This project is a data-fetching library and REST API. Relevant areas include:

- Remote code execution or command injection via user-supplied input
- Dependency vulnerabilities (please check [Dependabot alerts](https://github.com/earthobservations/wetterdienst/security/dependabot) first)
- REST API authentication or data exposure issues

Out of scope: vulnerabilities in upstream data provider services (DWD, NOAA, etc.).
