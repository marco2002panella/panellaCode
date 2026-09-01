import time
from typing import Optional
from src.orchestrator import Orchestrator
from src.monitor_v2 import LiveMonitorV2
from src.status_panel import StatusPanel
from src.input_handler import InputHandler
from src.models import Wave


class InteractiveSession:
    HELP_TEXT = """
    🎮 Interactive Mode Commands:
    ------------------------------
    p = Pause execution
    r = Resume execution
    s = Skip current wave
    v = View detailed status
    q = Quit (cancel current run)
    h = Show this help
    ------------------------------
    """
    
    def __init__(self, orchestrator: Orchestrator, problem: str, output_dir: str, manifest_root: str = None):
        self.orchestrator = orchestrator
        self.problem = problem
        self.output_dir = output_dir
        self.manifest_root = manifest_root
        self.input_handler = InputHandler()
        self._paused = False
        self._skipped_waves: set = set()
    
    def run(self) -> str:
        """Run orchestrator with interactive monitoring."""
        cost_tracker = self.orchestrator.cost_tracker
        
        print("🔄 Decomposing problem...")
        tasks = self.orchestrator._decompose_with_repair(self.problem, self.manifest_root)
        
        print("📋 Scheduling tasks...")
        waves = self.orchestrator._schedule_tasks(tasks)
        
        monitor = LiveMonitorV2(waves, verbose=True)
        monitor.start()
        
        status_panel = StatusPanel(waves, cost_tracker)
        
        self.input_handler.start()
        
        print(self.HELP_TEXT)
        print("🚀 Starting execution...")
        
        for wave_idx, wave in enumerate(waves):
            while self.input_handler.is_alive():
                cmd = self.input_handler.get_command(timeout=0.5)
                if cmd:
                    self._handle_command(cmd, wave_idx, status_panel)
                
                if self._paused:
                    print("⏸️  Paused. Press 'r' to resume, 'q' to quit.")
                    time.sleep(0.5)
                    continue
                break
            
            if self._paused:
                continue
            
            if wave_idx in self._skipped_waves:
                wave.status = "skipped"
                continue
            
            for task in wave.tasks:
                monitor.update(task.id, "running")
            
            self.orchestrator._execute_wave(wave, self.output_dir)
            
            for res in wave.task_results:
                status_panel.update(res["task_id"], res["status"])
                monitor.update(res["task_id"], res["status"])
        
        self.input_handler.stop()
        monitor.stop(cost_tracker.summary())
        
        print("📦 Collecting results...")
        report = self.orchestrator._generate_report(waves)
        
        return report
    
    def _handle_command(self, cmd: str, wave_idx: int, status_panel: StatusPanel):
        if cmd == "p":
            self._paused = True
            print("⏸️  Paused.")
        elif cmd == "r":
            if self._paused:
                self._paused = False
                print("▶️  Resumed.")
        elif cmd == "s":
            self._skipped_waves.add(wave_idx)
            print(f"⏭️  Wave {wave_idx} skipped.")
        elif cmd == "v":
            print("\n" + status_panel.render() + "\n")
        elif cmd == "q":
            print("❌ Quitting...")
            self.input_handler.stop()
            raise KeyboardInterrupt("Interactive session cancelled")
        elif cmd == "h":
            print(self.HELP_TEXT)
        else:
            print(f"❓ Unknown command: {cmd}. Type 'h' for help.")
