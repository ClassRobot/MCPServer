"""Tests for the MarkItDown conversion service safety and persistence behavior."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from mcp_server.config import MarkItDownSettings
from mcp_server.services.markitdown import MarkItDownConversionService


class FakeMarkItDownService(MarkItDownConversionService):
    """Avoid importing the third-party converter in unit tests."""

    def convert_local_file(self, source_path: Path) -> str:
        return f"# Converted\n\nSource: {source_path.name}\n"


def test_markitdown_service_converts_and_saves_output(tmp_path: Path) -> None:
    source_file = tmp_path / "sample.txt"
    source_file.write_text("hello", encoding="utf-8")
    output_dir = tmp_path / "runtime" / "markitdown"
    service = FakeMarkItDownService(
        MarkItDownSettings(
            allowed_roots=(tmp_path,),
            output_dir=output_dir,
            save_output_by_default=True,
        ),
        project_root=tmp_path,
    )

    result = asyncio.run(service.convert_to_markdown("sample.txt"))

    assert result.source_name == "sample.txt"
    assert result.source_uri == "sample.txt"
    assert result.markdown.startswith("# Converted")
    assert result.output_resource_uri is not None
    assert (output_dir / result.output_resource_uri.removeprefix("markitdown://")).is_file()


def test_markitdown_service_accepts_file_uri(tmp_path: Path) -> None:
    source_file = tmp_path / "sample.txt"
    source_file.write_text("hello", encoding="utf-8")
    service = FakeMarkItDownService(
        MarkItDownSettings(allowed_roots=(tmp_path,), output_dir=tmp_path / "out"),
        project_root=tmp_path,
    )

    result = asyncio.run(service.convert_to_markdown(source_file.as_uri(), save_output=False))

    assert result.source_name == "sample.txt"
    assert result.markdown.startswith("# Converted")
    assert result.output_resource_uri is None


def test_markitdown_service_respects_disabled_setting(tmp_path: Path) -> None:
    source_file = tmp_path / "sample.txt"
    source_file.write_text("hello", encoding="utf-8")
    service = FakeMarkItDownService(
        MarkItDownSettings(
            enabled=False,
            allowed_roots=(tmp_path,),
            output_dir=tmp_path / "out",
        ),
        project_root=tmp_path,
    )

    with pytest.raises(RuntimeError, match="disabled by configuration"):
        asyncio.run(service.convert_to_markdown("sample.txt"))


def test_markitdown_service_rejects_remote_uri(tmp_path: Path) -> None:
    service = FakeMarkItDownService(
        MarkItDownSettings(allowed_roots=(tmp_path,), output_dir=tmp_path / "out"),
        project_root=tmp_path,
    )

    with pytest.raises(ValueError, match="only accepts local paths"):
        service.resolve_source_uri("https://example.com/file.pdf")


def test_markitdown_service_rejects_path_outside_allowed_roots(tmp_path: Path) -> None:
    source_root = tmp_path / "allowed"
    outside_root = tmp_path / "outside"
    source_root.mkdir()
    outside_root.mkdir()
    outside_file = outside_root / "secret.txt"
    outside_file.write_text("secret", encoding="utf-8")
    service = FakeMarkItDownService(
        MarkItDownSettings(allowed_roots=(source_root,), output_dir=tmp_path / "out"),
        project_root=tmp_path,
    )

    with pytest.raises(ValueError, match="outside the configured allowed roots"):
        service.resolve_source_uri(str(outside_file))


def test_markitdown_service_rejects_large_inputs(tmp_path: Path) -> None:
    source_file = tmp_path / "large.txt"
    source_file.write_text("123456", encoding="utf-8")
    service = FakeMarkItDownService(
        MarkItDownSettings(
            allowed_roots=(tmp_path,),
            output_dir=tmp_path / "out",
            max_input_bytes=5,
        ),
        project_root=tmp_path,
    )

    with pytest.raises(ValueError, match="MAX_INPUT_BYTES"):
        asyncio.run(service.convert_to_markdown("large.txt"))
