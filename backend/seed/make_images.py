"""Render the fictional sample card and lab-result images into seed/assets/.

Run: uv run python -m seed.make_images
Everything is made up: no real agency logos, obviously fake numbers, SAMPLE watermarks on cards.
"""
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from seed import persona

ASSETS = Path(__file__).resolve().parent / "assets"
SAMPLE = "SAMPLE – HINDI TOTOO"
PATIENT = "DELA CRUZ, REMEDIOS S."

_SANS = ["/System/Library/Fonts/Supplemental/Arial.ttf", "/Library/Fonts/Arial.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
_BOLD = ["/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/Library/Fonts/Arial Bold.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
_HAND = ["/System/Library/Fonts/Supplemental/Bradley Hand Bold.ttf", "/System/Library/Fonts/Supplemental/Chalkduster.ttf"]


def font(size: int, bold: bool = False, hand: bool = False) -> ImageFont.ImageFont:
    for path in (_HAND if hand else _BOLD if bold else _SANS):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def _center(d, box, text, f, fill):
    x0, y0, x1, y1 = box
    w = d.textlength(text, font=f)
    d.text(((x0 + x1 - w) / 2, y0), text, font=f, fill=fill)


# ---------------------------------------------------------------- cards

def _watermark(img: Image.Image, size: int = 64, alpha: int = 85) -> Image.Image:
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    f = font(size, bold=True)
    w = int(d.textlength(SAMPLE, font=f))
    txt = Image.new("RGBA", (w + 20, size + 30), (0, 0, 0, 0))
    ImageDraw.Draw(txt).text((10, 5), SAMPLE, font=f, fill=(200, 20, 20, alpha))
    txt = txt.rotate(28, expand=True, resample=Image.BICUBIC)
    layer.paste(txt, ((img.width - txt.width) // 2, (img.height - txt.height) // 2), txt)
    return Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")


def _card_base(color, title, subtitle):
    img = Image.new("RGB", (1011, 638), (250, 250, 246))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, 1010, 637), radius=36, outline=(150, 150, 150), width=4)
    d.rectangle((6, 6, 1004, 130), fill=color)
    d.ellipse((34, 24, 112, 102), fill=(255, 255, 255))  # generic emblem, not any real logo
    d.polygon([(73, 34), (100, 78), (46, 78)], fill=color)
    d.text((136, 26), title, font=font(40, bold=True), fill=(255, 255, 255))
    d.text((136, 78), subtitle, font=font(26), fill=(235, 235, 235))
    return img, d


def _front(stem, color, title, subtitle, lines, number):
    img, d = _card_base(color, title, subtitle)
    y = 170
    for k, v in lines:
        d.text((50, y), k, font=font(22), fill=(110, 110, 110))
        d.text((50, y + 26), v, font=font(34, bold=True), fill=(20, 20, 20))
        y += 82
    d.text((50, 570), number, font=font(40, bold=True), fill=(20, 20, 20))
    d.rounded_rectangle((760, 170, 960, 410), radius=14, outline=(150, 150, 150), width=3, fill=(228, 232, 236))
    d.ellipse((822, 200, 898, 276), fill=(180, 186, 192))
    d.pieslice((790, 290, 930, 430), 180, 360, fill=(180, 186, 192))
    return _watermark(img)


def _back(stem, color, lines):
    img = Image.new("RGB", (1011, 638), (250, 250, 246))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, 1010, 637), radius=36, outline=(150, 150, 150), width=4)
    d.rectangle((6, 50, 1004, 130), fill=(40, 40, 40))
    y = 190
    for line in lines:
        d.text((50, y), line, font=font(28), fill=(40, 40, 40))
        y += 48
    d.rectangle((50, 520, 560, 580), outline=(120, 120, 120), width=2)
    d.text((60, 534), "Signature:  (SAMPLE)", font=font(24), fill=(120, 120, 120))
    d.text((620, 540), "This is a SAMPLE card for demo only.", font=font(20), fill=(120, 120, 120))
    return _watermark(img)


