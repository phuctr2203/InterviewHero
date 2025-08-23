#!/usr/bin/env python3
"""
Simple log viewer for the email monitor system
"""
import requests
import time
import sys
from datetime import datetime

BASE_URL = "http://localhost:8001"

def watch_logs():
    """Watch the system logs in real-time"""
    print("📋 EMAIL MONITOR LOG VIEWER")
    print("=" * 50)
    print("⏰ Starting log monitoring...")
    print("   Press Ctrl+C to stop")
    print()
    
    last_check_count = 0
    
    try:
        while True:
            # Get current status
            try:
                response = requests.get(f"{BASE_URL}/monitor/status")
                if response.status_code == 200:
                    status = response.json()
                    
                    current_time = datetime.now().strftime('%H:%M:%S')
                    
                    # Show status update if checks changed
                    if status['total_checks'] != last_check_count:
                        last_check_count = status['total_checks']
                        
                        print(f"[{current_time}] 🔍 Check #{status['total_checks']} completed")
                        print(f"   📊 Processed: {status['processed_count']} | Success: {status['successful_schedules']} | Failed: {status['failed_schedules']}")
                        
                        if status['last_check_time']:
                            last_check = datetime.fromisoformat(status['last_check_time']).strftime('%H:%M:%S')
                            print(f"   ⏰ Last check: {last_check}")
                        
                        print()
                    
                    # Show status every 10 cycles if nothing happening
                    elif last_check_count > 0 and last_check_count % 10 == 0:
                        print(f"[{current_time}] 💤 Monitoring... (Check #{status['total_checks']})")
                
            except requests.exceptions.ConnectionError:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Cannot connect to server")
            except Exception as e:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ Error: {e}")
            
            time.sleep(5)  # Check every 5 seconds
            
    except KeyboardInterrupt:
        print("\n👋 Log monitoring stopped")

def show_current_status():
    """Show current detailed status"""
    try:
        response = requests.get(f"{BASE_URL}/monitor/status")
        if response.status_code == 200:
            status = response.json()
            
            print("📊 CURRENT STATUS")
            print("=" * 30)
            print(f"🔄 Running: {'Yes' if status['is_running'] else 'No'}")
            print(f"📧 Processed Emails: {status['processed_count']}")
            print(f"🔍 Total Checks: {status['total_checks']}")
            print(f"✅ Successful Schedules: {status['successful_schedules']}")
            print(f"❌ Failed Schedules: {status['failed_schedules']}")
            print(f"⏱️  Check Interval: {status['check_interval']} seconds")
            
            if status['last_check_time']:
                last_check = datetime.fromisoformat(status['last_check_time']).strftime('%Y-%m-%d %H:%M:%S')
                print(f"🕐 Last Check: {last_check}")
            
            print(f"💬 Status: {status['message']}")
            
        else:
            print("❌ Cannot get status from server")
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server. Make sure it's running on port 8001")
    except Exception as e:
        print(f"❌ Error: {e}")

def main():
    if len(sys.argv) > 1:
        if sys.argv[1] == "status":
            show_current_status()
            return
        elif sys.argv[1] == "watch":
            watch_logs()
            return
    
    print("📋 Email Monitor Log Viewer")
    print("=" * 40)
    print("Usage:")
    print("  python view_logs.py status  - Show current status")
    print("  python view_logs.py watch   - Watch logs in real-time")
    print()
    
    choice = input("Choose option (status/watch): ").lower().strip()
    
    if choice == "status":
        show_current_status()
    elif choice == "watch":
        watch_logs()
    else:
        show_current_status()

if __name__ == "__main__":
    main()