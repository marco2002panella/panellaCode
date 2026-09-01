# Design: TUI Avanzata per myagent

Data: 2026-09-01
Stato: Approvato — in attesa di piano di implementazione

## Obiettivo

Aggiungere una TUI avanzata stile opencode, nel terminale, molto più ricca
dell'attuale `interactive` mode. Layout a 4 pannelli: Wave/Task, Log live in
streaming, Viewer risultati, Costi. Streaming live vero dell'output dei
subprocess `opencode run`.

## Decisioni raccolte dal brainstorming

- Framework: **Textual** (nuova dipendenza).
- Layout: **4 pannelli** — Wave/Task (principale), Log live, Viewer risultati, Costi
  + header di stato/controlli.
- Streaming: **live vero** dei subprocess (modifica executor).
- Architettura: **worker thread + coda eventi** (ThreadPoolExecutor già in uso).

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
  - `app.py` — `AgentTUI(App)` Textual: layout a 4 pannelli, bindings tastiera.
  - `panels.py` — `WavePanel`, `LogPanel`, `ResultPanel`, `CostPanel`, `HeaderPanel`.
  - `bridge.py` — `TUIEventBridge`: coda `queue.Queue` di eventi (`TaskStarted`,
    `TaskOutput`, `TaskDone`, `CostUpdate`, `WaveStarted`).
  - `run_tui.py` — entrypoint che lancia worker thread + App.
- `src/executor_stream.py` — versione dell'executor che lancia `subprocess.Popen`
  e, da un thread reader, spinge le righe di stdout su un callback/coda.

### File esistenti intoccati

`api_client.py`, `zen_router.py`, `decomposer.py`, `scheduler.py`, `collector.py`,
`checkpointing.py`.

Riuso di `Orchestrator`: `__init__`, `_decompose_with_repair`,
`_assign_default_models`, `_schedule_tasks`. Cambia solo l'esecuzione wave.

## Streaming live dei subprocess

L'executor attuale usa `subprocess.run(... capture_output=True)`. Per il live
stream:

- `execute_task_v2_stream(task, executor_model, router, on_output, on_done, proc_lock)`:
  - `subprocess.Popen` su `opencode run` senza `capture_output`
  - thread reader: `for line in iter(proc.stdout.readline, '')` -> `on_output(line)`;
    stderr su stesso callback con prefisso `[err]`
  - `on_output` spinge su coda thread-safe -> TUI aggiorna via `call_from_thread`
  - al termine: `on_done(exit_code, result_file)` con parse `parse_executor_output` riusato.

- Facciata comune `run_executor(task, ..., mode="stream"|"blocking")` in
  `src/executor_stream.py`. Internamente delega: `mode="blocking"` -> chiude
  verso `executor_v2.execute_task_v2` (identica all'attuale; la CLI `run`
  normale non cambia), `mode="stream"` -> `execute_task_v2_stream` (sola TUI).
  Non c'è divergenza di prompt/parsing tra i due: entrambi usano
  `build_executor_prompt` e `parse_executor_output`. Il `result.md` prodotto è
  identico; nell'output stream del subprocess le righe vanno alla coda TUI,
  mentre il file risultato viene scritto come oggi.
- Le wave parallele usano il `proc_lock` globale già esistente.

### Flusso dati

```
subprocess stdout → thread reader (executor_stream) → on_output → queue.Queue
        └───────────────────────────────────────────────→ App._handle_events (timer 100ms) → LogPanel + CostPanel
worker thread (`ThreadPoolExecutor`) → esegue wave → eventi lifecycle (WaveStarted/TaskStarted/TaskDone) → medesima coda
```

Un singolo task "ancella" (es. `opencode run --help`) usa la medesima coda per i
log, così il pannello log mostra anche i task non-LLM.

## Controlli tastiera

| Tasto | Azione |
|-------|--------|
| `p` | Pause/Resume (congela la schedulazione della wave; il worker continua il task corrente) |
| `s` | Skip task corrente (segna failed/skipped nel checkpoint, passa al prossimo) |
| `v` | Cambia focus: il Viewer risultati mostra il file selezionato |
| `↑/↓` | Naviga la lista task |
| `1..9` | Jump a una wave |
| `q` | Quit pulito (event flag ai worker, attende completamento, salva checkpoint) |
| `Ctrl+C` | Forced quit (flag di kill) |

Nota: l'attuale `interactive` mode (`p/r/s/v/q`, prompt_toolkit) resta invariato
e indipendente.

## Integrazione CLI

Nuova sotto-comando: `python3 main.py tui "problema" --manifest .` — separato da
`interactive` che resta invariato.

## Dipendenze

- Nuova dipendenza: `textual>=0.70` in `requirements.txt` (versione minima da
  verificare installabile). `prompt_toolkit` resta per l'interactive legacy.

## Testing

Nessuna TUI invocata sui CI aggregati; solo test di unità:

- `tests/test_executor_stream.py` — Popen con subprocess finto
  (es. `bash -c 'echo a; echo b'`): righe in ordine su `on_output`, `on_done`
  riceve exit_code+result.
- `tests/test_tui_bridge.py` — coda eventi: `TaskStarted`/`TaskOutput`/`TaskDone`
  validi, thread-safe.
- `tests/test_tui_panels.py` — pannelli renderizzano con dati mock (nessuna App
  reale).
- `tests/test_run_tui_cli.py` — sottocomando `tui` registrato; smoke test con
  flag `--no-live`/`--check-only`.
- Aggiornare `tests/test_requirements.txt` con textual.

Verifica finale: `pytest` full verde (120 esistenti + ~10 nuovi), poi smoke test
manuale TUI in pty.

## Fuori scope

- Cambiamenti a `api_client`, `zen_router`, scheduler, decomposer, collector.
- Modifiche all'interactive mode esistente.
- Persistenza dei costi su file (solo pannello in memoria).