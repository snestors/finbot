from src.agent.registry import register_tool

def send_to_claude_code_agent(messages: list):
    # Esta es una simulación. En una implementación real, aquí se llamaría a Claude Code.
    # Por ahora, solo confirmamos que el 'plugin' puede ser llamado.
    return f'Simulando envío de {len(messages)} mensajes a Claude Code Agent.'

register_tool(send_to_claude_code_agent)
