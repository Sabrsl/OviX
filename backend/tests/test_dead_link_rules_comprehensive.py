"""
Comprehensive Functional Test for Dead Link Module Rules

This script tests ALL rules in the Dead Link module by executing real cases
and verifying that the expected rule is triggered.

Test methodology:
1. Create a test case with a specific URL
2. Execute the Dead Link analyzer on the case
3. Capture the actual result (status, decision, logs)
4. Compare with expected result
5. Record PASS/FAIL with proof
"""

import sys
import os
import time
import json
from typing import Dict, List, Any
from dataclasses import dataclass, asdict

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from wikipedia_maintenance.utils.link_checker import LinkChecker, LinkStatus
from wikipedia_maintenance.utils.link_validator import LinkValidator, RepairDecision
from wikipedia_maintenance.utils.redirect_finder import RedirectFinder, RedirectDecision
from wikipedia_maintenance.utils.content_verifier import ContentVerifier, ContentMatch


@dataclass
class TestCase:
    """Test case for a specific rule"""
    id: str
    rule: str
    description: str
    url: str
    expected_status: str
    expected_decision: str = None
    should_apply: bool = True
    category: str = "http_status"


@dataclass
class TestResult:
    """Result of a test case"""
    test_id: str
    rule: str
    url: str
    expected_status: str
    expected_decision: str
    actual_status: str
    actual_decision: str
    should_apply: bool
    passed: bool
    proof: Dict[str, Any]
    error: str = None


