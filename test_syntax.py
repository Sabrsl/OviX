# Test syntax of the new modules
import ast
import sys

def test_syntax(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            code = f.read()
        ast.parse(code)
        print(f"✓ {filepath} - syntax OK")
        return True
    except SyntaxError as e:
        print(f"✗ {filepath} - syntax error: {e}")
        return False

print("Testing syntax of new modules...")
test_syntax("src/wikipedia_maintenance/utils/secure_credentials.py")
test_syntax("src/wikipedia_maintenance/utils/structured_logging.py")
print("Syntax tests completed")