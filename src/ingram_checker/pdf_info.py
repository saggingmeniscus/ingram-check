"""PDF metadata extraction helpers using pikepdf and PyMuPDF."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF
import pikepdf


@dataclass
class PageBoxes:
    """Page box dimensions in points (1 point = 1/72 inch)."""

    media_box: tuple[float, float, float, float]  # x0, y0, x1, y1
    trim_box: tuple[float, float, float, float] | None = None
    bleed_box: tuple[float, float, float, float] | None = None
    crop_box: tuple[float, float, float, float] | None = None

    @property
    def width_pts(self) -> float:
        return self.media_box[2] - self.media_box[0]

    @property
    def height_pts(self) -> float:
        return self.media_box[3] - self.media_box[1]

    @property
    def width_in(self) -> float:
        return self.width_pts / 72.0

    @property
    def height_in(self) -> float:
        return self.height_pts / 72.0


@dataclass
class FontInfo:
    """Information about a font used in the PDF."""

    name: str
    embedded: bool
    subset: bool = False
    page: int = 0


@dataclass
class ImageInfo:
    """Information about an image in the PDF."""

    page: int
    width_px: int
    height_px: int
    effective_dpi_x: float
    effective_dpi_y: float
    color_space: str
    bits_per_component: int = 8
    # Display position on page in points (x0, y0, x1, y1)
    position: tuple[float, float, float, float] | None = None


@dataclass
class ColorSpaceInfo:
    """Information about a color space found in the PDF."""

    name: str
    cs_type: str  # DeviceRGB, DeviceCMYK, DeviceGray, ICCBased, Separation, DeviceN
    page: int = 0
    context: str = ""  # e.g. "image", "drawing", "text"


def _box_to_tuple(box: pikepdf.Array) -> tuple[float, float, float, float]:
    return (float(box[0]), float(box[1]), float(box[2]), float(box[3]))


def get_page_boxes(pdf_path: str | Path) -> list[PageBoxes]:
    """Extract page box dimensions for all pages."""
    results = []
    with pikepdf.open(pdf_path) as pdf:
        for page in pdf.pages:
            media = _box_to_tuple(page.MediaBox)
            trim = _box_to_tuple(page.TrimBox) if "/TrimBox" in page else None
            bleed = _box_to_tuple(page.BleedBox) if "/BleedBox" in page else None
            crop = _box_to_tuple(page.CropBox) if "/CropBox" in page else None
            results.append(
                PageBoxes(
                    media_box=media,
                    trim_box=trim,
                    bleed_box=bleed,
                    crop_box=crop,
                )
            )
    return results


def get_page_count(pdf_path: str | Path) -> int:
    with pikepdf.open(pdf_path) as pdf:
        return len(pdf.pages)


def get_fonts(pdf_path: str | Path) -> list[FontInfo]:
    """Extract font information from all pages."""
    fonts: list[FontInfo] = []
    seen: set[str] = set()

    with pikepdf.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            page_fonts = _extract_fonts_from_resources(page, page_num)
            for f in page_fonts:
                key = f"{f.name}:{f.embedded}"
                if key not in seen:
                    seen.add(key)
                    fonts.append(f)
    return fonts


def _extract_fonts_from_resources(page: pikepdf.Page, page_num: int) -> list[FontInfo]:
    """Extract fonts from a page's resource dictionary."""
    fonts = []
    resources = page.get("/Resources")
    if resources is None:
        return fonts

    font_dict = resources.get("/Font")
    if font_dict is None:
        return fonts

    for _name, font_ref in dict(font_dict).items():
        try:
            font_obj = font_ref
            if isinstance(font_obj, pikepdf.Stream):
                font_obj = font_ref
            base_name = str(font_obj.get("/BaseFont", "/Unknown"))
            if base_name.startswith("/"):
                base_name = base_name[1:]

            # Check for subset prefix (6 uppercase letters + '+')
            subset = "+" in base_name and len(base_name.split("+")[0]) == 6

            # Check if font is embedded
            embedded = False
            desc = font_obj.get("/FontDescriptor")
            if desc is not None:
                embedded = any(key in desc for key in ("/FontFile", "/FontFile2", "/FontFile3"))

            # Type 0 (CID) fonts: check descendant
            if str(font_obj.get("/Subtype", "")) == "/Type0":
                descendants = font_obj.get("/DescendantFonts")
                if descendants is not None and len(descendants) > 0:
                    desc_font = descendants[0]
                    desc2 = desc_font.get("/FontDescriptor")
                    if desc2 is not None:
                        embedded = any(
                            key in desc2 for key in ("/FontFile", "/FontFile2", "/FontFile3")
                        )

            fonts.append(
                FontInfo(
                    name=base_name,
                    embedded=embedded,
                    subset=subset,
                    page=page_num,
                )
            )
        except Exception:
            continue
    return fonts


