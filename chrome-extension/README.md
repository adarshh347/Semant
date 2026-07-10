# Sharirasutra Chrome Extension

A Chrome extension that lets you save images from any website to your Sharirasutra gallery with one click.

## Installation

1. **Open Chrome Extensions:**
   - Go to `chrome://extensions/` in your browser
   - Or: Menu → More Tools → Extensions

2. **Enable Developer Mode:**
   - Toggle the "Developer mode" switch in the top-right corner

3. **Load the Extension:**
   - Click "Load unpacked"
   - Navigate to this `chrome-extension` folder
   - Select the folder

4. **You're Done!**
   - You should see the Sharirasutra icon in your extensions bar
   - Pin it for easy access

## Usage

1. **Browse any website** normally
2. **Hover over an image** you want to save
3. A **"Save to Sharirasutra"** button will appear on the image
4. **Click the button** to save the image to your gallery

## Requirements

- The Sharirasutra backend must be running (`uvicorn backend.main:app --reload --host 0.0.0.0 --port 5007`)
- The extension connects to `localhost:8000`

## Features

- ✨ One-click image saving
- 🖼️ Works on any website
- 🔍 Only shows button on images larger than 100x100px
- 📱 Instant feedback (Saving... → ✓ Saved!)

## Icon Generation

The extension needs PNG icons. To generate them from the SVG:

```bash
# Using ImageMagick (if installed)
convert icons/icon.svg -resize 16x16 icons/icon16.png
convert icons/icon.svg -resize 48x48 icons/icon48.png
convert icons/icon.svg -resize 128x128 icons/icon128.png
```

Or create simple colored squares as placeholders.

## Troubleshooting

**"Backend not running" error:**
- Make sure uvicorn is running on port 5007
- Check the terminal for any errors

**Button doesn't appear:**
- The image might be too small (< 100x100)
- Try refreshing the page
- Check the browser console for errors

**Save fails:**
- Some websites block image downloads (CORS)
- Try right-clicking and copying the image URL directly