def make_cards():
    name = "REMEDIOS S. DELA CRUZ"
    specs = {
        "philhealth": ((30, 120, 70), "HEALTH INSURANCE", "Member card (sample design)",
                       [("MEMBER NAME", name), ("DATE OF BIRTH", "1953-04-12"), ("CATEGORY", "Senior / Lifetime member")],
                       "00-000000000-0",
                       ["Show this card on admission or consultation.", "Keep your member data record updated.",
                        "Number shown is a dummy: 00-000000000-0", "Fictional card for the Kapiling demo."]),
        "senior": ((30, 80, 160), "SENIOR CITIZEN ID", "City government (sample design)",
                   [("NAME", name), ("DATE OF BIRTH", "1953-04-12"), ("ADDRESS", "Marikina City")],
                   "ID No. 0000-SAMPLE",
                   ["Entitled to the privileges for senior citizens.", "Valid only with a government-issued ID.",
                    "Number shown is a dummy: 0000-SAMPLE", "Fictional card for the Kapiling demo."]),
        "hmo": ((150, 60, 120), "CAREFIRST HEALTH", "HMO membership (fictional company)",
                [("MEMBER", name), ("PLAN", "Silver Plus"), ("VALID UNTIL", "12/2027")],
                "HMO-000-000-000",
                ["Present this card at accredited hospitals.", "Emergency hotline: 02-8000-0000 (dummy)",
                 "Number shown is a dummy: HMO-000-000-000", "Fictional company for the Kapiling demo."]),
    }
    for stem, (color, title, sub, lines, number, back) in specs.items():
        _front(stem, color, title, sub, lines, number).save(ASSETS / f"card_{stem}_front.png")
        _back(stem, color, back).save(ASSETS / f"card_{stem}_back.png")
    # vaccination card: a small table
    img, d = _card_base((190, 90, 40), "IMMUNIZATION RECORD", "Vaccination card (sample design)")
    d.text((50, 150), name, font=font(30, bold=True), fill=(20, 20, 20))
    rows = [("VACCINE", "DATE"), ("Influenza", "2025-04-10"), ("PCV13", "2023-06-02"), ("COVID-19 booster", "2023-01-15")]
    y = 215
    for i, (a, b) in enumerate(rows):
        f = font(30, bold=(i == 0))
        d.line((50, y + 50, 960, y + 50), fill=(170, 170, 170), width=2)
        d.text((60, y + 6), a, font=f, fill=(20, 20, 20))
        d.text((620, y + 6), b, font=f, fill=(20, 20, 20))
        y += 62
    d.text((50, 580), "Card No. 00000-SAMPLE", font=font(30, bold=True), fill=(20, 20, 20))
    _watermark(img).save(ASSETS / "card_vaccination_front.png")
    _back("vaccination", (190, 90, 40), [
        "Keep this card and bring it to every visit.", "Next influenza dose due: 2026-04",
        "Number shown is a dummy: 00000-SAMPLE", "Fictional card for the Kapiling demo."]).save(ASSETS / "card_vaccination_back.png")


# ---------------------------------------------------------------- avatars

def make_avatars():
    def avatar(path, bg, skin, hair, bun):
        img = Image.new("RGB", (512, 512), bg)
        d = ImageDraw.Draw(img)
        d.ellipse((90, 340, 422, 700), fill=(70, 110, 150))  # shoulders
        d.rectangle((226, 290, 286, 370), fill=skin)  # neck
        if bun:
            d.ellipse((196, 40, 316, 150), fill=hair)
        d.ellipse((136, 90, 376, 340), fill=skin)  # head
        d.pieslice((130, 80, 382, 300), 180, 360, fill=hair)  # hair top
        d.ellipse((200, 205, 228, 225), fill=(40, 30, 30))
        d.ellipse((284, 205, 312, 225), fill=(40, 30, 30))
        d.arc((206, 240, 306, 310), 20, 160, fill=(150, 60, 60), width=6)
        img.save(path)
    avatar(ASSETS / "avatar_lola.png", (214, 232, 226), (232, 190, 160), (190, 190, 190), True)
    avatar(ASSETS / "avatar_mika.png", (248, 226, 214), (236, 196, 166), (40, 30, 30), False)


# ---------------------------------------------------------------- paper "photos"

def _photograph(sheet: Image.Image, seed: int) -> Image.Image:
    """Put a sheet on a desk-coloured background: slight rotation, shadow, blur and noise."""
    rng = random.Random(seed)
    angle = rng.choice([-1, 1]) * rng.uniform(1.5, 3.0)
    pad = 150
    desk = Image.new("RGB", (sheet.width + 2 * pad + 160, sheet.height + 2 * pad), (139, 104, 72))
    dd = ImageDraw.Draw(desk)
    for y in range(0, desk.height, 6):  # wood grain
        shade = rng.randint(-9, 9)
        dd.line((0, y, desk.width, y), fill=(139 + shade, 104 + shade, 72 + shade), width=6)
    rot = sheet.convert("RGBA").rotate(angle, expand=True, resample=Image.BICUBIC)
    shadow = Image.new("RGBA", rot.size, (0, 0, 0, 0))
    shadow.putalpha(rot.getchannel("A").point(lambda a: 120 if a else 0))
    shadow = shadow.filter(ImageFilter.GaussianBlur(14))
    x, y = (desk.width - rot.width) // 2, (desk.height - rot.height) // 2
    desk.paste(shadow, (x + 14, y + 18), shadow)
    desk.paste(rot, (x, y), rot)
    desk = desk.filter(ImageFilter.GaussianBlur(0.7))
    # deterministic sensor noise (effect_noise is not seedable)
    noise = Image.frombytes("L", desk.size, rng.randbytes(desk.width * desk.height)).convert("RGB")
    return Image.blend(desk, noise, 0.06)


