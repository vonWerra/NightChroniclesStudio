#!/usr/bin/env python3
"""
Claude Generator - Automatické generování narativních textů z promptů
Optimalizovaná verze s paralelním zpracováním, cachingem, metrikami a lepší bezpečností
"""

import os
import sys
import json
import time
import re
import yaml
import hashlib
import asyncio
import aiofiles
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, AsyncGenerator
from dataclasses import dataclass, asdict, field
import logging
import traceback
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache, wraps
import threading
from collections import defaultdict
import pickle
import gzip
import atexit

# filelock (optional, fallback to internal lock)
try:
    from filelock import FileLock, Timeout as FileLockTimeout
except Exception:
    FileLock = None
    FileLockTimeout = Exception

# Import knihoven s error handlingem
from dotenv import load_dotenv

try:
    from anthropic import Anthropic, AsyncAnthropic
except Exception as e:
    print("ERROR: Missing required package 'anthropic'. Install with: pip install anthropic")
    sys.exit(1)

# optional dependencies
try:
    import keyring
except Exception:
    keyring = None

try:
    import httpx
except Exception as e:
    print("ERROR: Missing required package 'httpx'. Install with: pip install httpx")
    sys.exit(1)

try:
    from cryptography.fernet import Fernet
except Exception:
    Fernet = None

# Konfigurace
load_dotenv()

# Utility: strip markdown code fences (e.g. ```yaml ... ```)
def _strip_code_fences(s: Optional[str]) -> Optional[str]:
    """Remove surrounding and internal triple-backtick fences (optionally with language) from string.
    Keeps inner content and returns stripped text. Returns None if input is falsy.
    """
    if not s:
        return s
    try:
        # remove leading/trailing fences
        s = re.sub(r"^\s*```(?:yaml|yml)?\s*", "", s, flags=re.I)
        s = re.sub(r"\s*```\s*$", "", s)
        # replace any fenced blocks with their inner content
        s = re.sub(r"```(?:yaml|yml)?\s*(.*?)\s*```", r"\1", s, flags=re.S|re.I)
        return s.strip()
    except Exception:
        return s


# ============= BEZPEČNOST =============

class SecureCredentialManager:
    """Bezpečná správa credentials"""

    SERVICE_NAME = "claude_generator"

    @staticmethod
    def get_api_key() -> str:
        """Získá API klíč z keyring nebo environment"""
        # Nejdřív zkusit keyring, pokud je dostupný
        try:
            if keyring:
                key = keyring.get_password(SecureCredentialManager.SERVICE_NAME, "anthropic_api_key")
                if key:
                    return key
        except Exception:
            pass

        # Fallback na environment
        key = os.getenv('ANTHROPIC_API_KEY')
        if key:
            # Uložit do keyring pro příště, pokud je dostupný
            try:
                if keyring:
                    keyring.set_password(SecureCredentialManager.SERVICE_NAME, "anthropic_api_key", key)
            except Exception:
                pass
        return key or ""

    @staticmethod
    def sanitize_path(path: str, allowed_roots: Optional[List[str]] = None) -> Path:
        """Sanitizace cesty proti path traversal útokům.

        Pokud allowed_roots není zadáno, povolí cwd a NC_OUTPUTS_ROOT (pokud je nastaven).
        """
        p = Path(path).expanduser().resolve()

        # Sestavíme seznam povolených kořenů
        if allowed_roots is None:
            allowed_roots = [str(Path.cwd())]
            nc_root = os.getenv('NC_OUTPUTS_ROOT')
            if nc_root:
                try:
                    allowed_roots.append(str(Path(nc_root).resolve()))
                except Exception:
                    pass

        # Normalizace a validace
        normalized_allowed = []
        for r in allowed_roots:
            try:
                normalized_allowed.append(str(Path(r).resolve()))
            except Exception:
                continue

        for root in normalized_allowed:
            try:
                p.relative_to(root)
                return p
            except Exception:
                continue

        # Pokud žádný match, povolíme, pokud je cesta relativní a leží pod cwd
        try:
            if str(p).startswith(str(Path.cwd())):
                return p
        except Exception:
            pass

        raise ValueError(f"Nepovolená cesta: {path}. Povolené kořeny: {normalized_allowed}")

# ============= METRIKY A MONITORING =============

@dataclass
class PerformanceMetrics:
    """Sledování výkonnostních metrik"""
    api_calls: int = 0
    api_errors: int = 0
    tokens_used: int = 0
    tokens_cost: float = 0.0
    segments_generated: int = 0
    segments_failed: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    total_generation_time: float = 0.0
    # running average support
    total_response_time: float = 0.0
    response_count: int = 0
    average_response_time: float = 0.0
    success_rate: float = 100.0
    memory_usage_mb: float = 0.0

    def update_success_rate(self):
        """Aktualizuje úspěšnost"""
        total = self.segments_generated + self.segments_failed
        if total > 0:
            self.success_rate = (self.segments_generated / total) * 100

    def to_dict(self) -> Dict:
        """Export metrik do slovníku"""
        return asdict(self)

    def get_summary(self) -> str:
        """Textový souhrn metrik"""
        return f"""
        === PERFORMANCE METRICS ===
        API volání: {self.api_calls} (chyby: {self.api_errors})
        Tokeny: {self.tokens_used} (cena: ${self.tokens_cost:.4f})
        Segmenty: {self.segments_generated} úspěšných, {self.segments_failed} selhalo
        Cache: {self.cache_hits} hits, {self.cache_misses} misses
        Průměrná odezva: {self.average_response_time:.2f}s
        Úspěšnost: {self.success_rate:.1f}%
        Paměť: {self.memory_usage_mb:.1f} MB
        """

class HealthMonitor:
    """Monitorování zdraví systému"""

    def __init__(self):
        self.metrics = PerformanceMetrics()
        self.start_time = datetime.now()
        self.last_health_check = datetime.now()
        self._lock = threading.Lock()

    def update_metric(self, metric_name: str, value: Any, increment: bool = True):
        """Thread-safe aktualizace metriky

        Special-case: average_response_time je spravováno jako running average
        pomocí total_response_time a response_count polí v PerformanceMetrics.
        """
        with self._lock:
            if metric_name == 'average_response_time':
                try:
                    self.metrics.total_response_time += float(value)
                    self.metrics.response_count += 1
                    if self.metrics.response_count > 0:
                        self.metrics.average_response_time = self.metrics.total_response_time / self.metrics.response_count
                except Exception:
                    pass
                return

            if increment:
                current = getattr(self.metrics, metric_name, 0)
                try:
                    setattr(self.metrics, metric_name, current + value)
                except Exception:
                    # pokud nelze sčítat (např. přepis), nastavíme přímo
                    setattr(self.metrics, metric_name, value)
            else:
                setattr(self.metrics, metric_name, value)

    def get_health_status(self) -> Dict:
        """Získá aktuální zdraví systému"""
        try:
            import psutil  # type: ignore
        except Exception:
            # psutil není dostupný -> vrátíme základní metriky bez detailů
            return {
                'status': 'healthy' if self.metrics.success_rate > 80 else 'degraded',
                'uptime': str(datetime.now() - self.start_time),
                'cpu_percent': None,
                'memory_percent': None,
                'disk_usage': None,
                'metrics': self.metrics.to_dict()
            }

        try:
            return {
                'status': 'healthy' if self.metrics.success_rate > 80 else 'degraded',
                'uptime': str(datetime.now() - self.start_time),
                'cpu_percent': psutil.cpu_percent(interval=1),
                'memory_percent': psutil.virtual_memory().percent,
                'disk_usage': psutil.disk_usage('/').percent,
                'metrics': self.metrics.to_dict()
            }
        except Exception:
            return {
                'status': 'degraded',
                'uptime': str(datetime.now() - self.start_time),
                'cpu_percent': None,
                'memory_percent': None,
                'disk_usage': None,
                'metrics': self.metrics.to_dict()
            }

    def should_throttle(self) -> bool:
        """Určí, zda je potřeba zpomalit zpracování"""
        try:
            import psutil  # type: ignore
        except Exception:
            # Bez psutil kontrolujeme pouze chyby API
            return self.metrics.api_errors > 10

        try:
            # Kontrola paměti a CPU
            if psutil.virtual_memory().percent > 90:
                return True
            if psutil.cpu_percent(interval=0.1) > 95:
                return True
        except Exception:
            # Pokud čtení selže, fallback na chyby API
            pass

        # Kontrola chybovosti
        return self.metrics.api_errors > 10

