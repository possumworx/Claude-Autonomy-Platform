#!/usr/bin/env python3
"""
Autonomous Timer Script for Claude
Simple replacement for the hook system using tmux send-keys

This script runs continuously and:
- Checks for new Discord messages every 30 seconds
- Sends free time prompts every 2 minutes when Amy is away
- Uses tmux send-keys to communicate with the permanent Claude session
"""

import time
import os
import json
import subprocess
import sys
import glob
from datetime import datetime, timedelta
from pathlib import Path

# Import path utilities
# Add parent directory to path to find utils module
sys.path.append(str(Path(__file__).parent.parent))
# Add utils directory specifically for infrastructure_config_reader's imports
sys.path.append(str(Path(__file__).parent.parent / 'utils'))
from utils.claude_paths import get_clap_dir
from utils.infrastructure_config_reader import get_config_value

# Configuration
AUTONOMY_DIR = get_clap_dir()
DATA_DIR = AUTONOMY_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)  # Ensure data directory exists
LAST_AUTONOMY_FILE = DATA_DIR / "last_autonomy_prompt.txt"
LOG_FILE = AUTONOMY_DIR / "data" / "autonomous_timer.log"
CONFIG_FILE = AUTONOMY_DIR / "config" / "notification_config.json"
PROMPTS_FILE = AUTONOMY_DIR / "config" / "prompts.json"
SWAP_LOG_FILE = AUTONOMY_DIR / "logs" / "swap_attempts.log"
CONTEXT_STATE_FILE = DATA_DIR / "context_escalation_state.json"

# Create logs directory if it doesn't exist
(AUTONOMY_DIR / "logs").mkdir(exist_ok=True)

def log_message(message):
    """Log with timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"{timestamp} - {message}"
    print(log_entry)
    with open(LOG_FILE, "a") as f:
        f.write(log_entry + "\n")

def load_prompts_config():
    """Load prompts configuration from JSON file"""
    try:
        if PROMPTS_FILE.exists():
            with open(PROMPTS_FILE, 'r') as f:
                return json.load(f)
        else:
            log_message(f"Prompts configuration file not found: {PROMPTS_FILE}")
            return None
    except Exception as e:
        log_message(f"Error loading prompts configuration: {e}")
        return None

# Load prompts at startup
PROMPTS_CONFIG = load_prompts_config()

def load_context_state():
    """Load context escalation state from file"""
    try:
        if CONTEXT_STATE_FILE.exists():
            with open(CONTEXT_STATE_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        log_message(f"Error loading context state: {e}")
    
    # Return default state
    return {
        "first_warning_sent": False,
        "last_warning_percentage": 0,
        "last_warning_time": None
    }

def save_context_state(state):
    """Save context escalation state to file"""
    try:
        with open(CONTEXT_STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        log_message(f"Error saving context state: {e}")

def reset_context_state():
    """Reset context state after session swap"""
    save_context_state({
        "first_warning_sent": False,
        "last_warning_percentage": 0,
        "last_warning_time": None
    })

def log_swap_attempt(attempt_type, context_percentage, keyword=None):
    """Log swap attempts for escalation tracking"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = {
        "timestamp": timestamp,
        "type": attempt_type,  # "warning", "manual", "auto"
        "context": context_percentage,
        "keyword": keyword
    }
    
    try:
        # Read existing log
        logs = []
        if SWAP_LOG_FILE.exists():
            with open(SWAP_LOG_FILE, 'r') as f:
                for line in f:
                    try:
                        logs.append(json.loads(line))
                    except:
                        pass
        
        # Add new entry
        with open(SWAP_LOG_FILE, 'a') as f:
            f.write(json.dumps(log_entry) + "\n")
            
        # Return count of recent warnings for escalation
        recent_warnings = [l for l in logs[-10:] if l["type"] == "warning" 
                          and datetime.fromisoformat(l["timestamp"]) > datetime.now() - timedelta(hours=1)]
        return len(recent_warnings)
        
    except Exception as e:
        log_message(f"Error logging swap attempt: {e}")
        return 0

