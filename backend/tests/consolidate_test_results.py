"""
Consolidate all test results into a single matrix and recalculate validation rate.

This script reads all test result JSON files and consolidates them into a single
validation matrix with: ID, scenario, expected oracle, proof, status.
"""

import json
import os
from typing import Dict, List, Any
from dataclasses import dataclass, asdict


@dataclass
class RuleValidation:
    """Single rule validation entry"""
    id: str
    rule: str
    category: str
    scenario: str
    expected_oracle: str
    actual_result: str
    proof: str
    status: str  # PASS, FAIL, PARTIAL, NOT_TESTED
    test_file: str


class TestResultsConsolidator:
    """Consolidates test results from multiple sources"""
    
    def __init__(self):
        self.validations: List[RuleValidation] = []
        
    def load_all_results(self):
        """Load all test result JSON files"""
        base_dir = os.path.dirname(__file__)
        # Go up two levels: backend/tests -> backend -> project root
        project_root = os.path.dirname(os.path.dirname(base_dir))
        
        # List of result files to load (in data/ directory)
        result_files = [
            "data/dead_link_rules_test_results.json",
            "data/dead_link_edge_cases_test_results.json",
            "data/dead_link_integration_test_results.json",
            "data/dead_link_strict_validation_test_results.json",
            "data/dead_link_retry_archive_test_results.json"
        ]
        
        for result_file in result_files:
            file_path = os.path.join(project_root, result_file)
            if os.path.exists(file_path):
                self._load_result_file(file_path, result_file)
            else:
                print(f"Warning: {result_file} not found at {file_path}")
    
    def _load_result_file(self, file_path: str, source_file: str):
        """Load a single result file"""
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        results = data.get('results', [])
        
        for result in results:
            # Extract relevant fields
            test_id = result.get('test_id', '')
            rule = result.get('rule', '')
            description = result.get('description', '')
            url = result.get('url', '')
            article_content = result.get('article_content', '')
            
            # Determine scenario
            if url:
                scenario = f"URL: {url}"
            elif article_content:
                scenario = f"Article: {article_content[:50]}..."
            else:
                scenario = description
            
            # Expected oracle - try multiple fields
            expected_oracle = (
                result.get('expected_behavior') or
                result.get('expected') or
                result.get('expected_decision') or
                result.get('expected_status') or
                ""
            )
            
            # Actual result - try multiple fields
            actual_result = (
                result.get('actual_behavior') or
                result.get('actual') or
                result.get('actual_decision') or
                result.get('actual_status') or
                ""
            )
            
            # Proof
            proof = self._format_proof(result.get('proof', {}))
            
            # Status - Normalize automatically from actual result
            passed = result.get('passed', False)
            error = result.get('error', None)
            rule = result.get('rule', '')
            description = result.get('description', '')
            actual_behavior = result.get('actual_behavior', '')
            actual_result = result.get('actual', '')
            expected_oracle = result.get('expected_behavior', result.get('expected', ''))
            
            # Check if the test is explicitly marked as NOT TESTED
            if "NOT TESTED" in rule.upper() or "NOT TESTED" in description.upper():
                status = "NOT_TESTED"
            elif error and "NOT TESTED" in error.upper():
                status = "NOT_TESTED"
            # Check if the actual result contains PARTIAL
            elif "PARTIAL" in actual_behavior.upper() or "PARTIAL" in actual_result.upper():
                status = "PARTIAL"
            elif error and "PARTIAL" in error.upper():
                status = "PARTIAL"
            # Check if the actual result contradicts the expected oracle
            elif expected_oracle and actual_behavior and expected_oracle not in actual_behavior and "not fully implemented" in actual_behavior.lower():
                status = "PARTIAL"
            elif expected_oracle and actual_result and expected_oracle not in actual_result and "not fully implemented" in actual_result.lower():
                status = "PARTIAL"
            elif passed:
                status = "PASS"
            else:
                status = "FAIL"
            
            # Determine category from test_id
            if test_id.startswith("DL-"):
                category = "HTTP Status / Redirect / Validator"
            elif test_id.startswith("EDGE-"):
                category = "Edge Cases"
            elif test_id.startswith("INT-"):
                category = "Integration"
            elif test_id.startswith("LV-"):
                category = "Link Validator"
            elif test_id.startswith("CV-"):
                category = "Content Verifier"
            elif test_id.startswith("RETRY-"):
                category = "Retry Logic"
            elif test_id.startswith("ARCH-"):
                category = "Archive Fallback"
            else:
                category = "Unknown"
            
            validation = RuleValidation(
                id=test_id,
                rule=rule,
                category=category,
                scenario=scenario,
                expected_oracle=expected_oracle,
                actual_result=actual_result,
                proof=proof,
                status=status,
                test_file=source_file
            )
            
            self.validations.append(validation)
    
    def _format_proof(self, proof_dict: Dict[str, Any]) -> str:
        """Format proof dictionary as string"""
        if not proof_dict:
            return "No proof"
        
        # Extract key fields
        key_fields = []
        for key in ['status', 'decision', 'retry_count', 'http_status_code', 'error_type', 'note']:
            if key in proof_dict:
                key_fields.append(f"{key}={proof_dict[key]}")
        
        if key_fields:
            return ", ".join(key_fields)
        
        return str(proof_dict)[:100]
    
    def calculate_statistics(self) -> Dict[str, Any]:
        """Calculate validation statistics based on unique rules"""
        total = len(self.validations)
        passed = sum(1 for v in self.validations if v.status == "PASS")
        failed = sum(1 for v in self.validations if v.status == "FAIL")
        partial = sum(1 for v in self.validations if v.status == "PARTIAL")
        not_tested = sum(1 for v in self.validations if v.status == "NOT_TESTED")
        
        # Group by unique rule ID
        rules_by_id = {}
        for v in self.validations:
            if v.id not in rules_by_id:
                rules_by_id[v.id] = []
            rules_by_id[v.id].append(v)
        
        # Total unique rules
        total_rules = len(rules_by_id)
        
        # Determine status for each unique rule
        rule_statuses = {}
        for rule_id, validations in rules_by_id.items():
            # If any test failed, the rule is FAIL
            if any(v.status == "FAIL" for v in validations):
                rule_statuses[rule_id] = "FAIL"
            # If any test is PARTIAL and none failed, the rule is PARTIAL
            elif any(v.status == "PARTIAL" for v in validations):
                rule_statuses[rule_id] = "PARTIAL"
            # If any test is NOT_TESTED and none failed/partial, the rule is NOT_TESTED
            elif any(v.status == "NOT_TESTED" for v in validations):
                rule_statuses[rule_id] = "NOT_TESTED"
            # If all tests passed, the rule is PASS
            elif all(v.status == "PASS" for v in validations):
                rule_statuses[rule_id] = "PASS"
            else:
                rule_statuses[rule_id] = "UNKNOWN"
        
        # Count by status
        rules_passed = sum(1 for s in rule_statuses.values() if s == "PASS")
        rules_failed = sum(1 for s in rule_statuses.values() if s == "FAIL")
        rules_partial = sum(1 for s in rule_statuses.values() if s == "PARTIAL")
        rules_not_tested = sum(1 for s in rule_statuses.values() if s == "NOT_TESTED")
        
        # Validation rate (fully validated / total rules)
        validation_rate = (rules_passed / total_rules * 100) if total_rules > 0 else 0
        
        return {
            'total_tests': total,
            'passed': passed,
            'failed': failed,
            'partial': partial,
            'not_tested': not_tested,
            'total_rules': total_rules,
            'rules_passed': rules_passed,
            'rules_failed': rules_failed,
            'rules_partial': rules_partial,
            'rules_not_tested': rules_not_tested,
            'validation_rate': f"{validation_rate:.1f}%",
            'rule_statuses': rule_statuses
        }
    
    def generate_markdown_matrix(self) -> str:
        """Generate markdown validation matrix"""
        stats = self.calculate_statistics()
        
        md = "# DEAD LINK MODULE - MATRICE DE VALIDATION CONSOLIDÉE\n\n"
        md += f"**Date de génération :** Automatique\n\n"
        md += f"**Total de règles identifiées :** {stats['total_rules']}\n\n"
        md += "## Statistiques (au niveau des règles)\n\n"
        md += f"| Métrique | Count | Percentage |\n"
        md += f"|---------|-------|------------|\n"
        md += f"| Total de tests exécutés | {stats['total_tests']} | - |\n"
        md += f"| 🟢 Règles entièrement validées (PASS) | {stats['rules_passed']} | {(stats['rules_passed']/stats['total_rules']*100):.1f}% |\n"
        md += f"| 🔴 Règles en échec (FAIL) | {stats['rules_failed']} | {(stats['rules_failed']/stats['total_rules']*100):.1f}% |\n"
        md += f"| 🟠 Règles partiellement testées (PARTIAL) | {stats['rules_partial']} | {(stats['rules_partial']/stats['total_rules']*100):.1f}% |\n"
        md += f"| ⚪ Règles non testées (NOT_TESTED) | {stats['rules_not_tested']} | {(stats['rules_not_tested']/stats['total_rules']*100):.1f}% |\n"
        md += f"| **Taux de validation réel** | - | **{stats['validation_rate']}** |\n\n"
        
        md += "## Matrice de Validation (une ligne par règle unique)\n\n"
        md += "| ID | Règle | Catégorie | Scénario | Oracle attendu | Résultat réel | Preuve | Statut | Source |\n"
        md += "|----|-------|-----------|----------|----------------|---------------|--------|--------|--------|\n"
        
        # Group by unique rule ID and take the first validation for each
        rules_by_id = {}
        for v in self.validations:
            if v.id not in rules_by_id:
                rules_by_id[v.id] = v
        
        # Sort by ID
        sorted_rules = sorted(rules_by_id.values(), key=lambda x: x.id)
        
        for v in sorted_rules:
            # Get the rule status from statistics
            rule_status = stats['rule_statuses'].get(v.id, "UNKNOWN")
            status_icon = {
                "PASS": "🟢",
                "FAIL": "🔴",
                "PARTIAL": "🟠",
                "NOT_TESTED": "⚪",
                "UNKNOWN": "❓"
            }.get(rule_status, "❓")
            
            scenario = (v.scenario[:30] + "...") if v.scenario and len(v.scenario) > 30 else (v.scenario or "")
            expected = (v.expected_oracle[:30] + "...") if v.expected_oracle and len(v.expected_oracle) > 30 else (v.expected_oracle or "")
            actual = (v.actual_result[:30] + "...") if v.actual_result and len(v.actual_result) > 30 else (v.actual_result or "")
            proof = (v.proof[:30] + "...") if v.proof and len(v.proof) > 30 else (v.proof or "")
            
            md += f"| {v.id} | {v.rule} | {v.category} | {scenario} | {expected} | {actual} | {proof} | {status_icon} {rule_status} | {v.test_file} |\n"
        
        return md
    
    def generate_detailed_matrix(self) -> str:
        """Generate detailed validation matrix with full information"""
        stats = self.calculate_statistics()
        
        md = "# DEAD LINK MODULE - MATRICE DE VALIDATION DÉTAILLÉE\n\n"
        md += f"**Total de règles identifiées :** {stats['total_rules']}\n"
        md += f"**Taux de validation :** {stats['validation_rate']}\n\n"
        
        # Group by category
        categories = {}
        for v in self.validations:
            if v.category not in categories:
                categories[v.category] = []
            categories[v.category].append(v)
        
        for category, validations in categories.items():
            md += f"\n## {category}\n\n"
            md += "| ID | Règle | Scénario | Oracle attendu | Résultat réel | Preuve | Statut |\n"
            md += "|----|-------|----------|----------------|---------------|--------|--------|\n"
            
            sorted_validations = sorted(validations, key=lambda x: x.id)
            
            for v in sorted_validations:
                status_icon = {
                    "PASS": "🟢",
                    "FAIL": "🔴",
                    "PARTIAL": "🟠",
                    "NOT_TESTED": "⚪"
                }.get(v.status, "❓")
                
                md += f"| {v.id} | {v.rule} | {v.scenario or ''} | {v.expected_oracle or ''} | {v.actual_result or ''} | {v.proof or ''} | {status_icon} {v.status} |\n"
        
        return md
    
    def save_results(self, output_file: str):
        """Save consolidated results"""
        with open(output_file, 'w') as f:
            json.dump({
                'statistics': self.calculate_statistics(),
                'validations': [asdict(v) for v in self.validations]
            }, f, indent=2)
        
        print(f"Consolidated results saved to: {output_file}")


