import requests
import time
from config import RAILWAY_API_KEY, RAILWAY_API_URL, RAILWAY_PROJECT_ID, DEPLOYMENT_POLL_INTERVAL, DEPLOYMENT_TIMEOUT

class RailwayManager:
    def __init__(self):
        self.api_key = RAILWAY_API_KEY
        self.api_url = RAILWAY_API_URL
        self.project_id = RAILWAY_PROJECT_ID
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def graphql_query(self, query, variables=None):
        """Execute a GraphQL query against Railway API"""
        payload = {
            "query": query,
            "variables": variables or {}
        }
        
        try:
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"Railway API error: {str(e)}")
    
    def get_latest_deployment(self):
        """Get the latest deployment for the project"""
        query = """
        query GetDeployments($projectId: String!) {
            project(id: $projectId) {
                deployments(first: 1) {
                    edges {
                        node {
                            id
                            status
                            createdAt
                            meta
                        }
                    }
                }
            }
        }
        """
        
        variables = {"projectId": self.project_id}
        
        try:
            result = self.graphql_query(query, variables)
            
            if "errors" in result:
                raise Exception(f"GraphQL errors: {result['errors']}")
            
            deployments = result.get("data", {}).get("project", {}).get("deployments", {}).get("edges", [])
            
            if not deployments:
                return None
            
            return deployments[0]["node"]
            
        except Exception as e:
            raise Exception(f"Failed to get deployment: {str(e)}")
    
    def get_deployment_logs(self, deployment_id):
        """Get logs for a specific deployment"""
        query = """
        query GetDeploymentLogs($deploymentId: String!) {
            deploymentLogs(deploymentId: $deploymentId, limit: 1000) {
                message
                timestamp
            }
        }
        """
        
        variables = {"deploymentId": deployment_id}
        
        try:
            result = self.graphql_query(query, variables)
            
            if "errors" in result:
                return []
            
            logs = result.get("data", {}).get("deploymentLogs", [])
            return logs
            
        except Exception as e:
            return []
    
    def wait_for_deployment(self, initial_deployment_id=None):
        """
        Wait for a deployment to complete and return its status and logs.
        Returns: (status, logs, deployment_id)
        """
        start_time = time.time()
        last_deployment_id = initial_deployment_id
        
        print(f"Waiting for Railway deployment...")
        
        while time.time() - start_time < DEPLOYMENT_TIMEOUT:
            try:
                deployment = self.get_latest_deployment()
                
                if not deployment:
                    time.sleep(DEPLOYMENT_POLL_INTERVAL)
                    continue
                
                deployment_id = deployment["id"]
                status = deployment["status"]
                
                # If we have a new deployment, update tracking
                if deployment_id != last_deployment_id:
                    print(f"New deployment detected: {deployment_id}")
                    last_deployment_id = deployment_id
                
                print(f"Deployment status: {status}")
                
                # Check if deployment is complete
                if status in ["SUCCESS", "FAILED", "CRASHED"]:
                    logs = self.get_deployment_logs(deployment_id)
                    log_messages = [log["message"] for log in logs]
                    return status, log_messages, deployment_id
                
                # Still deploying
                time.sleep(DEPLOYMENT_POLL_INTERVAL)
                
            except Exception as e:
                print(f"Error checking deployment: {str(e)}")
                time.sleep(DEPLOYMENT_POLL_INTERVAL)
        
        # Timeout reached
        return "TIMEOUT", ["Deployment timed out after 10 minutes"], last_deployment_id
    
    def trigger_deployment(self):
        """
        Trigger a new deployment (if Railway doesn't auto-deploy from GitHub).
        Note: Railway typically auto-deploys on push, so this may not be necessary.
        """
        query = """
        mutation DeploymentTrigger($projectId: String!) {
            deploymentTrigger(input: {projectId: $projectId}) {
                id
            }
        }
        """
        
        variables = {"projectId": self.project_id}
        
        try:
            result = self.graphql_query(query, variables)
            
            if "errors" in result:
                raise Exception(f"Failed to trigger deployment: {result['errors']}")
            
            deployment_id = result.get("data", {}).get("deploymentTrigger", {}).get("id")
            return deployment_id
            
        except Exception as e:
            # Railway might auto-deploy, so this failing is okay
            print(f"Note: Could not manually trigger deployment: {str(e)}")
            return None
    
    def format_logs_for_prompt(self, logs):
        """Format deployment logs for DeepSeek prompt"""
        if not logs:
            return "No logs available."
        
        formatted = []
        for i, log in enumerate(logs[-100:], 1):  # Last 100 logs
            formatted.append(f"{i}. {log}")
        
        return "\n".join(formatted)
