import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import editor_payload as payload


class PayloadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.url = 'https://article-images.zsxq.com/synthetic'
        self.manifest = {'fingerprint': 'example', 'title': '合成测试', 'tags': ['线下聚会', '生财朋友圈'],
                         'blocks': [{'kind': 'image', 'sha256': 'hash', 'alt': '图"'},
                                    {'kind': 'paragraph', 'text': '正文 **重点** <script>'}]}
        (self.root / 'manifest.json').write_text(json.dumps(self.manifest), encoding='utf-8')
        self.mapping = self.root / 'mapping.json'
        self.mapping.write_text(json.dumps({'hash': self.url}), encoding='utf-8')

    def tearDown(self):
        self.tmp.cleanup()

    def test_compile_uses_verified_urls_and_escapes_text(self):
        expected = payload.compile_payload(self.root, self.mapping, self.root / 'out')
        body = (self.root / 'out/body.html').read_text(encoding='utf-8')
        paste = (self.root / 'out/paste.js').read_text(encoding='utf-8')
        self.assertTrue(body.startswith('<p><img'))
        self.assertIn('图&quot;', body)
        self.assertNotIn('<script>', body)
        self.assertIn('.ql-editor[contenteditable=true]', paste)
        self.assertIn('.tiptap.ProseMirror[contenteditable=true]', paste)
        self.assertEqual(expected['images'], [self.url])

    def test_missing_mapping_writes_nothing(self):
        self.mapping.write_text('{}')
        with self.assertRaises(KeyError):
            payload.compile_payload(self.root, self.mapping, self.root / 'out')
        self.assertFalse((self.root / 'out').exists())

    def test_unuploaded_or_wrong_host_rejected(self):
        for url in ['data:image/png;base64,x', 'file:///private.png', 'https://article-images.zsxq.com.evil.invalid/x']:
            self.mapping.write_text(json.dumps({'hash': url}))
            with self.assertRaises(ValueError):
                payload.compile_payload(self.root, self.mapping, self.root / 'out')

    def test_readback_detects_missing_tags_wrong_order_and_unloaded_image(self):
        expected = {'title': 't', 'images': ['a', 'b'], 'tags': ['x', 'y']}
        actual = {'title': 't', 'images': [{'src': 'a', 'loaded': True}, {'src': 'b', 'loaded': True}], 'tags': ['x', 'y']}
        self.assertTrue(payload.verify(expected, actual)['ok'])
        actual['images'].reverse()
        self.assertFalse(payload.verify(expected, actual)['ok'])
        actual['images'].reverse()
        actual['images'][0]['loaded'] = False
        del actual['tags']
        self.assertEqual(len(payload.verify(expected, actual)['errors']), 2)


if __name__ == '__main__':
    unittest.main()
