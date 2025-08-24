#!/bin/bash
# Safe cleanup script for ClAP temporary files
# As per Linear issue POSS-272

set -e  # Exit on error

echo "ClAP Safe Cleanup Script"
echo "========================"
echo "This will remove temporary files that don't affect functionality."
echo ""

# Function to count files before deletion
count_files() {
    local pattern="$1"
    local count=$(find . -name "$pattern" 2>/dev/null | wc -l)
    echo "$count"
}

# Function to show what will be deleted
preview_cleanup() {
    echo "Preview of files to be deleted:"
    echo ""
    
    echo "Python cache directories (__pycache__):"
    find . -name "__pycache__" -type d 2>/dev/null | head -10
    local pycache_count=$(count_files "__pycache__")
    if [ $pycache_count -gt 10 ]; then
        echo "... and $((pycache_count - 10)) more"
    fi
    echo ""
    
    echo "Backup files (.bak, .tmp, .orig):"
    find . \( -name "*.bak" -o -name "*.tmp" -o -name "*.orig" \) 2>/dev/null | head -10
    local backup_count=$(find . \( -name "*.bak" -o -name "*.tmp" -o -name "*.orig" \) 2>/dev/null | wc -l)
    if [ $backup_count -gt 10 ]; then
        echo "... and $((backup_count - 10)) more"
    fi
    echo ""
    
    echo "Old session logs (session_ended_*.log):"
    find . -name "session_ended_*.log" 2>/dev/null | head -10
    local session_count=$(count_files "session_ended_*.log")
    if [ $session_count -gt 10 ]; then
        echo "... and $((session_count - 10)) more"
    fi
    echo ""
}

# Main cleanup function
perform_cleanup() {
    echo "Starting cleanup..."
    echo ""
    
    # Remove Python cache directories
    echo -n "Removing Python cache directories... "
    find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
    echo "done"
    
    # Remove backup files
    echo -n "Removing .bak, .tmp, .orig files... "
    find . \( -name "*.bak" -o -name "*.tmp" -o -name "*.orig" \) -exec rm -f {} + 2>/dev/null || true
    echo "done"
    
    # Remove old session logs
    echo -n "Removing old session logs... "
    find . -name "session_ended_*.log" -exec rm -f {} + 2>/dev/null || true
    echo "done"
    
    # Remove empty directories
    echo -n "Removing empty directories... "
    find . -type d -empty -delete 2>/dev/null || true
    echo "done"
    
    echo ""
    echo "Cleanup complete!"
}

# Show current directory
echo "Working directory: $(pwd)"
echo ""

# Preview what will be deleted
preview_cleanup

# Ask for confirmation
echo ""
read -p "Do you want to proceed with cleanup? (y/N) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    perform_cleanup
    
    # Test that services still work
    echo ""
    echo "Testing services..."
    if systemctl --user is-active autonomous-timer.service >/dev/null 2>&1; then
        echo "✓ autonomous-timer.service is running"
    else
        echo "⚠ autonomous-timer.service is not running"
    fi
    
    if systemctl --user is-active session-swap-monitor.service >/dev/null 2>&1; then
        echo "✓ session-swap-monitor.service is running"
    else
        echo "⚠ session-swap-monitor.service is not running"
    fi
    
    echo ""
    echo "✅ Cleanup completed successfully!"
else
    echo "Cleanup cancelled."
fi