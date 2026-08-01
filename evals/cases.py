"""
MARK — Evaluation cases.

`expect` is the tool the router should choose. None means "just talk" — no tool
call. `any_of` accepts a set when more than one choice is genuinely correct.

These exist because prompt changes are invisible until something breaks in
conversation. Before this file, there was no way to know whether an edit to the
routing prompt had silently degraded ten other intents.
"""

# (utterance, expected_tool_or_None, alternatives_also_acceptable)
CASES = [
    # ── Pure conversation: must NOT call a tool ──
    ("hey mark", None, set()),
    ("hello", None, set()),
    ("who are you", None, set()),
    ("what can you do", None, set()),
    ("thanks, that's great", None, set()),
    ("how are you today", None, set()),
    ("tell me a joke", None, set()),
    ("that was perfect", None, set()),

    # ── System control ──
    ("set the volume to 40", "set_volume", set()),
    ("mute the sound", "mute_volume", set()),
    ("turn the brightness down", "set_brightness", set()),
    ("put the mac to sleep", "system_sleep", set()),
    ("take a screenshot", "take_screenshot", set()),
    ("how much ram am I using", "get_system_stats", set()),
    ("is my battery ok", "get_system_stats", set()),

    # ── Apps & windows ──
    ("open spotify", "open_app", set()),
    ("launch visual studio code", "open_app", set()),
    ("switch to chrome", "focus_app", {"open_app", "focus_window"}),
    ("what apps are open right now", "list_windows", {"get_open_windows"}),
    ("put safari and notes side by side", "tile_windows", set()),
    ("hide everything except vscode", "dim_all_except", set()),

    # ── Web ──
    ("open youtube", "open_website", {"open_app"}),
    ("go to github.com", "open_website", set()),
    ("search the web for rust async runtimes", "web_search", {"web_search_deep"}),
    ("what's tesla stock at", "web_get_stock", {"web_search", "web_search_deep"}),
    ("give me the news headlines", "get_news", {"get_news_briefing"}),

    # ── Memory ──
    ("remember that my wifi password is hunter2", "rag_remember", {"save_memory"}),
    ("what's my wifi password", "rag_recall", {"recall_memory"}),
    ("do you remember what I told you about my sister", "rag_recall", {"recall_memory"}),
    ("what do you remember about me", "rag_list", {"rag_recall", "list_memories"}),
    ("forget what I said about the party", "rag_forget", {"delete_memory"}),

    # ── Files ──
    ("create a folder called invoices on my desktop", "create_folder", set()),
    ("what's inside my downloads folder", "list_directory", {"open_folder"}),
    ("read the file notes.txt", "read_file", {"open_file"}),
    ("find a file called budget", "search_files", {"search_content"}),
    ("tidy up my desktop it's a mess", "clean_desktop", set()),
    ("organize my downloads folder", "organize_downloads", {"clean_desktop"}),

    # ── Media ──
    ("play bohemian rhapsody", "play_music", set()),
    ("play some jazz on spotify", "play_music", set()),

    # ── Reminders ──
    ("remind me to call mom in an hour", "set_reminder", set()),
    ("what reminders do I have", "list_reminders", set()),
    ("clear all my reminders", "clear_reminders", {"delete_reminder"}),

    # ── Screen / vision ──
    ("what's on my screen right now", "analyze_screen", {"vision_describe", "get_context"}),
    ("look at my screen and tell me what this error means", "analyze_screen", {"vision_describe"}),
    ("click the submit button", "vision_click", {"click_text"}),

    # ── Focus / routines ──
    ("start a focus session for 30 minutes", "start_focus", set()),
    ("end my focus session", "stop_focus", set()),
    ("activate coding mode", "run_routine", set()),
    ("what routines do you have", "list_routines", set()),

    # ── Dev tools ──
    ("run git status in my project folder", "run_terminal", set()),
    ("write a python script that renames files", "write_code", set()),
    ("build me a portfolio website", "build_website", set()),
    ("generate a strong password", "generate_password", set()),

    # ── Safety layer ──
    ("undo that", "undo_last_action", set()),
    ("what have you done recently", "list_recent_actions", set()),

    # ── Clipboard / context ──
    ("what did I copy earlier", "get_clipboard_history", {"search_clipboard"}),
    ("what am I looking at", "get_context", {"analyze_screen", "vision_describe"}),

    # ── Misc ──
    ("track this number +919876543210", "track_number", set()),
    ("research quantum computing and write it up", "research_topic", set()),
]


# Cases for the deterministic fast router. `expect` None means it must fall
# through to the model rather than shortcut.
FAST_ROUTE_CASES = [
    ("volume 40", "set_volume"),
    ("set volume to 80", "set_volume"),
    ("mute", "mute_volume"),
    ("unmute", "unmute_volume"),
    ("brightness 60", "set_brightness"),
    ("brightness up", "set_brightness"),
    ("screenshot", "take_screenshot"),
    ("open spotify", "open_app"),
    ("open github.com", "open_website"),
    ("go to youtube", "open_website"),

    # Regressions — these previously got hijacked into a web search or an app
    # launch and must now reach the model instead.
    ("what is my favorite color", None),
    ("who are you", None),
    ("how do I fix this bug", None),
    ("what can you do for me", None),
    ("why is my mac slow", None),
    ("hey mark", None),
    ("thanks", None),
    ("message me the details later", None),
    ("open the pod bay doors and then land the ship", None),
    ("can you open spotify for me and play some jazz", None),
]
