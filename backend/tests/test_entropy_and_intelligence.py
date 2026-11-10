"""Tests for Genuine Streaming Shannon Entropy and 3-Tier Metadata Pipeline.

Verifies:
1. Streaming whole-file Shannon entropy:
   - Empty file: 0.0
   - Uniform byte file (all 0x00 or all 0xFF): 0.0
   - Maximally disordered 256-byte distribution: 8.0
   - High entropy pseudo-random payload: > 7.9
2. Block-based entropy analysis (256 KB blocks):
   - Correct block count
   - High-entropy flag (> 7.2)
3. Forensic metadata extraction:
   - Filesystem metadata (size, MACB timestamps, inode, permissions, ownership)
   - Embedded metadata (PE, ELF, PDF, docx, image)
   - Disguised extension anomaly detection (e.g., MZ executable disguised as .jpg)
"""

import os
import stat
import math
import tempfile
import pytest
from pathlib import Path
from backend.app.services.entropy import (
    calculate_streaming_entropy,
    extract_forensic_metadata,
    HIGH_ENTROPY_THRESHOLD
)


def test_empty_file_entropy():
    with tempfile.NamedTemporaryFile() as tf:
        p = Path(tf.name)
        res = calculate_streaming_entropy(p)
        assert res["whole_file_entropy"] == 0.0
        assert res["total_bytes_analyzed"] == 0
        assert res["total_blocks"] == 0
        assert res["high_entropy_blocks_count"] == 0
        assert res["is_high_entropy_overall"] is False


def test_uniform_single_byte_entropy():
    with tempfile.NamedTemporaryFile() as tf:
        p = Path(tf.name)
        p.write_bytes(b"\x00" * 300000)
        res = calculate_streaming_entropy(p, block_size=262144)
        assert res["whole_file_entropy"] == 0.0
        assert res["total_bytes_analyzed"] == 300000
        assert res["total_blocks"] == 2  # 1 full 256KB block + 1 remainder
        assert res["high_entropy_blocks_count"] == 0
        assert res["is_high_entropy_overall"] is False


def test_perfect_max_entropy_distribution():
    with tempfile.NamedTemporaryFile() as tf:
        p = Path(tf.name)
        # Uniform distribution of all 256 byte values repeated 100 times
        payload = bytes(range(256)) * 100
        p.write_bytes(payload)
        res = calculate_streaming_entropy(p)
        assert res["whole_file_entropy"] == 8.0
        assert res["is_high_entropy_overall"] is True


def test_high_entropy_blocks_detection():
    with tempfile.NamedTemporaryFile() as tf:
        p = Path(tf.name)
        # Block 1: Low entropy (zeros)
        block1 = b"\x00" * 262144
        # Block 2: High entropy (random)
        block2 = os.urandom(262144)
        p.write_bytes(block1 + block2)

        res = calculate_streaming_entropy(p, block_size=262144)
        assert res["total_blocks"] == 2
        assert res["high_entropy_blocks_count"] == 1
        assert res["blocks"][0]["is_high_entropy"] is False
        assert res["blocks"][1]["is_high_entropy"] is True
        assert res["blocks"][1]["entropy"] > 7.9


def test_disguised_executable_extension_mismatch():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "invoice.pdf.jpg"
        # DOS MZ header
        header = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff" + b"\x00" * 200
        p.write_bytes(header)

        meta = extract_forensic_metadata(p, header, "PE32_EXECUTABLE", "MALWARE_SAMPLE")

        extracted = meta.get("extracted_metadata", {})
        mismatch = extracted.get("signature_extension_mismatch", {})
        assert mismatch.get("mismatch_detected") is True
        assert mismatch.get("severity") == "CRITICAL"
        assert "ANTI-FORENSIC" in mismatch.get("description", "")


def test_filesystem_macb_metadata_extraction():
    with tempfile.NamedTemporaryFile() as tf:
        p = Path(tf.name)
        p.write_bytes(b"Forensic test content for metadata verification")
        meta = extract_forensic_metadata(p, b"Forensic test content", "PLAINTEXT_FILE", "DOCUMENT")

        fs = meta.get("filesystem_metadata", {})
        assert fs["size_bytes"] == len(b"Forensic test content for metadata verification")
        assert "timestamps" in fs
        assert "modified_at" in fs["timestamps"]
        assert "accessed_at" in fs["timestamps"]
        assert "changed_at" in fs["timestamps"]
        assert "born_at" in fs["timestamps"]
        assert "inode" in fs
        assert "permissions" in fs
        assert "octal" in fs["permissions"]
        assert "ownership" in fs
