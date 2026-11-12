#!/usr/bin/env python3
"""Render the actual PPTX with LibreOffice and Poppler in an isolated profile.

Unlike compose_pptx's Pillow preview this exercises the office layout engine.
Fonts still must be installed or supplied via --font-dir; inspect the output.
"""
import argparse
import json
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
from xml.sax.saxutils import escape


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('pptx', type=Path)
    ap.add_argument('--out-dir', type=Path, required=True)
    ap.add_argument('--font-dir', type=Path, action='append', default=[])
    args = ap.parse_args()
    for program in ['soffice', 'pdftoppm']:
        if not shutil.which(program):
            ap.error(f'{program} unavailable: actual office render was NOT performed')
    if not args.pptx.is_file():
        ap.error('PPTX does not exist')
    if any(not p.is_dir() for p in args.font_dir):
        ap.error('every --font-dir must be an existing directory')
    out = args.out_dir.resolve(); out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='pptx-render-') as tmp:
        temp = Path(tmp); env = os.environ.copy()
        if args.font_dir:
            config = temp/'fonts.conf'
            config.write_text('<?xml version="1.0"?><fontconfig>' + ''.join(
                '<dir>' + escape(str(p.resolve())) + '</dir>' for p in args.font_dir
            ) + '<cachedir>' + escape(str(temp/'font-cache')) + '</cachedir></fontconfig>')
            env['FONTCONFIG_FILE'] = str(config)
        profile = (temp/'profile').as_uri()
        # Convert privately first so an old PDF cannot be mistaken for success.
        converted = temp/'converted'; converted.mkdir()
        subprocess.run(['soffice', f'-env:UserInstallation={profile}', '--headless',
                        '--convert-to', 'pdf', '--outdir', str(converted), str(args.pptx.resolve())],
                       env=env, check=True, timeout=180)
        pdf = converted/(args.pptx.stem + '.pdf')
        if not pdf.is_file():
            raise RuntimeError('LibreOffice returned without creating a PDF')
        shutil.copy2(pdf, out/'rendered.pdf')
        subprocess.run(['pdftoppm', '-scale-to', '2000', '-png', str(pdf), str(out/'slide')],
                       check=True, timeout=180)
    (out/'render-info.json').write_text(json.dumps({
        'renderer': 'LibreOffice PDF export + Poppler', 'approximate': False,
        'source': str(args.pptx.resolve()), 'font_dirs': [str(p.resolve()) for p in args.font_dir],
        'status': 'rendered_visual_review_required',
        'limitations': 'Not Microsoft PowerPoint; verify font substitutions and visual fidelity.',
    }, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
