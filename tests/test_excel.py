import sys
from pathlib import Path

from openpyxl import load_workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_excel  # noqa: E402


def test_workbook_builds_with_formulas(tmp_path):
    path = build_excel.build(tmp_path / "model.xlsx")
    wb = load_workbook(path)
    assert wb.sheetnames == ["Cover", "Inputs", "Model", "Scenarios", "Peer_Screen", "Checks", "Bank_Data"]
    formulas = sum(1 for ws in wb.worksheets for row in ws.iter_rows() for c in row if isinstance(c.value, str) and c.value.startswith("="))
    assert formulas > 1500
    text = " ".join(str(c.value) for ws in wb.worksheets for row in ws.iter_rows() for c in row if isinstance(c.value, str))
    for banned in ["XLOOKUP", "FILTER(", "SORT(", "UNIQUE(", "#REF!"]:
        assert banned not in text
    assert wb["Inputs"]["C4"].value == build_excel.DEFAULT_BANK
    assert wb["Bank_Data"].max_row >= 102


def test_model_rows_are_formulas(tmp_path):
    wb = load_workbook(build_excel.build(tmp_path / "model.xlsx"))
    md = wb["Model"]
    projected = [md.cell(row=r, column=c).value for r in range(24, 43) for c in range(4, 12)]
    assert all(isinstance(v, str) and v.startswith("=") for v in projected)
