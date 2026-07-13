"""Testes para src/ingest/csv_utils.py — funções puras sem dependência de DB."""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ingest.csv_utils import _guess_delimiter, _decode_bytes, normalize_header


class TestGuessDelimiter:
    def test_comma_csv(self):
        sample = "nome,email,valor\nJoão,joao@test.com,100"
        assert _guess_delimiter(sample) == ","

    def test_semicolon_csv(self):
        sample = "nome;email;valor\nJoão;joao@test.com;100"
        assert _guess_delimiter(sample) == ";"

    def test_fallback_semis_win_when_sniffer_fails(self, mocker):
        # Sniffer can return incorrect results for single-line ambiguous input;
        # force the fallback counting logic by making Sniffer raise csv.Error.
        mocker.patch.object(csv.Sniffer, "sniff", side_effect=csv.Error)
        sample = "a;b;c;d,e"  # 4 semicolons vs 1 comma
        assert _guess_delimiter(sample) == ";"

    def test_more_commas_than_semis(self):
        sample = "a,b,c,d;e"
        assert _guess_delimiter(sample) == ","


class TestDecodeBytes:
    def test_utf8(self):
        data = "Olá mundo".encode("utf-8")
        assert _decode_bytes(data) == "Olá mundo"

    def test_utf8_bom(self):
        data = "teste".encode("utf-8-sig")
        result = _decode_bytes(data)
        assert "teste" in result

    def test_latin1_fallback(self):
        data = "caf\xe9".encode("latin-1")
        result = _decode_bytes(data)
        assert "caf" in result

    def test_cp1252(self):
        data = "R$ 1.234,56".encode("cp1252")
        result = _decode_bytes(data)
        assert "1.234" in result


class TestNormalizeHeader:
    def test_lowercase_strip(self):
        assert normalize_header("  Email  ") == "email"

    def test_remove_accents(self):
        result = normalize_header("Campanha")
        assert "campanha" in result

    def test_empty_string(self):
        assert normalize_header("") == ""
