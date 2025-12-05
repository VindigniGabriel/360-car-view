"""
Lazy loading module for 360° viewer.
Generates viewer with progressive frame loading.
"""
import math
import os


def generate_lazy_viewer(
    output_path: str,
    num_frames: int,
    frame_width: int,
    frame_height: int,
    frame_ext: str = "webp",
    preload_count: int = 5,
) -> str:
    """
    Generate a 360° viewer with lazy loading of individual frames.
    
    This viewer loads frames on-demand as the user rotates,
    reducing initial load time for high-frame-count viewers.
    
    Args:
        output_path: Path for output HTML file
        num_frames: Number of frames
        frame_width: Frame width
        frame_height: Frame height
        frame_ext: Frame file extension
        preload_count: Number of frames to preload around current
    
    Returns:
        Path to created HTML file
    """
    html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>360° Car Viewer</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        
        h1 {{ color: white; margin-bottom: 24px; font-size: 24px; }}
        
        .viewer-container {{
            background: #fff;
            border-radius: 16px;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
            padding: 20px;
            max-width: 100%;
        }}
        
        .viewer {{
            width: {frame_width}px;
            height: {frame_height}px;
            max-width: 100%;
            position: relative;
            cursor: grab;
            border-radius: 8px;
            overflow: hidden;
            background: #f3f4f6;
        }}
        
        .viewer:active {{ cursor: grabbing; }}
        
        .viewer img {{
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            object-fit: cover;
            opacity: 0;
            transition: opacity 0.15s ease;
        }}
        
        .viewer img.active {{ opacity: 1; }}
        .viewer img.loaded {{ }}
        
        .loading-indicator {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            color: #9ca3af;
            font-size: 14px;
        }}
        
        .controls {{
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 16px;
            margin-top: 16px;
            padding-top: 16px;
            border-top: 1px solid #e5e7eb;
        }}
        
        .btn {{
            background: #3b82f6;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            transition: background 0.2s;
        }}
        
        .btn:hover {{ background: #2563eb; }}
        
        .frame-indicator {{
            font-size: 14px;
            color: #6b7280;
            min-width: 100px;
            text-align: center;
        }}
        
        .progress-bar {{
            width: 100%;
            height: 4px;
            background: #e5e7eb;
            border-radius: 2px;
            margin-top: 12px;
            overflow: hidden;
        }}
        
        .progress-bar-fill {{
            height: 100%;
            background: #3b82f6;
            width: 0%;
            transition: width 0.3s ease;
        }}
        
        @media (max-width: 840px) {{
            .viewer {{
                width: 100%;
                height: auto;
                aspect-ratio: {frame_width} / {frame_height};
            }}
        }}
    </style>
</head>
<body>
    <h1>360° Car Viewer</h1>
    
    <div class="viewer-container">
        <div class="viewer" id="viewer">
            <div class="loading-indicator" id="loadingIndicator">Loading...</div>
        </div>
        
        <div class="progress-bar">
            <div class="progress-bar-fill" id="progressBar"></div>
        </div>
        
        <div class="controls">
            <button class="btn" id="autoRotateBtn">▶ Auto Rotate</button>
            <span class="frame-indicator" id="frameIndicator">1 / {num_frames}</span>
            <button class="btn" id="resetBtn">↺ Reset</button>
        </div>
    </div>
    
    <script>
        const viewer = document.getElementById('viewer');
        const frameIndicator = document.getElementById('frameIndicator');
        const progressBar = document.getElementById('progressBar');
        const loadingIndicator = document.getElementById('loadingIndicator');
        const autoRotateBtn = document.getElementById('autoRotateBtn');
        const resetBtn = document.getElementById('resetBtn');
        
        const config = {{
            totalFrames: {num_frames},
            frameExt: '{frame_ext}',
            preloadCount: {preload_count},
        }};
        
        let currentFrame = 0;
        let isDragging = false;
        let startX = 0;
        let autoRotate = false;
        let autoRotateInterval = null;
        let loadedFrames = new Set();
        let frameElements = {{}};
        
        // Create frame elements
        for (let i = 0; i < config.totalFrames; i++) {{
            const img = document.createElement('img');
            img.dataset.frame = i;
            img.dataset.src = `frames/frame_${{String(i).padStart(3, '0')}}.${{config.frameExt}}`;
            frameElements[i] = img;
            viewer.appendChild(img);
        }}
        
        function loadFrame(frameIndex) {{
            if (loadedFrames.has(frameIndex)) return Promise.resolve();
            
            const img = frameElements[frameIndex];
            if (!img || img.src) return Promise.resolve();
            
            return new Promise((resolve) => {{
                img.onload = () => {{
                    loadedFrames.add(frameIndex);
                    img.classList.add('loaded');
                    updateProgress();
                    resolve();
                }};
                img.onerror = resolve;
                img.src = img.dataset.src;
            }});
        }}
        
        function preloadAround(frameIndex) {{
            const promises = [];
            for (let offset = -config.preloadCount; offset <= config.preloadCount; offset++) {{
                const idx = (frameIndex + offset + config.totalFrames) % config.totalFrames;
                promises.push(loadFrame(idx));
            }}
            return Promise.all(promises);
        }}
        
        function updateProgress() {{
            const percent = (loadedFrames.size / config.totalFrames) * 100;
            progressBar.style.width = `${{percent}}%`;
            
            if (loadedFrames.size >= config.totalFrames) {{
                loadingIndicator.style.display = 'none';
            }}
        }}
        
        function updateFrame(frame) {{
            currentFrame = ((frame % config.totalFrames) + config.totalFrames) % config.totalFrames;
            
            // Hide all frames
            Object.values(frameElements).forEach(img => img.classList.remove('active'));
            
            // Show current frame
            const currentImg = frameElements[currentFrame];
            if (currentImg) {{
                currentImg.classList.add('active');
            }}
            
            frameIndicator.textContent = `${{currentFrame + 1}} / ${{config.totalFrames}}`;
            
            // Preload nearby frames
            preloadAround(currentFrame);
        }}
        
        function handleDragStart(e) {{
            isDragging = true;
            startX = e.type.includes('touch') ? e.touches[0].clientX : e.clientX;
            viewer.style.cursor = 'grabbing';
            stopAutoRotate();
        }}
        
        function handleDragMove(e) {{
            if (!isDragging) return;
            
            const clientX = e.type.includes('touch') ? e.touches[0].clientX : e.clientX;
            const deltaX = clientX - startX;
            const sensitivity = 10;
            const frameDelta = Math.floor(deltaX / sensitivity);
            
            if (frameDelta !== 0) {{
                updateFrame(currentFrame - frameDelta);
                startX = clientX;
            }}
        }}
        
        function handleDragEnd() {{
            isDragging = false;
            viewer.style.cursor = 'grab';
        }}
        
        function startAutoRotate() {{
            autoRotate = true;
            autoRotateBtn.textContent = '⏸ Pause';
            autoRotateInterval = setInterval(() => updateFrame(currentFrame + 1), 100);
        }}
        
        function stopAutoRotate() {{
            autoRotate = false;
            autoRotateBtn.textContent = '▶ Auto Rotate';
            if (autoRotateInterval) {{
                clearInterval(autoRotateInterval);
                autoRotateInterval = null;
            }}
        }}
        
        // Event listeners
        viewer.addEventListener('mousedown', handleDragStart);
        document.addEventListener('mousemove', handleDragMove);
        document.addEventListener('mouseup', handleDragEnd);
        viewer.addEventListener('touchstart', handleDragStart, {{ passive: true }});
        document.addEventListener('touchmove', handleDragMove, {{ passive: true }});
        document.addEventListener('touchend', handleDragEnd);
        viewer.addEventListener('contextmenu', e => e.preventDefault());
        
        autoRotateBtn.addEventListener('click', () => {{
            autoRotate ? stopAutoRotate() : startAutoRotate();
        }});
        
        resetBtn.addEventListener('click', () => {{
            stopAutoRotate();
            updateFrame(0);
        }});
        
        document.addEventListener('keydown', (e) => {{
            if (e.key === 'ArrowLeft') updateFrame(currentFrame - 1);
            else if (e.key === 'ArrowRight') updateFrame(currentFrame + 1);
            else if (e.key === ' ') {{
                e.preventDefault();
                autoRotate ? stopAutoRotate() : startAutoRotate();
            }}
        }});
        
        // Initialize
        loadFrame(0).then(() => {{
            updateFrame(0);
            // Preload all frames in background
            for (let i = 1; i < config.totalFrames; i++) {{
                setTimeout(() => loadFrame(i), i * 50);
            }}
        }});
    </script>
</body>
</html>'''
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    return output_path
