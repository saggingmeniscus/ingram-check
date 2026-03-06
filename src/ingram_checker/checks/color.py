"""Color space, spot color, and ICC profile checks."""

from __future__ import annotations

from pathlib import Path

from ..models import BookSpec, CheckResult, CheckStatus, ColorType, ProductType, Severity
from ..pdf_info import get_color_spaces, has_pdfx_output_intent
from .base import BaseCheck


class ICCProfileCheck(BaseCheck):
    name = "icc_profiles"
    description = "No ICC profiles (except PDF/X OutputIntent)"

    def run(self, pdf_path: Path, spec: BookSpec) -> list[CheckResult]:
        color_spaces = get_color_spaces(pdf_path)
        has_pdfx = has_pdfx_output_intent(pdf_path)

        # Filter out document-level OutputIntents if they're PDF/X conformant
        icc_entries = []
        for cs in color_spaces:
            if cs.cs_type != "ICCBased":
                continue
            if cs.context == "document" and has_pdfx:
                continue  # PDF/X OutputIntent ICC profile is expected
            icc_entries.append(cs)

        if not icc_entries:
            msg = "No problematic ICC profiles"
            if has_pdfx:
                msg += " (PDF/X OutputIntent present — OK)"
            return [CheckResult(
                check_name=self.name,
                status=CheckStatus.PASS,
                message=msg,
                severity=Severity.ERROR,
            )]

        details = [
            f"  {cs.name} ({cs.context}, page {cs.page})" for cs in icc_entries
        ]
        return [CheckResult(
            check_name=self.name,
            status=CheckStatus.FAIL,
            message=f"{len(icc_entries)} ICC profile(s) found in page resources",
            severity=Severity.ERROR,
            details=details,
            fixable=True,
        )]


class SpotColorCheck(BaseCheck):
    name = "spot_colors"
    description = "No Separation or DeviceN color spaces"

    def run(self, pdf_path: Path, spec: BookSpec) -> list[CheckResult]:
        color_spaces = get_color_spaces(pdf_path)
        spot_entries = [
            cs for cs in color_spaces
            if cs.cs_type in ("Separation", "DeviceN")
        ]

        if not spot_entries:
            return [CheckResult(
                check_name=self.name,
                status=CheckStatus.PASS,
                message="No spot colors found",
                severity=Severity.ERROR,
            )]

        details = [
            f"  {cs.name} ({cs.cs_type}, page {cs.page})" for cs in spot_entries
        ]
        return [CheckResult(
            check_name=self.name,
            status=CheckStatus.FAIL,
            message=f"{len(spot_entries)} spot color(s) found",
            severity=Severity.ERROR,
            details=details,
            fixable=True,
        )]


class ColorSpaceCheck(BaseCheck):
    name = "color_space"
    description = "Color space must match book type (Grayscale for BW, CMYK for color)"

    def run(self, pdf_path: Path, spec: BookSpec) -> list[CheckResult]:
        color_spaces = get_color_spaces(pdf_path)
        product_label = spec.product_type.value

        if spec.color_type == ColorType.BW:
            bad = [
                cs for cs in color_spaces
                if cs.cs_type in ("DeviceRGB", "DeviceCMYK", "CalRGB")
                and cs.context in ("image", "resource")
            ]
            if bad:
                details = [
                    f"  {cs.name}: {cs.cs_type} (page {cs.page})" for cs in bad
                ]
                return [CheckResult(
                    check_name=self.name,
                    status=CheckStatus.FAIL,
                    message=f"BW {product_label} has {len(bad)} non-grayscale color space(s)",
                    severity=Severity.ERROR,
                    details=details,
                    fixable=True,
                    data={"target": "grayscale"},
                )]
        else:
            rgb_entries = [
                cs for cs in color_spaces
                if cs.cs_type in ("DeviceRGB", "CalRGB")
                and cs.context in ("image", "resource")
            ]
            if rgb_entries:
                details = [
                    f"  {cs.name}: {cs.cs_type} (page {cs.page})"
                    for cs in rgb_entries
                ]
                return [CheckResult(
                    check_name=self.name,
                    status=CheckStatus.FAIL,
                    message=f"Color {product_label} has {len(rgb_entries)} RGB color space(s) — must be CMYK",
                    severity=Severity.ERROR,
                    details=details,
                    fixable=True,
                    data={"target": "cmyk"},
                )]

        return [CheckResult(
            check_name=self.name,
            status=CheckStatus.PASS,
            message=f"Color spaces are correct for {spec.color_type.value} {product_label}",
            severity=Severity.ERROR,
        )]
