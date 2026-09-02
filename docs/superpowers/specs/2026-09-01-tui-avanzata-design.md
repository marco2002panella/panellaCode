# Design: problemSolver TUI (ex myagent)

Data: 2026-09-01
Stato: Approvato — implementato

## Obiettivo

Aggiungere una TUI avanzata stile opencode, nel terminale, molto più ricca
dell'attuale `interactive` mode. `python3 main.py` senza argomenti apre la GUI
direttamente su un campo input problema; layout a 4 pannelli (Wave/Task, Log
live, Viewer risultati, Costi); streaming live vero dell'output dei subprocess
`opencode run`; ciclo continuo (più problemi per sessione).
Il programma è rinominato **problemSolver** (branding; entry main.py invariato).

## Decisioni raccolte dal brainstorming

- Framework: **Textual** (nuova dipendenza).
- Layout: **4 pannelli** — Wave/Task (principale), Log live, Viewer risultati, Costi
  + header di stato/controlli e campo input in cima.
- Streaming: **live vero** dei subprocess (modifica executor).
- Architettura: **worker thread + coda eventi** (ThreadPoolExecutor già in uso).
- Apertura: `main.py` senza argomenti → GUI (callback typer
  `invoke_without_command=True`); con subcommand → `run`/`interactive`/`version`
  invariati.
- Input: campo problema in cima; **congelato (disabled) durante la run**,
  riattivato a `RunDone`; ciclo continuo per più problemi.
- Configurazione: **OptionsScreen** richiudibile (manifest root, output dir,
  decomposer/executor model, config path) — senza flag.
- Branding: `version` → `problemSolver 0.1.0`, titolo GUI, README.

## Architettura

### Componenti

```
┌────────────────────────────────────────────────────────────┐
│ Header: fase corrente (decomposing/validating/executing)    │
│         + controlli [p]ause [s]kip [v]iew [q]uit            │
├──────────────────────────┬─────────────────────────────────┤
│ Wave/Task (principale)   │  Log live (streaming)            │
│  Wave 0                 │  ▸ task_001 reasoning...         │
│   ✓ task_001  completed │  ▸ ✓ file created                │
│   ⟳ task_002  running   │  ▸ model big-pickle              │
│   ○ task_003  pending   │                                 │
├──────────────────────────┼─────────────────────────────────┤
│ Viewer risultati         │  Costi                          │
│  task_002/result.md      │  calls: 12  in: 45k out: 12k    │
│  (contenuto selezionato) │  big-pickle: $0.00  nemotron:   │
└──────────────────────────┴─────────────────────────────────┘
```

### Nuovi moduli

- `src/tui/` (pacchetto):
  - `app.py` — `AgentTUI(App)` Textual: layout a 4 pannelli, bindings tastiera,
    timer poll eventi, freeze/riabilita input, `OptionsScreen`.
  - `panels.py` — `WavePanel`, `LogPanel`, `ResultPanel`, `CostPanel`,
    `OptionsState` (stato+render testabile senza App).
  - `bridge.py` — `TUIEventBridge`: `event_queue` (worker→UI) +
    `command_queue` (UI→worker) e flag control (pause/skip/quit).
  - `run_tui.py` — `run_gui(config)`: crea Orchestrator + bridge + App.
- `src/executor_stream.py` — versione dell'executor che lancia `subprocess.Popen`
  e, da due thread reader (stdout/stderr), spinge le righe su un callback;
  facciata `run_executor(task, ..., mode="stream"|"blocking")`.

### File esistenti intoccati

`api_client.py`, `zen_router.py`, `decomposer.py`, `scheduler.py`, `collector.py`,
`checkpointing.py`.

Riuso di `Orchestrator`: `__init__`, `_decompose_with_repair`,
`_assign_default_models`, `_schedule_tasks`. Cambia solo l'esecuzione wave.

## Streaming live dei subprocess

L'executor attuale usa `subprocess.run(... capture_output=True)`. Per il live
stream:

- `execute_task_v2_stream(task, output_dir, manifest, max_retries, router,
  on_output, on_done, proc_lock)`:
  - `subprocess.Popen` su `opencode run` senza `capture_output`
  - due thread reader (stdout/stderr): `on_output(line, is_stderr)`;
    le righe stdout pulite da `\n`
  - `on_output` spinge su coda thread-safe → reostatis nei pannelli
  - al termine: `on_done(result)` con `result_path` scritto come oggi.