def get_color_spaces(pdf_path: str | Path) -> list[ColorSpaceInfo]:
    """Extract color space information from the PDF."""
    results: list[ColorSpaceInfo] = []
    seen: set[str] = set()

    with pikepdf.open(pdf_path) as pdf:
        # Check document-level OutputIntents
        root = pdf.Root
        if "/OutputIntents" in root:
            for intent in root["/OutputIntents"]:
                if "/ICCBased" in str(intent) or "/DestOutputProfile" in intent:
                    key = "OutputIntent:ICCBased:0"
                    if key not in seen:
                        seen.add(key)
                        results.append(
                            ColorSpaceInfo(
                                name="OutputIntent",
                                cs_type="ICCBased",
                                page=0,
                                context="document",
                            )
                        )

        for page_num, page in enumerate(pdf.pages, 1):
            _extract_color_spaces_from_page(page, page_num, results, seen)

    return results


def _classify_colorspace(cs_obj: object) -> str:
    """Classify a color space object into its type string."""
    if isinstance(cs_obj, pikepdf.Name):
        name = str(cs_obj)
        if name in ("/DeviceRGB", "/DeviceCMYK", "/DeviceGray"):
            return name[1:]  # strip leading /
        return name[1:]

    if isinstance(cs_obj, pikepdf.Array) and len(cs_obj) > 0:
        cs_type = str(cs_obj[0])
        if cs_type == "/ICCBased":
            return "ICCBased"
        if cs_type == "/Separation":
            return "Separation"
        if cs_type == "/DeviceN":
            return "DeviceN"
        if cs_type == "/Indexed":
            # The base color space is the second element
            if len(cs_obj) > 1:
                return f"Indexed({_classify_colorspace(cs_obj[1])})"
            return "Indexed"
        if cs_type == "/CalGray":
            return "CalGray"
        if cs_type == "/CalRGB":
            return "CalRGB"
        if cs_type == "/Lab":
            return "Lab"
        return cs_type[1:] if cs_type.startswith("/") else cs_type

    return "Unknown"


def _extract_color_spaces_from_page(
    page: pikepdf.Page,
    page_num: int,
    results: list[ColorSpaceInfo],
    seen: set[str],
) -> None:
    """Extract color spaces from page resources."""
    resources = page.get("/Resources")
    if resources is None:
        return

    # Check ColorSpace resource dictionary
    cs_dict = resources.get("/ColorSpace")
    if cs_dict is not None:
        for cs_name, cs_obj in dict(cs_dict).items():
            cs_type = _classify_colorspace(cs_obj)
            key = f"{cs_name}:{cs_type}:{page_num}"
            if key not in seen:
                seen.add(key)
                results.append(
                    ColorSpaceInfo(
                        name=str(cs_name)[1:] if str(cs_name).startswith("/") else str(cs_name),
                        cs_type=cs_type,
                        page=page_num,
                        context="resource",
                    )
                )

    # Check XObject (images) for their color spaces
    xobjects = resources.get("/XObject")
    if xobjects is not None:
        for xo_name, xo_ref in dict(xobjects).items():
            try:
                xo = xo_ref
                if str(xo.get("/Subtype", "")) == "/Image":
                    cs = xo.get("/ColorSpace")
                    if cs is not None:
                        cs_type = _classify_colorspace(cs)
                        key = f"image:{cs_type}:{page_num}"
                        if key not in seen:
                            seen.add(key)
                            results.append(
                                ColorSpaceInfo(
                                    name=str(xo_name)[1:]
                                    if str(xo_name).startswith("/")
                                    else str(xo_name),
                                    cs_type=cs_type,
                                    page=page_num,
                                    context="image",
                                )
                            )
            except Exception:
                continue


