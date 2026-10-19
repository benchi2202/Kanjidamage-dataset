# -*- coding: utf-8 -*-
"""Extract clean structured data from the KanjiDamage Anki deck.

Outputs (all UTF-8):
  kanjidamage.json        main dataset (array, ordered by position)
  tags.json               tag id -> {name, description, count}
  onyomi-keywords.json    reading -> keyword (from the official appendix)
  media/                  all 2028 media files, renamed to their real names
"""
import sqlite3, re, json, html, sys, os, zipfile, urllib.request
from html import unescape as _un
from urllib.parse import unquote

FS = chr(31)
BASE = r'C:\Users\Admin\Documents\deepseek-harness\anki'
OUT = BASE
os.makedirs(os.path.join(OUT, 'media'), exist_ok=True)

def strip_html(s):
    if not s:
        return ""
    s = re.sub(r'<br\s*/?>', '\n', s, flags=re.I)
    s = re.sub(r'</(p|tr|li|div|h\d|h1)>', '\n', s, flags=re.I)
    s = re.sub(r'<[^>]+>', '', s)
    s = _un(s)
    s = re.sub(r'[ \t]+\n', '\n', s)
    s = re.sub(r'\n{3,}', '\n\n', s)
    s = re.sub(r'[ \t]{2,}', ' ', s)
    return s.strip()

def extract_img_src(s):
    m = re.search(r'src="([^"]+)"', s)
    return m.group(1) if m else None

def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    return urllib.request.urlopen(req, timeout=30).read().decode('utf-8', 'replace')

# ---------------- load index (position -> entry) ----------------
idx = json.load(open(os.path.join(BASE, 'extract', 'kanji_index.json'), encoding='utf-8'))
pos_map = {}
for e in idx:
    if e['position'] in pos_map:
        raise SystemExit('duplicate position %s' % e['position'])
    pos_map[e['position']] = e
id_map = {e['id']: e for e in idx}

# ---------------- tags (canonical names from official page) ----------------
tags_html = fetch('https://www.kanjidamage.com/tags')
tags = {}
tag_id_to_name = {}
for m in re.finditer(r'<tr>\s*<td>\s*<a href="/tags/(\d+)">([^<]*)</a>\s*</td>\s*<td>(\d+)</td>\s*<td>(.*?)</td>\s*</tr>', tags_html, re.S):
    tid = int(m.group(1)); name = _un(m.group(2)).strip()
    count = int(m.group(3)); desc = strip_html(m.group(4)) or None
    tags[tid] = {'name': name, 'description': desc, 'count': count}
    tag_id_to_name[tid] = name
def tag_names(ids):
    return [tag_id_to_name.get(i, str(i)) for i in ids]

con = sqlite3.connect(os.path.join(BASE, 'extract', 'collection.anki2'))
cur = con.cursor()
cur.execute('SELECT flds FROM notes ORDER BY id')
rows = [r[0] for r in cur.fetchall()]

def stars_to_int(header):
    m = re.search(r'usefulness-stars"[^>]*title="(\d+) out of 5', header)
    if m:
        return int(m.group(1))
    if 'usefulness-stars' in header:
        sm = re.search(r'usefulness-stars[^>]*>\s*([\u2605\u2606]+)', header)
        if sm:
            return sm.group(1).count('\u2605')
    return None

def parse_components(header):
    comps = []
    pat = re.compile(
        r'<a class="component"[^>]*href="[^"]*/kanji/(\d+)-[^"]*"[^>]*>(.*?)</a>\s*\(([^)]*)\)', re.S)
    for m in pat.finditer(header):
        cid = int(m.group(1)); inner = m.group(2); label = _un(m.group(3)).strip()
        if '<img' in inner:
            img = extract_img_src(inner)
            kanji = id_map.get(cid, {}).get('kanji')
            comps.append({'id': cid, 'kanji': kanji, 'image': img, 'label': label})
        else:
            comps.append({'id': cid, 'kanji': _un(strip_html(inner)), 'image': None, 'label': label})
    return comps

