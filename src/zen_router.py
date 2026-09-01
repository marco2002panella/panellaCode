from typing import Dict, List, Optional


class ZenRouter:
    """Gestisce la catena di modelli: free di OpenCode Zen -> fallback Regolo.

    La catena e' costruita da config e usata in due modi:
    - round-robin tra i modelli free per l'esecuzione (distribuzione carico)
    - fallback al modello successivo quando uno satura (429 / rate-limit)
    """

    def __init__(
        self,
        zen_free_models: Optional[List[str]] = None,
        regolo_fallback_models: Optional[List[str]] = None,
        executor_default: Optional[str] = None,
    ):
        self.zen_free_models = [
            m for m in (zen_free_models or []) if m
        ] or ["opencode_zen:big-pickle"]
        self.regolo_fallback_models = [m for m in (regolo_fallback_models or []) if m]
        self.executor_default = executor_default or self.zen_free_models[0]
        if self.executor_default not in self.zen_free_models:
            self.zen_free_models.insert(0, self.executor_default)
        self._satcati: set = set()
        self._wave_counter = 0

    @property
    def chain(self) -> List[str]:
        """Catena completa ordinata: free (non saturi) poi fallback Regolo."""
        free = [m for m in self.zen_free_models if m not in self._satcati]
        regolo = [m for m in self.regolo_fallback_models if m not in self._satcati]
        return free + regolo

    def next_for_role(self, role: str = "executor_default") -> str:
        """Modello default per un ruolo: primo free disponibile (big-pickle)."""
        available = [m for m in self.zen_free_models if m not in self._satcati]
        if available:
            return available[0]
        return self._first_available_fallback()

    def rotate_for_wave(self, wave_idx: int) -> str:
        """Round-robin tra i modelli free per distribuire il carico tra le wave."""
        available = [m for m in self.zen_free_models if m not in self._satcati]
        if not available:
            return self._first_available_fallback()
        return available[wave_idx % len(available)]

    def next_fallback(self, current: str) -> Optional[str]:
        """Prossimo modello in catena dopo `current`; None se la catena e' finita."""
        chain = self.chain
        try:
            pos = chain.index(current)
        except ValueError:
            pos = -1
        candidates = chain[pos + 1:]
        return candidates[0] if candidates else None

    def register_failure(self, model: Optional[str]):
        """Marca un modello come saturo per la run corrente (in-memory)."""
        if model:
            self._satcati.add(model)

    def reset(self):
        self._satcati.clear()
        self._wave_counter = 0

    def _first_available_fallback(self) -> str:
        for m in self.regolo_fallback_models:
            if m not in self._satcati:
                return m
        return self.zen_free_models[0]

    @staticmethod
    def is_rate_limit(error_text: str) -> bool:
        if not error_text:
            return False
        lowered = error_text.lower()
        markers = (
            "429",
            "free usage exceeded",
            "freeusagelimiterror",
            "rate limit exceeded",
            "retry-after",
            "403 forbidden",
        )
        return any(m in lowered for m in markers)


def to_opencode_model(model_spec: str, provider_aliases: Optional[Dict[str, str]] = None) -> str:
    """Converte 'provider:model' nel formato che opencode run accetta.

    I modelli opencode_zen vengono usati senza prefisso provider (opencode li
    risolve sul default zen). Gli altri usano 'provider/model' con alias.
    """
    aliases = provider_aliases or {"regolo": "regolo-ai"}
    if ":" not in model_spec:
        return model_spec
    provider, model = model_spec.split(":", 1)
    if provider == "opencode_zen":
        return model
    return f"{aliases.get(provider, provider)}/{model}"