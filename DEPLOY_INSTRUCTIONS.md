# How to Deploy Your Dashboard

## 1. Configure Git (Fix for "Run git config" error)
To fix the commit error, you need to tell Git who you are. Run these commands in your terminal (replace with your info):
```bash
git config --global user.email "you@example.com"
git config --global user.name "Your Name"
```

## 2. Commit and Push
Once Git is configured, run these commands to push your dashboard:
```bash
git add .
git commit -m "Add web dashboard and firebase config"
git push origin main
```

## 3. Enable GitHub Pages
1. Go to your repository on **GitHub.com**.
2. Click **Settings** (top right tab).
3. On the left sidebar, click **Pages**.
4. Under **Build and deployment**:
   - **Source**: Select `GitHub Actions` (Beta or Standard).
5. The deployment will start automatically. You can watch it in the **Actions** tab.

## 4. View Your Dashboard
Once the Action finishes (green checkmark), your dashboard will be live! The URL will usually be:
`https://<your-username>.github.io/<your-repo-name>/`
