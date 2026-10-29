"""Unit tests for Compose short-syntax OpenSandbox volume parsing."""

import pytest
from opensandbox.models import Volume

from harness.open_sandbox._scheme import (
    check_volume_specs,
    check_volumes,
    parse_compose_volume,
    split_compose_volume,
)

# region Compose short-syntax volumes


def test_split_compose_volume_strips_mode_and_keeps_absolute_mount():
    source, mount, read_only = split_compose_volume("data:/var/lib/data:ro")
    assert source == "data"
    assert mount == "/var/lib/data"
    assert read_only is True
    source, mount, read_only = split_compose_volume("cache:/tmp/cache:rw")
    assert source == "cache"
    assert mount == "/tmp/cache"
    assert read_only is False


def test_parse_compose_volume_named_mount_and_ro():
    volume = parse_compose_volume("data:/var/lib/data")
    assert isinstance(volume, Volume)
    assert volume.name == "data"
    assert volume.mount_path == "/var/lib/data"
    assert volume.read_only is False
    assert volume.pvc is not None
    assert volume.pvc.claim_name == "data"
    assert volume.host is None
    assert volume.ossfs is None
    assert parse_compose_volume("cache:/tmp/cache:ro").read_only is True


def test_parse_compose_volume_rejects_host_binds_and_bad_shape():
    with pytest.raises(ValueError, match="host path"):
        parse_compose_volume("/host/data:/var/lib/data")
    with pytest.raises(ValueError, match="host path"):
        parse_compose_volume("./data:/var/lib/data")
    with pytest.raises(ValueError, match="short syntax"):
        parse_compose_volume("data:relative")
    with pytest.raises(ValueError, match="short syntax"):
        parse_compose_volume("data")
    with pytest.raises(ValueError, match=r"ro'| 'rw"):
        parse_compose_volume("data:/mnt:xx")
    with pytest.raises(ValueError, match="unsupported"):
        parse_compose_volume("ftp://host/path:/mnt")


def test_parse_compose_volume_rejects_remote_uris():
    """Remote schemes are not mapped onto native Volume (no drive / webdav / s3)."""
    for entry in (
        "drive://workspaces:/workspaces",
        "dav://host/path:/mnt/w",
        "webdav+http://host/w:/mnt/w",
        "s3://user:pass@host/bucket:/mnt/s3",
    ):
        with pytest.raises(ValueError, match="unsupported"):
            parse_compose_volume(entry)


def test_check_volume_specs_shape_and_unique_names():
    assert check_volume_specs(None) is None
    assert check_volume_specs([]) is None
    specs = check_volume_specs(["data:/var/lib/data", "cache:/cache:ro"])
    assert specs == ["data:/var/lib/data", "cache:/cache:ro"]
    with pytest.raises(ValueError, match="host path"):
        check_volume_specs(["/host/data:/var/lib/data"])
    with pytest.raises(ValueError, match="unique"):
        check_volume_specs(["data:/a", "data:/b"])


def test_check_volumes_materializes_native_volumes():
    assert check_volumes(None) is None
    assert check_volumes([]) is None
    checked = check_volumes(["data:/var/lib/data", "cache:/cache:ro"])
    assert checked is not None and len(checked) == 2
    assert all(isinstance(volume, Volume) for volume in checked)
    assert checked[0].pvc is not None and checked[0].pvc.claim_name == "data"
    assert checked[1].read_only is True
    with pytest.raises(ValueError, match="unique"):
        check_volumes(["data:/a", "data:/b"])


# endregion
