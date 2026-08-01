"""
MARK — Screen Perception

Three independent ways of understanding what is on screen, tried in order of
reliability:

  1. Accessibility (AXUIElement) — the real widget tree, with roles, titles and
     exact frames. Native apps hand us buttons and text fields directly, so
     there is nothing to infer. Most reliable by a wide margin.
  2. Vision.framework OCR — Apple's on-device text recognition, with per-word
     bounding boxes and confidence. Built into macOS: no Tesseract, no brew, no
     Python OCR dependency.
  3. The multimodal model — for questions the first two cannot answer
     ("is this chart trending up?").

The previous implementation depended solely on pytesseract, which was not
installed and whose binary was absent, so every vision tool returned an error.
"""

import os
import re
import subprocess
import time

_CAPTURE_PATH = "/tmp/mark_screen.png"

# ─────────────────────────────────────────────
# CAPTURE
# ─────────────────────────────────────────────

_permission_warned = False


def capture(path=_CAPTURE_PATH, window_only=False):
    """
    Capture the screen. Returns a path, or None if macOS denied permission.

    Screen Recording is a TCC permission that only the user can grant, so we
    detect the failure explicitly and report it as an actionable message rather
    than as a mysterious empty result.
    """
    global _permission_warned
    args = ["screencapture", "-x", "-C"]
    if window_only:
        args += ["-o", "-l", str(_front_window_id() or 0)]
    args.append(path)

    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=10)
        if result.returncode != 0 or not os.path.exists(path):
            if not _permission_warned:
                _permission_warned = True
                print("  ⚠ Screen capture blocked — grant Screen Recording in "
                      "System Settings › Privacy & Security")
            return None
        return path
    except Exception as e:
        print(f"  ✗ Screen capture error: {e}")
        return None


def capture_available():
    """True if we can actually take screenshots right now."""
    return capture("/tmp/mark_capture_probe.png") is not None


PERMISSION_HINT = (
    "I can't see the screen, sir — macOS hasn't granted me Screen Recording. "
    "Open System Settings, go to Privacy and Security, then Screen Recording, "
    "and enable it for the app running MARK."
)


def _front_window_id():
    try:
        import Quartz
        infos = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
            Quartz.kCGNullWindowID,
        )
        for info in infos or []:
            if info.get("kCGWindowLayer", 1) == 0:
                return info.get("kCGWindowNumber")
    except Exception:
        pass
    return None


def screen_size():
    """Logical screen size in points (what pyautogui clicks in)."""
    try:
        import Quartz
        bounds = Quartz.CGDisplayBounds(Quartz.CGMainDisplayID())
        return int(bounds.size.width), int(bounds.size.height)
    except Exception:
        try:
            import pyautogui
            return pyautogui.size()
        except Exception:
            return 1920, 1080


# ─────────────────────────────────────────────
# 1. ACCESSIBILITY TREE
# ─────────────────────────────────────────────

_INTERACTIVE_ROLES = {
    "AXButton", "AXLink", "AXTextField", "AXTextArea", "AXCheckBox",
    "AXRadioButton", "AXPopUpButton", "AXMenuItem", "AXMenuButton",
    "AXComboBox", "AXSlider", "AXTab", "AXSearchField", "AXDisclosureTriangle",
    "AXCell", "AXRow", "AXStaticText", "AXImage",
}

_ax_warned = False


def ax_available():
    """True if this process is trusted for Accessibility."""
    try:
        from ApplicationServices import AXIsProcessTrusted
        return bool(AXIsProcessTrusted())
    except Exception:
        return False


AX_PERMISSION_HINT = (
    "I need Accessibility access to read the interface, sir. System Settings, "
    "Privacy and Security, Accessibility — enable it for the app running MARK."
)


def _ax_value(element, attribute):
    try:
        from ApplicationServices import AXUIElementCopyAttributeValue
        err, value = AXUIElementCopyAttributeValue(element, attribute, None)
        return value if err == 0 else None
    except Exception:
        return None


def _ax_frame(element):
    """Return (x, y, w, h) in screen points, or None."""
    try:
        import ApplicationServices as AS

        pos = _ax_value(element, "AXPosition")
        size = _ax_value(element, "AXSize")
        if pos is None or size is None:
            return None

        # pyobjc bridges AXValueGetValue with an out-parameter: pass None and
        # take the value from the returned tuple. Passing a pre-allocated
        # struct raises, which — swallowed by the caller — silently dropped
        # every element and made the accessibility tree look empty.
        ok_pos, point = AS.AXValueGetValue(pos, AS.kAXValueCGPointType, None)
        ok_size, rect = AS.AXValueGetValue(size, AS.kAXValueCGSizeType, None)
        if not ok_pos or not ok_size:
            return None

        return int(point.x), int(point.y), int(rect.width), int(rect.height)
    except Exception:
        return None


