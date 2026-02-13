import sys
import os

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from trend_analyzer import analyze_trends, filter_outliers
from models import Case
from entity_extractor import EntityExtractor
import json

# Handle Windows console encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def test_filter_logic_standalone():
    print("\n[TEST] Standalone Outlier Filter (Fix 8)")
    data = [100.0, 100.0, 100.0, 100.0, 10000000.0]
    filtered = filter_outliers(data)
    if len(filtered) == 4 and max(filtered) == 100.0:
        print("[PASS]: Filter logic works correctly (80M dropped).")
    else:
        print(f"[FAIL]: Filter logic failed. Got: {filtered}")

def test_compensation_fix():
    print("\n[TEST] Compensation Robustness (Fix 1)")
    
    # Mock cases: 1 outlier (80M) and 4 normal (50k-100k)
    cases = []
    # Outlier
    cases.append(Case(
        case_id="OUTLIER", 
        judgment="حكمت بإلزام المدعى عليه بسداد مبلغ 80,000,000 ريال", 
        facts="", is_real=True, court="Test", legal_reasoning="", source="Test", language="ar"
    ))
    # Normal cases
    amounts = [50000, 60000, 70000, 80000]
    for i, amt in enumerate(amounts):
        cases.append(Case(
            case_id=f"NORMAL_{i}", 
            judgment=f"حكمت بإلزام المدعى عليه بسداد مبلغ {amt:,} ريال", 
            facts="", is_real=True, court="Test", legal_reasoning="", source="Test", language="ar"
        ))
        
    stats = analyze_trends(cases)
    avg = stats['average_compensation']
    med = stats['median_compensation']
    
    print(f"Stats: Avg={avg:,.2f}, Median={med:,.2f}")
    
    if avg < 1000000:
        print("[PASS]: Outlier filtered (Avg is reasonable)")
    else:
        print(f"[FAIL]: Outlier NOT filtered (Avg {avg:,.2f} > 1M)")

def test_entity_extraction():
    print("\n[TEST] Entity Extraction (Fix 2)")
    
    text = """
    أصدرت الدائرة التجارية الأولى بالمحكمة العامة بالرياض حكمها في القضية رقم 1234
    المقامة من شركة النور التجارية (سجل تجاري: 1010) ضد مؤسسة الأمل للمقاولات
    وذلك بتاريخ 1445/05/20 هـ
    بشأن مطالبة مالية بمبلغ وقدره 50,000 ريال بموجب العقد المبرم.
    """
    
    entities = EntityExtractor.extract(text)
    print(f"Extracted: {json.dumps(entities, ensure_ascii=True, indent=2)}")
    
    passed = True
    if entities.get('plaintiff') != "النور التجارية (سجل تجاري: 1010)":
        print(f"[FAIL]: Plaintiff mismatch (Got: {entities.get('plaintiff')})")
        passed = False
    if entities.get('defendant') != "الأمل للمقاولات":
        print(f"[FAIL]: Defendant mismatch (Got: {entities.get('defendant')})")
        passed = False
    if entities.get('date') != "1445/05/20":
        print(f"[FAIL]: Date mismatch")
        passed = False
    if entities.get('compensation_amount') != "50,000 ريال":
        print(f"[FAIL]: Amount mismatch")
        passed = False
        
    if passed:
        print("[PASS]: All entities extracted correctly.")

def test_multi_part_award_summing():
    print("\n[TEST] Multi-part Award Summing (Fix Grounding)")
    
    text = """
    منطوق الحكم:
    حكمت المحكمة بإلزام المدعى عليها بدفع مبلغ وقدره 48,000 ريال كتعويض، 
    ومبلغ 16,000 ريال كبدل إشعار، ومبلغ 24,000 ريال مكافأة نهاية خدمة.
    """
    
    entities = EntityExtractor.extract(text)
    print(f"Entities: {json.dumps(entities, ensure_ascii=False, indent=2)}")
    
    # Expected: 48000 + 16000 + 24000 = 88000
    expected = "88,000 ريال"
    actual = entities.get('compensation_amount')
    
    if actual == expected:
        print(f"[PASS]: Summing logic correct. Got: {actual}")
    else:
        print(f"[FAIL]: Summing logic failed. Expected: {expected}, Got: {actual}")

if __name__ == "__main__":
    try:
        test_filter_logic_standalone()
        test_compensation_fix()
        test_entity_extraction()
        test_multi_part_award_summing()
    except Exception as e:
        print(f"[ERROR]: {e}")
        import traceback
        traceback.print_exc()
