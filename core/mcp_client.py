"""
MARK — MCP Client
Connects to MCP (Model Context Protocol) tool servers.
Dynamically discovers and registers external tools.
Supports stdio transport for local MCP servers.

Requires: pip install mcp
"""

import os
import json
import asyncio
import threading
import traceback
from contextlib import AsyncExitStack


# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────

_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CONFIG_PATH = os.path.join(_PROJECT_DIR, "mcp_servers.json")


def _load_config():
    """Load MCP server configurations from disk."""
    if not os.path.exists(_CONFIG_PATH):
        with open(_CONFIG_PATH, "w") as f:
            json.dump({}, f, indent=2)
        return {}
    try:
        with open(_CONFIG_PATH, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, Exception) as e:
        print(f"  ✗ MCP config error: {e}")
        return {}


def _save_config(config):
    """Save MCP server configurations to disk."""
    with open(_CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


# ─────────────────────────────────────────────
# MCP MANAGER (Singleton)
# ─────────────────────────────────────────────

class MCPManager:
    """Manages multiple MCP server connections and their tools."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self.servers = {}        # name → {"session": ClientSession, "status": str}
        self.tools = {}          # "mcp__server__tool" → {"server": name, "tool_name": str, "schema": dict}
        self._exit_stacks = {}   # name → AsyncExitStack
        self._async_lock = None  # initialized lazily in async context
        self._config = _load_config()

    def _get_async_lock(self):
        if self._async_lock is None:
            self._async_lock = asyncio.Lock()
        return self._async_lock

    # ─────────────────────────────────────────
    # CONNECTION MANAGEMENT
    # ─────────────────────────────────────────

    async def connect(self, server_name):
        """Connect to a single MCP server by name.

        Returns: True on success, False on failure.
        """
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
        except ImportError:
            print("  ✗ MCP SDK not installed. Run: pip install mcp")
            return False

        config = self._config.get(server_name)
        if not config:
            print(f"  ✗ MCP server '{server_name}' not found in config")
            return False

        # Disconnect existing connection if any
        if server_name in self.servers:
            await self.disconnect(server_name)

        command = config.get("command", "")
        args = config.get("args", [])
        env_vars = config.get("env")

        # Build environment
        env = os.environ.copy()
        if env_vars:
            env.update(env_vars)

        # Ensure common paths are in PATH
        for extra in ["/usr/local/bin", "/opt/homebrew/bin"]:
            if extra not in env.get("PATH", ""):
                env["PATH"] = extra + ":" + env.get("PATH", "")

        try:
            server_params = StdioServerParameters(
                command=command,
                args=args,
                env=env,
            )

            stack = AsyncExitStack()
            read_stream, write_stream = await stack.enter_async_context(
                stdio_client(server_params)
            )
            session = await stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
            await session.initialize()

            self._exit_stacks[server_name] = stack
            self.servers[server_name] = {
                "session": session,
                "status": "connected",
                "command": command,
                "args": args,
            }

            # Discover tools from this server
            await self.discover_tools(server_name)

            tool_count = sum(1 for t in self.tools.values() if t["server"] == server_name)
            print(f"  ✓ MCP: Connected to '{server_name}' ({tool_count} tools)")
            return True

        except FileNotFoundError:
            print(f"  ✗ MCP: Command '{command}' not found. Is it installed?")
            if command == "npx":
                print("    Install Node.js: brew install node")
            return False
        except Exception as e:
            print(f"  ✗ MCP: Failed to connect to '{server_name}': {e}")
            traceback.print_exc()
            # Clean up partial connection
            if server_name in self._exit_stacks:
                try:
                    await self._exit_stacks[server_name].aclose()
                except Exception:
                    pass
                del self._exit_stacks[server_name]
            return False

    async def connect_all(self):
        """Connect to all configured MCP servers.

        Returns: {"connected": [...], "failed": [...]}
        """
        self._config = _load_config()  # refresh config
        connected = []
        failed = []
        skipped = []

        for name, config in self._config.items():
            # Servers ship disabled so a missing npm package or an offline
            # first run can never turn into a startup error.
            if config.get("disabled"):
                skipped.append(name)
                continue
            ok = await self.connect(name)
            if ok:
                connected.append(name)
            else:
                failed.append(name)

        return {"connected": connected, "failed": failed, "skipped": skipped}

    async def disconnect(self, server_name):
        """Disconnect from a specific MCP server."""
        # Remove tools from this server
        to_remove = [k for k, v in self.tools.items() if v["server"] == server_name]
        for key in to_remove:
            del self.tools[key]

        # Close the connection
        if server_name in self._exit_stacks:
            try:
                await self._exit_stacks[server_name].aclose()
            except Exception as e:
                print(f"  ⚠ MCP: Error closing '{server_name}': {e}")
            del self._exit_stacks[server_name]

        if server_name in self.servers:
            self.servers[server_name]["status"] = "disconnected"
            del self.servers[server_name]

        print(f"  ✓ MCP: Disconnected from '{server_name}'")

    async def disconnect_all(self):
        """Disconnect from all MCP servers."""
        names = list(self.servers.keys())
        for name in names:
            await self.disconnect(name)

    # ─────────────────────────────────────────
    # TOOL DISCOVERY
    # ─────────────────────────────────────────

    async def discover_tools(self, server_name):
        """Discover tools from a connected server and register them.

        Returns: List of tool dicts in OpenAI function calling format.
        """
        server = self.servers.get(server_name)
        if not server or server["status"] != "connected":
            return []

        session = server["session"]
        try:
            result = await session.list_tools()
        except Exception as e:
            print(f"  ✗ MCP: Failed to list tools from '{server_name}': {e}")
            return []

        openai_tools = []

        for tool in result.tools:
            # Namespace the tool name to avoid conflicts
            full_name = f"mcp__{server_name}__{tool.name}"

            # Convert MCP inputSchema to OpenAI parameters format
            params = tool.inputSchema if tool.inputSchema else {"type": "object", "properties": {}, "required": []}

            # Ensure required field exists
            if "required" not in params:
                params["required"] = []

            self.tools[full_name] = {
                "server": server_name,
                "tool_name": tool.name,
                "schema": params,
                "description": tool.description or f"MCP tool: {tool.name}",
            }

            openai_tool = {
                "type": "function",
                "function": {
                    "name": full_name,
                    "description": (tool.description or f"MCP tool from {server_name}: {tool.name}"),
                    "parameters": params,
                },
            }
            openai_tools.append(openai_tool)

        return openai_tools

    async def discover_all_tools(self):
        """Discover tools from all connected servers."""
        all_tools = []
        for name in list(self.servers.keys()):
            tools = await self.discover_tools(name)
            all_tools.extend(tools)
        return all_tools

    # ─────────────────────────────────────────
    # TOOL EXECUTION
    # ─────────────────────────────────────────

    async def call_tool(self, full_tool_name, arguments):
        """Call an MCP tool by its namespaced name.

        Args:
            full_tool_name: "mcp__servername__toolname"
            arguments: dict of arguments

        Returns: str result
        """
        tool_info = self.tools.get(full_tool_name)
        if not tool_info:
            return f"Unknown MCP tool: {full_tool_name}"

        server_name = tool_info["server"]
        tool_name = tool_info["tool_name"]

        server = self.servers.get(server_name)
        if not server or server["status"] != "connected":
            return f"MCP server '{server_name}' is not connected."

        session = server["session"]

        try:
            result = await asyncio.wait_for(
                session.call_tool(tool_name, arguments=arguments),
                timeout=30.0,
            )

            # Extract text from content blocks
            texts = []
            for block in result.content:
                if hasattr(block, "text"):
                    texts.append(block.text)
                elif hasattr(block, "type") and block.type == "text":
                    texts.append(str(block))
                else:
                    texts.append(str(block))

            return "\n".join(texts) if texts else "Tool returned no output."

        except asyncio.TimeoutError:
            return f"MCP tool '{tool_name}' timed out after 30s."
        except Exception as e:
            error_msg = f"MCP tool error ({tool_name}): {type(e).__name__}: {str(e)}"
            print(f"  ✗ {error_msg}")
            return error_msg

    # ─────────────────────────────────────────
    # OPENAI FORMAT HELPERS
    # ─────────────────────────────────────────

    def get_openai_tool_defs(self):
        """Return all discovered MCP tools in OpenAI function calling format."""
        defs = []
        for full_name, info in self.tools.items():
            defs.append({
                "type": "function",
                "function": {
                    "name": full_name,
                    "description": info["description"],
                    "parameters": info["schema"],
                },
            })
        return defs

    def is_mcp_tool(self, tool_name):
        """Check if a tool name is an MCP tool."""
        return tool_name.startswith("mcp__")

    # ─────────────────────────────────────────
    # STATUS
    # ─────────────────────────────────────────

    def get_status(self):
        """Get connection status of all servers."""
        status = {}
        for name, info in self.servers.items():
            tool_count = sum(1 for t in self.tools.values() if t["server"] == name)
            status[name] = {
                "status": info["status"],
                "command": info.get("command", ""),
                "tools": tool_count,
            }

        # Also include configured but disconnected servers
        config = _load_config()
        for name in config:
            if name not in status:
                status[name] = {"status": "disconnected", "command": config[name].get("command", ""), "tools": 0}

        return status


# ─────────────────────────────────────────────
# CONFIG MANAGEMENT (sync)
# ─────────────────────────────────────────────

def add_server_config(name, command, args, env=None):
    """Add or update an MCP server configuration.

    Args:
        name: Server name identifier
        command: Command to run (e.g., "npx", "python3")
        args: List of arguments
        env: Optional dict of environment variables
    """
    config = _load_config()
    config[name] = {"command": command, "args": args}
    if env:
        config[name]["env"] = env
    _save_config(config)
    # Update singleton config
    mgr = MCPManager()
    mgr._config = config
    return True


def remove_server_config(name):
    """Remove an MCP server configuration."""
    config = _load_config()
    if name not in config:
        return False
    del config[name]
    _save_config(config)
    mgr = MCPManager()
    mgr._config = config
    return True


def list_server_configs():
    """List all configured MCP servers."""
    return _load_config()


def enabled_server_configs():
    """Only the servers that are actually set to connect."""
    return {name: cfg for name, cfg in _load_config().items() if not cfg.get("disabled")}


def mcp_enable_server(name=""):
    """Enable a configured MCP server and connect to it."""
    config = _load_config()
    if name not in config:
        available = ", ".join(config) or "none configured"
        return f"No MCP server called '{name}'. Available: {available}"
    config[name]["disabled"] = False
    _save_config(config)
    MCPManager()._config = config
    ok = mcp_connect_server_sync(name)
    if ok:
        return f"Enabled and connected to MCP server '{name}'."
    return (f"Enabled '{name}' but the connection failed. "
            f"Check that its command is installed and you're online.")


def mcp_disable_server(name=""):
    """Disable a configured MCP server and disconnect it."""
    config = _load_config()
    if name not in config:
        return f"No MCP server called '{name}'."
    config[name]["disabled"] = True
    _save_config(config)
    MCPManager()._config = config
    try:
        _run_async(MCPManager().disconnect(name))
    except Exception:
        pass
    return f"Disabled MCP server '{name}'."


# ─────────────────────────────────────────────
# SYNC WRAPPERS (for integration with MARK's sync tools)
# ─────────────────────────────────────────────

# Dedicated event loop for MCP async operations, running in its own thread.
_mcp_loop = None
_mcp_thread = None
_mcp_lock = threading.Lock()


def _ensure_mcp_loop():
    """Ensure the MCP event loop is running in a background thread."""
    global _mcp_loop, _mcp_thread

    with _mcp_lock:
        if _mcp_loop is not None and _mcp_loop.is_running():
            return _mcp_loop

        _mcp_loop = asyncio.new_event_loop()

        def _run():
            asyncio.set_event_loop(_mcp_loop)
            _mcp_loop.run_forever()

        _mcp_thread = threading.Thread(target=_run, daemon=True, name="mcp-event-loop")
        _mcp_thread.start()
        return _mcp_loop


def _run_async(coro):
    """Run an async coroutine synchronously using the MCP event loop."""
    loop = _ensure_mcp_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result(timeout=60)


def mcp_connect_all_sync():
    """Connect to all configured MCP servers synchronously.

    Returns: {"connected": [...], "failed": [...]}
    """
    try:
        mgr = MCPManager()
        return _run_async(mgr.connect_all())
    except Exception as e:
        return {"connected": [], "failed": [], "error": str(e)}


def mcp_connect_server_sync(server_name):
    """Connect to a specific MCP server synchronously."""
    try:
        mgr = MCPManager()
        return _run_async(mgr.connect(server_name))
    except Exception as e:
        return False


def mcp_disconnect_all_sync():
    """Disconnect all MCP servers synchronously."""
    try:
        mgr = MCPManager()
        _run_async(mgr.disconnect_all())
        return True
    except Exception as e:
        return False


def mcp_call_tool_sync(full_tool_name, arguments):
    """Call an MCP tool synchronously.

    Args:
        full_tool_name: "mcp__servername__toolname"
        arguments: dict of arguments

    Returns: str result
    """
    try:
        mgr = MCPManager()
        return _run_async(mgr.call_tool(full_tool_name, arguments))
    except Exception as e:
        return f"MCP tool call error: {type(e).__name__}: {str(e)}"


def mcp_get_tools_sync():
    """Get all MCP tool definitions in OpenAI format synchronously."""
    mgr = MCPManager()
    return mgr.get_openai_tool_defs()


def mcp_get_status_sync():
    """Get MCP server status synchronously."""
    mgr = MCPManager()
    return mgr.get_status()


def mcp_is_tool(tool_name):
    """Check if a tool name is an MCP tool (sync, no async needed)."""
    return tool_name.startswith("mcp__")


# ─────────────────────────────────────────────
# TOOL-COMPATIBLE WRAPPERS (for MARK's TOOL_MAP)
# ─────────────────────────────────────────────

def mcp_status():
    """Get status of all MCP server connections."""
    status = mcp_get_status_sync()
    if not status:
        config = list_server_configs()
        if not config:
            return "No MCP servers configured. Add servers to mcp_servers.json in the MARK directory."
        return "MCP servers configured but none connected. Use mcp_connect to connect."

    lines = ["MCP Server Status", "─" * 40]
    for name, info in status.items():
        icon = "●" if info["status"] == "connected" else "○"
        lines.append(f"  {icon} {name}: {info['status']} ({info['tools']} tools) [{info['command']}]")

    return "\n".join(lines)


def mcp_connect(server_name="all"):
    """Connect to MCP servers. Use 'all' to connect to all configured servers."""
    if server_name == "all":
        result = mcp_connect_all_sync()
        connected = result.get("connected", [])
        failed = result.get("failed", [])
        parts = []
        if connected:
            parts.append(f"Connected: {', '.join(connected)}")
        if failed:
            parts.append(f"Failed: {', '.join(failed)}")
        if not connected and not failed:
            return "No MCP servers configured. Add servers to mcp_servers.json."
        return " | ".join(parts)
    else:
        ok = mcp_connect_server_sync(server_name)
        if ok:
            mgr = MCPManager()
            tool_count = sum(1 for t in mgr.tools.values() if t["server"] == server_name)
            return f"Connected to '{server_name}' successfully ({tool_count} tools available)."
        return f"Failed to connect to '{server_name}'. Check config and ensure the command is installed."


def mcp_disconnect(server_name="all"):
    """Disconnect from MCP servers."""
    if server_name == "all":
        ok = mcp_disconnect_all_sync()
        return "All MCP servers disconnected." if ok else "Error disconnecting servers."
    else:
        try:
            mgr = MCPManager()
            _run_async(mgr.disconnect(server_name))
            return f"Disconnected from '{server_name}'."
        except Exception as e:
            return f"Error disconnecting from '{server_name}': {e}"


def mcp_list_tools():
    """List all available MCP tools from connected servers."""
    mgr = MCPManager()
    if not mgr.tools:
        return "No MCP tools available. Connect to MCP servers first using mcp_connect."

    lines = ["Available MCP Tools", "─" * 40]
    by_server = {}
    for full_name, info in mgr.tools.items():
        server = info["server"]
        if server not in by_server:
            by_server[server] = []
        by_server[server].append((info["tool_name"], info["description"]))

    for server, tools in by_server.items():
        lines.append(f"\n  [{server}] ({len(tools)} tools)")
        for name, desc in tools:
            short_desc = desc[:60] + "..." if len(desc) > 60 else desc
            lines.append(f"    • {name}: {short_desc}")

    return "\n".join(lines)


def mcp_add_server(name="", command="", args="", env=""):
    """Add a new MCP server configuration.

    Args:
        name: Server identifier (e.g., 'filesystem', 'github')
        command: Command to run (e.g., 'npx', 'python3')
        args: Space-separated or JSON array of arguments
        env: JSON object of environment variables (optional)
    """
    if not name or not command:
        return "Both 'name' and 'command' are required."

    # Parse args
    if isinstance(args, str):
        args = args.strip()
        if args.startswith("["):
            try:
                args_list = json.loads(args)
            except json.JSONDecodeError:
                return "Invalid JSON for args. Use a JSON array like [\"arg1\", \"arg2\"]."
        else:
            args_list = args.split() if args else []
    else:
        args_list = list(args)

    # Parse env
    env_dict = None
    if env:
        if isinstance(env, str):
            try:
                env_dict = json.loads(env)
            except json.JSONDecodeError:
                return "Invalid JSON for env. Use a JSON object like {\"KEY\": \"value\"}."
        elif isinstance(env, dict):
            env_dict = env

    add_server_config(name, command, args_list, env_dict)
    return f"MCP server '{name}' configured. Use mcp_connect to connect."


def mcp_remove_server(name=""):
    """Remove an MCP server configuration."""
    if not name:
        return "Server name is required."
    ok = remove_server_config(name)
    if ok:
        return f"MCP server '{name}' removed from configuration."
    return f"MCP server '{name}' not found in configuration."
