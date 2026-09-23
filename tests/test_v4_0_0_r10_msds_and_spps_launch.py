from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, urlparse

from peptiforg_core.msds_lookup import (
    google_msds_url,
    open_google_msds,
    peptide_chemistry_terms,
    terms_from_text,
)
from spps_v4_gui.classic_base import ClassicBaseCore


ROOT = Path(__file__).resolve().parents[1]


def test_google_msds_url_expands_known_abbreviation_without_scraping() -> None:
    url = google_msds_url("DMF")
    parsed = urlparse(url)
    assert parsed.netloc == "www.google.com"
    query = parse_qs(parsed.query)["q"][0]
    assert "N,N-Dimethylformamide" in query
    assert "SDS" in query and "MSDS" in query


def test_google_msds_open_uses_supplied_browser_opener() -> None:
    opened = []
    url = open_google_msds("TFA", opener=opened.append)
    assert opened == [url]
    assert "google.com/search" in url


def test_msds_terms_extract_mixed_spps_condition_components() -> None:
    terms = terms_from_text("95% TFA + TIS / DCM")
    assert terms == ["TFA", "TIS", "DCM"]


def test_pde_msds_context_keeps_explicit_modified_chemistry_only() -> None:
    terms = peptide_chemistry_terms("Ac-Aib-Ahx-E-NH2")
    assert "Ac" in terms
    assert "Aib" in terms
    assert "Ahx" in terms
    # Natural one-letter Glu is intentionally not guessed into a protected bottle.
    assert "E" not in terms


def test_spps_log_is_safe_when_streamlined_ui_has_no_log_widget() -> None:
    class Dummy:
        pass

    dummy = Dummy()
    ClassicBaseCore._log(dummy, "startup warning\n")
    ClassicBaseCore._log(dummy, "second message\n")
    assert dummy._pending_log_messages == ["startup warning\n", "second message\n"]


def test_spps_surface_exposes_msds_lookup_and_safe_log_contract() -> None:
    classic = (ROOT / "spps_v4_gui" / "classic_base.py").read_text(encoding="utf-8")
    controller = (ROOT / "spps_v4_gui" / "controller.py").read_text(encoding="utf-8")
    assert "pm_msds_button" in classic
    assert "MSDS / SDS" in classic
    assert "def open_msds_lookup" in controller
    assert "show_msds_lookup" in controller


def test_pde_surface_exposes_google_msds_lookup_in_chemistry_and_results() -> None:
    source = (ROOT / "apps" / "peptide_design_engine" / "Python" / "desktop_gui.py").read_text(encoding="utf-8")
    assert "def _msds_context_terms" in source
    assert "def open_msds_lookup" in source
    assert source.count('text="MSDS / SDS (Google)"') >= 2
    assert "PDE chemistry names are design tokens" in source
