import requests
import json
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
   {{"operations": [
       {{"operation": "CREATE_FILE", "path": "file1.py", "content": "..."}},
       {{"operation": "INSERT_LINES", "path": "file2.py", "line": 5, "content": "..."}}
   ]}}

7. VERIFY_COMPLETE: Indicate you've verified the code and it's ready
   {{"operation": "VERIFY_COMPLETE", "message": "Code is correct and ready for deployment"}}

8. NEEDS_RETRY: Indicate issues found that need fixing, with fixes to apply
   {{"operation": "NEEDS_RETRY", "message": "Issue description", "fixes": [
       {{"operation": "OVERWRITE_FILE", "path": "file.py", "content": "..."}},
       {{"operation": "INSERT_LINES", "path": "file.py", "line": 10, "content": "..."}}
   ]}}

IMPORTANT RULES:
- Line numbers are 1-indexed (first line is line 1)
- When inserting at line N, content is inserted BEFORE that line
- Be precise with line numbers - verify them against the current codebase
- Always respond with valid JSON
- You can perform multiple operations in one response
- After deployment errors, analyze the error and provide fixes

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
    
    def parse_operations(self, response):
        """Parse DeepSeek response to extract operations"""
        try:
            response_original = response
            response = response.strip()
            
            # Method 1: Try to extract JSON from markdown code blocks
            json_candidates = []
            
            # Look for ```json blocks
            if "```json" in response:
                blocks = response.split("```json")
                for block in blocks[1:]:  # Skip first split (before first ```)
                    if "```" in block:
                        json_candidates.append(block.split("```")[0].strip())
            
            # Look for ``` blocks (without language specifier)
            elif "```" in response:
                blocks = response.split("```")
                for i in range(1, len(blocks), 2):  # Get odd indices (code blocks)
                    json_candidates.append(blocks[i].strip())
            
            # Method 2: Try to find JSON objects with regex-like search
            if not json_candidates:
                # Look for { ... } patterns
                import re
                # Find all potential JSON objects (outermost braces)
                brace_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
                matches = re.finditer(brace_pattern, response, re.DOTALL)
                for match in matches:
                    json_candidates.append(match.group(0))
            
            # Method 3: If response starts with explanation, try to find JSON after it
            if not json_candidates:
                # Split by common delimiters
                for delimiter in ['\n\n', 'Here\'s', 'here\'s', 'implementation:', 'solution:']:
                    if delimiter in response:
                        parts = response.split(delimiter)
                        for part in parts:
                            if '{' in part and '}' in part:
                                # Extract from first { to last }
                                start = part.find('{')
                                end = part.rfind('}') + 1
                                if start != -1 and end > start:
                                    json_candidates.append(part[start:end])
            
            # Try to parse each candidate
            for candidate in json_candidates:
                try:
                    parsed = json.loads(candidate)
                    
                    # Handle single operation
                    if "operation" in parsed:
                        return [parsed]
                    
                    # Handle multiple operations
                    if "operations" in parsed:
                        return parsed["operations"]
                    
                except json.JSONDecodeError:
                    continue
            
            # Method 4: Try parsing the entire response as JSON
            try:
                parsed = json.loads(response)
                if "operation" in parsed:
                    return [parsed]
                if "operations" in parsed:
                    return parsed["operations"]
            except json.JSONDecodeError:
                pass
            
            # If all methods fail, return empty (conversational response)
            return []
            
        except Exception as e:
            print(f"Error parsing operations: {str(e)}")
            return []
    
    def reset_conversation(self):
        """Reset the conversation history"""
        self.conversation_history = []
