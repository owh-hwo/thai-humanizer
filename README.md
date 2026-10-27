# thai-humanizer

สกิลสำหรับ [Claude Code](https://claude.com/claude-code) ปรับข้อความภาษาไทย (และภาษาอังกฤษ) ที่อ่านแล้วดูเป็น AI หรือเป็นสำนวนแปลจากอังกฤษ ให้อ่านเหมือนคนเขียนเอง โดยไม่เปลี่ยนสิ่งที่ข้อความพูด

A Claude Code skill that rewrites AI-sounding or translated-sounding Thai so it reads like a Thai writer wrote it, without changing what it says. English text is handled by the bundled [Humanizer](https://github.com/blader/humanizer) (v3.1, MIT).

## ทำอะไร

- **ภาษาไทย**
  - ตอนร่าง: แม่แบบย่อหน้าภาษาไทยวิชาการ 10 แบบ คลังคำเชื่อม/กริยาที่ใช้จริง และตารางสำนวนแปลตรงจากอังกฤษ 20+ รายการ (`thai-prose-patterns.md`)
  - ตอนเกลา: รายการร่องรอยภาษา AI (เปิดเรื่องสำเร็จรูป ไตรภาคบังคับ คำขยายเกินจริง คำเชื่อมซ้ำ ประโยคปิดสวย ๆ) และสำนวนแปล (ประธานนามธรรม กรรมวาจก "ซึ่ง" ซ้อน nominalization) พร้อมข้อควรระวังไม่ให้การแก้สำนวนเปลี่ยนความหมาย (`thai-humanizer.md`)
  - สคริปต์ `thai_style_check.py` นับร่องรอยต่อ 1,000 คำ ชี้บรรทัด เกณฑ์เตือนปรับจากบทความตีพิมพ์จริง ข้ามข้อความใน `[ตัวบท]...[/ตัวบท]` และในเครื่องหมายคำพูด
  - ขั้น "ผู้ตรวจที่ไม่เห็นภาษาอังกฤษ" สำหรับงานที่อ้างแหล่งต่างประเทศมาก
- **ภาษาอังกฤษ**: Humanizer 26 patterns จาก Wikipedia "Signs of AI writing" รวมไว้ตามต้นฉบับ

สิ่งที่สกิลไม่ทำ: ไม่เพิ่มข้อเท็จจริง ไม่เปลี่ยนตัวเลข การอ้างอิง หรือระดับความมั่นใจ ไม่แตะข้อความกฎหมายหรือคำพูดที่ยกมา และไม่ได้มีเป้าหมายหลบเครื่องตรวจ AI

## ติดตั้ง

### plugin (แนะนำ)

```
/plugin marketplace add owh-hwo/thai-humanizer
/plugin install thai-humanizer@thai-humanizer
```

อัปเดตด้วย `/plugin marketplace update thai-humanizer`

### คัดลอกเป็น personal skill

```bash
git clone https://github.com/owh-hwo/thai-humanizer.git
cp -r thai-humanizer/skills/thai-humanizer ~/.claude/skills/
```

Windows (PowerShell): `Copy-Item -Recurse thai-humanizer\skills\thai-humanizer "$HOME\.claude\skills\"`

สคริปต์ใช้ Python 3.9+ ไม่ต้องติดตั้งไลบรารี ถ้ามี `pythainlp` (`pip install pythainlp`) จะนับคำและความยาวประโยคแม่นขึ้น

## ใช้งาน

พิมพ์ได้เลย เช่น "ช่วยเกลาสำนวนย่อหน้านี้ให้ไม่ดูเป็น AI" "ข้อความนี้อ่านเหมือนแปลจากอังกฤษ ช่วยปรับ" "humanize this paragraph" หรือเรียก `/thai-humanizer` (ติดตั้งแบบ plugin: `/thai-humanizer:thai-humanizer`)

รันสคริปต์ตรงก็ได้:

```bash
python -I skills/thai-humanizer/scripts/thai_style_check.py draft.md --top 5
python -I skills/thai-humanizer/scripts/thai_style_check.py draft.md --strict   # exit 1 เมื่อมี WARN
```

ตัวอย่างผลจาก `tests/ai_sample.md` (ข้อความที่ตั้งใจเขียนให้เป็น AI) ได้ WARN 19 รายการ ส่วน `tests/human_sample.md` ได้ 0

```
WARN   ย่อหน้าที่เปิดด้วยคำเชื่อมสำเร็จรูป: 3 ครั้ง = 13.8/1,000 คำ [นอกจากนี้ 2, ดังนั้น 1] จาก 4 ย่อหน้า
         บ.5: …นอกจากนี้ ประโยชน์ของระบบดิจิทัลน่าจะขึ้นกับ…
WARN   กรรมวาจก 'ถูก' (ไม่นับ ถูกต้อง/ถูกหัก/ถูกกฎหมาย): 5 ครั้ง = 22.9/1,000 คำ (เกณฑ์ ≤ 4.5/1,000 คำ)
WARN   จุดยืนผู้เขียน (ผู้เขียนเห็นว่า ...): 0 ครั้ง ไม่พบเลย บทความวิชาการควรมี
```

## ใช้ร่วมกับ

- [research-article](https://github.com/owh-hwo/research-article) สกิลเขียนบทความวิชาการไทยส่งวารสาร TCI เรียกสกิลนี้ตอนร่างและตอนตรวจก่อนส่ง

## โครงสร้าง

```
.claude-plugin/                 plugin.json, marketplace.json
skills/thai-humanizer/
  SKILL.md                      ทางเข้า เลือกเส้นทางตามภาษา
  references/thai-prose-patterns.md   ให้เขียนอย่างไร (ตอนร่าง)
  references/thai-humanizer.md        อย่าเขียนอย่างไร (ตอนเกลา)
  references/humanizer-en.md          Humanizer ภาษาอังกฤษ (ต้นฉบับ)
  scripts/thai_style_check.py
  LICENSE-humanizer
tests/                          ตัวอย่างสำหรับทดสอบสคริปต์
```

## License

ส่วนภาษาไทย: MIT (owh-hwo) ส่วน `humanizer-en.md`: MIT, Copyright (c) 2025 Siqi Chen, ดู `skills/thai-humanizer/LICENSE-humanizer`
