# Tests fonctionnels réels pour l'architecture robuste du kill switch
# Tests que l'état persistant fonctionne et que le Publisher bloque réellement

import sys
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

print("=" * 70)
print("TESTS FONCTIONNELS - KILL SWITCH ROBUSTE")
print("=" * 70)

results = []

# TEST 1: État persistant
print("\n=== TEST 1: État Persistant ===")
try:
    from wikipedia_maintenance.utils import KillSwitchManager, KillSwitchTrigger
    
    # Créer un fichier temporaire pour l'état
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        state_file = f.name
    
    try:
        # Créer manager
        manager = KillSwitchManager(state_file)
        
        # Vérifier état initial
        if not manager.is_enabled():
            print("✓ Kill switch désactivé par défaut")
            results.append(("État initial désactivé", True))
        else:
            print("✗ Kill switch activé par défaut")
            results.append(("État initial désactivé", False))
        
        # Activer le kill switch
        manager.enable(
            reason="Test activation",
            trigger_source=KillSwitchTrigger.MANUAL,
            requested_by="test_user"
        )
        
        # Vérifier qu'il est activé
        if manager.is_enabled():
            print("✓ Kill switch activé avec succès")
            results.append(("Activation kill switch", True))
        else:
            print("✗ Kill switch non activé")
            results.append(("Activation kill switch", False))
        
        # Créer un NOUVEAU manager (simule un redémarrage)
        manager2 = KillSwitchManager(state_file)
        
        # Vérifier que l'état persiste
        if manager2.is_enabled():
            print("✓ État persiste après redémarrage")
            results.append(("Persistance état", True))
        else:
            print("✗ État ne persiste pas")
            results.append(("Persistance état", False))
        
        # Désactiver
        manager2.disable(reason="Test", requested_by="test_user")
        
        # Vérifier désactivation
        if not manager2.is_enabled():
            print("✓ Kill switch désactivé")
            results.append(("Désactivation kill switch", True))
        else:
            print("✗ Kill switch non désactivé")
            results.append(("Désactivation kill switch", False))
    
    finally:
        # Nettoyer le fichier temporaire
        if os.path.exists(state_file):
            os.remove(state_file)
        
except Exception as e:
    print(f"✗ Test état persistant échoué: {e}")
    results.append(("État persistant", False))

# TEST 2: Page de discussion avec commandes déterministes
print("\n=== TEST 2: Page de Discussion - Commandes Déterministes ===")
try:
    from wikipedia_maintenance.utils import TalkPageMonitor, TalkPageCommand
    from wikipedia_maintenance.utils import KillSwitchManager, KillSwitchTrigger
    
    monitor = TalkPageMonitor("TestBot")
    
    # Test avec commande STOP valide
    page_content = """
    == Discussion ==
    
    Some text here.
    
    <!-- BOT-CONTROL: STOP -->
    
    More text.
    """
    
    commands = monitor.parse_commands(page_content)
    
    if len(commands) == 1 and commands[0].command == "STOP":
        print("✓ Commande STOP détectée correctement")
        results.append(("Détection commande STOP", True))
    else:
        print(f"✗ Commande STOP non détectée: {len(commands)} commandes trouvées")
        results.append(("Détection commande STOP", False))
    
    # Test avec commande RESUME valide
    page_content_resume = """
    == Discussion ==
    
    <!-- BOT-CONTROL: RESUME -->
    
    More text.
    """
    
    commands_resume = monitor.parse_commands(page_content_resume)
    
    if len(commands_resume) == 1 and commands_resume[0].command == "RESUME":
        print("✓ Commande RESUME détectée correctement")
        results.append(("Détection commande RESUME", True))
    else:
        print(f"✗ Commande RESUME non détectée")
        results.append(("Détection commande RESUME", False))
    
    # Test que le langage naturel n'est PAS interprété
    page_natural = """
    == Discussion ==
    
    Il faudrait arrêter ce bot pendant quelques minutes.
    
    More text.
    """
    
    commands_natural = monitor.parse_commands(page_natural)
    
    if len(commands_natural) == 0:
        print("✓ Langage naturel ignoré (pas de fausse détection)")
        results.append(("Ignorer langage naturel", True))
    else:
        print(f"✗ Langage naturel interprété par erreur")
        results.append(("Ignorer langage naturel", False))
        
except Exception as e:
    print(f"✗ Test page discussion échoué: {e}")
    results.append(("Page discussion", False))

