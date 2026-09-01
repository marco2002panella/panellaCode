from src.input_handler import InputHandler


def test_input_handler_start_stop():
    handler = InputHandler()
    handler.start()
    assert handler.is_alive()
    handler.stop()
    assert not handler.is_alive()


def test_input_handler_capture_commands():
    handler = InputHandler()
    handler.start()
    handler._commands.put("p")
    cmd = handler.get_command()
    assert cmd == "p"
    handler.stop()
