rule ADFIP_SYNTHETIC_YARA_MARKER_001
{
    meta:
        description = "ADFIP deterministic forensic test marker"
        purpose = "test_only"

    strings:
        $marker = "ADFIP_SYNTHETIC_YARA_MARKER_001"

    condition:
        $marker
}
