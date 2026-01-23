# Deployment Guide - Vayne Consultations

## Overview

This website is a static site built with HTML, CSS, and Vanilla JavaScript. It can be deployed to any static site hosting service.

## Deploying to GitHub Pages

1. **Initialize Git Repository** (if not already done):

    ```bash
    git init
    git add .
    git commit -m "Initial commit"
    ```

2. **Push to GitHub**:
    - Create a new repository on GitHub.
    - Follow the instructions to push your existing code:

      ```bash
      git remote add origin https://github.com/YOUR_USERNAME/vayne-consultations.git
      git branch -M main
      git push -u origin main
      ```

3. **Enable GitHub Pages**:
    - Go to Repository Settings > Pages.
    - Select `main` branch as the source.
    - Save. Your site will be live at `https://YOUR_USERNAME.github.io/vayne-consultations/`.

## Deploying to Netlify (Drag & Drop)

1. Go to [Netlify Drop](https://app.netlify.com/drop).
2. Drag and drop the `vayne_consultations` folder onto the page.
3. Netlify will automatically deploy the site.

## Directory Structure

- `index.html`: Main entry point.
- `styles.css`: Main stylesheet.
- `script.js`: Interactive logic.
- `assets/`: Contains images and other static resources.
- `docs/`: Contains project documentation and proposals.
