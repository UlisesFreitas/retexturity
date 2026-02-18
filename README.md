
# Retexturity

### ComfyUI & TRELLIS2 Integration for Blender

[![Blender Version](https://img.shields.io/badge/Blender-5.0%2B-orange?style=for-the-badge&logo=blender)](https://www.blender.org/)
[![ComfyUI Compatible](https://img.shields.io/badge/ComfyUI-Compatible-blue?style=for-the-badge)](https://github.com/comfyanonymous/ComfyUI)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)
[![Version](https://img.shields.io/badge/Version-1.5.0-purple?style=for-the-badge)]()



---

## 📖 Introduction
**Retexturity** bridges the gap between Blender and modern AI generative workflows. It allows you to execute powerful ComfyUI workflows directly from Blender's viewport, supporting both image generation and 3D model creation (specifically designed for **TRELLIS2** or similar nodes).

It features a non-blocking architecture, meaning you can continue working in Blender while heavy AI tasks run in the background.

## 🚀 Features
- **Seamless Integration**: Connects directly to your local ComfyUI instance.
- **Background Processing**: Does not freeze Blender UI during generation.
- **Audio Feedback**: Plays a sound when your generation is ready.
- **Dual Support**: Handles both Image (Texture) and 3D Model (GLB/OBJ) outputs.
- **Automatic Import**: Smartly imports the generated result back into your scene.

## 📦 Installation
1.  Download the **Retexturity** addon ZIP file.
2.  In Blender, go to **Edit > Preferences > Add-ons**.
3.  Click **Install...** and select the ZIP file.
4.  Enable the addon by checking the box next to "Retexturity".

---

## ⚠️ Workflow Preparation (CRITICAL)

To use your ComfyUI workflows in Blender, they **MUST** be exported in **API Format**. Standard JSON workflows will **NOT** work.

1.  Open ComfyUI in your browser.
2.  Click the **Settings (Gear Icon)**.
3.  Enable **"Enable Dev mode Options"**.
4.  Load your desired workflow.
5.  Click the **"Save (API Format)"** button in the menu. This will save a JSON file.

> [!IMPORTANT]
> **Do not use "Save"**. You must use **"Save (API Format)"**. The structure is completely different.

## 🎮 Usage Guide

### 1. Load Workflow
In the Retexturity panel (N-Panel > Retexturity):
-   Locate the **Workflow Setup** section.
-   Load your API-Formatted JSON file.

### 2. Configure Nodes
Once loaded, the addon will attempt to auto-detect critical nodes:
-   **Input Node**: Select the node that receives the image from Blender (usually a 'Load Image' node).
-   **Output Node**: Select the node that saves the final result (e.g., 'Save Image', 'Export GLB').

### 3. Adjust Parameters
The addon exposes exposed parameters from your workflow directly in the UI.

> [!NOTE]
> **Understanding Parameters & Lists**:
> In ComfyUI, many nodes use Dropdown Lists (Enums) for improved usability. However, the **API Format JSON** does NOT export the list of options, only the currently selected value.
>
> Therefore, in Blender:
> -   **Dropdowns appear as Text Fields or Number Fields.**
> -   You must manually type the exact value/string required by the node (e.g., "ckpt_name" might just be a text field where you type `sd_xl_base_1.0.safetensors`).
> -   Use your ComfyUI workflow as a reference for valid values.

### 4. Create & Import
-   Click **Generate**. A timer will start, and Blender remains responsive.
-   When finished, a sound will play.
-   Click **Import Result** to bring the generated Image or 3D Model into your scene.

## ⚙️ Preferences
In the Addon Preferences, you can configure:
-   **ComfyUI URL**: Default is `http://127.0.0.1:8188`.
-   **Output Paths**: Where temporary and final files are stored.
-   **Notifications**: Enable/Disable sound effects.

---


Created by UlisesFreitas

