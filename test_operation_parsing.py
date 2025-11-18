#!/usr/bin/env python3
"""
Test script to verify operation parsing works correctly
"""

from deepseek_client import DeepSeekClient
import json

def test_parsing():
    client = DeepSeekClient()
    
    print("=" * 60)
    print("Operation Parsing Test Suite")
    print("=" * 60)
    
    # Test 1: NEEDS_RETRY with fixes
    print("\n1. Testing NEEDS_RETRY with fixes...")
    test1 = '''
    {
      "operation": "NEEDS_RETRY",
      "message": "Found multiple issues in the codebase that need fixing before deployment",
      "fixes": [
        {
          "operation": "OVERWRITE_FILE",
          "path": "Procfile",
          "content": "web: python news_fetcher.py"
        },
        {
          "operation": "INSERT_LINES",
          "path": "news_fetcher.py",
          "line": 73,
          "content": "            'api-key': 'test'"
        }
      ]
    }
    '''
    
    ops = client.parse_operations(test1)
    print(f"Parsed {len(ops)} operations")
    if ops:
        print(f"Operation type: {ops[0].get('operation')}")
        print(f"Has fixes: {'fixes' in ops[0]}")
        if 'fixes' in ops[0]:
            print(f"Number of fixes: {len(ops[0]['fixes'])}")
            print(f"Fix types: {[f.get('operation') for f in ops[0]['fixes']]}")
    
    validated = client.validate_operations(ops)
    print(f"Validated: {len(validated)} operations")
    print(f"✓ Test 1 passed" if validated else "✗ Test 1 failed")
    
    # Test 2: Multiple operations in markdown
    print("\n2. Testing operations in markdown code block...")
    test2 = '''
    I'll create a comprehensive solution...
    
    ```json
    {
      "operations": [
        {
          "operation": "CREATE_FILE",
          "path": "literature_transformer.py",
          "content": "import torch"
        }
      ]
    }
    ```
    '''
    
    ops = client.parse_operations(test2)
    print(f"Parsed {len(ops)} operations")
    if ops:
        print(f"Operation type: {ops[0].get('operation')}")
        print(f"✓ Test 2 passed")
    else:
        print("✗ Test 2 failed")
    
    # Test 3: MULTIPLE_OPERATIONS nested
    print("\n3. Testing MULTIPLE_OPERATIONS...")
    test3 = '''
    {
      "operation": "MULTIPLE_OPERATIONS",
      "operations": [
        {"operation": "CREATE_FILE", "path": "test1.py", "content": "print('test1')"},
        {"operation": "CREATE_FILE", "path": "test2.py", "content": "print('test2')"}
      ]
    }
    '''
    
    ops = client.parse_operations(test3)
    print(f"Parsed {len(ops)} operations")
    if ops:
        print(f"Operation type: {ops[0].get('operation')}")
        if 'operations' in ops[0]:
            print(f"Nested operations: {len(ops[0]['operations'])}")
            print(f"✓ Test 3 passed")
        else:
            print("✗ Test 3 failed - no nested operations")
    else:
        print("✗ Test 3 failed")
    
    # Test 4: VERIFY_COMPLETE
    print("\n4. Testing VERIFY_COMPLETE...")
    test4 = '''
    {
      "operation": "VERIFY_COMPLETE",
      "message": "Code is correct and ready for deployment"
    }
    '''
    
    ops = client.parse_operations(test4)
    print(f"Parsed {len(ops)} operations")
    if ops and ops[0].get('operation') == 'VERIFY_COMPLETE':
        print(f"✓ Test 4 passed")
    else:
        print("✗ Test 4 failed")
    
    # Test 5: Complex nested structure
    print("\n5. Testing complex nested NEEDS_RETRY...")
    test5 = '''
    ```json
    {
      "operation": "NEEDS_RETRY",
      "message": "Issues found",
      "fixes": [
        {
          "operation": "MULTIPLE_OPERATIONS",
          "operations": [
            {"operation": "CREATE_FILE", "path": "a.py", "content": "x=1"},
            {"operation": "CREATE_FILE", "path": "b.py", "content": "y=2"}
          ]
        },
        {"operation": "DELETE_FILE", "path": "old.py"}
      ]
    }
    ```
    '''
    
    ops = client.parse_operations(test5)
    validated = client.validate_operations(ops)
    print(f"Parsed {len(ops)} operations")
    print(f"Validated {len(validated)} operations")
    if validated and validated[0].get('operation') == 'NEEDS_RETRY':
        fixes = validated[0].get('fixes', [])
        print(f"Number of fixes: {len(fixes)}")
        print(f"Fix types: {[f.get('operation') for f in fixes]}")
        print(f"✓ Test 5 passed")
    else:
        print("✗ Test 5 failed")
    
    print("\n" + "=" * 60)
    print("Test suite complete!")
    print("=" * 60)

if __name__ == "__main__":
    test_parsing()
