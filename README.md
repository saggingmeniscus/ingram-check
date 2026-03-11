# ingram-check

A command-line tool that checks PDF files for [Ingram Lightning Source](https://www.ingramcontent.com/publishers/print) compliance and auto-fixes common issues.

## Requirements

- Python 3.11+
- [Ghostscript](https://www.ghostscript.com/) (`gs`) — optional; use `--use-ghostscript` to prefer it over the native Python backend

## Installation

```bash
# Install with uv (recommended)
uv tool install .

# Or install in a virtual environment
uv sync
```

After installation, the `ingram-check` command is available globally.

## Usage

### Interior PDFs

```bash
# Basic check — auto-detects page size
ingram-check interior book.pdf

# Specify trim size and color type
ingram-check interior book.pdf -t 6x9 -c bw

# With bleed
ingram-check interior book.pdf -t 6x9 --bleed

# Auto-fix (ICC removal, color conversion, crop stripping, downsampling, etc.)
ingram-check interior book.pdf --fix

# Unsafe fixes (includes upsampling low-res images)
ingram-check interior book.pdf --fix-unsafe

# JSON output
ingram-check interior book.pdf --format json
```

If `--trim-size` is omitted, the tool detects the page size from the PDF and reports it. An error is shown only if pages have inconsistent dimensions.

Trim sizes can be specified as dimensions (`6x9`, `5.5x8.5`) or aliases (`trade`, `a5`, `letter`, `digest`, `royal`, `mass market`).

### Cover PDFs

```bash
ingram-check cover cover.pdf -t 6x9
ingram-check cover cover.pdf -t 6x9 -b casewrap --fix
```

### Listing checks

```bash
ingram-check interior --list-checks
ingram-check cover --list-checks
```

Individual checks can be toggled with `-e` (enable) and `-d` (disable):

```bash
ingram-check interior book.pdf -e bracketed_text -d margins
```

## Checks

### Interior (15 checks)

| Check | Severity | Auto-fixable |
|-------|----------|:------------:|
| Font embedding | Error | |
| Page count (must be even) | Error | Yes |
| Page size consistency | Error | |
| Bleed dimensions | Error | |
| ICC profile removal | Error | Yes |
| Spot color removal | Error | Yes |
| Color space (Grayscale/CMYK) | Error | Yes |
| Crop/registration marks | Error | Yes |
| Ink density (warn 240%, error 300%) | Error | |
| Image resolution | Error/Warning | Yes* |
| Manufacturing statements | Error | |
| Paper certification claims | Error | |
| Bracketed text | Warning | |
| Margins (0.5" recommended) | Warning | |
| PDF/X compliance | Warning | |

*Downsampling high-res images is a safe fix (`--fix`). Upsampling low-res images requires `--fix-unsafe`.

### Cover (9 checks)

Font embedding, page count, cover size, ICC profiles, spot colors, color space, ink density, resolution, and barcode (manual verification).

## Auto-fix

`--fix` applies safe, lossless corrections:
- Pad odd page count with a blank page
- Remove ICC profiles from page resources and image XObjects
- Convert spot colors to CMYK
- Convert RGB to Grayscale or CMYK
- Strip crop/registration marks by setting CropBox = TrimBox
- Downsample images above 375ppi to 300ppi

`--fix-unsafe` additionally applies fixes that may degrade quality:
- Upsample images below 300ppi (adds pixels via bicubic interpolation, but no real detail)

Fixed PDFs are written to `<filename>_fixed.pdf` in the same directory.

By default, all fixes use native Python (pikepdf + Pillow). Pass `--use-ghostscript` to use Ghostscript's `pdfwrite` device instead.

## License

MIT — see [LICENSE](LICENSE).
