#!/bin/bash
# Quick start example for oryxforge CLI

set -e

echo "Quick Start: OryxForge CLI Setup"
echo "================================"

# Check dependencies
echo "Checking dependencies..."
if ! command -v oryxforge &> /dev/null; then
    echo "❌ oryxforge CLI not found. Please install it first:"
    echo "   pip install oryxforge"
    exit 1
fi

# Check environment variables
if [ -z "$SUPABASE_URL" ] || [ -z "$SUPABASE_ANON_KEY" ]; then
    echo "❌ Missing environment variables. Please set:"
    echo "   export SUPABASE_URL='https://your-project.supabase.co'"
    echo "   export SUPABASE_ANON_KEY='your-anon-key-here'"
    exit 1
fi

echo "✅ Dependencies and environment OK"
echo ""

# Get user ID from argument or prompt
if [ $# -eq 0 ]; then
    read -p "Enter your user ID: " USER_ID
else
    USER_ID="$1"
fi

echo "Setting up with user ID: $USER_ID"
echo ""

# Set user ID
echo "1. Setting user ID..."
oryxforge admin userid set "$USER_ID"

# Verify user ID
echo "   Verifying configuration..."
oryxforge admin userid get

# Create first project
echo "2. Creating your first project..."
oryxforge admin projects create "Getting Started Project"

# Pull and activate
echo "3. Setting up project directory..."
mkdir -p ./my-oryx-project
cd ./my-oryx-project

echo "4. Pulling project (interactive selection)..."
oryxforge admin pull

echo "5. Final status..."
oryxforge admin status

echo ""
echo "🎉 Quick start complete!"
echo "You're now ready to use oryxforge in this directory."
echo ""
echo "Next steps:"
echo "- Use 'oryxforge admin dataset activate' to switch datasets"
echo "- Use 'oryxforge admin sheet activate' to switch datasheets"
echo "- Use 'oryxforge admin status' to check your current configuration"