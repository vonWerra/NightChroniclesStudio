from __future__ import annotations

import os
import sys
import json
import asyncio
from typing import Optional
import hashlib
from pathlib import Path
from datetime import datetime, timezone

from PySide6.QtCore import QThread, Signal, QObject, QSettings, QCoreApplication, Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QTabWidget,
    QVBoxLayout,
    QPushButton,
    QTextEdit,
    QFileDialog,
    QLabel,
    QHBoxLayout,
    QCheckBox,
    QLineEdit,
    QComboBox,
    QFormLayout,
    QSpinBox,
    QDoubleSpinBox,
    QGroupBox,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
)

from .process_runner import ProcessRunner
from .qprocess_runner import SubprocessController
from .utils.path_resolver import PathResolver
from .utils.fs_helpers import normalize_name, resolve_topic_dir, find_topic_in_index

import logging
import structlog


def _configure_logging(level: int = logging.INFO) -> None:
    """Configure stdlib logging and structlog for the GUI.

    Sets a reasonable default formatter and adjusts the root logger level so
    debug noise (like PathResolver.debug) can be suppressed by using INFO.
    """
    logging.basicConfig(level=level, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
    # Use stdlib LoggerFactory so structlog messages go through standard logging
    structlog.configure(logger_factory=structlog.stdlib.LoggerFactory(), cache_logger_on_first_use=True)
    logging.getLogger().setLevel(level)

def _start_qprocess(cmd: list[str], env: dict | None, parent: QObject, log_cb, finished_cb, cwd: str | None = None):
    """Helper to start a SubprocessController in a QThread and connect callbacks.

    finished_cb is expected to accept a single int exit_code (legacy callers).
    Returns (thread, worker)
    """
    thread = QThread(parent)
    worker = SubprocessController()
    # DŮLEŽITÉ: moveToThread PŘED nastavením signálů
    worker.moveToThread(thread)

    # wire basic log line -> UI callback (use QueuedConnection to ensure thread safety)
    worker.log_line.connect(log_cb, Qt.QueuedConnection)

    # parsed structured logs -> send as stdout JSON string to log_cb
    def _on_parsed(obj):
        try:
            s = json.dumps(obj, ensure_ascii=False)
        except Exception:
            s = str(obj)
        log_cb("stdout", s)
    worker.parsed_log.connect(_on_parsed, Qt.QueuedConnection)

    # errors from controller
    worker.error.connect(lambda msg: log_cb("stderr", f"[qprocess_runner] {msg}"), Qt.QueuedConnection)

    # finished emits (exit_code, exit_status) -> call legacy finished_cb(exit_code)
    def _wrapped_finished(exit_code: int, exit_status: int):
        try:
            finished_cb(int(exit_code))
        finally:
            # stop thread once finished
            try:
                thread.quit()
            except Exception:
                pass
    worker.finished.connect(_wrapped_finished, Qt.QueuedConnection)

    def _start():
        prog = cmd[0]
        args = cmd[1:]
        # forward cwd to worker.start so subprocess runs in desired working dir
        worker.start(prog, args, env=env, cwd=cwd)

    thread.started.connect(_start)
    thread.start()
    return thread, worker


class AsyncRunner(QObject):
    line = Signal(str, str)  # stream, text
    finished = Signal(int)

    def __init__(self, cmd: list[str], cwd: Optional[str] = None, env: Optional[dict[str, str]] = None) -> None:
        super().__init__()
        self.cmd = cmd
        self.cwd = cwd
        self.env = env

    def start(self) -> None:
        asyncio.run(self._run())

    async def _run(self) -> None:
        runner = ProcessRunner(self.cmd, cwd=self.cwd, env=self.env)
        await runner.start()
        async for evt in runner.iter_lines():
            self.line.emit(evt.stream, evt.line)
        code = await runner.wait()
        self.finished.emit(code)


from .widgets.log_pane import LogPane



class ProjectTab(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.outputs_root: Optional[str] = None
        self.settings = QSettings()

        v = QVBoxLayout(self)
        btn_pick = QPushButton("Select outputs/ root…", self)
        btn_pick.clicked.connect(self.pick_root)
        self.lbl = QLabel("NC_OUTPUTS_ROOT = (nenastaveno)", self)
        # Rescan button and status
        self.btn_rescan = QPushButton("Rescan outputs", self)
        self.btn_rescan.clicked.connect(self.rescan_outputs)
        self.lbl_rescan_status = QLabel("", self)
        self.rescan_progress = QProgressBar(self)
        self.rescan_progress.setRange(0, 100)
        self.rescan_progress.setValue(0)

        # progress layout
        prog_layout = QWidget(self)
        pl = QHBoxLayout(prog_layout)
        pl.setContentsMargins(0,0,0,0)
        pl.addWidget(self.lbl_rescan_status)
        pl.addWidget(self.rescan_progress)
        # place progress widget into main vertical layout
        v.addWidget(prog_layout)

        top_row = QWidget(self)
        top_layout = QHBoxLayout(top_row)
        top_layout.setContentsMargins(0,0,0,0)
        top_layout.addWidget(btn_pick)
        top_layout.addWidget(self.btn_rescan)
        top_layout.addWidget(self.lbl)
        # Add cancel rescan button
        self.btn_rescan_cancel = QPushButton('Cancel rescan', self)
        self.btn_rescan_cancel.clicked.connect(lambda: getattr(self, '_rescan_stop_event', None) and self._rescan_stop_event.set())
        top_layout.addWidget(self.btn_rescan_cancel)

        v.addWidget(top_row)

        self.log = LogPane()
        v.addWidget(self.log)

        # Load saved root (persisted in QSettings); if not present, adopt current env and persist
        saved = self.settings.value("project/nc_outputs_root", "")
        if saved:
            self.outputs_root = str(saved)
            self.lbl.setText(f"NC_OUTPUTS_ROOT = {self.outputs_root}")
            os.environ["NC_OUTPUTS_ROOT"] = self.outputs_root
        else:
            # adopt environment if provided and persist so it survives restarts
            env_root = os.environ.get("NC_OUTPUTS_ROOT")
            if env_root:
                self.outputs_root = env_root
                self.lbl.setText(f"NC_OUTPUTS_ROOT = {env_root}")
                self.settings.setValue("project/nc_outputs_root", env_root)

    def pick_root(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Vyber outputs/ root")
        if path:
            self.outputs_root = path
            self.lbl.setText(f"NC_OUTPUTS_ROOT = {path}")
            os.environ["NC_OUTPUTS_ROOT"] = path
            self.settings.setValue("project/nc_outputs_root", path)

    def rescan_outputs(self) -> None:
        """Trigger rescanning of prompts/narration outputs and persist indexes to studio_gui/.tmp."""
        # disable button to avoid reentrancy
        self.btn_rescan.setEnabled(False)
        self.lbl_rescan_status.setText("Scanning...")
        self.log.append('stdout', 'Starting rescan of outputs...')

        # Run scan in background thread to avoid blocking UI
        import threading
        stop_event = threading.Event()

        def _progress_cb(module: str, percent: int, message: str):
            # append a brief progress update to log (throttled by design) and update progress bar
            try:
                self.log.append('stdout', f'[{module}] {percent}% - {message}')
            except Exception:
                pass
            # update UI progress bar on main thread
            try:
                from PySide6.QtCore import QTimer
                def _u():
                    try:
                        self.rescan_progress.setValue(int(percent))
                        self.lbl_rescan_status.setText(message)
                    except Exception:
                        pass
                QTimer.singleShot(0, _u)
            except Exception:
                pass

        def _worker():
            try:
                from .fs_index import discover_prompts_root, scan_prompts_root, discover_narration_root, scan_narration_root, save_index
                tmp_dir = os.path.join('studio_gui', '.tmp')
                os.makedirs(tmp_dir, exist_ok=True)

                # Prompts
                try:
                    pr = discover_prompts_root()
                    self.log.append('stdout', f'Rescanning prompts root: {pr}')
                    pindex = scan_prompts_root(pr, stop_event=stop_event, progress_callback=_progress_cb)
                    save_index(os.path.join(tmp_dir, 'prompts_index.json'), pindex)
                    self.log.append('stdout', f'Prompts index saved: {os.path.join(tmp_dir, "prompts_index.json")}')
                except Exception as e:
                    self.log.append('stderr', f'Error scanning prompts: {e}')

                # Narration
                try:
                    nr = discover_narration_root()
                    self.log.append('stdout', f'Rescanning narration root: {nr}')
                    nindex = scan_narration_root(nr, stop_event=stop_event, progress_callback=_progress_cb)
                    save_index(os.path.join(tmp_dir, 'narration_index.json'), nindex)
                    self.log.append('stdout', f'Narration index saved: {os.path.join(tmp_dir, "narration_index.json")}')
                except Exception as e:
                    self.log.append('stderr', f'Error scanning narration: {e}')

                # Postprocess scanning could be added similarly
                success = True
            except Exception as e:
                success = False
                err = str(e)
            # schedule UI update back on main thread
            from PySide6.QtCore import QTimer
            def _finish():
                if success:
                    self.lbl_rescan_status.setText('Done')
                    self.log.append('stdout', 'Rescan finished successfully')
                else:
                    self.lbl_rescan_status.setText('Error')
                    self.log.append('stderr', f'Rescan failed: {err}')
                self.rescan_progress.setValue(100 if success else 0)
                self.btn_rescan.setEnabled(True)
                # refresh tabs that have refresh_topics or load indexes from .tmp
                try:
                    win = self.window()
                    tw = win.centralWidget()
                    # try to load cached indexes
                    tmp_dir = os.path.join('studio_gui', '.tmp')
                    prompts_idx = None
                    narration_idx = None
                    try:
                        from .fs_index import load_index
                        prompts_idx = load_index(os.path.join(tmp_dir, 'prompts_index.json'))
                        narration_idx = load_index(os.path.join(tmp_dir, 'narration_index.json'))
                    except Exception:
                        prompts_idx = None
                        narration_idx = None

                    for i in range(tw.count()):
                        w = tw.widget(i)
                        try:
                            # prefer methods that accept setting indexes directly
                            if prompts_idx and hasattr(w, 'set_prompt_index'):
                                w.set_prompt_index(prompts_idx)
                            if narration_idx and hasattr(w, 'set_narration_index'):
                                w.set_narration_index(narration_idx)
                            if hasattr(w, 'refresh_topics'):
                                w.refresh_topics()
                        except Exception:
                            pass
                except Exception:
                    pass
            QTimer.singleShot(0, _finish)

        # store stop_event so other UI elements (like cancel) could set it in future
        self._rescan_stop_event = stop_event
        t = threading.Thread(target=_worker, daemon=True)
        t.start()


class OutlineTab(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.thread: Optional[QThread] = None
        self.worker: Optional[AsyncRunner] = None
        self.base_config_data: Optional[dict] = None
        self.settings = QSettings()

        v = QVBoxLayout(self)

        # Output path info (read-only)
        self.lbl_output_root = QLabel("", self)
        v.addWidget(self.lbl_output_root)
        # update label with current output root
        from .utils.path_resolver import PathResolver
        self.lbl_output_root.setText(f"Output root: {PathResolver.osnova_root()}")

        # Languages
        row_lang = QHBoxLayout()
        self.chk = {code: QCheckBox(code) for code in ["CS", "EN", "DE", "ES", "FR"]}
        for c in self.chk.values():
            c.setChecked(True)
            row_lang.addWidget(c)
        v.addLayout(row_lang)

        # Basic paths and run options
        form_top = QFormLayout()
        self.txt_config = QLineEdit(os.path.join("outline-generator", "config", "outline_config.json"), self)
        btn_cfg = QPushButton("…", self)
        btn_cfg.clicked.connect(self.pick_config)
        cont_cfg = QWidget(self)
        lay_cfg = QHBoxLayout(cont_cfg)
        lay_cfg.setContentsMargins(0, 0, 0, 0)
        lay_cfg.addWidget(self.txt_config)
        lay_cfg.addWidget(btn_cfg)
        form_top.addRow("Config (-c):", cont_cfg)

        self.txt_template = QLineEdit(os.path.join("outline-generator", "templates", "outline_master.txt"), self)
        btn_tpl = QPushButton("…", self)
        btn_tpl.clicked.connect(self.pick_template)
        cont_tpl = QWidget(self)
        lay_tpl = QHBoxLayout(cont_tpl)
        lay_tpl.setContentsMargins(0, 0, 0, 0)
        lay_tpl.addWidget(self.txt_template)
        lay_tpl.addWidget(btn_tpl)
        form_top.addRow("Template (-t):", cont_tpl)

        self.cmb_verbose = QComboBox(self)
        self.cmb_verbose.addItem("Warning (default)", 0)
        self.cmb_verbose.addItem("Info (-v)", 1)
        self.cmb_verbose.addItem("Debug (-vv)", 2)
        form_top.addRow("Verbosity:", self.cmb_verbose)

        self.chk_parallel = QCheckBox("Parallel (-p)", self)
        self.chk_cache = QCheckBox("Cache (--cache)", self)
        self.chk_cache.setChecked(True)
        self.chk_dry = QCheckBox("Dry run (--dry-run)", self)

        cont_opts = QWidget(self)
        lay_opts = QHBoxLayout(cont_opts)
        lay_opts.setContentsMargins(0, 0, 0, 0)
        lay_opts.addWidget(self.chk_parallel)
        lay_opts.addWidget(self.chk_cache)
        lay_opts.addWidget(self.chk_dry)
        form_top.addRow("Options:", cont_opts)

        v.addLayout(form_top)

        # Config overrides group
        grp = QGroupBox("Config overrides (uloží se do dočasného JSON a použijí se pro běh)", self)
        g = QFormLayout(grp)
        # Topic
        self.ed_topic = QLineEdit(self)
        g.addRow("Topic:", self.ed_topic)
        # Episodes
        row_ep = QWidget(self)
        lay_ep = QHBoxLayout(row_ep)
        lay_ep.setContentsMargins(0, 0, 0, 0)
        self.chk_ep_auto = QCheckBox("auto", self)
        self.spn_episodes = QSpinBox(self)
        self.spn_episodes.setRange(1, 50)
        self.spn_episodes.setValue(6)
        self.chk_ep_auto.setChecked(True)
        self.spn_episodes.setEnabled(False)
        self.chk_ep_auto.toggled.connect(lambda v: self.spn_episodes.setEnabled(not v))
        lay_ep.addWidget(self.chk_ep_auto)
        lay_ep.addWidget(self.spn_episodes)
        g.addRow("Episodes:", row_ep)
        # Episode minutes
        self.spn_ep_minutes = QSpinBox(self)
        self.spn_ep_minutes.setRange(10, 180)
        self.spn_ep_minutes.setValue(12)
        g.addRow("Episode minutes:", self.spn_ep_minutes)
        # Episode count range
        row_ecr = QWidget(self)
        lay_ecr = QHBoxLayout(row_ecr)
        lay_ecr.setContentsMargins(0, 0, 0, 0)
        self.spn_ecr_min = QSpinBox(self)
        self.spn_ecr_min.setRange(1, 50)
        self.spn_ecr_max = QSpinBox(self)
        self.spn_ecr_max.setRange(1, 50)
        lay_ecr.addWidget(QLabel("min"))
        lay_ecr.addWidget(self.spn_ecr_min)
        lay_ecr.addWidget(QLabel("max"))
        lay_ecr.addWidget(self.spn_ecr_max)
        g.addRow("Episode count range:", row_ecr)
        # MSP params
        self.spn_msp_per = QSpinBox(self)
        self.spn_msp_per.setRange(3, 10)
        self.spn_msp_per.setValue(5)
        g.addRow("MSP per episode:", self.spn_msp_per)
        self.spn_msp_max_words = QSpinBox(self)
        self.spn_msp_max_words.setRange(5, 50)
        self.spn_msp_max_words.setValue(20)
        g.addRow("MSP max words:", self.spn_msp_max_words)
        # Description and series context
        self.spn_desc_max_sent = QSpinBox(self)
        self.spn_desc_max_sent.setRange(1, 10)
        self.spn_desc_max_sent.setValue(2)
        g.addRow("Description max sentences:", self.spn_desc_max_sent)
        row_scs = QWidget(self)
        lay_scs = QHBoxLayout(row_scs)
        lay_scs.setContentsMargins(0, 0, 0, 0)
        self.spn_scs_min = QSpinBox(self)
        self.spn_scs_min.setRange(1, 10)
        self.spn_scs_max = QSpinBox(self)
        self.spn_scs_max.setRange(1, 10)
        lay_scs.addWidget(QLabel("min"))
        lay_scs.addWidget(self.spn_scs_min)
        lay_scs.addWidget(QLabel("max"))
        lay_scs.addWidget(self.spn_scs_max)
        g.addRow("Series context sentences:", row_scs)
        # Ordering
        self.cmb_ordering = QComboBox(self)
        self.cmb_ordering.addItems(["chronological", "thematic"])
        g.addRow("Ordering:", self.cmb_ordering)
        # Tolerances
        row_tol = QWidget(self)
        lay_tol = QHBoxLayout(row_tol)
        lay_tol.setContentsMargins(0, 0, 0, 0)
        self.spn_tol_min = QSpinBox(self)
        self.spn_tol_min.setRange(1, 400)
        self.spn_tol_max = QSpinBox(self)
        self.spn_tol_max.setRange(1, 400)
        lay_tol.addWidget(QLabel("min"))
        lay_tol.addWidget(self.spn_tol_min)
        lay_tol.addWidget(QLabel("max"))
        lay_tol.addWidget(self.spn_tol_max)
        g.addRow("Tolerance (min/max minutes):", row_tol)
        # Sources
        row_src = QWidget(self)
        lay_src = QHBoxLayout(row_src)
        lay_src.setContentsMargins(0, 0, 0, 0)
        self.spn_src_min = QSpinBox(self)
        self.spn_src_min.setRange(1, 50)
        self.spn_src_max = QSpinBox(self)
        self.spn_src_max.setRange(1, 50)
        self.cmb_src_format = QComboBox(self)
        self.cmb_src_format.addItems(["name-only", "with-url", "full-citation"])
        lay_src.addWidget(QLabel("per-episode min"))
        lay_src.addWidget(self.spn_src_min)
        lay_src.addWidget(QLabel("max"))
        lay_src.addWidget(self.spn_src_max)
        lay_src.addWidget(QLabel("format"))
        lay_src.addWidget(self.cmb_src_format)
        g.addRow("Sources:", row_src)
        # Factuality
        row_fac = QWidget(self)
        lay_fac = QHBoxLayout(row_fac)
        lay_fac.setContentsMargins(0, 0, 0, 0)
        self.chk_no_dialogue = QCheckBox("no_dialogue", self)
        self.chk_no_spec = QCheckBox("no_speculation", self)
        self.chk_consensus = QCheckBox("consensus_only", self)
        self.chk_disputes = QCheckBox("note_disputes_briefly", self)
        for w in [self.chk_no_dialogue, self.chk_no_spec, self.chk_consensus, self.chk_disputes]:
            w.setChecked(True)
            lay_fac.addWidget(w)
        g.addRow("Factuality:", row_fac)

        # API overrides (optional)
        row_api = QWidget(self)
        lay_api = QHBoxLayout(row_api)
        lay_api.setContentsMargins(0, 0, 0, 0)
        self.ed_model = QLineEdit(self)
        self.ed_model.setPlaceholderText("gpt-4.1-mini")
        self.ds_temp = QDoubleSpinBox(self)
        self.ds_temp.setRange(0.0, 2.0)
        self.ds_temp.setSingleStep(0.1)
        self.ds_temp.setValue(0.3)
        self.sp_max_tokens = QSpinBox(self)
        self.sp_max_tokens.setRange(100, 10000)
        self.sp_max_tokens.setValue(6000)
        lay_api.addWidget(QLabel("model"))
        lay_api.addWidget(self.ed_model)
        lay_api.addWidget(QLabel("temperature"))
        lay_api.addWidget(self.ds_temp)
        lay_api.addWidget(QLabel("max_tokens"))
        lay_api.addWidget(self.sp_max_tokens)
        g.addRow("API (env overrides):", row_api)

        # Buttons for overrides
        row_btns = QWidget(self)
        lay_btns = QHBoxLayout(row_btns)
        lay_btns.setContentsMargins(0, 0, 0, 0)
        self.btn_load_cfg = QPushButton("Načíst z configu", self)
        self.btn_load_cfg.clicked.connect(self.load_from_config_file)
        lay_btns.addWidget(self.btn_load_cfg)
        g.addRow("", row_btns)

        v.addWidget(grp)

        # Run button
        self.btn_run = QPushButton("Run outline-generator", self)
        self.btn_run.clicked.connect(self.run_outline)
        v.addWidget(self.btn_run)

        # Logs
        self.log = LogPane()
        v.addWidget(self.log)

        # Load persisted prefs if available; otherwise seed from config file
        if not self.load_prefs():
            self.load_from_config_file()

    def pick_config(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Vyber config.json", self.txt_config.text() or ".", "JSON files (*.json);;All files (*)")
        if path:
            self.txt_config.setText(path)
            self.load_from_config_file()

    def pick_template(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Vyber template", self.txt_template.text() or ".", "Text files (*.txt);;All files (*)")
        if path:
            self.txt_template.setText(path)

    def load_from_config_file(self) -> None:
        cfg = self.txt_config.text().strip()
        try:
            with open(cfg, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.base_config_data = data
        except Exception as e:
            self.log.append("stderr", f"Nepodařilo se načíst config: {e}")
            return

        # Helper to read key with fallbacks
        def get2(d: dict, key1: str, key2: Optional[str] = None, default=None):
            if key1 in d:
                return d[key1]
            if key2 and key2 in d:
                return d[key2]
            return default

        # Topic
        self.ed_topic.setText(str(get2(data, "topic", "TOPIC", "")))
        # Episodes
        episodes = get2(data, "episodes", "EPISODES", "auto")
        if isinstance(episodes, str) and episodes == "auto":
            self.chk_ep_auto.setChecked(True)
        else:
            try:
                self.spn_episodes.setValue(int(episodes))
                self.chk_ep_auto.setChecked(False)
            except Exception:
                self.chk_ep_auto.setChecked(True)
        # Episode minutes
        epm = int(get2(data, "episode_minutes", "EPISODE_MINUTES", 12))
        self.spn_ep_minutes.setValue(epm)
        # Episode count range
        ecr = get2(data, "episode_count_range", "EPISODE_COUNT_RANGE", {"min": 6, "max": 8})
        self.spn_ecr_min.setValue(int(get2(ecr, "min", None, 6)))
        self.spn_ecr_max.setValue(int(get2(ecr, "max", None, 8)))
        # MSP
        self.spn_msp_per.setValue(int(get2(data, "msp_per_episode", "MSP_PER_EPISODE", 5)))
        self.spn_msp_max_words.setValue(int(get2(data, "msp_max_words", "MSP_MAX_WORDS", 20)))
        # Description
        self.spn_desc_max_sent.setValue(int(get2(data, "description_max_sentences", "DESCRIPTION_MAX_SENTENCES", 2)))
        # Series context sentences
        scs = get2(data, "series_context_sentences", "SERIES_CONTEXT_SENTENCES", {"min": 1, "max": 2})
        self.spn_scs_min.setValue(int(get2(scs, "min", None, 1)))
        self.spn_scs_max.setValue(int(get2(scs, "max", None, 2)))
        # Ordering
        ordering = str(get2(data, "ordering", "ORDERING", "chronological")).lower()
        idx = max(0, ["chronological", "thematic"].index(ordering) if ordering in ["chronological", "thematic"] else 0)
        self.cmb_ordering.setCurrentIndex(idx)
        # Tolerances
        self.spn_tol_min.setValue(int(get2(data, "tolerance_min", "TOLERANCE_MIN", 10)))
        self.spn_tol_max.setValue(int(get2(data, "tolerance_max", "TOLERANCE_MAX", 15)))
        # Sources
        sources = get2(data, "sources", "SOURCES", {}) or {}
        per_ep = get2(sources, "per_episode", "PER_EPISODE", {}) or {}
        self.spn_src_min.setValue(int(get2(per_ep, "min", "min", 2)))
        self.spn_src_max.setValue(int(get2(per_ep, "max", "max", 4)))
        fmt = str(get2(sources, "format", "FORMAT", "name-only"))
        fmt_idx = ["name-only", "with-url", "full-citation"].index(fmt) if fmt in ["name-only", "with-url", "full-citation"] else 0
        self.cmb_src_format.setCurrentIndex(fmt_idx)
        # Factuality
        factuality = get2(data, "factuality", "FACTUALITY", {}) or {}
        self.chk_no_dialogue.setChecked(bool(get2(factuality, "no_dialogue", "NO_DIALOGUE", True)))
        self.chk_no_spec.setChecked(bool(get2(factuality, "no_speculation", "NO_SPECULATION", True)))
        self.chk_consensus.setChecked(bool(get2(factuality, "consensus_only", "CONSENSUS_ONLY", True)))
        self.chk_disputes.setChecked(bool(get2(factuality, "note_disputes_briefly", "NOTE_DISPUTES_BRIEFLY", True)))

    def build_overridden_config(self) -> dict:
        # Start with base config if loaded, else minimal structure
        data = self.base_config_data.copy() if isinstance(self.base_config_data, dict) else {}

        def ensure_path(d: dict, *keys: str) -> dict:
            cur = d
            for k in keys:
                cur = cur.setdefault(k, {})
            return cur

        # Scalars
        data["topic"] = self.ed_topic.text().strip() or data.get("topic") or ""
        data["episode_minutes"] = int(self.spn_ep_minutes.value())
        data["msp_per_episode"] = int(self.spn_msp_per.value())
        data["msp_max_words"] = int(self.spn_msp_max_words.value())
        data["description_max_sentences"] = int(self.spn_desc_max_sent.value())
        data["ordering"] = self.cmb_ordering.currentText()
        data["tolerance_min"] = int(self.spn_tol_min.value())
        data["tolerance_max"] = int(self.spn_tol_max.value())
        # Episodes (auto or number)
        data["episodes"] = "auto" if self.chk_ep_auto.isChecked() else int(self.spn_episodes.value())
        # Ranges and nested
        ecr = ensure_path(data, "episode_count_range")
        ecr["min"] = int(self.spn_ecr_min.value())
        ecr["max"] = int(self.spn_ecr_max.value())
        scs = ensure_path(data, "series_context_sentences")
        scs["min"] = int(self.spn_scs_min.value())
        scs["max"] = int(self.spn_scs_max.value())
        sources = ensure_path(data, "sources")
        per_ep = ensure_path(sources, "per_episode")
        per_ep["min"] = int(self.spn_src_min.value())
        per_ep["max"] = int(self.spn_src_max.value())
        sources["format"] = self.cmb_src_format.currentText()
        factuality = ensure_path(data, "factuality")
        factuality["no_dialogue"] = bool(self.chk_no_dialogue.isChecked())
        factuality["no_speculation"] = bool(self.chk_no_spec.isChecked())
        factuality["consensus_only"] = bool(self.chk_consensus.isChecked())
        factuality["note_disputes_briefly"] = bool(self.chk_disputes.isChecked())

        # Ensure languages present for Pydantic validation
        data["languages"] = [code for code, w in self.chk.items() if w.isChecked()]

        return data

    def write_temp_config(self) -> str:
        data = self.build_overridden_config()
        tmp_dir = os.path.join("studio_gui", ".tmp")
        os.makedirs(tmp_dir, exist_ok=True)
        tmp_path = os.path.join(tmp_dir, "outline_config_gui.json")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.log.append("stderr", f"Nelze zapsat dočasný config: {e}")
        return tmp_path

    def run_outline(self) -> None:
        langs = [c for c, w in self.chk.items() if w.isChecked()]
        if not langs:
            self.log.append("stderr", "Vyberte alespoň jeden jazyk.")
            return
        # Persist current preferences
        self.save_prefs()

        # Build command to run repo-local script
        script = os.path.join("outline-generator", "generate_outline.py")
        if not os.path.exists(script):
            self.log.append("stderr", f"Nenalezen skript: {script}")
            return

        cmd: list[str] = [sys.executable, script]

        # Verbosity
        vlevel = int(self.cmb_verbose.currentData() or 0)
        cmd.extend(["-v"] * vlevel)

        # Required paths
        tpl = self.txt_template.text().strip()
        if not os.path.isfile(tpl):
            self.log.append("stderr", f"Template soubor neexistuje: {tpl}")
            return
        cmd += ["-t", tpl]

        # Config from overrides -> temp file
        tmp_cfg = self.write_temp_config()
        cmd += ["-c", tmp_cfg]

        # Always use PathResolver.osnova_root() for consistent output location
        from .utils.path_resolver import PathResolver
        out = str(PathResolver.osnova_root())
        cmd += ["-o", out]

        # Languages
        cmd += ["-l", *langs]

        # Flags
        if self.chk_parallel.isChecked():
            cmd.append("-p")
        if self.chk_cache.isChecked():
            cmd.append("--cache")
        if self.chk_dry.isChecked():
            cmd.append("--dry-run")

        # Env overrides for API + force UTF-8 stdout/stderr on Windows
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        model = self.ed_model.text().strip()
        if model:
            env["GPT_MODEL"] = model
        env["GPT_TEMPERATURE"] = str(self.ds_temp.value())
        env["GPT_MAX_TOKENS"] = str(self.sp_max_tokens.value())

        # Launch using SubprocessController (QProcess)
        self.thread, self.worker = _start_qprocess(cmd, env, self, self.log.append, self.on_finished)
        self.btn_run.setEnabled(False)

    def on_finished(self, code: int) -> None:
        self.log.append("stdout", f"Process finished with exit code {code}")
        self.btn_run.setEnabled(True)
        if self.thread:
            self.thread.quit()
            self.thread.wait()
            self.thread = None
            self.worker = None
        # Trigger refresh of PromptsTab after outline generation
        if code == 0:
            try:
                win = self.window()
                tw = win.centralWidget()
                for i in range(tw.count()):
                    w = tw.widget(i)
                    if hasattr(w, 'refresh_topics'):
                        w.refresh_topics()
            except Exception:
                pass

    def load_prefs(self) -> bool:
        s = self.settings
        cfg = s.value("outline/config_path", None)
        if not cfg:
            return False
        # Basic paths/options
        self.txt_config.setText(str(cfg))
        self.txt_template.setText(str(s.value("outline/template_path", self.txt_template.text())))
        vlevel = int(s.value("outline/verbosity", 0))
        self.cmb_verbose.setCurrentIndex(max(0, min(2, vlevel)))
        self.chk_parallel.setChecked(bool(int(s.value("outline/parallel", 0))))
        self.chk_cache.setChecked(bool(int(s.value("outline/cache", 1))))
        self.chk_dry.setChecked(bool(int(s.value("outline/dry", 0))))
        # Languages
        langs_str = str(s.value("outline/langs", "CS,EN,DE,ES,FR"))
        langs = [x for x in langs_str.split(",") if x]
        for code, w in self.chk.items():
            w.setChecked(code in langs)
        # Overrides
        self.ed_topic.setText(str(s.value("outline/topic", self.ed_topic.text())))
        episodes_auto = bool(int(s.value("outline/episodes_auto", 1)))
        self.chk_ep_auto.setChecked(episodes_auto)
        self.spn_episodes.setValue(int(s.value("outline/episodes", self.spn_episodes.value())))
        self.spn_ep_minutes.setValue(int(s.value("outline/episode_minutes", self.spn_ep_minutes.value())))
        self.spn_ecr_min.setValue(int(s.value("outline/ecr_min", self.spn_ecr_min.value())))
        self.spn_ecr_max.setValue(int(s.value("outline/ecr_max", self.spn_ecr_max.value())))
        self.spn_msp_per.setValue(int(s.value("outline/msp_per", self.spn_msp_per.value())))
        self.spn_msp_max_words.setValue(int(s.value("outline/msp_max_words", self.spn_msp_max_words.value())))
        self.spn_desc_max_sent.setValue(int(s.value("outline/desc_max_sent", self.spn_desc_max_sent.value())))
        self.spn_scs_min.setValue(int(s.value("outline/scs_min", self.spn_scs_min.value())))
        self.spn_scs_max.setValue(int(s.value("outline/scs_max", self.spn_scs_max.value())))
        ordering = str(s.value("outline/ordering", self.cmb_ordering.currentText()))
        idx = ["chronological", "thematic"].index(ordering) if ordering in ["chronological", "thematic"] else 0
        self.cmb_ordering.setCurrentIndex(idx)
        self.spn_tol_min.setValue(int(s.value("outline/tol_min", self.spn_tol_min.value())))
        self.spn_tol_max.setValue(int(s.value("outline/tol_max", self.spn_tol_max.value())))
        self.spn_src_min.setValue(int(s.value("outline/src_min", self.spn_src_min.value())))
        self.spn_src_max.setValue(int(s.value("outline/src_max", self.spn_src_max.value())))
        src_fmt = str(s.value("outline/src_fmt", self.cmb_src_format.currentText()))
        fmt_idx = ["name-only", "with-url", "full-citation"].index(src_fmt) if src_fmt in ["name-only", "with-url", "full-citation"] else 0
        self.cmb_src_format.setCurrentIndex(fmt_idx)
        self.chk_no_dialogue.setChecked(bool(int(s.value("outline/fac_no_dialogue", int(self.chk_no_dialogue.isChecked())))))
        self.chk_no_spec.setChecked(bool(int(s.value("outline/fac_no_spec", int(self.chk_no_spec.isChecked())))))
        self.chk_consensus.setChecked(bool(int(s.value("outline/fac_consensus", int(self.chk_consensus.isChecked())))))
        self.chk_disputes.setChecked(bool(int(s.value("outline/fac_disputes", int(self.chk_disputes.isChecked())))))
        # API
        self.ed_model.setText(str(s.value("outline/api_model", self.ed_model.text())))
        try:
            self.ds_temp.setValue(float(s.value("outline/api_temp", self.ds_temp.value())))
        except Exception:
            pass
        self.sp_max_tokens.setValue(int(s.value("outline/api_max_tokens", self.sp_max_tokens.value())))
        return True

    def save_prefs(self) -> None:
        s = self.settings
        s.setValue("outline/config_path", self.txt_config.text().strip())
        s.setValue("outline/template_path", self.txt_template.text().strip())
        s.setValue("outline/verbosity", int(self.cmb_verbose.currentIndex()))
        s.setValue("outline/parallel", int(self.chk_parallel.isChecked()))
        s.setValue("outline/cache", int(self.chk_cache.isChecked()))
        s.setValue("outline/dry", int(self.chk_dry.isChecked()))
        langs = ",".join([c for c, w in self.chk.items() if w.isChecked()])
        s.setValue("outline/langs", langs)
        # Overrides
        s.setValue("outline/topic", self.ed_topic.text().strip())
        s.setValue("outline/episodes_auto", int(self.chk_ep_auto.isChecked()))
        s.setValue("outline/episodes", int(self.spn_episodes.value()))
        s.setValue("outline/episode_minutes", int(self.spn_ep_minutes.value()))
        s.setValue("outline/ecr_min", int(self.spn_ecr_min.value()))
        s.setValue("outline/ecr_max", int(self.spn_ecr_max.value()))
        s.setValue("outline/msp_per", int(self.spn_msp_per.value()))
        s.setValue("outline/msp_max_words", int(self.spn_msp_max_words.value()))
        s.setValue("outline/desc_max_sent", int(self.spn_desc_max_sent.value()))
        s.setValue("outline/scs_min", int(self.spn_scs_min.value()))
        s.setValue("outline/scs_max", int(self.spn_scs_max.value()))
        s.setValue("outline/ordering", self.cmb_ordering.currentText())
        s.setValue("outline/tol_min", int(self.spn_tol_min.value()))
        s.setValue("outline/tol_max", int(self.spn_tol_max.value()))
        s.setValue("outline/src_min", int(self.spn_src_min.value()))
        s.setValue("outline/src_max", int(self.spn_src_max.value()))
        s.setValue("outline/src_fmt", self.cmb_src_format.currentText())
        s.setValue("outline/fac_no_dialogue", int(self.chk_no_dialogue.isChecked()))
        s.setValue("outline/fac_no_spec", int(self.chk_no_spec.isChecked()))
        s.setValue("outline/fac_consensus", int(self.chk_consensus.isChecked()))
        s.setValue("outline/fac_disputes", int(self.chk_disputes.isChecked()))
        # API
        s.setValue("outline/api_model", self.ed_model.text().strip())
        s.setValue("outline/api_temp", float(self.ds_temp.value()))
        s.setValue("outline/api_max_tokens", int(self.sp_max_tokens.value()))


class PromptsTab(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.thread: Optional[QThread] = None
        self.worker: Optional[AsyncRunner] = None
        self.settings = QSettings()

        v = QVBoxLayout(self)

        # Topic + Language selection
        row = QHBoxLayout()
        self.cmb_topic = QComboBox(self)
        self.btn_refresh = QPushButton("Refresh", self)
        self.btn_refresh.clicked.connect(self.refresh_topics)
        row.addWidget(QLabel("Topic:", self))
        row.addWidget(self.cmb_topic, 1)
        row.addWidget(self.btn_refresh)
        v.addLayout(row)

        row2 = QHBoxLayout()
        self.cmb_lang = QComboBox(self)
        row2.addWidget(QLabel("Language:", self))
        row2.addWidget(self.cmb_lang)
        v.addLayout(row2)

        # Roots info (read-only transparency)
        self.lbl_outline_root = QLabel("", self)
        self.lbl_prompts_root = QLabel("", self)
        v.addWidget(self.lbl_outline_root)
        v.addWidget(self.lbl_prompts_root)

        # Verbosity
        rowv = QHBoxLayout()
        self.cmb_verbose = QComboBox(self)
        self.cmb_verbose.addItem("Warning (default)", 0)
        self.cmb_verbose.addItem("Info (-v)", 1)
        self.cmb_verbose.addItem("Debug (-vv)", 2)
        rowv.addWidget(QLabel("Verbosity:", self))
        rowv.addWidget(self.cmb_verbose)
        v.addLayout(rowv)

        self.chk_overwrite = QCheckBox("Overwrite existing (-y)", self)
        self.chk_overwrite.setChecked(True)
        v.addWidget(self.chk_overwrite)

        self.btn_run = QPushButton("Run B_core/generate_prompts.py", self)
        self.btn_run.clicked.connect(self.run_prompts)
        v.addWidget(self.btn_run)

        self.log = LogPane()
        v.addWidget(self.log)

                # Init
        self.cmb_topic.currentTextChanged.connect(self.on_topic_changed)
        self.refresh_topics()
        self.load_prefs()
        self.on_topic_changed(self.cmb_topic.currentText())

    def osnova_root(self) -> str:
        """Delegate to PathResolver for outline/osnova root."""
        return str(PathResolver.osnova_root())

    def prompts_root(self) -> str:
        """Delegate to PathResolver for prompts root."""
        return str(PathResolver.prompts_root())

    def refresh_topics(self) -> None:
        self.log.append('stdout', '=== PromptsTab.refresh_topics() START ===')

        # PromptsTab needs to show ALL topics from outline root (not just those with prompts)
        # because users need to select a topic to GENERATE prompts for it
        root = self.osnova_root()
        self.log.append('stdout', f'Scanning outline root for available topics: {root}')
        self.log.append('stdout', f'Path exists: {os.path.isdir(root)}')

        topics: list[str] = []
        try:
            if not os.path.isdir(root):
                self.log.append('stderr', f'Outline root does not exist: {root}')
            else:
                entries = os.listdir(root)
                self.log.append('stdout', f'Found {len(entries)} entries in outline root')
                for name in entries:
                    full = os.path.join(root, name)
                    self.log.append('stdout', f'  Checking: {name} -> isdir={os.path.isdir(full)}')
                    if os.path.isdir(full):
                        topics.append(name)
                        self.log.append('stdout', f'    ✓ Added topic: {name}')
        except Exception as e:
            self.log.append("stderr", f"Error scanning outline root: {e}")
            topics = []

        topics.sort()
        # Filter out hidden folders (starting with dot)
        topics = [t for t in topics if not t.startswith('.')]
        self.log.append('stdout', f'Final topics list ({len(topics)}): {topics}')
        self.log.append('stdout', '=== PromptsTab.refresh_topics() END ===')

        cur = self.cmb_topic.currentText()
        self.cmb_topic.blockSignals(True)
        self.cmb_topic.clear()
        self.cmb_topic.addItems(topics)
        self.cmb_topic.blockSignals(False)
        # restore if possible
        if cur and cur in topics:
            self.cmb_topic.setCurrentText(cur)
        # Update roots info labels
        self.lbl_outline_root.setText(f"Outline root: {self.osnova_root()}")
        self.lbl_prompts_root.setText(f"Prompts root: {self.prompts_root()}")

    def on_topic_changed(self, topic: str) -> None:
        # Recompute languages for selected topic
        self.cmb_lang.clear()
        if not topic:
            return
        root = self.osnova_root()
        topic_dir = os.path.join(root, topic)
        langs = []
        for code in ["CS", "EN", "DE", "ES", "FR"]:
            # Support both unified and legacy outline layouts:
            # unified: <root>/<topic>/<code>/osnova.json
            # legacy project-structure: <root>/<topic>/<code>/01_outline/osnova.json
            p1 = os.path.join(topic_dir, code, "osnova.json")
            p2 = os.path.join(topic_dir, code, "01_outline", "osnova.json")
            if os.path.isfile(p1) or os.path.isfile(p2):
                langs.append(code)
        self.cmb_lang.addItems(langs)
        # ensure a current selection exists
        if langs and self.cmb_lang.currentIndex() < 0:
            self.cmb_lang.setCurrentIndex(0)
        # restore saved language if matches
        saved = self.settings.value("prompts/lang", "")
        if saved and saved in langs:
            self.cmb_lang.setCurrentText(str(saved))

    def run_prompts(self) -> None:
        topic = self.cmb_topic.currentText().strip()
        lang = self.cmb_lang.currentText().strip()
        if not topic or not lang:
            self.log.append("stderr", "Vyberte Topic a Language.")
            return

        # Save prefs
        self.save_prefs()

        script = os.path.join("B_core", "generate_prompts.py")
        if not os.path.isfile(script):
            self.log.append("stderr", f"Nenalezen skript: {script}")
            return
        cmd: list[str] = [sys.executable, script, "--topic", topic, "--language", lang]
        # Verbosity
        vlevel = int(self.cmb_verbose.currentData() or 0)
        cmd.extend(["-v"] * vlevel)
        if self.chk_overwrite.isChecked():
            cmd.append("-y")

        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        # Ensure NC_OUTPUTS_ROOT is set so generate_prompts.py finds the right paths
        nc_root = os.environ.get("NC_OUTPUTS_ROOT")
        if not nc_root:
            # Use parent of osnova_root as NC_OUTPUTS_ROOT
            nc_root = str(Path(self.osnova_root()).parent)
            env["NC_OUTPUTS_ROOT"] = nc_root
            self.log.append("stdout", f"Setting NC_OUTPUTS_ROOT={nc_root}")

        # Launch using SubprocessController (QProcess)
        self.thread, self.worker = _start_qprocess(cmd, env, self, self.log.append, self.on_finished)
        self.btn_run.setEnabled(False)

    def on_finished(self, code: int) -> None:
        self.log.append("stdout", f"Process finished with exit code {code}")
        self.btn_run.setEnabled(True)
        if self.thread:
            self.thread.quit()
            self.thread.wait()
            self.thread = None
            self.worker = None

    def load_prefs(self) -> None:
        s = self.settings
        topic = s.value("prompts/topic", "")
        if topic:
            idx = self.cmb_topic.findText(str(topic))
            if idx >= 0:
                self.cmb_topic.setCurrentIndex(idx)
        lang = s.value("prompts/lang", "")
        if lang:
            idx2 = self.cmb_lang.findText(str(lang))
            if idx2 >= 0:
                self.cmb_lang.setCurrentIndex(idx2)
        self.chk_overwrite.setChecked(bool(int(s.value("prompts/overwrite", 1))))
        try:
            self.cmb_verbose.setCurrentIndex(int(s.value("prompts/verbosity", 0)))
        except Exception:
            pass

    def save_prefs(self) -> None:
        s = self.settings
        s.setValue("prompts/topic", self.cmb_topic.currentText().strip())
        s.setValue("prompts/lang", self.cmb_lang.currentText().strip())
        s.setValue("prompts/overwrite", int(self.chk_overwrite.isChecked()))
        s.setValue("prompts/verbosity", int(self.cmb_verbose.currentIndex()))


    def set_narration_index(self, index: dict) -> None:
        """Set cached narration index (from rescan) and refresh UI."""
        try:
            self._narration_index = index
            try:
                self.refresh_topics()
            except Exception:
                pass
        except Exception:
            pass

class NarrationTab(QWidget):
    # Delegate methods using shared utils (kept as class methods for backward compatibility)
    def _resolve_topic_dir(self, root: str | Path, topic_display: str) -> str:
        try:
            p = resolve_topic_dir(Path(root), topic_display)
            return str(p)
        except Exception:
            try:
                return os.path.join(str(root), topic_display)
            except Exception:
                return str(Path(root) / topic_display)

    def _normalize_name(self, s: str) -> str:
        try:
            return normalize_name(s)
        except Exception:
            return s.lower().strip()

    def _find_index_topic(self, topic_display: str, index: dict | None) -> str | None:
        try:
            return find_topic_in_index(topic_display, index)
        except Exception:
            return None

    # NarrationTab

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.thread: Optional[QThread] = None
        self.worker: Optional[SubprocessController] = None
        self.settings = QSettings()

        v = QVBoxLayout(self)

        row = QHBoxLayout()
        self.cmb_topic = QComboBox(self)
        self.btn_refresh = QPushButton("Refresh", self)
        self.btn_refresh.clicked.connect(self.refresh_topics)
        row.addWidget(QLabel("Topic:", self))
        row.addWidget(self.cmb_topic, 1)
        row.addWidget(self.btn_refresh)
        v.addLayout(row)

        row2 = QHBoxLayout()
        self.cmb_lang = QComboBox(self)
        row2.addWidget(QLabel("Language:", self))
        row2.addWidget(self.cmb_lang)
        v.addLayout(row2)

        # Roots info (read-only transparency) - similar to PromptsTab
        self.lbl_outline_root = QLabel("", self)
        self.lbl_prompts_root = QLabel("", self)
        v.addWidget(self.lbl_outline_root)
        v.addWidget(self.lbl_prompts_root)

        # Episodes list (selectable)
        self.lst_episodes = QListWidget(self)
        self.lst_episodes.setSelectionMode(QListWidget.SingleSelection)
        self.lst_episodes.itemSelectionChanged.connect(self._on_episode_selected)
        self.lst_episodes.itemDoubleClicked.connect(lambda it: self.run_claude_episode())
        v.addWidget(self.lst_episodes)

        # Prompts list for selected episode
        self.lbl_prompts = QLabel("Prompts:", self)
        v.addWidget(self.lbl_prompts)
        self.lst_prompts = QListWidget(self)
        self.lst_prompts.setSelectionMode(QListWidget.SingleSelection)
        self.lst_prompts.itemSelectionChanged.connect(self._on_prompt_selected)
        self.lst_prompts.itemDoubleClicked.connect(lambda it: self.run_selected_prompt())
        v.addWidget(self.lst_prompts)

        # Segments list for selected episode (to track generation status)
        self.lbl_segments = QLabel("Segments:", self)
        v.addWidget(self.lbl_segments)
        self.lst_segments = QListWidget(self)
        self.lst_segments.setSelectionMode(QListWidget.SingleSelection)
        v.addWidget(self.lst_segments)

        # Initialize state
        self._status_map: dict[str, str] = {}
        self._prompt_index: Optional[dict] = None
        self._narration_index: Optional[dict] = None

        opts = QHBoxLayout()
        self.chk_retry_failed = QCheckBox("Retry failed only", self)
        opts.addWidget(self.chk_retry_failed)
        self.btn_run = QPushButton("Send selected episode to Claude", self)
        self.btn_run.clicked.connect(self.run_claude_episode)
        self.btn_run.setEnabled(False)
        opts.addWidget(self.btn_run)

        # Button to send single selected prompt
        self.btn_send_prompt = QPushButton("Send selected prompt to Claude", self)
        self.btn_send_prompt.clicked.connect(self.run_selected_prompt)
        self.btn_send_prompt.setEnabled(False)
        opts.addWidget(self.btn_send_prompt)

        # Status label
        self.lbl_selected = QLabel("No episode selected", self)
        opts.addWidget(self.lbl_selected)
        # PID label
        self.lbl_pid = QLabel("", self)
        opts.addWidget(self.lbl_pid)
        self.btn_cancel = QPushButton("Cancel", self)
        self.btn_cancel.clicked.connect(self.cancel)
        opts.addWidget(self.btn_cancel)
        self.btn_kill = QPushButton("Terminate", self)
        self.btn_kill.clicked.connect(self.kill)
        opts.addWidget(self.btn_kill)
        self.btn_open = QPushButton("Open output folder", self)
        self.btn_open.clicked.connect(self.open_output_folder)
        opts.addWidget(self.btn_open)
        v.addLayout(opts)

        self.log = LogPane()
        v.addWidget(self.log)

        self.cmb_topic.currentTextChanged.connect(self.on_topic_changed)
        self.cmb_lang.currentTextChanged.connect(lambda: self.populate_episodes())
        self.refresh_topics()

        # After loading topics, trigger language/episode population for first topic
        # Use QTimer to ensure it runs after UI is fully initialized
        if self.cmb_topic.count() > 0:
            QTimer.singleShot(0, lambda: self.on_topic_changed(self.cmb_topic.currentText()))
    def _normalize_name(self, s: str) -> str:
        """Normalize name for case/diacritics-insensitive comparison (delegates to utils)."""
        return normalize_name(s)

    def _resolve_topic_dir(self, root, topic_display: str) -> str:
        """Resolve topic directory with case-insensitive matching (delegates to utils)."""
        from pathlib import Path
        return str(resolve_topic_dir(Path(root), topic_display))

    def _find_index_topic(self, topic_display: str, index) -> str | None:
        """Find topic in index with normalized matching (delegates to utils)."""
        return find_topic_in_index(topic_display, index)

    def prompts_root(self) -> str:
        pr_root = os.environ.get("PROMPTS_OUTPUT_ROOT")
        if pr_root:
            return pr_root
        nc_root = os.environ.get("NC_OUTPUTS_ROOT")
        if nc_root:
            return os.path.join(nc_root, "prompts")
        repo_root = os.getcwd()
        return os.path.join(repo_root, "outputs", "prompts")

    def osnova_root(self) -> str:
        # Unified outputs structure detection with sensible fallbacks (for label only)
        out_root = os.environ.get("OUTLINE_OUTPUT_ROOT")
        if out_root:
            return out_root
        nc_root = os.environ.get("NC_OUTPUTS_ROOT")
        if nc_root:
            return os.path.join(nc_root, "outline")
        repo_root = os.getcwd()
        unified = os.path.join(repo_root, "outputs", "outline")
        legacy = os.path.join(repo_root, "outline-generator", "output")
        default_out = os.path.join(repo_root, "output")
        if os.path.isdir(unified):
            return unified
        if os.path.isdir(legacy):
            return legacy
        if os.path.isdir(default_out):
            return default_out
        return unified

    def narration_root(self) -> str:
        nr = os.environ.get("NARRATION_OUTPUT_ROOT")
        if nr:
            return nr
        nc_root = os.environ.get("NC_OUTPUTS_ROOT")
        if nc_root:
            return os.path.join(nc_root, "narration")
        # fallback to repository-level outputs/narration
        repo_root = os.getcwd()
        return os.path.join(repo_root, "outputs", "narration")

    def refresh_topics(self) -> None:
        # Try to load cached prompts index for faster topic listing
        try:
            tmp_dir = os.path.join('studio_gui', '.tmp')
            from .fs_index import load_index
            idx = load_index(os.path.join(tmp_dir, 'prompts_index.json'))
        except Exception:
            idx = None

        topics: list[str] = []
        if idx:
            try:
                topics = sorted(idx.get('topics', {}).keys())
            except Exception:
                topics = []
        # If no prompts topics found, fall back to outline topics to at least enable language selection
        if not topics:
            root = self.osnova_root()
            try:
                for name in os.listdir(root):
                    full = os.path.join(root, name)
                    if os.path.isdir(full):
                        topics.append(name)
            except Exception as e:
                self.log.append("stderr", f"Nelze načíst témata z {root}: {e}")
                topics = []
            topics.sort()

        cur = self.cmb_topic.currentText()
        self.cmb_topic.blockSignals(True)
        self.cmb_topic.clear()
        self.cmb_topic.addItems(topics)
        self.cmb_topic.blockSignals(False)

        # Auto-select first topic if nothing was selected before, or restore previous
        if topics:
            if cur and cur in topics:
                self.cmb_topic.setCurrentText(cur)
            elif not cur:
                self.cmb_topic.setCurrentIndex(0)

        # Update roots info labels
        self.lbl_outline_root.setText(f"Outline root: {self.osnova_root()}")
        self.lbl_prompts_root.setText(f"Prompts root: {self.prompts_root()}")

    def _force_populate_from_index(self, topic: str) -> bool:
        """Best-effort immediate UI population from narration index without relying on signals.
        Returns True if it populated languages (and episodes), else False."""
        try:
            idx = getattr(self, '_narration_index', None)
            key = self._find_index_topic(topic, idx)
            if not key:
                return False
            langs = list(idx.get('topics', {}).get(key, {}).get('languages', {}).keys())
            langs = sorted(set([str(l).upper() for l in langs]))
            self.cmb_lang.clear()
            self.cmb_lang.addItems(langs)
            if langs:
                # log and select first language
                try:
                    self.log.append('stdout', f'Languages resolved (index): {langs}')
                except Exception:
                    pass
                self.cmb_lang.setCurrentIndex(0)
                # populate episodes directly from index
                eps_map = idx['topics'][key]['languages'][langs[0]].get('episodes', {})
                self.lst_episodes.clear()
                for ep in sorted(eps_map.keys()):
                    segs = eps_map[ep].get('segments', []) or []
                    generated = len(segs)
                    # no total here; we set as PARTIAL/PENDING depending on generated
                    status = 'PENDING' if generated == 0 else 'PARTIAL'
                    item_text = f"{ep}: {generated}/? -> {status}"
                    item = QListWidgetItem(item_text)
                    item.setData(Qt.UserRole, ep)
                    self.lst_episodes.addItem(item)
                return True
            return False
        except Exception:
            return False

    def on_topic_changed(self, topic: str) -> None:
        self.cmb_lang.clear()
        if not topic:
            return
        try:
            self.log.append('stdout', f'on_topic_changed: {topic}')
        except Exception:
            pass
        debug_lines = [f"on_topic_changed: topic={topic}"]
        langs: list[str] = []
        # 1) Prefer using cached indexes if available (prompts index or narration index)
        try:
            # try exact topic key in prompts index
            if getattr(self, '_prompt_index', None):
                try:
                    key = self._find_index_topic(topic, self._prompt_index)
                    if key:
                        langs = list(self._prompt_index['topics'].get(key, {}).get('languages', {}).keys())
                        debug_lines.append(f"languages from prompts index (key={key}): {langs}")
                    else:
                        debug_lines.append(f"topic not found in prompts index: {topic}")
                except Exception as e:
                    debug_lines.append(f"error reading prompts index: {e}")
            # try narration index using normalized match
            if not langs and getattr(self, '_narration_index', None):
                try:
                    key = self._find_index_topic(topic, self._narration_index)
                    if key:
                        langs = list(self._narration_index['topics'].get(key, {}).get('languages', {}).keys())
                        debug_lines.append(f"languages from narration index (key={key}): {langs}")
                    else:
                        debug_lines.append(f"topic not found in narration index: {topic}")
                except Exception as e:
                    debug_lines.append(f"error reading narration index: {e}")
        except Exception as e:
            debug_lines.append(f"index lookup error: {e}")
            langs = []

        # 2) If still empty, fall back to filesystem checks (prompts -> narration -> outline)
        if not langs:
            allowed = {"CS", "EN", "DE", "ES", "FR"}
            base_prompts = self._resolve_topic_dir(self.prompts_root(), topic)
            debug_lines.append(f"resolved prompts dir: {base_prompts}")
            try:
                for name in os.listdir(base_prompts):
                    if os.path.isdir(os.path.join(base_prompts, name)) and name.upper() in allowed:
                        langs.append(name.upper())
                debug_lines.append(f"prompts detected langs: {langs}")
            except Exception as e:
                debug_lines.append(f"prompts listing error: {e}")

        if not langs:
            base_narr = self._resolve_topic_dir(self.narration_root(), topic)
            debug_lines.append(f"resolved narration dir: {base_narr}")
            try:
                for name in os.listdir(base_narr):
                    if os.path.isdir(os.path.join(base_narr, name)) and name.upper() in {"CS","EN","DE","ES","FR"}:
                        langs.append(name.upper())
                debug_lines.append(f"narration detected langs: {langs}")
            except Exception as e:
                debug_lines.append(f"narration listing error: {e}")

        if not langs:
            root_outline = self.osnova_root()
            topic_dir = os.path.join(root_outline, topic)
            debug_lines.append(f"resolved outline dir: {topic_dir}")
            try:
                for code in ["CS", "EN", "DE", "ES", "FR"]:
                    p1 = os.path.join(topic_dir, code, "osnova.json")
                    p2 = os.path.join(topic_dir, code, "01_outline", "osnova.json")
                    if os.path.isfile(p1) or os.path.isfile(p2):
                        langs.append(code)
                debug_lines.append(f"outline detected langs: {langs}")
            except Exception as e:
                debug_lines.append(f"outline listing error: {e}")

        langs = sorted(set([l.upper() for l in langs]))
        self.cmb_lang.addItems(langs)
        # ensure a current selection exists for downstream code (populate_episodes uses currentText)
        if langs and self.cmb_lang.currentIndex() < 0:
            self.cmb_lang.setCurrentIndex(0)
        # immediate UI feedback
        try:
            if langs:
                self.log.append('stdout', f'Languages resolved: {langs}')
            else:
                self.log.append('stderr', 'No languages found for selected topic')
        except Exception:
            pass

        # persist debug to disk
        try:
            tmpd = os.path.join('studio_gui', '.tmp')
            os.makedirs(tmpd, exist_ok=True)
            dbg_path = os.path.join(tmpd, 'narration_debug.log')
            with open(dbg_path, 'a', encoding='utf-8') as df:
                df.write(f"--- on_topic_changed at {datetime.now(timezone.utc).isoformat()}\n")
                for ln in debug_lines:
                    df.write(ln + "\n")
        except Exception:
            pass

        # Build mapping of uppercase lang code -> actual folder name for case-insensitive resolution
        try:
            base_topic_dir = self._resolve_topic_dir(self.prompts_root(), topic) if os.path.isdir(self._resolve_topic_dir(self.prompts_root(), topic)) else self._resolve_topic_dir(self.narration_root(), topic)
            folder_map = {}
            try:
                for fn in os.listdir(base_topic_dir):
                    folder_map[fn.upper()] = fn
            except Exception:
                folder_map = {}
            self._lang_folder_map = folder_map
        except Exception:
            self._lang_folder_map = {}

        # after language list changed -> repopulate indexes and episodes using fs_index
        try:
            from .fs_index import scan_prompts_root, discover_prompts_root, scan_narration_root, discover_narration_root
            try:
                self._prompt_index = scan_prompts_root(discover_prompts_root())
            except Exception:
                self._prompt_index = None
            try:
                self._narration_index = scan_narration_root(discover_narration_root())
            except Exception:
                self._narration_index = None
        except Exception:
            self._prompt_index = None
            self._narration_index = None
        self.populate_episodes()

    def populate_episodes(self) -> None:
        topic = self.cmb_topic.currentText().strip()
        lang = self.cmb_lang.currentText().strip()
        # fallback: if currentText is empty but items exist, use the first item
        if not lang and self.cmb_lang.count() > 0:
            try:
                lang = self.cmb_lang.itemText(0).strip()
            except Exception:
                lang = ''
        self.lst_episodes.clear()
        self.lbl_selected.setText("No episode selected")
        if not topic or not lang:
            return

                # DEBUG: Log what we're searching for
        try:
            self.log.append('stdout', f'[DEBUG] populate_episodes: topic={topic}, lang={lang}')
        except Exception:
            pass

        if not topic or not lang:
            try:
                self.log.append('stderr', f'[DEBUG] Missing topic or lang, aborting')
            except Exception:
                pass
            return

        base_topic_dir = self._resolve_topic_dir(self.narration_root(), topic)
        base = os.path.join(base_topic_dir, lang)

        # DEBUG: Log the path we're scanning
        try:
            self.log.append('stdout', f'[DEBUG] Scanning for episodes in: {base}')
            self.log.append('stdout', f'[DEBUG] Path exists: {os.path.isdir(base)}')
        except Exception:
            pass

        try:
            eps = [d for d in os.listdir(base) if os.path.isdir(os.path.join(base, d)) and d.startswith('ep')]
            # DEBUG: Log what we found
            try:
                self.log.append('stdout', f'[DEBUG] Found {len(eps)} episodes: {eps}')
            except Exception:
                pass
        except Exception as e:
            # DEBUG: Log the error
            try:
                self.log.append('stderr', f'[DEBUG] Error listing episodes: {e}')
            except Exception:
                pass
            eps = []

        eps.sort()
        for ep in eps:
            item = QListWidgetItem(ep)
            item.setData(Qt.UserRole, ep)
            self.lst_episodes.addItem(item)

        # DEBUG: Log final count
        try:
            self.log.append('stdout', f'[DEBUG] Added {len(eps)} episodes to list')
        except Exception:
            pass

        # Prefer using precomputed indexes if available
        prompt_idx = getattr(self, '_prompt_index', None)
        narr_idx = getattr(self, '_narration_index', None)

        # 1) Try narration index first (most accurate for existing outputs)
        try:
            if narr_idx:
                key = self._find_index_topic(topic, narr_idx)
                if key and narr_idx.get('topics', {}).get(key, {}).get('languages', {}).get(lang):
                    eps_map = narr_idx['topics'][key]['languages'][lang]['episodes']
                    eps = sorted(eps_map.keys())
                    for ep in eps:
                        segs = eps_map[ep].get('segments', []) or []
                        generated = len(segs)
                        # try to detect expected total from prompts index if available
                        total = 0
                        try:
                            if prompt_idx and prompt_idx.get('topics', {}).get(topic, {}).get('languages', {}).get(lang, {}).get('episodes', {}).get(ep):
                                total = int(prompt_idx['topics'][topic]['languages'][lang]['episodes'][ep].get('expected_segments', 0) or 0)
                        except Exception:
                            total = 0
                        status = 'OK' if total and generated == total else ('PENDING' if generated == 0 else 'PARTIAL')
                        item_text = f"{ep}: {generated}/{total} -> {status}"
                        item = QListWidgetItem(item_text)
                        item.setData(Qt.UserRole, ep)
                        self.lst_episodes.addItem(item)
                    return
        except Exception:
            pass

        # 2) Then try prompts index (with normalized key lookup)
        if prompt_idx:
            try:
                key = self._find_index_topic(topic, prompt_idx)
                if key and prompt_idx.get('topics', {}).get(key, {}).get('languages', {}).get(lang):
                    eps_map = prompt_idx['topics'][key]['languages'][lang]['episodes']
                eps = sorted(eps_map.keys())
                for ep in eps:
                    info = eps_map[ep]
                    generated = 0
                    try:
                        generated = sum(1 for p in info.get('prompts', []) if p['name'].lower().startswith('msp_') and p['name'].lower().endswith('.txt') and 'execution' in p['name'].lower())
                    except Exception:
                        generated = 0
                    total = int(info.get('expected_segments', 0) or 0)
                    if narr_idx:
                        try:
                            narr_key = self._find_index_topic(topic, narr_idx)
                            if narr_key and narr_idx.get('topics', {}).get(narr_key, {}).get('languages', {}).get(lang, {}).get('episodes', {}).get(ep):
                                segs = narr_idx['topics'][narr_key]['languages'][lang]['episodes'][ep].get('segments', [])
                                generated = len(segs)
                        except Exception:
                            pass
                    status = 'OK' if total and generated == total else ('PENDING' if generated == 0 else 'PARTIAL')
                    item_text = f"{ep}: {generated}/{total} -> {status}"
                    item = QListWidgetItem(item_text)
                    item.setData(Qt.UserRole, ep)
                    self.lst_episodes.addItem(item)
                return
            except Exception:
                pass

        # 3) Fallback: scan filesystem (prefer narration root if exists)
        base_topic_dir = self._resolve_topic_dir(self.narration_root(), topic)
        # resolve actual folder name case-insensitively
        try:
            actual_lang = None
            for fn in os.listdir(base_topic_dir):
                if fn.upper() == lang.upper():
                    actual_lang = fn
                    break
            if not actual_lang:
                actual_lang = lang
        except Exception:
            actual_lang = lang
        base = os.path.join(base_topic_dir, actual_lang)
        eps = []
        try:
            eps = [d for d in os.listdir(base) if os.path.isdir(os.path.join(base, d)) and d.startswith('ep')]
        except Exception as e:
            # try prompts meta as last resort
            try:
                base_meta = os.path.join(self.prompts_root(), topic, lang)
                eps = [d for d in os.listdir(base_meta) if os.path.isdir(os.path.join(base_meta, d)) and d.startswith('ep')]
            except Exception as e2:
                self.lst_episodes.addItem(f"ERROR: Nelze načíst epizody: {e or e2}")
                return
        eps.sort()
        for ep in eps:
            # total from prompts meta if available
            total = 0
            try:
                meta = os.path.join(self.prompts_root(), topic, lang, ep, 'meta', 'episode_context.json')
                if os.path.isfile(meta):
                    with open(meta, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        total = len(data.get('segments', []))
            except Exception:
                total = 0
            # generated from narration outputs
            generated = 0
            try:
                out_dir = os.path.join(base, ep)
                if os.path.isdir(out_dir):
                    for name in os.listdir(out_dir):
                        if name.startswith('segment_') and name.endswith('.txt'):
                            generated += 1
            except Exception:
                generated = 0
            status = 'OK' if total and generated == total else ('PENDING' if generated == 0 else 'PARTIAL')
            item_text = f"{ep}: {generated}/{total} -> {status}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, ep)
            self.lst_episodes.addItem(item)


    def run_claude(self) -> None:
        # legacy: not used for single-episode send
        self.log.append('stderr', 'Use "Send selected episode to Claude" to send a specific episode.')

    def _on_episode_selected(self) -> None:
        items = self.lst_episodes.selectedItems()
        # clear prompts selection and list
        self.lst_prompts.clear()
        self.btn_send_prompt.setEnabled(False)
        if not items:
            self.lbl_selected.setText("No episode selected")
            self.btn_run.setEnabled(False)
            return
        ep = items[0].data(Qt.UserRole)
        if not ep:
            ep = items[0].text()
        self.lbl_selected.setText(f"Selected: {ep}")
        self.btn_run.setEnabled(True)
        # populate prompts list for this episode
        topic = self.cmb_topic.currentText().strip()
        lang = self.cmb_lang.currentText().strip()
        self.populate_prompts_for_episode(topic, lang, ep)
        # populate segments list using narration index if available
        self.lst_segments.clear()
        self._status_map.clear()
        narr_idx = getattr(self, '_narration_index', None)
        if narr_idx and narr_idx.get('topics', {}).get(topic, {}).get('languages', {}).get(lang, {}).get('episodes', {}).get(ep):
            try:
                segs = narr_idx['topics'][topic]['languages'][lang]['episodes'][ep].get('segments', [])
                for s in segs:
                    name = s.get('name')
                    it = QListWidgetItem(f"{name} - PENDING")
                    it.setData(Qt.UserRole, s.get('fullpath'))
                    self.lst_segments.addItem(it)
                    self._status_map[name] = 'PENDING'
                return
            except Exception:
                pass
        # fallback to filesystem
        seg_dir = os.path.join(self._resolve_topic_dir(self.narration_root(), topic), lang, ep)
        try:
            names = [n for n in os.listdir(seg_dir) if n.endswith('.txt')]
        except Exception:
            names = []
        names.sort()
        for n in names:
            it = QListWidgetItem(f"{n} - PENDING")
            it.setData(Qt.UserRole, os.path.join(seg_dir, n))
            self.lst_segments.addItem(it)
            self._status_map[n] = 'PENDING'

    def _update_pid_label(self) -> None:
        """Update PID label s process ID"""
        try:
            if self.worker and hasattr(self.worker, 'pid'):
                pid = self.worker.pid()
                if pid:
                    self.lbl_pid.setText(f"PID: {pid}")
                else:
                    self.lbl_pid.setText("")
        except Exception:
            self.lbl_pid.setText("")

    def populate_prompts_for_episode(self, topic: str, lang: str, ep: str) -> None:
        """Fill self.lst_prompts with prompt files for given topic/lang/ep."""
        self.lst_prompts.clear()
        if not topic or not lang or not ep:
            return
        # prefer index
        try:
            if getattr(self, '_prompt_index', None):
                # Use normalized key lookup for prompts index
                key = self._find_index_topic(topic, self._prompt_index)
                if key and self._prompt_index.get('topics', {}).get(key, {}).get('languages', {}).get(lang, {}).get('episodes', {}).get(ep):
                    pf = self._prompt_index['topics'][key]['languages'][lang]['episodes'][ep]['prompts']
                for p in pf:
                    item = QListWidgetItem(p['name'])
                    item.setData(Qt.UserRole, p['fullpath'])
                    self.lst_prompts.addItem(item)
                return
        except Exception:
            pass
        # fallback: filesystem scan
        prompts_dir = os.path.join(self.prompts_root(), topic, lang, ep, 'prompts')
        try:
            for name in sorted(os.listdir(prompts_dir)):
                fp = os.path.join(prompts_dir, name)
                if os.path.isfile(fp):
                    item = QListWidgetItem(name)
                    item.setData(Qt.UserRole, fp)
                    self.lst_prompts.addItem(item)
        except Exception:
            return

    def _on_prompt_selected(self) -> None:
        items = self.lst_prompts.selectedItems()
        if not items:
            # leave episode selection label as is
            self.btn_send_prompt.setEnabled(False)
            return
        prompt_name = items[0].text()
        self.btn_send_prompt.setEnabled(True)
        # show which prompt selected in status label
        self.lbl_selected.setText(f"Selected: {prompt_name}")

    def run_selected_prompt(self) -> None:
        items = self.lst_prompts.selectedItems()
        if not items:
            self.log.append('stderr', 'Vyberte prompt ze seznamu.')
            return
        prompt_path = items[0].data(Qt.UserRole)
        if not prompt_path:
            self.log.append('stderr', 'Nelze získat cestu k promptu')
            return
        runner = os.path.join('claude_generator', 'runner_cli.py')
        if not os.path.isfile(runner):
            self.log.append('stderr', f'Nenalezen runner: {runner}')
            return
        cmd = [sys.executable, runner, '--prompt-file', prompt_path]
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        self.thread, self.worker = _start_qprocess(cmd, env, self, self.log.append, self.on_finished)
        QTimer.singleShot(250, self._update_pid_label)
        self.btn_send_prompt.setEnabled(False)

    def run_claude_episode(self) -> None:
        # Decide whether to send whole episode or specific prompt(s)
        items = self.lst_episodes.selectedItems()
        if not items:
            self.log.append('stderr', 'Vyberte epizodu ze seznamu.')
            return
        ep = items[0].data(Qt.UserRole)
        if not ep:
            ep = items[0].text()
        topic = self.cmb_topic.currentText().strip()
        lang = self.cmb_lang.currentText().strip()
        if not topic or not lang:
            self.log.append('stderr', 'Topic nebo Language neni nastaven')
            return
        runner = os.path.join('claude_generator', 'runner_cli.py')
        if not os.path.isfile(runner):
            self.log.append('stderr', f'Nenalezen runner: {runner}')
            return

        # If we have an index, find prompt files for this episode and ask user (simple choose: execution files)
        prompt_files = []
        try:
            if getattr(self, '_prompt_index', None):
                key = self._find_index_topic(topic, self._prompt_index)
                if key and self._prompt_index.get('topics', {}).get(key, {}).get('languages', {}).get(lang, {}).get('episodes', {}).get(ep):
                    pf = self._prompt_index['topics'][key]['languages'][lang]['episodes'][ep]['prompts']
                    # choose execution prompts by default
                    prompt_files = [p['fullpath'] for p in pf if 'execution' in p['name'].lower()]
        except Exception:
            prompt_files = []

        # Confirm with user before sending whole episode (may be expensive)
        # Estimate time based on expected segment count (from index) or number of execution prompts
        avg_sec_per_segment = 30  # heuristic: average seconds per segment generation
        n = None
        try:
            if getattr(self, '_prompt_index', None):
                key = self._find_index_topic(topic, self._prompt_index)
                if key and self._prompt_index.get('topics', {}).get(key, {}).get('languages', {}).get(lang, {}).get('episodes', {}).get(ep):
                    n = int(self._prompt_index['topics'][key]['languages'][lang]['episodes'][ep].get('expected_segments', 0) or 0)
            if not n and prompt_files:
                n = len(prompt_files)
        except Exception:
            n = len(prompt_files) if prompt_files else None

        if n and n > 0:
            est_seconds = n * avg_sec_per_segment
            mins = est_seconds // 60
            secs = est_seconds % 60
            time_str = f"~{mins}m {secs}s" if mins else f"~{secs}s"
            msg = (
                f"Send whole episode {ep} to Claude? This will process {n} segments (~{time_str}) "
                "and call external APIs (may consume credits). Continue?"
            )
        else:
            msg = (
                f"Send whole episode {ep} to Claude? This will call external APIs (may consume credits). "
                "Estimated time unknown. Continue?"
            )

        resp = QMessageBox.question(self, "Confirm send episode", msg, QMessageBox.Yes | QMessageBox.No)
        if resp != QMessageBox.Yes:
            self.log.append('stdout', 'User cancelled sending episode')
            return
        # send all execution prompts for the episode (or fallback)
        cmd = [sys.executable, runner, '--topic', topic, '--language', lang, '--episodes', ep]
        if self.chk_retry_failed.isChecked():
            cmd.append('--retry-failed')

        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        # Launch using SubprocessController
        self.thread, self.worker = _start_qprocess(cmd, env, self, self.log.append, self.on_finished)
        QTimer.singleShot(250, self._update_pid_label)
        self.btn_run.setEnabled(False)

    def cancel(self) -> None:
        if self.worker:
            self.worker.terminate()
            self.log.append('stdout', 'Sent terminate to process')

    def kill(self) -> None:
        if self.worker:
            self.worker.kill()
            self.log.append('stdout', 'Sent kill to process')

    def on_finished(self, code: int) -> None:
        self.log.append('stdout', f'Process finished with exit code {code}')
        self.btn_run.setEnabled(True)
        # refresh status
        self.populate_episodes()
        if self.thread:
            self.thread.quit()
            self.thread.wait()
            self.thread = None
            self.worker = None

    def open_output_folder(self) -> None:
        """Otevře output složku pro vybranou epizodu, nebo postproc root"""
        topic = self.cmb_topic.currentText().strip()
        lang = self.cmb_lang.currentText().strip()
        items = self.lst_episodes.selectedItems()

        if items and topic and lang:
            # Open specific episode folder
            ep = items[0].text()
            path = Path(self.postproc_root()) / topic / lang / ep
        elif topic and lang:
            # Open topic/lang folder
            path = Path(self.postproc_root()) / topic / lang
        else:
            # Open postproc root
            path = Path(self.postproc_root())

        if not path.exists():
            QMessageBox.warning(
                self,
                "Složka nenalezena",
                f"Output složka neexistuje:\n{path}\n\nSpusť nejprve zpracování epizody."
            )
            return

        try:
            if sys.platform.startswith('win'):
                os.startfile(str(path))
            elif sys.platform == 'darwin':
                import subprocess
                subprocess.Popen(['open', str(path)])
            else:
                import subprocess
                subprocess.Popen(['xdg-open', str(path)])

            self.log.append('stdout', f'Opened folder: {path}')
        except Exception as e:
            self.log.append('stderr', f'Cannot open folder: {e}')
            QMessageBox.critical(self, "Chyba", f"Nelze otevřít složku:\n{e}")


    def set_prompt_index(self, index: dict) -> None:
        """Set cached prompts index (from rescan) and refresh UI."""
        try:
            self._prompt_index = index
            try:
                self.refresh_topics()
            except Exception:
                pass
        except Exception:
            pass

    def set_narration_index(self, index: dict) -> None:
        """Set cached narration index (from rescan) and refresh UI."""
        try:
            self._narration_index = index
            try:
                self.refresh_topics()
            except Exception:
                pass
        except Exception:
            pass

class PostProcessTab(QWidget):
    def _resolve_topic_dir(self, root: str | Path, topic_display: str) -> str:
        try:
            p = resolve_topic_dir(Path(root), topic_display)
            return str(p)
        except Exception:
            try:
                return os.path.join(str(root), topic_display)
            except Exception:
                return str(Path(root) / topic_display)

    def _normalize_name(self, s: str) -> str:
        try:
            return normalize_name(s)
        except Exception:
            return s.lower().strip()

    def _find_index_topic(self, topic_display: str, index: dict | None) -> str | None:
        try:
            return find_topic_in_index(topic_display, index)
        except Exception:
            return None

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.thread: Optional[QThread] = None
        self.worker: Optional[SubprocessController] = None
        self.settings = QSettings()

        v = QVBoxLayout(self)

        # Top selectors
        row = QHBoxLayout()
        self.cmb_topic = QComboBox(self)
        self.btn_refresh = QPushButton("Refresh", self)
        self.btn_refresh.clicked.connect(self.refresh_topics)
        row.addWidget(QLabel("Topic:", self))
        row.addWidget(self.cmb_topic, 1)
        row.addWidget(self.btn_refresh)
        v.addLayout(row)

        row2 = QHBoxLayout()
        self.cmb_lang = QComboBox(self)
        row2.addWidget(QLabel("Language:", self))
        row2.addWidget(self.cmb_lang)
        v.addLayout(row2)

        # Episode controls and presets/rules
        top_opts = QHBoxLayout()
        self.btn_run_episode = QPushButton("Run episode (batch)", self)
        self.btn_run_episode.clicked.connect(self.run_episode)
        top_opts.addWidget(self.btn_run_episode)

        self.btn_run_selected = QPushButton("Run selected segments", self)
        self.btn_run_selected.clicked.connect(self.run_selected_segments)
        top_opts.addWidget(self.btn_run_selected)

        self.btn_retry_failed = QPushButton("Retry failed only", self)
        self.btn_retry_failed.clicked.connect(self.retry_failed_only)
        top_opts.addWidget(self.btn_retry_failed)

        # Episode-mode (merged) controls
        self.chk_use_gpt = QCheckBox("Use GPT (intro/transitions + grammar)", self)
        self.chk_use_gpt.setToolTip("Enable OpenAI-based intro & transitions and conservative grammar/splitting")
        top_opts.addWidget(self.chk_use_gpt)
        self.chk_prefer_existing = QCheckBox("Prefer existing merged", self)
        self.chk_prefer_existing.setChecked(True)
        top_opts.addWidget(self.chk_prefer_existing)
        self.chk_force_rebuild = QCheckBox("Force rebuild", self)
        top_opts.addWidget(self.chk_force_rebuild)
        self.chk_save_merged = QCheckBox("Save merged", self)
        self.chk_save_merged.setChecked(True)
        top_opts.addWidget(self.chk_save_merged)
        self.btn_run_episode_merged = QPushButton("Run episode (merged)", self)
        self.btn_run_episode_merged.setToolTip("Process whole episode via episode-mode: reuse or GPT, write episode_merged.txt and manifest")
        self.btn_run_episode_merged.clicked.connect(self.run_episode_merged)
        top_opts.addWidget(self.btn_run_episode_merged)

        # Preset selection
        self.cmb_preset = QComboBox(self)
        self.cmb_preset.addItems(["default", "minimal", "aggressive"])
        top_opts.addWidget(QLabel("Preset:"))
        top_opts.addWidget(self.cmb_preset)

        # Rules file picker
        self.ed_rules = QLineEdit("", self)
        btn_rules = QPushButton("Rules…", self)
        btn_rules.clicked.connect(self.pick_rules)
        top_opts.addWidget(self.ed_rules)
        top_opts.addWidget(btn_rules)

        # Concurrency
        self.spn_concurrency = QSpinBox(self)
        self.spn_concurrency.setRange(1, 16)
        self.spn_concurrency.setValue(3)
        top_opts.addWidget(QLabel("Concurrency:"))
        top_opts.addWidget(self.spn_concurrency)

        v.addLayout(top_opts)

        status_row = QWidget(self)
        sr_layout = QHBoxLayout(status_row)
        sr_layout.setContentsMargins(0,0,0,0)
        self.lbl_selected = QLabel("No episode selected", self)
        sr_layout.addWidget(self.lbl_selected)
        self.lbl_pid = QLabel("", self)
        sr_layout.addWidget(self.lbl_pid)
        v.addWidget(status_row)

        # Episodes and segments
        row3 = QHBoxLayout()
        self.lst_episodes = QListWidget(self)
        self.lst_episodes.setMaximumWidth(260)
        self.lst_episodes.itemSelectionChanged.connect(self._on_episode_selected)
        row3.addWidget(self.lst_episodes)

        # Segment list
        seg_col = QVBoxLayout()
        seg_hdr = QLabel("Segments:", self)
        seg_col.addWidget(seg_hdr)
        self.lst_segments = QListWidget(self)
        self.lst_segments.itemSelectionChanged.connect(self._on_segment_selected)
        seg_col.addWidget(self.lst_segments)

        btns_seg = QHBoxLayout()
        self.btn_preview = QPushButton("Preview selected", self)
        self.btn_preview.clicked.connect(self.preview_selected)
        btns_seg.addWidget(self.btn_preview)
        self.btn_apply = QPushButton("Apply (save)", self)
        self.btn_apply.clicked.connect(self.apply_current)
        btns_seg.addWidget(self.btn_apply)
        seg_col.addLayout(btns_seg)

        row3.addLayout(seg_col)
        v.addLayout(row3)

        # Split view: source / preview
        split_row = QHBoxLayout()
        left_col = QVBoxLayout()
        left_col.addWidget(QLabel("Source (narration):", self))
        self.src_view = QTextEdit(self)
        self.src_view.setReadOnly(True)
        left_col.addWidget(self.src_view)
        split_row.addLayout(left_col)

        right_col = QVBoxLayout()
        right_col.addWidget(QLabel("Post-processed preview (editable):", self))
        self.preview_view = QTextEdit(self)
        right_col.addWidget(self.preview_view)
        split_row.addLayout(right_col)

        v.addLayout(split_row)

        # Log and open folder
        bottom_row = QHBoxLayout()
        self.log = LogPane()
        bottom_row.addWidget(self.log, 3)
        right_bottom = QVBoxLayout()
        self.btn_open = QPushButton("Open output folder", self)
        self.btn_open.clicked.connect(self.open_output_folder)
        right_bottom.addWidget(self.btn_open)
        self.btn_open_merged = QPushButton("Open merged file", self)
        self.btn_open_merged.clicked.connect(self.open_merged_file)
        right_bottom.addWidget(self.btn_open_merged)
        self.btn_open_manifest = QPushButton("Open manifest.json", self)
        self.btn_open_manifest.clicked.connect(self.open_manifest)
        right_bottom.addWidget(self.btn_open_manifest)
        right_bottom.addStretch(1)
        bottom_row.addLayout(right_bottom, 1)
        v.addLayout(bottom_row)

        # state
        self._last_index = None
        self._current_source_path: Optional[str] = None
        self._last_dry_temp: Optional[str] = None
        self._status_map: dict[str, str] = {}
        self._queue: list[str] = []
        self._running: list[tuple[QThread, SubprocessController]] = []
        self._worker_to_path: dict[int, str] = {}

        self.cmb_topic.currentTextChanged.connect(self.on_topic_changed)
        self.refresh_topics()

    def _force_populate_from_index(self, topic: str) -> bool:
        """Best-effort immediate UI population from narration index without relying on signals.
        Returns True if it populated languages (and episodes), else False."""
        try:
            idx = getattr(self, '_narration_index', None)
            key = self._find_index_topic(topic, idx)
            if not key:
                return False
            langs = list(idx.get('topics', {}).get(key, {}).get('languages', {}).keys())
            langs = sorted(set([str(l).upper() for l in langs]))
            self.cmb_lang.clear()
            self.cmb_lang.addItems(langs)
            if langs:
                try:
                    self.log.append('stdout', f'Languages resolved (index): {langs}')
                except Exception:
                    pass
                self.cmb_lang.setCurrentIndex(0)
                # populate episodes via existing method (will scan FS)
                self.populate_episodes()
                return True
            return False
        except Exception:
            return False

    def pick_rules(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select rules JSON", os.getcwd(), "JSON files (*.json);;All files (*)")
        if path:
            self.ed_rules.setText(path)

    def narration_root(self) -> str:
        nr = os.environ.get("NARRATION_OUTPUT_ROOT")
        if nr:
            return nr
        nc_root = os.environ.get("NC_OUTPUTS_ROOT")
        if nc_root:
            return os.path.join(nc_root, "narration")
        # fallback
        return os.path.join(os.getcwd(), "outputs", "narration")

    def postproc_root(self) -> str:
        pr = os.environ.get("POSTPROC_OUTPUT_ROOT")
        if pr:
            return pr
        nc_root = os.environ.get("NC_OUTPUTS_ROOT")
        if nc_root:
            return os.path.join(nc_root, "postprocess")
        return os.path.join(os.getcwd(), "outputs", "postprocess")

    def prompts_root(self) -> str:
        pr_root = os.environ.get("PROMPTS_OUTPUT_ROOT")
        if pr_root:
            return pr_root
        nc_root = os.environ.get("NC_OUTPUTS_ROOT")
        if nc_root:
            return os.path.join(nc_root, "prompts")
        repo_root = os.getcwd()
        return os.path.join(repo_root, "outputs", "prompts")

    def osnova_root(self) -> str:
        out_root = os.environ.get("OUTLINE_OUTPUT_ROOT")
        if out_root:
            return out_root
        nc_root = os.environ.get("NC_OUTPUTS_ROOT")
        if nc_root:
            return os.path.join(nc_root, "outline")
        repo_root = os.getcwd()
        unified = os.path.join(repo_root, "outputs", "outline")
        legacy = os.path.join(repo_root, "outline-generator", "output")
        default_out = os.path.join(repo_root, "output")
        if os.path.isdir(unified):
            return unified
        if os.path.isdir(legacy):
            return legacy
        if os.path.isdir(default_out):
            return default_out
        return unified



    def refresh_topics(self) -> None:
        # Try to load cached narration index for faster topic listing
        try:
            tmp_dir = os.path.join('studio_gui', '.tmp')
            from .fs_index import load_index
            idx = load_index(os.path.join(tmp_dir, 'narration_index.json'))
        except Exception:
            idx = None

        topics: list[str] = []
        debug_lines = []
        if idx:
            try:
                topics = sorted(idx.get('topics', {}).keys())
                debug_lines.append(f"Loaded narration_index.json with {len(topics)} topics")
                # keep index available for later population
                try:
                    self._narration_index = idx
                except Exception:
                    pass
            except Exception:
                topics = []
                debug_lines.append("Failed to parse narration_index.json")
        else:
            root = self.narration_root()
            debug_lines.append(f"Using narration_root: {root}")
            try:
                entries = []
                for name in os.listdir(root):
                    full = os.path.join(root, name)
                    entries.append(name)
                    if os.path.isdir(full):
                        topics.append(name)
                debug_lines.append(f"narration_root exists: {os.path.isdir(root)}, entries_count: {len(entries)}")
            except Exception as e:
                self.log.append("stderr", f"Nelze načíst témata z {root}: {e}")
                debug_lines.append(f"listing error: {e}")
                topics = []
            topics.sort()

        # write debug info to disk for easier inspection
        try:
            tmpd = os.path.join('studio_gui', '.tmp')
            os.makedirs(tmpd, exist_ok=True)
            dbg_path = os.path.join(tmpd, 'narration_debug.log')
            from datetime import timezone
            with open(dbg_path, 'a', encoding='utf-8') as df:
                df.write(f"--- refresh_topics at {datetime.now(timezone.utc).isoformat()}\n")
                for ln in debug_lines:
                    df.write(ln + "\n")
        except Exception:
            pass

        cur = self.cmb_topic.currentText()
        self.cmb_topic.blockSignals(True)
        self.cmb_topic.clear()
        self.cmb_topic.addItems(topics)
        self.cmb_topic.blockSignals(False)
        # if previous selection still present, restore it
        if cur and cur in topics:
            self.cmb_topic.setCurrentText(cur)
            sel = cur
        else:
            # if nothing selected and topics exist, auto-select first to populate languages
            sel = topics[0] if topics else ""
            if sel:
                self.cmb_topic.setCurrentIndex(0)
        # Try immediate population from index to avoid relying on signals
        if sel:
            if self._force_populate_from_index(sel):
                return
        # Otherwise call handler with the actual selection (may be empty)
        try:
            self.on_topic_changed(sel)
        except Exception:
            try:
                self.on_topic_changed(self.cmb_topic.currentText())
            except Exception:
                pass

    def on_topic_changed(self, topic: str) -> None:
        self.cmb_lang.clear()
        if not topic:
            return

        # Prefer languages from prompts root (normalized topic mapping)
        langs: list[str] = []
        base_prompts = self._resolve_topic_dir(self.prompts_root(), topic)
        try:
            for name in os.listdir(base_prompts):
                if os.path.isdir(os.path.join(base_prompts, name)) and name in ["CS","EN","DE","ES","FR"]:
                    langs.append(name)
        except Exception:
            langs = []

        # Fallback to narration root if prompts not present
        if not langs:
            base = self._resolve_topic_dir(self.narration_root(), topic)
            try:
                for name in os.listdir(base):
                    if os.path.isdir(os.path.join(base, name)):
                        langs.append(name)
            except Exception:
                pass

        # Final fallback to outline root (detect languages by presence of osnova.json)
        if not langs:
            root_outline = self.osnova_root()
            topic_dir = os.path.join(root_outline, topic)
            for code in ["CS", "EN", "DE", "ES", "FR"]:
                p1 = os.path.join(topic_dir, code, "osnova.json")
                p2 = os.path.join(topic_dir, code, "01_outline", "osnova.json")
                if os.path.isfile(p1) or os.path.isfile(p2):
                    langs.append(code)

        langs = sorted(set(langs))
        self.cmb_lang.addItems(langs)
        if not langs:
            try:
                self.log.append('stderr', 'No languages found in prompts/narration/outline roots for the selected topic.')
            except Exception:
                pass

        # DEBUG: Na konci, když už jsou jazyky načtené!
        try:
            self.log.append('stdout', f'[DEBUG] on_topic_changed: calling populate_episodes()')
        except Exception:
            pass

        self.populate_episodes()  # ← JEN TOHLE JEDNO volání na úplném konci!

    def populate_episodes(self) -> None:
        topic = self.cmb_topic.currentText().strip()
        lang = self.cmb_lang.currentText().strip()
        if not lang and self.cmb_lang.count() > 0:
            try:
                lang = self.cmb_lang.itemText(0).strip()
            except Exception:
                lang = ''
        self.lst_episodes.clear()
        if not topic or not lang:
            return
        base_topic_dir = self._resolve_topic_dir(self.narration_root(), topic)
        base = os.path.join(base_topic_dir, lang)
        try:
            eps = [d for d in os.listdir(base) if os.path.isdir(os.path.join(base, d)) and d.startswith('ep')]
        except Exception:
            eps = []
        eps.sort()
        for ep in eps:
            item = QListWidgetItem(ep)
            self.lst_episodes.addItem(item)

    def _on_episode_selected(self) -> None:
        items = self.lst_episodes.selectedItems()
        self.lst_segments.clear()
        self._status_map.clear()
        if not items:
            return
        ep = items[0].text()
        topic = self.cmb_topic.currentText().strip()
        lang = self.cmb_lang.currentText().strip()
        seg_dir = os.path.join(self._resolve_topic_dir(self.narration_root(), topic), lang, ep)
        try:
            names = [n for n in os.listdir(seg_dir) if n.endswith('.txt')]
        except Exception:
            names = []
        names.sort()
        for n in names:
            it = QListWidgetItem(n)
            self.lst_segments.addItem(it)
            self._status_map[n] = 'PENDING'

    def _on_segment_selected(self) -> None:
        pass

    def preview_selected(self) -> None:
        pass

    def apply_current(self) -> None:
        pass

    def run_episode(self) -> None:
        pass

    def run_selected_segments(self) -> None:
        pass

    def retry_failed_only(self) -> None:
        pass

    def run_episode_merged(self) -> None:
        pass

    def open_output_folder(self) -> None:
        pass

    def open_merged_file(self) -> None:
        pass

    def open_manifest(self) -> None:
        pass


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("NightChronicles Studio")
        self.resize(1400, 900)

        tabs = QTabWidget(self)
        tabs.addTab(ProjectTab(self), "Project")
        tabs.addTab(OutlineTab(self), "Outline")
        tabs.addTab(PromptsTab(self), "Prompts")
        tabs.addTab(NarrationTab(self), "Narration")
        tabs.addTab(PostProcessTab(self), "PostProcess")

        self.setCentralWidget(tabs)


def main() -> None:
    _configure_logging(logging.INFO)
    QCoreApplication.setOrganizationName("NightChronicles")
    QCoreApplication.setApplicationName("NightChroniclesStudio")

    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
