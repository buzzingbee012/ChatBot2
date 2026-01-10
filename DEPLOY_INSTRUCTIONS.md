# How to Deploy Your Dashboard (Automatic Updates)

To automatically deploy changes when you push to GitHub, connect Netlify to your repository.

## 1. Push Your Code to GitHub
(If you haven't already)
```bash
git add .
git commit -m "Update dashboard"
git push origin main
```

## Option A: Create New Site (Easiest)
1. Log in to **[app.netlify.com](https://app.netlify.com)**.
2. Click **"Add new site"** > **"Import from an existing project"**.
3. Select **GitHub**.
4. Authorize Netlify and choose your `ChatBot` repository.

## Option B: Link Existing Site
If you already created a site via Drag & Drop:
1. Go to your **Site Settings**.
2. Click **Build & deploy** in the sidebar.
3. Click **Link site to Git**.
4. Select **GitHub** and choose your repository.

## 3. Configure Build Settings (Critical!)
For both options, ensure these settings are correct:
- **Base directory**: `web_dashboard`
- **Publish directory**: `web_dashboard` (or leave empty if Base is set)
- **Build command**: (Leave empty)

Click **Deploy Site**.

## 4. Done!
Now, whenever you run `git push`, Netlify will see the change and update your site automatically within seconds.

