"""Compile verified uploaded image URLs into HTML and a DOM paste script.

Offline only: never uploads, replaces an editor, or clicks Publish itself.
The operator must back up the current editor and explicitly select its body
before executing paste.js with the browser tool.
"""
import argparse
import html
import json
from pathlib import Path
from urllib.parse import urlparse
from prepare import inline


def compile_payload(packet, mapping, output):
    packet, output = Path(packet), Path(output)
    manifest = json.loads((packet / 'manifest.json').read_text(encoding='utf-8'))
    urls = json.loads(Path(mapping).read_text(encoding='utf-8'))
    parts, expected_images = [], []
    for block in manifest['blocks']:
        if block['kind'] == 'image':
            url = urls[block['sha256']]
            parsed = urlparse(url)
            if parsed.scheme != 'https' or parsed.hostname != 'article-images.zsxq.com' or parsed.username or parsed.password:
                raise ValueError('Expected a verified HTTPS Knowledge Planet image URL')
            expected_images.append(url)
            parts.append('<p><img src="' + html.escape(url, quote=True) + '" alt="' + html.escape(block['alt'], quote=True) + '"></p>')
        elif block['kind'] == 'heading':
            level = max(2, block['level'])
            parts.append(f'<h{level}>' + inline(block['text']) + f'</h{level}>')
        else:
            parts.append('<p>' + inline(block['text']).replace('\n', '<br>') + '</p>')
    content = '\n'.join(parts)
    expected = {'fingerprint': manifest['fingerprint'], 'title': manifest['title'],
                'tags': manifest['tags'], 'images': expected_images}
    js = '(() => { const e=document.querySelector(".tiptap.ProseMirror"); if(!e) throw new Error("Supported editor not found"); const d=new DataTransfer(); d.setData("text/html",' + json.dumps(content, ensure_ascii=False) + '); e.dispatchEvent(new ClipboardEvent("paste",{clipboardData:d,bubbles:true,cancelable:true})); return "Paste dispatched; readback required"; })()'
    output.mkdir(parents=True, exist_ok=True)
    (output / 'body.html').write_text(content, encoding='utf-8')
    (output / 'paste.js').write_text(js, encoding='utf-8')
    (output / 'expected.json').write_text(json.dumps(expected, ensure_ascii=False, indent=2), encoding='utf-8')
    return expected


def verify(expected, actual):
    """actual is a browser DOM readback, not an application API response."""
    errors = []
    if actual.get('title') != expected['title']:
        errors.append('title mismatch')
    if [i.get('src') for i in actual.get('images', [])] != expected['images']:
        errors.append('image count or order mismatch')
    if any(not i.get('loaded') for i in actual.get('images', [])):
        errors.append('image not loaded')
    if 'tags' not in actual:
        errors.append('tags not independently observed')
    elif actual['tags'] != expected['tags']:
        errors.append('tag order or selection mismatch')
    return {'ok': not errors, 'errors': errors}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    c = sub.add_parser('compile')
    for arg in ('packet', 'mapping', 'out'):
        c.add_argument('--' + arg, required=True, type=Path)
    v = sub.add_parser('verify')
    v.add_argument('--expected', required=True, type=Path)
    v.add_argument('--actual', required=True, type=Path)
    a = p.parse_args()
    if a.command == 'compile':
        print(json.dumps(compile_payload(a.packet, a.mapping, a.out), ensure_ascii=False))
    else:
        result = verify(json.loads(a.expected.read_text(encoding='utf-8')), json.loads(a.actual.read_text(encoding='utf-8')))
        print(json.dumps(result, ensure_ascii=False))
        raise SystemExit(0 if result['ok'] else 1)
