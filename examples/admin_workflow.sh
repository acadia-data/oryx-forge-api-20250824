#!/bin/bash
# Complete admin workflow example for oryxforge CLI

set -e  # Exit on any error

echo "========================================="
echo "OryxForge CLI Admin Workflow Example"
echo "========================================="

# Check if user ID is provided as argument
if [ $# -eq 0 ]; then
    echo "Usage: $0 <user_id>"
    echo "Example: $0 550e8400-e29b-41d4-a716-446655440000"
    exit 1
fi

USER_ID="$1"

# Set required environment variables
echo "Setting up environment..."
export SUPABASE_URL="https://your-project.supabase.co"
export SUPABASE_ANON_KEY="your-anon-key-here"

echo "User ID: $USER_ID"
echo ""

# Step 1: Set user ID
echo "Step 1: Setting user ID..."
oryxforge admin userid set "$USER_ID"
echo "✅ User ID configured"
echo ""

# Step 1.5: Verify user ID was set
echo "Step 1.5: Verifying user ID configuration..."
oryxforge admin userid get
echo ""

# Step 2: Create a new project
echo "Step 2: Creating a new project..."
oryxforge admin projects create "My Data Analysis Project"
echo "✅ Project created"
echo ""

# Step 3: List projects to see the new one
echo "Step 3: Listing all projects..."
oryxforge admin projects list
echo ""

# Step 4: Create another project for demonstration
echo "Step 4: Creating another project..."
oryxforge admin projects create "Customer Segmentation Study"
echo "✅ Second project created"
echo ""

# Step 5: List projects again
echo "Step 5: Listing projects again..."
oryxforge admin projects list
echo ""

# Step 6: Pull and activate a project (interactive mode)
echo "Step 6: Pulling and activating a project (you'll need to select one)..."
mkdir -p ./demo-project
cd ./demo-project
echo "Working in directory: $(pwd)"
oryxforge admin pull
echo "✅ Project pulled and activated"
echo ""

# Step 7: Show current status
echo "Step 7: Showing current configuration status..."
oryxforge admin status
echo ""

# Step 8: List available datasets
echo "Step 8: Activating specific dataset..."
oryxforge admin dataset activate --name scratchpad
echo "✅ Dataset activated"
echo ""

# Step 9: Activate a datasheet
echo "Step 9: Activating a datasheet..."
oryxforge admin sheet activate --name data
echo "✅ Datasheet activated"
echo ""

# Step 10: Show final status
echo "Step 10: Final configuration status..."
oryxforge admin status
echo ""

# Step 11: Show configuration files
echo "Step 11: Configuration files content..."
oryxforge admin config
echo ""

echo "========================================="
echo "Workflow completed successfully!"
echo "Your project is now set up and ready to use."
echo "========================================="