"""Pruebas unitarias de lo que el agente expone para observabilidad."""

from app.agent import Agent

GET_EMPLOYEE = '{"tool": "get_employee", "args": {"employee_id": "EMP-0001"}}'


def test_on_tool_call_receives_only_the_tools_that_run(directory, scripted_model):
    model = scripted_model(
        [GET_EMPLOYEE, '{"tool": "fire_employee", "args": {}}', '{"answer": "Ok."}']
    )
    calls = []
    result = Agent(model, directory, max_steps=3).run(
        "¿Quién es EMP-0001?",
        [],
        on_tool_call=lambda name, args: calls.append((name, args)),
    )
    assert calls == [("get_employee", {"employee_id": "EMP-0001"})]
    assert result.stopped is False


def test_agent_reports_stopped_when_it_hits_the_step_cap(directory, scripted_model):
    model = scripted_model([GET_EMPLOYEE])
    result = Agent(model, directory, max_steps=1).run("¿Quién es EMP-0001?", [])
    assert result.stopped is True
    assert result.steps == 1
