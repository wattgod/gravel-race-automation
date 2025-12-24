# Push to GitHub - Instructions

## Quick Push (if you already have a GitHub repo)

Replace `YOUR_USERNAME` and `YOUR_REPO_NAME` with your actual GitHub username and repository name:

```bash
# Add remote repository
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git

# Push to GitHub
git push -u origin main
```

## Create New GitHub Repository First

1. Go to https://github.com/new
2. Repository name: `gravel-race-database` (or your preferred name)
3. Description: "WordPress publishing system for 166+ gravel cycling races"
4. Choose Public or Private
5. **DO NOT** initialize with README, .gitignore, or license (we already have these)
6. Click "Create repository"

Then run:

```bash
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
git push -u origin main
```

## What's Been Committed

✅ All 166 races in database  
✅ CSV files for all 7 regions  
✅ Enhanced parser scripts  
✅ WordPress publishing system  
✅ Documentation  
✅ .gitignore (excludes sensitive config.py and logs)

## Files NOT Committed (by design)

- `config.py` - Contains WordPress credentials (in .gitignore)
- `push_results.json` - Runtime logs (in .gitignore)
- `__pycache__/` - Python cache (in .gitignore)