def _sheet(height):
    sheet = Image.new("RGB", (1500, height), (253, 252, 248))
    return sheet, ImageDraw.Draw(sheet)


def _header(d, facility, subtitle, title):
    d.text((70, 60), facility, font=font(52, bold=True), fill=(20, 40, 90))
    d.text((70, 128), subtitle, font=font(28), fill=(80, 80, 80))
    d.line((70, 175, 1430, 175), fill=(20, 40, 90), width=5)
    _center(d, (0, 205, 1500, 260), title, font(44, bold=True), (20, 20, 20))


def _patient_block(d, date, y=290, extra=None):
    f, fb = font(32), font(32, bold=True)
    rows = [("Patient:", PATIENT), ("Age / Sex:", "73 / F"), ("Date:", date), ("Requesting physician:", persona.DOCTOR)]
    if extra:
        rows.append(extra)
    for k, v in rows:
        d.text((70, y), k, font=f, fill=(70, 70, 70))
        d.text((440, y), v, font=fb, fill=(10, 10, 10))
        y += 50
    return y + 20


def _table(d, y, rows):
    cols = [70, 640, 920, 1130, 1430]
    f, fb = font(32), font(32, bold=True)
    d.rectangle((70, y, 1430, y + 60), fill=(222, 230, 242))
    for x, h in zip(cols, ["Test", "Result", "Unit", "Reference range"]):
        d.text((x + 12, y + 10), h, font=fb, fill=(10, 10, 10))
    y += 60
    for r in rows:
        for i, (x, cell) in enumerate(zip(cols, r)):
            d.text((x + 12, y + 12), str(cell), font=fb if i == 1 else f, fill=(10, 10, 10))
        y += 62
        d.line((70, y, 1430, y), fill=(190, 190, 190), width=2)
    d.rectangle((70, y - 62 * len(rows) - 60, 1430, y), outline=(90, 90, 90), width=3)
    for x in cols[1:-1]:
        d.line((x, y - 62 * len(rows) - 60, x, y), fill=(190, 190, 190), width=2)
    return y


def _signature(d, y, tech="Maria L. Bautista, RMT", doc="Dr. A. Villanueva, Pathologist"):
    d.text((70, y + 40), "SAMPLE document – fictional patient and facility.", font=font(24), fill=(120, 120, 120))
    for x, name in ((120, tech), (820, doc)):
        d.line((x, y + 190, x + 520, y + 190), fill=(20, 20, 20), width=3)
        d.text((x, y + 200), name, font=font(28), fill=(40, 40, 40))
    d.text((150, y + 120), "M. Bautista", font=font(46, hand=True), fill=(30, 30, 120))  # handwritten signature


def _lab(stem, title, date, rows, seed, extra=None):
    sheet, d = _sheet(1560)
    _header(d, persona.LAB_FACILITY, "123 Sample Street, Marikina City  |  Tel. 02-8000-0000 (dummy)", title)
    y = _patient_block(d, date, extra=extra)
    y = _table(d, y + 10, rows)
    _signature(d, y + 30)
    _photograph(sheet.crop((0, 0, 1500, min(sheet.height, y + 460))), seed).save(ASSETS / f"{stem}.jpg", quality=85)


