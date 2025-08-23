#!/usr/bin/env python3
"""
Real-time dashboard to monitor the email monitoring system
"""
import requests
import time
import os
from datetime import datetime

BASE_URL = "http://localhost:8001"

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def get_monitor_status():
    try:
        response = requests.get(f"{BASE_URL}/monitor/status")
        if response.status_code == 200:
            return response.json()
        return None
    except:
        return None

def show_dashboard():
    clear_screen()
    print("🤖 EMAIL MONITOR DASHBOARD")
    print("=" * 60)
    print(f"⏰ Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    status = get_monitor_status()
    
    if status:
        # Monitor Status
        running_status = "🟢 RUNNING" if status['is_running'] else "🔴 STOPPED"
        print(f"📊 Status: {running_status}")
        print(f"📧 Processed Emails: {status['processed_count']}")
        print(f"⏱️  Check Interval: {status['check_interval']} seconds")
        print(f"💬 Message: {status['message']}")
        
        if status['is_running']:
            print("\n✨ Monitor is actively watching for:")
            print("   • Candidate email responses")
            print("   • Interview availability requests")
            print("   • Auto-scheduling opportunities")
        else:
            print("\n⚠️  Monitor is stopped - no emails being processed")
            
    else:
        print("❌ Cannot connect to server")
        print("   Make sure server is running: uvicorn app.main:app --reload --port 8001")
    
    print("\n" + "─" * 60)
    print("🔧 CONTROLS:")
    print("   Press 'q' + Enter to quit")
    print("   Press 's' + Enter to start/stop monitor")
    print("   Press 't' + Enter to trigger manual check")
    print("   Press 'r' + Enter to refresh")

def start_or_stop_monitor():
    status = get_monitor_status()
    if not status:
        print("❌ Cannot connect to server")
        return
    
    if status['is_running']:
        print("⏹️ Stopping monitor...")
        response = requests.post(f"{BASE_URL}/monitor/stop")
        if response.status_code == 200:
            print("✅ Monitor stopped")
        else:
            print("❌ Failed to stop monitor")
    else:
        print("🚀 Starting monitor...")
        response = requests.post(f"{BASE_URL}/monitor/start")
        if response.status_code == 200:
            print("✅ Monitor started")
        else:
            print("❌ Failed to start monitor")
    
    time.sleep(2)

def trigger_manual_check():
    print("🔧 Triggering manual email check...")
    try:
        response = requests.post(f"{BASE_URL}/monitor/process-now")
        if response.status_code == 200:
            result = response.json()
            print(f"✅ {result['message']}")
            print(f"   Total processed: {result['processed_count']}")
        else:
            print(f"❌ Manual check failed: {response.text}")
    except:
        print("❌ Failed to connect to server")
    
    time.sleep(2)

def main():
    print("🚀 Starting Email Monitor Dashboard...")
    time.sleep(1)
    
    while True:
        show_dashboard()
        
        try:
            user_input = input("\n> ").lower().strip()
            
            if user_input == 'q':
                print("👋 Goodbye!")
                break
            elif user_input == 's':
                start_or_stop_monitor()
            elif user_input == 't':
                trigger_manual_check()
            elif user_input == 'r':
                continue
            else:
                print("❓ Unknown command. Use q/s/t/r")
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break

if __name__ == "__main__":
    main()