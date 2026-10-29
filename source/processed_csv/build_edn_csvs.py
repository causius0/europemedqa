#!/usr/bin/env python3
"""Parse EDN France exam PDFs (CNG annales 2023-2025) into question/answer CSVs.

Reads pdftotext -layout text dumps, splits stems/questions, extracts choices,
links embedded figures, writes one CSV per year.

No answer key exists (official CNG PDFs are questions-only; community
corrections are platform-locked) -> correct_answer left empty.
"""
import csv, os, re, sys
try:
    import fitz
    HAVE_FITZ = True
except ImportError:
    HAVE_FITZ = False

SRC = os.path.expanduser('~/workspace/medical-ai-leaderboard-staging/repo/data/updates_raw/edn_france')
TXTDIR = '/tmp/edn_txt'
OUTDIR = os.path.expanduser('~/workspace/medical-ai-leaderboard-staging/repo/data/processed_csv')
IMGDIR = os.path.join(OUTDIR, 'images')

import subprocess as _sp

# (year, paper_label, pdf_rel, txt_name)
PAPERS_TXT = [
    ('2023', 'P1', '2023/EDN_P1.pdf', '2023_EDN_P1.txt'),
    ('2023', 'P2', '2023/EDN_P2.pdf', '2023_EDN_P2.txt'),
    ('2023', 'P3', '2023/EDN_P3.pdf', '2023_EDN_P3.txt'),
    ('2023', 'LCA', '2023/lca/EDN_LCA_P.pdf', '2023_LCA.txt'),
    ('2024', 'P1', '2024/EDN_P1.pdf', '2024_EDN_P1.txt'),
    ('2024', 'P2', '2024/EDN_P2.pdf', '2024_EDN_P2.txt'),
    ('2024', 'P3', '2024/EDN_P3.pdf', '2024_EDN_P3.txt'),
    ('2024', 'LCA', '2024/lca/EDN_LCA_P.pdf', '2024_LCA.txt'),
    ('2025', 'R1', '2025/EDN_P1_reserve.pdf', '2025_EDN_P1.txt'),
    ('2025', 'P2', '2025/EDN_P2.pdf', '2025_EDN_P2.txt'),
    ('2025', 'P3', '2025/EDN_P3.pdf', '2025_EDN_P3.txt'),
    ('2025', 'LCA', '2025/lca/EDN_LCA_P.pdf', '2025_LCA.txt'),
]


def ensure_text():
    os.makedirs(TXTDIR, exist_ok=True)
    for year, paper, pdf_rel, txt_name in PAPERS_TXT:
        dest = os.path.join(TXTDIR, txt_name)
        if not os.path.exists(dest):
            _sp.run(['pdftotext', '-layout', os.path.join(SRC, pdf_rel), dest], check=True)

# (year, paper_label, pdf_name)
PAPERS = [
    ('2023', 'P1', 'EDN_P1.pdf'), ('2023', 'P2', 'EDN_P2.pdf'), ('2023', 'P3', 'EDN_P3.pdf'),
    ('2023', 'LCA', 'lca/EDN_LCA_P.pdf'),
    ('2024', 'P1', 'EDN_P1.pdf'), ('2024', 'P2', 'EDN_P2.pdf'), ('2024', 'P3', 'EDN_P3.pdf'),
    ('2024', 'LCA', 'lca/EDN_LCA_P.pdf'),
    ('2025', 'R1', 'EDN_P1_reserve.pdf'), ('2025', 'P2', 'EDN_P2.pdf'), ('2025', 'P3', 'EDN_P3.pdf'),
    ('2025', 'LCA', 'lca/EDN_LCA_P.pdf'),
]
PDFMAP = {(y, p): f'{y}/{pdf}' for y, p, pdf in PAPERS}
MIN_DIM = 100  # min(w,h) for a figure worth extracting (<100 = UI decoration)

RE_STEM = re.compile(r'^(KFP|DP|QI|TCS|LCA) (\d+)\s*$')
RE_Q = re.compile(r'^Question (\d+) - (.+?)\s*$')
RE_FOOTER = re.compile(r'^Epreuve .*?\b(\d+)/(\d+)\s*$')
RE_TITLE = re.compile(r'^\s*Epreuve de .*$')
RE_PROP = re.compile(r'^ {1,12}Proposition ([A-P])\s*$')
RE_REPONSE = re.compile(r'^\s*Réponse\s*:\s*$')
RE_FIN = re.compile(r'--- Fin de copie ---')
RE_ZONELABEL = re.compile(r'^\s*(\d+)\s*-\s*(.*?)\s*$')
LIKERT = ['Très peu probable', 'Peu probable', 'Ni plus ni moins', 'Probable', 'Très probable']
IMG_KW = re.compile(
    r'ci-dessous|ci-dessus|'
    r'\b(figures?|images?|clichés?|photos?|schémas?|tracés?|courbes?)\b|'
    r'\b(ECG|électrocardiogrammes?)\b|'
    r'\b(radiographies?|scanners?|scanographies?|coupes?)\b|'
    r'\bradio\b',
    re.I)

