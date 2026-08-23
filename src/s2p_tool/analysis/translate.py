"""Optional automatic translation of extracted datasheet snippets.

Offline-first: a locally installed Argos Translate model does the work with no
network. If a DeepL API key is present (``DEEPL_API_KEY``) and the ``deepl``
package is installed, DeepL is used as a higher-quality fallback. A small domain
glossary normalizes technical terms, and every translation is cached on disk so
repeat runs cost nothing. Degrades to the ORIGINAL text when no backend is
available — it never fabricates a translation.

Backend order for ``backend="auto"``: argos (offline) -> deepl (fallback) ->
glossary (term-only) -> passthrough.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Dict, List, Optional

try:
    import argostranslate.translate as _argt
    _HAVE_ARGOS = True
except Exception:  # pragma: no cover
    _HAVE_ARGOS = False

_CACHE_PATH = os.path.join(os.path.expanduser("~"), ".s2p_tool",
                           "translate_cache.json")

# Domain glossary EN -> TR (whole-word, case-insensitive). Used by the
# glossary-only backend and as a post-edit term lock over MT output.
_GLOSSARY: Dict[str, str] = {
    "reference voltage": "referans gerilimi",
    "quiescent current": "sükunet akımı",
    "shutdown current": "kapalı-durum akımı",
    "switching frequency": "anahtarlama frekansı",
    "current limit": "akım limiti",
    "soft-start": "yumuşak başlatma",
    "soft start": "yumuşak başlatma",
    "feedback": "geri besleme",
    "input voltage": "giriş gerilimi",
    "output voltage": "çıkış gerilimi",
    "input capacitor": "giriş kapasitörü",
    "output capacitor": "çıkış kapasitörü",
    "inductor": "indüktör",
    "capacitor": "kapasitör",
    "efficiency": "verim",
    "duty cycle": "görev çevrimi",
    "ripple": "dalgalanma",
    "thermal pad": "termal ped",
    "power supply": "güç kaynağı",
    "power good": "güç-hazır (power good)",
    "enable": "etkinleştirme",
    "switch current": "anahtar akımı",
    "peak current": "tepe akımı",
    "output current": "çıkış akımı",
    "load current": "yük akımı",
    "logic input": "mantık girişi",
    "logic high": "mantık yüksek",
    "logic low": "mantık düşük",
}
# TR -> TR normalizations applied after MT (safe, whole-word) to align the
# model's word choice with datasheet terminology. Argos mis-renders many EE
# terms literally ("ground plane"->"zemin uçağı", "board"->"yönetim kurulu",
# "rail-to-rail"->"ray-to-ray"); these are the whole-word corrections that make
# an op-amp/regulator report read like engineering Turkish. Applied on the
# Turkish MT output, so keys are the mistranslated Turkish surface forms.
# Multi-word keys are matched before their single-word parts (longest-first).
_POSTEDIT: Dict[str, str] = {
    # legacy regulator normalizations
    r"stabil": "kararlı",
    r"voltaj": "gerilim",
    r"geçiş frekansı": "anahtarlama frekansı",
    r"geçiş düğümü": "anahtarlama düğümü",
    r"kapatma modu": "kapalı-durum modu",
    # ground / plane / PCB board. Turkish agglutinates, so the "uçak" (plane)
    # family is enumerated with its case suffixes (longest-first sorting picks
    # the most specific); "zemin" (ground) is normalized to "toprak" separately.
    r"zemin": "toprak",
    r"uçağını": "düzlemini",
    r"uçağına": "düzlemine",
    r"uçağın": "düzlemin",
    r"uçağa": "düzleme",
    r"uçağı": "düzlemi",
    r"uçaklara": "düzlemlere",
    r"uçakları": "düzlemleri",
    r"uçaklarda": "düzlemlerde",
    r"uçaklar": "düzlemler",
    r"uçakta": "düzlemde",
    r"uçak": "düzlem",
    r"yönetim kurulu": "kart",
    r"basılı-circuit": "baskı devre",
    r"basılı devre": "baskı devre",
    r"circuit": "devre",
    # interference / susceptibility
    r"müdahalesine": "girişimine",
    r"müdahalesi": "girişimi",
    r"müdahaleye": "girişime",
    r"müdahale": "girişim",
    r"susceptabilitesini": "duyarlılığını",
    r"susceptabilite": "duyarlılık",
    r"susceptability": "duyarlılık",
    r"interfering": "girişim yapan",
    # amplifier-domain terms
    r"önyargısı": "bias akımı",
    r"önyargı": "bias",
    r"dengeleme": "ofset",
    r"kud": "dörtlü",
    r"yaygın-mode": "ortak-mod",
    r"ortak-mode": "ortak-mod",
    r"common-mode": "ortak-mod",
    r"ray-to-ray": "rail-to-rail",
    r"af ampleri": "op-amp'ler",
    r"reddedilmesi": "bastırılması",
    # polarity: argos renders electrical +/- as olumlu/olumsuz (approval sense)
    r"olumsuz giriş": "negatif giriş",
    r"olumlu giriş": "pozitif giriş",
    r"olumlu": "pozitif",
    r"olumsuz": "negatif",
    # supply / geometry leftovers
    r"tedariki": "beslemesi",
    r"tedarik": "besleme",
    r"perpendicularla": "dik olarak",
    r"perpendicular": "dik",
}
_POSTEDIT_RE = [(re.compile(rf"\b{k}\b", re.I), v)
                for k, v in sorted(_POSTEDIT.items(), key=lambda kv: -len(kv[0]))]
_GLOSS_RE = [(re.compile(rf"\b{re.escape(k)}\b", re.I), v)
             for k, v in sorted(_GLOSSARY.items(), key=lambda kv: -len(kv[0]))]


# --- backend availability -------------------------------------------------
def argos_available(source: str = "en", target: str = "tr") -> bool:
    if not _HAVE_ARGOS:
        return False
    try:
        codes = {l.code for l in _argt.get_installed_languages()}
        return source in codes and target in codes
    except Exception:
        return False


def deepl_available() -> bool:
    if not os.environ.get("DEEPL_API_KEY"):
        return False
    try:
        import deepl  # noqa: F401
        return True
    except Exception:
        return False


def any_available(source: str = "en", target: str = "tr") -> bool:
    return argos_available(source, target) or deepl_available()


def _select_backend(backend: str, source: str, target: str) -> str:
    if backend and backend != "auto":
        return backend
    if argos_available(source, target):
        return "argos"
    if deepl_available():
        return "deepl"
    return "glossary"


def active_backend(source: str = "en", target: str = "tr") -> str:
    return _select_backend("auto", source, target)


# --- cache ----------------------------------------------------------------
def _load_cache() -> Dict[str, str]:
    try:
        with open(_CACHE_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def _save_cache(cache: Dict[str, str]) -> None:
    try:
        os.makedirs(os.path.dirname(_CACHE_PATH), exist_ok=True)
        with open(_CACHE_PATH, "w", encoding="utf-8") as fh:
            json.dump(cache, fh, ensure_ascii=False)
    except Exception:
        pass


_CACHE_VER = "v5"                          # bump when glossary/post-edit changes


def _key(backend: str, source: str, target: str, text: str) -> str:
    h = hashlib.sha1(
        f"{_CACHE_VER}|{backend}|{source}|{target}|{text}".encode("utf-8"))
    return h.hexdigest()


# --- post-processing ------------------------------------------------------
_DUP_WORD_RE = re.compile(r"\b(\w+)(?:\s+\1\b)+", re.I | re.U)


def _postedit(text: str) -> str:
    for rx, repl in _POSTEDIT_RE:
        text = rx.sub(repl, text)
    # Argos repeats short tokens ("Output" -> "Çıktı Çıktı Çıktı"); collapse any
    # run of the same word back to one occurrence.
    text = _DUP_WORD_RE.sub(r"\1", text)
    return text


def _glossary_only(text: str) -> str:
    for rx, repl in _GLOSS_RE:
        text = rx.sub(repl, text)
    return text


# --- backend runners ------------------------------------------------------
def _run_argos(texts: List[str], source: str, target: str) -> List[str]:
    out = []
    for t in texts:
        try:
            out.append(_argt.translate(t, source, target))
        except Exception:
            out.append(t)
    return out


def _run_deepl(texts: List[str], source: str, target: str) -> List[str]:
    try:
        import deepl
        tr = deepl.Translator(os.environ["DEEPL_API_KEY"])
        res = tr.translate_text(texts, target_lang="TR",
                                source_lang=source.upper())
        return [r.text for r in res]
    except Exception:
        return list(texts)


def _run_backend(backend: str, texts: List[str], source: str,
                 target: str) -> List[str]:
    if backend == "argos":
        return _run_argos(texts, source, target)
    if backend == "deepl":
        return _run_deepl(texts, source, target)
    if backend == "glossary":
        return [_glossary_only(t) for t in texts]
    return list(texts)


# --- public API -----------------------------------------------------------
def translate(texts: List[str], target: str = "tr", source: str = "en",
              backend: str = "auto") -> List[str]:
    """Translate ``texts`` into ``target``. Returns a list the same length as
    the input; blanks pass through unchanged, and any text that cannot be
    translated is returned as-is (never fabricated). Results are disk-cached."""
    if not texts:
        return list(texts)
    chosen = _select_backend(backend, source, target)
    cache = _load_cache()
    out: List[Optional[str]] = [None] * len(texts)
    todo_idx: List[int] = []
    todo_txt: List[str] = []
    for i, tx in enumerate(texts):
        if not tx or not tx.strip():
            out[i] = tx
            continue
        ck = _key(chosen, source, target, tx)
        if ck in cache:
            out[i] = cache[ck]
        else:
            todo_idx.append(i)
            todo_txt.append(tx)
    if todo_txt:
        done = _run_backend(chosen, todo_txt, source, target)
        for j, i in enumerate(todo_idx):
            val = done[j] if done[j] else texts[i]
            if chosen in ("argos", "deepl"):
                val = _postedit(_glossary_only(val))
            out[i] = val
            cache[_key(chosen, source, target, texts[i])] = val
        _save_cache(cache)
    return [o if o is not None else "" for o in out]
