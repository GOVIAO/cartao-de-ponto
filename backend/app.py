from __future__ import annotations

import csv
import io
import json
import os
import re
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent
MAX_UPLOAD = int(os.getenv("MAX_UPLOAD_MB", "15")) * 1024 * 1024
MAX_OCR_PAGES = int(os.getenv("MAX_OCR_PAGES", "40"))

app = FastAPI(title="Cartão de Ponto - Quick Filler")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

DB: dict[str, dict[str, Any]] = {}
DATE_RE = re.compile(r"(?<!\d)(\d{2}/\d{2}/\d{4})(?!\d)")
TIME_RE = re.compile(r"(?<!\d)(\+?\d{1,2}:\d{2})(?:[a-zA-Z])?(?!\d)")
MONEY_RE = re.compile(r"(?<![\w])[-+]?\d{1,3}(?:\.\d{3})*,\d{2}(?!\w)")
CODE_RE = re.compile(r"^\s*(/?\d{3,4})\b\s*(.*)$")

class UpdateBody(BaseModel):
    value: dict[str, Any]


def normalize_time(raw: str) -> str:
    token = raw.strip().lstrip("+")
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", token)
    if not m:
        return token
    hh, mm = int(m.group(1)), int(m.group(2))
    if 0 <= hh <= 23 and 0 <= mm <= 59:
        return f"{hh:02d}:{mm:02d}"
    return "?"


def valid_date(s: str) -> bool:
    try:
        datetime.strptime(s, "%d/%m/%Y")
        return True
    except ValueError:
        return False


