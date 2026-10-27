"""Count AI-writing and translated-prose tells in a Thai draft.md.

Usage:
  python -I thai_style_check.py draft.md [--top 5] [--json out.json] [--strict]
                                         [--genre academic|general|letter|chat|auto]

What it measures (body text only: frontmatter, headings, tables, images,
reference sections, [ตัวบท]...[/ตัวบท] blocks and “quoted” text are skipped)
  WARN   paragraph openers repeated (นอกจากนี้ / อย่างไรก็ตาม / ดังนั้น ...)
  WARN   stock AI phrases per 1,000 words above threshold (inflation, staging,
         closers, calques, vague authority, stacked hedges, assistant leakage)
  WARN   "ซึ่ง" chains, passive "ถูก" density, การ/ความ nominalization chains,
         "ของ" chains, em dashes, bold inside academic prose
  WARN   lists that chop prose (any genre): 3+ "- **label:**" items, 2+ items
         opening with a connective; academic: items over 200 characters
  WARN   "มีนัยสำคัญ" with no statistical context nearby (ambiguous)
  INFO   author stance present/absent, "ไม่ใช่ X แต่ Y" contrasts to re-check,
         long paragraphs without any citation, sentence-length profile
         (needs pythainlp), cliché openings in the introduction
Genre: --genre academic keeps every check; general skips the academic-only
checks (stance, long list items, bold in prose, "มัน"); letter and chat are aliases of general
(judge them on raw counts, the text is short); auto (default) guesses from
citations and section names. Thresholds are trial values tuned on a small sample of
published Thai journal prose. Numbers call for a human read; they are not
verdicts. Short texts (an email) should be judged on raw counts, not rates.
Exit code 1 only with --strict and at least one WARN.
"""
import argparse, json, re, statistics, sys

THAI = re.compile(r"[฀-๿]")
REF_HEAD = re.compile(r"^#\s*(เอกสารอ้างอิง|บรรณานุกรม|References?)", re.M)
CITE = re.compile(r"\((?:[^()]*?,\s*)?(?:19|20|25)\d{2}[a-zก-ฮ]?\)|et al\.|และคณะ|\b(?:19|20|25)\d{2}\)")
ACADEMIC_SECTION = re.compile(r"บทนำ|บทคัดย่อ|ทบทวนวรรณกรรม|วิธี(?:ดำเนินการ)?วิจัย|ผลการวิจัย|อภิปรายผล|กรอบแนวคิด|Abstract|Introduction|Method")
VERBATIM = re.compile(r"\[ตัวบท\].*?\[/ตัวบท\]", re.S)
QUOTED = re.compile(r"[“\"][^”\"]{8,}[”\"]")

OPENERS = ["นอกจากนี้", "อย่างไรก็ตาม", "อย่างไรก็ดี", "ดังนั้น", "ทั้งนี้", "ด้วยเหตุนี้",
           "ในขณะเดียวกัน", "ยิ่งไปกว่านั้น", "กล่าวโดยสรุป", "โดยสรุป", "ในทางกลับกัน", "ด้วยเหตุผลดังกล่าว"]

