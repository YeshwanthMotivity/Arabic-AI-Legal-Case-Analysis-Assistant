"""
Classification Validation Engine for Issue 2
Tests and validates case classification accuracy
"""

import json
import logging
from typing import Dict, List, Any
import os
from classification_engine import classifier, CASE_TYPES

logger = logging.getLogger(__name__)

class ClassificationValidator:
    """Validates classification accuracy and confidence calibration"""
    
    def __init__(self):
        self.test_cases = self._load_test_cases()
        self.results = {
            "total": 0,
            "correct": 0,
            "failures": [],
            "by_category": {},
            "confidence_analysis": {}
        }
    
    def _load_test_cases(self) -> List[Dict[str, Any]]:
        """Load test cases for validation"""
        # Commercial contract dispute test cases
        test_cases = [
            {
                "id": "commercial_001",
                "category": "commercial_dispute",
                "text": """
                نزاع حول عقد توريد بضائع بين الشركة أ والشركة ب.
                التاريخ: 2024-01-15
                الطرف الأول: شركة النجم للتجارة (المشتري)
                الطرف الثاني: شركة الخليج للتوريد (الموردة)
                
                موضوع النزاع: عدم تنفيذ بنود العقد المتفق عليه بشأن توريد 500 طن من مواد البناء
                وعدم الالتزام بتواريخ التسليم المحددة في العقد.
                
                قيمة العقد: 250,000 ريال
                المطالبات: تعويض عن التأخير وفسخ العقد
                """,
                "expected": "commercial_dispute"
            },
            {
                "id": "commercial_002",
                "category": "commercial_dispute",
                "text": """
                كمبيالة معطلة بين الشركة الأولى والثانية.
                المبلغ: 100,000 ريال
                تاريخ الاستحقاق: 2024-06-30
                
                المشتكي يطالب بسداد قيمة الكمبيالة المستحقة.
                """,
                "expected": "commercial_dispute"
            },
            {
                "id": "labor_001",
                "category": "labor_dispute",
                "text": """
                طلب نقض حكم فصل تعسفي.
                الموظف: محمد علي أحمد
                الشركة: شركة الأمل للخدمات
                
                تفاصيل القضية: تم فصله من العمل بدون سبب وبدون إنذار مسبق.
                المطالبات:
                - راتب الفصل الفوري
                - مكافأة نهاية الخدمة (10 سنوات خدمة)
                - بدل الإجازات المستحقة (45 يوم)
                - تعويض عن الفصل التعسفي
                
                المبلغ الإجمالي: 85,000 ريال
                """,
                "expected": "labor_dispute"
            },
            {
                "id": "labor_002",
                "category": "labor_dispute",
                "text": """
                دعوى استحقاق رواتب متأخرة.
                الموظف: فاطمة محمد
                المؤسسة: مصنع النسيج الوطني
                
                لم تتقاضى الموظفة راتبها لمدة 6 أشهر (يناير - يونيو).
                الراتب الشهري: 3,000 ريال
                المستحقات: 18,000 ريال
                """,
                "expected": "labor_dispute"
            },
            {
                "id": "property_001",
                "category": "property_dispute",
                "text": """
                دعوى إخلاء عقار من المستأجر.
                المؤجر: أحمد سلطان
                المستأجر: علي محمود
                
                الموضوع: تأخر المستأجر عن دفع الإيجار لمدة 12 شهر متتالي.
                قيمة الإيجار الشهري: 2,000 ريال
                المبلغ المستحق: 24,000 ريال
                
                المطالبة: إخلاء العقار + سداد المستحقات
                """,
                "expected": "property_dispute"
            },
            {
                "id": "property_002",
                "category": "property_dispute",
                "text": """
                نزاع بشأن ملكية أرض.
                المدعي: محمد حسن
                المدعى عليه: سلطان علي
                
                النزاع حول ملكية قطعة أرض مساحتها 2000 متر مربع في الطريق الشرقي.
                يملك المدعي صك ملكية قديم للأرض، والمدعى عليه بنى عليها بسور وحوشة.
                """,
                "expected": "property_dispute"
            },
            {
                "id": "traffic_001",
                "category": "traffic_accident",
                "text": """
                حادثة مرورية - تصادم سيارتين.
                التاريخ: 2024-02-20
                الموقع: طريق الملك فهد، الرياض
                
                تصادم بين سيارة تويوتا نصادم مع سيارة هونداي.
               الأضرار: كسر زجاج أمامي، خدش هيكل السيارة
                المصابين: راكب في السيارة الأولى أصيب برضح في الرأس
                
                المسؤول عن الحادث: السائق الثاني (خرج من الطريق الجانبي بدون الانتظار)
                """,
                "expected": "traffic_accident"
            },
            {
                "id": "compensation_001",
                "category": "compensation",
                "text": """
                مطالبة بتعويض عن ضرر.
                المدعي: شركة الأمل
                المدعى عليه: شركة البناء المتقدمة
                
                اتفقت الشركتان على عقد مقاولة لبناء مستودع.
                قامت شركة البناء بعمل خاطئ أدى لانهيار جزئي للجدران.
                تطلب الشركة الأولى تعويض بقيمة 150,000 ريال.
                """,
                "expected": "compensation"
            },
            {
                "id": "unknown_001",
                "category": "jurisdictional",
                "text": """
                دفع بعدم الاختصاص النوعي.
                يتقدم الخصم بدفع يفيد بأن المحكمة الحالية غير مختصة نوعياً.
                """,
                "expected": "jurisdictional"
            }
        ]
        
        return test_cases
    
    def validate_all(self) -> Dict[str, Any]:
        """Validate all test cases"""
        logger.info("[VALIDATE] Starting classification validation")
        logger.info(f"[VALIDATE] Testing {len(self.test_cases)} cases")
        
        self.results["total"] = len(self.test_cases)
        
        for test_case in self.test_cases:
            result = self._validate_single(test_case)
            
            # Track results
            if result["correct"]:
                self.results["correct"] += 1
            else:
                self.results["failures"].append(result)
            
            # Track by category
            category = test_case["category"]
            if category not in self.results["by_category"]:
                self.results["by_category"][category] = {"total": 0, "correct": 0}
            
            self.results["by_category"][category]["total"] += 1
            if result["correct"]:
                self.results["by_category"][category]["correct"] += 1
        
        # Calculate statistics
        self.results["overall_accuracy"] = self.results["correct"] / self.results["total"] if self.results["total"] > 0 else 0
        
        logger.info(f"[VALIDATE] Validation complete - accuracy: {self.results['overall_accuracy']:.1%}")
        
        return self.results
    
    def _validate_single(self, test_case: Dict) -> Dict:
        """Validate a single test case"""
        case_id = test_case["id"]
        expected = test_case["expected"]
        text = test_case["text"]
        
        # Classify
        classification = classifier.classify_case(text)
        predicted = classification["case_type"]
        confidence = classification["confidence"]
        
        is_correct = predicted == expected
        
        logger.debug(f"[CASE] {case_id}: Expected={expected}, Predicted={predicted}, Confidence={confidence:.2%}")
        
        return {
            "case_id": case_id,
            "expected": expected,
            "predicted": predicted,
            "confidence": confidence,
            "correct": is_correct,
            "matched_keywords": classification.get("matched_keywords", []),
            "sub_types": classification.get("sub_types", [])
        }
    
    def print_report(self):
        """Print validation report"""
        print("\n" + "="*70)
        print("CLASSIFICATION VALIDATION REPORT")
        print("="*70)
        
        print(f"\nOVERALL ACCURACY: {self.results['overall_accuracy']:.1%}")
        print(f"Passed: {self.results['correct']}/{self.results['total']}")
        
        print("\n" + "-"*70)
        print("ACCURACY BY CATEGORY:")
        print("-"*70)
        
        for category, stats in self.results["by_category"].items():
            accuracy = stats["correct"] / stats["total"] if stats["total"] > 0 else 0
            category_name = CASE_TYPES.get(category, {}).get("name_ar", category)
            print(f"├─ {category_name}: {stats['correct']}/{stats['total']} ({accuracy:.1%})")
        
        if self.results["failures"]:
            print("\n" + "-"*70)
            print(f"FAILURES ({len(self.results['failures'])}):")
            print("-"*70)
            
            for failure in self.results["failures"][:10]:  # Show first 10
                expected_name = CASE_TYPES.get(failure["expected"], {}).get("name_ar", failure["expected"])
                predicted_name = CASE_TYPES.get(failure["predicted"], {}).get("name_ar", failure["predicted"])
                print(f"\n└─ {failure['case_id']}:")
                print(f"   Expected: {expected_name}")
                print(f"   Predicted: {predicted_name} (confidence: {failure['confidence']:.2%})")
        
        print("\n" + "="*70)
    
    def save_report(self, filepath: str = "classification_validation_report.json"):
        """Save validation report to file"""
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)
        logger.info(f"[VALIDATE] Report saved to {filepath}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    validator = ClassificationValidator()
    results = validator.validate_all()
    validator.print_report()
    validator.save_report()
    
    # Exit with appropriate code
    if results["overall_accuracy"] >= 0.90:
        print("\n✓ Classification accuracy acceptable (>= 90%)")
        exit(0)
    else:
        print(f"\n✗ Classification accuracy below threshold: {results['overall_accuracy']:.1%}")
        exit(1)
