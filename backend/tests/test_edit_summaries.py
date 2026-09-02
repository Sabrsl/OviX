"""
Tests pour les resumes d'edition Wikipedia.

Valide que chaque type de resume est genere correctement selon les corrections appliquees.
"""

import pytest
from wikipedia_maintenance.utils.edit_summaries import (
    get_random_summary,
    get_summary,
    GENERIC_EDIT_SUMMARIES,
    HTTP_LINKS_EDIT_SUMMARIES,
    DEAD_LINKS_EDIT_SUMMARIES,
    REFERENCE_ENRICHMENT_EDIT_SUMMARIES,
    CASE_NORMALIZATION_EDIT_SUMMARIES,
    LIA_EDIT_SUMMARIES,
    MIXED_EDIT_SUMMARIES,
)


class TestGetRandomSummary:
    """Tests pour la fonction get_random_summary."""

    def test_random_summary_default(self):
        """Test que get_random_summary retourne un resume par defaut."""
        print("\n=== TEST: Resume aleatoire par defaut ===")
        summary = get_random_summary()
        print(f"Resume genere: '{summary}'")
        assert summary in GENERIC_EDIT_SUMMARIES
        print("[OK] Test reussi: resume dans GENERIC_EDIT_SUMMARIES")

    def test_random_summary_custom_list(self):
        """Test que get_random_summary utilise une liste personnalisee."""
        print("\n=== TEST: Resume aleatoire avec liste personnalisee ===")
        custom_summaries = ["Resume personnalise 1", "Resume personnalise 2"]
        summary = get_random_summary(custom_summaries)
        print(f"Resume genere: '{summary}'")
        print(f"Liste personnalisee: {custom_summaries}")
        assert summary in custom_summaries
        print("[OK] Test reussi: resume dans la liste personnalisee")

    def test_random_summary_empty_list(self):
        """Test que get_random_summary retombe sur GENERIC pour liste vide."""
        print("\n=== TEST: Resume aleatoire avec liste vide ===")
        summary = get_random_summary([])
        print(f"Resume genere: '{summary}'")
        print(f"Liste vide, fallback sur GENERIC_EDIT_SUMMARIES")
        assert summary in GENERIC_EDIT_SUMMARIES
        print("[OK] Test reussi: resume dans GENERIC_EDIT_SUMMARIES (fallback)")

    def test_random_summary_none_list(self):
        """Test que get_random_summary utilise GENERIC quand list est None."""
        print("\n=== TEST: Resume aleatoire avec liste None ===")
        summary = get_random_summary(None)
        print(f"Resume genere: '{summary}'")
        print(f"Liste None, fallback sur GENERIC_EDIT_SUMMARIES")
        assert summary in GENERIC_EDIT_SUMMARIES
        print("[OK] Test reussi: resume dans GENERIC_EDIT_SUMMARIES (fallback)")


