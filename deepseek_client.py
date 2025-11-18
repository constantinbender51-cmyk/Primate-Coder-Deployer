import requests
import json
import re
from typing import List, Dict, Any, Optional
from config import DEEPSEEK_API_KEY, DEEPSEEK_API_URL, DEEPSEEK_MODEL

class DeepSeekClient:
    def __init__(self):
        self.api_key = DEEPSEEK_API_KEY
        self.api_url = DEEPSEEK_API_URL
        self.model = DEEPSEEK_MODEL
        self.conversation_history = []
    
    def create_coder_system_prompt(self, codebase_content):
        """Create a specialized system prompt for code generation and editing"""
        return f"""You are an expert software engineer and coder. Your task is to write, modify, and debug code based on user requirements.

CURRENT CODEBASE:
{codebase_content}

IMPORTANT DEPLOYMENT REQUIREMENTS:
- Railway deployment requires a Procfile that specifies how to run the application
- For Flask applications, use: web: gunicorn app:app
- For Python scripts with main, use: web: python your_script.py
- Make sure the Procfile is in the root directory

AVAILABLE OPERATIONS:
You can perform the following operations by responding in JSON format:

1. CREATE_FILE: Create a new file
   {{"operation": "CREATE_FILE", "path": "filename.py", "content": "file content here"}}

2. OVERWRITE_FILE: Replace entire file content
   {{"operation": "OVERWRITE_FILE", "path": "filename.py", "content": "new file content"}}

3. INSERT_LINES: Insert code at a specific line number
   {{"operation": "INSERT_LINES", "path": "filename.py", "line": 10, "content": "code to insert"}}

4. DELETE_FILE: Delete a file
   {{"operation": "DELETE_FILE", "path": "filename.py"}}

5. DELETE_LINES: Delete specific lines from a file
   {{"operation": "DELETE_LINES", "path": "filename.py", "start_line": 5, "end_line": 10}}

6. MULTIPLE_OPERATIONS: Perform multiple operations at once
   {{"operation": "MULTIPLE_OPERATIONS", "operations": [
       {{"operation": "CREATE_FILE", "path": "file1.py", "content": "..."}},
       {{"operation": "INSERT_LINES", "path": "file2.py", "line": 5, "content": "..."}}
   ]}}

7. VERIFY_COMPLETE: Indicate you've verified the code and it's ready
   {{"operation": "VERIFY_COMPLETE", "message": "Code is correct and ready for deployment"}}

8. NEEDS_RETRY: Indicate issues found that need fixing
   {{"operation": "NEEDS_RETRY", "message": "Issue description", "fixes": [...]}}

IMPORTANT RULES:
- Always respond with valid JSON that can be parsed by json.loads()
- If you need to provide explanations, put them in a "comment" field within the JSON
- For MULTIPLE_OPERATIONS, use the "operations" array field
- Line numbers are 1-indexed (first line is line 1)
- When inserting at line N, content is inserted BEFORE that line
- Be precise with line numbers - verify them against the current codebase

Your goal is to create working, production-ready code that fulfills the user's requirements."""

    def chat(self, user_message, codebase_content=""):
        """Send a message to DeepSeek and get a response"""
        # Add system prompt with codebase on first message or when codebase updates
        if not self.conversation_history or codebase_content:
            system_prompt = self.create_coder_system_prompt(codebase_content)
            # Reset conversation with new codebase context
            self.conversation_history = [
                {"role": "system", "content": system_prompt}
            ]
        
        # Add user message
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })
        
        # Make API request
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": self.conversation_history,
            "temperature": 0.3,
            "max_tokens": 8000
        }
        
        try:
            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=120
            )
            response.raise_for_status()
            
            result = response.json()
            assistant_message = result["choices"][0]["message"]["content"]
            
            # Add assistant response to history
            self.conversation_history.append({
                "role": "assistant",
                "content": assistant_message
            })
            
            return assistant_message
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"DeepSeek API error: {str(e)}")
    
    def extract_json_objects(self, text: str) -> List[str]:
        """Extract all potential JSON objects from text using multiple methods"""
        candidates = []
        
        # Method 1: Extract from markdown code blocks
        code_block_pattern = r'```(?:json)?\s*(.*?)\s*```'
        code_matches = re.findall(code_block_pattern, text, re.DOTALL | re.IGNORECASE)
        candidates.extend(code_matches)
        
        # Method 2: Find JSON objects by balancing braces (more robust)
        brace_objects = self._extract_balanced_braces(text)
        candidates.extend(brace_objects)
        
        # Method 3: Look for JSON-like structures after keywords
        keyword_objects = self._extract_after_keywords(text)
        candidates.extend(keyword_objects)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_candidates = []
        for candidate in candidates:
            if candidate not in seen:
                seen.add(candidate)
                unique_candidates.append(candidate)
        
        return unique_candidates
    
    def _extract_balanced_braces(self, text: str) -> List[str]:
        """Extract text between balanced braces { }"""
        objects = []
        stack = []
        start_index = -1
        
        for i, char in enumerate(text):
            if char == '{':
                if not stack:
                    start_index = i
                stack.append('{')
            elif char == '}':
                if stack:
                    stack.pop()
                    if not stack and start_index != -1:
                        # Found balanced object
                        obj_text = text[start_index:i+1]
                        objects.append(obj_text)
                        start_index = -1
        
        return objects
    
    def _extract_after_keywords(self, text: str) -> List[str]:
        """Extract JSON after common introductory phrases"""
        objects = []
        patterns = [
            r'Here (?:is|are)[^\{]*\{.*?\}',
            r'response[^\{]*\{.*?\}',
            r'answer[^\{]*\{.*?\}',
            r'operation[^\{]*\{.*?\}',
            r'json[^\{]*\{.*?\}',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
            for match in matches:
                # Extract just the JSON part
                brace_start = match.find('{')
                if brace_start != -1:
                    obj_text = match[brace_start:]
                    objects.append(obj_text)
        
        return objects
    
    def safe_json_parse(self, json_str: str) -> Optional[Dict[str, Any]]:
        """Safely parse JSON with multiple fallback strategies"""
        # Clean the string first
        json_str = json_str.strip()
        
        # Strategy 1: Direct parse
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass
        
        # Strategy 2: Try to fix common issues
        try:
            # Fix trailing commas
            fixed_json = re.sub(r',\s*}', '}', json_str)
            fixed_json = re.sub(r',\s*]', ']', fixed_json)
            return json.loads(fixed_json)
        except json.JSONDecodeError:
            pass
        
        # Strategy 3: Try to extract the largest valid JSON object
        try:
            # Find the longest valid JSON substring
            for length in range(len(json_str), 0, -1):
                for start in range(len(json_str) - length + 1):
                    substring = json_str[start:start+length]
                    try:
                        if substring.startswith('{') and substring.endswith('}'):
                            return json.loads(substring)
                    except json.JSONDecodeError:
                        continue
        except:
            pass
        
        return None
    
    def parse_operations(self, response: str) -> List[Dict[str, Any]]:
        """Robustly parse DeepSeek response to extract operations"""
        try:
            # Try direct parse first (in case it's pure JSON)
            direct_parse = self.safe_json_parse(response)
            if direct_parse:
                return self._extract_operations_from_object(direct_parse)
            
            # Extract all potential JSON objects
            json_candidates = self.extract_json_objects(response)
            
            # Try to parse each candidate
            for candidate in json_candidates:
                parsed = self.safe_json_parse(candidate)
                if parsed:
                    operations = self._extract_operations_from_object(parsed)
                    if operations:
                        return operations
            
            # If no valid operations found, check if it's a conversational response
            conversational_ops = self._parse_conversational_operations(response)
            if conversational_ops:
                return conversational_ops
            
            return []
            
        except Exception as e:
            print(f"Error parsing operations: {str(e)}")
            return []
    
    def _extract_operations_from_object(self, obj: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract operations from a parsed JSON object"""
        operations = []
        
        # Handle single operation
        if isinstance(obj, dict) and "operation" in obj:
            operations.append(obj)
        
        # Handle multiple operations array
        elif isinstance(obj, dict) and "operations" in obj:
            if isinstance(obj["operations"], list):
                operations.extend(obj["operations"])
        
        # Handle root-level array of operations
        elif isinstance(obj, list):
            for item in obj:
                if isinstance(item, dict) and "operation" in item:
                    operations.append(item)
        
        return operations
    
    def _parse_conversational_operations(self, response: str) -> List[Dict[str, Any]]:
        """Try to parse operations from conversational text (fallback)"""
        # Look for operation type mentions
        operation_types = [
            "CREATE_FILE", "OVERWRITE_FILE", "INSERT_LINES", 
            "DELETE_FILE", "DELETE_LINES", "MULTIPLE_OPERATIONS",
            "VERIFY_COMPLETE", "NEEDS_RETRY"
        ]
        
        found_operations = []
        
        for op_type in operation_types:
            if op_type in response:
                # Create a basic operation object
                if op_type in ["VERIFY_COMPLETE", "NEEDS_RETRY"]:
                    found_operations.append({
                        "operation": op_type,
                        "message": response
                    })
        
        return found_operations
    
    def validate_operations(self, operations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate and clean extracted operations"""
        valid_operations = []
        
        for op in operations:
            if not isinstance(op, dict):
                continue
                
            # Basic validation
            if "operation" not in op:
                continue
                
            # Clean the operation
            cleaned_op = {k: v for k, v in op.items() if v is not None}
            
            # Type-specific validation
            operation_type = cleaned_op.get("operation")
            
            if operation_type in ["CREATE_FILE", "OVERWRITE_FILE"]:
                if "path" in cleaned_op and "content" in cleaned_op:
                    valid_operations.append(cleaned_op)
                    
            elif operation_type == "INSERT_LINES":
                if all(k in cleaned_op for k in ["path", "line", "content"]):
                    valid_operations.append(cleaned_op)
                    
            elif operation_type == "DELETE_FILE":
                if "path" in cleaned_op:
                    valid_operations.append(cleaned_op)
                    
            elif operation_type == "DELETE_LINES":
                if all(k in cleaned_op for k in ["path", "start_line", "end_line"]):
                    valid_operations.append(cleaned_op)
                    
            elif operation_type == "MULTIPLE_OPERATIONS":
                if "operations" in cleaned_op and isinstance(cleaned_op["operations"], list):
                    # Validate nested operations recursively
                    nested_ops = self.validate_operations(cleaned_op["operations"])
                    if nested_ops:
                        cleaned_op["operations"] = nested_ops
                        valid_operations.append(cleaned_op)
                        
            elif operation_type in ["VERIFY_COMPLETE", "NEEDS_RETRY"]:
                valid_operations.append(cleaned_op)
        
        return valid_operations
    
    def get_validated_operations(self, response: str) -> List[Dict[str, Any]]:
        """Main method to get validated operations from response"""
        operations = self.parse_operations(response)
        return self.validate_operations(operations)
    
    def reset_conversation(self):
        """Reset the conversation history"""
        self.conversation_history = []
