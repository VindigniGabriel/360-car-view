"""
360° Viewer HTML generator.
Creates an interactive HTML viewer for the processed frames.
"""
import math


def generate_viewer(
    output_path: str,
    num_frames: int,
    frame_width: int,
    frame_height: int,
    use_sprite: bool = True,
    use_webp: bool = True,
    enable_lazy_loading: bool = True,
    transparent: bool = False,
) -> str:
    """
    Generate an interactive 360° viewer HTML file.
    
    Args:
        output_path: Path for output HTML file
        num_frames: Number of frames in the sequence
        frame_width: Width of each frame
        frame_height: Height of each frame
        use_sprite: Whether to use sprite sheet (True) or individual frames (False)
        use_webp: Whether to use WebP format for images
        enable_lazy_loading: Whether to enable lazy loading for individual frames
        transparent: Whether the images have transparent background
    
    Returns:
        Path to the created HTML file
    """
    columns = int(math.ceil(math.sqrt(num_frames)))
    
    if transparent:
        sprite_ext = "png"
        frame_ext = "png"
    else:
        sprite_ext = "webp" if use_webp else "jpg"
        frame_ext = "webp" if use_webp else "jpg"
    
    html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>360° Car Viewer</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        
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
            background-color: {'transparent' if transparent else '#f5f5f5'};
            background-image: url('sprite.{sprite_ext}');
            background-size: {columns * frame_width}px auto;
            background-position: 0 0;
            background-repeat: no-repeat;
            cursor: grab;
            border-radius: 8px;
            user-select: none;
            -webkit-user-select: none;
        }}
        
        .viewer-container.transparent {{
            background: linear-gradient(45deg, #e0e0e0 25%, transparent 25%),
                        linear-gradient(-45deg, #e0e0e0 25%, transparent 25%),
                        linear-gradient(45deg, transparent 75%, #e0e0e0 75%),
                        linear-gradient(-45deg, transparent 75%, #e0e0e0 75%);
            background-size: 20px 20px;
            background-position: 0 0, 0 10px, 10px -10px, -10px 0px;
            background-color: #f0f0f0;
        }}
        
        .bg-selector {{
            display: {'flex' if transparent else 'none'};
            gap: 8px;
            margin-top: 12px;
            justify-content: center;
        }}
        
        .bg-option {{
            width: 30px;
            height: 30px;
            border-radius: 50%;
            cursor: pointer;
            border: 2px solid #ccc;
            transition: border-color 0.2s;
        }}
        
        .bg-option:hover, .bg-option.active {{
            border-color: #3b82f6;
        }}
        
        .bg-option.white {{ background: white; }}
        .bg-option.black {{ background: #1a1a1a; }}
        .bg-option.gray {{ background: #808080; }}
        .bg-option.checker {{
            background: linear-gradient(45deg, #ccc 25%, transparent 25%),
                        linear-gradient(-45deg, #ccc 25%, transparent 25%),
                        linear-gradient(45deg, transparent 75%, #ccc 75%),
                        linear-gradient(-45deg, transparent 75%, #ccc 75%);
            background-size: 10px 10px;
            background-color: #fff;
        }}
        
        .viewer:active {{
            cursor: grabbing;
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
            font-weight: 500;
            transition: background 0.2s;
        }}
        
        .btn:hover {{
            background: #2563eb;
        }}
        
        .btn:disabled {{
            background: #9ca3af;
            cursor: not-allowed;
        }}
        
        .frame-indicator {{
            font-size: 14px;
            color: #6b7280;
            min-width: 80px;
            text-align: center;
        }}
        
        .instructions {{
            color: #9ca3af;
            font-size: 12px;
            margin-top: 12px;
            text-align: center;
        }}
        
        h1 {{
            color: white;
            margin-bottom: 24px;
            font-size: 24px;
            font-weight: 600;
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
    
    <div class="viewer-container{' transparent' if transparent else ''}" id="viewerContainer">
        <div class="viewer" id="viewer"></div>
        
        <div class="controls">
            <button class="btn" id="autoRotateBtn">▶ Auto Rotate</button>
            <span class="frame-indicator" id="frameIndicator">1 / {num_frames}</span>
            <button class="btn" id="resetBtn">↺ Reset</button>
        </div>
        
        <div class="bg-selector">
            <div class="bg-option white active" data-bg="white" title="White"></div>
            <div class="bg-option black" data-bg="black" title="Black"></div>
            <div class="bg-option gray" data-bg="gray" title="Gray"></div>
            <div class="bg-option checker" data-bg="checker" title="Transparent"></div>
        </div>
        
        <p class="instructions">Drag left/right to rotate • {'Click colors to change background' if transparent else 'Use mouse wheel to zoom'}</p>
    </div>
    
    <script>
        const viewer = document.getElementById('viewer');
        const frameIndicator = document.getElementById('frameIndicator');
        const autoRotateBtn = document.getElementById('autoRotateBtn');
        const resetBtn = document.getElementById('resetBtn');
        
        const config = {{
            totalFrames: {num_frames},
            columns: {columns},
            frameWidth: {frame_width},
            frameHeight: {frame_height},
        }};
        
        let currentFrame = 0;
        let isDragging = false;
        let startX = 0;
        let autoRotate = false;
        let autoRotateInterval = null;
        
        function updateFrame(frame) {{
            currentFrame = ((frame % config.totalFrames) + config.totalFrames) % config.totalFrames;
            
            const col = currentFrame % config.columns;
            const row = Math.floor(currentFrame / config.columns);
            
            const x = -col * config.frameWidth;
            const y = -row * config.frameHeight;
            
            viewer.style.backgroundPosition = `${{x}}px ${{y}}px`;
            frameIndicator.textContent = `${{currentFrame + 1}} / ${{config.totalFrames}}`;
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
            
            // Sensitivity: pixels per frame
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
            autoRotateInterval = setInterval(() => {{
                updateFrame(currentFrame + 1);
            }}, 100);
        }}
        
        function stopAutoRotate() {{
            autoRotate = false;
            autoRotateBtn.textContent = '▶ Auto Rotate';
            if (autoRotateInterval) {{
                clearInterval(autoRotateInterval);
                autoRotateInterval = null;
            }}
        }}
        
        // Mouse events
        viewer.addEventListener('mousedown', handleDragStart);
        document.addEventListener('mousemove', handleDragMove);
        document.addEventListener('mouseup', handleDragEnd);
        
        // Touch events
        viewer.addEventListener('touchstart', handleDragStart, {{ passive: true }});
        document.addEventListener('touchmove', handleDragMove, {{ passive: true }});
        document.addEventListener('touchend', handleDragEnd);
        
        // Prevent context menu on long press
        viewer.addEventListener('contextmenu', e => e.preventDefault());
        
        // Button events
        autoRotateBtn.addEventListener('click', () => {{
            if (autoRotate) {{
                stopAutoRotate();
            }} else {{
                startAutoRotate();
            }}
        }});
        
        resetBtn.addEventListener('click', () => {{
            stopAutoRotate();
            updateFrame(0);
        }});
        
        // Keyboard navigation
        document.addEventListener('keydown', (e) => {{
            if (e.key === 'ArrowLeft') {{
                updateFrame(currentFrame - 1);
            }} else if (e.key === 'ArrowRight') {{
                updateFrame(currentFrame + 1);
            }} else if (e.key === ' ') {{
                e.preventDefault();
                if (autoRotate) {{
                    stopAutoRotate();
                }} else {{
                    startAutoRotate();
                }}
            }}
        }});
        
        // Background selector (for transparent mode)
        document.querySelectorAll('.bg-option').forEach(option => {{
            option.addEventListener('click', () => {{
                document.querySelectorAll('.bg-option').forEach(o => o.classList.remove('active'));
                option.classList.add('active');
                
                const container = document.getElementById('viewerContainer');
                const bg = option.dataset.bg;
                
                container.classList.remove('transparent');
                container.style.background = '';
                
                if (bg === 'white') {{
                    container.style.background = 'white';
                }} else if (bg === 'black') {{
                    container.style.background = '#1a1a1a';
                }} else if (bg === 'gray') {{
                    container.style.background = '#808080';
                }} else if (bg === 'checker') {{
                    container.classList.add('transparent');
                }}
            }});
        }});
        
        // Initialize
        updateFrame(0);
    </script>
</body>
</html>'''
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    return output_path
