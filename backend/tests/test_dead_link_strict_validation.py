"""
Strict Validation Tests for ContentVerifier and LinkValidator

This script tests the actual decision outputs (not just status):
- ContentVerifier: STRONG_MATCH, WEAK_MATCH, NO_MATCH, INDETERMINATE
- LinkValidator: NO_ACTION, DEAD_NO_REPLACEMENT, REPLACEMENT_CONFIRMED, REPAIR_REJECTED, REPAIR_DIFF_REJECTED
"""

import sys
import os
import json
from typing import Dict, List, Any
from dataclasses import dataclass, asdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from wikipedia_maintenance.utils.link_checker import LinkChecker, LinkStatus, LinkCheckResult
from wikipedia_maintenance.utils.link_validator import LinkValidator, RepairDecision, RepairResult
from wikipedia_maintenance.utils.content_verifier import ContentVerifier, ContentMatch, ContentVerificationResult


@dataclass
class StrictTestCase:
    """Strict test case"""
    id: str
    rule: str
    description: str
    input_data: Dict[str, Any]
    expected_decision: str
    expected_status: str = None


@dataclass
class StrictTestResult:
    """Result of strict test"""
    test_id: str
    rule: str
    expected_decision: str
    actual_decision: str
    expected_status: str
    actual_status: str
    passed: bool
    proof: Dict[str, Any]
    error: str = None


class StrictValidatorTester:
    """Strict tester for validator decision outputs"""
    
    def __init__(self):
        self.link_checker = LinkChecker(timeout=10, max_retries=3)
        self.link_validator = LinkValidator(link_checker=self.link_checker)
        self.content_verifier = ContentVerifier(timeout=15)
        self.results: List[StrictTestResult] = []
        
    def run_all_tests(self) -> List[StrictTestResult]:
        """Run all strict validation tests"""
        test_cases = self._generate_strict_tests()
        
        print(f"\n{'='*80}")
        print(f"DEAD LINK MODULE - STRICT VALIDATION TESTS")
        print(f"{'='*80}")
        print(f"Total strict tests: {len(test_cases)}")
        print(f"{'='*80}\n")
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n[{i}/{len(test_cases)}] Testing: {test_case.id} - {test_case.rule}")
            print(f"  Description: {test_case.description}")
            print(f"  Expected decision: {test_case.expected_decision}")
            
            result = self._run_strict_test(test_case)
            self.results.append(result)
            
            status_icon = "🟢 PASS" if result.passed else "🔴 FAIL"
            print(f"  Result: {status_icon}")
            
            if result.error:
                print(f"  Error: {result.error}")
            
            if not result.passed:
                print(f"  Expected decision: {result.expected_decision}")
                print(f"  Actual decision: {result.actual_decision}")
                if result.expected_status:
                    print(f"  Expected status: {result.expected_status}")
                    print(f"  Actual status: {result.actual_status}")
        
        return self.results
    
    def _generate_strict_tests(self) -> List[StrictTestCase]:
        """Generate strict test cases"""
        base_url = "http://localhost:5000/test"
        
        test_cases = [
            # ===== LINK VALIDATOR DECISION TESTS =====
            StrictTestCase(
                id="LV-001",
                rule="HEALTHY → NO_ACTION",
                description="Healthy link should result in NO_ACTION decision",
                input_data={
                    "url": f"{base_url}/200",
                    "check_result": None  # Will be fetched
                },
                expected_decision="no_action",
                expected_status="healthy"
            ),
            
            StrictTestCase(
                id="LV-002",
                rule="TEMPORARY_ERROR → NO_ACTION",
                description="Temporary error should result in NO_ACTION decision",
                input_data={
                    "url": f"{base_url}/503",
                },
                expected_decision="no_action",
                expected_status="temporary_error"
            ),
            
            StrictTestCase(
                id="LV-003",
                rule="RATE_LIMITED → NO_ACTION",
                description="Rate limited should result in NO_ACTION decision",
                input_data={
                    "url": f"{base_url}/429",
                },
                expected_decision="no_action",
                expected_status="rate_limited"
            ),
            
            StrictTestCase(
                id="LV-004",
                rule="REVIEW_REQUIRED → REPAIR_REJECTED",
                description="Review required should result in REPAIR_REJECTED decision",
                input_data={
                    "url": f"{base_url}/403",
                },
                expected_decision="repair_rejected",
                expected_status="review_required"
            ),
            
            StrictTestCase(
                id="LV-005",
                rule="DEAD without redirect → REPAIR_REJECTED",
                description="Dead link without redirect should result in REPAIR_REJECTED (insufficient proofs)",
                input_data={
                    "url": f"{base_url}/404",
                },
                expected_decision="repair_rejected",
                expected_status="dead"
            ),
            
            # ===== CONTENT VERIFIER DECISION TESTS =====
            StrictTestCase(
                id="CV-001",
                rule="Same content → STRONG_MATCH",
                description="Same content should result in STRONG_MATCH decision",
                input_data={
                    "original_url": f"{base_url}/content_match",
                    "candidate_url": f"{base_url}/content_match",
                },
                expected_decision="strong_match"
            ),
            
            StrictTestCase(
                id="CV-002",
                rule="Different content same domain → WEAK_MATCH",
                description="Different content with same domain should result in WEAK_MATCH",
                input_data={
                    "original_url": f"{base_url}/content_match",
                    "candidate_url": f"{base_url}/content_different",
                },
                expected_decision="weak_match"
            ),
            
            StrictTestCase(
                id="CV-003",
                rule="Different domain → NO_MATCH",
                description="Different domain should result in NO_MATCH decision",
                input_data={
                    "original_url": f"{base_url}/content_match",
                    "candidate_url": "https://example.com/content",
                },
                expected_decision="no_match"
            ),
        ]
        
        return test_cases
    
    def _run_strict_test(self, test_case: StrictTestCase) -> StrictTestResult:
        """Run a single strict test"""
        proof = {}
        actual_decision = ""
        actual_status = ""
        error = None
        passed = False
        
        try:
            if test_case.id.startswith("LV-"):
                # Link Validator test
                url = test_case.input_data["url"]
                check_result = self.link_checker.check_link(url)
                actual_status = check_result.status.value
                
                repair_result = self.link_validator.validate_repair(
                    check_result=check_result,
                    redirect_result=None
                )
                actual_decision = repair_result.decision.value
                
                proof['link_check'] = {
                    'status': actual_status,
                    'http_status_code': check_result.http_status_code,
                    'error_type': check_result.error_type
                }
                proof['validator'] = {
                    'decision': actual_decision,
                    'reason': repair_result.reason,
                    'replacement_url': repair_result.replacement_url
                }
                
                passed = (actual_decision == test_case.expected_decision and
                         (test_case.expected_status is None or actual_status == test_case.expected_status))
                
            elif test_case.id.startswith("CV-"):
                # Content Verifier test
                original_url = test_case.input_data["original_url"]
                candidate_url = test_case.input_data["candidate_url"]
                
                content_result = self.content_verifier.verify_same_resource(
                    original_url=original_url,
                    candidate_url=candidate_url
                )
                actual_decision = content_result.decision.value
                
                proof['content'] = {
                    'decision': actual_decision,
                    'title_match': content_result.title_match,
                    'domain_match': content_result.domain_match,
                    'path_similarity': content_result.path_similarity,
                    'content_similarity': content_result.content_similarity,
                    'reason': content_result.reason
                }
                
                passed = actual_decision == test_case.expected_decision
                
        except Exception as e:
            error = str(e)
            proof['exception'] = error
            passed = False
        
        return StrictTestResult(
            test_id=test_case.id,
            rule=test_case.rule,
            expected_decision=test_case.expected_decision,
            actual_decision=actual_decision,
            expected_status=test_case.expected_status or "",
            actual_status=actual_status,
            passed=passed,
            proof=proof,
            error=error
        )
    
    def generate_validation_table(self) -> str:
        """Generate validation table in markdown format"""
        table = "| ID     | Règle                 | Exécution réelle | Décision attendue | Décision réelle | Statut attendu | Statut réel | Statut  |\n"
        table += "| ------ | --------------------- | ---------------- | ---------------- | --------------- | ------------- | ----------- | ------- |\n"
        
        for result in self.results:
            status_icon = "🟢 PASS" if result.passed else "🔴 FAIL"
            
            table += f"| {result.test_id} | {result.rule} | Validator/Verifier | {result.expected_decision} | {result.actual_decision} | {result.expected_status} | {result.actual_status} | {status_icon} |\n"
        
        return table
    
    def generate_summary(self) -> Dict[str, Any]:
        """Generate test summary"""
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        failed = total - passed
        
        return {
            'total_tests': total,
            'passed': passed,
            'failed': failed,
            'success_rate': f"{(passed/total*100):.1f}%" if total > 0 else "0%"
        }