# (label, regex, max per 1,000 words, genres it applies to)
PHRASES = [
    ("คำขยายเกินจริง", r"อย่างยิ่ง|อย่างมหาศาล|อย่างก้าวกระโดด|กุญแจสำคัญ|หัวใจสำคัญ|มีบทบาทสำคัญ|บทบาทสำคัญอย่าง|ปฏิวัติ(?!ฝรั่งเศส|รัสเซีย|อุตสาหกรรม|สยาม|เขียว|จีน|อเมริก|\s*(?:พ\.ศ\.|ค\.ศ\.|ปี))|ปลดล็อก|เปิดประตูสู่|ก้าวสู่|พลิกโฉม|ทรงพลัง|อย่างไม่เคยมีมาก่อน", 1.0, "both"),
    ("โครงสร้างจัดฉาก (ไม่เพียง/มิใช่...หากแต่)", r"ไม่เพียงแต่|ไม่เพียง[^\s]{0,12}แต่ยัง|มิใช่[^\s]{0,30}หากแต่|ไม่ใช่แค่|ไม่ใช่เพียง", 0.8, "both"),
    ("ประโยคปิดสำเร็จรูป", r"สะท้อนให้เห็นถึงความสำคัญ|ไม่อาจมองข้าม|จึงเป็นสิ่งสำคัญ|อย่างหลีกเลี่ยงไม่ได้|เป็นสิ่งที่ปฏิเสธไม่ได้|ถือเป็นก้าวสำคัญ", 0.5, "both"),
    ("สำนวนแปลตรง", r"ในบริบทของ|ภูมิทัศน์(?:ของ|ทาง|ด้าน|การ|ธุรกิจ|สื่อ|ดิจิทัล|การเมือง|อุตสาหกรรม)|ทำให้มั่นใจว่า|ในแง่ของ|เป็นที่น่าสังเกตว่า|ทำการ(?:ศึกษา|วิเคราะห์|สำรวจ|ทดสอบ|พัฒนา)|ซึ่งกันและกัน|เพื่อที่จะ|หนึ่งใน[^\s]{0,20}ที่สำคัญที่สุด|ในส่วนของ|ภายใต้การ(?!ดูแล|กำกับ|ควบคุม|บังคับ|นำ|บริหาร|คุ้มครอง|สนับสนุน|อนุมัติ)|บนพื้นฐานของ|ผ่านทางการ", 2.0, "both"),
    ("สำนวนไทยที่ใช้ได้แต่ข้อความ AI ใช้ถี่", r"ให้ความสำคัญกับ|มีส่วนร่วมในการ|มีแนวโน้ม|มาพร้อมกับ|เมื่อพูดถึง", 3.0, "both"),
    ("คู่คำไม่เข้ากัน / แปลคำต่อคำ (ตรวจทุกจุด)", r"ตัดสินใจอย่างมีข้อมูล|การตัดสินใจที่มีข้อมูล|แก้ไขความท้าทาย|บรรลุความต้องการ|ตอบสนองความท้าทาย|เมื่อมันมาถึง", 0.0, "both"),
    ("อ้างอำนาจลอย ๆ", r"นักวิชาการหลายท่าน|นักวิชาการจำนวนมาก|งานวิจัยจำนวนมาก|หลายการศึกษา|เป็นที่ยอมรับกันโดยทั่วไป|เป็นที่ทราบกันดี|หลายฝ่ายเห็นว่า|ผู้เชี่ยวชาญหลายคน", 0.3, "both"),
    ("คำซ้อนมิติความเป็นไปได้", r"อาจจะมีแนวโน้ม|น่าจะอาจ|อาจจะน่าจะ|มีแนวโน้มที่จะอาจ|อาจมีความเป็นไปได้", 0.3, "both"),
    ("'มีความ' + คุณศัพท์", r"มีความ(?:สำคัญ|จำเป็น|ซับซ้อน|แตกต่าง|เหมาะสม|ชัดเจน|หลากหลาย|ยืดหยุ่น|โปร่งใส|น่าเชื่อถือ)", 2.0, "both"),
    ("'สามารถ...ได้' ถี่", r"(?<!ความ)(?<!ขีดความ)สามารถ", 6.0, "both"),
    ("'ส่งผลกระทบ' ไม่บอกทิศทาง", r"ส่งผลกระทบต่อ", 1.5, "both"),
    ("'ถือเป็น/ถือได้ว่า'", r"ถือเป็น|ถือได้ว่า|ถือว่าเป็น", 1.5, "both"),
    ("'มัน' ขึ้นต้นวลี ในงานวิชาการ (ตรวจว่ามีสิ่งอ้างถึง)", r"(?<![ก-๙])มัน(?:เป็นเรื่อง|เป็นสิ่ง|ทำให้|ช่วยให้|คือ)", 1.0, "academic"),
    ("'ของคุณ/ของท่าน' ถี่ (ตรวจว่าต้องแยกเจ้าของจริงไหม)", r"ของ(?:คุณ|ท่าน)(?!ภาพ|สมบัติ|ค่า|ธรรม|ลักษณะ|ประโยชน์|วุฒิ|หญิง|นาย|หมอ|ครู)", 4.0, "both"),
    ("'สิ่งนี้/สิ่งดังกล่าว' (ตำแหน่งให้ตรวจว่าอ้างกลับชัด)", r"สิ่งนี้|สิ่งดังกล่าว|สิ่งเหล่านี้|นั่นทำให้", 2.0, "both"),
    ("ถ้อยคำของผู้ช่วยหลุดในตัวบท", r"หากคุณต้องการให้ฉัน|ฉันสามารถ(?:ปรับ|เขียน|สรุป)(?:ข้อความ|บทความ|ฉบับ|ให้)|ต่อไปนี้คือ(?:ฉบับ|ร่าง|ข้อความ)|หวังว่า(?:ข้อมูล|บทความ|คำตอบ)นี้", 0.0, "both"),
]

