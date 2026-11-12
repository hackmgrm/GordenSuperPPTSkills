import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np
from PIL import Image
from pptx import Presentation

ROOT = Path(__file__).resolve().parents[1]


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


ALPHA = module(ROOT / 'GordenImage2PPTX/scripts/alpha_qa.py', 'alpha')


class AlphaTests(unittest.TestCase):
    def test_opaque_and_empty_are_rejected(self):
        for im in [Image.new('RGB', (20, 20), 'black'), Image.new('RGBA', (20, 20))]:
            self.assertTrue(ALPHA.inspect_alpha(im)[0]['errors'])

    def test_clean_gold_transparency(self):
        im = Image.new('RGBA', (40, 30))
        im.paste((245, 180, 40, 255), (5, 8, 35, 12))
        report, _ = ALPHA.inspect_alpha(im, (0, 255, 0))
        self.assertFalse(report['errors']); self.assertFalse(report['warnings'])
        self.assertGreater(report['transparent_fraction'], .8)

    def test_green_fringe_requires_review(self):
        im = Image.new('RGBA', (40, 30))
        im.paste((70, 240, 20, 160), (5, 8, 35, 12))
        report, _ = ALPHA.inspect_alpha(im, (0, 255, 0))
        self.assertEqual(report['status'], 'needs_review')
        self.assertGreater(report['candidate_pixels'], 0)

    def test_hidden_green_is_not_visible_residue(self):
        im = Image.new('RGBA', (40, 30), (0, 255, 0, 0))
        im.paste((255, 255, 255, 255), (5, 8, 35, 12))
        self.assertEqual(ALPHA.inspect_alpha(im, (0, 255, 0))[0]['candidate_pixels'], 0)

    def test_multibackground_composites_preserve_foreground(self):
        with tempfile.TemporaryDirectory() as td:
            im = Image.new('RGBA', (20, 20)); im.putpixel((10, 10), (200, 80, 10, 255))
            report, candidates = ALPHA.inspect_alpha(im)
            ALPHA.write_views(im, candidates, Path(td))
            for name, value in [('white', 255), ('gray', 128), ('black', 0)]:
                with Image.open(Path(td)/f'{name}.png') as composite:
                    self.assertEqual(composite.getpixel((0, 0)), (value,)*3)
                    self.assertEqual(composite.getpixel((10, 10)), (200, 80, 10))


class ChromaTests(unittest.TestCase):
    def test_magenta_key_preserves_blue_and_orange(self):
        chroma = module(ROOT / 'GordenImage2PPTX/scripts/chroma_key.py', 'chroma')
        source = np.array([[[0, 45, 150, 255], [255, 100, 0, 255], [255, 0, 255, 255]]], dtype=np.uint8)
        out, _ = chroma.remove_key(source, (255, 0, 255), 24, 86, True, 0, 0,
                                  True, 0, 1, 0, 0, 255, .2)
        np.testing.assert_array_equal(out[0,:2], source[0,:2])
        self.assertEqual(out[0,2,3], 0)


class ComposerTests(unittest.TestCase):
    def test_both_standalone_composers(self):
        for skill in ['GordenImage2PPTX', 'GordenImagePPTGen']:
            with self.subTest(skill=skill), tempfile.TemporaryDirectory() as td:
                base = Path(td); assets = base/'assets'; assets.mkdir()
                Image.new('RGB', (16, 9), '#202020').save(assets/'photo.png')
                data = dict(units='fraction', ref_width=1600, ref_height=900,
                            assets_dir='assets', background_color='#112233',
                            shapes=[dict(name='gold-vertical', type='line', x=.3, y=.2, w=0, h=.2,
                                         line='#F4B83E', line_width=2),
                                    dict(name='gold-horizontal', type='rect', x=.1, y=.6, w=.2, h=.01,
                                         fill='#F4B83E')],
                            texts=[dict(text='A\nA', x=.5, y=.2, w=.4, h=.7,
                                        size=30, color='#FFFFFF', line_spacing=1.8)])
                layout = base/'layout.json'; layout.write_text(json.dumps(data))
                composer = module(ROOT/skill/'scripts/compose_pptx.py', skill)
                deck = composer._load_deck(layout)
                self.assertEqual(Path(deck['assets_dir']).resolve(), assets.resolve())
                out = base/'deck.pptx'
                subprocess.run([sys.executable, str(ROOT/skill/'scripts/compose_pptx.py'),
                                str(layout), str(out), '--preview-dir', str(base/'preview')],
                               cwd='/', check=True, capture_output=True)
                prs = Presentation(out); slide = prs.slides[0]
                self.assertEqual(len(slide.shapes), 3)  # two editable shapes plus text, no raster frame
                self.assertEqual(slide.shapes[0].name, 'gold-vertical')
                for shape in list(slide.shapes)[:2]:
                    for effect in shape._element.xpath('./p:style/a:effectRef'):
                        self.assertEqual(effect.get('idx'), '0')
                self.assertEqual(str(slide.background.fill.fore_color.rgb), '112233')
                self.assertAlmostEqual(slide.shapes[2].text_frame.paragraphs[0].line_spacing, 1.8)
                with Image.open(base/'preview/slide_01.png') as preview:
                    self.assertEqual(preview.getpixel((0, 0)), (17, 34, 51))
                    # Same glyph on two lines: baseline distance should follow 1.8, not hardcoded 1.3.
                    a=np.asarray(preview); mask=(a[:,:,0]>245)&(a[:,:,1]>245)&(a[:,:,2]>245)
                    rows=np.flatnonzero(mask[:,800:].any(axis=1)); starts=rows[np.r_[True,np.diff(rows)>1]]
                    self.assertEqual(len(starts),2)
                    self.assertAlmostEqual(starts[1]-starts[0],90,delta=2)
                self.assertTrue(json.loads((base/'preview/render-info.json').read_text())['approximate'])
                # Relative assets survive a different CWD and picture remains embedded.
                data['background']='photo.png'; layout.write_text(json.dumps(data))
                subprocess.run([sys.executable, str(ROOT/skill/'scripts/compose_pptx.py'),str(layout),str(out)],
                               cwd='/',check=True,capture_output=True)
                self.assertEqual(len(Presentation(out).slides[0].shapes),4)

    def test_native_shape_coordinates_are_guarded(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td); Image.new('RGB',(1600,900)).save(base/'source.png')
            data=dict(ref_width=1600,ref_height=900,units='fraction',shapes=[
                dict(type='line',x=.4,y=.4,w=0,h=-.2,source_bbox=[640,360,0,-180])])
            layout=base/'layout.json';layout.write_text(json.dumps(data))
            cmd=[sys.executable,str(ROOT/'GordenImage2PPTX/scripts/layout_guard.py'),str(base/'source.png'),str(layout),'--strict']
            good=subprocess.run(cmd,capture_output=True,text=True)
            self.assertEqual(good.returncode,0,good.stdout+good.stderr)
            data['shapes'][0]['x']=.6;layout.write_text(json.dumps(data))
            self.assertNotEqual(subprocess.run(cmd,capture_output=True).returncode,0)


if __name__ == '__main__':
    unittest.main()