def main():
    """Main entry point"""
    print("Consolidating test results...")
    
    consolidator = TestResultsConsolidator()
    consolidator.load_all_results()
    
    print(f"Loaded {len(consolidator.validations)} validation entries")
    
    # Calculate statistics
    stats = consolidator.calculate_statistics()
    print("\nStatistics:")
    print(f"  Total rules: {stats['total_rules']}")
    print(f"  Rules passed: {stats['rules_passed']}")
    print(f"  Rules failed: {stats['rules_failed']}")
    print(f"  Rules partial: {stats['rules_partial']}")
    print(f"  Rules not tested: {stats['rules_not_tested']}")
    print(f"  Validation rate: {stats['validation_rate']}")
    print(f"  Total tests: {stats['total_tests']}")
    print(f"  Test PASS: {stats['passed']}")
    print(f"  Test FAIL: {stats['failed']}")
    print(f"  Test PARTIAL: {stats['partial']}")
    print(f"  Test NOT_TESTED: {stats['not_tested']}")
    
    # Save consolidated results
    output_file = "data/dead_link_consolidated_results.json"
    consolidator.save_results(output_file)
    
    # Generate markdown matrix
    md_matrix = consolidator.generate_markdown_matrix()
    md_file = "DEAD_LINK_MODULE_CONSOLIDATED_MATRIX.md"
    with open(md_file, 'w', encoding='utf-8') as f:
        f.write(md_matrix)
    print(f"Markdown matrix saved to: {md_file}")
    
    # Generate detailed matrix
    md_detailed = consolidator.generate_detailed_matrix()
    md_detailed_file = "DEAD_LINK_MODULE_DETAILED_MATRIX.md"
    with open(md_detailed_file, 'w', encoding='utf-8') as f:
        f.write(md_detailed)
    print(f"Detailed matrix saved to: {md_detailed_file}")
    
    return stats


if __name__ == '__main__':
    stats = main()
    print(f"\nFinal validation rate: {stats['validation_rate']}")