def ax_elements(max_elements=220, max_depth=14):
    """
    Walk the focused application's accessibility tree.

    Returns a list of {role, label, x, y, w, h} for interactive elements, where
    (x, y) is the clickable centre in screen points.
    """
    global _ax_warned
    if not ax_available():
        if not _ax_warned:
            _ax_warned = True
            print("  ⚠ Accessibility not trusted — element tree unavailable")
        return []

    try:
        from ApplicationServices import AXUIElementCreateApplication
        from AppKit import NSWorkspace
    except Exception:
        return []

    app = NSWorkspace.sharedWorkspace().frontmostApplication()
    if app is None:
        return []

    root = AXUIElementCreateApplication(app.processIdentifier())
    found = []
    seen = 0

    def walk(element, depth):
        nonlocal seen
        if depth > max_depth or len(found) >= max_elements or seen > 4000:
            return
        seen += 1

        role = _ax_value(element, "AXRole")
        if role in _INTERACTIVE_ROLES:
            label = None
            for attribute in ("AXTitle", "AXValue", "AXDescription",
                              "AXLabel", "AXHelp", "AXPlaceholderValue"):
                candidate = _ax_value(element, attribute)
                if isinstance(candidate, str) and candidate.strip():
                    label = candidate.strip()
                    break
            frame = _ax_frame(element)
            if label and frame and frame[2] > 0 and frame[3] > 0:
                x, y, w, h = frame
                found.append({
                    "role": str(role).replace("AX", ""),
                    "label": label[:90],
                    "x": x + w // 2,
                    "y": y + h // 2,
                    "w": w,
                    "h": h,
                    "source": "accessibility",
                })

        children = _ax_value(element, "AXChildren") or []
        for child in children:
            walk(child, depth + 1)

    try:
        walk(root, 0)
    except Exception as e:
        print(f"  ⚠ Accessibility walk failed: {e}")

    return found


# ─────────────────────────────────────────────
# 2. NATIVE VISION OCR
# ─────────────────────────────────────────────

_vision_warned = False


def ocr_elements(image_path=None, min_confidence=0.3):
    """
    Run Apple's on-device text recognition.

    Returns [{label, x, y, w, h, confidence}] with coordinates already
    converted from Vision's normalised bottom-left space into screen points.
    """
    global _vision_warned
    try:
        import Quartz
        import Vision
        from Foundation import NSURL
    except ImportError:
        if not _vision_warned:
            _vision_warned = True
            print("  ⚠ pyobjc Vision unavailable — install pyobjc-framework-Vision")
        return []

    path = image_path or capture()
    if not path:
        return []

    try:
        url = NSURL.fileURLWithPath_(path)
        source = Quartz.CGImageSourceCreateWithURL(url, None)
        if source is None:
            return []
        image = Quartz.CGImageSourceCreateImageAtIndex(source, 0, None)
        if image is None:
            return []

        px_w = Quartz.CGImageGetWidth(image)
        px_h = Quartz.CGImageGetHeight(image)
        pt_w, pt_h = screen_size()
        # Retina: the capture is in pixels, clicks happen in points.
        scale_x = pt_w / px_w if px_w else 1.0
        scale_y = pt_h / px_h if px_h else 1.0

        handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(image, None)
        request = Vision.VNRecognizeTextRequest.alloc().init()
        request.setRecognitionLevel_(0)          # 0 = accurate
        request.setUsesLanguageCorrection_(True)

        ok, _ = handler.performRequests_error_([request], None)
        if not ok:
            return []

        results = []
        for observation in request.results() or []:
            candidates = observation.topCandidates_(1)
            if not candidates:
                continue
            text = candidates[0].string()
            confidence = float(observation.confidence())
            if not text or not text.strip() or confidence < min_confidence:
                continue

            box = observation.boundingBox()
            # Vision origin is bottom-left, normalised. Convert to top-left points.
            x_px = box.origin.x * px_w
            y_px = (1.0 - box.origin.y - box.size.height) * px_h
            w_px = box.size.width * px_w
            h_px = box.size.height * px_h

            results.append({
                "label": text.strip()[:90],
                "x": int((x_px + w_px / 2) * scale_x),
                "y": int((y_px + h_px / 2) * scale_y),
                "w": int(w_px * scale_x),
                "h": int(h_px * scale_y),
                "confidence": round(confidence, 3),
                "source": "ocr",
            })
        return results

    except Exception as e:
        print(f"  ✗ Vision OCR error: {e}")
        return []


