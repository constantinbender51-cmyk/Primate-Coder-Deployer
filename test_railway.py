#!/usr/bin/env python3
"""
Test script to diagnose Railway API connectivity issues
Run this to check if your Railway configuration is correct
"""

from config import validate_config
from railway_manager import RailwayManager

def main():
    print("=" * 60)
    print("Railway API Diagnostic Tool")
    print("=" * 60)
    
    # Validate configuration
    print("\n1. Validating configuration...")
    try:
        validate_config()
        print("✓ Configuration validated")
    except ValueError as e:
        print(f"✗ Configuration error: {e}")
        return
    
    # Test Railway connection
    print("\n2. Testing Railway API connection...")
    railway = RailwayManager()
    railway.test_connection()
    
    # Try to get latest deployment
    print("\n3. Fetching latest deployment...")
    try:
        deployment = railway.get_latest_deployment()
        if deployment:
            print(f"✓ Found deployment: {deployment['id']}")
            print(f"  Status: {deployment['status']}")
            print(f"  Created: {deployment.get('createdAt', 'N/A')}")
            
            # Try to get logs
            print("\n4. Fetching deployment logs...")
            logs = railway.get_deployment_logs(deployment['id'])
            if logs:
                print(f"✓ Retrieved {len(logs)} log entries")
                print("\nFirst 5 log entries:")
                for i, log in enumerate(logs[:5], 1):
                    msg = log.get('message', str(log))
                    print(f"  {i}. {msg[:100]}...")
            else:
                print("⚠ No logs found (deployment may not have logs yet)")
        else:
            print("⚠ No deployments found")
            print("\nPossible reasons:")
            print("  - Project has never been deployed")
            print("  - Incorrect project ID")
            print("  - API key doesn't have access to this project")
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("Diagnostic complete!")
    print("=" * 60)

if __name__ == "__main__":
    main()
