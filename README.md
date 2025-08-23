# InterviewHero - AI-Powered Recruitment Automation System

🤖 **Work Smarter, Hire Better** - An intelligent multi-agent system that automates the entire recruitment workflow from CV analysis to interview scheduling.

## ✨ Features

- **🔍 AI CV Analysis**: Automatically extract and analyze candidate CVs from PDF uploads
- **📧 Smart Email Automation**: Send personalized interview invitations and monitor responses
- **🤖 Multi-Agent System**: Coordinated AI agents for different recruitment tasks
- **📅 Auto-Scheduling**: Automatically schedule interviews based on candidate availability
- **📝 Interview Question Generation**: Create personalized interview questions based on CV analysis
- **📊 Real-time Dashboard**: Monitor recruitment workflows and agent activities
- **🎭 Interview Analysis**: AI-powered analysis of interview conversations
- **🔄 Gmail Integration**: Seamless integration with Gmail for email management

## 🏗️ Architecture

The system uses a multi-agent architecture with specialized agents:

- **CV Analyzer Agent**: Processes and analyzes candidate CVs
- **Email Monitor Agent**: Watches for candidate email responses
- **Scheduler Agent**: Handles interview scheduling and calendar management
- **Interview Analyzer Agent**: Evaluates interview performance
- **Coordinator Agent**: Orchestrates workflows between agents

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Gmail Account with API access
- OpenAI/Azure OpenAI API access
- Google Cloud Console project

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/InterviewHero.git
cd InterviewHero

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Gmail API Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable the Gmail API
4. Create credentials (OAuth 2.0 Client ID)
5. Download the credentials file as `app/credentials.json`

### 3. OpenAI API Setup

Create `.env` file in project root:

```env
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here

# Or for Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your_azure_api_key_here
AZURE_OPENAI_DEPLOYMENT=your_deployment_name
```

### 4. Run the Application

```bash
# Start the FastAPI server
uvicorn app.main:app --reload

# In another terminal, start the Streamlit dashboard
streamlit run streamlit_dashboard.py
```

## 📖 How to Use

### Option 1: Streamlit Dashboard (Recommended)

1. **Open Dashboard**: Navigate to `http://localhost:8501`
2. **Start Agent System**: Go to "Agent Control" and click "Start Agents"
3. **Upload CV**: 
   - Go to "Candidate Screening"
   - Fill in candidate details (name, email, position)
   - Upload PDF CV file
   - Click "Start Screening Workflow"
4. **Monitor Progress**: Check "Workflow Status" to see real-time progress
5. **Email Automation**: The system will automatically:
   - Analyze the CV
   - Send interview invitation to candidate
   - Monitor for candidate replies
   - Schedule interviews when candidates respond

### Option 2: Direct API Usage

#### Step 1: Start Email Monitor

```bash
curl -X POST http://localhost:8000/monitor/start
```

#### Step 2: Upload and Analyze CV

```bash
curl -X POST http://localhost:8000/cv/analyze-pdf \
  -F "file=@candidate_cv.pdf" \
  -F "candidate_email=candidate@example.com"
```

#### Step 3: Check Status

```bash
# Check agent system status
curl http://localhost:8000/agents/status

# Check workflow status
curl http://localhost:8000/agents/workflows/active

# Get interview questions for a candidate
curl http://localhost:8000/agents/interview-questions/candidate@example.com
```

## 🔄 Complete Workflow

1. **CV Upload & Analysis**
   - Upload candidate CV (PDF format)
   - AI extracts and analyzes skills, experience, education
   - Generates personalized interview questions
   - Calculates job match score

2. **Automated Email Outreach**
   - Sends professional interview invitation
   - Asks for 2-3 available time slots
   - Tracks email thread for monitoring

3. **Smart Response Processing**
   - Monitors Gmail for candidate replies
   - AI parses availability information
   - Extracts dates, times, and timezone preferences

4. **Auto-Scheduling**
   - Selects best available time slot
   - Generates Google Meet link
   - Sends meeting confirmation with details
   - Removes thread from monitoring

5. **Interview Management**
   - Provides HR with personalized interview guide
   - Tracks interview progress
   - Analyzes interview conversations (optional)

## 📊 API Endpoints

### Core Endpoints

- `POST /cv/analyze-pdf` - Upload and analyze CV
- `POST /schedule/request-availability` - Send availability request
- `POST /schedule/schedule-meeting` - Schedule interview
- `GET /schedule/check-responses` - Check email responses

### Agent System

- `GET /agents/status` - System status
- `POST /agents/start` - Start agent system  
- `POST /agents/stop` - Stop agent system
- `GET /agents/workflows/active` - Active workflows
- `GET /agents/interview-questions/{email}` - Get interview questions

### Email Monitor

- `POST /monitor/start` - Start email monitoring
- `POST /monitor/stop` - Stop email monitoring
- `GET /monitor/status` - Monitor status

## 🎛️ Configuration

### Email Templates

The system uses professional email templates that can be customized in:
- `app/core/agent_manager.py` - Availability request template
- `app/agents/scheduling_agent.py` - Meeting confirmation template

### AI Prompts

Customize AI behavior by modifying prompts in:
- `app/services/openai_client.py` - CV analysis and email parsing
- `app/core/agent_manager.py` - Interview question generation

### Monitoring Settings

Configure monitoring behavior in `app/core/agent_manager.py`:
- Check frequency (default: 60 seconds)
- Thread timeout settings
- Response parsing confidence thresholds

## 🔧 Troubleshooting

### Common Issues

**Gmail Authentication Failed**
```bash
# Remove old token and re-authenticate
rm app/token.json
# Restart the application
```

**Email Monitor Not Working**
```bash
# Check monitor status
curl http://localhost:8000/monitor/status

# Restart monitor
curl -X POST http://localhost:8000/monitor/stop
curl -X POST http://localhost:8000/monitor/start
```

**Agent System Issues**
```bash
# Check system status
curl http://localhost:8000/agents/status

# Restart agents
curl -X POST http://localhost:8000/agents/stop
curl -X POST http://localhost:8000/agents/start
```

### Logs and Debugging

- Check FastAPI logs in terminal where uvicorn is running
- Monitor email processing in real-time via dashboard
- Use `GET /agents/status` to see detailed agent information

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- OpenAI/Azure OpenAI for AI capabilities
- Gmail API for email integration
- FastAPI for the robust backend framework
- Streamlit for the intuitive dashboard interface

---

**Need Help?** 
- 📧 Open an issue for bug reports
- 💡 Submit feature requests via GitHub Issues
- 📖 Check the documentation for detailed guides

**Made with ❤️ using AI-powered automation**
