#!/usr/bin/env python3
"""
decompressor.py
---------------
Core recursive decompression engine used by the Flask app.

Supported formats (detected via magic bytes, NOT file extensions):
    zip, tar (all variants), gzip, bzip2, xz

Public API:
    recursive_decompress(input_path, output_dir) -> list[str]
        Copies input_path into output_dir and recursively extracts
        every archive found until none remain.
        Returns a list of log lines describing what was done.
"""

import os
import shutil
import zipfile
import tarfile
import gzip
import bz2
import lzma
import pathlib

try:
    import magic
except ImportError:
    raise ImportError("python-magic is required. Run: pip install python-magic")


# ─────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────

MAX_DEPTH = 50   # maximum extraction passes (zip-bomb protection)


# ─────────────────────────────────────────────
# Internal logger
# ─────────────────────────────────────────────

class _Logger:
    """Collects log lines and optionally prints them."""

    def __init__(self):
        self.lines: list[str] = []

    def info(self, msg: str) -> None:
        line = f"[+] {msg}"
        self.lines.append(line)
        print(line)

    def warn(self, msg: str) -> None:
        line = f"[!] {msg}"
        self.lines.append(line)
        print(line)

    def error(self, msg: str) -> None:
        line = f"[-] {msg}"
        self.lines.append(line)
        print(line)

    def separator(self, label: str = "") -> None:
        line = f"── {label} " + "─" * max(0, 48 - len(label))
        self.lines.append(line)
        print(line)


# ─────────────────────────────────────────────
# File-type detection
# ─────────────────────────────────────────────

# MIME type → canonical archive-type string
_MIME_MAP: dict[str, str] = {
    "application/zip"              : "zip",
    "application/x-zip-compressed" : "zip",
    "application/x-tar"            : "tar",
    "application/x-gzip"           : "gzip",
    "application/gzip"             : "gzip",
    "application/x-bzip2"          : "bzip2",
    "application/x-xz"             : "xz",
}

# Substrings in the human-readable magic description → archive type
_DESC_MAP: list[tuple[str, str]] = [
    ("zip archive",    "zip"),
    ("tar archive",    "tar"),
    ("posix tar",      "tar"),
    ("gzip compressed",  "gzip"),
    ("bzip2 compressed", "bzip2"),
    ("xz compressed",    "xz"),
]


def detect_file_type(filepath: str) -> str | None:
    """
    Inspect *filepath* using magic bytes and return its archive type.

    Returns one of: 'zip', 'tar', 'gzip', 'bzip2', 'xz'
    Returns None if the file is not a recognised archive.
    """
    try:
        mime = magic.from_file(filepath, mime=True)
    except Exception:
        return None

    # Primary: MIME lookup
    archive_type = _MIME_MAP.get(mime)

    # Fallback: human-readable description
    if archive_type is None:
        try:
            description = magic.from_file(filepath).lower()
        except Exception:
            return None
        for keyword, atype in _DESC_MAP:
            if keyword in description:
                archive_type = atype
                break

    return archive_type


# ─────────────────────────────────────────────
# Format-specific extractors
# ─────────────────────────────────────────────

def _safe_extract_zip(archive_path: str, dest_dir: str) -> None:
    """
    Extract a ZIP archive into dest_dir.
    Skips entries with absolute paths or '..' components (path-traversal guard).
    """
    with zipfile.ZipFile(archive_path, "r") as zf:
        for member in zf.infolist():
            member_path = pathlib.Path(member.filename)
            if member_path.is_absolute() or ".." in member_path.parts:
                continue   # silently skip dangerous entries
            zf.extract(member, dest_dir)


def _safe_extract_tar(archive_path: str, dest_dir: str) -> None:
    """
    Extract a TAR archive (plain / gz / bz2 / xz) into dest_dir.
    Filters out path-traversal entries before extraction.
    """
    with tarfile.open(archive_path, "r:*") as tf:
        safe_members = [
            m for m in tf.getmembers()
            if not pathlib.Path(m.name).is_absolute()
            and ".." not in pathlib.Path(m.name).parts
        ]
        # 'filter' keyword was added in Python 3.12 — use it when available
        try:
            tf.extractall(dest_dir, members=safe_members, filter="data")
        except TypeError:
            tf.extractall(dest_dir, members=safe_members)


def _decompress_stream(archive_path: str, dest_dir: str, archive_type: str) -> None:
    """
    Decompress a single-stream format (gzip / bzip2 / xz) into dest_dir.

    Output filename = archive stem (e.g. 'data.gz' → 'data').
    Falls back to '<original_name>.out' if no stem can be determined.
    """
    base = os.path.basename(archive_path)
    stem, _ = os.path.splitext(base)
    out_name = stem if stem else base + ".out"
    out_path = os.path.join(dest_dir, out_name)

    openers = {
        "gzip" : gzip.open,
        "bzip2": bz2.open,
        "xz"   : lzma.open,
    }

    with openers[archive_type](archive_path, "rb") as src, \
         open(out_path, "wb") as dst:
        shutil.copyfileobj(src, dst)


# ─────────────────────────────────────────────
# Public extraction dispatcher
# ─────────────────────────────────────────────