issues = []  # (year, paper, qid, message)


def clean(s):
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def join_lines(lines):
    """Join wrapped layout lines; trailing '-' = hyphenation -> concat directly."""
    out = ''
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        if out.endswith('-'):
            out += ln
        else:
            out = (out + ' ' + ln).strip() if out else ln
    return clean(out)


def parse_paper(year, paper, txt_path):
    raw = open(txt_path, encoding='utf-8').read().replace('\f', '\n')
    lines = raw.split('\n')
    questions = []
    page = 1
    stem = None  # (type, num)
    stem_text_lines = []  # vignette text between stem header and its first question
    cur = None   # current question dict
    q_pages = []

    def flush():
        nonlocal cur
        if cur is not None:
            finalize(cur)
            questions.append(cur)
            cur = None

    def finalize(q):
        # split body into question text vs choices
        body = q['body']  # list of (line, page)
        text_lines, choices, zone_labels = [], [], []
        mode = 'text'
        cur_letter, cur_clines = None, []
        likert_done = False
        in_legend = False  # QZP: inside figure zone-label legend
        for ln, pg in body:
            if RE_FIN.search(ln):
                break
            # QZP figure legend: "N - label" lines (label may wrap onto following lines)
            if q['is_qzp'] and mode == 'text':
                mz = RE_ZONELABEL.match(ln)
                if mz:
                    zone_labels.append([mz.group(1), clean(mz.group(2))])
                    in_legend = True
                    continue
                if in_legend and ln.strip():
                    zone_labels[-1][1] = (zone_labels[-1][1] + ' ' + clean(ln)).strip()
                    continue
            mp = RE_PROP.match(ln)
            if mp and mode == 'text':
                # start of choices
                if cur_letter:
                    choices.append((cur_letter, join_lines(cur_clines)))
                cur_letter, cur_clines = mp.group(1), []
                mode = 'choices'
                continue
            if mode == 'text' and RE_REPONSE.match(ln):
                mode = 'reponse'  # QROC answer area: ignore rest
                continue
            if mode == 'text' and 'Très peu probable' in ln and 'Très probable' in ln:
                parts = [p.strip() for p in re.split(r'\s{2,}', ln.strip()) if p.strip()]
                if len(parts) >= 5:
                    choices.extend([(chr(65 + i), parts[i]) for i in range(5)])
                else:  # fallback: fixed labels
                    choices.extend([(chr(65 + i), LIKERT[i]) for i in range(5)])
                likert_done = True
                mode = 'likert'
                continue
            if mode == 'choices':
                if mp:  # next proposition
                    choices.append((cur_letter, join_lines(cur_clines)))
                    cur_letter, cur_clines = mp.group(1), []
                else:
                    cur_clines.append(ln)
                continue
            if mode == 'reponse':
                continue
            if mode == 'likert':
                continue
            text_lines.append(ln)
        if cur_letter:
            choices.append((cur_letter, join_lines(cur_clines)))
        q['choices'] = choices
        q['text'] = join_lines(text_lines)
        if zone_labels:
            zl = '; '.join(f'{n} - {t}' for n, t in zone_labels)
            q['text'] = (q['text'] + f' [Zones de la figure : {zl}]').strip()
        q['pages'] = sorted(set(q_pages))

    for ln in lines:
        if RE_FIN.search(ln):
            flush()
            break
        mf = RE_FOOTER.match(ln)
        if mf:
            page = int(mf.group(1))
            continue
        if RE_TITLE.match(ln):
            continue
        ms = RE_STEM.match(ln)
        if ms:
            flush()
            stem = (ms.group(1), ms.group(2))
            stem_text_lines = []
            continue
        mq = RE_Q.match(ln)
        if mq:
            flush()
            fmt = mq.group(2)
            cur = {'sub': int(mq.group(1)), 'format': fmt, 'body': [],
                   'stem': stem, 'start_page': page,
                   'stem_text': join_lines(stem_text_lines),
                   'is_qzp': 'zone à pointer' in fmt}
            q_pages = [page]
            continue
        if cur is not None:
            if ln.strip() == '':
                cur['body'].append(('', page))
            else:
                cur['body'].append((ln, page))
            q_pages.append(page)
        elif stem is not None and ln.strip():
            stem_text_lines.append(ln)
    flush()

    # assign ids
    for q in questions:
        st, sn = q['stem'] if q['stem'] else ('NA', '0')
        q['qid'] = f"edn{year}_{paper}_{st}{sn}_q{q['sub']}"
    return questions


