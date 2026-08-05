# Security Policy

## Reporting a Vulnerability

Please open a private security advisory if you discover a security issue.

## Security Review

This project underwent an AI security review in August 2026 (v1.1 release).

- Scope: source code + packaged Windows executable
- Outcome: No critical or high severity issues remained after remediation in v1.2.0. Medium findings around unbounded remote content, artwork URL trust, and release/supply-chain verifiability were addressed without Authenticode signing (checksums, CycloneDX SBOM, and build provenance are published instead).
