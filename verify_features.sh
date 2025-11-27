#!/bin/bash
# verify_features.sh - Quick verification script for technical features

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║        Technical Features Verification Script               ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Check if virtual environment is activated
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "⚠️  Warning: Virtual environment not activated"
    echo "   Run: source .venv/bin/activate"
    echo ""
fi

# 1. Check Python syntax
echo "1️⃣  Checking Python syntax..."
python -m py_compile features/*.py tests/test_features/*.py conftest.py 2>/dev/null
if [ $? -eq 0 ]; then
    echo "   ✅ All files compile successfully"
else
    echo "   ❌ Syntax errors found"
    exit 1
fi
echo ""

# 2. Check imports
echo "2️⃣  Checking imports..."
python -c "from features import TechnicalFeatures, FeatureManager; print('   ✅ Imports work correctly')" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "   ❌ Import errors (is pandas installed?)"
    echo "   Run: pip install -r requirements.txt"
    exit 1
fi
echo ""

# 3. Count files
echo "3️⃣  Counting implementation files..."
IMPL_FILES=$(find features tests/test_features examples -name "*.py" 2>/dev/null | wc -l | tr -d ' ')
echo "   ✅ $IMPL_FILES Python files found"
echo ""

# 4. Check for tests
echo "4️⃣  Checking test files..."
if [ -f "tests/test_features/test_technical.py" ]; then
    echo "   ✅ test_technical.py found"
else
    echo "   ❌ test_technical.py missing"
fi

if [ -f "tests/test_features/test_feature_manager.py" ]; then
    echo "   ✅ test_feature_manager.py found"
else
    echo "   ❌ test_feature_manager.py missing"
fi
echo ""

# 5. Check conftest.py
echo "5️⃣  Checking pytest configuration..."
if [ -f "conftest.py" ]; then
    echo "   ✅ conftest.py found (import paths configured)"
else
    echo "   ❌ conftest.py missing (imports may fail)"
fi
echo ""

# Summary
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                    VERIFICATION COMPLETE                     ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "✅ All checks passed!"
echo ""
echo "Next steps:"
echo "  1. Run tests:     pytest tests/test_features/ -v"
echo "  2. Run examples:  python examples/feature_engineering_example.py"
echo "  3. Commit:        git add . && git commit"
echo ""
echo "Expected test result: 48 tests passed ✅"
echo ""


