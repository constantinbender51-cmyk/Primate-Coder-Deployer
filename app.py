from flask import Flask, render_template, request, jsonify, Response
import json
import time
from threading import Thread
import queue
from config import validate_config, GITHUB_REPO, RAILWAY_PROJECT_ID
from deepseek_client import DeepSeekClient
from github_manager import GitHubManager
from railway_manager import RailwayManager

app = Flask(__name__)

# Global queue for Server-Sent Events
message_queue = queue.Queue()

def send_update(message_type, content):
    """Send an update to the frontend via SSE"""
    message = {
        "type": message_type,
        "content": content,
        "timestamp": time.time()
    }
    message_queue.put(message)
    print(f"[{message_type}] {content}")

def apply_operations_recursive(github, operations):
    """Recursively apply operations, handling nested MULTIPLE_OPERATIONS"""
    applied_count = 0
    for operation in operations:
        op_type = operation.get("operation")
        
        # Check for special operations
        if op_type == "VERIFY_COMPLETE":
            send_update("status", "DeepSeek verified code is complete!")
            send_update("complete", operation.get("message", "Code verified"))
            return applied_count
        
        if op_type == "NEEDS_RETRY":
            send_update("error", f"DeepSeek found issues: {operation.get('message')}")
            continue
        
        if op_type == "MULTIPLE_OPERATIONS":
            # Handle nested operations
            nested_ops = operation.get("operations", [])
            nested_count = apply_operations_recursive(github, nested_ops)
            applied_count += nested_count
            send_update("operation_success", f"Applied {nested_count} nested operations")
            continue
        
        # Apply the operation
        try:
            send_update("operation", f"Applying {op_type}: {operation.get('path', 'N/A')}")
            github.apply_operation(operation)
            send_update("operation_success", f"Successfully applied {op_type}")
            applied_count += 1
        except Exception as e:
            send_update("error", f"Failed to apply {op_type}: {str(e)}")
    
    return applied_count