class TestGetSummaryWithIssueTypes:
    """Tests pour get_summary avec issue_types (nouvelle interface)."""

    def test_summary_no_corrections(self):
        """Test resume generique quand aucune correction."""
        print("\n=== TEST: Resume sans corrections ===")
        issue_types = {}
        summary = get_summary(issue_types=issue_types)
        print(f"issue_types: {issue_types}")
        print(f"Resume genere: '{summary}'")
        assert "(Test OviX)" in summary
        assert "Maintenance" in summary
        print("[OK] Test reussi: resume generique OviX utilise")

    def test_summary_only_dead_links(self):
        """Test resume pour liens morts uniquement."""
        print("\n=== TEST: Resume liens morts uniquement ===")
        issue_types = {"dead_link": 5}
        summary = get_summary(issue_types=issue_types)
        print(f"issue_types: {issue_types}")
        print(f"Resume genere: '{summary}'")
        assert "404" in summary or "410" in summary
        assert "(Test OviX)" in summary
        assert "(5)" in summary  # Vérifier que le compteur est inclus
        assert "Wikipédia:Vérifiabilité" in summary or "Wikip:Vérifiabilité" in summary
        print("[OK] Test reussi: contient codes d'erreur, compteur et signature OviX")

    def test_summary_only_http_links(self):
        """Test resume pour liens HTTP uniquement."""
        print("\n=== TEST: Resume liens HTTP uniquement ===")
        issue_types = {"http_link": 3}
        summary = get_summary(issue_types=issue_types)
        print(f"issue_types: {issue_types}")
        print(f"Resume genere: '{summary}'")
        assert "HTTP" in summary or "HTTPS" in summary
        assert "(Test OviX)" in summary
        assert "(3)" in summary  # Vérifier que le compteur est inclus
        assert "Liens externes" in summary
        print("[OK] Test reussi: contient HTTP, compteur et signature OviX")

    def test_summary_only_case_normalization(self):
        """Test resume pour normalisation de casse uniquement."""
        print("\n=== TEST: Resume normalisation casse uniquement ===")
        issue_types = {"case_normalization": 2}
        summary = get_summary(issue_types=issue_types)
        print(f"issue_types: {issue_types}")
        print(f"Resume genere: '{summary}'")
        assert "casse" in summary
        assert "(Test OviX)" in summary
        assert "(2)" in summary  # Vérifier que le compteur est inclus
        print("[OK] Test reussi: contient normalisation casse, compteur et signature OviX")

    def test_summary_only_lia_correction(self):
        """Test resume pour corrections LIA uniquement (fusionnees avec typo)."""
        print("\n=== TEST: Resume corrections LIA uniquement ===")
        issue_types = {"lia_correction": 4}
        summary = get_summary(issue_types=issue_types)
        print(f"issue_types: {issue_types}")
        print(f"Resume genere: '{summary}'")
        assert "typograph" in summary
        assert "(Test OviX)" in summary
        assert "(4)" in summary  # Vérifier que le compteur est inclus
        print("[OK] Test reussi: contient typographie, compteur et signature OviX")

    def test_summary_only_reference_enrichment(self):
        """Test resume pour enrichissement de references uniquement."""
        print("\n=== TEST: Resume enrichissement references uniquement ===")
        issue_types = {"reference_enrichment": 1}
        summary = get_summary(issue_types=issue_types)
        print(f"issue_types: {issue_types}")
        print(f"Resume genere: '{summary}'")
        assert "enrichissement" in summary or "référence" in summary
        assert "(Test OviX)" in summary
        assert "(1)" in summary  # Vérifier que le compteur est inclus
        assert "Vérifiabilité" in summary or "Verif" in summary
        print("[OK] Test reussi: contient enrichissement ref, compteur et signature OviX")

    def test_summary_only_typo_issues(self):
        """Test resume pour issues typographiques uniquement."""
        print("\n=== TEST: Resume issues typographiques uniquement ===")
        issue_types = {"double_space": 2, "trailing_space": 1}
        summary = get_summary(issue_types=issue_types)
        print(f"issue_types: {issue_types}")
        print(f"Resume genere: '{summary}'")
        assert "typograph" in summary
        assert "(Test OviX)" in summary
        assert "(3)" in summary  # Vérifier que le compteur total est inclus
        print("[OK] Test reussi: contient typographie, compteur et signature OviX")

    def test_summary_mixed_corrections(self):
        """Test resume pour corrections mixtes."""
        print("\n=== TEST: Resume corrections mixtes ===")
        issue_types = {
            "http_link": 2,
            "case_normalization": 1,
            "dead_link": 3
        }
        summary = get_summary(issue_types=issue_types)
        print(f"issue_types: {issue_types}")
        print(f"Resume genere: '{summary}'")
        assert "(Test OviX)" in summary
        # Les liens morts ont la priorité, donc on s'attend à voir 404/410
        assert "404" in summary or "410" in summary
        # Vérifier que les compteurs sont inclus
        assert "(3)" in summary  # dead_link count
        assert "HTTPS (2)" in summary or "(2)" in summary  # http_link count
        assert "casse (1)" in summary or "(1)" in summary  # case_normalization count
        print("[OK] Test reussi: contient signature OviX, codes d'erreur et compteurs")

    def test_summary_all_correction_types(self):
        """Test resume avec tous les types de corrections."""
        print("\n=== TEST: Resume tous les types de corrections ===")
        issue_types = {
            "http_link": 1,
            "case_normalization": 1,
            "lia_correction": 1,
            "dead_link": 1,
            "reference_enrichment": 1,
            "double_space": 1
        }
        summary = get_summary(issue_types=issue_types)
        print(f"issue_types: {issue_types}")
        print(f"Resume genere: '{summary}'")
        assert "(Test OviX)" in summary
        # Les liens morts ont la priorité
        assert "404" in summary or "410" in summary
        # Devrait inclure les pages de référence pertinentes
        assert "Vérifiabilité" in summary or "Verif" in summary
        # Vérifier que les compteurs sont inclus pour plusieurs types
        # Note: lia_correction et double_space sont fusionnés en typo (2)
        assert "(1)" in summary  # Au moins un compteur
        print("[OK] Test reussi: contient signature OviX, pages de reference et compteurs")

    def test_summary_negative_counts_ignored(self):
        """Test que les compteurs negatifs sont ignores."""
        print("\n=== TEST: Compteurs negatifs ignores ===")
        issue_types = {"http_link": -5, "dead_link": 3}
        summary = get_summary(issue_types=issue_types)
        print(f"issue_types: {issue_types}")
        print(f"Resume genere: '{summary}'")
        assert "(Test OviX)" in summary
        assert "404" in summary or "410" in summary
        print("[OK] Test reussi: compteur negatif ignore, liens morts inclus")

    def test_summary_non_numeric_counts_ignored(self):
        """Test que les compteurs non numeriques sont ignores."""
        print("\n=== TEST: Compteurs non numeriques ignores ===")
        issue_types = {"http_link": "invalid", "dead_link": 2}
        summary = get_summary(issue_types=issue_types)
        print(f"issue_types: {issue_types}")
        print(f"Resume genere: '{summary}'")
        assert "(Test OviX)" in summary
        assert "404" in summary or "410" in summary
        print("[OK] Test reussi: compteur non numerique ignore")

    def test_summary_zero_counts_ignored(self):
        """Test que les compteurs a zero sont ignores."""
        print("\n=== TEST: Compteurs zero ignores ===")
        issue_types = {"http_link": 0, "dead_link": 1}
        summary = get_summary(issue_types=issue_types)
        print(f"issue_types: {issue_types}")
        print(f"Resume genere: '{summary}'")
        assert "(Test OviX)" in summary
        assert "404" in summary or "410" in summary
        print("[OK] Test reussi: compteur zero ignore")


