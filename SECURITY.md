# Security Policy

## Reporting a Vulnerability

Please open a private security advisory if you discover a security issue.

## Security Review

This project underwent an AI security review in August 2026 (v1.1 release).

- Scope: source code + packaged Windows executable
- Outcome: No critical or high severity issues were identified. Version 1.2.0 addressed medium findings around unbounded remote content and artwork URL trust, and improved release/supply-chain verifiability with published checksums, a CycloneDX SBOM, and build provenance. The executable is not Authenticode-signed, so these artifacts do not cryptographically establish publisher identity.