# TEST 3: Vérification finale dans Publisher
print("\n=== TEST 3: Vérification Finale Publisher ===")
try:
    from wikipedia_maintenance.utils import Publisher, get_kill_switch_manager
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        state_file = f.name
    
    try:
        # Créer kill switch manager
        kill_switch = get_kill_switch_manager(state_file)
        
        # Activer le kill switch
        kill_switch.enable(
            reason="Test Publisher check",
            trigger_source=KillSwitchTrigger.MANUAL,
            requested_by="test"
        )
        
        # Créer publisher
        with patch('wikipedia_maintenance.utils.publisher.Publisher._throttled_get'), \
             patch('wikipedia_maintenance.utils.publisher.Publisher.authenticate'):
            
            publisher = Publisher(username="test", password="test", language="fr", dry_run=False)
            
            # Tenter de publier - doit être bloqué par kill switch
            success, message = publisher.publish(
                page_title="Test",
                content="Test content",
                summary="Test"
            )
            
            if not success and "blocked" in message.lower():
                print(f"✓ Publication bloquée par kill switch: {message[:60]}...")
                results.append(("Publisher vérifie kill switch", True))
            else:
                print(f"✗ Publication non bloquée: success={success}, message={message}")
                results.append(("Publisher vérifie kill switch", False))
    
    finally:
        if os.path.exists(state_file):
            os.remove(state_file)
        
except Exception as e:
    print(f"✗ Test Publisher échoué: {e}")
    results.append(("Publisher vérification", False))

# TEST 4: Seuil exact de validation diff (2000 caractères)
print("\n=== TEST 4: Seuil Exact Validation Diff (2000 caractères) ===")
try:
    from wikipedia_maintenance.utils.publisher import Publisher
    
    with patch('wikipedia_maintenance.utils.publisher.Publisher._throttled_get'), \
         patch('wikipedia_maintenance.utils.publisher.Publisher.authenticate'):
        
        publisher = Publisher(username="test", password="test", language="fr", dry_run=True)
        
        print(f"Seuil max_diff_size configuré: {publisher.max_diff_size} caractères")
        
        if publisher.max_diff_size == 2000:
            print("✓ Seuil correctement fixé à 2000 caractères")
            results.append(("Seuil 2000 caractères", True))
        else:
            print(f"✗ Seuil incorrect: {publisher.max_diff_size}")
            results.append(("Seuil 2000 caractères", False))
        
        # Test avec diff acceptable (1999 caractères)
        original = "A" * 1000
        new = "A" * (1000 + 1999)  # Diff de 1999 caractères
        is_valid, msg = publisher._validate_diff_size(original, new)
        
        if is_valid:
            print("✓ Diff de 1999 caractères accepté")
            results.append(("Diff 1999 accepté", True))
        else:
            print(f"✗ Diff de 1999 rejeté: {msg}")
            results.append(("Diff 1999 accepté", False))
        
        # Test avec diff au seuil exact (2000 caractères)
        original = "A" * 1000
        new = "A" * (1000 + 2000)  # Diff de 2000 caractères
        is_valid, msg = publisher._validate_diff_size(original, new)
        
        if not is_valid:
            print("✓ Diff de 2000 caractères bloqué (au seuil)")
            results.append(("Diff 2000 bloqué", True))
        else:
            print(f"✗ Diff de 2000 non bloqué")
            results.append(("Diff 2000 bloqué", False))
        
        # Test avec diff au-dessus du seuil (2001 caractères)
        original = "A" * 1000
        new = "A" * (1000 + 2001)  # Diff de 2001 caractères
        is_valid, msg = publisher._validate_diff_size(original, new)
        
        if not is_valid:
            print("✓ Diff de 2001 caractères bloqué")
            results.append(("Diff 2001 bloqué", True))
        else:
            print(f"✗ Diff de 2001 non bloqué")
            results.append(("Diff 2001 bloqué", False))
        
except Exception as e:
    print(f"✗ Test seuil échoué: {e}")
    results.append(("Seuil validation", False))

# Résumé
print("\n" + "=" * 70)
print("RÉSUMÉ DES TESTS FONCTIONNELS ROBUSTES")
print("=" * 70)

passed = sum(1 for _, result in results if result)
total = len(results)

for test_name, result in results:
    status = "✓ PASS" if result else "✗ FAIL"
    print(f"{status} - {test_name}")

print(f"\nTotal: {passed}/{total} tests fonctionnels passés")

if passed == total:
    print("✅ TOUS LES TESTS FONCTIONNELS ROBUSTES SONT PASSÉS")
    exit_code = 0
else:
    print(f"⚠️  {total - passed} test(s) fonctionnel(s) échoué(s)")
    exit_code = 1