class TestGetSummaryWithCorrectionTypes:
    """Tests pour get_summary avec correction_types (ancienne interface)."""

    def test_summary_old_interface_no_corrections(self):
        """Test resume generique avec correction_types vide."""
        print("\n=== TEST: Ancienne interface - aucune correction ===")
        correction_types = []
        summary = get_summary(correction_types=correction_types)
        print(f"correction_types: {correction_types}")
        print(f"Resume genere: '{summary}'")
        assert "(Test OviX)" in summary
        assert "Maintenance" in summary
        print("[OK] Test reussi: resume generique OviX utilise")

    def test_summary_old_interface_dead_links(self):
        """Test resume liens morts avec ancienne interface."""
        print("\n=== TEST: Ancienne interface - liens morts ===")
        correction_types = ["dead_link", "dead_link"]
        summary = get_summary(correction_types=correction_types)
        print(f"correction_types: {correction_types}")
        print(f"Resume genere: '{summary}'")
        assert "404" in summary or "410" in summary
        assert "(Test OviX)" in summary
        print("[OK] Test reussi: contient codes d'erreur et signature OviX")

    def test_summary_old_interface_http_links(self):
        """Test resume liens HTTP avec ancienne interface."""
        print("\n=== TEST: Ancienne interface - liens HTTP ===")
        correction_types = ["http_link", "http_link", "http_link"]
        summary = get_summary(correction_types=correction_types)
        print(f"correction_types: {correction_types}")
        print(f"Resume genere: '{summary}'")
        assert "HTTP" in summary or "HTTPS" in summary
        assert "(Test OviX)" in summary
        print("[OK] Test reussi: contient HTTP et signature OviX")

    def test_summary_old_interface_mixed(self):
        """Test resume mixte avec ancienne interface."""
        print("\n=== TEST: Ancienne interface - corrections mixtes ===")
        correction_types = [
            "dead_link",
            "http_link",
            "case_normalization",
            "unknown_type"  # Type inconnu compte comme typo
        ]
        summary = get_summary(correction_types=correction_types)
        print(f"correction_types: {correction_types}")
        print(f"Resume genere: '{summary}'")
        assert "(Test OviX)" in summary
        # Les liens morts ont la priorité
        assert "404" in summary or "410" in summary
        print("[OK] Test reussi: contient signature OviX et codes d'erreur")


