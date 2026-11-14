"""Pruebas unitarias del agente con un modelo de guion inyectado."""

from app.agent import Agent

TOOL_PREFIX = "Resultado de la herramienta: "


def test_bad_json_and_unknown_tool_do_not_break_the_loop(directory, scripted_model):
    model = scripted_model(
        [
            "esto no es JSON",
            '{"tool": "fire_employee", "args": {}}',
            '{"answer": "Listo."}',
        ]
    )
    result = Agent(model, directory, max_steps=3).run("¿Algo?", [])
    assert result.answer == "Listo."
    assert result.steps == 3
    assert model.calls[1][-1]["content"].startswith(TOOL_PREFIX)
    assert model.calls[2][-1]["content"].startswith(TOOL_PREFIX)


def test_tools_run_in_order_and_tokens_add_up_across_steps(directory, scripted_model):
    model = scripted_model(
        [
            '{"tool": "get_employee", "args": {"employee_id": "EMP-0001"}}',
            '{"tool": "search_by_department", "args": {"department": "Ventas"}}',
            '{"answer": "Hecho."}',
        ]
    )
    history = [{"role": "user", "content": "Hola"}]
    result = Agent(model, directory, max_steps=3).run("¿Quién es EMP-0001?", history)
    assert result.tools_used == ["get_employee", "search_by_department"]
    assert (result.input_tokens, result.output_tokens) == (30, 6)
    assert model.calls[0][0]["content"] == "Hola"
    tool_message = model.calls[1][-1]
    assert tool_message["role"] == "user"
    assert tool_message["content"].startswith(TOOL_PREFIX)
    assert "Ana López" in tool_message["content"]
