# Test-Only Mock Forensic Executables

These Python scripts (`vol`, `yara`, `exiftool`) are isolated test fixtures designed specifically for hermetic offline test scenarios.
They must NEVER be placed in production `PATH`, `tools/bin/`, or discovered by `PlatformAwareToolRegistry`.
Production tool discovery strictly requires genuine compiled binaries and verifies native executable signatures and version headers.
