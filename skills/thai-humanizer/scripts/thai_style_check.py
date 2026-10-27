"""Count AI-writing and translated-prose tells in a Thai draft.md.

Usage:
  python -I thai_style_check.py draft.md [--top 5] [--json out.json] [--strict]

What it measures (body text only: frontmatter, headings, tables, images,
reference sections, [ตัวบท]...[/ตัวบท] blocks and “quoted” text are skipped)
  WARN   paragraph openers repeated (นอกจากนี้ / อย่างไรก็ตาม / ดังนั้น ...)
  WARN   stock AI phrases per 1,000 words above threshold (inflation, staging,
         closers, calques, vague authority, stacked hedges)
  WARN   "ซึ่ง" chains, passive "ถูก" density, การ/ความ nominalization chains,
         "ของ" chains, em dashes, bullets/bold inside prose
  WARN   "มีนัยสำคัญ" with no statistical context nearby
  WARN   no author stance ("ผู้เขียนเห็นว่า" ...) in an academic article
  INFO   long paragraphs without any citation, sentence-length uniformity
         (needs pythainlp), cliché openings in the introduction
This is a style report, not a detector: numbers guide a human read.
Exit code 1 only with --strict and at least one WARN.
"""
import argparse, json, re, statistics, sys

THAI = re.compile(r"[฀-๿]")
REF_HEAD = re.compile(r"^#\s*(เอกสารอ้างอิง|บรรณานุกรม|References?)", re.M)
CITE = re.compile(r"\((?:[^()]*?,\s*)?(?:19|20|25)\d{2}[a-zก-ฮ]?\)|et al\.|และคณะ|\b(?:19|20|25)\d{2}\)")
VERBATIM = re.compile(r"\[ตัวบท\].*?\[/ตัวบท\]", re.S)
QUOTED = re.compile(r"[“\"][^”\"]{8,}[”\"]")

OPENERS = ["นอกจากนี้", "อย่างไรก็ตาม", "อย่างไรก็ดี", "ดังนั้น", "ทั้งนี้", "ด้วยเหตุนี้",
           "ในขณะเดียวกัน", "ยิ่งไปกว่านั้น", "กล่าวโดยสรุป", "โดยสรุป", "ในทางกลับกัน", "ด้วยเหตุผลดังกล่าว"]

# (label, regex, max per 1,000 words)
PHRASES = [
    ("คำขยายเกินจริง", r"อย่างยิ่ง|อย่างมหาศาล|อย่างก้าวกระโดด|กุญแจสำคัญ|หัวใจสำคัญ|มีบทบาทสำคัญ|บทบาทสำคัญอย่าง|ปฏิวัติ|ปลดล็อก|เปิดประตูสู่|ก้าวสู่|พลิกโฉม|ทรงพลัง|อย่างไม่เคยมีมาก่อน", 1.0),
    ("โครงสร้างจัดฉาก (ไม่เพียง/มิใช่...หากแต่)", r"ไม่เพียงแต่|ไม่เพียง[^\s]{0,12}แต่ยัง|มิใช่[^\s]{0,30}หากแต่|ไม่ใช่แค่|ไม่ใช่เพียง", 0.8),
    ("ประโยคปิดสำเร็จรูป", r"สะท้อนให้เห็นถึงความสำคัญ|ไม่อาจมองข้าม|จึงเป็นสิ่งสำคัญ|อย่างหลีกเลี่ยงไม่ได้|เป็นสิ่งที่ปฏิเสธไม่ได้|ถือเป็นก้าวสำคัญ", 0.5),
    ("สำนวนแปลตรง", r"ในบริบทของ|ภูมิทัศน์|ทำให้มั่นใจว่า|ในแง่ของ|เป็นที่น่าสังเกตว่า|ทำการ(?:ศึกษา|วิเคราะห์|สำรวจ|ทดสอบ|พัฒนา)|ซึ่งกันและกัน|เพื่อที่จะ|หนึ่งใน[^\s]{0,20}ที่สำคัญที่สุด|ให้ความสำคัญกับ|มีส่วนร่วมในการ|ในส่วนของ", 2.0),
    ("อ้างอำนาจลอย ๆ", r"นักวิชาการหลายท่าน|นักวิชาการจำนวนมาก|งานวิจัยจำนวนมาก|หลายการศึกษา|เป็นที่ยอมรับกันโดยทั่วไป|เป็นที่ทราบกันดี|หลายฝ่ายเห็นว่า|ผู้เชี่ยวชาญหลายคน", 0.3),
    ("hedging ซ้อน", r"อาจจะมีแนวโน้ม|อาจจะสามารถ|น่าจะอาจ|อาจจะน่าจะ|มีแนวโน้มที่จะอาจ|อาจมีความเป็นไปได้", 0.3),
    ("'มีความ' + คุณศัพท์", r"มีความ(?:สำคัญ|จำเป็น|ซับซ้อน|แตกต่าง|เหมาะสม|ชัดเจน|หลากหลาย|ยืดหยุ่น|โปร่งใส|น่าเชื่อถือ)", 2.0),
    ("'สามารถ...ได้' ถี่", r"(?<!ความ)(?<!ขีดความ)สามารถ", 6.0),
    ("'ส่งผลกระทบ' ไม่บอกทิศทาง", r"ส่งผลกระทบต่อ", 1.5),
    ("'ถือเป็น/ถือได้ว่า'", r"ถือเป็น|ถือได้ว่า|ถือว่าเป็น", 1.5),
]

