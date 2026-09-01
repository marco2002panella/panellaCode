import threading
from queue import Queue
from typing import Optional


class InputHandler:
    def __init__(self):
        self._commands: Queue = Queue()
        self._thread: Optional[threading.Thread] = None
        self._running = False
    
    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._run_input_loop, daemon=True)
        self._thread.start()
    
    def stop(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
    
    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()
    
    def get_command(self, timeout: float = 0.1) -> Optional[str]:
        try:
            return self._commands.get(timeout=timeout)
        except Exception:
            return None
    
    def _run_input_loop(self) -> None:
        try:
            from prompt_toolkit import PromptSession
            from prompt_toolkit.patch_stdout import patch_stdout
            
            prompt = PromptSession()
            
            while self._running:
                try:
                    with patch_stdout():
                        text = prompt.prompt(">", style=None)
                    cmd = text.strip().lower()
                    if cmd:
                        self._commands.put(cmd)
                except (EOFError, KeyboardInterrupt):
                    self._commands.put("q")
                    break
                except Exception:
                    pass
        except Exception:
            pass
