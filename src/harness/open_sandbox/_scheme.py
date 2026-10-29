"""Compose short-syntax volume schemes for OpenSandbox.

Parses ``source:mount_path[:ro|rw]`` into the native ``opensandbox`` ``Volume``
model (PVC / named volume). Host binds and remote URIs are rejected.
"""

from __future__ import annotations

import posixpath
from collections.abc import Sequence
from urllib.parse import urlsplit

from opensandbox.models import PVC, Volume

# region Compose short-syntax volumes
# Parse ``source:mount_path[:ro|rw]`` into an OpenSandbox ``Volume``.
# ``source`` is a named PVC (``data:/var/lib/data``). Host binds and remote
# URIs (webdav / s3 / drive) are rejected — use the SDK's typed Volume APIs
# for host / ossfs mounts.


def split_compose_volume(entry: str) -> tuple[str, str, bool]:
    """Split ``source:mount_path[:ro|rw]`` without treating ``://`` as a mount separator."""
    read_only = False
    body = entry
    if body.endswith(":ro"):
        read_only = True
        body = body[:-3]
    elif body.endswith(":rw"):
        body = body[:-3]

    # Rightmost ":/" that is not a scheme's "://".
    mount_at: int | None = None
    cursor = 0
    while True:
        found = body.find(":/", cursor)
        if found < 0:
            break
        if body[found : found + 3] != "://":
            mount_at = found
        cursor = found + 1
    if mount_at is None:
        raise ValueError(
            f"volume must be Compose short syntax 'source:mount_path[:ro|rw]', got {entry!r}."
        )
    source = body[:mount_at]
    mount_path = body[mount_at + 1 :]
    if not source:
        raise ValueError(f"volume source must not be empty, got {entry!r}.")
    # Leftover ":mode" after stripping :ro/:rw is an unsupported mode, not a path.
    if ":" in mount_path:
        raise ValueError(f"volume mode must be 'ro' or 'rw' when present, got {entry!r}.")
    if not mount_path or not posixpath.isabs(mount_path):
        raise ValueError(f"volume mount path must be absolute, got {mount_path!r} in {entry!r}.")
    return source, posixpath.normpath(mount_path), read_only


def _check_named_volume_source(source: str, entry: str) -> None:
    """Accept only a named PVC/volume; reject host paths and remote URIs."""
    scheme = urlsplit(source).scheme.casefold()
    if scheme:
        raise ValueError(
            f"unsupported remote volume protocol {scheme!r} in {entry!r}; "
            "use a named volume (PVC), e.g. 'data:/var/lib/data'."
        )
    if source.startswith(("/", ".", "~")) or "/" in source:
        raise ValueError(f"volume source must be a named volume, not a host path, got {entry!r}.")


def check_compose_volume_shape(entry: object) -> str:
    """Validate Compose short-syntax shape without building a ``Volume``."""
    if not isinstance(entry, str) or not entry.strip():
        raise ValueError(f"volume must be a non-empty string, got {entry!r}.")
    stripped = entry.strip()
    source, _mount_path, _read_only = split_compose_volume(stripped)
    _check_named_volume_source(source, stripped)
    return stripped


def check_volume_specs(volumes: object) -> list[str] | None:
    """Validate Compose volume strings for shape and unique names.

    Safe at agent-define time. Returns the stripped entries (or ``None``).
    Full ``Volume`` materialization is ``check_volumes``.
    """
    if volumes is None:
        return None
    if isinstance(volumes, (str, bytes)) or not isinstance(volumes, Sequence):
        raise ValueError("`volumes` must be a sequence of Compose short-syntax strings.")
    if not volumes:
        return None
    checked = [check_compose_volume_shape(entry) for entry in volumes]
    names = [split_compose_volume(entry)[0] for entry in checked]
    if len(names) != len(set(names)):
        raise ValueError("`volumes` names must be unique.")
    return checked


def parse_compose_volume(entry: object) -> Volume:
    """Parse Compose short syntax into a native OpenSandbox ``Volume``.

    Forms:

    - Named PVC: ``name:mount_path[:ro|rw]`` (e.g. ``data:/var/lib/data``)

    Host binds (``/path:...`` or ``./path:...``) and remote URIs are rejected.
    """
    stripped = check_compose_volume_shape(entry)
    source, mount_path, read_only = split_compose_volume(stripped)
    return Volume(
        name=source,
        pvc=PVC(claimName=source),
        mountPath=mount_path,
        readOnly=read_only,
    )


def check_volumes(volumes: object) -> list[Volume] | None:
    """Materialize Compose volume strings into native OpenSandbox ``Volume`` objects."""
    specs = check_volume_specs(volumes)
    if specs is None:
        return None
    checked = [parse_compose_volume(entry) for entry in specs]
    names = [volume.name for volume in checked]
    if len(names) != len(set(names)):
        raise ValueError("`volumes` names must be unique.")
    return checked


# endregion