def main():
    """Main entry point"""
    print("\n" + "="*80)
    print("DEAD LINK MODULE - STRICT VALIDATION TESTS")
    print("="*80)
    print("\nPrerequisite: Start the test server first:")
    print("  python backend/tests/test_http_server.py")
    print("\nPress Enter to continue or Ctrl+C to cancel...")
    input()
    
    tester = StrictValidatorTester()
    results = tester.run_all_tests()
    
    # Generate reports
    validation_table = tester.generate_validation_table()
    summary = tester.generate_summary()
    
    # Print validation table
    print("\n" + "="*80)
    print("STRICT VALIDATION TABLE")
    print("="*80)
    print(validation_table)
    
    # Print summary
    print("\n" + "="*80)
    print("STRICT VALIDATION SUMMARY")
    print("="*80)
    print(f"Total tests: {summary['total_tests']}")
    print(f"Passed: {summary['passed']}")
    print(f"Failed: {summary['failed']}")
    print(f"Success rate: {summary['success_rate']}")
    
    # Save results to file
    output_file = "dead_link_strict_validation_test_results.json"
    with open(output_file, 'w') as f:
        json.dump({
            'summary': summary,
            'validation_table': validation_table,
            'results': [asdict(r) for r in results]
        }, f, indent=2)
    
    print(f"\nResults saved to: {output_file}")
    
    return summary['failed'] == 0


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