def extract_images(year, paper, pdf_rel):
    """Save embedded figures (min dim >= MIN_DIM, skip title page). Returns {1-idx page: [fnames]}."""
    page_map, saved = {}, {}
    if not HAVE_FITZ:
        return page_map, 0
    d = fitz.open(os.path.join(SRC, pdf_rel))
    outdir = os.path.join(IMGDIR, f'edn_france_{year}')
    os.makedirs(outdir, exist_ok=True)
    for pno, page in enumerate(d):
        if pno == 0:
            continue  # title page: EDN banner
        for img in page.get_images(full=True):
            xref, w, h = img[0], img[2], img[3]
            if min(w, h) < MIN_DIM:
                continue
            if xref not in saved:
                fname = f'edn_france_{year}_{paper}_p{pno + 1:03d}_xref{xref}.png'
                try:
                    pix = fitz.Pixmap(d, xref)
                    if pix.n > 4:
                        pix = fitz.Pixmap(fitz.csRGB, pix)
                    # skip blank/uniform images (masks, empty placeholders)
                    s = pix.samples
                    step = max(1, len(s) // 4000)
                    vals = s[::step]
                    if max(vals) - min(vals) < 12:
                        continue
                    pix.save(os.path.join(outdir, fname))
                except Exception as e:
                    issues.append((year, paper, f'image save failed {fname}: {e}'))
                    continue
                saved[xref] = fname
            page_map.setdefault(pno + 1, [])
            if saved[xref] not in page_map[pno + 1]:
                page_map[pno + 1].append(saved[xref])
    d.close()
    return page_map, len(saved)


def link_images(year, paper, pdf_rel, qs):
    page_map, n_saved = extract_images(year, paper, pdf_rel)
    linked = 0
    claimed = {}  # image fname -> stem key of question that claimed it
    for q in qs:
        cands = []
        for pg in q['pages'] + [max(q['pages']) + 1]:
            cands.extend(page_map.get(pg, []))
        cands = list(dict.fromkeys(cands))
        needs = q['is_qzp'] or IMG_KW.search(q['text'] or '') or IMG_KW.search(q.get('stem_text') or '')
        if needs:
            stemkey = q['stem']
            # prefer a figure not already claimed by a *different* stem
            # (sub-questions of one stem legitimately share a figure)
            pick = None
            for c in cands:
                if claimed.get(c, stemkey) == stemkey:
                    pick = c
                    break
            if pick is None and cands:
                pick = cands[0]
            if pick:
                q['image_file'] = pick
                claimed.setdefault(pick, stemkey)
                linked += 1
            else:
                issues.append((year, q['qid'],
                               'QZP but no figure found' if q['is_qzp'] else 'image keyword but no figure found'))
        else:
            q['image_file'] = ''
    return n_saved, linked


def main():
    ensure_text()
    all_q = {}
    img_stats = {}
    for year, paper, pdf_rel, txt_name in PAPERS_TXT:
        txt = os.path.join(TXTDIR, txt_name)
        qs = parse_paper(year, paper, txt)
        n_saved, linked = link_images(year, paper, pdf_rel, qs)
        img_stats[(year, paper)] = (n_saved, linked)
        all_q.setdefault(year, []).extend(qs)
        print(f'{year} {paper}: {len(qs)} questions, {n_saved} images, {linked} linked')

    # write CSVs
    cols = ['exam_id', 'question_number', 'question_id', 'question_text',
            'choice_a', 'choice_b', 'choice_c', 'choice_d', 'choice_e',
            'correct_answer', 'image_file', 'language', 'country', 'year']
    for year in ('2023', '2024', '2025'):
        qs = all_q[year]
        path = os.path.join(OUTDIR, f'edn_france_{year}.csv')
        with open(path, 'w', encoding='utf-8', newline='') as fh:
            w = csv.writer(fh)
            w.writerow(cols)
            for i, q in enumerate(qs, 1):
                ch = {letter: text for letter, text in q['choices']}
                if len(q['choices']) > 5:
                    issues.append((year, q['qid'], f"{len(q['choices'])} proposals; kept A-E, dropped {len(q['choices'])-5}"))
                if not q['choices'] and not q['is_qzp'] and 'ouverte' not in q['format'] and 'concordance' not in q['format']:
                    issues.append((year, q['qid'], f"no choices parsed (format: {q['format']})"))
                if not q['text']:
                    issues.append((year, q['qid'], 'empty question text'))
                w.writerow([
                    f'edn_france_{year}', i, q['qid'], q['text'],
                    ch.get('A', ''), ch.get('B', ''), ch.get('C', ''),
                    ch.get('D', ''), ch.get('E', ''),
                    '',  # correct_answer: no key exists
                    q.get('image_file', ''),
                    'fr', 'France', year,
                ])
        print(f'wrote {path}: {len(qs)} rows')

    print('\nISSUES:', len(issues))
    for it in issues[:60]:
        print(it)
    with open(os.path.join(OUTDIR, 'edn_france_build_issues.log'), 'w', encoding='utf-8') as fh:
        fh.write(f'total issues: {len(issues)}\n')
        for it in issues:
            fh.write(repr(it) + '\n')
    print('full issue list -> edn_france_build_issues.log')


if __name__ == '__main__':
    main()