class DeadLinkRulesTester:
    """Comprehensive tester for Dead Link module rules"""
    
    def __init__(self):
        self.link_checker = LinkChecker(timeout=10, max_retries=3)
        self.link_validator = LinkValidator(link_checker=self.link_checker)
        self.redirect_finder = RedirectFinder(timeout=10)
        self.content_verifier = ContentVerifier(timeout=15)
        self.results: List[TestResult] = []
        
    def run_all_tests(self) -> List[TestResult]:
        """Run all test cases"""
        test_cases = self._generate_test_cases()
        
        print(f"\n{'='*80}")
        print(f"COMPREHENSIVE DEAD LINK MODULE RULES TEST")
        print(f"{'='*80}")
        print(f"Total test cases: {len(test_cases)}")
        print(f"{'='*80}\n")
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n[{i}/{len(test_cases)}] Testing: {test_case.id} - {test_case.rule}")
            print(f"  Description: {test_case.description}")
            print(f"  URL: {test_case.url}")
            print(f"  Expected: {test_case.expected_status}")
            
            result = self._run_test_case(test_case)
            self.results.append(result)
            
            status_icon = "🟢 PASS" if result.passed else "🔴 FAIL"
            print(f"  Result: {status_icon}")
            
            if result.error:
                print(f"  Error: {result.error}")
            
            if not result.passed:
                print(f"  Expected: {result.expected_status}")
                print(f"  Actual: {result.actual_status}")
                if result.expected_decision:
                    print(f"  Expected Decision: {result.expected_decision}")
                    print(f"  Actual Decision: {result.actual_decision}")
            
            # Small delay to avoid overwhelming the test server
            time.sleep(0.1)
        
        return self.results
    
    def _generate_test_cases(self) -> List[TestCase]:
        """Generate all test cases for all rules"""
        base_url = "http://localhost:5000/test"
        
        test_cases = [
            # ===== HTTP STATUS CODE RULES =====
            # Healthy links (2xx, 3xx)
            TestCase(
                id="DL-001",
                rule="200 → HEALTHY",
                description="HTTP 200 should be classified as HEALTHY",
                url=f"{base_url}/200",
                expected_status="healthy",
                should_apply=True,
                category="http_status"
            ),
            TestCase(
                id="DL-002",
                rule="301 → HEALTHY (redirect)",
                description="HTTP 301 redirect should be classified as HEALTHY",
                url=f"{base_url}/301",
                expected_status="healthy",
                should_apply=True,
                category="http_status"
            ),
            TestCase(
                id="DL-003",
                rule="302 → HEALTHY (redirect)",
                description="HTTP 302 redirect should be classified as HEALTHY",
                url=f"{base_url}/302",
                expected_status="healthy",
                should_apply=True,
                category="http_status"
            ),
            TestCase(
                id="DL-004",
                rule="307 → HEALTHY (redirect)",
                description="HTTP 307 redirect should be classified as HEALTHY",
                url=f"{base_url}/307",
                expected_status="healthy",
                should_apply=True,
                category="http_status"
            ),
            TestCase(
                id="DL-005",
                rule="308 → HEALTHY (redirect)",
                description="HTTP 308 redirect should be classified as HEALTHY",
                url=f"{base_url}/308",
                expected_status="healthy",
                should_apply=True,
                category="http_status"
            ),
            
            # Dead links (4xx specific codes)
            TestCase(
                id="DL-006",
                rule="404 → DEAD",
                description="HTTP 404 should be classified as DEAD",
                url=f"{base_url}/404",
                expected_status="dead",
                should_apply=True,
                category="http_status"
            ),
            TestCase(
                id="DL-007",
                rule="410 → DEAD",
                description="HTTP 410 should be classified as DEAD",
                url=f"{base_url}/410",
                expected_status="dead",
                should_apply=True,
                category="http_status"
            ),
            
            # Review required (ambiguous 4xx codes)
            TestCase(
                id="DL-008",
                rule="400 → REVIEW_REQUIRED",
                description="HTTP 400 should be classified as REVIEW_REQUIRED",
                url=f"{base_url}/400",
                expected_status="review_required",
                should_apply=True,
                category="http_status"
            ),
            TestCase(
                id="DL-009",
                rule="401 → REVIEW_REQUIRED",
                description="HTTP 401 should be classified as REVIEW_REQUIRED",
                url=f"{base_url}/401",
                expected_status="review_required",
                should_apply=True,
                category="http_status"
            ),
            TestCase(
                id="DL-010",
                rule="403 → REVIEW_REQUIRED",
                description="HTTP 403 should be classified as REVIEW_REQUIRED",
                url=f"{base_url}/403",
                expected_status="review_required",
                should_apply=True,
                category="http_status"
            ),
            
            # Rate limiting
            TestCase(
                id="DL-011",
                rule="429 → RATE_LIMITED",
                description="HTTP 429 should be classified as RATE_LIMITED",
                url=f"{base_url}/429",
                expected_status="rate_limited",
                should_apply=True,
                category="http_status"
            ),
            
            # Temporary errors (5xx codes)
            TestCase(
                id="DL-012",
                rule="408 → TEMPORARY_ERROR",
                description="HTTP 408 should be classified as TEMPORARY_ERROR",
                url=f"{base_url}/408",
                expected_status="temporary_error",
                should_apply=True,
                category="http_status"
            ),
            TestCase(
                id="DL-013",
                rule="500 → TEMPORARY_ERROR",
                description="HTTP 500 should be classified as TEMPORARY_ERROR",
                url=f"{base_url}/500",
                expected_status="temporary_error",
                should_apply=True,
                category="http_status"
            ),
            TestCase(
                id="DL-014",
                rule="502 → TEMPORARY_ERROR",
                description="HTTP 502 should be classified as TEMPORARY_ERROR",
                url=f"{base_url}/502",
                expected_status="temporary_error",
                should_apply=True,
                category="http_status"
            ),
            TestCase(
                id="DL-015",
                rule="503 → TEMPORARY_ERROR",
                description="HTTP 503 should be classified as TEMPORARY_ERROR",
                url=f"{base_url}/503",
                expected_status="temporary_error",
                should_apply=True,
                category="http_status"
            ),
            TestCase(
                id="DL-016",
                rule="504 → TEMPORARY_ERROR",
                description="HTTP 504 should be classified as TEMPORARY_ERROR",
                url=f"{base_url}/504",
                expected_status="temporary_error",
                should_apply=True,
                category="http_status"
            ),
            
            # ===== REDIRECT RULES =====
            TestCase(
                id="DL-017",
                rule="Same domain redirect → HEALTHY",
                description="Redirect to same domain should be HEALTHY (link checker follows redirects)",
                url=f"{base_url}/301",
                expected_status="healthy",
                should_apply=True,
                category="redirect"
            ),
            TestCase(
                id="DL-018",
                rule="Redirect chain → HEALTHY",
                description="Redirect chain should be HEALTHY (link checker follows redirects)",
                url=f"{base_url}/redirect_chain",
                expected_status="healthy",
                should_apply=True,
                category="redirect"
            ),
            TestCase(
                id="DL-019",
                rule="Different path redirect → HEALTHY",
                description="Redirect to different path on same domain should be HEALTHY",
                url=f"{base_url}/redirect_different_path",
                expected_status="healthy",
                should_apply=True,
                category="redirect"
            ),
            
            # ===== LINK VALIDATOR RULES =====
            TestCase(
                id="DL-021",
                rule="HEALTHY → NO_ACTION",
                description="Healthy link should result in NO_ACTION decision",
                url=f"{base_url}/200",
                expected_status="healthy",
                expected_decision="no_action",
                should_apply=True,
                category="validator"
            ),
            TestCase(
                id="DL-022",
                rule="TEMPORARY_ERROR → NO_ACTION",
                description="Temporary error should result in NO_ACTION decision",
                url=f"{base_url}/503",
                expected_status="temporary_error",
                expected_decision="no_action",
                should_apply=True,
                category="validator"
            ),
            TestCase(
                id="DL-023",
                rule="RATE_LIMITED → NO_ACTION",
                description="Rate limited should result in NO_ACTION decision",
                url=f"{base_url}/429",
                expected_status="rate_limited",
                expected_decision="no_action",
                should_apply=True,
                category="validator"
            ),
            TestCase(
                id="DL-024",
                rule="REVIEW_REQUIRED → REPAIR_REJECTED",
                description="Review required should result in REPAIR_REJECTED decision",
                url=f"{base_url}/403",
                expected_status="review_required",
                expected_decision="repair_rejected",
                should_apply=True,
                category="validator"
            ),
            TestCase(
                id="DL-025",
                rule="DEAD without redirect → REPAIR_REJECTED",
                description="Dead link without redirect should result in REPAIR_REJECTED (insufficient proofs)",
                url=f"{base_url}/404",
                expected_status="dead",
                expected_decision="repair_rejected",
                should_apply=True,
                category="validator"
            ),
            
            # ===== CONTENT VERIFICATION RULES =====
            TestCase(
                id="DL-026",
                rule="Same content → STRONG_MATCH",
                description="Same content should result in STRONG_MATCH",
                url=f"{base_url}/content_match",
                expected_status="healthy",
                expected_decision="strong_match",
                should_apply=True,
                category="content"
            ),
            TestCase(
                id="DL-027",
                rule="Different content → WEAK_MATCH",
                description="Different content with same domain should result in WEAK_MATCH (only SAME_SOURCE proof)",
                url=f"{base_url}/content_different",
                expected_status="healthy",
                expected_decision="weak_match",
                should_apply=True,
                category="content"
            ),
            
            # ===== NEGATIVE TESTS =====
            TestCase(
                id="DL-028",
                rule="404 should NOT be HEALTHY",
                description="HTTP 404 should NOT be classified as HEALTHY",
                url=f"{base_url}/404",
                expected_status="dead",
                should_apply=False,
                category="negative"
            ),
            TestCase(
                id="DL-029",
                rule="403 should NOT be DEAD",
                description="HTTP 403 should NOT be classified as DEAD",
                url=f"{base_url}/403",
                expected_status="review_required",
                should_apply=False,
                category="negative"
            ),
            TestCase(
                id="DL-030",
                rule="429 should NOT be DEAD",
                description="HTTP 429 should NOT be classified as DEAD",
                url=f"{base_url}/429",
                expected_status="rate_limited",
                should_apply=False,
                category="negative"
            ),
            TestCase(
                id="DL-031",
                rule="503 should NOT be DEAD",
                description="HTTP 503 should NOT be classified as DEAD",
                url=f"{base_url}/503",
                expected_status="temporary_error",
                should_apply=False,
                category="negative"
            ),
        ]
        
        return test_cases
    
    def _run_test_case(self, test_case: TestCase) -> TestResult:
        """Run a single test case"""
        proof = {}
        actual_status = None
        actual_decision = None
        error = None
        passed = False
        
        try:
            # Step 1: Check link status
            check_result = self.link_checker.check_link(test_case.url)
            actual_status = check_result.status.value
            proof['link_check'] = {
                'status': actual_status,
                'http_status_code': check_result.http_status_code,
                'error_type': check_result.error_type,
                'retry_count': check_result.retry_count,
                'confidence': check_result.confidence
            }
            
            # Step 2: Check redirect if applicable
            if test_case.category in ['redirect', 'validator']:
                redirect_result = self.redirect_finder.find_redirect(test_case.url)
                actual_decision = redirect_result.decision.value
                proof['redirect'] = {
                    'decision': actual_decision,
                    'redirected_url': redirect_result.redirected_url,
                    'http_status_code': redirect_result.http_status_code,
                    'reason': redirect_result.reason
                }
            
            # Step 3: Validate repair decision if applicable
            if test_case.category in ['validator', 'content']:
                repair_result = self.link_validator.validate_repair(
                    check_result=check_result,
                    redirect_result=self.redirect_finder.find_redirect(test_case.url) if test_case.category == 'validator' else None
                )
                actual_decision = repair_result.decision.value
                proof['validator'] = {
                    'decision': actual_decision,
                    'reason': repair_result.reason,
                    'replacement_url': repair_result.replacement_url
                }
            
            # Step 4: Content verification if applicable
            if test_case.category == 'content':
                content_result = self.content_verifier.verify_same_resource(
                    test_case.url,
                    f"{test_case.url}_different" if "different" in test_case.url else test_case.url
                )
                actual_decision = content_result.decision.value
                proof['content'] = {
                    'decision': actual_decision,
                    'title_match': content_result.title_match,
                    'domain_match': content_result.domain_match,
                    'path_similarity': content_result.path_similarity,
                    'reason': content_result.reason
                }
            
            # Step 5: Determine pass/fail
            if test_case.should_apply:
                # Positive test: rule should apply
                status_match = actual_status == test_case.expected_status
                decision_match = (test_case.expected_decision is None or 
                                actual_decision == test_case.expected_decision)
                passed = status_match and decision_match
            else:
                # Negative test: rule should NOT apply
                # For negative tests, we just check that the status is NOT the opposite
                status_match = actual_status == test_case.expected_status
                passed = status_match
            
        except Exception as e:
            error = str(e)
            proof['exception'] = error
            passed = False
        
        return TestResult(
            test_id=test_case.id,
            rule=test_case.rule,
            url=test_case.url,
            expected_status=test_case.expected_status,
            expected_decision=test_case.expected_decision,
            actual_status=actual_status,
            actual_decision=actual_decision,
            should_apply=test_case.should_apply,
            passed=passed,
            proof=proof,
            error=error
        )
    
    def generate_validation_table(self) -> str:
        """Generate validation table in markdown format"""
        table = "| ID     | Règle                 | Cas testé | Règle devrait s'appliquer ? | Résultat attendu | Résultat réel | Statut  |\n"
        table += "| ------ | --------------------- | --------- | --------------------------- | ---------------- | ------------- | ------- |\n"
        
        for result in self.results:
            status_icon = "🟢 PASS" if result.passed else "🔴 FAIL"
            should_apply = "Oui" if result.should_apply else "Non"
            
            table += f"| {result.test_id} | {result.rule} | {result.url} | {should_apply} | {result.expected_status} | {result.actual_status} | {status_icon} |\n"
        
        return table
    
    def generate_summary(self) -> Dict[str, Any]:
        """Generate test summary"""
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        failed = total - passed
        
        by_category = {}
        for result in self.results:
            category = result.proof.get('link_check', {}).get('category', 'unknown')
            if category not in by_category:
                by_category[category] = {'total': 0, 'passed': 0, 'failed': 0}
            by_category[category]['total'] += 1
            if result.passed:
                by_category[category]['passed'] += 1
            else:
                by_category[category]['failed'] += 1
        
        return {
            'total_tests': total,
            'passed': passed,
            'failed': failed,
            'success_rate': f"{(passed/total*100):.1f}%" if total > 0 else "0%",
            'by_category': by_category
        }
    
    def generate_detailed_report(self) -> str:
        """Generate detailed report with failed tests"""
        report = "\n" + "="*80 + "\n"
        report += "DETAILED REPORT\n"
        report += "="*80 + "\n\n"
        
        summary = self.generate_summary()
        report += f"Total tests: {summary['total_tests']}\n"
        report += f"Passed: {summary['passed']}\n"
        report += f"Failed: {summary['failed']}\n"
        report += f"Success rate: {summary['success_rate']}\n\n"
        
        failed_tests = [r for r in self.results if not r.passed]
        if failed_tests:
            report += "="*80 + "\n"
            report += "FAILED TESTS DETAILS\n"
            report += "="*80 + "\n\n"
            
            for result in failed_tests:
                report += f"Test ID: {result.test_id}\n"
                report += f"Rule: {result.rule}\n"
                report += f"URL: {result.url}\n"
                report += f"Expected status: {result.expected_status}\n"
                report += f"Actual status: {result.actual_status}\n"
                if result.expected_decision:
                    report += f"Expected decision: {result.expected_decision}\n"
                    report += f"Actual decision: {result.actual_decision}\n"
                if result.error:
                    report += f"Error: {result.error}\n"
                report += f"Proof: {json.dumps(result.proof, indent=2)}\n"
                report += "-"*80 + "\n\n"
        
        return report


def main():
    """Main entry point"""
    print("\n" + "="*80)
    print("DEAD LINK MODULE - COMPREHENSIVE RULES TEST")
    print("="*80)
    print("\nPrerequisite: Start the test server first:")
    print("  python backend/tests/test_http_server.py")
    print("\nPress Enter to continue or Ctrl+C to cancel...")
    input()
    
    tester = DeadLinkRulesTester()
    results = tester.run_all_tests()
    
    # Generate reports
    validation_table = tester.generate_validation_table()
    detailed_report = tester.generate_detailed_report()
    summary = tester.generate_summary()
    
    # Print validation table
    print("\n" + "="*80)
    print("VALIDATION TABLE")
    print("="*80)
    print(validation_table)
    
    # Print detailed report
    print(detailed_report)
    
    # Save results to file
    output_file = "dead_link_rules_test_results.json"
    with open(output_file, 'w') as f:
        json.dump({
            'summary': summary,
            'validation_table': validation_table,
            'detailed_report': detailed_report,
            'results': [asdict(r) for r in results]
        }, f, indent=2)
    
    print(f"\nResults saved to: {output_file}")
    
    return summary['failed'] == 0


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