def get_images(pdf_path: str | Path) -> list[ImageInfo]:
    """Extract image information including effective DPI using PyMuPDF."""
    results: list[ImageInfo] = []
    doc = fitz.open(str(pdf_path))
    try:
        for page_num in range(len(doc)):
            page = doc[page_num]
            image_list = page.get_images(full=True)
            for img_index, img in enumerate(image_list):
                xref = img[0]
                try:
                    img_info = doc.extract_image(xref)
                    if img_info is None:
                        continue

                    pix_width = img_info.get("width", 0)
                    pix_height = img_info.get("height", 0)
                    cs_name = img_info.get("colorspace", 0)
                    bpc = img_info.get("bpc", 8)

                    # Get the image's display dimensions on the page via transforms
                    img_rects = page.get_image_rects(img[7] if len(img) > 7 else xref)
                    if not img_rects:
                        continue

                    for rect in img_rects:
                        if rect.is_empty or rect.is_infinite:
                            continue
                        display_width_in = rect.width / 72.0
                        display_height_in = rect.height / 72.0

                        dpi_x = pix_width / display_width_in if display_width_in > 0 else 0
                        dpi_y = pix_height / display_height_in if display_height_in > 0 else 0

                        # Map colorspace number to name
                        if isinstance(cs_name, int):
                            cs_map = {1: "DeviceGray", 3: "DeviceRGB", 4: "DeviceCMYK"}
                            cs_name = cs_map.get(cs_name, f"Unknown({cs_name})")

                        results.append(
                            ImageInfo(
                                page=page_num + 1,
                                width_px=pix_width,
                                height_px=pix_height,
                                effective_dpi_x=dpi_x,
                                effective_dpi_y=dpi_y,
                                color_space=cs_name,
                                bits_per_component=bpc,
                                position=(rect.x0, rect.y0, rect.x1, rect.y1),
                            )
                        )
                except Exception:
                    continue
    finally:
        doc.close()
    return results


def get_text(pdf_path: str | Path, page_numbers: list[int] | None = None) -> dict[int, str]:
    """Extract text from specified pages (1-indexed). If None, extract all."""
    result: dict[int, str] = {}
    doc = fitz.open(str(pdf_path))
    try:
        pages = page_numbers or list(range(1, len(doc) + 1))
        for pn in pages:
            if 1 <= pn <= len(doc):
                page = doc[pn - 1]
                result[pn] = page.get_text()
    finally:
        doc.close()
    return result


@dataclass
class CoverTemplateGeometry:
    """Geometry extracted from Ingram cover template crop marks."""

    # Trim rectangle in points (x0, y0, x1, y1)
    trim_rect: tuple[float, float, float, float]
    # Spine fold lines in points (left_x, right_x), or None if not detected
    spine_fold: tuple[float, float] | None = None

    @property
    def trim_width_in(self) -> float:
        return (self.trim_rect[2] - self.trim_rect[0]) / 72

    @property
    def trim_height_in(self) -> float:
        return (self.trim_rect[3] - self.trim_rect[1]) / 72

    @property
    def spine_width_in(self) -> float | None:
        if self.spine_fold is None:
            return None
        return (self.spine_fold[1] - self.spine_fold[0]) / 72


