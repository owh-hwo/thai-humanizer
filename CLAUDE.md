# thai-humanizer (สกิลสาธารณะ)

โฟลเดอร์นี้คือ repo ของสกิล `thai-humanizer` (https://github.com/owh-hwo/thai-humanizer) สำหรับปรับข้อความไทย/อังกฤษไม่ให้ดูเป็น AI หรือสำนวนแปล ทุกอย่างในนี้เผยแพร่สาธารณะ

## โครงสร้าง

- `skills/thai-humanizer/SKILL.md`: ทางเข้า เลือกเส้นทางตามภาษา (ไทย → references ไทย + สคริปต์; อังกฤษ → `humanizer-en.md`)
- `skills/thai-humanizer/references/thai-prose-patterns.md`: "ให้เขียนอย่างไร" แม่แบบย่อหน้า คลังคำเชื่อม ตาราง calque ใช้ตอนร่าง
- `skills/thai-humanizer/references/thai-humanizer.md`: "อย่าเขียนอย่างไร" ร่องรอย AI และสำนวนแปล ข้อควรระวังตอนแก้ ใช้หลังร่าง
- `skills/thai-humanizer/references/humanizer-en.md`: Humanizer ภาษาอังกฤษของ Siqi Chen (blader/humanizer) คัดลอกมาทั้งไฟล์ตามเวอร์ชันที่ระบุในหัวไฟล์ **ห้ามแก้เนื้อหาในนี้** อัปเดตด้วยการคัดลอก SKILL.md รุ่นใหม่จากต้นทาง ตัด frontmatter แล้วใส่หัว comment เดิม
- `skills/thai-humanizer/scripts/thai_style_check.py`: นับร่องรอยต่อ 1,000 คำ ข้าม `[ตัวบท]` และข้อความในเครื่องหมายคำพูด
- `skills/thai-humanizer/LICENSE-humanizer`: MIT ของ Humanizer ต้นทาง ต้องคงไว้คู่กับ `humanizer-en.md`
- `.claude-plugin/`: plugin.json + marketplace.json ติดตั้งด้วย `/plugin marketplace add owh-hwo/thai-humanizer`
- `tests/`: ไฟล์ตัวอย่างสำหรับทดสอบสคริปต์ (`ai_sample.md` ควรได้ WARN หลายรายการ, `human_sample.md` ควรเกือบไม่มี WARN)

## กติกาเมื่อแก้

1. **ข้อมูลเฉพาะห้ามเข้า repo**: ชื่อบทความ ชื่อวารสาร ชื่อผู้วิจัยที่อ้างในงานจริง เลขกฎหมาย path ส่วนตัว อีเมล ตัวอย่างในไฟล์ต้องแต่งขึ้นหรือทำให้ทั่วไป ก่อนคอมมิตให้ grep หาคำเหล่านี้
2. **ตัวอย่างสำนวนที่แนะนำต้องไม่ซ้ำกับร่องรอยที่ห้าม** เคยเกิด: ตารางแนะนำ "ธุรกิจเห็นผลชัดเจน" ซึ่งทิ้งสิ่งที่งานวัด เวลาเพิ่มแถวในตาราง ให้เช็กว่าคำแนะนำไม่ละเมิดข้อควรระวังด้านล่างตาราง
3. **เกณฑ์เตือนในสคริปต์ปรับจากร้อยแก้วคนไทยจริง** ถ้าจะเปลี่ยน threshold ให้รันกับ `tests/human_sample.md` ก่อน ร้อยแก้วที่คนเขียนเองต้องไม่ได้ WARN เกิน 1-2 รายการ (เช่น "ถูก" ในบทความตีพิมพ์จริงอยู่ราว 4/1,000 คำ)
4. **สคริปต์ต้องรันได้โดยไม่มี pythainlp** และบน Windows (ตั้ง stdout เป็น utf-8 แล้ว อย่าพิมพ์อักขระนอก BMP ไทย/ละติน)
5. แก้แล้วรัน `python -I skills/thai-humanizer/scripts/thai_style_check.py tests/ai_sample.md` และ `tests/human_sample.md` เทียบผล แล้วรัน `claude plugin validate .`
6. บทเรียนที่ได้จากการใช้สกิลกับงานจริง ให้เขียนเป็นข้อทั่วไปลง `thai-humanizer.md` (ข้อควรระวัง) หรือ `thai-prose-patterns.md` (แม่แบบ/คำ) ไม่ใส่ประวัติการแก้บทความใด
7. เพิ่ม version ใน `SKILL.md` frontmatter และ `.claude-plugin/*.json` เมื่อเปลี่ยนพฤติกรรม แล้ว commit และ push ที่ `main`
8. เครื่องนี้ติดตั้งสกิลไว้ที่ `~/.claude/skills/thai-humanizer/` (สำเนา) แก้ใน repo แล้วคัดลอกทับ: `cp -r skills/thai-humanizer ~/.claude/skills/` เครื่องอื่นใช้ `/plugin marketplace update thai-humanizer`

## ความสัมพันธ์กับสกิลอื่น

- `research-article` (https://github.com/owh-hwo/research-article) เรียกสกิลนี้ในขั้นร่าง ขั้นปรับภาษา และขั้นตรวจก่อนส่ง เดิมไฟล์ไทยทั้งสามอยู่ในสกิลนั้น ย้ายมาที่นี่ 27 ต.ค. 2569 สกิลนั้นไม่เก็บสำเนาแล้ว
- `humanizer` ต้นทาง (blader/humanizer) ถ้าผู้ใช้ติดตั้งไว้ด้วย ทั้งสองทำงานกับภาษาอังกฤษได้เหมือนกัน สกิลนี้แค่รวมไว้ให้ติดตั้งครั้งเดียว
