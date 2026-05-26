#!/usr/bin/env python3
"""
Brand Asset Extraction Tool

Extracts a complete brand kit from a target website URL:
- Logos (SVG/PNG, light and dark variants)
- Favicon
- Colors (primary, accent, background, text, border)
- Fonts (families, weights, @font-face sources)
- Hero image (from homepage hero section or og:image)
- Category/section images (3-5 from nav or featured sections)
- Component styles (button radius, shadows, gradients)

Output structure:
    frontend/public/brands/{id}/
        logos/logo.svg, logo-dark.svg, logo-icon.svg
        images/hero.jpg, og-image.jpg, category-*.jpg
        fonts/{fontname}.woff2
        favicon.ico
    brand-kit.json   (raw extraction data)

Usage:
    python scripts/branding/extract_brand.py https://www.example.com mybrand
    python scripts/branding/extract_brand.py https://www.example.com mybrand --firecrawl
    python scripts/branding/extract_brand.py https://www.example.com mybrand --skip-images
"""

import argparse
import datetime
import json
import os
import re
import shutil
import sys
import urllib.parse
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BRANDS_DIR = PROJECT_ROOT / "frontend" / "public" / "brands"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class LogoAsset:
    url: str
    variant: str  # "primary", "dark", "icon"
    format: str   # "svg", "png", "jpg"
    local_path: Optional[str] = None


@dataclass
class ImageAsset:
    url: str
    role: str  # "hero", "og-image", "category"
    alt: str = ""
    local_path: Optional[str] = None


@dataclass
class FontAsset:
    family: str
    weight: str = "400"
    style: str = "normal"
    src_url: Optional[str] = None
    local_path: Optional[str] = None


@dataclass
class BrandKit:
    """Complete extracted brand data."""
    brand_id: str
    source_url: str
    colors: dict = field(default_factory=dict)
    colors_dark: dict = field(default_factory=dict)
    fonts: dict = field(default_factory=lambda: {
        "heading": "", "body": "", "fallback": ""
    })
    spacing: dict = field(default_factory=lambda: {
        "borderRadius": "6px", "borderRadiusSmall": "4px"
    })
    logos: list = field(default_factory=list)
    images: list = field(default_factory=list)
    font_assets: list = field(default_factory=list)
    favicon_url: Optional[str] = None
    favicon_local: Optional[str] = None
    gradients: dict = field(default_factory=dict)
    buttons: dict = field(default_factory=dict)
    links: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def download_file(url: str, dest: Path, *, timeout: int = 30) -> bool:
    """Download a file, return True on success."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout, stream=True)
        resp.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(8192):
                f.write(chunk)
        return True
    except Exception as exc:
        print(f"  [WARN] Failed to download {url}: {exc}")
        return False


def resolve_url(base: str, href: str) -> str:
    """Resolve a potentially relative URL against a base."""
    if not href:
        return ""
    if href.startswith("data:"):
        return href
    return urllib.parse.urljoin(base, href)


def fetch_html(url: str, timeout: int = 30) -> Optional[BeautifulSoup]:
    """Fetch and parse HTML from a URL."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except Exception as exc:
        print(f"  [WARN] Failed to fetch {url}: {exc}")
        return None


# ---------------------------------------------------------------------------
# Extraction: Logos
# ---------------------------------------------------------------------------