# ============= CACHE SYSTÉM =============

class SegmentCache:
    """Cache pro vygenerované segmenty

    Používá vnitřní threading lock a file-lock (filelock) pokud je dostupný.
    """

    def __init__(self, cache_dir: Path = Path(".cache/segments")):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.memory_cache: Dict[str, str] = {}
        self._lock = threading.Lock()
        self.cache_index = self._load_index()

    def _load_index(self) -> Dict:
        """Načte index cache (bezpečně s file-lockem pokud je dostupný)"""
        index_file = self.cache_dir / "index.json"
        if not index_file.exists():
            return {}

        if FileLock:
            lock_path = str(index_file) + ".lock"
            try:
                with FileLock(lock_path, timeout=2):
                    with open(index_file, 'r', encoding='utf-8') as f:
                        return json.load(f)
            except Exception:
                return {}
        else:
            try:
                with open(index_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return {}

    def _save_index(self):
        """Uloží index cache (atomic), používá filelock pokud je dostupný"""
        index_file = self.cache_dir / "index.json"
        tmp_file = self.cache_dir / "index.json.tmp"

        if FileLock:
            lock_path = str(index_file) + ".lock"
            try:
                with FileLock(lock_path, timeout=5):
                    with open(tmp_file, 'w', encoding='utf-8') as f:
                        json.dump(self.cache_index, f, indent=2)
                    os.replace(tmp_file, index_file)
            except Exception:
                # fallback bez locku
                try:
                    with open(index_file, 'w', encoding='utf-8') as f:
                        json.dump(self.cache_index, f, indent=2)
                except Exception:
                    try:
                        if tmp_file.exists():
                            tmp_file.unlink()
                    except Exception:
                        pass
        else:
            try:
                with open(tmp_file, 'w', encoding='utf-8') as f:
                    json.dump(self.cache_index, f, indent=2)
                os.replace(tmp_file, index_file)
            except Exception:
                try:
                    if tmp_file.exists():
                        tmp_file.unlink()
                except Exception:
                    pass

    def get_cache_key(self, prompt: str, params: Dict) -> str:
        """Vytvoří unikátní klíč pro cache"""
        content = f"{prompt}{json.dumps(params, sort_keys=True)}"
        return hashlib.sha256(content.encode()).hexdigest()

    def get(self, prompt: str, params: Dict) -> Optional[str]:
        """Získá segment z cache"""
        with self._lock:
            key = self.get_cache_key(prompt, params)

            # Nejdřív zkusit paměťovou cache
            if key in self.memory_cache:
                return self.memory_cache[key]

            # Pak diskovou cache
            cache_file = self.cache_dir / f"{key}.gz"
            if cache_file.exists():
                try:
                    if FileLock:
                        lock_path = str(cache_file) + ".lock"
                        with FileLock(lock_path, timeout=2):
                            with gzip.open(cache_file, 'rt', encoding='utf-8') as f:
                                data = json.load(f)
                    else:
                        with gzip.open(cache_file, 'rt', encoding='utf-8') as f:
                            data = json.load(f)

                    if datetime.fromisoformat(data['timestamp']) > datetime.now() - timedelta(days=7):
                        self.memory_cache[key] = data['content']
                        return data['content']
                except Exception:
                    # fallback čtení bez locku
                    try:
                        with gzip.open(cache_file, 'rt', encoding='utf-8') as f:
                            data = json.load(f)
                            if datetime.fromisoformat(data['timestamp']) > datetime.now() - timedelta(days=7):
                                self.memory_cache[key] = data['content']
                                return data['content']
                    except Exception:
                        pass

            return None

    def set(self, prompt: str, params: Dict, content: str):
        """Uloží segment do cache"""
        with self._lock:
            key = self.get_cache_key(prompt, params)

            # Uložit do paměťové cache
            self.memory_cache[key] = content

            # Uložit na disk (komprimovaně)
            cache_file = self.cache_dir / f"{key}.gz"
            tmp_file = self.cache_dir / f"{key}.gz.tmp"
            try:
                data = {
                    'timestamp': datetime.now().isoformat(),
                    'prompt_hash': hashlib.md5(prompt.encode()).hexdigest(),
                    'content': content
                }
                if FileLock:
                    lock_path = str(cache_file) + ".lock"
                    try:
                        with FileLock(lock_path, timeout=3):
                            with gzip.open(tmp_file, 'wt', encoding='utf-8') as f:
                                json.dump(data, f)
                            os.replace(tmp_file, cache_file)
                    except Exception:
                        # fallback bez locku
                        with gzip.open(cache_file, 'wt', encoding='utf-8') as f:
                            json.dump(data, f)
                else:
                    with gzip.open(tmp_file, 'wt', encoding='utf-8') as f:
                        json.dump(data, f)
                    os.replace(tmp_file, cache_file)

                # Aktualizovat index
                self.cache_index[key] = {
                    'timestamp': data['timestamp'],
                    'size': len(content)
                }
                self._save_index()
            except Exception as e:
                logging.error(f"Chyba při ukládání do cache: {e}")

    def clear_old_entries(self, days: int = 7):
        """Vyčistí staré záznamy z cache"""
        cutoff = datetime.now() - timedelta(days=days)
        with self._lock:
            for key, info in list(self.cache_index.items()):
                if datetime.fromisoformat(info['timestamp']) < cutoff:
                    cache_file = self.cache_dir / f"{key}.gz"
                    if cache_file.exists():
                        cache_file.unlink()
                    del self.cache_index[key]
                    if key in self.memory_cache:
                        del self.memory_cache[key]

            self._save_index()

# ============= OPTIMALIZOVANÁ KONFIGURACE =============

class GenerationStatus(Enum):
    """Stavy generování"""
    SUCCESS = "success"
    WARNING = "warning"
    FAILED = "failed"
    ERROR = "error"
    CACHED = "cached"

@dataclass
class SegmentResult:
    """Výsledek generování segmentu"""
    segment_index: int
    attempts: List[Dict]
    final_text: str
    final_wordcount: int
    status: GenerationStatus
    validation: Optional[Dict] = None
    error_message: Optional[str] = None
    from_cache: bool = False
    generation_time: float = 0.0

@dataclass
class Config:
    """Konfigurace aplikace s vylepšenou bezpečností"""
    api_key: str = field(default_factory=SecureCredentialManager.get_api_key)
    model: str = os.getenv('CLAUDE_MODEL', 'claude-opus-4-1-20250805')
    temperature: float = float(os.getenv('CLAUDE_TEMPERATURE', '0.3'))
    max_tokens: int = int(os.getenv('CLAUDE_MAX_TOKENS', '8000'))
    max_attempts: int = int(os.getenv('MAX_ATTEMPTS', '3'))
    word_tolerance_percent: int = int(os.getenv('WORD_TOLERANCE', '3'))
    rate_limit_delay: float = float(os.getenv('RATE_LIMIT_DELAY', '3.0'))

    # Centralizované výstupy (precedence: module-specific > NC_OUTPUTS_ROOT > legacy/fallback)
    _nc_outputs_root: Optional[str] = os.getenv('NC_OUTPUTS_ROOT')

    def _resolve_env_path(preferred: Optional[str], nc_root: Optional[str], nc_subdir: str,
                          legacy_var: Optional[str], legacy_default: str) -> str:
        """
        Resolve path with rules:
         - if preferred (explicit module-specific) is provided and not a placeholder -> use it (support placeholder substitution)
         - elif nc_root -> return nc_root / nc_subdir
         - elif legacy_var provided and not a placeholder -> use legacy_var (with substitution)
         - else -> legacy_default
        """
        def _is_placeholder(val: Optional[str]) -> bool:
            if not val:
                return True
            val_str = val.strip()
            # treat explicit placeholder tokens as unset
            if val_str in ('NC_OUTPUTS_ROOT', '${NC_OUTPUTS_ROOT}', '%NC_OUTPUTS_ROOT%'):
                return True
            return False

        def _substitute(val: str, nc: Optional[str]) -> str:
            if not nc:
                return val
            return val.replace('${NC_OUTPUTS_ROOT}', nc).replace('%NC_OUTPUTS_ROOT%', nc).replace('NC_OUTPUTS_ROOT', nc)

        # preferred (highest priority)
        if preferred and not _is_placeholder(preferred):
            return _substitute(preferred, nc_root)

        # use centralized NC_OUTPUTS_ROOT if available
        if nc_root:
            return os.path.join(nc_root, nc_subdir)

        # legacy env var
        if legacy_var and not _is_placeholder(legacy_var):
            return _substitute(legacy_var, nc_root)

        return legacy_default

    base_output_path: str = _resolve_env_path(
        os.getenv('PROMPTS_INPUT_PATH'),
        os.getenv('NC_OUTPUTS_ROOT'),
        'prompts',
        os.getenv('OUTPUT_PATH'),
        'D:/NightChronicles/B_core/outputs'
    )

    claude_output_path: str = _resolve_env_path(
        os.getenv('NARRATION_OUTPUT_ROOT'),
        os.getenv('NC_OUTPUTS_ROOT'),
        'narration',
        os.getenv('CLAUDE_OUTPUT'),
        'D:/NightChronicles/Claude_vystup/outputs'
    )

    # Nové konfigurace
    enable_cache: bool = True
    enable_parallel: bool = True
    max_parallel_segments: int = int(os.getenv('MAX_PARALLEL_SEGMENTS', '3'))
    max_parallel_episodes: int = int(os.getenv('MAX_PARALLEL_EPISODES', '2'))
    enable_streaming: bool = True
    enable_metrics: bool = True
    connection_pool_size: int = 10

    def validate(self) -> Tuple[bool, List[str]]:
        """Validace konfigurace"""
        errors = []

        if not self.api_key:
            errors.append("API klíč není nastaven")

        if self.temperature < 0 or self.temperature > 1:
            errors.append(f"Neplatná teplota: {self.temperature} (musí být 0-1)")

        if self.max_tokens < 100:
            errors.append(f"Příliš nízký max_tokens: {self.max_tokens}")

        # Bezpečná validace cest
        try:
            base_path = SecureCredentialManager.sanitize_path(self.base_output_path)
            if not base_path.exists():
                errors.append(f"Základní cesta neexistuje: {self.base_output_path}")
        except ValueError as e:
            errors.append(str(e))

        return len(errors) == 0, errors

# ============= HLAVNÍ GENERÁTOR S OPTIMALIZACEMI =============

class ClaudeGeneratorError(Exception):
    """Vlastní výjimka pro generátor"""
    pass

class APIError(ClaudeGeneratorError):
    """Chyba API volání"""
    pass

class ValidationError(ClaudeGeneratorError):
    """Chyba validace"""
    pass

class OptimizedClaudeGenerator:
    """Optimalizovaná třída pro generování textů"""

    def __init__(self, config: Config):
        self.config = config
        is_valid, errors = self.config.validate()
        if not is_valid:
            raise ValidationError(f"Chyby konfigurace: {'; '.join(errors)}")

        # HTTP client s connection pooling
        self.http_client = httpx.Client(
            limits=httpx.Limits(
                max_connections=config.connection_pool_size,
                max_keepalive_connections=5
            ),
            timeout=httpx.Timeout(180.0, connect=20.0, read=180.0, write=60.0)
        )

        # Synchronní klient
        try:
            self.client = Anthropic(
                api_key=self.config.api_key,
                http_client=self.http_client
            )
        except Exception as e:
            raise APIError(f"Nepodařilo se inicializovat synchronní Anthropic klienta: {e}")

        # Asynchronní http client a AsyncAnthropic (pokud podporováno)
        self.async_http_client = None
        self.async_client = None
        try:
            self.async_http_client = httpx.AsyncClient(
                limits=httpx.Limits(
                    max_connections=config.connection_pool_size,
                    max_keepalive_connections=5
                ),
                timeout=httpx.Timeout(180.0, connect=20.0, read=180.0, write=60.0)
            )
            try:
                # některé verze AsyncAnthropic očekávají 'http_client' nebo 'client'
                # zkusíme oba argumenty bezpečně
                try:
                    self.async_client = AsyncAnthropic(api_key=self.config.api_key, http_client=self.async_http_client)
                except TypeError:
                    try:
                        self.async_client = AsyncAnthropic(api_key=self.config.api_key, client=self.async_http_client)
                    except TypeError:
                        self.async_client = AsyncAnthropic(api_key=self.config.api_key)
            except Exception:
                # fallback
                self.async_client = AsyncAnthropic(api_key=self.config.api_key)
        except Exception as e:
            logging.getLogger(__name__).warning(f"Nelze inicializovat asynchronní klienta: {e}")
            self.async_http_client = None
            self.async_client = None

        # Inicializace komponent
        self.cache = SegmentCache() if config.enable_cache else None
        self.health_monitor = HealthMonitor() if config.enable_metrics else None
        self.executor = ThreadPoolExecutor(max_workers=config.max_parallel_segments)

        self.setup_logging()
        self.retry_delays = [1, 2, 4, 8]  # Exponenciální backoff

    def setup_logging(self):
        """Nastavení logování"""
        try:
            log_dir = Path(self.config.claude_output_path).parent / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = log_dir / f"generation_{timestamp}.log"

            logging.basicConfig(
                level=logging.DEBUG,
                format='%(asctime)s - %(levelname)s - [%(threadName)s] - %(message)s',
                handlers=[
                    logging.FileHandler(log_file, encoding='utf-8', errors='replace'),
                    logging.StreamHandler()
                ]
            )
            self.logger = logging.getLogger(__name__)
            # Ensure logger outputs debug
            try:
                self.logger.setLevel(logging.DEBUG)
            except Exception:
                pass
            self.logger.debug("Optimalizovaný generátor inicializován (DEBUG mode)")

        except Exception as e:
            print(f"Varování: Nepodařilo se nastavit logování: {e}")
            self.logger = logging.getLogger(__name__)
            self.logger.addHandler(logging.StreamHandler())

    async def _close_async_resources(self):
        """Zavře asynchronní http klienty pokud jsou otevřené."""
        try:
            if getattr(self, 'async_client', None):
                # pokud SDK poskytuje aplikuje methoda aclose
                aclose = getattr(self.async_client, 'aclose', None)
                if callable(aclose):
                    await aclose()
        except Exception:
            pass
        try:
            if getattr(self, 'async_http_client', None):
                await self.async_http_client.aclose()
        except Exception:
            pass

    def find_series(self, base_path: Path) -> List[Path]:
        """Najde všechny dostupné série"""
        series: List[Path] = []

        try:
            # Bezpečná validace cesty
            base_path = SecureCredentialManager.sanitize_path(str(base_path))

            if not base_path.exists():
                raise FileNotFoundError(f"Cesta neexistuje: {base_path}")

            for item in base_path.iterdir():
                try:
                    if not (item.is_dir() and not item.name.startswith('.')):
                        continue

                    # A) epizody přímo pod kořenem série
                    if any(d.is_dir() and d.name.startswith('ep') for d in item.iterdir()):
                        series.append(item)
                        continue

                    # B) jazykové podložky obsahující epizody
                    for lang_dir in (d for d in item.iterdir() if d.is_dir() and not d.name.startswith('.')):
                        if any(e.is_dir() and e.name.startswith('ep') for e in lang_dir.iterdir()):
                            series.append(lang_dir)

                except PermissionError as e:
                    self.logger.warning(f"Nelze přistoupit k {item}: {e}")
                    continue

            return sorted(series, key=lambda p: (p.parent.name, p.name))

        except Exception as e:
            self.logger.error(f"Chyba při hledání sérií: {e}")
            return []

    def find_episodes(self, series_path: Path) -> List[Path]:
        """Najde všechny epizody v sérii"""
        episodes = []

        try:
            for item in series_path.iterdir():
                if item.is_dir() and item.name.startswith('ep'):
                    if (item / 'prompts').exists():
                        episodes.append(item)

        except Exception as e:
            self.logger.error(f"Chyba při hledání epizod v {series_path}: {e}")

        return sorted(episodes)

    def safe_input(self, prompt: str, validator=None) -> str:
        """Bezpečný vstup s validací"""
        while True:
            try:
                value = input(prompt).strip()
                if validator and not validator(value):
                    print("Neplatná hodnota, zkuste znovu.")
                    continue
                return value
            except KeyboardInterrupt:
                print("\n\nPřerušeno uživatelem")
                sys.exit(0)

    def interactive_menu(self) -> Tuple[Path, List[Path]]:
        """Interaktivní menu pro výběr série a epizod"""
        base_path = Path(self.config.base_output_path)

        # Výběr série
        series = self.find_series(base_path)
        if not series:
            raise ClaudeGeneratorError(f"Nenalezeny žádné série v {base_path}")

        print("\n=== DOSTUPNÉ SÉRIE ===")
        for i, s in enumerate(series, 1):
            label = f"{s.parent.name}/{s.name}" if s.parent != base_path else s.name
            print(f"{i}. {label}")

        def validate_series(val):
            try:
                idx = int(val) - 1
                return 0 <= idx < len(series)
            except ValueError:
                return False

        choice = self.safe_input("\nVyberte sérii (číslo): ", validate_series)
        selected_series = series[int(choice) - 1]

        # Výběr epizod
        episodes = self.find_episodes(selected_series)
        if not episodes:
            raise ClaudeGeneratorError(f"Nenalezeny žádné epizody v {selected_series}")

        print(f"\n=== EPIZODY V '{selected_series.name}' ===")
        for i, ep in enumerate(episodes, 1):
            print(f"{i}. {ep.name}")
        print(f"{len(episodes)+1}. Všechny epizody")

        def validate_episodes(val):
            if val == str(len(episodes)+1):
                return True
            try:
                indices = [int(x.strip()) for x in val.split(',')]
                return all(1 <= idx <= len(episodes) for idx in indices)
            except ValueError:
                return False

        choice = self.safe_input(
            "\nVyberte epizody (čísla oddělená čárkou, nebo číslo pro všechny): ",
            validate_episodes
        )

        if choice == str(len(episodes)+1):
            selected_episodes = episodes
        else:
            indices = [int(x.strip())-1 for x in choice.split(',')]
            selected_episodes = [episodes[idx] for idx in indices]

        return selected_series, selected_episodes

    def load_prompt(self, prompt_file: Path) -> str:
        """Načte prompt ze souboru s error handlingem"""
        try:
            encodings = ['utf-8', 'utf-8-sig', 'cp1250', 'windows-1250', 'iso-8859-2']

            for encoding in encodings:
                try:
                    text = prompt_file.read_text(encoding=encoding)
                    if any(c in text for c in ['a', 'e', 'i', 'o', 'u']):
                        return text
                except (UnicodeDecodeError, UnicodeError):
                    continue

            return prompt_file.read_text(encoding='utf-8', errors='replace')

        except FileNotFoundError:
            raise FileNotFoundError(f"Soubor neexistuje: {prompt_file}")

    def parse_validation(self, text: str) -> Optional[Dict]:
        """Parsuje YAML validaci z výstupu"""
        try:
            patterns = [
                (r'---VALIDATION---\n(.*?)$', re.DOTALL),
                (r'---\n(.*?)$', re.DOTALL),
            ]

            yaml_text = None
            for pattern, flags in patterns:
                match = re.search(pattern, text, flags)
                if match:
                    yaml_text = match.group(1).strip()
                    break

            if not yaml_text:
                return None

            # Strip code fences if present
            yaml_text = _strip_code_fences(yaml_text)

            # Bezpečné parsování YAML s omezeními
            try:
                data = yaml.safe_load(yaml_text)
                if isinstance(data, dict):
                    return data
            except Exception as e:
                # Log more context for debugging
                try:
                    snippet = yaml_text[:400]
                except Exception:
                    snippet = str(yaml_text)
                self.logger.warning(f"Nepodařilo se parsovat validaci: {e}; snippet={snippet[:400]}")
                return None

        except Exception as e:
            self.logger.warning(f"Nepodařilo se parsovat validaci: {e}")
            return None

    def extract_narration(self, text: str) -> str:
        """Extrahuje narativní text"""
        if '---' in text:
            parts = text.split('---', 1)
            return parts[0].strip()
        return text.strip()

    def count_words(self, text: str) -> int:
        """Spočítá slova v textu"""
        cleaned = ' '.join(text.split())
        return len(cleaned.split()) if cleaned else 0

    def check_requirements(self, text: str, validation: Dict, target_words: int,
                         tolerance_percent: int) -> Tuple[bool, List[str]]:
        """Kontrola požadavků na segment"""
        issues = []

        try:
            word_count = self.count_words(text)

            # Kontrola délky
            min_words = int(target_words * (1 - tolerance_percent/100))
            max_words = int(target_words * (1 + tolerance_percent/100))

            if word_count < min_words:
                issues.append(f"Text je příliš krátký ({word_count} slov, minimum {min_words})")
            elif word_count > max_words:
                issues.append(f"Text je příliš dlouhý ({word_count} slov, maximum {max_words})")

            # Kontrola validace
            if validation:
                def check_field(field_name, expected_values, error_msg):
                    value = str(validation.get(field_name, '')).lower().strip()
                    if value not in [v.lower() for v in expected_values]:
                        issues.append(error_msg)

                check_field('opening_hook_present', ['yes', 'true', '1'], "Chybí úvodní hook")
                check_field('closing_handoff_present', ['yes', 'true', '1'], "Chybí závěrečný handoff")

        except Exception as e:
            issues.append(f"Chyba validace: {str(e)}")

        return len(issues) == 0, issues

    async def call_api_async(self, prompt: str) -> Optional[str]:
        """Asynchronní volání API"""
        try:
            if self.health_monitor:
                self.health_monitor.update_metric('api_calls', 1)

            start_time = time.time()

            response = await self.async_client.messages.create(
                model=self.config.model,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                messages=[{"role": "user", "content": prompt}]
            )

            elapsed = time.time() - start_time

            # diagnostics
            try:
                self._last_call_elapsed = elapsed
            except Exception:
                pass

            if self.health_monitor:
                self.health_monitor.update_metric('average_response_time', elapsed, increment=False)

            if response and response.content:
                # detect finish_reason (best-effort)
                truncated = False
                finish_reason = None
                try:
                    first = response.content[0]
                    if hasattr(first, 'finish_reason'):
                        finish_reason = getattr(first, 'finish_reason')
                    elif isinstance(first, dict):
                        finish_reason = first.get('finish_reason') or first.get('stop_reason')
                    if finish_reason and str(finish_reason).lower().find('max') != -1:
                        truncated = True
                except Exception:
                    pass

                try:
                    self._last_call_truncated = truncated
                    self._last_call_finish_reason = finish_reason
                except Exception:
                    pass

                # Debug: log truncated prompt for auditing (async path)
                try:
                    self.logger.debug("SENT PROMPT TRUNC (first 800 chars): %s", prompt[:800])
                    self.logger.debug("API elapsed=%.2fs finish_reason=%s truncated=%s", elapsed, str(finish_reason), truncated)
                except Exception:
                    pass

                if truncated:
                    self.logger.warning("Async response likely truncated (finish_reason=%s).", finish_reason)

                return response.content[0].text

        except Exception as e:
            if self.health_monitor:
                self.health_monitor.update_metric('api_errors', 1)
            raise APIError(f"API volání selhalo: {e}")

        return None

    def call_api_with_retry(self, prompt: str, attempt_num: int = 1, target_words: Optional[int] = None) -> Optional[str]:
        """Synchronní volání API s retry logikou a cache

        If target_words is provided, a cached result will be validated against requirements
        (word count + validation) and only returned if acceptable. Otherwise, cached result
        is returned unconditionally.
        """
        # Kontrola cache
        if self.cache and self.config.enable_cache:
            params = {
                'model': self.config.model,
                'temperature': self.config.temperature,
                'max_tokens': self.config.max_tokens
            }
            cached_result = self.cache.get(prompt, params)
            if cached_result:
                # If we have a target_words, validate cached result against requirements
                if target_words is not None:
                    try:
                        narration = self.extract_narration(cached_result)
                        validation = self.parse_validation(cached_result)
                        word_count = self.count_words(narration)
                        ok, issues = self.check_requirements(narration, validation, target_words, self.config.word_tolerance_percent)
                        if ok:
                            if self.health_monitor:
                                self.health_monitor.update_metric('cache_hits', 1)
                            self.logger.info("    ✓ Použit cache pro segment (validated)")
                            return cached_result
                        else:
                            # cached result not acceptable for this target -> log and continue to call API
                            self.logger.debug(f"Cached result failed validation for target {target_words}: {issues}")
                            if self.health_monitor:
                                self.health_monitor.update_metric('cache_misses', 1)
                    except Exception as e:
                        self.logger.debug(f"Error validating cached result: {e}")
                        if self.health_monitor:
                            self.health_monitor.update_metric('cache_misses', 1)
                else:
                    if self.health_monitor:
                        self.health_monitor.update_metric('cache_hits', 1)
                    self.logger.info(f"    ✓ Použit cache pro segment")
                    return cached_result
            elif self.health_monitor:
                self.health_monitor.update_metric('cache_misses', 1)

        max_retries = 3

        for retry in range(max_retries):
            try:
                # Kontrola zdraví systému
                if self.health_monitor and self.health_monitor.should_throttle():
                    self.logger.warning("Systém je přetížený, čekám...")
                    time.sleep(5)

                if retry > 0:
                    delay = self.retry_delays[min(retry, len(self.retry_delays)-1)]
                    self.logger.info(f"    Čekám {delay} sekund před dalším pokusem...")
                    time.sleep(delay)
                else:
                    time.sleep(self.config.rate_limit_delay)

                if self.health_monitor:
                    self.health_monitor.update_metric('api_calls', 1)

                start_time = time.time()

                response = self.client.messages.create(
                    model=self.config.model,
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                    messages=[{"role": "user", "content": prompt}]
                )

                elapsed = time.time() - start_time

                # store elapsed for diagnostics
                try:
                    self._last_call_elapsed = elapsed
                except Exception:
                    pass

                if self.health_monitor:
                    self.health_monitor.update_metric('average_response_time', elapsed, increment=False)

                if response and response.content:
                    result = response.content[0].text

                    # detect finish_reason if present (best-effort)
                    truncated = False
                    finish_reason = None
                    try:
                        first = response.content[0]
                        if hasattr(first, 'finish_reason'):
                            finish_reason = getattr(first, 'finish_reason')
                        elif isinstance(first, dict):
                            finish_reason = first.get('finish_reason') or first.get('stop_reason')
                        if finish_reason and str(finish_reason).lower().find('max') != -1:
                            truncated = True
                    except Exception:
                        pass

                    try:
                        self._last_call_truncated = truncated
                        self._last_call_finish_reason = finish_reason
                    except Exception:
                        pass

                    # Debug: log truncated prompt for auditing
                    try:
                        self.logger.debug("SENT PROMPT TRUNC (first 800 chars): %s", prompt[:800])
                        self.logger.debug("API elapsed=%.2fs finish_reason=%s truncated=%s", elapsed, str(finish_reason), truncated)
                    except Exception:
                        pass

                    if truncated:
                        self.logger.warning("Response likely truncated (finish_reason=%s). Will retry if attempts remain.", finish_reason)

                    return result

            except (httpx.ReadTimeout, httpx.WriteTimeout, httpx.ConnectTimeout, httpx.NetworkError) as e:
                # network/timeout specific -> increment api_errors metric and retry
                if self.health_monitor:
                    self.health_monitor.update_metric('api_errors', 1)
                self.logger.warning(f"Network/timeout error while calling API: {e}. Will retry if attempts remain.")
                # continue to next retry

            except Exception as e:
                if self.health_monitor:
                    self.health_monitor.update_metric('api_errors', 1)

                if retry == max_retries - 1:
                    raise APIError(f"API volání selhalo po {max_retries} pokusech: {e}")

            except Exception as e:
                if self.health_monitor:
                    self.health_monitor.update_metric('api_errors', 1)

                if retry == max_retries - 1:
                    raise APIError(f"API volání selhalo po {max_retries} pokusech: {e}")

        return None

    def generate_segment(self, prompt: str, fix_template: str, segment_idx: int,
                        target_words: int, series_name: Optional[str] = None) -> SegmentResult:
        """Generuje jeden segment s opravnými pokusy"""
        start_time = time.time()
        attempts = []
        best_result = None
        best_score = float('inf')

        for attempt_num in range(1, self.config.max_attempts + 1):
            self.logger.info(f"  Pokus {attempt_num}/{self.config.max_attempts}")

            try:
                if attempt_num > 1 and best_result and fix_template:
                    issues_text = "\n".join([f"- {issue}" for issue in best_result.get('issues', [])])
                    current_prompt = fix_template.replace("{ISSUE_LIST}", issues_text)
                    current_prompt = f"Previous output:\n{best_result['full_text']}\n\n{current_prompt}"

                    # Augment fix_template on retries with explicit instruction to reach target length
                    try:
                        extra_instruction = (
                            "Ensure the output meets the full target word count. "
                            "Extend narrative depth where needed."
                        )
                        if extra_instruction not in current_prompt:
                            current_prompt = extra_instruction + "\n\n" + current_prompt
                            self.logger.debug("Applied extra_instruction to fix_template for retry")
                    except Exception:
                        pass
                else:
                    current_prompt = prompt

                # If still retrying and series_name provided, prepend strict topic instruction to avoid drift
                if attempt_num > 1 and series_name:
                    try:
                        topic_token = series_name.replace('_', ' ')
                        strict_prefix = (
                            f"ONLY write about {topic_token}. Do NOT include unrelated topics. "
                            "If you cannot produce content exclusively about this topic, respond with an empty narration and a validation block.\n\n"
                        )
                        current_prompt = strict_prefix + current_prompt
                        self.logger.debug(f"Applied strict prefix for series '{series_name}' on attempt {attempt_num}")
                    except Exception:
                        pass

                full_text = self.call_api_with_retry(current_prompt, attempt_num, target_words=target_words)

                if not full_text:
                    raise APIError("API nevrátilo žádný text")

                narration = self.extract_narration(full_text)
                validation = self.parse_validation(full_text)
                word_count = self.count_words(narration)

                success, issues = self.check_requirements(
                    narration, validation, target_words,
                    self.config.word_tolerance_percent
                )

                score = abs(word_count - target_words)

                attempt_data = {
                    'attempt': attempt_num,
                    'wordcount': word_count,
                    'status': 'success' if success else 'failed',
                    'issues': issues
                }
                attempts.append(attempt_data)

                if score < best_score:
                    best_score = score
                    best_result = {
                        'text': narration,
                        'full_text': full_text,
                        'wordcount': word_count,
                        'validation': validation,
                        'issues': issues,
                        'success': success
                    }

                if success:
                    self.logger.info(f"    ✓ Úspěch! {word_count} slov")
                    if self.health_monitor:
                        self.health_monitor.update_metric('segments_generated', 1)
                    # Cache successful full_text for this prompt to speed up future runs
                    try:
                        if self.cache and self.config.enable_cache:
                            params = {
                                'model': self.config.model,
                                'temperature': self.config.temperature,
                                'max_tokens': self.config.max_tokens
                            }
                            # store full_text (including validation) under current_prompt
                            self.cache.set(current_prompt, params, full_text)
                            self.logger.debug('Cached successful result for prompt (validated)')
                    except Exception as e:
                        self.logger.debug(f'Failed to cache result: {e}')
                    break
                else:
                    self.logger.warning(f"    ✗ Problémy: {', '.join(issues)}")

            except APIError as e:
                self.logger.error(f"    API chyba: {e}")
                attempts.append({
                    'attempt': attempt_num,
                    'status': 'error',
                    'error': str(e)
                })
                break

            except Exception as e:
                self.logger.error(f"    Neočekávaná chyba: {e}")
                attempts.append({
                    'attempt': attempt_num,
                    'status': 'error',
                    'error': str(e)
                })

        generation_time = time.time() - start_time

        if best_result:
            status = GenerationStatus.SUCCESS if best_result['success'] else GenerationStatus.WARNING
            return SegmentResult(
                segment_index=segment_idx,
                attempts=attempts,
                final_text=best_result['text'],
                final_wordcount=best_result['wordcount'],
                status=status,
                validation=best_result['validation'],
                generation_time=generation_time
            )
        else:
            if self.health_monitor:
                self.health_monitor.update_metric('segments_failed', 1)
            return SegmentResult(
                segment_index=segment_idx,
                attempts=attempts,
                final_text='',
                final_wordcount=0,
                status=GenerationStatus.FAILED,
                error_message="Nepodařilo se vygenerovat žádný text",
                generation_time=generation_time
            )

    async def generate_segment_async(self, prompt: str, fix_template: str,
                                    segment_idx: int, target_words: int) -> SegmentResult:
        """Asynchronní generování segmentu"""
        start_time = time.time()

        # Kontrola cache
        if self.cache and self.config.enable_cache:
            params = {
                'model': self.config.model,
                'temperature': self.config.temperature,
                'max_tokens': self.config.max_tokens
            }
            cached_result = self.cache.get(prompt, params)
            if cached_result:
                if self.health_monitor:
                    self.health_monitor.update_metric('cache_hits', 1)

                narration = self.extract_narration(cached_result)
                word_count = self.count_words(narration)

                return SegmentResult(
                    segment_index=segment_idx,
                    attempts=[],
                    final_text=narration,
                    final_wordcount=word_count,
                    status=GenerationStatus.CACHED,
                    from_cache=True,
                    generation_time=time.time() - start_time
                )

        try:
            full_text = await self.call_api_async(prompt)

            if not full_text:
                raise APIError("API nevrátilo žádný text")

            narration = self.extract_narration(full_text)
            validation = self.parse_validation(full_text)
            word_count = self.count_words(narration)

            success, issues = self.check_requirements(
                narration, validation, target_words,
                self.config.word_tolerance_percent
            )

            # Uložit do cache
            if self.cache and self.config.enable_cache and success:
                params = {
                    'model': self.config.model,
                    'temperature': self.config.temperature,
                    'max_tokens': self.config.max_tokens
                }
                self.cache.set(prompt, params, full_text)

            if self.health_monitor:
                if success:
                    self.health_monitor.update_metric('segments_generated', 1)
                else:
                    self.health_monitor.update_metric('segments_failed', 1)

            return SegmentResult(
                segment_index=segment_idx,
                attempts=[{'attempt': 1, 'wordcount': word_count, 'status': 'success' if success else 'failed'}],
                final_text=narration,
                final_wordcount=word_count,
                status=GenerationStatus.SUCCESS if success else GenerationStatus.WARNING,
                validation=validation,
                generation_time=time.time() - start_time
            )

        except Exception as e:
            self.logger.error(f"Chyba při asynchronním generování: {e}")
            if self.health_monitor:
                self.health_monitor.update_metric('segments_failed', 1)

            return SegmentResult(
                segment_index=segment_idx,
                attempts=[],
                final_text='',
                final_wordcount=0,
                status=GenerationStatus.FAILED,
                error_message=str(e),
                generation_time=time.time() - start_time
            )

    def generate_segments_parallel(self, segments_data: List[Dict],
                                  prompts_dir: Path) -> List[SegmentResult]:
        """Paralelní generování segmentů"""
        results = []

        if not self.config.enable_parallel:
            # Sekvenční zpracování
            for seg_data in segments_data:
                result = self._process_single_segment(seg_data, prompts_dir)
                results.append(result)
        else:
            # Paralelní zpracování
            with ThreadPoolExecutor(max_workers=self.config.max_parallel_segments) as executor:
                futures = []
                for seg_data in segments_data:
                    future = executor.submit(self._process_single_segment, seg_data, prompts_dir)
                    futures.append((seg_data['segment_index'], future))

                # Zpracovat výsledky podle pořadí
                for seg_idx, future in sorted(futures, key=lambda x: x[0]):
                    try:
                        result = future.result(timeout=300)  # 5 minut timeout
                        results.append(result)
                    except Exception as e:
                        self.logger.error(f"Chyba při paralelním zpracování segmentu {seg_idx}: {e}")
                        results.append(SegmentResult(
                            segment_index=seg_idx,
                            attempts=[],
                            final_text='',
                            final_wordcount=0,
                            status=GenerationStatus.ERROR,
                            error_message=str(e)
                        ))

        return results

    def _process_single_segment(self, seg_data: Dict, prompts_dir: Path) -> SegmentResult:
        """Zpracuje jeden segment"""
        seg_idx = seg_data['segment_index']
        seg_pad = f"{seg_idx:02d}"

        try:
            self.logger.info(f"\nSegment {seg_idx}: {seg_data.get('msp_label', 'Bez názvu')[:50]}...")

            exec_file = prompts_dir / f"msp_{seg_pad}_execution.txt"
            fix_file = prompts_dir / f"msp_{seg_pad}_fix_template.txt"

            if not exec_file.exists():
                return SegmentResult(
                    segment_index=seg_idx,
                    attempts=[],
                    final_text='',
                    final_wordcount=0,
                    status=GenerationStatus.FAILED,
                    error_message=f"Chybí execution prompt"
                )

            exec_prompt = self.load_prompt(exec_file)
            fix_template = self.load_prompt(fix_file) if fix_file.exists() else ""

            # Debug: log prompt file info and short hash for auditing
            try:
                exec_hash = hashlib.sha256(exec_prompt.encode('utf-8')).hexdigest()[:8]
            except Exception:
                exec_hash = 'err'
            self.logger.debug(f"PROMPT_FILES: exec={exec_file} fix_exists={fix_file.exists()} exec_sha={exec_hash}")
            # Optional lightweight topic sanity check: warn if series name not mentioned in prompt
            try:
                series_name = prompts_dir.parent.name
                topic_token = series_name.replace('_', ' ').lower()
                if topic_token and topic_token not in exec_prompt.lower() and topic_token not in fix_template.lower():
                    self.logger.warning(f"Possible topic mismatch: series '{series_name}' not mentioned in exec prompt {exec_file}")
            except Exception:
                pass

            # Pass real series name (three levels up from prompts_dir): outputs/prompts/<series>/<lang>/epX/prompts
            real_series_name = prompts_dir.parent.parent.parent.name if prompts_dir.parent.parent.parent is not None else prompts_dir.parent.name
            return self.generate_segment(
                exec_prompt, fix_template, seg_idx,
                seg_data.get('word_target', 500),
                series_name=real_series_name
            )

        except Exception as e:
            self.logger.error(f"Chyba při zpracování segmentu {seg_idx}: {e}")
            return SegmentResult(
                segment_index=seg_idx,
                attempts=[],
                final_text='',
                final_wordcount=0,
                status=GenerationStatus.ERROR,
                error_message=str(e)
            )

    async def generate_fusion_async(self, segments: List[str], fusion_prompt: str) -> Optional[str]:
        """Asynchronní generování fúze"""
        self.logger.info("Generování fúze segmentů...")

        try:
            segments_text = "\n\n---SEGMENT---\n\n".join(segments)
            full_prompt = f"{fusion_prompt}\n\nSEGMENTS TO FUSE:\n\n{segments_text}"

            result = await self.call_api_async(full_prompt)

            if result:
                self.logger.info("Fúze úspěšně dokončena")
                return result.strip()

        except Exception as e:
            self.logger.error(f"Chyba při fúzi: {e}")

        return None

    def generate_fusion(self, segments: List[str], fusion_prompt: str) -> Optional[str]:
        """Synchronní generování fúze"""
        if self.config.enable_parallel:
            # Použít asynchronní verzi
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(
                    self.generate_fusion_async(segments, fusion_prompt)
                )
            finally:
                loop.close()
        else:
            # Původní synchronní implementace
            self.logger.info("Generování fúze segmentů...")
            try:
                segments_text = "\n\n---SEGMENT---\n\n".join(segments)
                full_prompt = f"{fusion_prompt}\n\nSEGMENTS TO FUSE:\n\n{segments_text}"

                result = self.call_api_with_retry(full_prompt)

                if result:
                    self.logger.info("Fúze úspěšně dokončena")
                    return result.strip()

            except Exception as e:
                self.logger.error(f"Chyba při fúzi: {e}")

            return None

    def save_with_backup(self, file_path: Path, content: str, encoding='utf-8'):
        """Uloží soubor s vytvořením zálohy"""
        try:
            # Bezpečná validace cesty
            file_path = SecureCredentialManager.sanitize_path(str(file_path))

            if file_path.exists():
                backup_path = file_path.with_name(f"{file_path.name}.bak_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
                try:
                    file_path.rename(backup_path)
                    self.logger.debug(f"Vytvořena záloha: {backup_path}")
                except Exception as e:
                    self.logger.warning(f"Nelze vytvořit zálohu {backup_path}: {e}")

            file_path.write_text(content, encoding=encoding)

        except Exception as e:
            self.logger.error(f"Chyba při ukládání {file_path}: {e}")
            raise

    async def save_progressive(self, file_path: Path, content: str):
        """Progresivní asynchronní ukládání"""
        try:
            file_path = SecureCredentialManager.sanitize_path(str(file_path))

            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(content)

        except Exception as e:
            self.logger.error(f"Chyba při progresivním ukládání: {e}")

    def process_episode(self, episode_path: Path, output_base: Path) -> bool:
        """Zpracuje jednu epizodu s optimalizacemi"""
        episode_name = episode_path.name
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"Zpracovávám epizodu: {episode_name}")
        self.logger.info(f"{'='*60}")

        try:
            prompts_dir = episode_path / 'prompts'
            meta_dir = episode_path / 'meta'

            # Načti metadata
            context_file = meta_dir / 'episode_context.json'
            if not context_file.exists():
                raise FileNotFoundError(f"Nenalezen episode_context.json v {meta_dir}")

            with open(context_file, 'r', encoding='utf-8') as f:
                context = json.load(f)

            if 'segments' not in context:
                raise ValidationError("episode_context.json neobsahuje 'segments'")

            # Výstupní adresář
            series_name = episode_path.parent.parent.name
            language_name = episode_path.parent.name
            output_dir = output_base / series_name / language_name / episode_name
            output_dir.mkdir(parents=True, exist_ok=True)

            # PARALELNÍ zpracování segmentů
            results = self.generate_segments_parallel(context['segments'], prompts_dir)

            successful_segments = sum(1 for r in results if r.status in [GenerationStatus.SUCCESS, GenerationStatus.WARNING, GenerationStatus.CACHED])

            # Progresivní ukládání segmentů
            for result in results:
                if result.final_text:
                    segment_file = output_dir / f"segment_{result.segment_index:02d}.txt"
                    self.save_with_backup(segment_file, result.final_text)

            # Fúze segmentů
            fusion_success = False
            if successful_segments >= 3:
                fusion_file = prompts_dir / 'fusion_instructions.txt'
                if fusion_file.exists():
                    try:
                        fusion_prompt = self.load_prompt(fusion_file)
                        segment_texts = [r.final_text for r in results if r.final_text]

                        if len(segment_texts) >= 3:
                            fused_text = self.generate_fusion(segment_texts, fusion_prompt)
                            if fused_text:
                                fusion_output = output_dir / 'fusion_result.txt'
                                self.save_with_backup(fusion_output, fused_text)
                                fusion_success = True
                                self.logger.info(f"✓ Fúze dokončena: {self.count_words(fused_text)} slov")
                    except Exception as e:
                        self.logger.error(f"Chyba při fúzi: {e}")

            # Ulož log s metrikami
            total_generation_time = sum(r.generation_time for r in results)

            log_data = {
                'episode': episode_name,
                'timestamp': datetime.now().isoformat(),
                'segments': [
                    {
                        'segment_index': r.segment_index,
                        'status': r.status.value,
                        'final_wordcount': r.final_wordcount,
                        'attempts': r.attempts,
                        'from_cache': r.from_cache,
                        'generation_time': r.generation_time,
                        'error_message': r.error_message
                    } for r in results
                ],
                'total_words': sum(r.final_wordcount for r in results),
                'successful_segments': successful_segments,
                'total_segments': len(results),
                'fusion_generated': fusion_success,
                'status': 'complete' if successful_segments == len(results) else 'partial',
                'total_generation_time': total_generation_time,
                'cache_hits': sum(1 for r in results if r.from_cache),
                'performance_metrics': self.health_monitor.metrics.to_dict() if self.health_monitor else None
            }

            log_file = output_dir / 'generation_log.json'
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, indent=2, ensure_ascii=False)

            # Aktualizace metrik
            if self.health_monitor:
                self.health_monitor.metrics.update_success_rate()

            self.logger.info(f"\n{'='*60}")
            self.logger.info(f"Epizoda {episode_name} dokončena")
            self.logger.info(f"Úspěšné segmenty: {successful_segments}/{len(results)}")
            self.logger.info(f"Cache hits: {sum(1 for r in results if r.from_cache)}")
            self.logger.info(f"Celkový čas: {total_generation_time:.2f}s")
            self.logger.info(f"Výsledky uloženy do: {output_dir}")
            self.logger.info(f"{'='*60}")

            return successful_segments > 0

        except Exception as e:
            self.logger.error(f"Kritická chyba při zpracování epizody {episode_name}: {e}")
            self.logger.debug(traceback.format_exc())
            return False

    def process_episodes_parallel(self, episodes: List[Path], output_base: Path) -> Dict[str, bool]:
        """Paralelní zpracování epizod"""
        results = {}

        if not self.config.enable_parallel:
            # Sekvenční zpracování
            for episode in episodes:
                results[episode.name] = self.process_episode(episode, output_base)
        else:
            # Paralelní zpracování epizod
            with ThreadPoolExecutor(max_workers=self.config.max_parallel_episodes) as executor:
                futures = {
                    executor.submit(self.process_episode, episode, output_base): episode
                    for episode in episodes
                }

                for future in as_completed(futures):
                    episode = futures[future]
                    try:
                        results[episode.name] = future.result(timeout=1800)  # 30 minut timeout
                    except Exception as e:
                        self.logger.error(f"Chyba při zpracování epizody {episode.name}: {e}")
                        results[episode.name] = False

        return results

    def run(self):
        """Hlavní běh programu s optimalizacemi"""
        print("\n=== OPTIMALIZOVANÝ CLAUDE NARRATION GENERATOR ===\n")

        try:
            # Interaktivní výběr
            series_path, episodes = self.interactive_menu()

            print(f"\nVybraná série: {series_path.name}")
            print(f"Vybrané epizody: {', '.join(ep.name for ep in episodes)}")

            if self.config.enable_parallel:
                print(f"Paralelní zpracování: ANO (max {self.config.max_parallel_episodes} epizod současně)")
            if self.config.enable_cache:
                print(f"Cache: AKTIVNÍ")
            if self.health_monitor:
                print(f"Monitoring: AKTIVNÍ")

            confirm = self.safe_input("\nPokračovat? (y/n): ", lambda x: x.lower() in ['y', 'n'])
            if confirm.lower() != 'y':
                print("Zrušeno")
                return

            # Výstupní adresář
            output_base = Path(self.config.claude_output_path)

            # Vyčistit starou cache
            if self.cache:
                self.cache.clear_old_entries(days=7)

            # Zpracuj epizody PARALELNĚ
            results = self.process_episodes_parallel(episodes, output_base)

            # Statistiky
            successful_episodes = sum(1 for success in results.values() if success)
            failed_episodes = [name for name, success in results.items() if not success]

            # Finální souhrn
            print("\n=== GENEROVÁNÍ DOKONČENO ===")
            print(f"Úspěšně zpracováno: {successful_episodes}/{len(episodes)} epizod")
            if failed_episodes:
                print(f"Selhané epizody: {', '.join(failed_episodes)}")

            # Zobraz metriky
            if self.health_monitor:
                print(self.health_monitor.metrics.get_summary())

                # Ulož zdravotní report
                health_report = self.health_monitor.get_health_status()
                report_file = Path(self.config.claude_output_path).parent / "logs" / f"health_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                with open(report_file, 'w', encoding='utf-8') as f:
                    json.dump(health_report, f, indent=2)
                print(f"Zdravotní report uložen: {report_file}")

            # Ulož souhrn session
            self.save_session_summary(
                output_base, episodes, successful_episodes, failed_episodes
            )

        except KeyboardInterrupt:
            print("\n\nPřerušeno uživatelem")
            # Ulož částečné výsledky
            if 'output_base' in locals():
                self.save_session_summary(
                    output_base, episodes[:len(results)] if 'results' in locals() else [],
                    sum(1 for s in results.values() if s) if 'results' in locals() else 0,
                    [n for n, s in results.items() if not s] if 'results' in locals() else []
                )
        except Exception as e:
            self.logger.error(f"Kritická chyba v hlavním běhu: {e}")
            self.logger.debug(traceback.format_exc())
            print(f"\nKRITICKÁ CHYBA: {e}")
            print("Zkontrolujte log soubory pro více informací")
        finally:
            # Cleanup
            if hasattr(self, 'executor'):
                self.executor.shutdown(wait=True)
            # close sync http client
            if hasattr(self, 'http_client'):
                try:
                    self.http_client.close()
                except Exception:
                    pass
            # close async resources
            try:
                # Pokud není běžící loop, použijeme asyncio.run
                loop = asyncio.get_event_loop()
                if not loop.is_running():
                    asyncio.run(self._close_async_resources())
                else:
                    loop.create_task(self._close_async_resources())
            except RuntimeError:
                # žádný event loop -> použijeme asyncio.run
                try:
                    asyncio.run(self._close_async_resources())
                except Exception:
                    pass
            except Exception:
                pass

    def save_session_summary(self, output_base: Path, episodes: List[Path],
                           successful: int, failed: List[str]):
        """Uloží souhrn celé session s metrikami"""
        try:
            summary_dir = output_base / "summaries"
            summary_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            summary_file = summary_dir / f"session_{timestamp}.json"

            summary = {
                'timestamp': datetime.now().isoformat(),
                'total_episodes': len(episodes),
                'successful_episodes': successful,
                'failed_episodes': failed,
                'episodes_processed': [ep.name for ep in episodes],
                'config': {
                    'model': self.config.model,
                    'temperature': self.config.temperature,
                    'max_tokens': self.config.max_tokens,
                    'word_tolerance': self.config.word_tolerance_percent,
                    'parallel_enabled': self.config.enable_parallel,
                    'cache_enabled': self.config.enable_cache,
                    'max_parallel_segments': self.config.max_parallel_segments,
                    'max_parallel_episodes': self.config.max_parallel_episodes
                },
                'performance_metrics': self.health_monitor.metrics.to_dict() if self.health_monitor else None,
                'health_status': self.health_monitor.get_health_status() if self.health_monitor else None
            }

            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)

            self.logger.info(f"Souhrn session uložen: {summary_file}")

        except Exception as e:
            self.logger.error(f"Nepodařilo se uložit souhrn session: {e}")

