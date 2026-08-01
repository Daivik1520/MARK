"""
MARK — Gemma 3 multimodal chat handler.

llama-cpp-python ships handlers for LLaVA, Moondream, Qwen-VL and friends, but
not for Gemma 3. The underlying machinery is already generic (it goes through
mtmd, which does support Gemma 3) — the only thing missing is the chat
template. So all we need to supply is Gemma's turn format; the base class
handles projector loading, image decoding and media-marker substitution.
"""

from llama_cpp.llama_chat_format import Llava15ChatHandler


class Gemma3ChatHandler(Llava15ChatHandler):
    """Multimodal handler using Gemma 3's native turn format.

    Gemma has no system role, so a system message is folded into the first user
    turn. Image parts render as the mtmd media marker, which the base handler
    swaps for real image embeddings before decoding.
    """

    DEFAULT_SYSTEM_MESSAGE = None

    CHAT_FORMAT = (
        # No explicit bos_token — llama.cpp's tokeniser prepends it, and
        # emitting a second one degrades the model's output.
        "{%- if messages[0]['role'] == 'system' -%}"
        "{%- set system_message = messages[0]['content'] | string -%}"
        "{%- set loop_messages = messages[1:] -%}"
        "{%- else -%}"
        "{%- set system_message = '' -%}"
        "{%- set loop_messages = messages -%}"
        "{%- endif -%}"
        "{%- for message in loop_messages -%}"
        "{%- set role = 'model' if message['role'] == 'assistant' else 'user' -%}"
        "<start_of_turn>{{ role }}\n"
        "{%- if loop.first and system_message -%}"
        "{{ system_message }}\n\n"
        "{%- endif -%}"
        "{%- if message['content'] is string -%}"
        "{{ message['content'] }}"
        "{%- else -%}"
        "{%- for part in message['content'] -%}"
        "{%- if part['type'] == 'text' -%}"
        "{{ part['text'] }}"
        "{%- elif part['type'] == 'image_url' -%}"
        # The URL must appear verbatim: the base handler rewrites each rendered
        # image URL into mtmd's media marker before tokenising. Emitting a
        # newline here instead is what made tokenisation fail.
        "{{ part['image_url']['url'] if part['image_url'] is mapping else part['image_url'] }}\n"
        "{%- endif -%}"
        "{%- endfor -%}"
        "{%- endif -%}"
        "<end_of_turn>\n"
        "{%- endfor -%}"
        "<start_of_turn>model\n"
    )