def make_labs():
    c = {d: (f, s, dia) for d, f, s, dia in persona.CHECKUPS}
    fbs = c["2026-03-02"][0]
    hba = dict(persona.HBA1C)["2026-03-02"]
    L = persona.LIPID
    _lab("lab_fbs_hba1c", "CLINICAL CHEMISTRY", "2026-03-02", [
        ("Fasting Blood Sugar", fbs, "mg/dL", "70 - 100"),
        ("Hemoglobin A1c (HbA1c)", hba, "%", "4.0 - 5.6"),
    ], 1)
    _lab("lab_lipid", "LIPID PROFILE", persona.LIPID_DATE, [
        ("Total Cholesterol", L["total_chol"], "mg/dL", "< 200"),
        ("LDL Cholesterol", L["ldl"], "mg/dL", "< 130"),
        ("HDL Cholesterol", L["hdl"], "mg/dL", "> 40"),
        ("Triglycerides", L["trig"], "mg/dL", "< 150"),
    ], 2)
    _lab("lab_cbc", "COMPLETE BLOOD COUNT", persona.CBC_DATE, [
        ("Hemoglobin", 12.8, "g/dL", "12.0 - 15.0"),
        ("Hematocrit", 38.5, "%", "36.0 - 46.0"),
        ("RBC count", 4.4, "x10^12/L", "4.0 - 5.2"),
        ("WBC count", 7.2, "x10^9/L", "4.5 - 11.0"),
        ("Platelet count", 265, "x10^9/L", "150 - 450"),
        ("Neutrophils", 62, "%", "50 - 70"),
        ("Lymphocytes", 31, "%", "20 - 40"),
    ], 3)
    _lab("lab_creatinine", "RENAL FUNCTION TEST", persona.CREATININE_DATE, [
        ("Creatinine", 0.9, "mg/dL", "0.6 - 1.1"),
        ("Blood Urea Nitrogen", 14, "mg/dL", "7 - 20"),
        ("eGFR", 72, "mL/min/1.73m2", ">= 60"),
        ("Uric Acid", 5.1, "mg/dL", "2.4 - 5.7"),
    ], 4)


def make_discharge():
    sheet, d = _sheet(1900)
    _header(d, "Marikina Riverside Hospital", "45 Sample Avenue, Marikina City  |  Medical Records Section", "DISCHARGE SUMMARY")
    y = _patient_block(d, "2019-08-18", extra=("Admitted:", "2019-08-14"))
    f, fb = font(32), font(32, bold=True)
    body = [
        ("Final diagnosis:", "Hypertensive urgency; Type 2 diabetes mellitus, uncontrolled"),
        ("Hospital course:", "Admitted for BP 190/110 with headache and dizziness. Given IV"),
        ("", "antihypertensives, BP stabilised to 140/90 within 48 hours. Blood sugar"),
        ("", "monitored; insulin sliding scale then oral agents. No complications."),
        ("Condition at discharge:", "Improved, ambulatory"),
        ("Discharge medicines:", "Losartan 50 mg once daily; Metformin 500 mg twice daily"),
        ("Allergies:", "Penicillin (rash)"),
        ("Follow-up:", "Internal Medicine clinic in 1 week; low-salt, diabetic diet"),
    ]
    for k, v in body:
        d.text((70, y), k, font=fb, fill=(50, 50, 50))
        d.text((470, y), v, font=f, fill=(10, 10, 10))
        y += 56
    _signature(d, y + 30, tech="Resident on duty", doc="Dr. J. Reyes, Internal Medicine")
    _photograph(sheet.crop((0, 0, 1500, y + 460)), 5).save(ASSETS / "discharge_2019.jpg", quality=85)


def make_prescription():
    sheet, d = _sheet(1500)
    d.text((70, 60), persona.CLINIC, font=font(50, bold=True), fill=(20, 40, 90))
    d.text((70, 124), f"{persona.DOCTOR}  |  Internal Medicine  |  Lic. No. 0000000 (sample)", font=font(28), fill=(80, 80, 80))
    d.line((70, 172, 1430, 172), fill=(20, 40, 90), width=5)
    for y in range(330, 1300, 70):  # ruled lines
        d.line((70, y, 1430, y), fill=(205, 215, 235), width=2)
    ink = (25, 35, 120)
    h = font(54, hand=True)
    d.text((70, 200), "Name: Remedios S. Dela Cruz        Age: 73", font=h, fill=ink)
    d.text((70, 262), "Date: 2026-03-02", font=h, fill=ink)
    d.text((70, 340), "Rx", font=font(120, bold=True), fill=ink)
    lines = ["Losartan 50 mg tab", "  1 tab once a day (AM) #30", "Metformin 500 mg tab", "  1 tab twice a day (AM & PM) #60",
             "Amlodipine 5 mg tab", "  1 tab once a day (HS) #30", "Return in 3 months"]
    y = 480
    for ln in lines:
        d.text((140, y), ln, font=h, fill=ink)
        y += 70
    d.line((900, 1290, 1400, 1290), fill=(20, 20, 20), width=3)
    d.text((930, 1215), "J. Reyes", font=font(60, hand=True), fill=ink)
    d.text((930, 1300), persona.DOCTOR, font=font(26), fill=(60, 60, 60))
    d.text((70, 1380), "SAMPLE prescription – fictional patient and doctor.", font=font(24), fill=(120, 120, 120))
    _photograph(sheet, 6).save(ASSETS / "prescription.jpg", quality=85)


