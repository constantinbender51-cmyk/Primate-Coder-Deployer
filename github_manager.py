import requests
import base64
from config import GITHUB_TOKEN, GITHUB_API_URL, GITHUB_REPO, DEFAULT_BRANCH

class GitHubManager:
    def __init__(self):
        self.token = GITHUB_TOKEN
        self.api_url = GITHUB_API_URL
        self.repo = GITHUB_REPO
        self.branch = DEFAULT_BRANCH
        self.headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json"
        }
    
    def get_file_content(self, path):
        """Get the content of a file from the repository"""
        url = f"{self.api_url}/repos/{self.repo}/contents/{path}"
        params = {"ref": self.branch}
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            content = base64.b64decode(data["content"]).decode("utf-8")
            sha = data["sha"]
            
            return {"content": content, "sha": sha}
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise Exception(f"GitHub API error: {str(e)}")
    
    def get_full_codebase(self):
        """Recursively get all files in the repository"""
        def get_tree(path=""):
            url = f"{self.api_url}/repos/{self.repo}/contents/{path}"
            params = {"ref": self.branch}
            
            try:
                response = requests.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                return response.json()
            except:
                return []
        
        def traverse(path=""):
            items = get_tree(path)
            files = {}
            
            for item in items:
                if item["type"] == "file":
                    # Get file content
                    file_data = self.get_file_content(item["path"])
                    if file_data:
                        files[item["path"]] = file_data["content"]
                elif item["type"] == "dir":
                    # Recursively get directory contents
                    files.update(traverse(item["path"]))
            
            return files
        
        return traverse()
    
    def format_codebase_for_prompt(self):
        """Format the entire codebase for DeepSeek prompt"""
        files = self.get_full_codebase()
        
        if not files:
            return "Repository is empty."
        
        formatted = []
        for path, content in files.items():
            lines = content.split("\n")
            numbered_lines = [f"{i+1:4d} | {line}" for i, line in enumerate(lines)]
            
            formatted.append(f"=== FILE: {path} ===")
            formatted.append("\n".join(numbered_lines))
            formatted.append("")
        
        return "\n".join(formatted)
    
    def create_file(self, path, content, message="Create file"):
        """Create a new file in the repository"""
        url = f"{self.api_url}/repos/{self.repo}/contents/{path}"
        
        encoded_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")
        
        data = {
            "message": message,
            "content": encoded_content,
            "branch": self.branch
        }
        
        try:
            response = requests.put(url, headers=self.headers, json=data)
            response.raise_for_status()
            return True
        except requests.exceptions.HTTPError as e:
            raise Exception(f"Failed to create file {path}: {str(e)}")
    
    def overwrite_file(self, path, content, message="Update file"):
        """Overwrite the entire content of a file"""
        # Get current file SHA
        file_data = self.get_file_content(path)
        
        if not file_data:
            # File doesn't exist, create it
            return self.create_file(path, content, message)
        
        url = f"{self.api_url}/repos/{self.repo}/contents/{path}"
        encoded_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")
        
        data = {
            "message": message,
            "content": encoded_content,
            "sha": file_data["sha"],
            "branch": self.branch
        }
        
        try:
            response = requests.put(url, headers=self.headers, json=data)
            response.raise_for_status()
            return True
        except requests.exceptions.HTTPError as e:
            raise Exception(f"Failed to overwrite file {path}: {str(e)}")
    
    def insert_lines(self, path, line_number, content, message="Insert lines"):
        """Insert content at a specific line number (1-indexed)"""
        file_data = self.get_file_content(path)
        
        if not file_data:
            raise Exception(f"File {path} does not exist")
        
        lines = file_data["content"].split("\n")
        
        # Validate line number
        if line_number < 1 or line_number > len(lines) + 1:
            raise Exception(f"Invalid line number {line_number}. File has {len(lines)} lines.")
        
        # Insert content at the specified line (before that line)
        insert_lines = content.split("\n")
        new_lines = lines[:line_number-1] + insert_lines + lines[line_number-1:]
        new_content = "\n".join(new_lines)
        
        return self.overwrite_file(path, new_content, message)
    
    def delete_file(self, path, message="Delete file"):
        """Delete a file from the repository"""
        file_data = self.get_file_content(path)
        
        if not file_data:
            raise Exception(f"File {path} does not exist")
        
        url = f"{self.api_url}/repos/{self.repo}/contents/{path}"
        
        data = {
            "message": message,
            "sha": file_data["sha"],
            "branch": self.branch
        }
        
        try:
            response = requests.delete(url, headers=self.headers, json=data)
            response.raise_for_status()
            return True
        except requests.exceptions.HTTPError as e:
            raise Exception(f"Failed to delete file {path}: {str(e)}")
    
    def delete_lines(self, path, start_line, end_line, message="Delete lines"):
        """Delete specific lines from a file (1-indexed, inclusive)"""
        file_data = self.get_file_content(path)
        
        if not file_data:
            raise Exception(f"File {path} does not exist")
        
        lines = file_data["content"].split("\n")
        
        # Validate line numbers
        if start_line < 1 or end_line > len(lines) or start_line > end_line:
            raise Exception(
                f"Invalid line range {start_line}-{end_line}. File has {len(lines)} lines."
            )
        
        # Delete lines (convert to 0-indexed)
        new_lines = lines[:start_line-1] + lines[end_line:]
        new_content = "\n".join(new_lines)
        
        return self.overwrite_file(path, new_content, message)
    
    def apply_operation(self, operation):
        """Apply a single operation to the repository"""
        op_type = operation.get("operation")
    
        if op_type == "MULTIPLE_OPERATIONS":
            # Handle nested operations
            nested_ops = operation.get("operations", [])
            results = []
            for nested_op in nested_ops:
                results.append(self.apply_operation(nested_op))
                return results
    
        elif op_type == "CREATE_FILE":
            return self.create_file(
                operation["path"],
                operation["content"],
                f"Create {operation['path']}"
            )
    
        elif op_type == "OVERWRITE_FILE":
            return self.overwrite_file(
                operation["path"],
                operation["content"],
                f"Update {operation['path']}"
            )
    
        elif op_type == "INSERT_LINES":
            return self.insert_lines(
                operation["path"],
                operation["line"],
                operation["content"],
                f"Insert lines in {operation['path']} at line {operation['line']}"
            )
    
        elif op_type == "DELETE_FILE":
            return self.delete_file(
                operation["path"],
                f"Delete {operation['path']}"
            )
    
        elif op_type == "DELETE_LINES":
            return self.delete_lines(
                operation["path"],
                operation["start_line"],
                operation["end_line"],
                f"Delete lines {operation['start_line']}-{operation['end_line']} from {operation['path']}"
            )
    
        else:
            raise Exception(f"Unknown operation type: {op_type}")
