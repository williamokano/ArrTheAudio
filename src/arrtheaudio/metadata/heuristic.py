"""Filename heuristics for extracting media metadata."""

import re
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)


def parse_filename(filename: str) -> Optional[dict]:
    """Parse filename to extract title, year, season/episode.

    Attempts to parse common filename patterns:
    - TV shows: "Show.Name.S01E01.1080p.mkv"
    - Movies: "Movie.Name.2023.1080p.mkv"
    - Movies with quality: "Movie.Name.(2023).BluRay.mkv"

    Args:
        filename: Filename to parse (can include extension)

    Returns:
        Dict with parsed metadata or None if parsing fails
        Keys: title, type, season, episode, year
    """
    logger.debug("Parsing filename", filename=filename)

    # Remove extension
    name_without_ext = filename.rsplit(".", 1)[0] if "." in filename else filename

    # Try TV show pattern: Show.Name.S01E01 or Show.Name.s01e01
    tv_result = _parse_tv_show(name_without_ext)
    if tv_result:
        logger.info(
            "Parsed TV show from filename",
            filename=filename,
            **tv_result,
        )
        return tv_result

    # Try movie pattern: Movie.Name.2023 or Movie.Name.(2023)
    movie_result = _parse_movie(name_without_ext)
    if movie_result:
        logger.info(
            "Parsed movie from filename",
            filename=filename,
            **movie_result,
        )
        return movie_result

    logger.debug("Could not parse filename", filename=filename)
    return None


def _parse_tv_show(name: str) -> Optional[dict]:
    """Parse TV show filename pattern.

    Patterns supported:
    - Show.Name.S01E01
    - Show.Name.s01e01
    - Show.Name.1x01
    - Show Name - S01E01
    - Show Name - 1x01

    Args:
        name: Filename without extension

    Returns:
        Dict with title, season, episode, type='tv' or None
    """
    # Pattern 1: S01E01 format (most common)
    pattern = r"^(.+?)[.\s-]+S(\d+)E(\d+)"
    if match := re.match(pattern, name, re.IGNORECASE):
        title = _clean_title(match.group(1))
        season = int(match.group(2))
        episode = int(match.group(3))
        return {
            "title": title,
            "season": season,
            "episode": episode,
            "type": "tv",
        }

    # Pattern 2: 1x01 format
    pattern = r"^(.+?)[.\s-]+(\d+)x(\d+)"
    if match := re.match(pattern, name, re.IGNORECASE):
        title = _clean_title(match.group(1))
        season = int(match.group(2))
        episode = int(match.group(3))
        return {
            "title": title,
            "season": season,
            "episode": episode,
            "type": "tv",
        }

    return None


def _parse_movie(name: str) -> Optional[dict]:
    """Parse movie filename pattern.

    Patterns supported:
    - Movie.Name.2023
    - Movie.Name.(2023)
    - Movie Name (2023)
    - Movie Name - 2023

    Args:
        name: Filename without extension

    Returns:
        Dict with title, year, type='movie' or None
    """
    # Pattern 1: Movie.Name.2023 or Movie.Name.(2023)
    pattern = r"^(.+?)[.\s-]+\(?(\d{4})\)?"
    if match := re.match(pattern, name):
        year_str = match.group(2)
        year = int(year_str)

        # Sanity check: year should be between 1900 and current year + 2
        if 1900 <= year <= 2030:
            title = _clean_title(match.group(1))

            # Remove year from title if it was captured as part of it
            title = re.sub(r"\s*\(\d{4}\)$", "", title)

            return {
                "title": title,
                "year": year,
                "type": "movie",
            }

    return None


def _clean_title(title: str) -> str:
    """Clean up extracted title.

    - Replace dots and underscores with spaces
    - Remove extra whitespace
    - Strip leading/trailing spaces

    Args:
        title: Raw extracted title

    Returns:
        Cleaned title
    """
    # Replace dots and underscores with spaces
    cleaned = title.replace(".", " ").replace("_", " ")

    # Remove extra whitespace
    cleaned = re.sub(r"\s+", " ", cleaned)

    # Strip
    cleaned = cleaned.strip()

    return cleaned


def extract_year_from_string(text: str) -> Optional[int]:
    """Extract a 4-digit year from a string.

    Args:
        text: String that may contain a year

    Returns:
        First valid year found (1900-2030), or None
    """
    pattern = r"\b(19\d{2}|20[0-2]\d|2030)\b"
    if match := re.search(pattern, text):
        return int(match.group(1))
    return None
