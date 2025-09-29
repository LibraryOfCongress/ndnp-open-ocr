from __future__ import annotations

import os
from typing import List, Tuple

import fsspec


def _norm_root(uri: str) -> str:
    return uri.rstrip("/")


def env_source_fallback() -> str:
    bucket = os.getenv("BUCKET_NAME")
    prefix = os.getenv("PREFIX")
    if not bucket or not prefix:
        raise ValueError("BUCKET_NAME and PREFIX must be set or provide SOURCE_URI")
    return f"s3://{bucket}/{prefix}"


def env_sink_fallback() -> str:
    bucket = os.getenv("OUTPUT_BUCKET_NAME")
    prefix = os.getenv("OUTPUT_PREFIX")
    if not bucket or not prefix:
        raise ValueError("OUTPUT_BUCKET_NAME and OUTPUT_PREFIX must be set or provide SINK_URI")
    return f"s3://{bucket}/{prefix}"


def list_inputs(source_uri: str, pattern: str = "**/*.tif") -> List[str]:
    """Return rel_paths of all matching inputs under the given source URI.

    Uses the filesystem-native path (from url_to_fs) to avoid scheme/bucket
    mismatches when stripping the root prefix.
    """
    root = _norm_root(source_uri)
    fs, fs_root = fsspec.core.url_to_fs(root)
    base = fs_root.rstrip("/")
    glob_pat = base + "/" + pattern
    paths = fs.glob(glob_pat)
    rels: List[str] = []
    prefix = base + "/"
    for p in paths:
        if p.startswith(prefix):
            rels.append(p[len(prefix) :])
        else:
            # Fallback: relative to fs_root
            try:
                rels.append(os.path.relpath(p, base))
            except Exception:
                rels.append(os.path.basename(p))
    return sorted(rels)


def prefetch_sidecars(fs, remote_input: str, temp_dir: str) -> None:
    base = os.path.splitext(os.path.basename(remote_input))[0]
    remote_dir = os.path.dirname(remote_input)
    for ext in (".jp2", ".pdf", ".xml"):
        r = os.path.join(remote_dir, base + ext)
        l = os.path.join(temp_dir, base + ext)
        try:
            if fs.exists(r):
                fs.get(r, l)
        except Exception:
            pass


def download_input(source_uri: str, rel_path: str, temp_dir: str) -> str:
    """Download the primary input to temp_dir preserving its extension when possible.

    Also prefetch common sidecars (.jp2/.pdf/.xml) for downstream use.
    Returns the local path to the primary input (with the same extension as rel_path).
    """
    root = _norm_root(source_uri)
    fs, fs_root = fsspec.core.url_to_fs(root)
    base = fs_root.rstrip("/")
    remote_path = base + "/" + rel_path
    base, ext = os.path.splitext(os.path.basename(rel_path))
    ext = ext or ".tif"
    local_path = os.path.join(temp_dir, base + ext)
    try:
        fs.get(remote_path, local_path)
    except Exception:
        # Ignore and rely on sidecar prefetch/fallbacks
        pass
    prefetch_sidecars(fs, remote_path, temp_dir)
    return local_path


def upload_outputs(sink_uri: str, output_dir: str, rel_dir: str) -> None:
    root = _norm_root(sink_uri)
    fs, _ = fsspec.core.url_to_fs(root)
    for name in os.listdir(output_dir):
        local_path = os.path.join(output_dir, name)
        if not os.path.isfile(local_path):
            continue
        dst = "/".join(filter(None, [root, rel_dir, name]))
        fs.put(local_path, dst)


def record_text_blob(sink_uri: str, blob_rel_key: str, content: str) -> None:
    root = _norm_root(sink_uri)
    fs, _ = fsspec.core.url_to_fs(root)
    dst = "/".join(filter(None, [root, blob_rel_key]))
    with fs.open(dst, "wb") as f:
        f.write(content.encode("utf-8"))
