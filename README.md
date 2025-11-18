# DeepSeek Code Assistant

An automated system that uses DeepSeek AI to write, deploy, and verify code through a web interface. The system integrates with GitHub for version control and Railway for automated deployment.

## Features

- 🤖 **AI-Powered Coding**: DeepSeek writes code based on natural language descriptions
- 📝 **Precise File Operations**: Create, update, insert, delete files and specific lines
- 🔄 **Automatic Verification**: DeepSeek verifies code before and after deployment
- 🚀 **Railway Integration**: Automatic deployment and monitoring
- 📊 **Real-time Monitoring**: Live updates of all processes via web interface
- 🔍 **Error Handling**: Automatic retry with AI-generated fixes

## Architecture

```
User Request → DeepSeek (Code Generation) → GitHub (Version Control) 
    → Railway (Deployment) → DeepSeek (Verification) → Success/Retry
```

## Setup

### 1. Prerequisites

- Python 3.8+
- GitHub account with a repository
- Railway account with a project linked to your GitHub repo
- DeepSeek API access

### 2. Installation

```bash
# Clone or create project directory
mkdir deepseek-coder
cd deepseek-coder

# Install dependencies
pip install -r requirements.txt

# Create templates directory
mkdir templates
```

### 3. Configuration

1. **Copy environment file:**
```bash
cp .env.example .env
```

2. **Edit `.env` with your API keys:**
```env
DEEPSEEK_API_KEY=your_deepseek_api_key
GITHUB_TOKEN=your_github_personal_access_token
RAILWAY_API_KEY=your_railway_api_token
```

3. **Edit `config.py`:**
```python
GITHUB_REPO = "yourusername/your-repo"
RAILWAY_PROJECT_ID = "your-railway-project-id"
```

### 4. Get API Keys

**GitHub Token:**
1. Go to GitHub Settings → Developer settings → Personal access tokens
2. Generate new token with `repo` scope
3. Copy the token to `.env`

**Railway API Token:**
1. Go to Railway dashboard → Account Settings → Tokens
2. Create new token
3. Copy to `.env`

**Railway Project ID:**
1. Open your Railway project
2. Go to Settings
3. Copy the Project ID

**DeepSeek API Key:**
1. Sign up at DeepSeek
2. Get your API key from the dashboard
3. Copy to `.env`

## Usage

### Start the Server

```bash
python app.py
```

The web interface will be available at `http://localhost:5000`

### Using the Interface

1. **Enter your request** in natural language:
   ```
   Create a Flask API with endpoints for user management:
   - POST /api/users - Create user
   - GET /api/users - List all users
   - GET /api/users/<id> - Get specific user
   Store data in a JSON file.
   ```

2. **Click "Generate & Deploy Code"**

3. **Monitor the process:**
   - Process Log: Shows all operations and status updates
   - DeepSeek Responses: Shows AI's code generation and analysis

4. **Wait for completion:**
   - Code is generated
   - Changes are applied to GitHub
   - Railway automatically deploys
   - DeepSeek verifies the deployment
   - If errors occur, DeepSeek automatically fixes them

## File Operations

DeepSeek can perform these operations:

### Create File
```json
{
  "operation": "CREATE_FILE",
  "path": "app.py",
  "content": "print('Hello World')"
}
```

### Overwrite File
```json
{
  "operation": "OVERWRITE_FILE",
  "path": "app.py",
  "content": "print('New content')"
}
```

### Insert Lines
```json
{
  "operation": "INSERT_LINES",
  "path": "app.py",
  "line": 5,
  "content": "# New comment\nprint('inserted')"
}
```

### Delete File
```json
{
  "operation": "DELETE_FILE",
  "path": "old_file.py"
}
```

### Delete Lines
```json
{
  "operation": "DELETE_LINES",
  "path": "app.py",
  "start_line": 10,
  "end_line": 15
}
```

### Multiple Operations
```json
{
  "operations": [
    {"operation": "CREATE_FILE", "path": "new.py", "content": "..."},
    {"operation": "INSERT_LINES", "path": "main.py", "line": 1, "content": "..."}
  ]
}
```

## Project Structure

```
deepseek-coder/
├── app.py                  # Main Flask application
├── config.py              # Configuration settings
├── deepseek_client.py     # DeepSeek API client
├── github_manager.py      # GitHub operations
├── railway_manager.py     # Railway deployment monitoring
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables (create from .env.example)
├── .env.example          # Example environment file
├── README.md             # This file
└── templates/
    └── index.html        # Web interface
```

## How It Works

1. **Fetch Codebase**: Retrieves all files from GitHub with line numbers
2. **Send to DeepSeek**: Includes full codebase context in prompt
3. **Generate Code**: DeepSeek writes/modifies code with specific operations
4. **Apply Changes**: Operations are executed on GitHub
5. **Pre-Verification**: DeepSeek reviews changes before deployment
6. **Deploy**: Railway automatically deploys from GitHub
7. **Monitor**: System waits for deployment completion
8. **Post-Verification**: DeepSeek reviews logs and confirms success
9. **Error Recovery**: If issues found, DeepSeek generates fixes and retries

## Troubleshooting

### Configuration Errors
- Ensure all API keys are set in `.env`
- Verify `GITHUB_REPO` format is `owner/repo`
- Check Railway Project ID is correct

### Deployment Issues
- Ensure Railway is linked to your GitHub repository
- Check that Railway has auto-deploy enabled
- Verify your repository has proper deployment configuration

### Line Number Errors
- The system uses 1-indexed line numbers (first line is 1)
- INSERT_LINES inserts BEFORE the specified line
- Check current codebase in the interface to verify line numbers

## Advanced Usage

### Custom Deployment Timeout
Edit `config.py`:
```python
DEPLOYMENT_TIMEOUT = 900  # 15 minutes
```

### Custom Polling Interval
```python
DEPLOYMENT_POLL_INTERVAL = 5  # Check every 5 seconds
```

### Using Different DeepSeek Models
```python
DEEPSEEK_MODEL = "deepseek-coder"  # or other available models
```

## Security Notes

- Never commit `.env` file to version control
- Keep API keys secure
- Use GitHub tokens with minimal required permissions
- Consider using environment-specific configurations

## License

MIT License - Feel free to use and modify as needed.
