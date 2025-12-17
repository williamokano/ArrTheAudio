"""File scanner for discovering video files."""

from pathlib import Path
from typing import List

from arrtheaudio.utils.logger import get_logger

logger = get_logger(__name__)


class FileScanner:
    """Scan directories for video files."""

    SUPPORTED_EXTENSIONS = {".mkv", ".mp4"}

    def scan(
        self, path: Path, recursive: bool = True, extensions: set[str] | None = None
    ) -> List[Path]:
        """Scan a path for video files.

        Args:
            path: Path to scan (file or directory)
            recursive: If True, scan subdirectories recursively
            extensions: Set of file extensions to include (default: .mkv, .mp4)

        Returns:
            List of video file paths, sorted by path

        Raises:
            FileNotFoundError: If path doesn't exist
            ValueError: If path is not a file or directory
        """
        if not path.exists():
            raise FileNotFoundError(f"Path not found: {path}")

        if extensions is None:
            extensions = self.SUPPORTED_EXTENSIONS

        # Normalize extensions (ensure they start with dot and are lowercase)
        extensions = {ext.lower() if ext.startswith(".") else f".{ext.lower()}" for ext in extensions}

        files = []

        # If path is a file, check if it matches extensions
        if path.is_file():
            if path.suffix.lower() in extensions:
                files.append(path)
                logger.debug("Single file matched", file=str(path))
            else:
                logger.warning(
                    "File extension not supported",
                    file=str(path),
                    extension=path.suffix,
                    supported=list(extensions),
                )
            return files

        # If path is a directory, scan it
        if path.is_dir():
            if recursive:
                # Recursive scan using rglob
                for ext in extensions:
                    pattern = f"**/*{ext}"
                    found = list(path.rglob(pattern))
                    files.extend(found)
                    logger.debug(
                        "Recursive scan pattern",
                        directory=str(path),
                        pattern=pattern,
                        found_count=len(found),
                    )
            else:
                # Non-recursive scan using glob
                for ext in extensions:
                    pattern = f"*{ext}"
                    found = list(path.glob(pattern))
                    files.extend(found)
                    logger.debug(
                        "Non-recursive scan pattern",
                        directory=str(path),
                        pattern=pattern,
                        found_count=len(found),
                    )

            # Remove duplicates and sort
            files = sorted(set(files))

            logger.info(
                "Directory scan complete",
                directory=str(path),
                recursive=recursive,
                total_files=len(files),
            )

            return files

        raise ValueError(f"Path is neither a file nor a directory: {path}")

    def scan_pattern(self, pattern: str) -> List[Path]:
        """Scan using a glob pattern.

        Args:
            pattern: Glob pattern (e.g., "/media/**/*.mkv")

        Returns:
            List of matching file paths, sorted

        Example:
            scanner.scan_pattern("/media/anime/**/*.mkv")
            scanner.scan_pattern("/media/tv/Show/Season 1/*.mkv")
        """
        # Convert pattern string to Path and use glob
        pattern_path = Path(pattern)

        # If pattern contains wildcards, use the parent directory
        if "*" in str(pattern_path):
            # Find the base directory (part before first wildcard)
            parts = pattern_path.parts
            base_parts = []
            for part in parts:
                if "*" in part:
                    break
                base_parts.append(part)

            if not base_parts:
                raise ValueError("Pattern must have a base directory before wildcards")

            base_dir = Path(*base_parts)
            relative_pattern = str(pattern_path.relative_to(base_dir))

            if not base_dir.exists():
                raise FileNotFoundError(f"Base directory not found: {base_dir}")

            files = list(base_dir.glob(relative_pattern))
            files = sorted(files)

            logger.info(
                "Pattern scan complete",
                pattern=pattern,
                base_dir=str(base_dir),
                total_files=len(files),
            )

            return files

        # No wildcards, treat as regular path
        return self.scan(pattern_path)
