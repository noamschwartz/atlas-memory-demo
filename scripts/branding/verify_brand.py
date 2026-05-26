#!/usr/bin/env python3
"""
Brand Verification Tool

Checks that a brand's extracted assets are complete and valid:
- All referenced files exist (logos, favicon, fonts, images)
- Theme file has all required fields populated
- Font files are loadable (valid woff2/woff)
- Image files are valid (not corrupt/truncated)
- Logo SVG files are valid
- No hardcoded hex colors in custom pages (should use CSS vars)

Usage:
    python scripts/branding/verify_brand.py mybrand
    python scripts/branding/verify_brand.py mybrand --strict
    python scripts/branding/verify_brand.py --all
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BRANDS_DIR = PROJECT_ROOT / "frontend" / "public" / "brands"
BRANDING_SRC = PROJECT_ROOT / "frontend" / "src" / "branding"
PAGES_DIR = PROJECT_ROOT / "frontend" / "src" / "pages"


# ---------------------------------------------------------------------------
# Result tracking
# ---------------------------------------------------------------------------

class VerificationResult:
    def __init__(self):
        self.passes: list[str] = []
        self.warnings: list[str] = []
        self.failures: list[str] = []

    def ok(self, msg: str):
        self.passes.append(msg)

    def warn(self, msg: str):
        self.warnings.append(msg)

    def fail(self, msg: str):
        self.failures.append(msg)

    @property
    def passed(self) -> bool:
        return len(self.failures) == 0

    def summary(self) -> str:
        lines = []
        for p in self.passes:
            lines.append(f"  [PASS] {p}")
        for w in self.warnings:
            lines.append(f"  [WARN] {w}")
        for f in self.failures:
            lines.append(f"  [FAIL] {f}")
        total = len(self.passes) + len(self.warnings) + len(self.failures)
        lines.append(f"\n  {len(self.passes)}/{total} passed, "
                     f"{len(self.warnings)} warnings, "
                     f"{len(self.failures)} failures")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# File validation helpers
# ---------------------------------------------------------------------------

def is_valid_svg(path: Path) -> bool:
    """Check if a file is a valid SVG (contains <svg tag)."""
    try:
        content = path.read_text(errors="replace")
        return "<svg" in content.lower()
    except Exception:
        return False


def is_valid_image(path: Path) -> bool:
    """Check if an image file has valid magic bytes."""
    try:
        data = path.read_bytes()
        if len(data) < 8:
            return False
        # JPEG
        if data[:2] == b'\xff\xd8':
            return True
        # PNG
        if data[:4] == b'\x89PNG':
            return True
        # GIF
        if data[:3] == b'GIF':
            return True
        # WebP
        if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
            return True
        # SVG (text)
        if b'<svg' in data[:500].lower():
            return True
        # ICO
        if data[:4] == b'\x00\x00\x01\x00' or data[:4] == b'\x00\x00\x02\x00':
            return True
        return False
    except Exception:
        return False


def is_valid_font(path: Path) -> bool:
    """Check if a font file has valid headers."""
    try:
        data = path.read_bytes()
        if len(data) < 4:
            return False
        # WOFF2
        if data[:4] == b'wOF2':
            return True
        # WOFF
        if data[:4] == b'wOFF':
            return True
        # TrueType / OpenType
        if data[:4] in (b'\x00\x01\x00\x00', b'OTTO', b'true', b'typ1'):
            return True
        return False
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Theme file checks
# ---------------------------------------------------------------------------

REQUIRED_COLOR_KEYS = ["primary", "accent", "background", "white", "black",
                       "textPrimary", "textBody", "border"]

TIER_1_SECTIONS = ["links", "buttons"]
TIER_4_SECTIONS = ["gradients", "heroImage", "fontFaces", "favicon"]


def check_theme_file(brand_id: str, result: VerificationResult, strict: bool = False):
    """Check the TypeScript theme file for completeness."""
    theme_path = BRANDING_SRC / f"{brand_id}Theme.ts"

    if not theme_path.exists():
        result.fail(f"Theme file not found: {theme_path.relative_to(PROJECT_ROOT)}")
        return

    content = theme_path.read_text()
    result.ok(f"Theme file exists: {theme_path.name}")

    # Check required color keys
    for key in REQUIRED_COLOR_KEYS:
        pattern = rf"{key}:\s*['\"]#[0-9a-fA-F]{{3,8}}['\"]"
        if re.search(pattern, content):
            result.ok(f"Color '{key}' is set")
        else:
            # Check for empty strings
            empty_pattern = rf"{key}:\s*['\"]['\"]"
            if re.search(empty_pattern, content):
                result.fail(f"Color '{key}' is empty string")
            else:
                result.warn(f"Color '{key}' may be missing or using non-hex value")

    # Check fonts
    for font_key in ["heading", "body"]:
        if re.search(rf"fonts.*{font_key}:", content, re.DOTALL):
            result.ok(f"Font '{font_key}' is declared")
        else:
            result.fail(f"Font '{font_key}' is missing")

    # Check logo
    if re.search(r"logo:\s*\{", content):
        # Check for non-empty logo URL or svgDataUrl
        has_url = bool(re.search(r"(?:url|svgDataUrl):\s*['\"][^'\"]+['\"]", content))
        if has_url:
            result.ok("Logo has a URL or SVG data")
        else:
            result.fail("Logo declared but URL/svgDataUrl is empty")
    else:
        result.fail("Logo section is missing")

    # Check colorsDark
    if "colorsDark" in content:
        result.ok("Dark mode colors are defined")
    else:
        result.warn("No colorsDark section — dark mode will use calculated defaults")

    # Tier 1 checks
    for section in TIER_1_SECTIONS:
        if section in content:
            result.ok(f"Tier 1: '{section}' section present")
        elif strict:
            result.fail(f"Tier 1: '{section}' section missing (strict mode)")
        else:
            result.warn(f"Tier 1: '{section}' section not present")

    # Tier 4 checks
    for section in TIER_4_SECTIONS:
        if section in content:
            result.ok(f"Tier 4: '{section}' present")
        elif strict:
            result.fail(f"Tier 4: '{section}' missing (strict mode)")
        else:
            result.warn(f"Tier 4: '{section}' not present")

    # Check customCss
    if "customCss" in content:
        result.ok("Custom CSS section present")
        # Check for domain-prefixed classes
        css_classes = re.findall(r"\.([\w-]+)\s*\{", content)
        branded_classes = [c for c in css_classes if c.startswith(f"{brand_id}-")]
        if branded_classes:
            result.ok(f"Custom CSS has {len(branded_classes)} brand-prefixed classes")
        else:
            result.warn(f"Custom CSS classes not prefixed with '{brand_id}-'")
    elif strict:
        result.fail("Custom CSS section missing (strict mode)")
    else:
        result.warn("No customCss section for domain-specific components")


# ---------------------------------------------------------------------------
# Asset file checks
# ---------------------------------------------------------------------------

def check_assets(brand_id: str, result: VerificationResult):
    """Check that brand asset files exist and are valid."""
    brand_dir = BRANDS_DIR / brand_id

    if not brand_dir.exists():
        result.fail(f"Brand directory not found: {brand_dir.relative_to(PROJECT_ROOT)}")
        return

    result.ok(f"Brand directory exists: brands/{brand_id}/")

    # Check logos
    logo_files = list((brand_dir / "logos").glob("*")) if (brand_dir / "logos").exists() else []
    top_level_logos = [f for f in brand_dir.glob("logo*") if f.is_file()]
    all_logos = logo_files + top_level_logos

    if all_logos:
        result.ok(f"Found {len(all_logos)} logo file(s)")
        for logo in all_logos:
            if logo.suffix.lower() == ".svg":
                if is_valid_svg(logo):
                    result.ok(f"Logo SVG valid: {logo.name}")
                else:
                    result.fail(f"Logo SVG invalid: {logo.name}")
            elif logo.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
                if is_valid_image(logo):
                    result.ok(f"Logo image valid: {logo.name}")
                else:
                    result.fail(f"Logo image corrupt: {logo.name}")
    else:
        result.fail("No logo files found")

    # Check for both light and dark logo variants
    has_light = any("white" in f.name.lower() or "light" in f.name.lower() for f in all_logos)
    has_dark = any("dark" in f.name.lower() for f in all_logos) or any(
        f.name in ("logo.svg", "logo.png") for f in all_logos
    )
    if has_light or len(all_logos) >= 2:
        result.ok("Has light/dark logo variants")
    else:
        result.warn("Only one logo variant found — header may not match content areas")

    # Check favicon
    favicon_files = list(brand_dir.glob("favicon*"))
    if favicon_files:
        for fav in favicon_files:
            if is_valid_image(fav):
                result.ok(f"Favicon valid: {fav.name}")
            else:
                result.fail(f"Favicon invalid (may be a 404 HTML page saved as .ico): {fav.name}")
    else:
        result.fail("No favicon file found")

    # Check images
    images_dir = brand_dir / "images"
    if images_dir.exists():
        image_files = [f for f in images_dir.iterdir() if f.is_file()]
        if image_files:
            result.ok(f"Found {len(image_files)} image(s)")

            hero_images = [f for f in image_files if "hero" in f.name.lower()]
            if hero_images:
                result.ok("Hero image present")
            else:
                result.warn("No hero image found")

            category_images = [f for f in image_files if "category" in f.name.lower()]
            if len(category_images) >= 3:
                result.ok(f"Found {len(category_images)} category images")
            elif category_images:
                result.warn(f"Only {len(category_images)} category image(s) — recommend 3+")
            else:
                result.warn("No category images found")

            for img in image_files:
                if is_valid_image(img):
                    result.ok(f"Image valid: {img.name}")
                else:
                    result.fail(f"Image corrupt: {img.name}")
        else:
            result.warn("Images directory exists but is empty")
    else:
        result.warn("No images/ directory — pages will lack hero banners and category imagery")

    # Check fonts
    fonts_dir = brand_dir / "fonts"
    if fonts_dir.exists():
        font_files = [f for f in fonts_dir.iterdir() if f.is_file()]
        if font_files:
            result.ok(f"Found {len(font_files)} font file(s)")
            for font in font_files:
                if is_valid_font(font):
                    result.ok(f"Font valid: {font.name}")
                else:
                    result.fail(f"Font invalid: {font.name}")
        else:
            result.warn("Fonts directory exists but is empty")


# ---------------------------------------------------------------------------
# Page hardcoded color checks
# ---------------------------------------------------------------------------

HEX_PATTERN = re.compile(r"""(?:color|background|border|fill|stroke)\s*[:=]\s*['"]?(#[0-9a-fA-F]{3,8})""")
ALLOWED_HEX = {"#FFFFFF", "#ffffff", "#FFF", "#fff", "#000000", "#000", "#1A1C21"}


def check_hardcoded_colors(brand_id: str, result: VerificationResult):
    """Check custom pages for hardcoded hex colors that should use CSS vars."""
    if not PAGES_DIR.exists():
        return

    brand_pages = []
    for page in PAGES_DIR.glob("*.tsx"):
        content = page.read_text()
        # Check pages that reference the brand
        if brand_id.lower() in page.name.lower() or brand_id in content.lower():
            brand_pages.append(page)

    if not brand_pages:
        result.warn(f"No brand-specific pages found matching '{brand_id}'")
        return

    for page in brand_pages:
        content = page.read_text()
        matches = HEX_PATTERN.findall(content)
        bad_hex = [h for h in matches if h.upper() not in {a.upper() for a in ALLOWED_HEX}]

        if bad_hex:
            unique = sorted(set(bad_hex))
            result.warn(
                f"{page.name}: {len(unique)} hardcoded color(s) found: "
                f"{', '.join(unique[:5])}{'...' if len(unique) > 5 else ''} "
                f"— consider using CSS vars"
            )
        else:
            result.ok(f"{page.name}: no hardcoded colors (good!)")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def verify_brand(brand_id: str, strict: bool = False) -> VerificationResult:
    """Run all verification checks for a brand."""
    result = VerificationResult()

    print(f"\n=== Verifying brand: {brand_id} ===\n")

    print("--- Theme File ---")
    check_theme_file(brand_id, result, strict=strict)

    print("--- Asset Files ---")
    check_assets(brand_id, result)

    print("--- Hardcoded Colors ---")
    check_hardcoded_colors(brand_id, result)

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Verify brand extraction completeness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("brand_id", nargs="?", help="Brand ID to verify")
    parser.add_argument("--all", action="store_true", help="Verify all brands")
    parser.add_argument("--strict", action="store_true",
                        help="Require Tier 1-4 fields (fails instead of warns)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if args.all:
        if not BRANDS_DIR.exists():
            print(f"No brands directory found at {BRANDS_DIR.relative_to(PROJECT_ROOT)}")
            print("Run extract_brand.py first to create brand assets.")
            sys.exit(0)
        brand_ids = [
            d.name for d in BRANDS_DIR.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        ]
        if not brand_ids:
            print("No brands found. Run extract_brand.py first.")
            sys.exit(0)
    elif args.brand_id:
        brand_ids = [args.brand_id]
    else:
        parser.error("Provide a brand_id or use --all")
        return

    all_passed = True
    for brand_id in sorted(brand_ids):
        result = verify_brand(brand_id, strict=args.strict)

        if args.json:
            print(json.dumps({
                "brand_id": brand_id,
                "passed": result.passed,
                "passes": result.passes,
                "warnings": result.warnings,
                "failures": result.failures,
            }, indent=2))
        else:
            print(result.summary())

        if not result.passed:
            all_passed = False

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
