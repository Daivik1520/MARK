"""
MARK — Image Tools
Voice-controlled image manipulation via Pillow.
Supports chained operations: crop, resize, watermark, rotate, blur, flip, grayscale.
"""

import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter


# ─────────────────────────────────────────────
# OPERATION HANDLERS
# ─────────────────────────────────────────────

def _crop_square(img):
    """Center-crop to a square."""
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    return img.crop((left, top, left + side, top + side))


def _resize(img, dimensions):
    """Resize to WxH (e.g. '800x600')."""
    try:
        parts = dimensions.lower().split("x")
        width, height = int(parts[0]), int(parts[1])
        return img.resize((width, height), Image.LANCZOS)
    except (ValueError, IndexError):
        return img


def _watermark(img, text):
    """Add a semi-transparent text watermark diagonally across the image."""
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Try to use a system font, fall back to default
    font_size = max(img.size[0] // 12, 24)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
    except (IOError, OSError):
        try:
            font = ImageFont.truetype("/System/Library/Fonts/SFNSMono.ttf", font_size)
        except (IOError, OSError):
            font = ImageFont.load_default()

    # Get text bounding box
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    # Center the watermark
    x = (img.size[0] - text_width) // 2
    y = (img.size[1] - text_height) // 2

    # Draw with red semi-transparent color
    draw.text((x, y), text, fill=(255, 0, 0, 100), font=font)

    # Rotate overlay for diagonal effect
    overlay = overlay.rotate(30, expand=False, center=(img.size[0] // 2, img.size[1] // 2))

    # Composite
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    result = Image.alpha_composite(img, overlay)
    return result


def _rotate(img, degrees):
    """Rotate image by given degrees."""
    try:
        deg = float(degrees)
    except ValueError:
        deg = 90
    return img.rotate(deg, expand=True, fillcolor=(0, 0, 0))


def _grayscale(img):
    """Convert to grayscale."""
    return img.convert("L").convert("RGBA" if img.mode == "RGBA" else "RGB")


def _blur(img, radius):
    """Apply Gaussian blur."""
    try:
        r = float(radius)
    except ValueError:
        r = 5
    return img.filter(ImageFilter.GaussianBlur(radius=r))


def _flip(img, direction):
    """Flip image horizontally or vertically."""
    direction = direction.lower().strip()
    if direction in ("horizontal", "h", "horiz"):
        return img.transpose(Image.FLIP_LEFT_RIGHT)
    elif direction in ("vertical", "v", "vert"):
        return img.transpose(Image.FLIP_TOP_BOTTOM)
    return img


def _brightness(img, factor):
    """Adjust brightness. factor > 1 = brighter, < 1 = darker."""
    from PIL import ImageEnhance
    try:
        f = float(factor)
    except ValueError:
        f = 1.2
    enhancer = ImageEnhance.Brightness(img)
    return enhancer.enhance(f)


def _contrast(img, factor):
    """Adjust contrast. factor > 1 = more contrast, < 1 = less."""
    from PIL import ImageEnhance
    try:
        f = float(factor)
    except ValueError:
        f = 1.3
    enhancer = ImageEnhance.Contrast(img)
    return enhancer.enhance(f)


# ─────────────────────────────────────────────
# OPERATION DISPATCHER
# ─────────────────────────────────────────────

OPERATIONS = {
    "crop_square": lambda img, _: _crop_square(img),
    "resize": lambda img, arg: _resize(img, arg),
    "watermark": lambda img, arg: _watermark(img, arg),
    "rotate": lambda img, arg: _rotate(img, arg),
    "grayscale": lambda img, _: _grayscale(img),
    "blur": lambda img, arg: _blur(img, arg),
    "flip": lambda img, arg: _flip(img, arg),
    "brightness": lambda img, arg: _brightness(img, arg),
    "contrast": lambda img, arg: _contrast(img, arg),
}


def edit_image(input_path, output_path="", operations=""):
    """
    Apply a chain of operations to an image.
    
    Args:
        input_path: Path to source image (supports ~ expansion)
        output_path: Where to save (default: Desktop with _edited suffix)
        operations: Comma-separated ops, e.g. "crop_square,watermark:CONFIDENTIAL,resize:800x800"
    
    Returns:
        Summary of what was done + output path
    """
    # Expand paths
    input_path = os.path.expanduser(input_path)
    
    if not os.path.isfile(input_path):
        return f"❌ File not found: {input_path}"

    # Default output path
    if not output_path:
        name, ext = os.path.splitext(os.path.basename(input_path))
        output_path = os.path.join(os.path.expanduser("~/Desktop"), f"{name}_edited{ext}")
    else:
        output_path = os.path.expanduser(output_path)

    # Parse operations
    if not operations:
        return "❌ No operations specified. Use comma-separated ops like: crop_square,watermark:CONFIDENTIAL,resize:800x800"

    ops_list = [op.strip() for op in operations.split(",") if op.strip()]

    # Load image
    try:
        img = Image.open(input_path)
        original_size = img.size
        original_mode = img.mode
    except Exception as e:
        return f"❌ Cannot open image: {e}"

    # Apply operations in sequence
    applied = []
    for op_str in ops_list:
        # Parse "operation:argument"
        if ":" in op_str:
            op_name, op_arg = op_str.split(":", 1)
        else:
            op_name, op_arg = op_str, ""

        op_name = op_name.lower().strip()
        handler = OPERATIONS.get(op_name)
        if handler:
            try:
                img = handler(img, op_arg)
                applied.append(op_str)
            except Exception as e:
                applied.append(f"{op_str} (⚠️ {e})")
        else:
            applied.append(f"{op_str} (❌ unknown)")

    # Save output
    try:
        # Ensure correct mode for saving (JPEG doesn't support RGBA)
        output_ext = os.path.splitext(output_path)[1].lower()
        if output_ext in (".jpg", ".jpeg") and img.mode == "RGBA":
            img = img.convert("RGB")
        
        img.save(output_path, quality=95)
    except Exception as e:
        return f"❌ Failed to save: {e}"

    # Open the result
    try:
        import subprocess
        subprocess.Popen(["open", output_path])
    except Exception:
        pass

    return (
        f"🎨 **Image Edited Successfully**\n\n"
        f"📥 Input: {os.path.basename(input_path)} ({original_size[0]}×{original_size[1]})\n"
        f"📤 Output: {output_path} ({img.size[0]}×{img.size[1]})\n"
        f"🔧 Operations: {', '.join(applied)}\n"
        f"📂 Opened for preview."
    )
