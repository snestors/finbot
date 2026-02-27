"""
Plugin template — copy this to create a new plugin.
File: plugins/my_plugin.py

Tools: sync functions called via {"tipo": "tool", "name": "tool_name", "params": {...}}
Actions: async functions called via {"tipo": "action_name", ...params}
"""


def register():
    return {
        "tools": {
            # "my_tool": {
            #     "description": "What this tool does",
            #     "handler": my_tool,
            # },
        },
        "actions": {
            # "my_action": my_action,
        },
    }


# def my_tool(params: dict) -> str:
#     """Sync tool — returns string result."""
#     return "result"


# async def my_action(accion: dict, repos: dict) -> dict:
#     """Async action — returns dict with data_response, alert, gasto_id, etc."""
#     return {"data_response": "result"}