CHAIN_WHICH = re.compile(r"ซึ่ง[^\s]{0,80}ซึ่ง")                      # two ซึ่ง inside one clause
PASSIVE = re.compile(r"ถูก(?!ต้อง|หัก|กฎหมาย|ใจ|ลง|กว่า|สุขลักษณะ|จริต|โฉลก|คอ|ชะตา|ระเบียบ)")
NOMINAL = re.compile(r"การ[^\s]{1,14}(?:ใน|ของ|เพื่อ)?การ[^\s]{1,14}การ")  # การ...การ...การ
NOMINAL2 = re.compile(r"การดำเนินการ(?:ใน|เพื่อ)การ|การจัดทำการ|ความ[^\s]{1,10}ความ[^\s]{1,10}ความ")
OF_CHAIN = re.compile(r"ของ[^\s]{1,25}ของ[^\s]{1,25}ของ")
DASH = re.compile(r"[—–]")
BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+", re.M)
BOLD = re.compile(r"\*\*[^*]+\*\*")
SIGNIF = re.compile(r"มีนัยสำคัญ")
STAT_CTX = re.compile(r"ทางสถิติ|p\s*[<=>]|ที่ระดับ|\.0[0-9]+|α|นัยสำคัญทางสถิติ")
STANCE = re.compile(r"ผู้เขียน(?:เห็นว่า|มีความเห็นว่า|ตั้งข้อสังเกต|เสนอ|อนุมาน|สันนิษฐาน|เห็นต่าง)|ในมุมมองของผู้เขียน|ในทัศนะของผู้เขียน")
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("draft")
    ap.add_argument("--top", type=int, default=5, help="examples to show per finding")
    ap.add_argument("--json")
    ap.add_argument("--strict", action="store_true")
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
    for label, rx, limit in PHRASES:
        r = re.compile(rx)
        ex = [(ln, ctx(p, m)) for ln, _, p in cleaned for m in r.finditer(p)]
        add("WARN" if len(ex) * per > limit else "INFO", label, len(ex), ex, limit)

    # 3. structural tells
    for label, r, limit in [("'ซึ่ง' ซ้อนกันในประโยคเดียว", CHAIN_WHICH, 1.0),
                            ("กรรมวาจก 'ถูก' (ไม่นับ ถูกต้อง/ถูกหัก/ถูกกฎหมาย)", PASSIVE, 4.5),
                            ("'การ/ความ' ซ้อนสามชั้น", NOMINAL, 1.2),
                            ("'การดำเนินการในการ' / 'ความ...ความ...ความ'", NOMINAL2, 0.3),
                            ("'ของ' ซ้อนสามชั้น", OF_CHAIN, 0.8),
                            ("ขีด em/en dash ในเนื้อหา", DASH, 0.0)]:
        ex = [(ln, ctx(p, m)) for ln, _, p in cleaned for m in r.finditer(p)]
        add("WARN" if len(ex) * per > limit else "INFO", label, len(ex), ex, limit)

    ex = [(ln, p[:50]) for ln, _, p in cleaned if BULLET.match(p) or BOLD.search(p)]
    add("WARN" if ex else "INFO", "บูลเล็ต/ตัวหนาในย่อหน้าร้อยแก้ว", len(ex), ex)

    # 4. significance without statistics
    ex = []
    for ln, _, p in cleaned:
        for m in SIGNIF.finditer(p):
            window = p[max(0, m.start() - 60): m.end() + 60]
            if not STAT_CTX.search(window):
                ex.append((ln, ctx(p, m)))
    add("WARN" if ex else "INFO", "'มีนัยสำคัญ' โดยไม่มีบริบทสถิติใกล้เคียง", len(ex), ex)

    # 5. author stance
    stance = [(ln, ctx(p, m)) for ln, _, p in cleaned for m in STANCE.finditer(p)]
    add("WARN" if not stance else "INFO", "จุดยืนผู้เขียน (ผู้เขียนเห็นว่า ...)", len(stance), stance[:2],
        None, "" if stance else "ไม่พบเลย บทความวิชาการควรมี")

    # 6. paragraphs without citation
    nocite = [(ln, f"[{sec}] " + p[:45]) for ln, sec, p in cleaned
              if len(p) > 450 and not CITE.search(p) and not re.search(r"บทคัดย่อ|สรุป|Abstract", sec)]
    add("INFO", "ย่อหน้ายาว (>450 อักขระ) ที่ไม่มีการอ้างอิง", len(nocite), nocite)

    # 7. cliché opening in introduction
    intro = [(ln, sec, p) for ln, sec, p in cleaned if "บทนำ" in sec][:2]
    ex = [(ln, ctx(p, m)) for ln, _, p in intro for m in CLICHE_OPEN.finditer(p)]
    add("WARN" if ex else "INFO", "เปิดบทนำแบบสำเร็จรูป", len(ex), ex)

    # 8. sentence-length uniformity
    sents, smode = sentences(body)
    if sents and len(sents) >= 10:
        lens = [len(s) for s in sents]
        cv = statistics.pstdev(lens) / statistics.mean(lens)
        longest = sorted(((len(s), s[:60]) for s in sents), reverse=True)[:3]
        add("WARN" if cv < 0.35 else "INFO", f"ความยาวประโยค ({smode})", len(sents), [(0, f"{l} อักขระ: {s}") for l, s in longest], None,
            f"เฉลี่ย {statistics.mean(lens):.0f} อักขระ, CV {cv:.2f} (ต่ำกว่า 0.35 = ยาวเท่ากันผิดปกติ)")
    else:
        add("INFO", "ความยาวประโยค", 0, None, None, "ข้าม (ต้องมี pythainlp)")

    warns = sum(1 for f in findings if f["level"] == "WARN")
    print(f"ตรวจ {len(cleaned)} ย่อหน้า ประมาณ {words:,} คำ ({wmode}); ข้าม [ตัวบท] {verbatim_blocks} ช่วง\n")
    print("\n".join(report))
    print(f"\nสรุป: WARN {warns} รายการ ตัวเลขเป็นเพียงสัญญาณ ให้อ่านประโยคจริงก่อนแก้ และห้ามแก้ข้อความใน [ตัวบท] หรือข้อความยกตรง")
    if a.json:
        json.dump({"words": words, "paragraphs": len(cleaned), "findings": findings}, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    sys.exit(1 if a.strict and warns else 0)


if __name__ == "__main__":
    main()
