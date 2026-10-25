"""Build immutable, offline review packets. Does not upload or publish anything."""
import argparse
import base64
import hashlib
import html
import json
import re
from pathlib import Path
from urllib.parse import urlparse


def digest(data):
    return hashlib.sha256(data).hexdigest()


def image_type(data):
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    if data.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg'
    if data[:6] in (b'GIF87a', b'GIF89a'):
        return 'image/gif'
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return 'image/webp'
    raise ValueError('Unsupported image bytes; use PNG, JPEG, GIF or WebP')


def inline(text):
    return re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html.escape(text))


def parse(draft):
    text = draft.read_text(encoding='utf-8-sig').strip()
    lines = text.splitlines()
    if not lines or not lines[0].startswith('# '):
        raise ValueError('First line must be # title')
    title = lines[0][2:].strip()
    if not title:
        raise ValueError('Empty title')
    root = draft.parent.resolve()
    blocks, images, paragraph = [], [], []

    def flush():
        if paragraph:
            blocks.append({'kind': 'paragraph', 'text': '\n'.join(paragraph)})
            paragraph.clear()

    for line in lines[1:]:
        line = line.strip()
        if not line:
            flush()
            continue
        match = re.fullmatch(r'!\[([^\]]*)\]\((.+)\)', line)
        if match:
            flush()
            alt, relative = match.groups()
            path = (root / relative).resolve()
            if not path.is_relative_to(root):
                raise ValueError('Image must be inside draft folder')
            data = path.read_bytes()
            mime = image_type(data)
            item = {'kind': 'image', 'alt': alt, 'path': relative,
                    'sha256': digest(data), 'bytes': len(data), 'mime': mime}
            blocks.append(item)
            images.append((item, data))
        elif '![' in line or '<img' in line.lower():
            raise ValueError('Image must be a standalone Markdown line')
        elif re.match(r'#{1,4} ', line):
            flush()
            heading, content = line.split(' ', 1)
            blocks.append({'kind': 'heading', 'level': len(heading), 'text': content})
        else:
            paragraph.append(line)
    flush()
    if not any(b['kind'] != 'image' for b in blocks):
        raise ValueError('Article has no text body')
    return title, blocks, images


def build(draft, out, destination, tags=()):
    parsed_url = urlparse(destination)
    if parsed_url.scheme != 'https' or parsed_url.hostname != 'wx.zsxq.com' or parsed_url.path != '/article':
        raise ValueError('Destination must be the actual HTTPS Knowledge Planet article editor URL')
    title, blocks, images = parse(Path(draft))
    selected = list(dict.fromkeys(t.strip() for t in tags if t.strip()))
    document = {'title': title, 'blocks': blocks, 'destination': destination, 'tags': selected}
    fingerprint = digest(json.dumps(document, ensure_ascii=False, sort_keys=True).encode())
    revision = Path(out) / fingerprint[:16]
    if revision.exists():
        saved = json.loads((revision / 'manifest.json').read_text(encoding='utf-8'))
        if saved['fingerprint'] != fingerprint:
            raise ValueError('Version collision')
        return revision
    # All source files validated before writing a packet.
    revision.mkdir(parents=True)
    media = revision / 'images'
    media.mkdir()
    rendered = []
    image_index = 0
    export_blocks = []
    for block in blocks:
        block = dict(block)
        kind = block['kind']
        if kind == 'image':
            item, data = images[image_index]
            image_index += 1
            extension = {'image/png': '.png', 'image/jpeg': '.jpg', 'image/gif': '.gif', 'image/webp': '.webp'}[item['mime']]
            filename = f'{image_index:02d}{extension}'
            target = media / filename
            target.write_bytes(data)
            if digest(target.read_bytes()) != item['sha256']:
                raise OSError('Image copy verification failed')
            block['path'] = 'images/' + filename
            encoded = base64.b64encode(data).decode('ascii')
            rendered.append(f'<figure><img src="data:{item["mime"]};base64,{encoded}" alt="{html.escape(item["alt"], quote=True)}"><figcaption>{html.escape(item["alt"])}</figcaption></figure>')
        elif kind == 'heading':
            level = max(2, block['level'])
            rendered.append(f'<h{level}>{inline(block["text"])}</h{level}>')
        else:
            rendered.append('<p>' + inline(block['text']).replace('\n', '<br>') + '</p>')
        export_blocks.append(block)
    manifest = {'fingerprint': fingerprint, 'title': title, 'destination': destination,
                'tags': selected, 'image_count': len(images), 'blocks': export_blocks}
    (revision / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    (revision / 'state.json').write_text(json.dumps({'stage': 'prepared', 'fingerprint': fingerprint,
        'approved': False, 'editor_filled': False, 'published': False}, indent=2), encoding='utf-8')
    body = '\n'.join(rendered)
    page = '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
    page += '<title>' + html.escape(title) + '</title><style>body{margin:0;background:#f4f6f5;color:#222;font:18px/1.9 system-ui}main,aside{max-width:760px;margin:24px auto;padding:24px;background:white}h1{font-size:30px;line-height:1.5}h2{font-size:24px;margin-top:44px}img{width:100%;height:auto}figure{margin:32px 0}figcaption{font-size:13px;color:#777}aside{font-size:14px;border-left:4px solid #169c80}@media(max-width:800px){main,aside{margin:12px;padding:18px}}</style>'
    page += '<aside>发布前预览 · 尚未发布<br>标签：' + html.escape('、'.join(selected) or '待选择') + f'<br>正文配图：{len(images)} 张<br>版本：{fingerprint[:16]}</aside>'
    page += '<main><h1>' + html.escape(title) + '</h1>' + body + '</main></html>'
    (revision / 'preview.html').write_text(page, encoding='utf-8')
    return revision


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--draft', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--destination', required=True)
    parser.add_argument('--tag', action='append', default=[])
    args = parser.parse_args()
    print(build(args.draft, args.out, args.destination, args.tag))
