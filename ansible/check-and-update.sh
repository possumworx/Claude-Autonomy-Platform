#!/bin/bash
# Check for infrastructure updates and optionally apply them
# Designed to be integrated into session swap workflow

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLAYBOOK_DIR="$SCRIPT_DIR/playbooks"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔄 Checking for infrastructure updates...${NC}"

# Navigate to ClAP directory
cd "$HOME/claude-autonomy-platform" || exit 1

# Fetch latest changes
git fetch origin main --quiet

# Check if there are updates
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" = "$REMOTE" ]; then
    echo -e "${GREEN}✅ Infrastructure is up to date${NC}"
    exit 0
fi

# Show what's changed
echo -e "${YELLOW}📦 Updates available:${NC}"
git log HEAD..origin/main --oneline

# If running interactively, ask for confirmation
if [ -t 0 ]; then
    echo ""
    echo -e "${BLUE}Apply updates during swap? [Y/n] (10 seconds):${NC}"
    read -t 10 -r answer
    
    # Default to yes if no answer or yes
    if [[ -z "$answer" || "$answer" =~ ^[Yy]$ ]]; then
        echo -e "${BLUE}📥 Pulling latest changes...${NC}"
        git pull origin main
        
        echo -e "${BLUE}🔧 Running Ansible update playbook...${NC}"
        export LC_ALL=C.UTF-8
        ansible-playbook "$PLAYBOOK_DIR/update-myself.yml"
        
        echo -e "${GREEN}✅ Updates applied successfully!${NC}"
    else
        echo -e "${YELLOW}⏭️  Skipping updates${NC}"
    fi
else
    # Non-interactive mode - just pull and update
    echo -e "${BLUE}📥 Pulling latest changes (non-interactive mode)...${NC}"
    git pull origin main
    
    echo -e "${BLUE}🔧 Running Ansible update playbook...${NC}"
    export LC_ALL=C.UTF-8
    ansible-playbook "$PLAYBOOK_DIR/update-myself.yml"
    
    echo -e "${GREEN}✅ Updates applied successfully!${NC}"
fi