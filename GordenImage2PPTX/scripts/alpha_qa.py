#!/usr/bin/env python3
"""Inspect a transparent asset; create multi-background previews, never modify it.

Color-key findings are review candidates, not proof of incorrect color. Use only
on assets intended to be transparent, not opaque photographic backgrounds.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


def inspect_alpha(image, key=None):
    has_alpha = 'A' in image.getbands() or 'transparency' in image.info
    rgba = np.asarray(image.convert('RGBA'))
    alpha = rgba[..., 3]
    visible = alpha > 8
    errors, warnings = [], []
    if not has_alpha:
        errors.append('missing_alpha')
    if not np.any(visible):
        errors.append('empty_foreground')
    if np.all(alpha == 255):
        errors.append('fully_opaque')
    candidates = np.zeros(alpha.shape, dtype=bool)
    if key is not None:
        rgb = rgba[..., :3].astype(float)
        key = np.asarray(key, dtype=float)
        # Key-like opaque remnants and key-dominant edge colors. This may flag
        # legitimate content of the same hue; no destructive automatic cleanup.
        close = np.max(np.abs(rgb - key), axis=2) < 65
        outside = Image.fromarray(((alpha < 250) * 255).astype('uint8'))
        edge = np.asarray(outside.filter(ImageFilter.MaxFilter(5))) > 0
        channels = np.where(key >= key.max() - 24)[0]
        others = np.array([c for c in range(3) if c not in channels])
        dominant = np.zeros(alpha.shape, dtype=bool)
        if len(others) and key.max() >= 110:
            dominant = rgb[..., channels].min(axis=2) > rgb[..., others].max(axis=2) + 18
        candidates = visible & (close | (edge & dominant))
        if np.any(candidates):
            warnings.append('possible_key_residue_review_required')
    report = {
        'size': list(image.size), 'has_alpha': has_alpha,
        'transparent_fraction': float((alpha == 0).mean()),
        'partial_fraction': float(((alpha > 0) & (alpha < 255)).mean()),
        'visible_pixels': int(visible.sum()),
        'candidate_pixels': int(candidates.sum()),
        'errors': errors, 'warnings': warnings,
        'status': 'fail' if errors else 'needs_review' if warnings else 'checks_passed_visual_review_required',
    }
    return report, candidates


def write_views(image, candidates, out):
    out.mkdir(parents=True, exist_ok=True)
    image = image.convert('RGBA')
    for name, color in [('white', '#FFFFFF'), ('gray', '#808080'), ('black', '#000000')]:
        bg = Image.new('RGBA', image.size, color)
        bg.alpha_composite(image)
        bg.convert('RGB').save(out / f'{name}.png')
    # Crop the transparent asset for QA only, never for delivered slide content.
    bbox = image.getchannel('A').getbbox()
    if bbox:
        zoom = image.crop(bbox)
        factor = min(4, 2048 / max(zoom.size))
        zoom = zoom.resize((max(1, round(zoom.width * factor)), max(1, round(zoom.height * factor))))
        bg = Image.new('RGBA', zoom.size, '#808080'); bg.alpha_composite(zoom)
        bg.convert('RGB').save(out / 'foreground-zoom.png')
    overlay = np.zeros((*candidates.shape, 4), dtype=np.uint8)
    overlay[candidates] = [255, 0, 255, 255]
    Image.fromarray(overlay).save(out / 'candidates.png')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--out-dir', type=Path, required=True)
    parser.add_argument('--key-color', help='Optional six-digit RGB, e.g. #00ff00')
    parser.add_argument('--strict', action='store_true', help='Nonzero on errors or review warnings')
    args = parser.parse_args()
    key = None
    if args.key_color:
        value = args.key_color.lstrip('#')
        try:
            if len(value) != 6:
                raise ValueError()
            key = tuple(int(value[i:i+2], 16) for i in (0, 2, 4))
        except ValueError:
            parser.error('--key-color requires six hex digits')
    with Image.open(args.input) as image:
        report, candidates = inspect_alpha(image, key)
        write_views(image, candidates, args.out_dir)
    (args.out_dir / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))
    return 1 if report['errors'] or (args.strict and report['warnings']) else 0


if __name__ == '__main__':
    raise SystemExit(main())