def make_intake_form():
    """A blank patient-information sheet (18 fields) for the fill-a-form demo. A clean scan, not a desk photo."""
    sheet, d = _sheet(2000)
    _header(d, persona.CLINIC, "Out-Patient Department  |  Tel. 02-8000-0000 (dummy)", "PATIENT INFORMATION SHEET")
    f, fb, small = font(30), font(30, bold=True), font(24)
    ink, line = (20, 20, 20), (90, 90, 90)

    def section(y, title):
        d.rectangle((70, y, 1430, y + 50), fill=(222, 230, 242))
        d.text((84, y + 9), title, font=fb, fill=ink)
        return y + 80

    def blank(x, y, label, end):
        d.text((x, y), label, font=f, fill=ink)
        lx = x + d.textlength(label, font=f) + 14
        d.line((lx, y + 36, end, y + 36), fill=line, width=2)

    def boxes(x, y, label, options):
        d.text((x, y), label, font=f, fill=ink)
        bx = x + d.textlength(label, font=f) + 24
        for o in options:
            d.rectangle((bx, y + 4, bx + 28, y + 32), outline=line, width=3)
            d.text((bx + 40, y), o, font=f, fill=ink)
            bx += 40 + d.textlength(o, font=f) + 40

    y = section(290, "I. PERSONAL INFORMATION")
    blank(70, y, "Last name:", 730); blank(760, y, "First name:", 1430); y += 80  # noqa: E702
    blank(70, y, "Middle name:", 730); blank(760, y, "Date of birth (YYYY-MM-DD):", 1430); y += 80  # noqa: E702
    blank(70, y, "Age:", 330); boxes(360, y, "Sex:", ["Male", "Female"]); y += 80  # noqa: E702
    boxes(70, y, "Civil status:", ["Single", "Married", "Widowed", "Separated"]); y += 80  # noqa: E702
    blank(70, y, "Home address:", 1430); y += 80  # noqa: E702
    blank(70, y, "Contact number:", 730); blank(760, y, "PhilHealth no.:", 1430); y += 80  # noqa: E702
    blank(70, y, "Blood type:", 730); y += 100  # noqa: E702

    y = section(y, "II. IN CASE OF EMERGENCY")
    blank(70, y, "Contact person:", 1430); y += 80  # noqa: E702
    blank(70, y, "Relationship:", 730); blank(760, y, "Mobile number:", 1430); y += 100  # noqa: E702

    y = section(y, "III. MEDICAL HISTORY")
    blank(70, y, "Known allergies:", 1430); y += 80  # noqa: E702
    blank(70, y, "Current medications:", 1430); y += 80  # noqa: E702
    boxes(70, y, "Hypertension?", ["Yes", "No"]); y += 80  # noqa: E702
    boxes(70, y, "Diabetes?", ["Yes", "No"]); y += 80  # noqa: E702
    boxes(70, y, "Do you smoke?", ["Yes", "No"]); y += 110  # noqa: E702

    d.text((70, y), "I certify that the information above is true and correct.", font=small, fill=(70, 70, 70))
    d.line((900, y + 120, 1430, y + 120), fill=line, width=2)
    d.text((960, y + 130), "Signature over printed name", font=small, fill=(70, 70, 70))
    d.rectangle((70, y + 60, 700, y + 170), outline=(150, 150, 150), width=2)
    d.text((84, y + 70), "FOR CLINIC USE ONLY", font=small, fill=(120, 120, 120))
    d.text((84, y + 105), "Patient no.: ________   Seen by: ________", font=small, fill=(120, 120, 120))
    d.text((70, y + 210), "SAMPLE form – fictional clinic, for the Kapiling demo.", font=small, fill=(120, 120, 120))
    sheet.crop((0, 0, 1500, y + 270)).save(ASSETS / "intake_form.png")


def main():
    ASSETS.mkdir(parents=True, exist_ok=True)
    make_cards()
    make_avatars()
    make_labs()
    make_discharge()
    make_prescription()
    make_intake_form()
    print(f"wrote {len(list(ASSETS.glob('*.png'))) + len(list(ASSETS.glob('*.jpg')))} images to {ASSETS}")


if __name__ == "__main__":
    main()
