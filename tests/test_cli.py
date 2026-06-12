import subprocess
import sys


def run_cli(args, stdin=""):
    return subprocess.run(
        [sys.executable, "-m", "promptpress.cli", *args],
        input=stdin, capture_output=True, text=True,
    )


def test_count_stdin():
    p = run_cli(["count", "-"], stdin="hello world this is a test")
    assert p.returncode == 0
    assert int(p.stdout.strip()) > 0


def test_compress_stdin_with_report():
    text = "The quick brown fox was really just very tired today. " * 30
    p = run_cli(["compress", "-", "--report"], stdin=text)
    assert p.returncode == 0
    assert len(p.stdout) < len(text)
    assert "tokens:" in p.stderr


def test_unmet_budget_exit_code():
    p = run_cli(["compress", "-", "--budget", "1"], stdin="word " * 200)
    assert p.returncode == 2


def test_file_roundtrip(tmp_path):
    src = tmp_path / "in.md"
    dst = tmp_path / "out.md"
    src.write_text("Some    spaced   text\n\n\n\nmore", encoding="utf-8")
    p = run_cli(["compress", str(src), "-o", str(dst)])
    assert p.returncode == 0
    assert dst.read_text(encoding="utf-8")
