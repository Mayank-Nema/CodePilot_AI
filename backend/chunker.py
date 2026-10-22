"""
Chunker — Semantic code chunking pipeline.

Combines AST-based structural parsing with line-based windowed chunking
for files without AST parser support or oversized code elements.

Responsibilities:
    - Receive a list of SourceFile objects.
    - Parse Python and Java files structurally using Tree-sitter parsers.
    - Split oversized AST chunks into smaller sub-chunks while preserving parent symbol metadata.
    - Perform windowed chunking for non-AST source files (e.g. JS, HTML, Markdown).
    - Ensure every chunk contains file_path, line range, symbol/block context, and language metadata.
"""

from typing import List, Optional

from backend.config import PARSEABLE_LANGUAGES
from backend.parsers.parser_factory import get_parser
from models.code_chunk import CodeChunk
from models.source_file import SourceFile


def chunk_repository(
    source_files: List[SourceFile],
    max_lines_per_chunk: int = 60,
    overlap_lines: int = 10,
) -> List[CodeChunk]:
    """Chunk all source files in a repository.

    Args:
        source_files: List of loaded SourceFile objects.
        max_lines_per_chunk: Maximum line span for any single chunk.
        overlap_lines: Line overlap when splitting large chunks or fallback windowing.

    Returns:
        List of all processed CodeChunk objects ready for vector embedding.
    """
    all_chunks: List[CodeChunk] = []

    for source_file in source_files:
        file_chunks = chunk_source_file(
            source_file,
            max_lines_per_chunk=max_lines_per_chunk,
            overlap_lines=overlap_lines,
        )
        all_chunks.extend(file_chunks)

    return all_chunks


def chunk_source_file(
    source_file: SourceFile,
    max_lines_per_chunk: int = 60,
    overlap_lines: int = 10,
) -> List[CodeChunk]:
    """Chunk a single SourceFile into CodeChunk objects."""

    # 1. Try AST Parsing for supported languages
    if source_file.language in PARSEABLE_LANGUAGES:
        parser = get_parser(source_file.language)
        if parser is not None:
            try:
                ast_chunks = parser.parse(source_file)
                if ast_chunks:
                    # Post-process AST chunks: split oversized chunks if needed
                    final_ast_chunks: List[CodeChunk] = []
                    for chunk in ast_chunks:
                        if chunk.line_count > max_lines_per_chunk and chunk.chunk_type not in ("import",):
                            sub_chunks = _split_oversized_chunk(
                                chunk, source_file, max_lines_per_chunk, overlap_lines
                            )
                            final_ast_chunks.extend(sub_chunks)
                        else:
                            final_ast_chunks.append(chunk)
                    return final_ast_chunks
            except Exception:
                # If AST parsing fails unexpectedly, fall back to windowed chunking below
                pass

    # 2. Fallback windowed chunking for non-AST languages or failed AST parses
    return _windowed_line_chunking(
        source_file, max_lines_per_chunk=max_lines_per_chunk, overlap_lines=overlap_lines
    )


def _split_oversized_chunk(
    chunk: CodeChunk,
    source_file: SourceFile,
    max_lines: int,
    overlap: int,
) -> List[CodeChunk]:
    """Split an oversized AST chunk into smaller overlapping sub-chunks.

    Preserves symbol parent name and marks metadata with sub_chunk index.
    """
    lines = chunk.code.split("\n")
    total_lines = len(lines)
    if total_lines <= max_lines:
        return [chunk]

    sub_chunks: List[CodeChunk] = []
    step = max(1, max_lines - overlap)
    part = 1

    for start_idx in range(0, total_lines, step):
        end_idx = min(start_idx + max_lines, total_lines)
        sub_code_lines = lines[start_idx:end_idx]
        sub_code = "\n".join(sub_code_lines)

        sub_start_line = chunk.start_line + start_idx
        sub_end_line = chunk.start_line + end_idx - 1

        sub_metadata = dict(chunk.metadata)
        sub_metadata["sub_chunk_part"] = part
        sub_metadata["original_lines"] = f"{chunk.start_line}-{chunk.end_line}"

        parent_context = chunk.qualified_name

        sub_chunks.append(
            CodeChunk(
                file_path=chunk.file_path,
                relative_path=chunk.relative_path,
                language=chunk.language,
                chunk_type=chunk.chunk_type,
                name=f"{chunk.name}_part{part}",
                code=sub_code,
                start_line=sub_start_line,
                end_line=sub_end_line,
                parent_symbol=parent_context,
                metadata=sub_metadata,
            )
        )
        part += 1

        if end_idx >= total_lines:
            break

    return sub_chunks


def _windowed_line_chunking(
    source_file: SourceFile,
    max_lines_per_chunk: int = 60,
    overlap_lines: int = 10,
) -> List[CodeChunk]:
    """Perform sliding-window line chunking for non-AST source files."""
    lines = source_file.content.split("\n")
    total_lines = len(lines)

    if total_lines == 0 or (total_lines == 1 and not lines[0].strip()):
        return []

    chunks: List[CodeChunk] = []
    step = max(1, max_lines_per_chunk - overlap_lines)
    part = 1

    for start_idx in range(0, total_lines, step):
        end_idx = min(start_idx + max_lines_per_chunk, total_lines)
        chunk_lines = lines[start_idx:end_idx]
        code = "\n".join(chunk_lines)

        # Skip empty whitespace-only chunks
        if not code.strip():
            if end_idx >= total_lines:
                break
            continue

        start_line = start_idx + 1
        end_line = end_idx

        block_name = f"{source_file.relative_path}:L{start_line}-{end_line}"

        chunks.append(
            CodeChunk(
                file_path=source_file.file_path,
                relative_path=source_file.relative_path,
                language=source_file.language,
                chunk_type="block",
                name=block_name,
                code=code,
                start_line=start_line,
                end_line=end_line,
                parent_symbol=source_file.relative_path,
                metadata={"window_part": part},
            )
        )
        part += 1

        if end_idx >= total_lines:
            break

    return chunks
