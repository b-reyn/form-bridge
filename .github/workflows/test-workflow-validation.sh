#!/bin/bash
# Test script to validate GitHub Actions workflow configuration locally

echo "🔍 GitHub Actions Workflow Validation Test"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Track failures
FAILED=0

# Function to check if file exists
check_file() {
    local file=$1
    local description=$2
    
    if [ -f "$file" ]; then
        echo -e "${GREEN}✅${NC} $description exists: $file"
        return 0
    else
        echo -e "${RED}❌${NC} $description missing: $file"
        FAILED=$((FAILED + 1))
        return 1
    fi
}

# Function to validate YAML syntax
check_yaml() {
    local file=$1
    
    # Skip CloudFormation templates as they use special tags
    if [[ "$file" == *"template"*.yaml ]] || [[ "$file" == *"template"*.yml ]]; then
        if [ -f "$file" ]; then
            echo -e "${GREEN}✅${NC} CloudFormation template exists: $file"
            return 0
        else
            echo -e "${RED}❌${NC} CloudFormation template missing: $file"
            FAILED=$((FAILED + 1))
            return 1
        fi
    fi
    
    if command -v python3 > /dev/null 2>&1; then
        if python3 -c "import yaml; yaml.safe_load(open('$file'))" 2>/dev/null; then
            echo -e "${GREEN}✅${NC} Valid YAML syntax: $file"
            return 0
        else
            echo -e "${RED}❌${NC} Invalid YAML syntax: $file"
            FAILED=$((FAILED + 1))
            return 1
        fi
    else
        echo -e "${YELLOW}⚠️${NC}  Python not available for YAML validation"
        return 0
    fi
}

# Function to check Python syntax
check_python() {
    local file=$1
    
    if command -v python3 > /dev/null 2>&1; then
        if python3 -m py_compile "$file" 2>/dev/null; then
            echo -e "${GREEN}✅${NC} Valid Python syntax: $file"
            return 0
        else
            echo -e "${RED}❌${NC} Invalid Python syntax: $file"
            FAILED=$((FAILED + 1))
            return 1
        fi
    else
        echo -e "${YELLOW}⚠️${NC}  Python not available for syntax validation"
        return 0
    fi
}

echo "1. Checking Ultra-Simple Architecture Files"
echo "-------------------------------------------"
check_file "ultra-simple/template-minimal.yaml" "SAM template"
check_file "ultra-simple/handler.py" "Lambda handler"
check_file "ultra-simple/requirements.txt" "Python requirements"
check_file "ultra-simple/deploy.sh" "Deployment script"
echo ""

echo "2. Checking GitHub Actions Workflow"
echo "------------------------------------"
check_file ".github/workflows/deploy-ultra-simple.yml" "Ultra-simple workflow"

# Check if old MVP workflow is disabled/removed
if [ -f ".github/workflows/deploy-mvp.yml" ]; then
    echo -e "${RED}❌${NC} Old MVP workflow still exists (should be removed/disabled)"
    FAILED=$((FAILED + 1))
else
    echo -e "${GREEN}✅${NC} Old MVP workflow removed"
fi
echo ""

echo "3. Validating File Syntax"
echo "-------------------------"
check_yaml "ultra-simple/template-minimal.yaml"
check_yaml ".github/workflows/deploy-ultra-simple.yml"
check_python "ultra-simple/handler.py"
echo ""

echo "4. Checking Workflow Path Triggers"
echo "-----------------------------------"
if grep -q "ultra-simple/\*\*" .github/workflows/deploy-ultra-simple.yml 2>/dev/null; then
    echo -e "${GREEN}✅${NC} Workflow monitors ultra-simple directory"
else
    echo -e "${YELLOW}⚠️${NC}  Workflow may not be monitoring ultra-simple directory correctly"
fi

if grep -q "lambdas/\*\*" .github/workflows/deploy-ultra-simple.yml 2>/dev/null; then
    echo -e "${RED}❌${NC} Workflow still monitors non-existent lambdas directory"
    FAILED=$((FAILED + 1))
else
    echo -e "${GREEN}✅${NC} Workflow doesn't monitor old lambdas directory"
fi
echo ""

echo "5. Checking Workflow File References"
echo "-------------------------------------"
# Check that workflow references correct files
WORKFLOW_FILE=".github/workflows/deploy-ultra-simple.yml"
if [ -f "$WORKFLOW_FILE" ]; then
    # Check for correct template reference
    if grep -q "ultra-simple/template-minimal.yaml" "$WORKFLOW_FILE"; then
        echo -e "${GREEN}✅${NC} Workflow references correct SAM template"
    else
        echo -e "${RED}❌${NC} Workflow doesn't reference ultra-simple/template-minimal.yaml"
        FAILED=$((FAILED + 1))
    fi
    
    # Check for correct handler reference
    if grep -q "ultra-simple/handler.py" "$WORKFLOW_FILE"; then
        echo -e "${GREEN}✅${NC} Workflow references correct handler"
    else
        echo -e "${RED}❌${NC} Workflow doesn't reference ultra-simple/handler.py"
        FAILED=$((FAILED + 1))
    fi
    
    # Check for working directory change
    if grep -q "cd ultra-simple" "$WORKFLOW_FILE"; then
        echo -e "${GREEN}✅${NC} Workflow changes to ultra-simple directory for deployment"
    else
        echo -e "${YELLOW}⚠️${NC}  Workflow may not change to correct directory"
    fi
fi
echo ""

echo "=========================================="
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ All validation checks passed!${NC}"
    echo "Your GitHub Actions workflow should now work correctly."
    echo ""
    echo "Next steps:"
    echo "1. Commit these changes to your repository"
    echo "2. Push to GitHub to trigger the workflow"
    echo "3. Check the Actions tab in GitHub for deployment status"
    exit 0
else
    echo -e "${RED}❌ $FAILED validation check(s) failed${NC}"
    echo "Please fix the issues above before pushing to GitHub."
    exit 1
fi