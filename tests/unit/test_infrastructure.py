"""
Basic infrastructure validation tests for Phase 0
"""
import pytest
import yaml
import os

def test_sam_template_exists():
    """Verify SAM template exists and is valid YAML"""
    template_path = "template-arm64-optimized.yaml"
    assert os.path.exists(template_path), "SAM template file should exist"
    
    with open(template_path, 'r') as f:
        template = yaml.safe_load(f)
    
    # Basic SAM template structure validation
    assert 'AWSTemplateFormatVersion' in template
    assert 'Transform' in template
    assert template['Transform'] == 'AWS::Serverless-2016-10-31'
    assert 'Resources' in template
    
def test_cloudformation_templates_exist():
    """Verify CloudFormation infrastructure templates exist"""
    templates = [
        "infrastructure/oidc-provider.yaml",
        "infrastructure/deployment-bucket.yaml"
    ]
    
    for template_path in templates:
        assert os.path.exists(template_path), f"Template {template_path} should exist"
        
        with open(template_path, 'r') as f:
            template = yaml.safe_load(f)
            
        assert 'AWSTemplateFormatVersion' in template
        assert 'Resources' in template

def test_github_workflow_exists():
    """Verify GitHub Actions workflow exists"""
    workflow_path = ".github/workflows/deploy.yml"
    assert os.path.exists(workflow_path), "Deployment workflow should exist"
    
    with open(workflow_path, 'r') as f:
        workflow = yaml.safe_load(f)
    
    assert 'name' in workflow
    assert 'jobs' in workflow
    assert 'validate' in workflow['jobs']

def test_phase_0_files_structure():
    """Verify all Phase 0 files are in place"""
    required_files = [
        "template-arm64-optimized.yaml",
        "infrastructure/oidc-provider.yaml", 
        "infrastructure/deployment-bucket.yaml",
        ".github/workflows/deploy.yml",
        "CI_CD_SETUP_GUIDE.md"
    ]
    
    for file_path in required_files:
        assert os.path.exists(file_path), f"Phase 0 requires {file_path}"