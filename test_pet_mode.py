"""
Quick test for Pet Mode functionality
Tests that pet-toxic pills are correctly identified
"""

import json
import sys

# Fix encoding for Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Load database
with open('pills_db.json', 'r') as f:
    PILL_DB = json.load(f)

print("=" * 80)
print("PET MODE FUNCTIONALITY TEST")
print("=" * 80)
print()

# Test cases for pet mode
test_cases = [
    {"name": "Tylenol (LETHAL to cats)", "imprint": "TYLENOL", "expected_pet_toxic": "LETHAL"},
    {"name": "Advil (EXTREME for pets)", "imprint": "ADVIL", "expected_pet_toxic": "EXTREME"},
    {"name": "Ibuprofen 200mg", "imprint": "IBU 200", "expected_pet_toxic": "EXTREME"},
    {"name": "Aleve (EXTREME for pets)", "imprint": "ALEVE", "expected_pet_toxic": "EXTREME"},
    {"name": "Xanax 2mg", "imprint": "XANAX 2", "expected_pet_toxic": "High"},
]

passed = 0
failed = 0

for test in test_cases:
    imprint_to_find = test["imprint"].upper()
    expected_toxic = test["expected_pet_toxic"]

    # Find pill in database
    found_pill = None
    for pill in PILL_DB:
        pill_imprint = pill["imprint"].upper()
        if pill_imprint == imprint_to_find:
            found_pill = pill
            break

    print(f"Test: {test['name']}")
    print(f"  Searching for imprint: {imprint_to_find}")

    if found_pill:
        pet_toxic = found_pill.get("pet_toxic")
        pet_action = found_pill.get("pet_action")

        print(f"  ✓ Found pill: {found_pill['name']}")
        print(f"  Pet Toxic Level: {pet_toxic}")
        print(f"  Pet Action: {pet_action}")

        if pet_toxic == expected_toxic:
            print(f"  [PASS] - Correctly flagged as {pet_toxic}")
            passed += 1
        else:
            print(f"  [FAIL] - Expected {expected_toxic}, got {pet_toxic}")
            failed += 1
    else:
        print(f"  [FAIL] - Pill not found in database")
        failed += 1

    print()

print("=" * 80)
print(f"FINAL SCORE: {passed} PASSED, {failed} FAILED")
print("=" * 80)

if failed == 0:
    print("✅ ALL PET MODE TESTS PASSED!")
    print("The purple 💀 screen will show for Tylenol in pet mode")
    print("Try the demo: Select 'Pet' mode, scan Tylenol → DEADLY TO CATS screen")
else:
    print(f"⚠️ WARNING: {failed} tests failed")