CHAIN_WHICH = re.compile(r"ซึ่ง[^\s]{0,80}ซึ่ง")                      # two ซึ่ง inside one clause
PASSIVE = re.compile(r"ถูก(?!ต้อง|หัก|กฎหมาย|ใจ|ลง|กว่า|สุขลักษณะ|จริต|โฉลก|คอ|ชะตา|ระเบียบ)")
NOMINAL = re.compile(r"การ[^\s]{1,14}(?:ใน|ของ|เพื่อ)?การ[^\s]{1,14}การ")  # การ...การ...การ
NOMINAL2 = re.compile(r"การดำเนินการ(?:ใน|เพื่อ)การ|การจัดทำการ|ความ[^\s]{1,10}ความ[^\s]{1,10}ความ")
OF_CHAIN = re.compile(r"ของ[^\s]{1,25}ของ[^\s]{1,25}ของ")
DASH = re.compile(r"—|(?<![0-9๐-๙])–(?![0-9๐-๙])")                  # interrupting dashes; keeps 15–20
BULLET = re.compile(r"^(\s*)(?:[-*•]|\d+[.)])\s+")
BOLD = re.compile(r"\*\*[^*]+\*\*")
LABEL_ITEM = re.compile(r"^\*\*[^*]{1,40}\*\*\s*[:：]|^\*\*[^*]{1,40}[:：]\*\*")   # "- **หัวข้อ:** ..."
LINKED_ITEM = re.compile(r"^(?:ดังนั้น|จึง|เพราะ|แต่|อย่างไรก็ตาม|อย่างไรก็ดี|นอกจากนี้|ยิ่งไปกว่านั้น|ด้วยเหตุนี้|ซึ่ง|ส่งผลให้|ในขณะเดียวกัน)")
LONG_ITEM = 200                                                         # characters: a paragraph behind a bullet
SIGNIF = re.compile(r"มีนัยสำคัญ")
STAT_CTX = re.compile(r"ทางสถิติ|p\s*[<=>]|ที่ระดับ|\.0[0-9]+|α|นัยสำคัญทางสถิติ")
STANCE = re.compile(r"ผู้เขียน(?:เห็นว่า|มีความเห็นว่า|ตั้งข้อสังเกต|เสนอ|อนุมาน|สันนิษฐาน|เห็นต่าง)|ในมุมมองของผู้เขียน|ในทัศนะของผู้เขียน")
CONTRAST = re.compile(r"ไม่(?:ใช่|ได้)(?!เพียง|แค่)[^\s]{1,25}\s(?:แต่|หากแต่)")   # "ไม่ใช่ X แต่ Y": scope check
CLICHE_OPEN = re.compile(r"ในยุคปัจจุบัน|ในโลกยุค|ในยุคที่|ปัจจุบันโลก|ในสังคมปัจจุบัน|ท่ามกลางกระแส|เป็นที่ทราบกันดี")


def strip_frontmatter(text):
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4:]
    return text


def body_paragraphs(text):
    """Return [(line_no, section, paragraph)] of prose paragraphs only."""
    m = REF_HEAD.search(text)
    if m:
        text = text[:m.start()]
    out, section, buf, start = [], "", [], 0
    for i, line in enumerate(text.split("\n"), 1):
        s = line.strip()
        if s.startswith("#"):
            section = s.lstrip("# ").strip()
            flush(out, buf, start, section); buf = []
            continue
        if not s:
            flush(out, buf, start, section); buf = []
            continue
        if s.startswith("|") or s.startswith("![") or s.startswith("ที่มา:") or re.match(r"^(ตารางที่|ภาพที่|คำสำคัญ|Keywords)", s):
            flush(out, buf, start, section); buf = []
            continue
        if not buf:
            start = i
        buf.append(s)
    flush(out, buf, start, section)
    return out


def flush(out, buf, start, section):
    if buf:
        p = " ".join(buf)
        if THAI.search(p):
            out.append((start, section, p))


