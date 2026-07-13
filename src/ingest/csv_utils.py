import csv
import io
import re
import unicodedata
from pathlib import Path


def _decode_bytes(data: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1", errors="replace")


def _guess_delimiter(sample: str) -> str:
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;")
        return dialect.delimiter
    except csv.Error:
        pass
    commas = sample.count(",")
    semis = sample.count(";")
    if semis > commas:
        return ";"
    return ","


def _pick_header_row(lines: list[str], required_headers: list[str] | None, start_at: int) -> int:
    if not required_headers:
        return start_at

    needed = [normalize_header(h) for h in required_headers if h]
    if not needed:
        return start_at

    limit = min(len(lines), start_at + 30)
    for idx in range(start_at, limit):
        line = lines[idx]
        if not line.strip():
            continue
        delimiter = _guess_delimiter(line)
        cols = [normalize_header(part.strip()) for part in line.split(delimiter)]
        if all(any(token in col for col in cols) for token in needed):
            return idx
    return start_at


def read_csv_rows(
    path: Path,
    *,
    skip_rows: int = 0,
    required_headers: list[str] | None = None,
) -> tuple[list[str], list[dict[str, str]]]:
    data = path.read_bytes()
    text = _decode_bytes(data)
    lines = text.splitlines()
    if not lines:
        return [], []

    header_row = _pick_header_row(lines, required_headers, max(skip_rows, 0))
    header_sample = lines[header_row] if header_row < len(lines) else lines[0]
    delimiter = _guess_delimiter(header_sample)
    sliced = "\n".join(lines[header_row:])
    reader = csv.DictReader(io.StringIO(sliced), delimiter=delimiter)
    headers = reader.fieldnames or []
    rows: list[dict[str, str]] = []
    for row in reader:
        cleaned: dict[str, str] = {}
        for k, v in row.items():
            key = k or ""
            if isinstance(v, list):
                value = ",".join([str(item) for item in v if item is not None]).strip()
            else:
                value = (v or "").strip()
            cleaned[key] = value
        if any(value for value in cleaned.values()):
            rows.append(cleaned)
    return headers, rows


def normalize_header(name: str) -> str:
    if not name:
        return ""
    text = unicodedata.normalize("NFKD", name)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    return text


def find_header(headers: list[str], pattern: str) -> str | None:
    regex = re.compile(pattern)
    for h in headers:
        if regex.search(normalize_header(h)):
            return h
    return None