def extract_archive(
    archive_path : str,
    dest_dir     : str,
    archive_type : str,
    logger       : _Logger,
) -> bool:
    """
    Extract *archive_path* (of known *archive_type*) into *dest_dir*.

    For gzip / bzip2 / xz files, first checks whether the payload is a
    TAR stream (i.e. .tar.gz style) and uses the TAR extractor if so.

    Returns True on success, False on failure.
    """
    os.makedirs(dest_dir, exist_ok=True)

    try:
        if archive_type == "zip":
            _safe_extract_zip(archive_path, dest_dir)

        elif archive_type == "tar":
            _safe_extract_tar(archive_path, dest_dir)

        elif archive_type in ("gzip", "bzip2", "xz"):
            # .tar.gz / .tar.bz2 / .tar.xz → treat as TAR
            if tarfile.is_tarfile(archive_path):
                _safe_extract_tar(archive_path, dest_dir)
            else:
                _decompress_stream(archive_path, dest_dir, archive_type)

        else:
            logger.error(f"Unsupported archive type '{archive_type}': {archive_path}")
            return False

        return True

    except Exception as exc:
        logger.error(f"Extraction failed for '{archive_path}': {exc}")
        return False


# ─────────────────────────────────────────────
# Directory scanner
# ─────────────────────────────────────────────

def find_archives(search_dir: str) -> list[str]:
    """
    Recursively walk *search_dir* and return full paths of every file
    whose magic bytes identify it as a supported archive.
    """
    archives: list[str] = []
    for root, _dirs, files in os.walk(search_dir):
        for fname in files:
            fpath = os.path.join(root, fname)
            if detect_file_type(fpath) is not None:
                archives.append(fpath)
    return archives


# ─────────────────────────────────────────────
# Main public function
# ─────────────────────────────────────────────

def recursive_decompress(input_path: str, output_dir: str) -> list[str]:
    """
    Recursively decompress *input_path* into *output_dir*.

    Algorithm
    ---------
    1. Copy the initial archive into output_dir.
    2. Scan output_dir for archive files (magic-byte detection).
    3. Extract each archive into its containing directory.
    4. Delete the archive after successful extraction.
    5. Repeat from step 2 until no archives remain or MAX_DEPTH is hit.

    Parameters
    ----------
    input_path : str
        Path to the initial archive file.
    output_dir : str
        Directory to extract everything into (created if absent).

    Returns
    -------
    list[str]
        Human-readable log lines describing every action taken.
    """
    logger = _Logger()

    # ── Setup ─────────────────────────────────────────────────────────────
    os.makedirs(output_dir, exist_ok=True)

    dest_start = os.path.join(output_dir, os.path.basename(input_path))
    shutil.copy2(input_path, dest_start)
    logger.info(f"Copied '{os.path.basename(input_path)}' into working directory.")

    # ── Iterative extraction loop ─────────────────────────────────────────
    for depth in range(1, MAX_DEPTH + 1):

        archives = find_archives(output_dir)

        if not archives:
            logger.info("No more archives found. Decompression complete.")
            break

        logger.separator(f"Pass {depth}  ({len(archives)} archive(s) found)")

        for archive_path in archives:

            archive_type = detect_file_type(archive_path)
            if archive_type is None:
                # File may have been removed between scan and now
                continue

            rel_path = os.path.relpath(archive_path, output_dir)
            logger.info(f"Processing '{rel_path}'  [{archive_type} archive]")

            # Extract into the same folder that contains the archive
            dest_dir = os.path.dirname(archive_path)
            success  = extract_archive(archive_path, dest_dir, archive_type, logger)

            if success:
                logger.info(f"Extracted → '{os.path.relpath(dest_dir, output_dir) or '.'}'")
                try:
                    os.remove(archive_path)
                except OSError as exc:
                    logger.warn(f"Could not remove archive '{rel_path}': {exc}")
            else:
                # Rename so the same broken file is not retried next pass
                broken_path = archive_path + ".broken"
                logger.warn(f"Marking as broken: '{rel_path}.broken'")
                try:
                    os.rename(archive_path, broken_path)
                except OSError:
                    pass

    else:
        logger.warn(
            f"Reached maximum extraction depth ({MAX_DEPTH}). "
            "Possible zip-bomb or deeply nested archive — stopping."
        )

    # ── Bonus: collect .txt file contents for the log ─────────────────────
    txt_files = _find_txt_files(output_dir)
    if txt_files:
        logger.separator("Text files found")
        for txt_path in txt_files:
            rel = os.path.relpath(txt_path, output_dir)
            logger.info(f"Text file: {rel}")
            try:
                with open(txt_path, "r", errors="replace") as fh:
                    contents = fh.read().strip()
                for line in contents.splitlines():
                    logger.lines.append(f"    {line}")
            except Exception as exc:
                logger.error(f"Could not read '{rel}': {exc}")

    logger.separator("Done")
    return logger.lines


# ─────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────

def _find_txt_files(search_dir: str) -> list[str]:
    """Return paths of all .txt files under search_dir."""
    result = []
    for root, _dirs, files in os.walk(search_dir):
        for fname in files:
            if fname.lower().endswith(".txt"):
                result.append(os.path.join(root, fname))
    return result