def parse_tags(text):
    out, seen = [], set()
    for m in re.finditer(r'/tags/(\d+)"[^>]*>([^<]*)</a>', text):
        tid = int(m.group(1))
        if tid not in seen:
            seen.add(tid); out.append(tid)
    return out

def parse_onyomi(full_onyomi):
    out = []
    for m in re.finditer(r'<tr>(.*?)</tr>', full_onyomi, re.S):
        row = m.group(1)
        rm = re.search(r'<span class="onyomi">([^<]*)</span>', row)
        if not rm:
            continue
        reading = _un(rm.group(1)).strip()
        tds = re.findall(r'<td[^>]*>(.*?)</td>', row, re.S)
        mnem = strip_html(tds[1]) if len(tds) >= 2 else None
        out.append({'reading': reading, 'mnemonic': mnem or None})
    return out

def parse_mnemonic(full_mnemonic):
    tds = re.findall(r'<td[^>]*>(.*?)</td>', full_mnemonic, re.S)
    if len(tds) >= 2:
        cell = tds[1]
        imgs = re.findall(r'src="([^"]+)"', cell)
        return (strip_html(cell) or None), imgs
    return None, []

def clean_particles(p):
    if p and p.strip().lower() == 'xxx':
        return None
    return p

def parse_kunyomi(full_kunyomi):
    out = []
    for m in re.finditer(r'<tr>(.*?)</tr>', full_kunyomi, re.S):
        row = m.group(1)
        tds = re.findall(r'<td[^>]*>(.*?)</td>', row, re.S)
        if len(tds) < 2:
            continue
        left, right = tds[0], tds[1]
        particles = None
        pm = re.search(r'<span class="particles">([^<]*)</span>', left)
        if pm:
            particles = clean_particles(_un(pm.group(1)).strip())
        km = re.search(r'<span class="kanji_character">(.*?)</span>', left, re.S)
        reading = strip_html(km.group(1)) if km else strip_html(left)
        r2 = re.sub(r'<span class="usefulness-stars"[^>]*>.*?</span>', '', right, flags=re.S)
        r2 = re.sub(r'<a class="label label-info"[^>]*>.*?</a>', '', r2, flags=re.S)
        meaning = strip_html(r2)
        usefulness = None
        sm = re.search(r'usefulness-stars"[^>]*title="(\d+) out of 5', right)
        if sm:
            usefulness = int(sm.group(1))
        tags = tag_names(parse_tags(right))
        out.append({'reading': reading, 'particles': particles, 'meaning': meaning or None,
                    'usefulness': usefulness, 'tags': tags})
    return out

def parse_jukugo(full_jukugo):
    out = []
    for m in re.finditer(r'<tr>(.*?)</tr>', full_jukugo, re.S):
        row = m.group(1)
        tds = re.findall(r'<td[^>]*>(.*?)</td>', row, re.S)
        if len(tds) < 2:
            continue
        left, right = tds[0], tds[1]
        word = None; reading = None; particles = None
        wm = re.search(r'<rt>([^<]*)</rt>', left)
        if wm:
            reading = _un(wm.group(1)).strip()
        km = re.search(r'<span class="kanji_character">(.*?)</span>', left, re.S)
        if km:
            wtext = km.group(1)
            wtext = re.sub(r'<rp>.*?</rp>', '', wtext, flags=re.S)
            wtext = re.sub(r'<rt>.*?</rt>', '', wtext, flags=re.S)
            word = strip_html(wtext)
        pm = re.search(r'<span class="particles">([^<]*)</span>', left)
        if pm:
            particles = clean_particles(_un(pm.group(1)).strip())
        blocks = re.findall(r'<p[^>]*>(.*?)</p>', right, re.S)
        meaning = None; usefulness = None; tags = []; comps = []; notes = None
        if blocks:
            b0 = blocks[0]
            # head is everything before the first <br/> (decomposition separator)
            head = re.split(r'<br\s*/?>', b0, maxsplit=1)[0]
            sm = re.search(r'title="(\d+) out of 5', head)
            if sm:
                usefulness = int(sm.group(1))
            tags = tag_names(parse_tags(head))
            h2 = re.sub(r'<span class="usefulness-stars"[^>]*>.*?</span>', '', head, flags=re.S)
            h2 = re.sub(r'<a class="label label-info"[^>]*>.*?</a>', '', h2, flags=re.S)
            meaning = strip_html(h2) or None
            # components: any /kanji/ link anywhere in the whole right cell
            for cm in re.finditer(r'<a[^>]*href="[^"]*/kanji/(\d+)-[^"]*"[^>]*>(.*?)</a>', b0, re.S):
                cid = int(cm.group(1)); inner = cm.group(2)
                if '<img' in inner:
                    img = extract_img_src(inner)
                    kanji = id_map.get(cid, {}).get('kanji')
                else:
                    img = None; kanji = _un(strip_html(inner))
                comps.append({'id': cid, 'kanji': kanji, 'image': img})
        if len(blocks) >= 2:
            notes = strip_html(blocks[1]) or None
        out.append({'word': word, 'reading': reading, 'particles': particles,
                    'meaning': meaning, 'usefulness': usefulness, 'tags': tags,
                    'components': comps, 'notes': notes})
    return out