def list_runs(text):
    """Return (runs, bold_prose_lines). A run is a list of (line_no, depth, item_text);
    blank lines between bullets stay inside the run, indented lines continue an item."""
    m = REF_HEAD.search(text)
    if m:
        text = text[:m.start()]
    text = VERBATIM.sub(lambda v: "\n" * v.group(0).count("\n"), text)
    runs, run, bold = [], [], []
    for i, line in enumerate(text.split("\n"), 1):
        s = line.strip()
        b = BULLET.match(line)
        if b:
            run.append([i, len(b.group(1).expandtabs(4)) // 2, line[b.end():].strip()])
        elif run and s and line[:1].isspace() and not s.startswith("|"):
            run[-1][2] += " " + s
        elif not s:
            continue
        else:
            if run:
                runs.append(run); run = []
            if not s.startswith(("#", "|", "![")) and THAI.search(s) and BOLD.search(QUOTED.sub(" ", s)):
                bold.append((i, s[:50]))
    if run:
        runs.append(run)
    runs = [[(ln, d, QUOTED.sub(" ", t)) for ln, d, t in r] for r in runs]
    return [r for r in runs if THAI.search(" ".join(t for _, _, t in r))], bold


def clean(p):
    """Remove verbatim-law blocks and quoted text before counting tells."""
    p = VERBATIM.sub(" ", p)
    p = QUOTED.sub(" ", p)
    return p


def count_words(text):
    try:
        from pythainlp.tokenize import word_tokenize
        return sum(1 for w in word_tokenize(text, keep_whitespace=False) if w.strip()), "pythainlp"
    except Exception:
        return max(1, int(len(THAI.findall(text)) / 4.5)), "approx"


def sentences(text):
    """Sentence-ish units. crfcut needs python-crfsuite; otherwise Thai prose
    separates clauses with spaces, which is close enough for a length profile."""
    try:
        from pythainlp.tokenize import sent_tokenize
    except Exception:
        return None, None
    try:
        return [s for s in sent_tokenize(text) if len(s.strip()) > 10], "crfcut"
    except Exception:
        try:
            return [s for s in sent_tokenize(text, engine="whitespace+newline") if len(s.strip()) > 10], "ช่วงคั่นด้วยช่องว่าง"
        except Exception:
            return None, None


def guess_genre(paras, body):
    cites = len(CITE.findall(body))
    sections = " ".join(sec for _, sec, _ in paras)
    if cites >= 2 or ACADEMIC_SECTION.search(sections):
        return "academic", f"เดาจากการอ้างอิง {cites} จุด / ชื่อหัวข้อ"
    return "general", f"เดาจากการอ้างอิง {cites} จุด และไม่มีหัวข้อแบบบทความวิจัย"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("draft")
    ap.add_argument("--top", type=int, default=5, help="examples to show per finding")
    ap.add_argument("--json")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--genre", choices=["academic", "general", "letter", "chat", "auto"], default="auto",
                    help="academic keeps every check; general (and its aliases letter, chat) skips academic-only checks")
    a = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8")   # Windows consoles default to cp874
    except Exception:
        pass

    raw = open(a.draft, encoding="utf-8").read()
    text = strip_frontmatter(raw)
    paras = body_paragraphs(text)
    if not paras:
        print("ERROR  ไม่พบย่อหน้าเนื้อหาภาษาไทย"); sys.exit(1)
    cleaned = [(ln, sec, clean(p)) for ln, sec, p in paras]
    body = "\n".join(p for _, _, p in cleaned)
    words, wmode = count_words(body)
    per = 1000.0 / words
    verbatim_blocks = len(VERBATIM.findall(text))
    if a.genre == "auto":
        genre, why = guess_genre(cleaned, body)
    elif a.genre in ("letter", "chat"):
        genre, why = "general", f"ระบุโดยผู้ใช้ ({a.genre} นับแบบ general ข้อความสั้นให้ดูจำนวนจริง)"
    else:
        genre, why = a.genre, "ระบุโดยผู้ใช้"
    academic = genre == "academic"
    findings, report = [], []

    def add(level, label, count, examples=None, limit=None, note=""):
        rate = count * per
        findings.append({"level": level, "label": label, "count": count, "per_1000": round(rate, 2), "limit": limit, "examples": examples or []})
        lim = f" (เกณฑ์ ≤ {limit}/1,000 คำ)" if limit is not None else ""
        report.append(f"{level:5}  {label}: {count} ครั้ง = {rate:.1f}/1,000 คำ{lim} {note}".rstrip())
        for ex in (examples or [])[:a.top]:
            report.append(f"         บ.{ex[0]}: …{ex[1]}…")

    def ctx(p, m, w=28):
        s, e = max(0, m.start() - w), min(len(p), m.end() + w)
        return p[s:e].replace("\n", " ")

    # 1. paragraph openers
    opener_hits, prev, consecutive = {}, None, 0
    for ln, sec, p in cleaned:
        hit = next((o for o in OPENERS if p.startswith(o)), None)
        if hit:
            opener_hits.setdefault(hit, []).append((ln, p[:40]))
            consecutive = consecutive + 1 if prev else 1
        else:
            consecutive = 0
        prev = hit
    total_open = sum(len(v) for v in opener_hits.values())
    worst = max(opener_hits.items(), key=lambda kv: len(kv[1]), default=None)
    level = "WARN" if (worst and len(worst[1]) >= 3) or total_open > len(cleaned) * 0.3 else "INFO"
    detail = ", ".join(f"{k} {len(v)}" for k, v in sorted(opener_hits.items(), key=lambda kv: -len(kv[1]))) or "ไม่มี"
    add(level, "ย่อหน้าที่เปิดด้วยคำเชื่อมสำเร็จรูป", total_open,
        [(ln, s) for v in opener_hits.values() for ln, s in v], None, f"[{detail}] จาก {len(cleaned)} ย่อหน้า")

    # 2. stock phrases
    for label, rx, limit, genres in PHRASES:
        if genres == "academic" and not academic:
            continue
        r = re.compile(rx)
        ex = [(ln, ctx(p, m)) for ln, _, p in cleaned for m in r.finditer(p)]
        add("WARN" if len(ex) * per > limit else "INFO", label, len(ex), ex, limit)

    # 3. structural tells
    for label, r, limit in [("'ซึ่ง' ซ้อนกันในประโยคเดียว", CHAIN_WHICH, 1.0),
                            ("กรรมวาจก 'ถูก' (ไม่นับ ถูกต้อง/ถูกหัก/ถูกกฎหมาย)", PASSIVE, 4.5),
                            ("'การ/ความ' ซ้อนสามชั้น", NOMINAL, 1.2),
                            ("'การดำเนินการในการ' / 'ความ...ความ...ความ'", NOMINAL2, 0.3),
                            ("'ของ' ซ้อนสามชั้น", OF_CHAIN, 0.8),
                            ("ขีดแทรก em/en dash ในเนื้อหา (ไม่นับขีดบอกช่วงตัวเลข)", DASH, 0.0)]:
        ex = [(ln, ctx(p, m)) for ln, _, p in cleaned for m in r.finditer(p)]
        add("WARN" if len(ex) * per > limit else "INFO", label, len(ex), ex, limit)

    # 3b. lists vs prose (same criterion in every genre; see "รายการหรือร้อยแก้ว")
    runs, bold_prose = list_runs(text)
    items = [it for r in runs for it in r]
    if items:
        label = [(ln, t[:50]) for ln, _, t in items if LABEL_ITEM.match(t)]
        add("WARN" if len(label) >= 3 else "INFO", "บูลเล็ตขึ้นต้นด้วยป้ายตัวหนา + ทวิภาค (ตรวจว่าเป็นเหตุผลต่อเนื่องที่ควรเขียนเป็นร้อยแก้วไหม)",
            len(label), label, None, "รายการขั้นตอน/เกณฑ์ที่ป้ายช่วยหาเจอคงไว้ได้")
        linked = [(ln, t[:50]) for ln, _, t in items if LINKED_ITEM.match(LABEL_ITEM.sub("", t).strip())]
        add("WARN" if len(linked) >= 2 else "INFO", "ข้อในรายการขึ้นต้นด้วยคำเชื่อม (ข้อนั้นต่อจากข้อก่อน ควรเป็นร้อยแก้ว)", len(linked), linked)
        long_ = [(ln, f"{len(t)} อักขระ: {t[:40]}") for ln, _, t in items if len(t) > LONG_ITEM]
        add("WARN" if (long_ and academic) else "INFO", f"ข้อในรายการยาวเกิน {LONG_ITEM} อักขระ (ย่อหน้าที่ใส่จุดนำหน้า)", len(long_), long_)
        short = [(r[0][0], r[0][2][:50]) for r in runs
                 if sum(1 for _, d, _ in r if d == min(d for _, d, _ in r)) <= 2]
        add("INFO", "รายการ 1-2 ข้อ (เขียนในประโยคได้)", len(short), short)
        nested = [(ln, t[:50]) for ln, d, t in items if d >= 2]
        add("INFO", "รายการซ้อนเกินหนึ่งชั้น", len(nested), nested)
        if academic:
            add("INFO", "รายการในงานวิชาการ (ตรวจว่าเป็นวัตถุประสงค์ สมมติฐาน เกณฑ์ หรือขั้นตอนวิธี และรูปแบบวารสารรองรับ)",
                len(runs), [(r[0][0], r[0][2][:50]) for r in runs])
    add("WARN" if (bold_prose and academic) else "INFO", "ตัวหนาในย่อหน้าร้อยแก้ว", len(bold_prose), bold_prose, None,
        "" if academic else "(งานทั่วไป: ใช้กับวันที่ จำนวนเงิน สิ่งที่ต้องทำ)")

    # 4. significance without statistics
    ex = []
    for ln, _, p in cleaned:
        for m in SIGNIF.finditer(p):
            window = p[max(0, m.start() - 60): m.end() + 60]
            if not STAT_CTX.search(window):
                ex.append((ln, ctx(p, m)))
    add("WARN" if ex else "INFO", "'มีนัยสำคัญ' โดยไม่มีบริบทสถิติใกล้เคียง (กำกวม: สถิติ หรือสำคัญเชิงเนื้อหา)", len(ex), ex)

    # 5. author stance (academic only, informational)
    if academic:
        stance = [(ln, ctx(p, m)) for ln, _, p in cleaned for m in STANCE.finditer(p)]
        add("INFO", "ระบุเจ้าของความเห็น (ผู้เขียนเห็นว่า ...)", len(stance), stance[:2], None,
            "" if stance else "ไม่พบ ถ้ามีย่อหน้าวิเคราะห์ ตรวจว่าแยกผลของงานที่อ้างออกจากความเห็นผู้เขียนได้ชัด")

    # 6. "ไม่ใช่ X แต่ Y" contrasts: scope check, informational
    ex = [(ln, ctx(p, m)) for ln, _, p in cleaned for m in CONTRAST.finditer(p)]
    add("INFO", "คู่ตรงข้าม 'ไม่ใช่ X แต่ Y' (ตำแหน่งให้ตรวจว่าไม่ตัด X ออกเกินหลักฐาน)", len(ex), ex)

    # 7. paragraphs without citation
    nocite = [(ln, f"[{sec}] " + p[:45]) for ln, sec, p in cleaned
              if len(p) > 450 and not CITE.search(p) and not re.search(r"บทคัดย่อ|สรุป|Abstract", sec)]
    if academic:
        add("INFO", "ย่อหน้ายาว (>450 อักขระ) ที่ไม่มีการอ้างอิง", len(nocite), nocite)

    # 8. cliché opening in introduction
    intro = [(ln, sec, p) for ln, sec, p in cleaned if "บทนำ" in sec][:2] or cleaned[:1]
    ex = [(ln, ctx(p, m)) for ln, _, p in intro for m in CLICHE_OPEN.finditer(p)]
    add("WARN" if ex else "INFO", "เปิดเรื่องแบบสำเร็จรูป", len(ex), ex)

    # 9. sentence-length profile (informational)
    sents, smode = sentences(body)
    if sents and len(sents) >= 10:
        lens = [len(s) for s in sents]
        cv = statistics.pstdev(lens) / statistics.mean(lens)
        longest = sorted(((len(s), s[:60]) for s in sents), reverse=True)[:3]
        add("INFO", f"ความยาวประโยค ({smode})", len(sents), [(0, f"{l} อักขระ: {s}") for l, s in longest], None,
            f"เฉลี่ย {statistics.mean(lens):.0f} อักขระ, CV {cv:.2f} (ต่ำมาก = ภาระการอ่านเท่ากันทุกประโยค ให้ดูประโยคยาวสุดว่าต้องแบ่งไหม)")
    else:
        add("INFO", "ความยาวประโยค", 0, None, None, "ข้าม (ต้องมี pythainlp)")

    warns = sum(1 for f in findings if f["level"] == "WARN")
    print(f"ตรวจ {len(cleaned)} ย่อหน้า ประมาณ {words:,} คำ ({wmode}); ประเภทงาน: {genre} ({why}); ข้าม [ตัวบท] {verbatim_blocks} ช่วง\n")
    print("\n".join(report))
    print(f"\nสรุป: WARN {warns} รายการ เกณฑ์เป็นค่าทดลอง ตัวเลขเป็นสัญญาณเรียกตรวจ ให้อ่านประโยคจริงก่อนแก้ และห้ามแก้ข้อความใน [ตัวบท] หรือข้อความยกตรง")
    if a.json:
        json.dump({"words": words, "paragraphs": len(cleaned), "genre": genre, "findings": findings}, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    sys.exit(1 if a.strict and warns else 0)


if __name__ == "__main__":
    main()