- `execute_wave_v2_stream(...)`: ogni task etichetta il proprio output.
  `on_output(task_id, line, is_stderr)`. Parallelismo via `ThreadPoolExecutor`
  come in `execute_wave_v2`.

- Facciata comune `run_executor(task, ..., mode="stream"|"blocking")` in
  `src/executor_stream.py`. Internamente delega: `mode="blocking"` -> chiude
  verso `executor_v2.execute_task_v2` (identica all'attuale; la CLI `run`
  normale non cambia), `mode="stream"` -> `execute_task_v2_stream` (sola TUI).
  Non c'è divergenza di prompt/parsing tra i due: entrambi usano
  `build_executor_prompt` e `parse_executor_output`. Il `result.md` prodotto è
  identico; nell'output stream del subprocess le righe vanno alla coda TUI,
  mentre il file risultato viene scritto come oggi.
- Il worker TUI usa il flag `pause` tra task/wave e `skip` per wave corrente.
  `quit` blocca la schedulazione delle wave successive.

### Flusso dati

```
subprocess stdout/stderr → thread reader (executor_stream) → on_output → TUIEventBridge.event_queue
        └───────────────────────────────────────────→ App._poll_events (timer 100ms) → pannelli
worker thread (`ThreadPoolExecutor`) → esegue wave → eventi lifecycle → medesima coda
```

Un singolo task "ancella" (es. `opencode run --help`) usa la medesima coda per i
log, così il pannello log mostra anche i task non-LLM.

## Controlli tastiera

| Tasto | Azione |
|-------|--------|
| `Enter` | Esegue il problema dal campo input |
| `p` | Pause (congela la schedulazione; il task corrente continua) |
| `r` | Resume |
| `s` | Skip della wave corrente (il worker passa alla successiva) |
| `v` | Focus pannello Risultati |
| `o` | Apre OptionsScreen (manifest/output/modelli/config) |
| `q` | Quit pulito (flag ai worker, attesa wave, salva checkpoint) |
| `Ctrl+C` | Forced quit |

Focus sull'input conquista i tasti alfanumerici; le azioni (p/s/v/o/q) valgono
quando l'input è disabilitato (durante la run). L'attuale `interactive` mode
(`p/r/s/v/q`, prompt_toolkit) resta invariato e indipendente.

## Integrazione CLI

`python3 main.py` senza argomenti → GUI via `@app.callback(invoke_without_command=True)`
che chiama `run_gui(config="config/default.yaml")`. Con subcommand:
`run`/`interactive`/`version` invariati. Non esiste un sotto-comando `tui`.

## Dipendenze

- Nuova dipendenza: `textual>=0.70` in `requirements.txt` (versione minima da
  verificare installabile). `prompt_toolkit` resta per l'interactive legacy.

## Testing

Nessuna TUI invocata sui CI aggregati; solo test di unità:

- `tests/test_executor_stream.py` — Popen con subprocess finto
  (es. `bash -c 'echo a; echo b'`): righe in ordine su `on_output`, `on_done`
  riceve exit_code+result; facciata blocking/stream.
- `tests/test_tui_bridge.py` — coda eventi: `TaskOutput`/`TaskDone` validi,
  thread-safe; flag pause/skip/quit.
- `tests/test_tui_panels.py` — pannelli renderizzano con dati mock (nessuna App
  reale).
- `tests/test_main_cli.py` — `main.py` senza argomenti → GUI (callback typer);
  `run`/`version` invariati; `version` stampa `problemSolver 0.1.0`.
- `tests/test_run_tui_cli.py` — `run_gui` crea Orchestrator + App e la avvia.
- Nuovo `tests/test_requirements.txt` con `-r requirements.txt` + pytest.

Verifica finale: `pytest` full verde (150 totali), poi smoke test GUI con il
pilot headless di Textual (mount pannelli, freeze/riattiva input, ciclo
continuo su più problemi).

## Fuori scope

- Cambiamenti a `api_client`, `zen_router`, scheduler, decomposer, collector.
- Modifiche all'interactive mode esistente.
- Persistenza dei costi su file (solo pannello in memoria).