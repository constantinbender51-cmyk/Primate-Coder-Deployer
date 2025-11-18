import requests
import time
import json
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
            print(f"Sending Railway API request...")
            print(f"Endpoint: {self.api_url}")
            print(f"Variables: {json.dumps(variables, indent=2)}")
            
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            print(f"Railway API Status Code: {response.status_code}")
            
            response.raise_for_status()
            result = response.json()
            
            return result
            
        except requests.exceptions.RequestException as e:
            error_detail = ""
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = f" Response: {e.response.text}"
                except:
                    pass
            raise Exception(f"Railway API error: {str(e)}{error_detail}")
    
    def get_latest_deployment(self):
        """Get the latest deployment for the project"""
        # Try multiple query variations for Railway API compatibility
        queries = [
            # Query variation 1: Standard structure
            """
            query GetDeployments($projectId: String!) {
                project(id: $projectId) {
                    deployments(first: 1, orderBy: {field: CREATED_AT, direction: DESC}) {
                        edges {
                            node {
                                id
                                status
                                createdAt
                            }
                        }
                    }
                }
            }
            """,
            # Query variation 2: Simplified structure
            """
            query GetDeployments($projectId: String!) {
                deployments(first: 1, input: {projectId: $projectId}) {
                    edges {
                        node {
                            id
                            status
                            createdAt
                        }
                    }
                }
            }
            """,
            # Query variation 3: Direct project query
            """
            query GetProject($projectId: String!) {
                project(id: $projectId) {
                    id
                    name
                    deployments(first: 5) {
                        edges {
                            node {
                                id
                                status
                                createdAt
                            }
                        }
                    }
                }
            }
            """
        ]
        
        variables = {"projectId": self.project_id}
        last_error = None
        
        for i, query in enumerate(queries):
            try:
                print(f"Trying Railway API query variation {i+1}...")
                result = self.graphql_query(query, variables)
                
                # Log the raw response for debugging
                print(f"Railway API Response: {json.dumps(result, indent=2)}")
                
                if "errors" in result:
                    error_msg = json.dumps(result['errors'], indent=2)
                    print(f"GraphQL errors in query {i+1}: {error_msg}")
                    last_error = f"GraphQL errors: {error_msg}"
                    continue
                
                # Try to extract deployments from various response structures
                deployments = None
                
                # Structure 1: data.project.deployments.edges
                if "data" in result and result["data"]:
                    if "project" in result["data"] and result["data"]["project"]:
                        project_data = result["data"]["project"]
                        if "deployments" in project_data:
                            deployments = project_data["deployments"].get("edges", [])
                    # Structure 2: data.deployments.edges
                    elif "deployments" in result["data"]:
                        deployments = result["data"]["deployments"].get("edges", [])
                
                if deployments and len(deployments) > 0:
                    deployment = deployments[0]["node"]
                    print(f"Found deployment: {deployment['id']} with status {deployment['status']}")
                    return deployment
                else:
                    print(f"No deployments found in query {i+1}")
                    last_error = "No deployments found in response"
                    continue
                    
            except Exception as e:
                print(f"Error with query variation {i+1}: {str(e)}")
                last_error = str(e)
                continue
        
        # If all queries failed, raise the last error
        if last_error:
            raise Exception(f"Failed to get deployment after trying all query variations: {last_error}")
        
        return None
    
    def get_deployment_logs(self, deployment_id):
        """Get logs for a specific deployment"""
        # Try multiple query structures for logs
        queries = [
            # Query 1: Standard deploymentLogs
            """
            query GetDeploymentLogs($deploymentId: String!) {
                deploymentLogs(deploymentId: $deploymentId, limit: 1000) {
                    message
                    timestamp
                }
            }
            """,
            # Query 2: Logs within deployment
            """
            query GetDeployment($deploymentId: String!) {
                deployment(id: $deploymentId) {
                    logs {
                        message
                        timestamp
                    }
                }
            }
            """,
            # Query 3: Build logs
            """
            query GetDeployment($deploymentId: String!) {
                deployment(id: $deploymentId) {
                    buildLogs
                    deployLogs
                }
            }
            """
        ]
        
        variables = {"deploymentId": deployment_id}
        
        for i, query in enumerate(queries):
            try:
                print(f"Fetching logs with query variation {i+1}...")
                result = self.graphql_query(query, variables)
                
                if "errors" in result:
                    print(f"Log query {i+1} errors: {result['errors']}")
                    continue
                
                # Try to extract logs from different structures
                logs = []
                
                if "data" in result:
                    # Structure 1: deploymentLogs array
                    if "deploymentLogs" in result["data"]:
                        logs = result["data"]["deploymentLogs"]
                    # Structure 2: deployment.logs
                    elif "deployment" in result["data"] and result["data"]["deployment"]:
                        deployment = result["data"]["deployment"]
                        if "logs" in deployment:
                            logs = deployment["logs"]
                        elif "buildLogs" in deployment:
                            # Convert string logs to structured format
                            build_logs = deployment.get("buildLogs", "")
                            deploy_logs = deployment.get("deployLogs", "")
                            combined = f"{build_logs}\n{deploy_logs}"
                            logs = [{"message": line, "timestamp": ""} for line in combined.split("\n") if line.strip()]
                
                if logs:
                    print(f"Successfully retrieved {len(logs)} log entries")
                    return logs
                    
            except Exception as e:
                print(f"Error fetching logs with query {i+1}: {str(e)}")
                continue
        
        print("Could not retrieve logs from any query variation")
        return []
    
    def wait_for_deployment(self, initial_deployment_id=None):
        """
        Wait for a deployment to complete and return its status and logs.
        Returns: (status, logs, deployment_id)
        """
        start_time = time.time()
        last_deployment_id = initial_deployment_id
        last_status = None
        poll_count = 0
        
        print(f"Waiting for Railway deployment...")
        print(f"Timeout: {DEPLOYMENT_TIMEOUT} seconds")
        print(f"Poll interval: {DEPLOYMENT_POLL_INTERVAL} seconds")
        
        while time.time() - start_time < DEPLOYMENT_TIMEOUT:
            poll_count += 1
            print(f"\n--- Poll #{poll_count} (elapsed: {int(time.time() - start_time)}s) ---")
            
            try:
                deployment = self.get_latest_deployment()
                
                if not deployment:
                    print("No deployment found, waiting...")
                    time.sleep(DEPLOYMENT_POLL_INTERVAL)
                    continue
                
                deployment_id = deployment["id"]
                status = deployment["status"]
                
                print(f"Deployment ID: {deployment_id}")
                print(f"Status: {status}")
                
                # Track status changes
                if status != last_status:
                    print(f"Status changed: {last_status} -> {status}")
                    last_status = status
                
                # If we have a new deployment, update tracking
                if deployment_id != last_deployment_id:
                    print(f"New deployment detected!")
                    print(f"Previous: {last_deployment_id}")
                    print(f"Current: {deployment_id}")
                    last_deployment_id = deployment_id
                    last_status = status
                
                # Check if deployment is complete
                # Railway statuses: INITIALIZING, BUILDING, DEPLOYING, SUCCESS, FAILED, CRASHED, REMOVED
                terminal_statuses = ["SUCCESS", "FAILED", "CRASHED", "REMOVED"]
                
                if status in terminal_statuses:
                    print(f"Deployment reached terminal status: {status}")
                    logs = self.get_deployment_logs(deployment_id)
                    log_messages = [log.get("message", str(log)) for log in logs]
                    return status, log_messages, deployment_id
                
                # Still deploying
                print(f"Deployment in progress ({status}), waiting {DEPLOYMENT_POLL_INTERVAL}s...")
                time.sleep(DEPLOYMENT_POLL_INTERVAL)
                
            except Exception as e:
                print(f"Error checking deployment: {str(e)}")
                import traceback
                traceback.print_exc()
                time.sleep(DEPLOYMENT_POLL_INTERVAL)
        
        # Timeout reached
        print(f"Deployment timed out after {DEPLOYMENT_TIMEOUT} seconds ({poll_count} polls)")
        return "TIMEOUT", [f"Deployment monitoring timed out after {DEPLOYMENT_TIMEOUT} seconds"], last_deployment_id
    
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
    
    def test_connection(self):
        """Test Railway API connection and print diagnostic info"""
        print("\n=== Railway API Connection Test ===")
        print(f"API URL: {self.api_url}")
        print(f"Project ID: {self.project_id}")
        print(f"API Key present: {bool(self.api_key)}")
        print(f"API Key length: {len(self.api_key) if self.api_key else 0}")
        
        try:
            # Test simple query
            query = """
            query {
                me {
                    id
                    email
                }
            }
            """
            result = self.graphql_query(query, {})
            print("\n✓ API Authentication successful!")
            if "data" in result and "me" in result["data"]:
                print(f"Authenticated as: {result['data']['me'].get('email', 'N/A')}")
            
            # Try to get project info
            print("\nTesting project access...")
            deployment = self.get_latest_deployment()
            if deployment:
                print(f"✓ Successfully accessed project deployments!")
                print(f"Latest deployment: {deployment['id']}")
                print(f"Status: {deployment['status']}")
            else:
                print("⚠ No deployments found (this is OK if project is new)")
                
        except Exception as e:
            print(f"\n✗ Connection test failed: {str(e)}")
            import traceback
            traceback.print_exc()