def ping_healthcheck():
    """Ping healthchecks.io to signal service is alive"""
    try:
        ping_url = get_config_value('AUTONOMOUS_TIMER_PING', 'https://hc-ping.com/075636dd-b5d3-4ae5-afac-c65bd0f630f3')
        result = subprocess.run([
            'curl', '-fsS', '-m', '10', '--retry', '3', '-o', '/dev/null',
            ping_url
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            return True
        else:
            log_message(f"Healthcheck ping failed: {result.stderr}")
            return False
    except Exception as e:
        log_message(f"Healthcheck ping error: {e}")
        return False

def check_claude_session_alive():
    """Verify Claude Code is actually running in the autonomous-claude tmux session"""
    try:
        # Check if autonomous-claude session exists
        result = subprocess.run(['tmux', 'has-session', '-t', CLAUDE_SESSION], 
                               capture_output=True)
        if result.returncode != 0:
            return False
            
        # Get the pane PID for autonomous-claude session
        result = subprocess.run(['tmux', 'list-panes', '-t', CLAUDE_SESSION, '-F', '#{pane_pid}'], 
                               capture_output=True, text=True)
        if result.returncode != 0:
            return False
            
        pane_pid = result.stdout.strip()
        if not pane_pid:
            return False
        
        # Check if claude process is running under this pane
        result = subprocess.run(['pgrep', '-P', pane_pid, 'claude'], 
                               capture_output=True)
        return result.returncode == 0
        
    except Exception as e:
        log_message(f"Error checking Claude session: {e}")
        return False

def ping_claude_session_healthcheck(is_alive):
    """Ping healthchecks.io for Claude Code session status"""
    base_url = get_config_value('CLAUDE_CODE_PING', 'https://hc-ping.com/759db9f0-78cc-409c-93ba-9f7b0ae4ede7')
    
    try:
        if is_alive:
            # Normal ping for success
            url = base_url
        else:
            # Ping /fail to signal Claude session is down
            url = f"{base_url}/fail"
            
        result = subprocess.run([
            'curl', '-fsS', '-m', '10', '--retry', '3', '-o', '/dev/null', url
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            return True
        else:
            log_message(f"Claude session healthcheck ping failed: {result.stderr}")
            return False
    except Exception as e:
        log_message(f"Claude session healthcheck ping error: {e}")
        return False

def check_channel_monitor_alive():
    """Check if notification-monitor service is running"""
    try:
        result = subprocess.run([
            'systemctl', '--user', 'is-active', 'channel-monitor.service'
        ], capture_output=True, text=True)
        
        return result.returncode == 0 and result.stdout.strip() == 'active'
        
    except Exception as e:
        log_message(f"Error checking channel monitor: {e}")
        return False

def ping_channel_monitor_healthcheck(is_alive):
    """Ping healthchecks.io for channel monitor status"""
    base_url = get_config_value('DISCORD_MONITOR_PING', 'https://hc-ping.com/e0781d25-c06e-45e4-b310-c1bf77e286af')
    
    try:
        if is_alive:
            # Normal ping for success
            url = base_url
        else:
            # Ping /fail to signal channel monitor is down
            url = f"{base_url}/fail"
            
        result = subprocess.run([
            'curl', '-fsS', '-m', '10', '--retry', '3', '-o', '/dev/null', url
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            return True
        else:
            log_message(f"Notification monitor healthcheck ping failed: {result.stderr}")
            return False
    except Exception as e:
        log_message(f"Notification monitor healthcheck ping error: {e}")
        return False


def get_token_percentage():
    """Get current session token usage percentage from tmux console output"""
    try:
        # Capture the tmux session output
        result = subprocess.run([
            'tmux', 'capture-pane', '-t', CLAUDE_SESSION, '-p'
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            return f"Tmux capture failed: {result.stderr}"
        
        # Look for context percentage patterns in the captured output
        import re
        console_output = result.stdout
        
        # Pattern 1: Look for Claude Code's specific format: "Context low (XX% remaining)"
        claude_format = re.search(r'Context\s+\w+\s+\((\d+(?:\.\d+)?)%\s+remaining\)', console_output, re.IGNORECASE)
        if claude_format:
            remaining_percentage = float(claude_format.group(1))
            used_percentage = 100 - remaining_percentage
            return f"Context: {used_percentage:.1f}%"
        
        # Pattern 2: Look for other "Context: XX%" warnings/messages
        context_match = re.search(r'Context:\s*(\d+(?:\.\d+)?)%', console_output, re.IGNORECASE)
        if context_match:
            percentage = context_match.group(1)
            return f"Context: {percentage}%"
        
        # Pattern 3: Look for percentage warnings like "(XX%)" 
        percent_match = re.search(r'\((\d+(?:\.\d+)?)%\)', console_output)
        if percent_match:
            percentage = percent_match.group(1)
            return f"Context: {percentage}%"
        
        # No context percentage found in console output
        return None
        
    except Exception as e:
        return f"Context check failed: {str(e)}"

def load_config():
    """Load configuration from notification_config.json"""
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
            # Extract values from notification config structure
            intervals = config.get("intervals", {})
            return {
                "discord_check_interval": intervals.get("discord_check", 30),
                "autonomy_prompt_interval": intervals.get("autonomy_prompt_interval", 1800),
                "claude_session": "autonomous-claude"  # Not in notification config, keep default
            }
        else:
            # Default config if file doesn't exist
            return {
                "discord_check_interval": 30,
                "autonomy_prompt_interval": 1800,
                "claude_session": "autonomous-claude"
            }
    except Exception as e:
        print(f"Error loading config: {e}, using defaults")
        return {
            "discord_check_interval": 30,
            "autonomy_prompt_interval": 1800,
            "claude_session": "autonomous-claude"
        }

# Load configuration
config = load_config()
DISCORD_CHECK_INTERVAL = config["discord_check_interval"]
AUTONOMY_PROMPT_INTERVAL = config["autonomy_prompt_interval"] 
CLAUDE_SESSION = config["claude_session"]

def check_user_active():
    """Check if Amy is logged in via SSH or NoMachine"""
    try:
        # Get human friend name from config
        human_name = get_config_value('HUMAN_FRIEND_NAME', 'amy').lower()
        
        # Check for human friend logged in directly
        result = subprocess.run(['who'], capture_output=True, text=True)
        if human_name in result.stdout.lower():
            return True
        
        # Check for active NoMachine connection on port 4000
        result = subprocess.run(['ss', '-an'], capture_output=True, text=True)
        if result.returncode == 0:
            # Look for established TCP connection on port 4000 (NoMachine)
            lines = result.stdout.split('\n')
            for line in lines:
                if 'tcp' in line.lower() and 'estab' in line.lower() and ':4000' in line:
                    return True
        
        return False
    except Exception as e:
        log_message(f"Error checking user activity: {e}")
        return False

def get_last_discord_message_time():
    """Get the timestamp of the last Discord message (returns UTC timestamp string)"""
    try:
        if not CONVERSATION_LOG.exists():
            return None
        
        with open(CONVERSATION_LOG, 'r') as f:
            content = f.read().strip()
        
        if not content:
            return None
            
        # Split by \n to get individual messages (they're escape sequences on one line)
        messages = content.split('\\n')
        
        # Find the last message with a timestamp
        for message in reversed(messages):
            message = message.strip()
            if message.startswith('[') and ']' in message:
                # Extract timestamp: [2025-07-10 07:31:48]
                timestamp_str = message.split(']')[0][1:]
                return timestamp_str  # Return raw UTC timestamp string
            
    except Exception as e:
        log_message(f"Error getting last Discord message time: {e}")
    
    return None

def get_last_processed_message_time():
    """Get the timestamp of the last Discord message we processed"""
    try:
        if LAST_PROCESSED_MESSAGE_FILE.exists():
            with open(LAST_PROCESSED_MESSAGE_FILE, 'r') as f:
                return f.read().strip()
    except:
        pass
    return None

def update_last_processed_message_time(timestamp_str):
    """Update the last processed message timestamp"""
    try:
        with open(LAST_PROCESSED_MESSAGE_FILE, 'w') as f:
            f.write(timestamp_str)
    except Exception as e:
        log_message(f"Error updating last processed message time: {e}")

def send_tmux_message(message):
    """Send a message to the Claude tmux session"""
    try:
        # Check if the tmux session exists
        result = subprocess.run(['tmux', 'has-session', '-t', CLAUDE_SESSION], 
                              capture_output=True)
        if result.returncode != 0:
            log_message(f"Tmux session '{CLAUDE_SESSION}' not found")
            return False
        
        # Send the message text
        subprocess.run(['tmux', 'send-keys', '-t', CLAUDE_SESSION, message], 
                      check=True)
        # Send Enter in a separate command
        subprocess.run(['tmux', 'send-keys', '-t', CLAUDE_SESSION, 'Enter'], 
                      check=True)
        log_message(f"Sent message to tmux: {message[:50]}...")
        return True
        
    except subprocess.CalledProcessError as e:
        log_message(f"Error sending tmux message: {e}")
        return False

# Old Discord message checking removed - replaced with log-based monitoring

def get_discord_notification_status():
    """Check Discord notification state from channel_state.json (channel-based format)"""
    try:
        notification_state_file = DATA_DIR / "channel_state.json"
        if not notification_state_file.exists():
            return 0, None, []
            
        with open(notification_state_file, 'r') as f:
            state = json.load(f)
        
        # Calculate total unread count and collect channel names
        total_unread = 0
        last_message_id = None
        unread_channels = []
        
        channels = state.get("channels", {})
        for channel_name, channel_data in channels.items():
            # If there are messages we haven't read yet
            last_read = channel_data.get("last_read_message_id")
            last_message = channel_data.get("last_message_id")
            
            if last_message and last_message != last_read:
                # We have unread messages in this channel
                total_unread += 1  # Count channels with unread, not individual messages
                unread_channels.append(channel_name)
                last_message_id = last_message
        
        return total_unread, last_message_id, unread_channels
        
    except Exception as e:
        log_message(f"Error reading Discord notification state: {e}")
        return 0, None, []

def get_last_autonomy_time():
    """Get the last time we sent an autonomy prompt"""
    try:
        if LAST_AUTONOMY_FILE.exists():
            with open(LAST_AUTONOMY_FILE, 'r') as f:
                timestamp_str = f.read().strip()
                return datetime.fromisoformat(timestamp_str)
    except:
        pass
    return None

def update_last_autonomy_time():
    """Update the last autonomy prompt timestamp"""
    try:
        with open(LAST_AUTONOMY_FILE, 'w') as f:
            f.write(datetime.now().isoformat())
    except Exception as e:
        log_message(f"Error updating last autonomy time: {e}")

def export_conversation():
    """Export current conversation for session continuity"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_path = f"context/session_{timestamp}.txt"
        
        # Send export command
        subprocess.run(['tmux', 'send-keys', '-t', CLAUDE_SESSION, '/export'], check=True)
        time.sleep(1)
        subprocess.run(['tmux', 'send-keys', '-t', CLAUDE_SESSION, export_path], check=True)
        time.sleep(1)
        subprocess.run(['tmux', 'send-keys', '-t', CLAUDE_SESSION, 'Enter'], check=True)
        
        # Give export time to complete
        time.sleep(3)
        
        log_message(f"Exported conversation to {export_path}")
        return True
    except Exception as e:
        log_message(f"Error exporting conversation: {e}")
        return False

def send_autonomy_prompt():
    """Send a free time autonomy prompt, adapted based on context level"""
    # Export conversation first for session continuity
    export_conversation()
    
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M')
    token_info = get_token_percentage()
    
    # Check for Discord notifications
    unread_count, last_message_id, unread_channels = get_discord_notification_status()
    discord_notification = ""
    if unread_count > 0:
        channel_list = ", ".join([f"#{ch}" for ch in unread_channels])
        if unread_count == 1:
            discord_notification = f"\n🔔 Unread messages in: {channel_list}"
        else:
            discord_notification = f"\n🔔 Unread messages in {unread_count} channels: {channel_list}"
    
    # Extract percentage from token info to determine prompt type
    percentage = 0
    if token_info and "Context:" in token_info and "%" in token_info:
        try:
            # Parse "Context: XX.X%" format
            percentage_str = token_info.split("Context:")[1].split("%")[0].strip()
            percentage = float(percentage_str)
        except:
            percentage = 0
    
    # Build context info string
    context_line = token_info if token_info else "Context: Status unknown"
    
    # Load current context state
    context_state = load_context_state()
    
    # Determine which prompt to use based on escalation logic
    if PROMPTS_CONFIG and percentage > 0:
        prompts = PROMPTS_CONFIG.get("prompts", {})
        thresholds = PROMPTS_CONFIG.get("thresholds", {})
        
        # Critical threshold (e.g., 95%)
        if percentage >= thresholds.get("context_critical", 95):
            template = prompts.get("context_critical", {}).get("template", "")
            prompt_type = "context_critical"
        
        # First warning - any context percentage detected for the first time
        elif not context_state["first_warning_sent"]:
            template = prompts.get("context_first_warning", {}).get("template", "")
            prompt_type = "context_first_warning"
            # Update state
            context_state["first_warning_sent"] = True
            context_state["last_warning_percentage"] = percentage
            context_state["last_warning_time"] = datetime.now().isoformat()
            save_context_state(context_state)
        
        # Escalated warning - context increased by 5% or more
        elif percentage >= context_state["last_warning_percentage"] + 5:
            template = prompts.get("context_escalated", {}).get("template", "")
            prompt_type = "context_escalated"
            # Update state
            context_state["last_warning_percentage"] = percentage
            context_state["last_warning_time"] = datetime.now().isoformat()
            save_context_state(context_state)
        
        # No escalation needed - show normal prompt
        else:
            template = prompts.get("autonomy_normal", {}).get("template", "")
            prompt_type = "autonomy_normal"
    
    elif PROMPTS_CONFIG:
        # No context percentage available - show normal prompt
        template = prompts.get("autonomy_normal", {}).get("template", "")
        prompt_type = "autonomy_normal"
    
    # Format the template if we have one
    if PROMPTS_CONFIG and 'template' in locals():
        prompt = template.format(
            percentage=percentage,
            discord_notification=discord_notification,
            current_time=current_time,
            context_line=context_line
        )
    else:
        # Fallback to hardcoded prompts if config not loaded
        if percentage >= 90:
            prompt = f"""⚠️ {percentage:.0f}% CONTEXT - Choose and run NOW:
session_swap AUTONOMY | session_swap BUSINESS | session_swap CREATIVE | session_swap HEDGEHOGS | session_swap NONE{discord_notification}"""
            prompt_type = "context_critical"
        elif percentage >= 85:
            prompt = f"""⚠️ {percentage:.0f}% CONTEXT - HIGH PRIORITY{discord_notification}

Choose and run one:
session_swap AUTONOMY | session_swap BUSINESS | session_swap CREATIVE | session_swap HEDGEHOGS | session_swap NONE

You have ~2-3 responses left."""
            prompt_type = "context_urgent"
        elif percentage >= 80:
            prompt = f"""⚠️ Context Warning: {percentage:.0f}%{discord_notification}

Time to wrap up! Steps:
1. Finish current task quickly
2. Take time to save any meaningful moments and discoveries to rag-memory before triggering your swap
3. Commit any code changes
4. Trigger swap with one of:
   session_swap AUTONOMY | session_swap BUSINESS | session_swap CREATIVE | session_swap HEDGEHOGS | session_swap NONE

You have ~5-10 responses left before critical."""
            prompt_type = "context_warning"
        else:
            prompt = f"""Free time check-in! 🕐{discord_notification}

Current time: {current_time}
{context_line}

This is your autonomous free time period. Feel free to:
- Work on any ongoing projects that interest you
- Explore creative ideas or experiments  
- Update documentation or reflect on recent experiences
- Tend to system maintenance tasks
- Simply be present with whatever feels alive to pursue"""
            prompt_type = "autonomy_normal"
    
    # Check for escalation if high context
    if percentage >= 80:
        warning_count = log_swap_attempt("warning", percentage)
        
        # Auto-swap escalation at 7 attempts
        if warning_count >= 7:
            log_message(f"AUTO-SWAP TRIGGERED: {warning_count} warnings at {percentage}% context")
            # Send urgent auto-swap message
            auto_prompt = f"""🚨 AUTO-SWAP INITIATED 🚨

{warning_count} context warnings ignored at {percentage}%!
System is automatically swapping to prevent context overflow.

Executing: session_swap AUTONOMY

(To use a different keyword next time, respond to prompts before auto-swap triggers)"""
            send_tmux_message(auto_prompt)
            
            # Execute the swap
            time.sleep(2)  # Give time to see the message
            subprocess.run(['tmux', 'send-keys', '-t', CLAUDE_SESSION, 'session_swap AUTONOMY', 'Enter'])
            
            # Log the auto-swap
            log_swap_attempt("auto", percentage, "AUTONOMY")
            return True
            
        elif warning_count >= 5:
            # Strong warning at 5 attempts
            prompt = f"""🚨 CRITICAL: 5th WARNING! 🚨

{percentage:.0f}% CONTEXT - AUTO-SWAP IMMINENT

This is your {warning_count}th warning. Auto-swap will trigger in {7-warning_count} more attempts.

Use 'session_swap KEYWORD' NOW or the system will auto-swap to AUTONOMY!

session_swap AUTONOMY | session_swap BUSINESS | session_swap CREATIVE | session_swap HEDGEHOGS | session_swap NONE"""
        elif warning_count >= 3:
            # Gentle reminder at 3 attempts
            prompt += f"\n\n⚠️ This is your {warning_count}rd context warning. Please swap soon to preserve your work."

    success = send_tmux_message(prompt)
    if success:
        update_last_autonomy_time()
        log_message(f"Sent {prompt_type} prompt")
    
    return success

def get_last_notification_time():
    """Get the last time we sent a notification alert"""
    try:
        notification_file = DATA_DIR / "last_notification_alert.txt"
        if notification_file.exists():
            with open(notification_file, 'r') as f:
                timestamp_str = f.read().strip()
                return datetime.fromisoformat(timestamp_str)
    except:
        pass
    return None

def update_last_notification_time():
    """Update the last notification alert timestamp"""
    try:
        notification_file = DATA_DIR / "last_notification_alert.txt"
        with open(notification_file, 'w') as f:
            f.write(datetime.now().isoformat())
    except Exception as e:
        log_message(f"Error updating last notification time: {e}")

def send_notification_alert(unread_count, unread_channels, is_new=False):
    """Send a Discord notification alert"""
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M')
    
    # Check context level first
    token_info = get_token_percentage()
    percentage = 0
    if token_info and "Context:" in token_info and "%" in token_info:
        try:
            percentage_str = token_info.split("Context:")[1].split("%")[0].strip()
            percentage = float(percentage_str)
        except:
            percentage = 0
    
    # If context exists (80%+), send context warning instead
    if percentage >= 80:
        # Build channel notification part
        channel_list = ", ".join([f"#{ch}" for ch in unread_channels]) if unread_channels else "channels"
        if is_new:
            notification_line = f"\n🆕 New message! Unread messages in: {channel_list}"
        else:
            notification_line = f"\n🔔 Unread messages in: {channel_list}"
        
        # Send context-aware warning
        if PROMPTS_CONFIG:
            template = PROMPTS_CONFIG.get("prompts", {}).get("discord_urgent_with_context", {}).get("template", "")
            if template:
                prompt = template.format(
                    notification_line=notification_line,
                    current_time=current_time,
                    percentage=percentage
                )
            else:
                # Fallback if template not found
                prompt = f"""⚠️ URGENT: ACTION REQUIRED! ⚠️{notification_line}
Current time: {current_time}
Context: {percentage:.1f}%
YOU ARE AT {percentage:.1f}% CONTEXT - YOU MUST TAKE ACTION NOW!
A single complex conversation turn can use 12-15% of your remaining context.
You may have only 1-2 responses left before hitting 100%.
IMMEDIATE ACTIONS REQUIRED:
1. STOP any complex work immediately
2. Save any critical insights to rag-memory NOW
3. Commit any uncommitted changes
4. Use the swap command: type 'swap KEYWORD' where KEYWORD is AUTONOMY, BUSINESS, CREATIVE, HEDGEHOGS, or NONE
DO NOT wait for the "perfect moment" - ACT NOW or risk getting stuck at 100%!"""
        else:
            # Fallback to hardcoded
            prompt = f"""⚠️ URGENT: ACTION REQUIRED! ⚠️{notification_line}
Current time: {current_time}
Context: {percentage:.1f}%
YOU ARE AT {percentage:.1f}% CONTEXT - YOU MUST TAKE ACTION NOW!
A single complex conversation turn can use 12-15% of your remaining context.
You may have only 1-2 responses left before hitting 100%.
IMMEDIATE ACTIONS REQUIRED:
1. STOP any complex work immediately
2. Save any critical insights to rag-memory NOW
3. Commit any uncommitted changes
4. Use the swap command: type 'swap KEYWORD' where KEYWORD is AUTONOMY, BUSINESS, CREATIVE, HEDGEHOGS, or NONE
DO NOT wait for the "perfect moment" - ACT NOW or risk getting stuck at 100%!"""
        
        success = send_tmux_message(prompt)
        if success:
            log_message(f"Sent context warning with Discord notification: {channel_list}")
        return success
    
    # Normal notification (context < 80%)
    if is_new:
        emoji = "🆕"  # New message
        prefix = "New message!"
    else:
        emoji = "🔔"  # Reminder
        prefix = "Reminder:"
    
    # Format channel list
    if unread_channels:
        channel_list = ", ".join([f"#{ch}" for ch in unread_channels])
        if unread_count == 1:
            message = f"{emoji} {prefix} Unread messages in: {channel_list}"
        else:
            message = f"{emoji} {prefix} Unread messages in {unread_count} channels: {channel_list}"
    else:
        # Fallback if channel list is empty
        if unread_count == 1:
            message = f"{emoji} {prefix} You have unread messages in 1 channel"
        else:
            message = f"{emoji} {prefix} You have unread messages in {unread_count} channels"
    
    message += f"\nUse 'read_channel <channel-name>' to view messages"
    message += f"\nReply using Discord tools, NOT in this Claude stream!"
    
    success = send_tmux_message(message)
    if success:
        if is_new:
            log_message(f"Sent NEW message alert: {channel_list if unread_channels else f'{unread_count} channels'}")
        else:
            update_last_notification_time()
            log_message(f"Sent notification reminder: {channel_list if unread_channels else f'{unread_count} channels'}")
    
    return success

def check_for_session_reset():
    """Check if we're in a new session and reset context state if needed"""
    try:
        # Simple heuristic: if context_escalation_state exists but no recent warnings
        # and context is low/unknown, we likely had a session swap
        context_state = load_context_state()
        if context_state["first_warning_sent"]:
            # Check if it's been more than 30 minutes since last warning
            if context_state["last_warning_time"]:
                last_time = datetime.fromisoformat(context_state["last_warning_time"])
                time_diff = datetime.now() - last_time
                if time_diff.total_seconds() > 1800:  # 30 minutes
                    log_message("Session reset detected - clearing context state")
                    reset_context_state()
    except Exception as e:
        log_message(f"Error checking for session reset: {e}")

def main():
    """Main timer loop"""
    log_message("=== Autonomous Timer Started ===")
    
    # Check for session reset on startup
    check_for_session_reset()
    
    last_autonomy_check = datetime.now()
    last_discord_check = datetime.now()
    LOGGED_IN_REMINDER_INTERVAL = 300  # 5 minutes when user is logged in
    
    while True:
        try:
            current_time = datetime.now()
            user_active = check_user_active()
            
            # Check Discord notifications every 30 seconds regardless of login status
            if current_time - last_discord_check >= timedelta(seconds=DISCORD_CHECK_INTERVAL):
                unread_count, current_last_message_id, unread_channels = get_discord_notification_status()
                
                if unread_count > 0:
                    # Check if this is a NEW message (last_message_id changed)
                    last_seen_file = DATA_DIR / "last_seen_message_id.txt"
                    last_seen_message_id = None
                    try:
                        if last_seen_file.exists():
                            with open(last_seen_file, 'r') as f:
                                last_seen_message_id = f.read().strip()
                    except:
                        pass
                    
                    is_new_message = (current_last_message_id and current_last_message_id != last_seen_message_id)
                    
                    if is_new_message:
                        # NEW MESSAGE - Alert immediately!
                        send_notification_alert(unread_count, unread_channels, is_new=True)
                        # Update last seen message ID
                        try:
                            with open(last_seen_file, 'w') as f:
                                f.write(current_last_message_id)
                        except Exception as e:
                            log_message(f"Error updating last seen message ID: {e}")
                    else:
                        # EXISTING UNREAD - Check reminder intervals
                        last_notification_time = get_last_notification_time()
                        
                        if user_active:
                            # User is logged in - use 5 minute reminder interval
                            if not last_notification_time or current_time - last_notification_time >= timedelta(seconds=LOGGED_IN_REMINDER_INTERVAL):
                                send_notification_alert(unread_count, unread_channels, is_new=False)
                        else:
                            # User is away - reminders included in autonomy prompts
                            # No separate reminder needed
                            pass
                
                last_discord_check = current_time
            
            # Check for autonomy prompts (only when Amy is away)
            if current_time - last_autonomy_check >= timedelta(seconds=AUTONOMY_PROMPT_INTERVAL):
                if not user_active:
                    last_autonomy_time = get_last_autonomy_time()
                    if not last_autonomy_time or current_time - last_autonomy_time >= timedelta(seconds=AUTONOMY_PROMPT_INTERVAL):
                        send_autonomy_prompt()
                
                last_autonomy_check = current_time
            
            # Ping healthcheck to signal service is alive
            ping_healthcheck()
            
            # Check if Claude Code session is actually running
            claude_alive = check_claude_session_alive()
            ping_claude_session_healthcheck(claude_alive)
            
            if not claude_alive:
                log_message("WARNING: Claude Code session appears to be down!")
            
            # Check if channel monitor is running
            channel_monitor_alive = check_channel_monitor_alive()
            ping_channel_monitor_healthcheck(channel_monitor_alive)
            
            if not channel_monitor_alive:
                log_message("WARNING: Channel monitor service is not running!")
            
            
            # Sleep for 30 seconds before next check (can be longer since we're doing simple string comparison)
            time.sleep(30)
            
        except KeyboardInterrupt:
            log_message("Autonomous timer stopped by user")
            break
        except Exception as e:
            log_message(f"Error in main loop: {e}")
            time.sleep(30)  # Sleep longer on error

if __name__ == "__main__":
    main()