def get_cover_template_geometry(pdf_path: str | Path) -> CoverTemplateGeometry | None:
    """Detect Ingram template crop marks and extract the trim rectangle and spine.

    Crop marks are short (~0.3") dark line segments at the corners of the
    trim rectangle, extending outward. Vertical marks at intermediate
    x-positions indicate spine fold lines.
    """
    doc = fitz.open(str(pdf_path))
    try:
        page = doc[0]
        drawings = page.get_drawings()

        h_lines: list[tuple[float, float, float]] = []  # (y, x0, x1)
        v_lines: list[tuple[float, float, float]] = []  # (x, y0, y1)

        for d in drawings:
            color = d.get("color")
            if color is None:
                continue
            # Dark color (near black)
            if not all(c < 0.3 for c in color):
                continue
            items = d["items"]
            if len(items) != 1 or items[0][0] != "l":
                continue
            rect = d["rect"]
            w_pts = rect.width
            h_pts = rect.height
            # Horizontal: narrow height, 0.1-0.5" wide
            if h_pts < 1.0 and 7 < w_pts < 40:
                h_lines.append((rect.y0, rect.x0, rect.x1))
            # Vertical: narrow width, 0.1-0.5" tall
            elif w_pts < 1.0 and 7 < h_pts < 40:
                v_lines.append((rect.x0, rect.y0, rect.y1))

        if len(h_lines) < 4 or len(v_lines) < 4:
            return None

        # Horizontal marks define top and bottom y of trim rect
        h_ys = sorted(set(round(y, 1) for y, _, _ in h_lines))
        if len(h_ys) < 2:
            return None
        top_y = min(h_ys)
        bottom_y = max(h_ys)

        # Vertical marks define edges. The outermost pair are left/right
        # of the trim rect; intermediate ones are spine fold lines.
        v_xs = sorted(set(round(x, 1) for x, _, _ in v_lines))
        if len(v_xs) < 2:
            return None
        left_x = min(v_xs)
        right_x = max(v_xs)

        spine_fold = None
        inner_xs = [x for x in v_xs if x > left_x + 1 and x < right_x - 1]
        if len(inner_xs) == 2:
            spine_fold = (inner_xs[0], inner_xs[1])

        trim_rect = (left_x, top_y, right_x, bottom_y)
        return CoverTemplateGeometry(trim_rect=trim_rect, spine_fold=spine_fold)
    finally:
        doc.close()


def get_content_bbox(
    pdf_path: str | Path, page_num: int = 0
) -> tuple[float, float, float, float] | None:
    """Get the bounding box of all visible content on a page, in points.

    Uses PyMuPDF to find the union of all drawings, images, and text blocks,
    excluding thin lines that look like crop marks or guides.
    """
    doc = fitz.open(str(pdf_path))
    try:
        page = doc[page_num]
        x0 = float("inf")
        y0 = float("inf")
        x1 = float("-inf")
        y1 = float("-inf")

        found = False

        # Images
        for img in page.get_images(full=True):
            xref = img[0]
            rects = page.get_image_rects(img[7] if len(img) > 7 else xref)
            for r in rects:
                if r.is_empty or r.is_infinite:
                    continue
                found = True
                x0 = min(x0, r.x0)
                y0 = min(y0, r.y0)
                x1 = max(x1, r.x1)
                y1 = max(y1, r.y1)

        # Drawings — skip thin lines (crop marks, guides)
        for d in page.get_drawings():
            rect = d["rect"]
            if rect.is_empty or rect.is_infinite:
                continue
            # Skip very thin elements (likely crop marks or fold lines)
            if rect.width < 2.0 or rect.height < 2.0:
                continue
            found = True
            x0 = min(x0, rect.x0)
            y0 = min(y0, rect.y0)
            x1 = max(x1, rect.x1)
            y1 = max(y1, rect.y1)

        # Text blocks
        for block in page.get_text("dict")["blocks"]:
            if block["type"] != 0:  # text block
                continue
            r = fitz.Rect(block["bbox"])
            if r.is_empty or r.is_infinite:
                continue
            found = True
            x0 = min(x0, r.x0)
            y0 = min(y0, r.y0)
            x1 = max(x1, r.x1)
            y1 = max(y1, r.y1)

        if not found:
            return None
        return (x0, y0, x1, y1)
    finally:
        doc.close()


def has_output_intents(pdf_path: str | Path) -> bool:
    """Check if the PDF has OutputIntents (PDF/X indicator)."""
    with pikepdf.open(pdf_path) as pdf:
        return "/OutputIntents" in pdf.Root


def has_pdfx_output_intent(pdf_path: str | Path) -> bool:
    """Check if the PDF has a PDF/X-conformant OutputIntent."""
    with pikepdf.open(pdf_path) as pdf:
        if "/OutputIntents" not in pdf.Root:
            return False
        for intent in pdf.Root["/OutputIntents"]:
            if "GTS_PDFX" in str(intent.get("/S", "")):
                return True
    return False