def _atexit_close_async(generator: Optional[OptimizedClaudeGenerator] = None):
    """Atexit hook pro zavření asynchronních klientů, pokud existují."""
    try:
        # pokud generátor je explicitně předán
        if generator:
            try:
                asyncio.run(generator._close_async_resources())
            except Exception:
                pass
        else:
            # Nic explicitního - není snadné najít instanci, proto nic neděláme
            pass
    except Exception:
        pass


def main():
    """Hlavní funkce"""
    try:
        # Kontrola Python verze
        if sys.version_info < (3, 7):
            print("Vyžadován Python 3.7 nebo novější")
            sys.exit(1)

        # Načtení konfigurace
        config = Config()

        # Vytvoření a spuštění optimalizovaného generátoru
        generator = OptimizedClaudeGenerator(config)
        # zaregistrujeme atexit handler, který zavře async resources pokud budeme chtít
        atexit.register(_atexit_close_async, generator)
        generator.run()

    except KeyboardInterrupt:
        print("\n\nProgram ukončen uživatelem")
        sys.exit(0)
    except ValidationError as e:
        print(f"CHYBA KONFIGURACE: {e}")
        print("\nZkontrolujte soubor .env a nastavení")
        sys.exit(1)
    except APIError as e:
        print(f"CHYBA API: {e}")
        print("\nZkontrolujte API klíč a připojení k internetu")
        sys.exit(1)
    except ClaudeGeneratorError as e:
        print(f"CHYBA GENERÁTORU: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"KRITICKÁ CHYBA: {e}")
        print("\nPro debug informace zkontrolujte log soubory")
        if '--debug' in sys.argv:
            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
