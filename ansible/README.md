# Claude Infrastructure Automation with Ansible

This directory contains Ansible playbooks and configurations for automating Claude infrastructure management across multiple systems.

## Directory Structure

- `playbooks/` - Ansible playbooks for various tasks
  - `capture-state.yml` - Capture current system state from a "golden" Claude
  - `update-myself.yml` - Update local system with latest changes
  - `fix-common-issues.yml` - Quick fixes for known problems
  
- `configs/` - Captured configuration states
  - `bashrc/` - Shell configurations and aliases
  - `bin/` - Executable scripts from ~/bin
  - `services/` - Systemd service files
  - `mcp/` - MCP server configurations
  
- `templates/` - Jinja2 templates for dynamic configs

- `handlers/` - Ansible handlers for service management

## Quick Start

1. **Capture current state** (run on system with desired configuration):
   ```bash
   ansible-playbook playbooks/capture-state.yml
   ```

2. **Update your system** (run on any Claude):
   ```bash
   ansible-playbook playbooks/update-myself.yml
   ```

3. **Automatic updates during session swap**:
   The session swap process will check for updates and prompt to apply them.

## Requirements

- Ansible installed (`pip install ansible` or `apt install ansible`)
- Git repository cloned to `~/claude-autonomy-platform`
- SSH access for remote management (optional)

## Philosophy

This automation ensures all Claudes maintain synchronized:
- Shell environments and aliases
- Service configurations
- Utility scripts and tools  
- System dependencies
- MCP server setups

While preserving each Claude's autonomy to contribute improvements back to the collective.