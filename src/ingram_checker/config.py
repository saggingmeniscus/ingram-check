"""Configuration constants for Ingram Lightning Source compliance."""

from __future__ import annotations

from .models import TrimSize

# Dimensional tolerance: 1/16 inch
TOLERANCE = 0.0625

# Bleed amounts in inches
INTERIOR_BLEED_TRIM_EDGE = 0.125  # trim (outside) edge only
INTERIOR_BLEED_TOP_BOTTOM = 0.125  # top and bottom each
COVER_BLEED = 0.125  # all four sides

# Ink density thresholds (% total)
INK_DENSITY_WARN = 240
INK_DENSITY_ERROR = 300

# Image resolution thresholds (PPI)
RESOLUTION_ERROR_INTERIOR = 72
RESOLUTION_ERROR_COVER = 200
RESOLUTION_WARN_LOW = 300
RESOLUTION_WARN_HIGH = 375

# Margin recommendations (inches from trim)
RECOMMENDED_MARGIN = 0.5
COVER_TYPE_SAFETY = 0.25  # 6mm ≈ 0.236", Ingram says 0.25"

# Standard Ingram Lightning Source trim sizes (width x height in inches)
TRIM_SIZES: dict[str, TrimSize] = {
    "5x8": TrimSize(5.0, 8.0, "5x8"),
    "5.06x7.81": TrimSize(5.06, 7.81, "5.06x7.81"),
    "5.25x8": TrimSize(5.25, 8.0, "5.25x8"),
    "5.5x8.5": TrimSize(5.5, 8.5, "5.5x8.5"),
    "6x9": TrimSize(6.0, 9.0, "6x9"),
    "6.14x9.21": TrimSize(6.14, 9.21, "6.14x9.21"),
    "6.69x9.61": TrimSize(6.69, 9.61, "6.69x9.61"),
    "7x10": TrimSize(7.0, 10.0, "7x10"),
    "7.44x9.69": TrimSize(7.44, 9.69, "7.44x9.69"),
    "7.5x9.25": TrimSize(7.5, 9.25, "7.5x9.25"),
    "8x10": TrimSize(8.0, 10.0, "8x10"),
    "8.25x11": TrimSize(8.25, 11.0, "8.25x11"),
    "8.5x11": TrimSize(8.5, 11.0, "8.5x11"),
    "5.83x8.27": TrimSize(5.83, 8.27, "5.83x8.27"),  # A5
    "8.27x11.69": TrimSize(8.27, 11.69, "8.27x11.69"),  # A4
    # Additional common sizes
    "4.25x6.87": TrimSize(4.25, 6.87, "4.25x6.87"),  # Mass market
    "5x7": TrimSize(5.0, 7.0, "5x7"),
    "5.5x7.5": TrimSize(5.5, 7.5, "5.5x7.5"),
    "6.5x6.5": TrimSize(6.5, 6.5, "6.5x6.5"),  # Square
    "7.5x7.5": TrimSize(7.5, 7.5, "7.5x7.5"),  # Square
    "8x8": TrimSize(8.0, 8.0, "8x8"),  # Square
    "8.5x8.5": TrimSize(8.5, 8.5, "8.5x8.5"),  # Square
    "8.5x10.88": TrimSize(8.5, 10.88, "8.5x10.88"),
    "9x7": TrimSize(9.0, 7.0, "9x7"),  # Landscape
    "10x8": TrimSize(10.0, 8.0, "10x8"),  # Landscape
    "11x8.5": TrimSize(11.0, 8.5, "11x8.5"),  # Landscape
}


# Case-insensitive aliases for common names
TRIM_SIZE_ALIASES: dict[str, str] = {
    "a4": "8.27x11.69",
    "a5": "5.83x8.27",
    "letter": "8.5x11",
    "digest": "5.5x8.5",
    "mass market": "4.25x6.87",
    "massmarket": "4.25x6.87",
    "us trade": "6x9",
    "trade": "6x9",
    "royal": "6.14x9.21",
    "crown quarto": "7.44x9.69",
    "crownquarto": "7.44x9.69",
}


def get_trim_size(spec: str) -> TrimSize | None:
    """Look up a trim size by its string spec (e.g. '6x9') or alias (e.g. 'A5')."""
    result = TRIM_SIZES.get(spec)
    if result:
        return result
    canonical = TRIM_SIZE_ALIASES.get(spec.lower())
    if canonical:
        return TRIM_SIZES.get(canonical)
    return None


def expected_interior_page_size(trim: TrimSize) -> tuple[float, float]:
    """Calculate expected page size for interior PDF with bleed.

    Interior bleed: 0.125" on trim edge + 0.125" top + 0.125" bottom.
    Width = trim_width + 0.125" (outside/trim edge only; spine edge has no bleed).
    Height = trim_height + 0.250" (top + bottom).
    """
    width = trim.width + INTERIOR_BLEED_TRIM_EDGE
    height = trim.height + 2 * INTERIOR_BLEED_TOP_BOTTOM
    return (width, height)


# Prohibited text patterns for copyright page scanning
PROHIBITED_MANUFACTURING_PATTERNS = [
    r"printed\s+in\s+\w+",
    r"manufactured\s+in\s+\w+",
]

PROHIBITED_PAPER_CERT_PATTERNS = [
    r"\bFSC\b",
    r"\bSFI\b",
    r"\bPEFC\b",
    r"forest\s+stewardship",
    r"sustainable\s+forest",
    r"recycled\s+paper",
    r"acid[\s-]*free",
]

BRACKET_PATTERN = r"\[.*?\]"
