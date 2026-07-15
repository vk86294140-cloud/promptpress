import subprocess
import sys


def run_cli(args, stdin=""):
    return subprocess.run(
        [sys.executable, "-m", "promptpress.cli", *args],
        input=stdin,
        capture_output=True,
        text=True,
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


def test_cli_version(capsys):
    import pytest

    from promptpress import __version__
    from promptpress.cli import main

    with pytest.raises(SystemExit) as e:
        main(["--version"])
    assert e.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_main_count_stdin_in_process(monkeypatch, capsys):
    from promptpress.cli import main

    monkeypatch.setattr("sys.stdin", __import__("io").StringIO("hello world"))
    rc = main(["count", "-"])
    assert rc == 0
    assert int(capsys.readouterr().out.strip()) > 0


def test_main_compress_file_roundtrip_in_process(tmp_path, capsys):
    from promptpress.cli import main

    src = tmp_path / "in.md"
    dst = tmp_path / "out.md"
    src.write_text("Some    spaced   text\n\n\n\nmore", encoding="utf-8")
    rc = main(["compress", str(src), "-o", str(dst), "--report"])
    assert rc == 0
    assert dst.read_text(encoding="utf-8")
    assert "tokens:" in capsys.readouterr().err


def test_main_unmet_budget_exit_code_in_process(tmp_path):
    from promptpress.cli import main

    src = tmp_path / "big.md"
    src.write_text("word " * 200, encoding="utf-8")
    rc = main(["compress", str(src), "--budget", "1", "-o", str(tmp_path / "out.md")])
    assert rc == 2