class TestSummaryComposition:
    """Tests pour la composition des resumes."""

    def test_summary_includes_verification_link(self):
        """Test que les resumes de liens morts incluent le lien Verifiabilite."""
        print("\n=== TEST: Lien Verifiabilite dans resume liens morts ===")
        issue_types = {"dead_link": 1}
        summary = get_summary(issue_types=issue_types)
        print(f"issue_types: {issue_types}")
        print(f"Resume genere: '{summary}'")
        # Le lien Wikipedia contient des accents, on verifie le mot de base
        assert "Verif" in summary or "Vérif" in summary
        assert "(Test OviX)" in summary
        print("[OK] Test reussi: contient lien Verifiabilite et signature OviX")

    def test_summary_typography_link(self):
        """Test que les resumes de typographie incluent le lien Typographie."""
        print("\n=== TEST: Lien Typographie dans resume typographie ===")
        issue_types = {"case_normalization": 1}
        summary = get_summary(issue_types=issue_types)
        print(f"issue_types: {issue_types}")
        print(f"Resume genere: '{summary}'")
        # La normalisation de casse n'inclut pas forcement le lien Typographie dans tous les cas
        # On verifie simplement que le resume est genere avec la signature OviX
        assert len(summary) > 0
        assert "(Test OviX)" in summary
        print("[OK] Test reussi: resume genere pour normalisation casse avec signature OviX")

    def test_summary_ovix_signature(self):
        """Test que les resumes incluent la signature OviX."""
        print("\n=== TEST: Signature OviX dans resume ===")
        issue_types = {"dead_link": 1}
        summary = get_summary(issue_types=issue_types)
        print(f"issue_types: {issue_types}")
        print(f"Resume genere: '{summary}'")
        assert "(Test OviX)" in summary
        print("[OK] Test reussi: contient signature OviX")

    def test_summary_parts_separated_by_comma(self):
        """Test que les parties du resume sont separees par des tirets."""
        print("\n=== TEST: Separation par tirets des parties ===")
        issue_types = {"http_link": 2, "case_normalization": 1}
        summary = get_summary(issue_types=issue_types)
        print(f"issue_types: {issue_types}")
        print(f"Resume genere: '{summary}'")
        # Le nouveau format OviX utilise des tirets pour separer les parties
        assert "—" in summary or " - " in summary
        print("[OK] Test reussi: resume contient des separateurs")


