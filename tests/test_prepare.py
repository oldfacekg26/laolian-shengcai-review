import base64
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('prepare', Path(__file__).parents[1] / 'scripts' / 'prepare.py')
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jWZkAAAAASUVORK5CYII=')
URL = 'https://wx.zsxq.com/article?groupId=123'


class ReviewPacketTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.draft = self.root / 'article.md'
        (self.root / 'image.png').write_bytes(PNG)
        self.draft.write_text('# 标题\n\n前段\n\n![图片](image.png)\n\n## 小节\n\n后段 **重点**', encoding='utf-8')

    def tearDown(self):
        self.temp.cleanup()

    def build(self, tags=()):
        return prepare.build(self.draft, self.root / 'output', URL, tags)

    def test_image_order_bytes_and_offline_preview(self):
        result = self.build(['线下聚会', '项目实操'])
        manifest = json.loads((result / 'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual([b['kind'] for b in manifest['blocks']], ['paragraph', 'image', 'heading', 'paragraph'])
        self.assertEqual((result / manifest['blocks'][1]['path']).read_bytes(), PNG)
        preview = (result / 'preview.html').read_text(encoding='utf-8')
        self.assertIn('data:image/png;base64,', preview)
        self.assertLess(preview.index('前段'), preview.index('<figure>'))
        self.assertLess(preview.index('</figure>'), preview.index('后段'))
        self.assertIn('<strong>重点</strong>', preview)

    def test_repeated_build_preserves_publication_receipt(self):
        result = self.build(['项目实操', '线下聚会'])
        state = result / 'state.json'
        receipt = '{"published": true, "url": "already-published"}'
        state.write_text(receipt, encoding='utf-8')
        repeated = self.build(['项目实操', '线下聚会', '项目实操'])
        self.assertEqual(result, repeated)
        self.assertEqual(state.read_text(encoding='utf-8'), receipt)

    def test_tag_order_is_preserved_and_versioned(self):
        a = self.build(['线下聚会', '生财朋友圈', '线下聚会'])
        b = self.build(['生财朋友圈', '线下聚会'])
        self.assertNotEqual(a, b)
        data = json.loads((a / 'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(data['tags'], ['线下聚会', '生财朋友圈'])

    def test_changed_content_and_tag_create_unapproved_revision(self):
        a = self.build()
        b = self.build(['线下聚会'])
        self.assertNotEqual(a, b)
        self.draft.write_text('# 标题\n\n修改正文', encoding='utf-8')
        c = self.build(['线下聚会'])
        self.assertNotEqual(b, c)
        state = json.loads((c / 'state.json').read_text())
        self.assertFalse(state['approved'])
        self.assertFalse(state['published'])

    def test_missing_image_fails_without_packet(self):
        (self.root / 'image.png').unlink()
        with self.assertRaises(FileNotFoundError):
            self.build()
        self.assertFalse((self.root / 'output').exists())

    def test_path_escape_rejected(self):
        self.draft.write_text('# 标题\n\n正文\n\n![图](../private.png)', encoding='utf-8')
        with self.assertRaises(ValueError):
            self.build()

    def test_invalid_image_and_inline_image_rejected(self):
        (self.root / 'image.png').write_bytes(b'not an image')
        with self.assertRaises(ValueError):
            self.build()
        self.draft.write_text('# 标题\n\n文字 ![图](image.png)', encoding='utf-8')
        with self.assertRaises(ValueError):
            self.build()

    def test_untrusted_html_is_text(self):
        self.draft.write_text('# <script>alert(1)</script>\n\n<script>alert(2)</script>', encoding='utf-8')
        preview = (self.build() / 'preview.html').read_text(encoding='utf-8')
        self.assertNotIn('<script>', preview)
        self.assertIn('&lt;script&gt;', preview)

    def test_wrong_destination_rejected(self):
        for target in ['http://wx.zsxq.com/article', 'https://wx.zsxq.com.attacker.invalid/article', 'https://wx.zsxq.com/login']:
            with self.assertRaises(ValueError):
                prepare.build(self.draft, self.root / 'out', target)


if __name__ == '__main__':
    unittest.main()
