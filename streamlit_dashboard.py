import streamlit as st
import requests
import json
import pandas as pd
from datetime import datetime
import time

# Configuration
API_BASE_URL = "http://127.0.0.1:8000"

# Page configuration
st.set_page_config(
    page_title="InterviewHero – Work Smarter, Hire Better - Dashboard",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        padding: 2rem 0;
        text-align: center;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 10px;
        margin-bottom: 2rem;
    }
    .metric-container {
        background: white;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #667eea;
        margin: 0.5rem 0;
    }
    .status-running {
        background-color: #d4edda;
        border-left: 4px solid #28a745;
    }
    .status-stopped {
        background-color: #f8d7da;
        border-left: 4px solid #dc3545;
    }
    .agent-card {
        border: 1px solid #ddd;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
        background: white;
    }
</style>
""", unsafe_allow_html=True)

def make_api_request(endpoint, method="GET", data=None):
    """Make API request with error handling"""
    try:
        url = f"{API_BASE_URL}/{endpoint}" if not endpoint.startswith('/') else f"{API_BASE_URL}{endpoint}"
        if method == "GET":
            response = requests.get(url)
        elif method == "POST":
            response = requests.post(url, json=data)
        
        if response.status_code == 200:
            return response.json(), None
        else:
            return None, f"Error {response.status_code}: {response.text}"
    except Exception as e:
        return None, f"Connection error: {str(e)}"

def get_system_status():
    """Get system status"""
    return make_api_request("/agents/status")

def get_active_workflows():
    """Get active workflows"""
    return make_api_request("/agents/workflows/active")

def start_agents():
    """Start the agent system"""
    return make_api_request("/agents/start", method="POST")

def stop_agents():
    """Stop the agent system"""
    return make_api_request("/agents/stop", method="POST")

def start_candidate_screening(candidate_data):
    """Start candidate screening workflow"""
    return make_api_request("/agents/workflows/candidate-screening", method="POST", data=candidate_data)

def get_interview_questions(candidate_email):
    """Get interview questions for a candidate"""
    return make_api_request(f"/agents/interview-questions/{candidate_email}")

def main():
    # Header
    st.markdown("""
    <div class="main-header">
        <h1>🤖 InterviewHero – Work Smarter, Hire Better - Dashboard</h1>
        <p>Control and monitor your intelligent recruitment agents</p>
    </div>
    """, unsafe_allow_html=True)

    # Sidebar
    st.sidebar.title("Navigation")
    page = st.sidebar.selectbox(
        "Choose a page",
        ["🏠 Dashboard", "👥 Agent Control", "📝 Candidate Screening", "📊 Workflow Status", "❓ Interview Questions", "🎭 Interview Analysis"]
    )

    if page == "🏠 Dashboard":
        show_dashboard()
    elif page == "👥 Agent Control":
        show_agent_control()
    elif page == "📝 Candidate Screening":
        show_candidate_screening()
    elif page == "📊 Workflow Status":
        show_workflow_status()
    elif page == "❓ Interview Questions":
        show_interview_questions()
    elif page == "🎭 Interview Analysis":
        show_interview_analysis()

def show_dashboard():
    """Main dashboard overview"""
    st.header("📊 System Overview")
    
    # Get system status
    status, error = get_system_status()
    
    if error:
        st.error(f"❌ Unable to connect to the agent system: {error}")
        st.info("Make sure the FastAPI server is running: `uvicorn app.main:app --reload`")
        return
    
    # System status metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        is_running = status.get('system_status', {}).get('is_running', False)
        st.metric(
            "System Status", 
            "🟢 Running" if is_running else "🔴 Stopped",
            delta="Active" if is_running else "Inactive"
        )
    
    with col2:
        total_messages = status.get('system_status', {}).get('total_messages', 0)
        st.metric("Total Messages", total_messages)
    
    with col3:
        active_tasks = status.get('system_status', {}).get('active_tasks', 0)
        st.metric("Active Tasks", active_tasks)
    
    with col4:
        agents = status.get('system_status', {}).get('agents', {})
        active_agents = sum(1 for agent in agents.values() if agent.get('active', False))
        st.metric("Active Agents", f"{active_agents}/{len(agents)}")
    
    # Agent status
    st.subheader("🤖 Agent Status")
    
    if agents:
        for agent_name, agent_info in agents.items():
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                status_icon = "🟢" if agent_info.get('active', False) else "🔴"
                st.write(f"{status_icon} **{agent_name.title().replace('_', ' ')}**")
            
            with col2:
                st.write(f"Queue: {agent_info.get('queue_size', 0)}")
            
            with col3:
                st.write("Active" if agent_info.get('active', False) else "Inactive")
    
    # Recent activity
    st.subheader("📈 Quick Stats")
    workflows, _ = get_active_workflows()
    if workflows:
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("Active Workflows", workflows.get('active_workflows', 0))
        
        with col2:
            st.metric("Total Tasks", workflows.get('total_tasks', 0))

def show_agent_control():
    """Agent control interface"""
    st.header("👥 Agent System Control")
    
    # Get current status
    status, error = get_system_status()
    
    if error:
        st.error(f"❌ Unable to connect: {error}")
        return
    
    is_running = status.get('system_status', {}).get('is_running', False)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("System Control")
        
        if is_running:
            st.success("✅ Agent system is running")
            if st.button("🛑 Stop Agents", type="secondary"):
                with st.spinner("Stopping agents..."):
                    result, error = stop_agents()
                    if error:
                        st.error(f"❌ Failed to stop: {error}")
                    else:
                        st.success("✅ Agents stopped successfully!")
                        st.rerun()
        else:
            st.warning("⚠️ Agent system is stopped")
            if st.button("🚀 Start Agents", type="primary"):
                with st.spinner("Starting agents..."):
                    result, error = start_agents()
                    if error:
                        st.error(f"❌ Failed to start: {error}")
                    else:
                        st.success("✅ Agents started successfully!")
                        st.rerun()
    
    with col2:
        st.subheader("System Information")
        if status:
            st.json(status)

def show_candidate_screening():
    """Candidate screening form"""
    st.header("📝 Candidate Screening Workflow")
    
    # Check if system is running
    status, error = get_system_status()
    if error or not status.get('system_status', {}).get('is_running', False):
        st.warning("⚠️ Agent system must be running to start workflows. Go to Agent Control to start it.")
        return
    
    st.info("Fill out the form below to start a candidate screening workflow")
    
    with st.form("candidate_screening_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            candidate_name = st.text_input("👤 Candidate Name", placeholder="e.g., John Doe")
            candidate_email = st.text_input("📧 Candidate Email", placeholder="john.doe@example.com")
            position_title = st.text_input("💼 Position Title", value="Software Engineer")
        
        with col2:
            job_description = st.text_area("📋 Job Description (Optional)", 
                                         placeholder="Brief description of the role and requirements...")
        
        st.subheader("📄 CV Upload")
        cv_upload_method = st.radio(
            "Choose CV input method:",
            ["📁 Upload PDF File", "📝 Paste Text"],
            horizontal=True
        )
        
        cv_file = None
        cv_text = ""
        
        if cv_upload_method == "📁 Upload PDF File":
            cv_file = st.file_uploader(
                "Upload Candidate's CV (PDF)", 
                type=['pdf'],
                help="Upload a PDF file containing the candidate's CV. The system will automatically extract text and analyze it."
            )
        else:
            cv_text = st.text_area(
                "📄 CV Text", 
                placeholder="Paste the candidate's CV content here...",
                height=200
            )
        
        submitted = st.form_submit_button("🚀 Start Screening Workflow", type="primary")
        
        if submitted:
            if not candidate_name or not candidate_email:
                st.error("❌ Please provide candidate name and email")
            elif cv_upload_method == "📁 Upload PDF File" and cv_file is None:
                st.error("❌ Please upload a PDF CV file")
            elif cv_upload_method == "📝 Paste Text" and not cv_text.strip():
                st.error("❌ Please provide CV text")
            else:
                # Handle PDF CV upload
                if cv_upload_method == "📁 Upload PDF File" and cv_file is not None:
                    with st.spinner("📄 Extracting text from PDF and analyzing CV..."):
                        try:
                            # Upload PDF to the CV analysis endpoint
                            files = {"file": (cv_file.name, cv_file.getvalue(), "application/pdf")}
                            data = {"candidate_email": candidate_email}
                            
                            import requests
                            response = requests.post(
                                f"{API_BASE_URL}/cv/analyze-pdf",
                                files=files,
                                data=data
                            )
                            
                            if response.status_code == 200:
                                pdf_result = response.json()
                                st.success(f"✅ PDF processed successfully!")
                                st.info(f"📊 Extracted {pdf_result['text_length']} characters from {pdf_result['pdf_info']['pages']} page(s)")
                                
                                # Show task ID and status
                                task_id = pdf_result.get('task_id')
                                if task_id:
                                    st.success("🔄 CV analysis and interview question generation started!")
                                    st.info(f"📋 Task ID: `{task_id}`")
                                    st.info("Check the Workflow Status page to monitor the analysis progress.")
                                    
                                    # Show PDF details
                                    with st.expander("📄 PDF Details"):
                                        st.json(pdf_result['pdf_info'])
                                
                                return  # Exit early as PDF processing is complete
                            else:
                                error_detail = response.json().get('detail', response.text) if response.headers.get('content-type', '').startswith('application/json') else response.text
                                st.error(f"❌ PDF processing failed: {error_detail}")
                                return
                                
                        except Exception as e:
                            st.error(f"❌ Error processing PDF: {str(e)}")
                            return
                
                # Handle text-based CV (original workflow)
                candidate_data = {
                    "candidate_name": candidate_name,
                    "candidate_email": candidate_email,
                    "position_title": position_title,
                    "cv_text": cv_text,
                    "job_description": job_description
                }
                
                with st.spinner("Starting candidate screening workflow..."):
                    result, error = start_candidate_screening(candidate_data)
                    
                    if error:
                        st.error(f"❌ Failed to start workflow: {error}")
                    else:
                        st.success("✅ Candidate screening workflow started successfully!")
                        
                        # Show workflow details
                        st.subheader("🔄 Workflow Started")
                        st.json(result)
                        
                        st.info("The workflow is now running. Check the Workflow Status page to monitor progress.")

def show_workflow_status():
    """Workflow status monitoring"""
    st.header("📊 Workflow Status")
    
    # Auto-refresh toggle
    auto_refresh = st.checkbox("🔄 Auto-refresh (every 10 seconds)")
    
    if auto_refresh:
        # Auto-refresh every 10 seconds
        placeholder = st.empty()
        while auto_refresh:
            with placeholder.container():
                display_workflow_status()
            time.sleep(10)
            st.rerun()
    else:
        if st.button("🔄 Refresh"):
            st.rerun()
        display_workflow_status()

def display_workflow_status():
    """Display current workflow status"""
    workflows, error = get_active_workflows()
    
    if error:
        st.error(f"❌ Unable to get workflow status: {error}")
        return
    
    # Summary metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Active Workflows", workflows.get('active_workflows', 0))
    
    with col2:
        st.metric("Total Tasks", workflows.get('total_tasks', 0))
    
    with col3:
        pending_tasks = len([t for t in workflows.get('tasks', []) if t.get('status') == 'pending'])
        st.metric("Pending Tasks", pending_tasks)
    
    # Task details
    if workflows.get('tasks'):
        st.subheader("📋 Active Tasks")
        
        # Create DataFrame for better display
        tasks_data = []
        for task in workflows['tasks']:
            tasks_data.append({
                'Task ID': task['task_id'],
                'Agent': task['agent'].title().replace('_', ' '),
                'Type': task['type'].replace('_', ' ').title(),
                'Status': task['status'].title(),
                'Created': task['created_at'][:19] if task['created_at'] else 'Unknown'
            })
        
        df = pd.DataFrame(tasks_data)
        st.dataframe(df, use_container_width=True)
        
    else:
        st.info("ℹ️ No active workflows or tasks")

def show_interview_questions():
    """Interview questions display"""
    st.header("❓ Interview Questions")
    
    st.info("Enter a candidate's email to view their generated interview questions")
    
    candidate_email = st.text_input("📧 Candidate Email", placeholder="candidate@example.com")
    
    if st.button("🔍 Get Interview Questions") and candidate_email:
        with st.spinner("Fetching interview questions..."):
            questions, error = get_interview_questions(candidate_email)
            
            if error:
                st.error(f"❌ {error}")
            else:
                # Display candidate info
                st.subheader(f"📋 Interview Guide for {questions.get('candidate_name', candidate_email)}")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.metric("Duration", questions.get('estimated_duration', 'N/A'))
                    st.metric("Total Questions", len(questions.get('interview_questions', [])))
                
                with col2:
                    cv_analysis = questions.get('cv_analysis', {})
                    st.metric("Match Score", f"{cv_analysis.get('match_score', 0)}%")
                    st.metric("Experience", f"{cv_analysis.get('experience_years', 0)} years")
                
                # CV Analysis Summary
                if cv_analysis:
                    st.subheader("👤 Candidate Summary")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write("**Education:**", cv_analysis.get('education', 'Not provided'))
                        st.write("**Key Skills:**", ', '.join(cv_analysis.get('key_skills', [])))
                    
                    with col2:
                        highlights = cv_analysis.get('highlights', [])
                        if highlights:
                            st.write("**Key Highlights:**")
                            for highlight in highlights:
                                st.write(f"• {highlight}")
                    
                    st.write("**Summary:**", cv_analysis.get('summary', 'No summary available'))
                
                # Interview Questions
                st.subheader("🎤 Interview Questions")
                
                interview_questions = questions.get('interview_questions', [])
                if interview_questions:
                    for i, question in enumerate(interview_questions, 1):
                        with st.expander(f"Question {i}: {question.get('question', '')[:50]}..."):
                            st.write("**Question:**", question.get('question', ''))
                            st.write("**Purpose:**", question.get('purpose', ''))
                            st.write("**Follow-up hints:**", question.get('follow_up_hints', ''))
                
                # Focus Areas
                focus_areas = questions.get('interview_focus_areas', [])
                if focus_areas:
                    st.subheader("🎯 Focus Areas")
                    for area in focus_areas:
                        st.write(f"• {area}")

def show_interview_analysis():
    """Interview Analysis page"""
    st.header("🎭 Interview Analysis")
    st.write("Analyze interview conversations and evaluate candidate performance using AI")
    
    # Create two main tabs
    tab1, tab2, tab3 = st.tabs(["📝 New Analysis", "📊 Analysis Results", "📋 Analysis History"])
    
    with tab1:
        st.subheader("📝 Analyze Interview Conversation")
        
        # Input form for interview analysis
        with st.form("interview_analysis_form"):
            candidate_name = st.text_input("Candidate Name", placeholder="e.g., John Smith")
            position = st.text_input("Position", value="Software Engineer", placeholder="e.g., Software Engineer")
            
            conversation_text = st.text_area(
                "Interview Conversation",
                height=300,
                placeholder="Paste the full interview conversation here...\n\nExample format:\nInterviewer: Can you tell me about yourself?\nCandidate: I am a software engineer with 5 years of experience...\n\nInterviewer: What programming languages do you know?\nCandidate: I'm proficient in Python, JavaScript, and Java..."
            )
            
            submit_button = st.form_submit_button("🔍 Analyze Interview")
        
        if submit_button:
            if not candidate_name or not conversation_text:
                st.error("Please provide both candidate name and conversation text.")
            else:
                with st.spinner("🤖 Analyzing interview conversation... This may take a few moments."):
                    try:
                        # Make API request to analyze interview
                        response, error = make_api_request(
                            "interview-analyzer/analyze",
                            method="POST",
                            data={
                                "candidate_name": candidate_name,
                                "position": position,
                                "conversation_text": conversation_text
                            }
                        )
                        
                        if error:
                            st.error(f"❌ API Error: {error}")
                        elif response and response.get("status") == "success":
                            st.success("✅ Interview analysis completed!")
                            
                            # Store the analysis in session state for viewing
                            st.session_state.latest_analysis = response["analysis"]
                            
                            # Show quick results
                            analysis = response["analysis"]
                            evaluation = analysis.get("evaluation", {})
                            
                            # Overall score
                            overall_score = evaluation.get("overall_score", 0)
                            recommendation = evaluation.get("recommendation", "Unknown")
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                st.metric("Overall Score", f"{overall_score}/100")
                            with col2:
                                st.metric("Recommendation", recommendation)
                            
                            st.info("📊 View detailed results in the 'Analysis Results' tab!")
                            
                        else:
                            st.error("❌ Failed to analyze interview. Please try again.")
                    
                    except Exception as e:
                        st.error(f"❌ Error analyzing interview: {str(e)}")
    
    with tab2:
        st.subheader("📊 Detailed Analysis Results")
        
        if "latest_analysis" in st.session_state and st.session_state.latest_analysis:
            analysis = st.session_state.latest_analysis
            
            # Header information
            st.markdown(f"""
            <div class="metric-container">
                <h4>📋 Interview Summary</h4>
                <p><strong>Candidate:</strong> {analysis.get('candidate_name', 'Unknown')}</p>
                <p><strong>Position:</strong> {analysis.get('position', 'Unknown')}</p>
                <p><strong>Processed:</strong> {analysis.get('processed_at', 'Unknown')}</p>
            </div>
            """, unsafe_allow_html=True)
            
            evaluation = analysis.get("evaluation", {})
            
            # Overall Evaluation
            st.subheader("🏆 Overall Evaluation")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                overall_score = evaluation.get("overall_score", 0)
                st.metric("Overall Score", f"{overall_score}/100")
                
                if overall_score >= 85:
                    st.success("Excellent performance!")
                elif overall_score >= 70:
                    st.info("Good performance")
                elif overall_score >= 55:
                    st.warning("Average performance")
                else:
                    st.error("Below average performance")
            
            with col2:
                recommendation = evaluation.get("recommendation", "Unknown")
                st.metric("Recommendation", recommendation)
                
                if recommendation == "Hire":
                    st.success("✅ Recommended for hire")
                elif recommendation == "No Hire":
                    st.error("❌ Not recommended")
                else:
                    st.warning("⚠️ Needs further evaluation")
            
            with col3:
                qa_count = len(analysis.get("questions_answers", []))
                st.metric("Questions Analyzed", qa_count)
            
            # Competency Scores
            st.subheader("💼 Competency Assessment")
            
            competencies = ["technical_competence", "communication_skills", "cultural_fit"]
            competency_names = ["Technical Competence", "Communication Skills", "Cultural Fit"]
            
            cols = st.columns(3)
            for i, (comp_key, comp_name) in enumerate(zip(competencies, competency_names)):
                with cols[i]:
                    comp_data = evaluation.get(comp_key, {})
                    score = comp_data.get("score", 0)
                    comments = comp_data.get("comments", "No comments available")
                    
                    st.metric(comp_name, f"{score}/100")
                    with st.expander(f"Details for {comp_name}"):
                        st.write(comments)
            
            # Strengths and Improvement Areas
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("💪 Strengths")
                strengths = evaluation.get("strengths", [])
                if strengths:
                    for strength in strengths:
                        st.write(f"✅ {strength}")
                else:
                    st.write("No specific strengths identified")
            
            with col2:
                st.subheader("📈 Areas for Improvement")
                improvement_areas = evaluation.get("improvement_areas", [])
                if improvement_areas:
                    for area in improvement_areas:
                        st.write(f"🔧 {area}")
                else:
                    st.write("No specific improvement areas identified")
            
            # Detailed Comments
            st.subheader("📝 Detailed Comments")
            detailed_comments = evaluation.get("detailed_comments", "No detailed comments available")
            st.write(detailed_comments)
            
            # Questions and Answers Analysis
            st.subheader("❓ Question-by-Question Analysis")
            
            questions_answers = analysis.get("questions_answers", [])
            if questions_answers:
                for qa in questions_answers:
                    question_num = qa.get("question_number", "?")
                    question = qa.get("question", "No question")
                    full_answer = qa.get("answer", "No answer")
                    summary = qa.get("answer_summary", "No summary")
                    quality = qa.get("answer_quality", "Unknown")
                    completeness = qa.get("completeness", "Unknown")
                    key_points = qa.get("key_points", [])
                    category = qa.get("category", "Unknown")
                    
                    with st.expander(f"Q{question_num}: {question[:60]}{'...' if len(question) > 60 else ''}"):
                        
                        # Question details
                        st.markdown(f"**Category:** {category}")
                        st.markdown(f"**Question:** {question}")
                        
                        # Quality indicators
                        col1, col2 = st.columns(2)
                        with col1:
                            if quality == "Excellent":
                                st.success(f"Quality: {quality}")
                            elif quality == "Good":
                                st.info(f"Quality: {quality}")
                            elif quality == "Fair":
                                st.warning(f"Quality: {quality}")
                            else:
                                st.error(f"Quality: {quality}")
                        
                        with col2:
                            if completeness == "Complete":
                                st.success(f"Completeness: {completeness}")
                            elif completeness == "Partial":
                                st.warning(f"Completeness: {completeness}")
                            else:
                                st.error(f"Completeness: {completeness}")
                        
                        # Answer tabs
                        ans_tab1, ans_tab2 = st.tabs(["📄 Summary", "📝 Full Answer"])
                        
                        with ans_tab1:
                            st.write("**Summary:**")
                            st.write(summary)
                            
                            if key_points:
                                st.write("**Key Points:**")
                                for point in key_points:
                                    st.write(f"• {point}")
                        
                        with ans_tab2:
                            st.write("**Full Answer:**")
                            st.write(full_answer)
                        
                        # Individual question score if available
                        question_scores = evaluation.get("question_scores", [])
                        question_score_data = next(
                            (qs for qs in question_scores if qs.get("question_number") == question_num),
                            None
                        )
                        
                        if question_score_data:
                            score = question_score_data.get("score", 0)
                            feedback = question_score_data.get("feedback", "No feedback")
                            
                            st.markdown(f"**Score:** {score}/100")
                            st.markdown(f"**Feedback:** {feedback}")
            else:
                st.write("No questions and answers to display")
        
        else:
            st.info("No analysis results to display. Please run an analysis first in the 'New Analysis' tab.")
    
    with tab3:
        st.subheader("📋 Analysis History")
        
        try:
            # Get list of all analysis tasks
            response, error = make_api_request("interview-analyzer/tasks")
            
            if error:
                st.error(f"❌ API Error: {error}")
            elif response and response.get("status") == "success":
                tasks = response.get("tasks", [])
                
                if tasks:
                    st.write(f"Found {len(tasks)} analysis tasks:")
                    
                    # Create DataFrame for better display
                    task_data = []
                    for task in tasks:
                        task_data.append({
                            "Task ID": task.get("task_id", "Unknown")[:12] + "...",
                            "Candidate": task.get("candidate_name", "Unknown"),
                            "Position": task.get("position", "Unknown"),
                            "Status": task.get("status", "Unknown"),
                            "Created": task.get("created_at", "Unknown")[:19] if task.get("created_at") else "Unknown",
                            "Completed": task.get("completed_at", "Unknown")[:19] if task.get("completed_at") else "In Progress"
                        })
                    
                    df = pd.DataFrame(task_data)
                    st.dataframe(df, use_container_width=True)
                    
                    # Task details
                    if st.selectbox("Select a task to view details:", ["None"] + [t.get("task_id", "") for t in tasks]) != "None":
                        selected_task_id = st.selectbox("Select a task to view details:", ["None"] + [t.get("task_id", "") for t in tasks])
                        
                        if selected_task_id != "None":
                            # Get task details
                            task_response, task_error = make_api_request(f"interview-analyzer/task/{selected_task_id}")
                            
                            if task_error:
                                st.error(f"❌ Error getting task details: {task_error}")
                            elif task_response and task_response.get("result"):
                                st.write("**Task Details:**")
                                st.json(task_response["result"])
                else:
                    st.info("No analysis tasks found.")
            else:
                st.warning("Could not retrieve analysis history.")
                
        except Exception as e:
            st.error(f"Error loading analysis history: {str(e)}")

if __name__ == "__main__":
    main()