def parse_lookalikes(full_lookalikes, own_id):
    out = []
    for m in re.finditer(r'<tr>(.*?)</tr>', full_lookalikes, re.S):
        row = m.group(1)
        if '<th>' in row:
            continue
        tds = re.findall(r'<td[^>]*>(.*?)</td>', row, re.S)
        if len(tds) < 4:
            continue
        kanji = None; kid = None
        km = re.search(r'/kanji/(\d+)-[^"]*"[^>]*>(.*?)</a>', tds[0], re.S)
        if km:
            kid = int(km.group(1)); inner = km.group(2)
            kanji = None if '<img' in inner else (_un(strip_html(inner)) or None)
        if kid == own_id:  # skip self-reference row
            continue
        meaning = strip_html(tds[1]) or None
        hint = strip_html(tds[2]) or None
        radical = None; rid = None; radical_image = None
        rm2 = re.search(r'/kanji/(\d+)-[^"]*"[^>]*>(.*?)</a>', tds[3], re.S)
        if rm2:
            inner = rm2.group(2)
            if '<img' in inner:
                radical_image = extract_img_src(inner)
                rid = int(rm2.group(1))
            else:
                txt = _un(strip_html(inner)) or None
                if txt:
                    radical = txt
                    rid = int(rm2.group(1))
        out.append({'kanji': kanji, 'id': kid, 'meaning': meaning, 'hint': hint,
                    'radical': radical, 'radical_id': rid, 'radical_image': radical_image})
    return out

def parse_used_in(full_used_in):
    out = []
    for m in re.finditer(r'<a[^>]*href="[^"]*/kanji/(\d+)-[^"]*"[^>]*>(.*?)</a>', full_used_in, re.S):
        kid = int(m.group(1)); inner = m.group(2)
        if '<img' in inner:
            img = extract_img_src(inner)
            kanji = id_map.get(kid, {}).get('kanji')
            out.append({'id': kid, 'kanji': kanji, 'image': img})
        else:
            out.append({'id': kid, 'kanji': _un(strip_html(inner)), 'image': None})
    return out

def clean_description(s):
    if not s:
        return None
    s = strip_html(s)
    s = re.sub(r'^\s*WHY\s+YOU\s+SHOULD\s+BOTHER\s*[：:]\s*', '', s, flags=re.I)
    return s or None

