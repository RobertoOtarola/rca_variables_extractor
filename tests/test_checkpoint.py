"""
test_checkpoint.py — Tests unitarios para checkpoint.py.
"""

import json
import pytest
from pathlib import Path

from checkpoint import Checkpoint


@pytest.fixture
def ckpt_path(tmp_path):
    """Retorna una ruta temporal para el archivo de checkpoint."""
    return tmp_path / "test_checkpoint.json"


class TestCheckpoint:
    def test_mark_ok(self, ckpt_path):
        ckpt = Checkpoint(ckpt_path)
        ckpt.mark_ok("test.pdf")
        assert ckpt.is_done("test.pdf") is True

    def test_mark_error_is_not_done(self, ckpt_path):
        ckpt = Checkpoint(ckpt_path)
        ckpt.mark_error("fail.pdf", "timeout")
        assert ckpt.is_done("fail.pdf") is False

    def test_pending_filters_done(self, ckpt_path):
        ckpt = Checkpoint(ckpt_path)
        files = [Path("a.pdf"), Path("b.pdf"), Path("c.pdf")]
        ckpt.mark_ok("a.pdf")
        ckpt.mark_error("b.pdf", "error")

        pending = ckpt.pending(files)
        names = [p.name for p in pending]
        assert "a.pdf" not in names  # ok → no pending
        assert "b.pdf" in names     # error → still pending
        assert "c.pdf" in names     # never processed → pending

    def test_summary(self, ckpt_path):
        ckpt = Checkpoint(ckpt_path)
        ckpt.mark_ok("a.pdf")
        ckpt.mark_ok("b.pdf")
        ckpt.mark_error("c.pdf", "fail")

        s = ckpt.summary()
        assert s["total"] == 3
        assert s["ok"] == 2
        assert s["error"] == 1

    def test_persists_across_instances(self, ckpt_path):
        ckpt1 = Checkpoint(ckpt_path)
        ckpt1.mark_ok("persist.pdf")

        ckpt2 = Checkpoint(ckpt_path)
        assert ckpt2.is_done("persist.pdf") is True

    def test_corrupt_checkpoint_resets(self, ckpt_path):
        ckpt_path.write_text("esto no es JSON", encoding="utf-8")
        ckpt = Checkpoint(ckpt_path)
        assert ckpt.is_done("anything.pdf") is False

    def test_empty_checkpoint(self, ckpt_path):
        ckpt = Checkpoint(ckpt_path)
        assert ckpt.summary() == {"total": 0, "ok": 0, "error": 0}