def process_user_request(user_request):
    """Main workflow: DeepSeek -> GitHub -> Railway -> Verification"""
    try:
        send_update("status", "Initializing...")
        
        # Initialize clients
        deepseek = DeepSeekClient()
        github = GitHubManager()
        railway = RailwayManager()
        
        # Step 1: Get current codebase
        send_update("status", "Fetching current codebase from GitHub...")
        codebase = github.format_codebase_for_prompt()
        send_update("codebase", codebase)
        
        # Step 2: Send request to DeepSeek
        send_update("status", "Sending request to DeepSeek...")
        response = deepseek.chat(user_request, codebase)
        send_update("deepseek_response", response)
        
        # Step 3: Parse operations
        operations = deepseek.parse_operations(response)
        
        if not operations:
            send_update("status", "DeepSeek provided a conversational response (no code operations)")
            send_update("complete", "Process complete - no code changes requested")
            return
        
        # Step 4: Apply operations to GitHub
        send_update("status", f"Applying operations to GitHub...")
        
        applied_count = apply_operations_recursive(github, operations)
        
        if applied_count == 0:
            send_update("status", "No operations were applied (only verification or retry operations)")
            send_update("complete", "Process complete - no code changes made")
            return
        
        send_update("status", f"Successfully applied {applied_count} operations")
        
        # Step 5: Get updated codebase for verification
        send_update("status", "Getting updated codebase for verification...")
        time.sleep(2)  # Give GitHub a moment to sync
        updated_codebase = github.format_codebase_for_prompt()
        
        # Step 6: Ask DeepSeek to verify the changes
        send_update("status", "Asking DeepSeek to verify the changes...")
        verification_response = deepseek.chat(
            "Please verify the above codebase is correct. If everything looks good, respond with VERIFY_COMPLETE operation. If there are issues, respond with NEEDS_RETRY operation with fixes.",
            updated_codebase
        )
        send_update("deepseek_response", verification_response)
        
        # Parse verification response
        verification_ops = deepseek.parse_operations(verification_response)
        
        # Check if verification passed
        if verification_ops and verification_ops[0].get("operation") == "VERIFY_COMPLETE":
            send_update("status", "✓ DeepSeek verified the code!")
        else:
            send_update("warning", "DeepSeek requested changes - applying fixes...")
            # Recursively apply fixes (limit recursion)
            if verification_ops:
                fix_count = apply_operations_recursive(github, verification_ops)
                if fix_count > 0:
                    send_update("status", f"Applied {fix_count} fixes based on DeepSeek feedback")
        
        # Step 7: Wait for Railway deployment
        send_update("status", "Waiting for Railway deployment...")
        send_update("deployment", "Deployment started (monitoring...)")
        
        # Note: Railway may take a moment to detect the GitHub push
        time.sleep(5)
        
        status, logs, deployment_id = railway.wait_for_deployment()
        
        send_update("deployment", f"Deployment status: {status}")
        send_update("logs", "\n".join(logs))
        
        # Step 8: Send deployment results to DeepSeek for evaluation
        if status == "SUCCESS":
            send_update("status", "Deployment successful! Sending logs to DeepSeek for final evaluation...")
            
            evaluation_prompt = f"""The code has been successfully deployed to Railway.
            
Deployment Status: {status}
Deployment ID: {deployment_id}

Deployment Logs:
{railway.format_logs_for_prompt(logs)}

Please review the deployment logs and confirm if the application is running correctly and doing what was intended. If there are any errors or issues, provide fixes using the operation format."""
            
            evaluation_response = deepseek.chat(evaluation_prompt)
            send_update("deepseek_response", evaluation_response)
            
            # Check if DeepSeek is satisfied
            eval_ops = deepseek.parse_operations(evaluation_response)
            
            if eval_ops and eval_ops[0].get("operation") == "VERIFY_COMPLETE":
                send_update("complete", "✓ Success! DeepSeek confirmed the script is running correctly.")
            else:
                send_update("warning", "DeepSeek found issues in deployment. Check the response above.")
        
        elif status in ["FAILED", "CRASHED"]:
            send_update("status", "Deployment failed! Sending error logs to DeepSeek...")
            
            error_prompt = f"""The deployment FAILED with status: {status}

Deployment Logs:
{railway.format_logs_for_prompt(logs)}

Please analyze the error and provide fixes using the operation format to correct the issues."""
            
            error_response = deepseek.chat(error_prompt)
            send_update("deepseek_response", error_response)
            
            # Apply fixes if provided
            error_ops = deepseek.parse_operations(error_response)
            if error_ops:
                send_update("status", "Applying DeepSeek's fixes...")
                fix_count = apply_operations_recursive(github, error_ops)
                if fix_count > 0:
                    send_update("status", f"Applied {fix_count} fixes. Waiting for new deployment...")
                    # Wait for the new deployment
                    time.sleep(5)
                    status, logs, deployment_id = railway.wait_for_deployment()
                    send_update("deployment", f"Retry deployment status: {status}")
                    send_update("logs", "\n".join(logs))
        
        else:
            send_update("error", f"Deployment status: {status}")
        
        send_update("complete", "Process finished")
        
    except Exception as e:
        send_update("error", f"Fatal error: {str(e)}")
        send_update("complete", "Process terminated with errors")

@app.route('/')
def index():
    """Render the main UI"""
    return render_template('index.html', repo=GITHUB_REPO, project_id=RAILWAY_PROJECT_ID)

@app.route('/api/submit', methods=['POST'])
def submit_request():
    """Handle user request submission"""
    data = request.json
    user_request = data.get('request', '')
    
    if not user_request:
        return jsonify({"error": "No request provided"}), 400
    
    # Clear the message queue
    while not message_queue.empty():
        message_queue.get()
    
    # Process request in background thread
    thread = Thread(target=process_user_request, args=(user_request,))
    thread.daemon = True
    thread.start()
    
    return jsonify({"status": "started"})

@app.route('/api/stream')
def stream():
    """Server-Sent Events stream for real-time updates"""
    def event_stream():
        while True:
            try:
                message = message_queue.get(timeout=30)
                yield f"data: {json.dumps(message)}\n\n"
            except queue.Empty:
                # Send keepalive
                yield f"data: {json.dumps({'type': 'keepalive'})}\n\n"
    
    return Response(event_stream(), mimetype="text/event-stream")

if __name__ == '__main__':
    try:
        validate_config()
        print("Configuration validated successfully!")
        print(f"GitHub Repo: {GITHUB_REPO}")
        print(f"Railway Project: {RAILWAY_PROJECT_ID}")
        print("\nStarting server on http://localhost:5000")
        app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)
    except ValueError as e:
        print(f"Configuration error: {str(e)}")
        exit(1)