def extract_logos(soup: BeautifulSoup, base_url: str) -> list[LogoAsset]:
    """Find logo images using common heuristics."""
    candidates = []

    # Strategy 1: <img> elements with "logo" in src, alt, or class
    for img in soup.find_all("img"):
        attrs_text = " ".join([
            img.get("src", ""), img.get("alt", ""),
            " ".join(img.get("class", [])),
            img.get("id", ""),
        ]).lower()

        if "logo" not in attrs_text:
            continue

        src = resolve_url(base_url, img.get("src", ""))
        if not src:
            continue

        in_header = bool(img.find_parent(["header", "nav"]))
        fmt = "svg" if ".svg" in src or src.startswith("data:image/svg") else "png"
        variant = "primary" if in_header else "dark"
        candidates.append(LogoAsset(url=src, variant=variant, format=fmt))

    # Strategy 2: Inline SVGs in header/nav with logo-related attributes
    for svg in soup.select("header svg, nav svg, [class*='logo'] svg, [id*='logo'] svg"):
        svg_str = str(svg)
        if len(svg_str) < 50:
            continue
        data_url = "data:image/svg+xml," + urllib.parse.quote(svg_str)
        candidates.append(LogoAsset(url=data_url, variant="primary", format="svg"))

    # Strategy 3: <link rel="icon"> (sometimes a simplified logo)
    for link in soup.find_all("link", rel=lambda r: r and "icon" in " ".join(r).lower()):
        href = resolve_url(base_url, link.get("href", ""))
        if href and ".svg" in href:
            candidates.append(LogoAsset(url=href, variant="icon", format="svg"))

    # Deduplicate by URL
    seen = set()
    unique = []
    for logo in candidates:
        key = logo.url[:200]
        if key not in seen:
            seen.add(key)
            unique.append(logo)

    return unique


# ---------------------------------------------------------------------------
# Extraction: Favicon
# ---------------------------------------------------------------------------