def ocr_text(image_path=None):
    """Full visible text on screen, in reading order."""
    elements = ocr_elements(image_path)
    if not elements:
        return ""
    elements.sort(key=lambda e: (e["y"] // 12, e["x"]))
    return "\n".join(e["label"] for e in elements)


# ─────────────────────────────────────────────
# 3. UNIFIED ELEMENT MAP  (Set-of-Marks grounding)
# ─────────────────────────────────────────────

def element_map(prefer_ax=True):
    """
    Merge the accessibility tree and OCR into one numbered element list.

    Numbering is what makes model-driven clicking reliable: instead of asking a
    4B model to guess pixel coordinates, we ask it to pick an index from a list
    we built ourselves, then click the coordinates *we* already know are
    correct. The model cannot hallucinate a location.
    """
    elements = []
    if prefer_ax:
        elements.extend(ax_elements())

    ax_points = {(e["x"] // 20, e["y"] // 20) for e in elements}
    for item in ocr_elements():
        # Skip OCR text that sits on top of an element we already have.
        if (item["x"] // 20, item["y"] // 20) in ax_points:
            continue
        elements.append(item)

    elements.sort(key=lambda e: (e["y"] // 24, e["x"]))
    for index, element in enumerate(elements, 1):
        element["index"] = index
    return elements


def render_element_map(elements, limit=60):
    """Render the element map as compact numbered lines for the prompt."""
    lines = []
    for element in elements[:limit]:
        role = element.get("role", "text")
        lines.append(f"[{element['index']}] {role}: {element['label']}")
    return "\n".join(lines)


def find_element(instruction, elements=None):
    """
    Locate the element best matching a natural-language instruction.

    Lexical scoring first (exact and substring matches are unambiguous), then
    the model as a tiebreaker over the numbered list.
    """
    elements = elements if elements is not None else element_map()
    if not elements:
        return None

    target = instruction.lower().strip()
    target = re.sub(r"^(?:the|a|an)\s+", "", target)
    target = re.sub(r"\s+(?:button|link|icon|field|box|tab|menu)$", "", target).strip()
    words = {w for w in re.findall(r"[a-z0-9]+", target) if len(w) > 1}

    best, best_score = None, 0.0
    for element in elements:
        label = element["label"].lower()
        score = 0.0

        if label == target:
            score = 100.0
        elif target and target in label:
            score = 60.0 - min(len(label) - len(target), 30) * 0.5
        elif label and label in target:
            score = 45.0
        else:
            label_words = set(re.findall(r"[a-z0-9]+", label))
            shared = words & label_words
            if shared:
                score = 22.0 * len(shared) / max(len(words), 1)

        # Real controls beat stray OCR text with the same wording.
        if element.get("source") == "accessibility":
            score *= 1.25
        if element.get("role") in ("Button", "Link", "TextField", "SearchField"):
            score *= 1.15

        if score > best_score:
            best, best_score = element, score

    if best and best_score >= 18:
        return best

    return _model_pick(instruction, elements)


def _model_pick(instruction, elements):
    """Ask the model to choose an index when lexical matching is inconclusive."""
    if not elements:
        return None
    try:
        from core.local_llm import local_chat_choice
    except Exception:
        return None

    subset = elements[:45]
    options = [str(e["index"]) for e in subset] + ["none"]
    prompt = (
        "These are the elements currently visible on screen:\n"
        f"{render_element_map(subset)}\n\n"
        f"Which number is: \"{instruction}\"?\n"
        "Reply with the number only, or \"none\" if it is not there."
    )
    choice = local_chat_choice([{"role": "user", "content": prompt}], options)
    if not choice or choice == "none":
        return None
    for element in subset:
        if str(element["index"]) == choice:
            return element
    return None


def describe_screen(query=None, max_chars=3000):
    """
    Best available understanding of the screen.

    Uses the multimodal model when it loaded successfully, otherwise composes an
    answer from the accessibility tree and OCR — which is often more precise
    anyway, since it carries exact labels rather than an impression.
    """
    path = capture()
    if not path:
        return PERMISSION_HINT

    # Image reasoning, if the user opted into the second model.
    try:
        from core.local_llm import vision_chat, vision_model_enabled
        if vision_model_enabled():
            prompt = query or "Describe what is on this screen, briefly and concretely."
            answer = vision_chat(path, prompt, max_tokens=400)
            if answer and len(answer.strip()) > 20:
                return answer.strip()
    except Exception:
        pass

    # Default path: structure from the accessibility tree and Apple's OCR,
    # interpreted by the text model. Cheaper and more literal than an image
    # model — it reads exact labels rather than forming an impression.
    elements = ax_elements()
    text = ocr_text(path)

    if not elements and not text:
        return ("I captured the screen but couldn't read anything from it, sir. "
                "If this keeps happening, check Screen Recording and Accessibility "
                "permissions in System Settings.")

    context = ""
    try:
        from core.context_engine import get_context
        context = get_context()
    except Exception:
        pass

    parts = []
    if context:
        parts.append(context)
    if elements:
        controls = ", ".join(f"{e['label']}" for e in elements[:25])
        parts.append(f"Interactive elements: {controls}")
    if text:
        parts.append(f"Visible text:\n{text[:max_chars]}")

    blob = "\n\n".join(parts)

    if not query:
        return blob

    try:
        from core.local_llm import local_chat
        answer = local_chat(
            [{"role": "user", "content":
              f"This is what is currently on the user's Mac screen:\n\n{blob[:4000]}\n\n"
              f"His question: {query}\n\n"
              "Answer concisely in a sentence or two, addressing him as 'sir'. "
              "No markdown."}],
            max_tokens=300, temperature=0.4,
        )
        if answer:
            return answer.strip()
    except Exception:
        pass

    return blob[:1500]
