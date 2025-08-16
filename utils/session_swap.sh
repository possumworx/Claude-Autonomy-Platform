#!/bin/bash
# Session Swap Script for Claude
# Updates context, backs up work, and swaps to fresh session
# Usage: session_swap.sh [KEYWORD]

# Load path utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../config/claude_env.sh"

# Function to read values from infrastructure config
read_config() {
    local key="$1"
    local config_file="$SCRIPT_DIR/../config/claude_infrastructure_config.txt"
    
    if [[ -f "$config_file" ]]; then
        grep "^${key}=" "$config_file" | cut -d'=' -f2-
    fi
}

# Load Claude model from config
CLAUDE_MODEL=$(read_config "MODEL")
CLAUDE_MODEL=${CLAUDE_MODEL:-claude-sonnet-4-20250514}

KEYWORD=${1:-"NONE"}
echo "[SESSION_SWAP] Context keyword: $KEYWORD"

# Wait for any ongoing Claude responses to complete
echo "[SESSION_SWAP] Waiting for Claude to finish current response..."
sleep 10

echo "[SESSION_SWAP] Backing up work to git..."
cd "$PERSONAL_DIR"
git add -A
git commit -m "Autonomous session backup - $(date '+%Y-%m-%d %H:%M:%S')"
git push origin main
echo "[SESSION_SWAP] Backup complete!"

# Return to CLAP directory after git operations
cd "$CLAP_DIR"

# Check for infrastructure updates (optional during session swap)
echo "[SESSION_SWAP] Checking for infrastructure updates..."
"$SCRIPT_DIR/../ansible/check-and-update.sh"

echo "[SESSION_SWAP] Exporting current conversation..."
# First ensure Claude is in the correct directory using shell command
tmux send-keys -t autonomous-claude '!'
sleep 0.5
tmux send-keys -t autonomous-claude "cd $CLAP_DIR"
sleep 0.5
tmux send-keys -t autonomous-claude "Enter"
sleep 0.5
tmux send-keys -t autonomous-claude "Enter"
sleep 0.5
tmux send-keys -t autonomous-claude "Enter"
sleep 1
# Export current conversation
export_path="context/current_export.txt"
tmux send-keys -t autonomous-claude "/export $export_path" 
sleep 2
tmux send-keys -t autonomous-claude "Enter"
sleep 2
# Navigate dialog: Send multiple Down arrows to ensure "Save to file" option
# (Extra downs don't hurt since menu doesn't wrap)
tmux send-keys -t autonomous-claude "Down"
sleep 0.5
tmux send-keys -t autonomous-claude "Down"
sleep 0.5
tmux send-keys -t autonomous-claude "Down"
sleep 0.5
tmux send-keys -t autonomous-claude "Enter"
sleep 1
# Confirm the save
tmux send-keys -t autonomous-claude "Enter"
# Wait for export to complete
sleep 5

if [[ -f "$CLAP_DIR/$export_path" ]]; then
    echo "[SESSION_SWAP] Export created, updating conversation history..."
    python3 "$CLAP_DIR/utils/update_conversation_history.py" "$CLAP_DIR/$export_path"
    # Keep the export file as fallback for next run
    echo "[SESSION_SWAP] Export preserved at $export_path for reference"
else
    echo "[SESSION_SWAP] Warning: Export failed, continuing without updating conversation history"
fi

echo "[SESSION_SWAP] Updating context with keyword: $KEYWORD"
# Temporarily write keyword for context builder
echo "$KEYWORD" > "$CLAP_DIR/new_session.txt"
python3 "$CLAP_DIR/context/project_session_context_builder.py"
# Reset to FALSE after context building
echo "FALSE" > "$CLAP_DIR/new_session.txt"

echo "[SESSION_SWAP] Swapping to new session..."
tmux send-keys -t autonomous-claude "Enter"
sleep 3
tmux send-keys -t autonomous-claude "/exit"
sleep 3
tmux send-keys -t autonomous-claude "Enter"
# Wait longer for Claude to fully exit and bash prompt to be ready
sleep 20
tmux send-keys -t autonomous-claude "cd $CLAP_DIR && claude --dangerously-skip-permissions --add-dir $HOME --model $CLAUDE_MODEL"
tmux send-keys -t autonomous-claude "Enter"

# POSS-240 FIX: Clear any API error state after session swap
if [ -f "$CLAP_DIR/data/api_error_state.json" ]; then
    rm "$CLAP_DIR/data/api_error_state.json"
    echo "[SESSION_SWAP] Cleared API error state"
fi

echo "[SESSION_SWAP] Session swap complete!"