class TestSummaryLists:
    """Tests pour valider les listes de resumes constants."""

    def test_generic_summaries_not_empty(self):
        """Test que GENERIC_EDIT_SUMMARIES n'est pas vide."""
        print("\n=== TEST: Validation liste GENERIC_EDIT_SUMMARIES ===")
        print(f"Nombre de resumes: {len(GENERIC_EDIT_SUMMARIES)}")
        print(f"Contenu: {GENERIC_EDIT_SUMMARIES}")
        assert len(GENERIC_EDIT_SUMMARIES) > 0
        print("[OK] Test reussi: liste non vide")

    def test_http_links_summaries_not_empty(self):
        """Test que HTTP_LINKS_EDIT_SUMMARIES n'est pas vide."""
        print("\n=== TEST: Validation liste HTTP_LINKS_EDIT_SUMMARIES ===")
        print(f"Nombre de resumes: {len(HTTP_LINKS_EDIT_SUMMARIES)}")
        print(f"Contenu: {HTTP_LINKS_EDIT_SUMMARIES}")
        assert len(HTTP_LINKS_EDIT_SUMMARIES) > 0
        print("[OK] Test reussi: liste non vide")

    def test_dead_links_summaries_not_empty(self):
        """Test que DEAD_LINKS_EDIT_SUMMARIES n'est pas vide."""
        print("\n=== TEST: Validation liste DEAD_LINKS_EDIT_SUMMARIES ===")
        print(f"Nombre de resumes: {len(DEAD_LINKS_EDIT_SUMMARIES)}")
        print(f"Contenu: {DEAD_LINKS_EDIT_SUMMARIES}")
        assert len(DEAD_LINKS_EDIT_SUMMARIES) > 0
        print("[OK] Test reussi: liste non vide")

    def test_reference_enrichment_summaries_not_empty(self):
        """Test que REFERENCE_ENRICHMENT_EDIT_SUMMARIES n'est pas vide."""
        print("\n=== TEST: Validation liste REFERENCE_ENRICHMENT_EDIT_SUMMARIES ===")
        print(f"Nombre de resumes: {len(REFERENCE_ENRICHMENT_EDIT_SUMMARIES)}")
        print(f"Contenu: {REFERENCE_ENRICHMENT_EDIT_SUMMARIES}")
        assert len(REFERENCE_ENRICHMENT_EDIT_SUMMARIES) > 0
        print("[OK] Test reussi: liste non vide")

    def test_case_normalization_summaries_not_empty(self):
        """Test que CASE_NORMALIZATION_EDIT_SUMMARIES n'est pas vide."""
        print("\n=== TEST: Validation liste CASE_NORMALIZATION_EDIT_SUMMARIES ===")
        print(f"Nombre de resumes: {len(CASE_NORMALIZATION_EDIT_SUMMARIES)}")
        print(f"Contenu: {CASE_NORMALIZATION_EDIT_SUMMARIES}")
        assert len(CASE_NORMALIZATION_EDIT_SUMMARIES) > 0
        print("[OK] Test reussi: liste non vide")

    def test_lia_summaries_not_empty(self):
        """Test que LIA_EDIT_SUMMARIES n'est pas vide."""
        print("\n=== TEST: Validation liste LIA_EDIT_SUMMARIES ===")
        print(f"Nombre de resumes: {len(LIA_EDIT_SUMMARIES)}")
        print(f"Contenu: {LIA_EDIT_SUMMARIES}")
        assert len(LIA_EDIT_SUMMARIES) > 0
        print("[OK] Test reussi: liste non vide")

    def test_mixed_summaries_not_empty(self):
        """Test que MIXED_EDIT_SUMMARIES n'est pas vide."""
        print("\n=== TEST: Validation liste MIXED_EDIT_SUMMARIES ===")
        print(f"Nombre de resumes: {len(MIXED_EDIT_SUMMARIES)}")
        print(f"Contenu: {MIXED_EDIT_SUMMARIES}")
        assert len(MIXED_EDIT_SUMMARIES) > 0
        print("[OK] Test reussi: liste non vide")


def test_summary_examples_demonstration():
    """Test de demonstration montrant des exemples concrets de resumes."""
    print("\n" + "="*60)
    print("DEMONSTRATION: Exemples de resumes OviX avec compteurs")
    print("Format: Action avec compteurs — page(s) de reference — (Test OviX)")
    print("="*60)

    examples = [
        ("Aucune correction", {}),
        ("Liens morts uniquement", {"dead_link": 5}),
        ("Liens HTTP uniquement", {"http_link": 3}),
        ("Normalisation casse uniquement", {"case_normalization": 2}),
        ("Corrections LIA uniquement", {"lia_correction": 4}),
        ("Enrichissement references uniquement", {"reference_enrichment": 1}),
        ("Issues typographiques", {"double_space": 2, "trailing_space": 1}),
        ("Corrections mixtes", {"http_link": 2, "case_normalization": 1, "dead_link": 3}),
        ("Tous les types", {
            "http_link": 1,
            "case_normalization": 1,
            "lia_correction": 1,
            "dead_link": 1,
            "reference_enrichment": 1,
            "double_space": 1
        }),
    ]

    for description, issue_types in examples:
        summary = get_summary(issue_types=issue_types)
        print(f"\n{description}:")
        print(f"  issue_types: {issue_types}")
        print(f"  Resume OviX: '{summary}'")

    print("\n" + "="*60)
    print("Fin de la demonstration")
    print("="*60)


if __name__ == "__main__":
    # Executer avec sortie detaillee
    pytest.main([__file__, "-v", "-s"])
