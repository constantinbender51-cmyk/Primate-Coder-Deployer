import os
from dotenv import load_dotenv

load_dotenv()

# Repository Configuration (EDIT THESE)
GITHUB_REPO = "constantinbender51-cmyk/Primate-Coder-Deployment"  # Format: "owner/repo"
RAILWAY_PROJECT_ID = "efd69085-b9c0-44c3-aa01-f7a28b1c5118"
DEFAULT_BRANCH = "main"

# API Keys (from environment variables)
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
RAILWAY_API_KEY = os.getenv("RAILWAY_API_KEY")

# API Endpoints
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
GITHUB_API_URL = "https://api.github.com"
RAILWAY_API_URL = "https://backboard.railway.app/graphql"

# Deployment Settings
DEPLOYMENT_POLL_INTERVAL = 10  # seconds
DEPLOYMENT_TIMEOUT = 600  # 10 minutes max wait

# DeepSeek Model
DEEPSEEK_MODEL = "deepseek-coder"

# Validate configuration
def validate_config():
    missing = []
    if not DEEPSEEK_API_KEY:
        missing.append("DEEPSEEK_API_KEY")
    if not GITHUB_TOKEN:
        missing.append("GITHUB_TOKEN")
    if not RAILWAY_API_KEY:
        missing.append("RAILWAY_API_KEY")
    
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
    
    if GITHUB_REPO == "username/repository-name":
        raise ValueError("Please update GITHUB_REPO in config.py")
    
    if RAILWAY_PROJECT_ID == "your-railway-project-id":
        raise ValueError("Please update RAILWAY_PROJECT_ID in config.py")

if __name__ == "__main__":
    validate_config()
    print("Configuration validated successfully!")
