from dataclasses import dataclass


@dataclass
class CodeChunk:
    file_path: str
    language: str
    chunk_type: str
    name: str
    code: str