def extract_pdf_pages(data: bytes) -> list[str]:
    """Extract text per PDF page; OCR only pages without usable text."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        pages = [(page.extract_text() or "").strip() for page in reader.pages]
    except Exception as exc:
        raise RuntimeError("Não foi possível abrir o PDF") from exc

    suspicious = [i for i, text in enumerate(pages) if ("ValorNomeVerba" in text or "Declaração Remuneração" in text and "Verba Nome" not in text)]
    if suspicious:
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(data)) as pdf:
                for i in suspicious:
                    pages[i] = (pdf.pages[i].extract_text() or "").strip()
        except Exception:
            pass

    missing = [i for i, text in enumerate(pages) if not text]
    if not missing:
        return pages
    try:
        import pytesseract
        from pdf2image import convert_from_bytes
        for page_index in missing[:MAX_OCR_PAGES]:
            images = convert_from_bytes(data, dpi=180, first_page=page_index + 1, last_page=page_index + 1)
            if images:
                pages[page_index] = pytesseract.image_to_string(images[0], lang="por+eng").strip()
    except Exception:
        pass
    return pages


def parse_timecard_page(text: str, page_no: int) -> dict[str, Any]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    jornada_layout = any(re.search(r"Dia\s+Semana\s+Jornada\s+Entrada", line, re.I) for line in lines)
    competence = re.search(r"Mes/Ano\s*:\s*(\d{1,2})\s*/\s*(\d{4})", text, flags=re.I)
    comp_month = int(competence.group(1)) if competence else None
    comp_year = int(competence.group(2)) if competence else None
    days: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    data_started = False
    for line in lines:
        if re.search(r"Dia\s+Semana\s+Jornada\s+Entrada|^Data\b.*\bEnt\w*\b.*\bSai", line, re.I):
            data_started = True
            continue
        if not data_started:
            continue
        date_match = re.match(r"^(\d{2}/\d{2}/\d{4})\b", line)
        day_match = re.match(r"^(\d{1,2})\s*-\s*[A-Za-zÀ-ÿ]{3}\b", line)
        if date_match:
            raw_date = date_match.group(1)
            current = {"date_raw": raw_date, "punches": []}
            days.append(current)
            after = line[date_match.end():]
            tokens = list(TIME_RE.finditer(after))
            limit = 4
            for token in tokens[:limit]:
                raw = token.group(1)
                current["punches"].append({"kind": "IN" if len(current["punches"]) % 2 == 0 else "OUT", "time_raw": raw, "time_hhmm": normalize_time(raw)})
            continue
        if day_match and jornada_layout:
            day_number = int(day_match.group(1))
            raw_date = f"{day_number:02d}/{comp_month:02d}/{comp_year:04d}" if comp_month and comp_year and 1 <= day_number <= 31 else "??/??/????"
            current = {"date_raw": raw_date, "punches": []}
            days.append(current)
            after = line[day_match.end():]
            tokens = list(TIME_RE.finditer(after))
            if tokens and normalize_time(tokens[0].group(1)) == "08:00":
                tokens = tokens[1:]
            for token in tokens[:2]:
                raw = token.group(1)
                current["punches"].append({"kind": "IN" if len(current["punches"]) % 2 == 0 else "OUT", "time_raw": raw, "time_hhmm": normalize_time(raw)})
            continue
        if current is None:
            continue
        if jornada_layout and re.match(r"^\+?\d{1,2}:\d{2}", line):
            tokens = list(TIME_RE.finditer(line))
            for token in tokens[: max(0, 4 - len(current["punches"]))]:
                raw = token.group(1)
                current["punches"].append({"kind": "IN" if len(current["punches"]) % 2 == 0 else "OUT", "time_raw": raw, "time_hhmm": normalize_time(raw)})
    return {"page": page_no, "days": days}


def _summary_values(line: str, label_patterns: list[tuple[str, str]]) -> list[dict[str, str]]:
    found: list[tuple[int, str, str]] = []
    for pattern, canonical in label_patterns:
        for m in re.finditer(pattern, line, flags=re.IGNORECASE):
            found.append((m.start(), m.end(), canonical))
    found.sort()
    out = []
    for idx, (_, end, canonical) in enumerate(found):
        segment_end = found[idx + 1][0] if idx + 1 < len(found) else len(line)
        nums = MONEY_RE.findall(line[end:segment_end])
        out.append({"label": canonical, "value": nums[0] if nums else ""})
    return out


def parse_payroll_page(text: str, page_no: int) -> dict[str, Any]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    competence = re.search(r"(?:Mês/Ano|Período)\s*:\s*(\d{1,2})/(\d{4})", text, flags=re.I)
    month = f"{int(competence.group(1)):02d}" if competence and 1 <= int(competence.group(1)) <= 12 else ""
    year = competence.group(2) if competence else ""
    fields: list[dict[str, str]] = []
    in_verbas = False
    for line in lines:
        if re.search(r"(?:\bVerba\s+Nome\b|\bCod\.\s+Descri)", line, flags=re.I):
            in_verbas = True
            continue
        if re.search(r"(?:Mês/Ano|Período)\s*:", line, flags=re.I):
            in_verbas = False
        if re.match(r"^(?:Remuneração|Adiantamento|Provisão|Margem|Consignação|Proventos|Total|L[ií]qüido|Base|Dep\.|Assinado|Impresso|Fls\.)", line, flags=re.I):
            in_verbas = False
        if not in_verbas:
            continue
        m = CODE_RE.match(line)
        if not m:
            continue
        code, rest = m.groups()
        nums = MONEY_RE.findall(rest)
        if not nums:
            continue
        value = nums[-1]
        reference = nums[-2] if len(nums) >= 2 else ""
        label = rest
        for n in nums:
            label = label.replace(n, "", 1)
        label = label.strip()
        fields.append({"code": code, "label": label, "reference": reference, "value": value})

    bases: list[dict[str, str]] = []
    canonical_patterns = [
        (r"Total\s+Vencimentos?\s*[:\-]?", "Total Vencimentos"),
        (r"Total\s+Descontos?\s*[:\-]?", "Total Descontos"),
        (r"L[ií]qüido\s*[:\-]?", "Valor Líquido"),
        (r"Proventos\s+L[ií]quidos\s*[:\-]?", "Valor Líquido"),
        (r"Proventos\s+Bruto\s*[:\-]?", "Total Vencimentos"),
        (r"Base\s+I\.?N\.?S\.?S\.?\s*[:\-]?", "Base INSS"),
        (r"F\.?G\.?T\.?S\.?\s+do\s+Mês\s*[:\-]?", "FGTS"),
        (r"Provisão\s+FGTS\s*[:\-]?", "FGTS"),
        (r"Base\s+I\.R\.R\.F\.\s+13o\.?\s*[:\-]?", "Base IR 13o."),
        (r"Base\s+I\.R\.R\.F\.(?!\s*13o)\s*", "Base IR"),
        (r"Base\s+FGTS\s*[:\-]?", "Base FGTS"),
    ]
    bases_started = True
    for line in lines:
        if re.search(r"Folha de Pagamento:\s*ACERTO", line, flags=re.I):
            bases_started = False
        if not bases_started:
            continue
        if any(re.search(pattern, line, flags=re.I) for pattern, _ in canonical_patterns):
            bases.extend(_summary_values(line, canonical_patterns))
        if re.match(r"^Total\s+", line, flags=re.I):
            nums = MONEY_RE.findall(line)
            if nums:
                bases.append({"label": "Total Vencimentos", "value": nums[0]})
                if len(nums) > 1: bases.append({"label": "Total Descontos", "value": nums[1]})
        if re.match(r"^L[ií]qüido\b", line, flags=re.I):
            nums = MONEY_RE.findall(line)
            if nums: bases.append({"label": "Valor Líquido", "value": nums[0]})
    seen = set(); clean_bases = []
    for item in bases:
        key = (item["label"], item["value"])
        if key not in seen:
            seen.add(key); clean_bases.append(item)
    return {"page": page_no, "year": year, "month": month, "fields": fields, "bases": clean_bases}


def parse_document(pages: list[str], tipo: str) -> dict[str, Any]:
    if tipo == "cartao-ponto": return {"pages": [parse_timecard_page(text, i) for i, text in enumerate(pages, 1)]}
    return {"pages": [parse_payroll_page(text, i) for i, text in enumerate(pages, 1)]}


def row_warnings(value: dict[str, Any], tipo: str) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    if tipo == "cartao-ponto":
        previous: date | None = None
        for page in value.get("pages", []):
            for day in page.get("days", []):
                msgs = []
                if len(day.get("punches", [])) % 2 == 1: msgs.append("Batidas ímpares: falta uma entrada ou saída")
                if "?" in json.dumps(day, ensure_ascii=False): msgs.append("Há caractere não lido com segurança (?)")
                try:
                    current = datetime.strptime(day.get("date_raw", ""), "%d/%m/%Y").date()
                    if previous and (current - previous).days != 1: msgs.append("Data não sequencial")
                    previous = current
                except ValueError: msgs.append("Data inválida ou ilegível")
                warnings.append({"messages": msgs})
    else:
        previous: tuple[int, int] | None = None
        for page in value.get("pages", []):
            msgs = []
            if not page.get("fields") and not page.get("bases"): msgs.append("Página vazia")
            if "?" in json.dumps(page, ensure_ascii=False): msgs.append("Há caractere não lido com segurança (?)")
            try:
                cur = (int(page.get("year")), int(page.get("month")))
                if previous:
                    py, pm = previous; expected = (py + 1, 1) if pm == 12 else (py, pm + 1)
                    if cur != expected: msgs.append("Mês não sequencial")
                previous = cur
            except (TypeError, ValueError): pass
            warnings.append({"messages": msgs})
    return warnings


def rows_for_export(value: dict[str, Any], tipo: str) -> tuple[list[str], list[list[str]], list[list[str]]]:
    if tipo == "cartao-ponto":
        all_days = [d for p in value.get("pages", []) for d in p.get("days", [])]
        max_punches = max((len(d.get("punches", [])) for d in all_days), default=0)
        headers = ["Data"] + [f'{"Entrada" if i % 2 else "Saída"} {(i + 1) // 2}' for i in range(1, max_punches + 1)]
        rows = [[d.get("date_raw", "")] + [p.get("time_hhmm", "") for p in d.get("punches", [])] + [""] * max(0, max_punches - len(d.get("punches", []))) for d in all_days]
        return headers, rows, [w["messages"] for w in row_warnings(value, tipo)]
    labels: list[str] = []
    for page in value.get("pages", []):
        for f in page.get("fields", []):
            if f.get("label") not in labels: labels.append(f.get("label", ""))
    headers = ["Pág.", "Mês", "Ano"] + labels
    rows = []
    for p in value.get("pages", []):
        mapping = {f.get("label", ""): f.get("value", "") for f in p.get("fields", [])}
        rows.append([p.get("page", ""), p.get("month", ""), p.get("year", "")] + [mapping.get(label, "") for label in labels])
    return headers, rows, [w["messages"] for w in row_warnings(value, tipo)]


def process_bytes(data: bytes, tipo: str) -> dict[str, Any]:
    if tipo not in {"cartao-ponto", "holerite"}: raise HTTPException(400, "Tipo de documento inválido")
    return parse_document(extract_pdf_pages(data), tipo)

@app.get("/", response_class=HTMLResponse)
def home() -> str:
    with open(BASE_DIR / "frontend" / "index.html", encoding="utf-8") as f: return f.read()

@app.get("/healthz")
def health() -> dict[str, str]: return {"status": "ok"}

async def _process_job(transcription_id: str, data: bytes, tipo: str) -> None:
    try: DB[transcription_id].update(status="concluido", value=process_bytes(data, tipo), erro=None)
    except HTTPException as exc: DB[transcription_id].update(status="erro", value=None, erro=str(exc.detail))
    except Exception: DB[transcription_id].update(status="erro", value=None, erro="Não foi possível processar o documento")

@app.post("/api/transcricoes", status_code=202)
async def create(background_tasks: BackgroundTasks, arquivo: UploadFile = File(...), tipo: str = Form(...)) -> dict[str, str]:
    if tipo not in {"cartao-ponto", "holerite"}: raise HTTPException(400, "Tipo de documento inválido")
    if not arquivo.filename or not arquivo.filename.lower().endswith(".pdf"): raise HTTPException(400, "Envie um arquivo PDF válido")
    data = await arquivo.read()
    if len(data) > MAX_UPLOAD: raise HTTPException(413, f"PDF excede o limite de {MAX_UPLOAD // 1024 // 1024} MB")
    transcription_id = str(uuid.uuid4())
    DB[transcription_id] = {"id": transcription_id, "tipo": tipo, "status": "processando", "erro": None, "value": None}
    background_tasks.add_task(_process_job, transcription_id, data, tipo)
    return {"id": transcription_id}

@app.get("/api/transcricoes/{transcription_id}")
def get_transcription(transcription_id: str) -> dict[str, Any]:
    item = DB.get(transcription_id)
    if not item: raise HTTPException(404, "Transcrição não encontrada")
    return item

@app.put("/api/transcricoes/{transcription_id}")
def update_transcription(transcription_id: str, body: UpdateBody) -> dict[str, Any]:
    item = DB.get(transcription_id)
    if not item: raise HTTPException(404, "Transcrição não encontrada")
    if item["status"] != "concluido": raise HTTPException(409, "Transcrição ainda não concluída")
    item["value"] = body.value
    return item

@app.get("/api/transcricoes/{transcription_id}/planilha")
def export(transcription_id: str, formato: str = "xlsx"):
    item = DB.get(transcription_id)
    if not item: raise HTTPException(404, "Transcrição não encontrada")
    if item["status"] != "concluido": raise HTTPException(409, "Transcrição ainda não concluída")
    formato = formato.lower(); headers, rows, warnings = rows_for_export(item["value"], item["tipo"])
    if formato == "json":
        raw = json.dumps(item["value"], ensure_ascii=False, indent=2).encode("utf-8")
        return StreamingResponse(io.BytesIO(raw), media_type="application/json", headers={"Content-Disposition": f'attachment; filename="{transcription_id}.json"'})
    if formato == "csv":
        out = io.StringIO(); writer = csv.writer(out); writer.writerow(headers); writer.writerows(rows)
        return StreamingResponse(io.BytesIO(out.getvalue().encode("utf-8-sig")), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{transcription_id}.csv"'})
    if formato == "xlsx":
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Border, Side
        wb = Workbook(); ws = wb.active; ws.title = "Transcrição"; ws.append(headers)
        header_fill = PatternFill("solid", fgColor="173772"); warning_fill = PatternFill("solid", fgColor="FFF3CD"); danger_fill = PatternFill("solid", fgColor="F8D7DA"); danger_side = Side(style="thin", color="DC3545")
        for cell in ws[1]: cell.font = Font(bold=True, color="FFFFFF"); cell.fill = header_fill
        for row_idx, row in enumerate(rows, start=2):
            ws.append(row); msgs = warnings[row_idx - 2] if row_idx - 2 < len(warnings) else []
            if msgs:
                fill = danger_fill if any("não sequencial" in m.lower() or "inválida" in m.lower() for m in msgs) else warning_fill
                for cell in ws[row_idx]: cell.fill = fill
                if fill == danger_fill: ws.cell(row_idx, 1).border = Border(left=danger_side)
        for col in ws.columns:
            width = min(max(len(str(c.value or "")) for c in col) + 2, 45); ws.column_dimensions[col[0].column_letter].width = width
        ws.freeze_panes = "A2"; out = io.BytesIO(); wb.save(out); out.seek(0)
        return StreamingResponse(out, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f'attachment; filename="{transcription_id}.xlsx"'})
    raise HTTPException(400, "Formato deve ser xlsx, csv ou json")