def extract_favicon(soup: BeautifulSoup, base_url: str) -> Optional[str]:
    """Find the favicon URL."""
    for link in soup.find_all("link", rel=lambda r: r and "icon" in " ".join(r).lower()):
        href = resolve_url(base_url, link.get("href", ""))
        if href:
            return href

    # Fallback: try /favicon.ico
    parsed = urllib.parse.urlparse(base_url)
    fallback = f"{parsed.scheme}://{parsed.netloc}/favicon.ico"
    try:
        resp = requests.head(fallback, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            return fallback
    except Exception:
        pass

    return None


# ---------------------------------------------------------------------------
# Extraction: Images (hero, og:image, category)
# ---------------------------------------------------------------------------

def extract_images(soup: BeautifulSoup, base_url: str) -> list[ImageAsset]:
    """Extract hero images, og:image, and category/section images."""
    images = []

    # og:image
    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        images.append(ImageAsset(
            url=resolve_url(base_url, og["content"]),
            role="og-image",
            alt="Open Graph image",
        ))

    # Hero images: look in first large sections, banners, hero elements
    hero_selectors = [
        "[class*='hero'] img",
        "[class*='banner'] img",
        "[class*='Hero'] img",
        "[class*='Banner'] img",
        "[class*='masthead'] img",
        "section:first-of-type img",
        "[role='banner'] img",
    ]
    for sel in hero_selectors:
        for img in soup.select(sel):
            src = resolve_url(base_url, img.get("src", ""))
            if src and not src.startswith("data:") and len(src) > 20:
                images.append(ImageAsset(
                    url=src,
                    role="hero",
                    alt=img.get("alt", "Hero image"),
                ))
                break
        if any(i.role == "hero" for i in images):
            break

    # Hero from CSS background-image (common pattern)
    for el in soup.select("[class*='hero'], [class*='banner'], [class*='masthead']"):
        style = el.get("style", "")
        bg_match = re.search(r"background-image:\s*url\(['\"]?([^'\")\s]+)", style)
        if bg_match:
            images.append(ImageAsset(
                url=resolve_url(base_url, bg_match.group(1)),
                role="hero",
                alt="Hero background",
            ))
            break

    # Category images: from nav links, category grids, featured sections
    category_selectors = [
        "nav a img",
        "[class*='category'] img",
        "[class*='Category'] img",
        "[class*='department'] img",
        "[class*='collection'] img",
        "[class*='featured'] img",
    ]
    cat_count = 0
    seen_urls = {i.url for i in images}
    for sel in category_selectors:
        for img in soup.select(sel):
            src = resolve_url(base_url, img.get("src", ""))
            if src and src not in seen_urls and not src.startswith("data:"):
                images.append(ImageAsset(
                    url=src,
                    role="category",
                    alt=img.get("alt", f"Category {cat_count + 1}"),
                ))
                seen_urls.add(src)
                cat_count += 1
                if cat_count >= 6:
                    break
        if cat_count >= 6:
            break

    return images


# ---------------------------------------------------------------------------
# Extraction: Colors (from inline styles, meta theme-color, CSS vars)
# ---------------------------------------------------------------------------

def extract_colors_from_html(soup: BeautifulSoup) -> dict:
    """Extract colors from HTML meta tags and common patterns."""
    colors = {}

    # theme-color meta
    tc = soup.find("meta", attrs={"name": "theme-color"})
    if tc and tc.get("content"):
        colors["primary"] = tc["content"]

    # msapplication-TileColor
    ms = soup.find("meta", attrs={"name": "msapplication-TileColor"})
    if ms and ms.get("content"):
        colors.setdefault("primary", ms["content"])

    return colors


# ---------------------------------------------------------------------------
# Extraction: Fonts (from <link> and <style> tags)
# ---------------------------------------------------------------------------

def extract_fonts_from_html(soup: BeautifulSoup, base_url: str) -> tuple[dict, list[FontAsset]]:
    """Extract font families and @font-face sources."""
    families = set()
    assets = []

    # Google Fonts links
    for link in soup.find_all("link", href=True):
        href = link["href"]
        if "fonts.googleapis.com" in href:
            fam_match = re.findall(r"family=([^&:]+)", href)
            for fam in fam_match:
                families.add(urllib.parse.unquote_plus(fam.replace("+", " ")))

    # @font-face in <style> blocks
    for style in soup.find_all("style"):
        text = style.string or ""
        for match in re.finditer(
            r"@font-face\s*\{([^}]+)\}", text, re.DOTALL
        ):
            block = match.group(1)
            fam_m = re.search(r"font-family:\s*['\"]?([^'\";\n]+)", block)
            src_m = re.search(r"src:\s*([^;]+)", block)
            weight_m = re.search(r"font-weight:\s*(\S+)", block)

            if fam_m:
                family = fam_m.group(1).strip().strip("'\"")
                families.add(family)

                src_url = None
                if src_m:
                    url_match = re.search(r"url\(['\"]?([^'\")\s]+)", src_m.group(1))
                    if url_match:
                        src_url = resolve_url(base_url, url_match.group(1))

                assets.append(FontAsset(
                    family=family,
                    weight=weight_m.group(1) if weight_m else "400",
                    src_url=src_url,
                ))

    font_list = sorted(families)
    fonts = {
        "heading": f"'{font_list[0]}', sans-serif" if font_list else "'Inter', sans-serif",
        "body": f"'{font_list[1] if len(font_list) > 1 else font_list[0]}', sans-serif" if font_list else "'Inter', sans-serif",
        "fallback": "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    }

    return fonts, assets


# ---------------------------------------------------------------------------
# Firecrawl extraction (optional, higher quality)
# ---------------------------------------------------------------------------

def extract_via_firecrawl(url: str) -> Optional[dict]:
    """Use Firecrawl API for comprehensive extraction. Returns raw branding dict."""
    api_key = os.environ.get("FIRECRAWL_API_KEY")
    if not api_key:
        return None

    try:
        from firecrawl import FirecrawlApp
        app = FirecrawlApp(api_key=api_key)
        result = app.scrape_url(url, params={"formats": ["branding"]})
        return result.get("branding")
    except ImportError:
        print("  [INFO] firecrawl package not installed, skipping Firecrawl extraction")
        return None
    except Exception as exc:
        print(f"  [WARN] Firecrawl extraction failed: {exc}")
        return None


# ---------------------------------------------------------------------------
# Main extraction orchestrator
# ---------------------------------------------------------------------------

def extract_brand(url: str, brand_id: str, *, use_firecrawl: bool = False,
                  skip_images: bool = False) -> BrandKit:
    """Run the full extraction pipeline."""
    kit = BrandKit(brand_id=brand_id, source_url=url)

    # Try Firecrawl first if requested
    fc_data = None
    if use_firecrawl:
        print("[1/6] Attempting Firecrawl extraction...")
        fc_data = extract_via_firecrawl(url)
        if fc_data:
            print("  [OK] Firecrawl data received")
            kit.colors = {
                "primary": fc_data.get("colors", {}).get("primary", "#0077CC"),
                "accent": fc_data.get("colors", {}).get("accent", "#00BFB3"),
                "background": fc_data.get("colors", {}).get("background", "#FFFFFF"),
                "white": "#FFFFFF",
                "black": fc_data.get("colors", {}).get("textPrimary", "#1A1C21"),
                "textPrimary": fc_data.get("colors", {}).get("textPrimary", "#1A1C21"),
                "textBody": fc_data.get("colors", {}).get("textPrimary", "#505050"),
                "border": "#D3DAE6",
            }
            # Firecrawl font data
            fc_fonts = fc_data.get("fonts", [])
            if fc_fonts:
                heading_font = next((f["family"] for f in fc_fonts if f.get("role") == "heading"), None)
                body_font = next((f["family"] for f in fc_fonts if f.get("role") == "body"), None)
                if heading_font:
                    kit.fonts["heading"] = f"'{heading_font}', sans-serif"
                if body_font:
                    kit.fonts["body"] = f"'{body_font}', sans-serif"

            # Firecrawl logo
            fc_images = fc_data.get("images", {})
            if fc_images.get("logo"):
                kit.logos.append(LogoAsset(
                    url=fc_images["logo"],
                    variant="primary",
                    format="svg" if "svg" in fc_images["logo"][:50] else "png",
                ))

            # Component styles
            fc_components = fc_data.get("components", {})
            if fc_components.get("buttonPrimary"):
                btn = fc_components["buttonPrimary"]
                kit.buttons = {
                    "primary": {
                        "backgroundColor": btn.get("background", kit.colors.get("primary", "#0077CC")),
                        "textColor": btn.get("textColor", "#FFFFFF"),
                        "borderRadius": btn.get("borderRadius", "6px"),
                    }
                }

            kit.metadata["firecrawl"] = True
            kit.metadata["personality"] = fc_data.get("personality", {})
        else:
            print("  [SKIP] Firecrawl not available, falling back to HTML parsing")
    else:
        print("[1/6] Skipping Firecrawl (not requested)")

    # HTML-based extraction (always runs to fill gaps)
    print("[2/6] Fetching and parsing HTML...")
    soup = fetch_html(url)
    if not soup:
        print("  [ERROR] Could not fetch HTML. Aborting.")
        return kit

    # Logos
    print("[3/6] Extracting logos...")
    html_logos = extract_logos(soup, url)
    # Merge: Firecrawl logos first, then HTML logos
    seen_urls = {l.url[:200] for l in kit.logos}
    for logo in html_logos:
        if logo.url[:200] not in seen_urls:
            kit.logos.append(logo)
            seen_urls.add(logo.url[:200])
    print(f"  Found {len(kit.logos)} logo candidate(s)")

    # Favicon
    print("[4/6] Extracting favicon...")
    if not kit.favicon_url:
        kit.favicon_url = extract_favicon(soup, url)
    if kit.favicon_url:
        print(f"  Found: {kit.favicon_url[:80]}")

    # Colors (merge HTML-extracted with Firecrawl)
    if not kit.colors:
        html_colors = extract_colors_from_html(soup)
        kit.colors = {
            "primary": html_colors.get("primary", "#0077CC"),
            "accent": "#00BFB3",
            "background": "#FFFFFF",
            "white": "#FFFFFF",
            "black": "#1A1C21",
            "textPrimary": "#343741",
            "textBody": "#69707D",
            "border": "#D3DAE6",
        }
    print(f"  Colors: primary={kit.colors.get('primary')}")

    # Fonts
    print("[5/6] Extracting fonts...")
    html_fonts, font_assets = extract_fonts_from_html(soup, url)
    if not kit.fonts.get("heading") or kit.fonts["heading"] == "":
        kit.fonts = html_fonts
    kit.font_assets = [asdict(f) for f in font_assets]
    print(f"  Font families: {kit.fonts.get('heading', 'none')}, {kit.fonts.get('body', 'none')}")

    # Images
    if skip_images:
        print("[6/6] Skipping image extraction (--skip-images)")
    else:
        print("[6/6] Extracting images...")
        kit.images = [asdict(i) for i in extract_images(soup, url)]
        print(f"  Found {len(kit.images)} image(s)")

    return kit


# ---------------------------------------------------------------------------
# Asset download and directory setup
# ---------------------------------------------------------------------------

def save_brand_assets(kit: BrandKit) -> Path:
    """Download all assets and create the brand directory structure."""
    brand_dir = BRANDS_DIR / kit.brand_id
    logos_dir = brand_dir / "logos"
    images_dir = brand_dir / "images"
    fonts_dir = brand_dir / "fonts"

    for d in [logos_dir, images_dir, fonts_dir]:
        d.mkdir(parents=True, exist_ok=True)

    print("\n--- Downloading assets ---")

    # Download logos
    for i, logo in enumerate(kit.logos):
        if isinstance(logo, dict):
            logo = LogoAsset(**logo)
        if logo.url.startswith("data:"):
            # Save inline SVG
            ext = "svg"
            filename = f"logo-{logo.variant}.{ext}"
            dest = logos_dir / filename
            if "svg+xml" in logo.url:
                svg_data = urllib.parse.unquote(logo.url.split(",", 1)[1]) if "," in logo.url else ""
                if svg_data:
                    dest.write_text(svg_data)
                    print(f"  [LOGO] Saved inline SVG -> {dest.relative_to(PROJECT_ROOT)}")
                    if isinstance(kit.logos[i], dict):
                        kit.logos[i]["local_path"] = str(dest.relative_to(BRANDS_DIR.parent))
                    else:
                        kit.logos[i].local_path = str(dest.relative_to(BRANDS_DIR.parent))
        else:
            ext = "svg" if ".svg" in logo.url else "png"
            filename = f"logo-{logo.variant}.{ext}"
            dest = logos_dir / filename
            if download_file(logo.url, dest):
                print(f"  [LOGO] {logo.variant} -> {dest.relative_to(PROJECT_ROOT)}")
                if isinstance(kit.logos[i], dict):
                    kit.logos[i]["local_path"] = str(dest.relative_to(BRANDS_DIR.parent))
                else:
                    kit.logos[i].local_path = str(dest.relative_to(BRANDS_DIR.parent))

    # Also copy primary logo to top-level logo.svg for convenience
    primary_logos = [
        l for l in kit.logos
        if (l["variant"] if isinstance(l, dict) else l.variant) == "primary"
    ]
    if primary_logos:
        pl = primary_logos[0]
        lp = pl["local_path"] if isinstance(pl, dict) else pl.local_path
        if lp:
            src = BRANDS_DIR.parent / lp
            if src.exists():
                ext = src.suffix
                shutil.copy2(src, brand_dir / f"logo{ext}")

    # Download favicon
    if kit.favicon_url and not kit.favicon_url.startswith("data:"):
        ext = ".ico"
        if ".png" in kit.favicon_url:
            ext = ".png"
        elif ".svg" in kit.favicon_url:
            ext = ".svg"
        dest = brand_dir / f"favicon{ext}"
        if download_file(kit.favicon_url, dest):
            kit.favicon_local = f"/brands/{kit.brand_id}/favicon{ext}"
            print(f"  [FAVICON] -> {dest.relative_to(PROJECT_ROOT)}")

    # Download images
    for i, img_data in enumerate(kit.images):
        img = img_data if isinstance(img_data, dict) else asdict(img_data)
        img_url = img["url"]
        role = img["role"]

        if img_url.startswith("data:"):
            continue

        ext = ".jpg"
        if ".png" in img_url:
            ext = ".png"
        elif ".webp" in img_url:
            ext = ".webp"
        elif ".svg" in img_url:
            ext = ".svg"

        if role == "category":
            filename = f"category-{i}{ext}"
        else:
            filename = f"{role}{ext}"

        dest = images_dir / filename
        if download_file(img_url, dest):
            kit.images[i]["local_path"] = f"/brands/{kit.brand_id}/images/{filename}"
            print(f"  [IMAGE] {role} -> {dest.relative_to(PROJECT_ROOT)}")

    # Download fonts
    for i, font_data in enumerate(kit.font_assets):
        fa = font_data if isinstance(font_data, dict) else asdict(font_data)
        src_url = fa.get("src_url")
        if not src_url:
            continue

        family_slug = re.sub(r"[^a-z0-9]", "-", fa["family"].lower())
        weight = fa.get("weight", "400")
        ext = ".woff2"
        if ".woff" in src_url and ".woff2" not in src_url:
            ext = ".woff"
        elif ".ttf" in src_url:
            ext = ".ttf"

        filename = f"{family_slug}-{weight}{ext}"
        dest = fonts_dir / filename
        if download_file(src_url, dest):
            kit.font_assets[i]["local_path"] = f"/brands/{kit.brand_id}/fonts/{filename}"
            print(f"  [FONT] {fa['family']} ({weight}) -> {dest.relative_to(PROJECT_ROOT)}")

    # Save brand-kit.json
    kit_path = brand_dir / "brand-kit.json"
    kit_dict = asdict(kit) if not isinstance(kit, dict) else kit
    kit_path.write_text(json.dumps(kit_dict, indent=2, default=str))
    print(f"\n  [KIT] Saved -> {kit_path.relative_to(PROJECT_ROOT)}")

    return brand_dir


# ---------------------------------------------------------------------------
# Theme file generation
# ---------------------------------------------------------------------------

def generate_theme_file(kit: BrandKit) -> str:
    """Generate a TypeScript theme file from the extracted brand kit."""
    bid = kit.brand_id
    name_camel = bid[0].upper() + bid[1:]

    # Determine logo paths
    logo_path = f"/brands/{bid}/logo.svg"
    logo_dark_path = f"/brands/{bid}/logos/logo-dark.svg"
    has_dark_logo = (BRANDS_DIR / bid / "logos" / "logo-dark.svg").exists()
    if not has_dark_logo:
        logo_dark_path = logo_path

    # Determine hero image
    hero_images = [
        i for i in kit.images
        if (i.get("role") if isinstance(i, dict) else i.role) in ("hero", "og-image")
    ]
    hero_local = None
    if hero_images:
        img = hero_images[0]
        hero_local = img.get("local_path") if isinstance(img, dict) else img.local_path

    # Determine favicon
    favicon_path = kit.favicon_local or f"/brands/{bid}/favicon.ico"

    # Font faces
    font_face_entries = []
    for fa in kit.font_assets:
        fa_dict = fa if isinstance(fa, dict) else asdict(fa)
        local = fa_dict.get("local_path")
        if not local:
            continue
        family = fa_dict["family"]
        weight = fa_dict.get("weight", "400")
        fmt = "woff2"
        if ".woff" in local and ".woff2" not in local:
            fmt = "woff"
        elif ".ttf" in local:
            fmt = "truetype"
        font_face_entries.append(
            f"""    {{
      family: '{family}',
      src: "url('{local}') format('{fmt}')",
      weight: '{weight}',
      style: 'normal',
      display: 'swap',
    }}"""
        )

    font_faces_str = ",\n".join(font_face_entries) if font_face_entries else ""

    # Button styles
    btn_primary = kit.buttons.get("primary", {})
    btn_bg = btn_primary.get("backgroundColor", kit.colors.get("primary", "#0077CC"))
    btn_radius = btn_primary.get("borderRadius", kit.spacing.get("borderRadius", "6px"))

    # Build the theme
    primary = kit.colors.get("primary", "#0077CC")
    accent = kit.colors.get("accent", "#00BFB3")

    ts = f'''/**
 * {kit.metadata.get("personality", {}).get("tone", "Professional")} Brand Theme — {bid}
 *
 * Auto-extracted from {kit.source_url}
 * Generated by scripts/branding/extract_brand.py
 *
 * REVIEW CHECKLIST (complete before committing):
 * - [ ] Logo renders correctly in header (dark bg) and content (light bg)
 * - [ ] Favicon loads without 404
 * - [ ] Fonts load via @font-face (not just declared in font-family)
 * - [ ] Hero image renders on homepage
 * - [ ] Dark mode colors are correct (test toggle)
 * - [ ] Custom CSS classes match domain vocabulary
 */

export const {bid}Branding = {{
  name: '{bid.upper() if len(bid) <= 4 else name_camel}',
  sourceUrl: '{kit.source_url}',
  extractedAt: '{datetime.date.today().isoformat()}',

  // --- Tier 0: Required ---

  colors: {{
    primary: '{primary}',
    accent: '{accent}',
    background: '{kit.colors.get("background", "#FFFFFF")}',
    white: '{kit.colors.get("white", "#FFFFFF")}',
    black: '{kit.colors.get("black", "#1A1C21")}',
    textPrimary: '{kit.colors.get("textPrimary", "#343741")}',
    textBody: '{kit.colors.get("textBody", "#69707D")}',
    border: '{kit.colors.get("border", "#D3DAE6")}',
  }},

  colorsDark: {{
    primary: '{kit.colors_dark.get("primary", primary)}',
    accent: '{kit.colors_dark.get("accent", accent)}',
    background: '{kit.colors_dark.get("background", "#1D1E24")}',
    white: '{kit.colors_dark.get("white", "#25262E")}',
    black: '{kit.colors_dark.get("black", "#FFFFFF")}',
    textPrimary: '{kit.colors_dark.get("textPrimary", "#FFFFFF")}',
    textBody: '{kit.colors_dark.get("textBody", "#B4B7C1")}',
    border: '{kit.colors_dark.get("border", "#404040")}',
  }},

  fonts: {{
    heading: {repr(kit.fonts.get("heading", "'Inter', sans-serif"))},
    body: {repr(kit.fonts.get("body", "'Inter', sans-serif"))},
    fallback: {repr(kit.fonts.get("fallback", "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"))},
  }},

  spacing: {{
    borderRadius: '{kit.spacing.get("borderRadius", "6px")}',
    borderRadiusSmall: '{kit.spacing.get("borderRadiusSmall", "4px")}',
  }},

  logo: {{
    url: '{logo_path}',
    alt: '{bid.upper() if len(bid) <= 4 else name_camel}',
    logoContainsText: true,
  }},

  logoDark: {{
    url: '{logo_dark_path}',
    alt: '{bid.upper() if len(bid) <= 4 else name_camel}',
  }},

  // --- Tier 1: Links & Buttons ---

  links: {{
    color: '{primary}',
    hoverColor: '{primary}',
    underlineThickness: '1px',
    underlineOffset: '.15em',
  }},

  buttons: {{
    primary: {{
      backgroundColor: '{btn_bg}',
      textColor: '#FFFFFF',
      borderRadius: '{btn_radius}',
      fontWeight: '600',
      hover: {{
        backgroundColor: '{btn_bg}',
      }},
    }},
  }},

  // --- Tier 2: Domain CSS ---

  customCss: `
    /* {bid} product card */
    .{bid}-product-card {{
      border-radius: var(--brand-border-radius);
      overflow: hidden;
      transition: box-shadow 0.2s ease;
    }}
    .{bid}-product-card:hover {{
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    }}

    /* {bid} badge */
    .{bid}-badge {{
      display: inline-block;
      padding: 2px 8px;
      border-radius: var(--brand-border-radius-small);
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }}
    .{bid}-badge--new {{
      background: var(--brand-accent);
      color: #FFFFFF;
    }}
    .{bid}-badge--sale {{
      background: #D4351C;
      color: #FFFFFF;
    }}

    /* {bid} price display */
    .{bid}-price {{
      font-weight: 700;
      color: var(--brand-text-primary);
    }}
    .{bid}-price--was {{
      text-decoration: line-through;
      color: var(--brand-text-body);
      font-weight: 400;
      margin-right: 8px;
    }}
    .{bid}-price--now {{
      color: var(--brand-accent);
    }}
  `,

  // --- Tier 3: Layout ---

  layout: {{
    maxWidth: '1200px',
    containerPadding: '24px',
    sectionSpacing: '32px',
    headerHeight: '56px',
  }},

  // --- Tier 4: Visual Fidelity ---

  gradients: {{
    primary: 'linear-gradient(135deg, {primary} 0%, {accent} 100%)',
    hero: 'linear-gradient(180deg, {primary}CC 0%, {primary}66 100%)',
  }},
'''

    if hero_local:
        ts += f'''
  heroImage: {{
    url: '{hero_local}',
    alt: '{name_camel} Hero',
    position: 'center',
    overlay: 'rgba(0, 0, 0, 0.4)',
  }},
'''

    if font_face_entries:
        ts += f'''
  fontFaces: [
{font_faces_str}
  ],
'''

    ts += f'''
  favicon: '{favicon_path}',
}}
'''
    return ts


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Extract a complete brand kit from a website URL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("url", help="Target website URL")
    parser.add_argument("brand_id", help="Brand identifier (lowercase, no spaces)")
    parser.add_argument("--firecrawl", action="store_true",
                        help="Try Firecrawl API first (needs FIRECRAWL_API_KEY)")
    parser.add_argument("--skip-images", action="store_true",
                        help="Skip hero/category image extraction")
    parser.add_argument("--theme-only", action="store_true",
                        help="Generate theme file without downloading assets")
    parser.add_argument("--output-dir", type=Path, default=None,
                        help="Override output directory (default: frontend/public/brands/{id})")

    args = parser.parse_args()

    print(f"=== Brand Extraction: {args.brand_id} from {args.url} ===\n")

    kit = extract_brand(
        args.url,
        args.brand_id,
        use_firecrawl=args.firecrawl,
        skip_images=args.skip_images,
    )

    if not args.theme_only:
        brand_dir = save_brand_assets(kit)
        print(f"\n  Brand assets -> {brand_dir.relative_to(PROJECT_ROOT)}")

    # Generate theme file
    theme_ts = generate_theme_file(kit)
    theme_path = PROJECT_ROOT / "frontend" / "src" / "branding" / f"{args.brand_id}Theme.ts"

    if theme_path.exists():
        draft_path = theme_path.with_suffix(".draft.ts")
        draft_path.write_text(theme_ts)
        print(f"\n  Theme file already exists. Draft saved -> {draft_path.relative_to(PROJECT_ROOT)}")
        print("  Review the draft and merge changes manually.")
    else:
        theme_path.write_text(theme_ts)
        print(f"\n  Theme file -> {theme_path.relative_to(PROJECT_ROOT)}")

    print("\n=== Extraction complete ===")
    print(f"  Logos:    {len(kit.logos)}")
    print(f"  Images:   {len(kit.images)}")
    print(f"  Fonts:    {len(kit.font_assets)}")
    print(f"  Favicon:  {'yes' if kit.favicon_url else 'no'}")
    print(f"  Colors:   {json.dumps(kit.colors, indent=2)}")

    # Print review checklist
    print("\n--- POST-EXTRACTION CHECKLIST ---")
    print("  [ ] Open the theme file and review all color values")
    print("  [ ] Check logo files render correctly (open in browser)")
    print("  [ ] Verify favicon is valid (not a 404 page saved as .ico)")
    print("  [ ] If fonts were found, verify @font-face loads in browser")
    print("  [ ] Run: python scripts/branding/verify_brand.py", args.brand_id)
    print("  [ ] Start dev server and visually check the brand renders")


if __name__ == "__main__":
    main()
