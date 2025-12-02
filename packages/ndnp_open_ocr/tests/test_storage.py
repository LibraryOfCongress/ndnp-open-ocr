from ndnp_open_ocr import storage


def test_source_output_prefix_s3_simple():
    result = storage.source_output_prefix("s3://bucket/batch_alpha")
    assert result == "batch_alpha"


def test_source_output_prefix_s3_nested():
    result = storage.source_output_prefix("s3://bucket/batches/batch_alpha")
    assert result == "batches/batch_alpha"


def test_source_output_prefix_s3_trim_to_batch():
    result = storage.source_output_prefix("s3://bucket/foo/bar/batch_alpha")
    assert result == "batch_alpha"


def test_source_output_prefix_file_scheme():
    result = storage.source_output_prefix("file:///tmp/batch_alpha")
    assert result == "batch_alpha"


def test_build_output_rel_dir_preserves_prefix():
    rel_dir = storage.build_output_rel_dir(
        "s3://bucket/batch_alpha",
        "path/to/some/file.jp2",
    )
    assert rel_dir == "batch_alpha/path/to/some"


def test_build_output_rel_dir_without_subdir():
    rel_dir = storage.build_output_rel_dir(
        "s3://bucket/batch_alpha",
        "leaf.jp2",
    )
    assert rel_dir == "batch_alpha"


def test_build_output_rel_dir_strips_leading_before_batch():
    rel_dir = storage.build_output_rel_dir(
        "s3://loc-preservation/loc-preservation",
        "batch_dlc_kite_ver01/test/1/1.jp2",
    )
    assert rel_dir == "batch_dlc_kite_ver01/test/1"


def test_build_output_rel_dir_no_batch_keeps_full():
    rel_dir = storage.build_output_rel_dir(
        "s3://bucket/foo",
        "bar/baz/file.jp2",
    )
    assert rel_dir == "foo/bar/baz"
