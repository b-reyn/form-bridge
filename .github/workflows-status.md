# GitHub Actions Status

## Current Workflows

### Deploy MVP - Fast & Reliable
[![Deploy MVP](https://github.com/YOUR_USERNAME/form-bridge/actions/workflows/deploy-mvp.yml/badge.svg)](https://github.com/YOUR_USERNAME/form-bridge/actions/workflows/deploy-mvp.yml)

**Status**: Active  
**Purpose**: Fast, reliable deployment of Form-Bridge MVP  
**Trigger**: Push to main/develop, manual dispatch  
**Timeout**: 10 minutes guaranteed  

**Features**:
- x86_64 builds for speed
- Minimal dependencies 
- Comprehensive validation
- Automatic smoke testing
- Environment-specific deployment

## Usage

### Automatic Deployment
- Push to `main` → Production deployment
- Push to `develop` → Staging deployment  
- Other branches → Development deployment

### Manual Deployment
1. Go to Actions tab
2. Select "Deploy MVP - Fast & Reliable"
3. Click "Run workflow"
4. Choose environment
5. Click "Run workflow"

## Expected Performance
- **Validation**: < 2 minutes
- **Deployment**: < 8 minutes
- **Total**: < 10 minutes

## Monitoring
- View real-time logs in GitHub Actions
- Check CloudWatch for Lambda execution logs
- Use validation script for health checks

---
*Replace YOUR_USERNAME with your actual GitHub username for working badges*