# backend/repository_analyzer.py

import os
from collections import Counter

from Backend.config import (
    IGNORED_DIRECTORIES,
    IGNORED_EXTENSIONS,
    EXTENSION_LANGUAGE
)


class RepositoryAnalyzer:

    def analyze(self, repo_path: str):

        language_counter = Counter()
        folders = set()

        total_files = 0
        largest_file = None
        largest_size = 0

        for root, dirs, files in os.walk(repo_path):

            # Ignore unwanted folders
            dirs[:] = [d for d in dirs if d not in IGNORED_DIRECTORIES]

            # Save folder names
            for directory in dirs:
                folders.add(directory)

            for file in files:

                extension = os.path.splitext(file)[1].lower()

                if extension in IGNORED_EXTENSIONS:
                    continue

                total_files += 1

                if extension in EXTENSION_LANGUAGE:
                    language = EXTENSION_LANGUAGE[extension]
                    language_counter[language] += 1

                file_path = os.path.join(root, file)

                try:
                    size = os.path.getsize(file_path)

                    if size > largest_size:
                        largest_size = size
                        largest_file = os.path.relpath(file_path, repo_path)

                except Exception:
                    pass

        if language_counter:
            main_language = language_counter.most_common(1)[0][0]
        else:
            main_language = "Unknown"

        return {
            "repo_name": os.path.basename(repo_path),
            "total_files": total_files,
            "main_language": main_language,
            "languages": dict(language_counter),
            "folders": sorted(folders),
            "largest_file": largest_file,
            "largest_size_kb": round(largest_size / 1024, 2)
        }