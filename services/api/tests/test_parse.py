"""G023: ClinVar parse normalisation."""

from app.clinvar import parse


def test_date_dec_17_2024() -> None:
    assert parse.norm_date("Dec 17, 2024") == "2024-12-17"


def test_date_dash_is_none() -> None:
    assert parse.norm_date("-") is None
    assert parse.norm_date("") is None
    assert parse.norm_date("   ") is None


def test_class_map_case_variants() -> None:
    assert parse.norm_class("Likely Pathogenic") == "LP"
    assert parse.norm_class("pathogenic") == "P"
    assert parse.norm_class("Uncertain significance") == "VUS"
    assert parse.norm_class("Likely benign") == "LB"
    assert parse.norm_class("Benign") == "B"
    assert parse.norm_class("Conflicting classifications of pathogenicity") == "CONFLICTING"
    assert parse.norm_class("drug response") == "OTHER"


def test_stars() -> None:
    assert parse.norm_stars("practice guideline") == 4
    assert parse.norm_stars("reviewed by expert panel") == 3
    assert parse.norm_stars("no assertion criteria provided") == 0


def test_submitter_slug_labcorp() -> None:
    name = "Women's Health and Genetics/Laboratory Corporation of America, LabCorp"
    assert parse.submitter_slug(name) == (
        "women-s-health-and-genetics-laboratory-corporation-of-america-labcorp"
    )


def test_split_genes_multi() -> None:
    assert parse.split_genes("BRCA2;BRCA1") == ["BRCA2", "BRCA1"]
    assert parse.split_genes("BRCA2") == ["BRCA2"]


def test_in_scope_gene_exactly_one() -> None:
    scope = {"BRCA1", "BRCA2"}
    assert parse.in_scope_gene("BRCA2", scope) == "BRCA2"
    assert parse.in_scope_gene("BRCA1;BRCA2", scope) is None  # two in scope -> skip
    assert parse.in_scope_gene("BRCA2;OTHER", scope) == "BRCA2"
    assert parse.in_scope_gene("TTN", scope) is None


def test_change_kind() -> None:
    assert parse.change_kind("VUS", "P") == "UP_TO_ACTIONABLE"
    assert parse.change_kind("P", "LB") == "DOWN_FROM_ACTIONABLE"
    assert parse.change_kind("VUS", "LB") == "VUS_RESOLVED_BENIGN"
    assert parse.change_kind("LB", "VUS") == "BENIGN_TO_VUS"
    assert parse.change_kind("VUS", "VUS") == "WITHIN_TIER"
    assert parse.change_kind("P", "CONFLICTING") == "NEEDS_REVIEW_CLASS"
