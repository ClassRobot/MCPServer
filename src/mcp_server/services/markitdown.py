"""Microsoft MarkItDown conversion service with project-level safety boundaries."""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

from mcp_server.config import MarkItDownSettings
from mcp_server.schemas import MarkItDownConversionResult


class MarkItDownConversionService:
    """Convert whitelisted local files to Markdown using Microsoft's MarkItDown library."""

    def __init__(self, settings: MarkItDownSettings, project_root: Path) -> None:
        self._settings = settings
        self._project_root = project_root.resolve()
        self._allowed_roots = tuple(root.resolve() for root in settings.allowed_roots)

    async def convert_to_markdown(
        self,
        uri: str,
        *,
        save_output: bool | None = None,
    ) -> MarkItDownConversionResult:
        """Convert a local path or file:// URI to Markdown."""
        if not self._settings.enabled:
            raise RuntimeError("MarkItDown conversion is disabled by configuration.")

        source_path = self.resolve_source_uri(uri)
        input_bytes = source_path.stat().st_size
        if input_bytes > self._settings.max_input_bytes:
            raise ValueError(
                "Input file exceeds MCP_MARKITDOWN_MAX_INPUT_BYTES "
                f"({input_bytes} > {self._settings.max_input_bytes})."
            )

        markdown = await asyncio.to_thread(self.convert_local_file, source_path)
        should_save = self._settings.save_output_by_default if save_output is None else save_output
        output_resource_uri = None
        if should_save:
            output_resource_uri = self.save_markdown_output(source_path, markdown)

        return MarkItDownConversionResult(
            source_name=source_path.name,
            source_uri=self.public_source_uri(source_path),
            markdown=markdown,
            output_resource_uri=output_resource_uri,
            input_bytes=input_bytes,
            output_bytes=len(markdown.encode("utf-8")),
        )

    def resolve_source_uri(self, uri: str) -> Path:
        """Resolve and validate a local source URI against the configured whitelist."""
        source_path = self.parse_local_uri(uri)
        if not source_path.is_file():
            raise FileNotFoundError(f"MarkItDown source file does not exist: {uri}")
        if not self.is_allowed_path(source_path):
            raise ValueError("MarkItDown source path is outside the configured allowed roots.")
        return source_path

    def parse_local_uri(self, uri: str) -> Path:
        """Parse project-relative paths, absolute local paths, and file:// URIs."""
        direct_path = Path(uri).expanduser()
        if direct_path.is_absolute():
            return direct_path.resolve()

        parsed = urlparse(uri)
        if parsed.scheme and parsed.scheme != "file":
            raise ValueError("MarkItDown only accepts local paths or file:// URIs.")

        if parsed.scheme == "file":
            if parsed.netloc not in {"", "localhost"}:
                raise ValueError("MarkItDown file:// URIs must target the local machine.")
            raw_path = url2pathname(unquote(parsed.path))
            path = Path(raw_path)
        else:
            path = direct_path

        if not path.is_absolute():
            path = self._project_root / path
        return path.expanduser().resolve()

    def is_allowed_path(self, source_path: Path) -> bool:
        """Return whether a resolved source path is inside an allowed root."""
        return any(source_path.is_relative_to(root) for root in self._allowed_roots)

    def convert_local_file(self, source_path: Path) -> str:
        """Run MarkItDown conversion for a local file path."""
        from markitdown import MarkItDown

        converter = MarkItDown()
        result = converter.convert_local(str(source_path))
        markdown = getattr(result, "text_content", None)
        if markdown is None:
            markdown = getattr(result, "markdown", None)
        if markdown is None:
            markdown = str(result)
        return markdown

    def save_markdown_output(self, source_path: Path, markdown: str) -> str:
        """Persist Markdown under the configured runtime directory and return its resource URI."""
        self._settings.output_dir.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(str(source_path).encode("utf-8")).hexdigest()[:12]
        safe_stem = _safe_filename(source_path.stem) or "document"
        output_name = f"{safe_stem}-{digest}.md"
        output_path = self._settings.output_dir / output_name
        output_path.write_text(markdown, encoding="utf-8")
        return f"markitdown://{output_name}"

    def public_source_uri(self, source_path: Path) -> str:
        """Return a non-absolute source identifier suitable for MCP responses."""
        try:
            return str(source_path.relative_to(self._project_root)).replace("\\", "/")
        except ValueError:
            return source_path.name


def _safe_filename(value: str) -> str:
    """Normalize filenames without leaking path fragments into resource names."""
    safe_chars: list[str] = []
    for char in value:
        if char.isalnum() or char in {"-", "_"}:
            safe_chars.append(char)
        elif char.isspace():
            safe_chars.append("-")
    return "".join(safe_chars).strip("-_").lower()
