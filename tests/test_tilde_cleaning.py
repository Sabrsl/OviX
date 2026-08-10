"""
Tests unitaires pour la fonction clean_tilde_artifacts.

Ces tests vérifient que la fonction de nettoyage des tildes
ne casse pas les entités HTML ni la ponctuation.
"""

import sys
from pathlib import Path

# Ajouter src au chemin
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from wikipedia_maintenance.analyzers.typography_utils import clean_tilde_artifacts


def test_clean_tilde_nbsp():
    """Test que &nbsp; reste intact après suppression de ~~"""
    # Cas 1: ~~&nbsp; → &nbsp; (le ; doit rester)
    result = clean_tilde_artifacts("avant ~~&nbsp; apres")
    assert result == "avant &nbsp; apres", f"Échec: {result} != 'avant &nbsp; apres'"
    print("✅ Test &nbsp; pass")


def test_clean_tilde_double_colon():
    """Test que :: reste intact après suppression de ~~"""
    # Cas 2: ~~::Exemples → ::Exemples (pas d'espace inséré)
    result = clean_tilde_artifacts("avant ~~::Exemples")
    assert result == "avant ::Exemples", f"Échec: {result} != 'avant ::Exemples'"
    print("✅ Test :: pass")


def test_clean_tilde_no_op():
    """Test que le texte normal n'est pas modifié"""
    result = clean_tilde_artifacts("texte normal")
    assert result == "texte normal", f"Échec: {result} != 'texte normal'"
    print("✅ Test texte normal pass")


def test_clean_tilde_multiple():
    """Test la suppression de multiples ~~"""
    result = clean_tilde_artifacts("~~debut~~fin")
    assert result == "debutfin", f"Échec: {result} != 'debutfin'"
    print("✅ Test multiples ~~ pass")


def test_clean_tilde_edges():
    """Test les ~~ au début et à la fin"""
    result1 = clean_tilde_artifacts("~~ seul")
    assert result1 == " seul", f"Échec: {result1} != ' seul'"
    
    result2 = clean_tilde_artifacts("fin ~~")
    assert result2 == "fin ", f"Échec: {result2} != 'fin '"
    print("✅ Test ~~ aux bords pass")


def test_clean_tilde_with_other_entities():
    """Test avec d'autres entités HTML"""
    result = clean_tilde_artifacts("~~&eacute;~~&amp;")
    assert result == "&eacute;&amp;", f"Échec: {result} != '&eacute;&amp;'"
    print("✅ Test autres entités HTML pass")


def test_clean_tilde_complex_punctuation():
    """Test avec ponctuation complexe"""
    result = clean_tilde_artifacts("texte~~;;,?!::autres")
    assert result == "texte;;,?!::autres", f"Échec: {result} != 'texte;;,?!::autres'"
    print("✅ Test ponctuation complexe pass")


if __name__ == "__main__":
    test_clean_tilde_nbsp()
    test_clean_tilde_double_colon()
    test_clean_tilde_no_op()
    test_clean_tilde_multiple()
    test_clean_tilde_edges()
    test_clean_tilde_with_other_entities()
    test_clean_tilde_complex_punctuation()
    print("\n=== TOUS LES TESTS DE NETTOYAGE DES TILDES PASSÉS ✅ ===")