entries = []
for flds in rows:
    f = flds.split(FS)
    num = int(f[0])
    e = pos_map.get(num)
    if e is None:
        raise SystemExit('no index entry for position %s' % num)
    kanji_field = f[1]
    is_img = kanji_field.startswith('<img')
    kanji = None
    image = None
    if is_img:
        image = extract_img_src(kanji_field)
    else:
        kanji = _un(kanji_field).strip()
    header = f[14]
    usefulness = stars_to_int(header)
    sm = re.search(r'(\d+)\s+strokes', header)
    stroke_count = int(sm.group(1)) if sm else None
    entry_tags = tag_names(parse_tags(header))
    # visual aids: scan all fields
    all_fields_text = flds
    visual_aids = []
    seen_va = set()
    for vm in re.finditer(r'visualaid-[^"\'\s<>]+', all_fields_text):
        va = vm.group(0)
        if va not in seen_va:
            seen_va.add(va); visual_aids.append(va)
    stroke_order = extract_img_src(f[3]) if f[3].strip() else None
    mnemonic, mnem_imgs = parse_mnemonic(f[17])
    entry = {
        'id': e['id'],
        'position': num,
        'slug': unquote(e['slug']),
        'url': 'https://www.kanjidamage.com/kanji/%d-%s' % (e['id'], e['slug']),
        'kanji': kanji,
        'image': image,
        'meaning': _un(f[2]).strip(),
        'usefulness': usefulness,
        'stroke_count': stroke_count,
        'frequency_ranking': int(f[22]) if f[22].strip() else None,
        'tags': entry_tags,
        'description': clean_description(f[15]),
        'components': parse_components(header),
        'onyomi': parse_onyomi(f[16]),
        'mnemonic': mnemonic,
        'kunyomi': parse_kunyomi(f[18]),
        'jukugo': parse_jukugo(f[19]),
        'lookalikes': parse_lookalikes(f[20], e['id']),
        'used_in': parse_used_in(f[21]),
        'media': {'stroke_order': stroke_order, 'visual_aids': visual_aids},
    }
    entries.append(entry)

entries.sort(key=lambda x: x['position'])
with open(os.path.join(OUT, 'kanjidamage.json'), 'w', encoding='utf-8') as fh:
    json.dump(entries, fh, ensure_ascii=False, indent=1)

print('wrote kanjidamage.json with %d entries' % len(entries))

# ---------------- tags.json (already parsed above) ----------------
with open(os.path.join(OUT, 'tags.json'), 'w', encoding='utf-8') as fh:
    json.dump(tags, fh, ensure_ascii=False, indent=1)
print('wrote tags.json with %d tags' % len(tags))

# ---------------- onyomi-keywords.json ----------------
ony_html = fetch('https://www.kanjidamage.com/appendix/onyomikeywords')
ony_text = strip_html(ony_html)
keywords = {}
for line in ony_text.split('\n'):
    line = line.strip()
    if not line:
        continue
    m = re.match(r'^([A-Za-z]+)(\s*)([-−–])(\s*)(.+)$', line)
    if not m:
        continue
    if not m.group(2) and not m.group(4):
        # hyphenated English compound (e.g. "Long-vowel"), not a keyword entry
        continue
    val = m.group(5).strip().lstrip('-−–').strip()
    if val:
        keywords[m.group(1).lower()] = val
with open(os.path.join(OUT, 'onyomi-keywords.json'), 'w', encoding='utf-8') as fh:
    json.dump(keywords, fh, ensure_ascii=False, indent=1)
print('wrote onyomi-keywords.json with %d keywords' % len(keywords))

# ---------------- media ----------------
apkg = os.path.join(BASE, 'Official_KanjiDamage_deck.apkg')
media_map = json.load(open(os.path.join(BASE, 'extract', 'media'), encoding='utf-8'))
zf = zipfile.ZipFile(apkg)
n = 0
for name in zf.namelist():
    if name in ('collection.anki2', 'media'):
        continue
    real = media_map.get(name)
    if real is None:
        continue
    dst = os.path.join(OUT, 'media', real)
    with zf.open(name) as src, open(dst, 'wb') as out:
        out.write(src.read())
    n += 1
print('extracted %d media files' % n)

# ---------------- validation summary ----------------
missing = [e for e in entries if e['kanji'] is None and e['image'] is None]
print('entries with neither kanji nor image:', len(missing))
img_radicals = sum(1 for e in entries if e['image'])
print('image radicals:', img_radicals)
char = sum(1 for e in entries if e['kanji'])
print('character entries:', char)
