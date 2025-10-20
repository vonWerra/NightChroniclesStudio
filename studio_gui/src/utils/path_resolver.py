from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Mapping

import structlog

logger = structlog.get_logger(__name__)


class PathResolver:
    """
    Central resolver for module output roots used by the GUI.

    Priority (highest -> lowest):
    1) Module-specific env var (e.g. OUTLINE_OUTPUT_ROOT)
    2) NC_OUTPUTS_ROOT + module subdir (NC_OUTPUTS_ROOT/<module>)
    3) QSettings (project/nc_outputs_root) + module subdir (only if available)
    4) Fallback to cwd()/outputs/<module>

    Returns pathlib.Path for consistency.
    """

    MODULE_ENV_MAP: Mapping[str, str] = {
        "outline": "OUTLINE_OUTPUT_ROOT",
        "prompts": "PROMPTS_OUTPUT_ROOT",
        "narration": "NARRATION_OUTPUT_ROOT",
        "postprocess": "POSTPROC_OUTPUT_ROOT",
        "tts": "TTS_OUTPUT_ROOT",
        "export": "EXPORT_OUTPUT_ROOT",
    }

    DEFAULT_SUBDIR: Mapping[str, str] = {
        "outline": "outline",
        "prompts": "prompts",
        "narration": "narration",
        "postprocess": "postprocess",
        "tts": "tts",
        "export": "export",
    }

    @classmethod
    def _env_or_none(cls, key: str) -> Optional[str]:
        v = os.environ.get(key)
        if v:
            logger.debug("PathResolver: using env var", var=key, value=v)
        return v

    @classmethod
    def _qsettings_nc_outputs_root(cls) -> Optional[str]:
        """Try to read NC_OUTPUTS_ROOT from QSettings if available (only in GUI).
        Import is local so this module can be used in headless tests.
        """
        try:
            from PySide6.QtCore import QSettings  # type: ignore

            qs = QSettings()
            value = qs.value("project/nc_outputs_root", type=str) or qs.value("NC_OUTPUTS_ROOT", type=str)
            if isinstance(value, str) and value:
                logger.debug("PathResolver: Using NC_OUTPUTS_ROOT from QSettings", value=value)
                return value
        except Exception:
            return None
        return None

    @classmethod
    def get_root(cls, module: str) -> Path:
        module = module.lower()
        if module not in cls.DEFAULT_SUBDIR:
            raise ValueError(f"Unknown module for PathResolver: {module!r}")

        # 1) module-specific env var
        module_env = cls.MODULE_ENV_MAP.get(module)
        if module_env:
            v = cls._env_or_none(module_env)
            if v:
                p = Path(v).expanduser().absolute()
                logger.debug("PathResolver: resolved module-specific env path", module=module, path=str(p))
                return p

        # 2) NC_OUTPUTS_ROOT env
        nc = cls._env_or_none("NC_OUTPUTS_ROOT")
        if nc:
            p = Path(nc).expanduser().absolute() / cls.DEFAULT_SUBDIR[module]
            logger.debug("PathResolver: resolved NC_OUTPUTS_ROOT + subdir", module=module, path=str(p))
            return p

        # 3) QSettings
        qs_nc = cls._qsettings_nc_outputs_root()
        if qs_nc:
            p = Path(qs_nc).expanduser().absolute() / cls.DEFAULT_SUBDIR[module]
            logger.debug("PathResolver: resolved QSettings NC_OUTPUTS_ROOT + subdir", module=module, path=str(p))
            return p

        # 4) fallback to ./outputs/<module>
        p = Path.cwd() / "outputs" / cls.DEFAULT_SUBDIR[module]
        logger.debug("PathResolver: using fallback outputs path", module=module, path=str(p))
        return p

    # convenience methods
    @classmethod
    def osnova_root(cls) -> Path:
        return cls.get_root("outline")

    @classmethod
    def prompts_root(cls) -> Path:
        return cls.get_root("prompts")

    @classmethod
    def narration_root(cls) -> Path:
        return cls.get_root("narration")

    @classmethod
    def postproc_root(cls) -> Path:
        return cls.get_root("postprocess")

    @classmethod
    def tts_root(cls) -> Path:
        return cls.get_root("tts")

    @classmethod
    def export_root(cls) -> Path:
        return cls.get_root("export")
