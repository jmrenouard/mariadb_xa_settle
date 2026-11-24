"""Executable tests for mariadb_xa_settle CLI, bash scripts, SQL templates, Mermaid, STE, and Diátaxis docs."""

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = REPO_ROOT / "docs"

LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)\n]+)\)")
FENCE_RE = re.compile(r"^(?P<indent>[ \t]*)(?P<ticks>`{3,}|~{3,})(?P<info>.*)$")
BOX_CHAR_RE = re.compile(r"[\u2500-\u257f▼▲◄►]")
FRENCH_MARKERS = re.compile(
    r"\b(?:procédure|tutoriel|démarrage|prérequis|vérification|"
    r"retour\s+arrière|utilisation|transaction\s+préparée)\b",
    re.IGNORECASE,
)
STE_BANNED = re.compile(
    r"(?:;|should\b|would\b|may\b|might\b|shall\b|"
    r"\b(?:don't|doesn't|isn't|aren't|won't|can't|let's)\b)",
    re.IGNORECASE,
)


def _iter_markdown() -> list[Path]:
    """Return all Markdown files in the repository excluding .git."""
    return sorted(p for p in REPO_ROOT.rglob("*.md") if ".git/" not in p.as_posix())


def _extract_fenced_blocks(text: str) -> list[dict[str, object]]:
    """Extract fenced code blocks with indentation and language tag metadata."""
    blocks: list[dict[str, object]] = []
    open_fence: dict[str, object] | None = None
    for idx, line in enumerate(text.splitlines(), start=1):
        match = FENCE_RE.match(line)
        if open_fence is None:
            if match:
                ticks = match.group("ticks")
                open_fence = {
                    "char": ticks[0],
                    "len": len(ticks),
                    "indent": match.group("indent"),
                    "info": match.group("info").strip().lower(),
                    "start_line": idx,
                    "lines": [],
                }
        else:
            if match and match.group("ticks")[0] == open_fence["char"] and len(match.group("ticks")) >= int(open_fence["len"]):
                if not match.group("info").strip():
                    open_fence["code"] = "\n".join(open_fence["lines"])  # type: ignore[arg-type]
                    blocks.append(open_fence)
                    open_fence = None
                    continue
            open_fence["lines"].append(line)  # type: ignore[union-attr]
    if open_fence is not None:
        raise AssertionError(f"Unclosed fenced code block at line {open_fence['start_line']}")
    return blocks


def _strip_code(text: str) -> str:
    """Return Markdown text outside fenced and inline code spans."""
    lines: list[str] = []
    in_fence = False
    fence_char = ""
    fence_len = 0
    for line in text.splitlines():
        match = FENCE_RE.match(line)
        if not in_fence:
            if match:
                in_fence = True
                fence_char = match.group("ticks")[0]
                fence_len = len(match.group("ticks"))
            else:
                lines.append(re.sub(r"`[^`]+`", "", line))
        else:
            if match and match.group("ticks")[0] == fence_char and len(match.group("ticks")) >= fence_len and not match.group("info").strip():
                in_fence = False
    return "\n".join(lines)


def _heading_slugs(text: str) -> set[str]:
    """Build GitHub-style heading anchors from Markdown outside code blocks."""
    slugs: set[str] = set()
    counts: dict[str, int] = {}
    for line in _strip_code(text).splitlines():
        match = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*$", line)
        if not match:
            continue
        raw = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", match.group(1).strip())
        slug = re.sub(r"[^a-z0-9\- ]+", "", raw.lower()).strip().replace(" ", "-")
        slug = re.sub(r"-{2,}", "-", slug)
        if not slug:
            continue
        seen = counts.get(slug, 0)
        counts[slug] = seen + 1
        slugs.add(slug if seen == 0 else f"{slug}-{seen}")
    return slugs


class TestMariaDbXaSettleDocsAndCli(unittest.TestCase):
    """Validate Diátaxis structure, STE rules, Mermaid, bash syntax, SQL templates, and CLI behavior."""

    def test_diataxis_structure_links_and_ste(self) -> None:
        required = [
            REPO_ROOT / "README.md",
            DOCS_DIR / "index.md",
            DOCS_DIR / "01-tutorials" / "index.md",
            DOCS_DIR / "01-tutorials" / "01-isolated-docker-xa-lab.md",
            DOCS_DIR / "02-how-to-guides" / "index.md",
            DOCS_DIR / "02-how-to-guides" / "settle-prepared-xa-transactions.md",
            DOCS_DIR / "03-reference" / "index.md",
            DOCS_DIR / "03-reference" / "cli-config-and-sql-templates.md",
            DOCS_DIR / "04-explanation" / "index.md",
            DOCS_DIR / "04-explanation" / "xa-two-phase-recovery-architecture.md",
        ]
        for path in required:
            self.assertTrue(path.is_file(), f"Missing doc: {path}")

        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertNotIn("$1--rollback_all", readme)
        self.assertNotIn("commiting", readme)
        self.assertNotIn("uncommited", readme)

        for md_file in _iter_markdown():
            content = md_file.read_text(encoding="utf-8")
            plain = _strip_code(content)
            self.assertIsNone(FRENCH_MARKERS.search(plain), f"French marker found in {md_file}")
            for link in LINK_RE.findall(plain):
                if link.startswith(("http://", "https://", "mailto:")):
                    continue
                target_str, _, anchor = link.partition("#")
                target_path = md_file if not target_str else (md_file.parent / target_str).resolve()
                self.assertTrue(target_path.exists(), f"Broken link '{link}' in {md_file}")
                if anchor and target_path.is_file() and target_path.suffix == ".md":
                    slugs = _heading_slugs(target_path.read_text(encoding="utf-8"))
                    self.assertIn(anchor, slugs, f"Broken anchor '#{anchor}' in {md_file}")

        for howto in sorted((DOCS_DIR / "02-how-to-guides").glob("*.md")):
            plain = _strip_code(howto.read_text(encoding="utf-8"))
            self.assertIsNone(STE_BANNED.search(plain), f"ASD-STE100 banned pattern in {howto}")

    def test_mermaid_and_zero_ascii_diagrams(self) -> None:
        mermaid_total = 0
        for md_file in _iter_markdown():
            content = md_file.read_text(encoding="utf-8")
            for block in _extract_fenced_blocks(content):
                code = str(block["code"])
                info = str(block["info"])
                if info == "mermaid":
                    mermaid_total += 1
                    self.assertEqual(block["indent"], "", f"Indented mermaid fence in {md_file}")
                    first_line = next((ln.strip() for ln in code.splitlines() if ln.strip()), "")
                    self.assertTrue(
                        first_line.startswith(("flowchart ", "graph ", "sequenceDiagram", "stateDiagram-v2")),
                        f"Unsupported mermaid diagram header '{first_line}' in {md_file}",
                    )
                elif info in {"", "text", "plaintext", "ascii"}:
                    self.assertNotIn("-->", code, f"ASCII arrow found in {md_file}")
                    self.assertNotIn("graph ", code, f"Untagged mermaid diagram in {md_file}")
                    self.assertIsNone(BOX_CHAR_RE.search(code), f"Box-drawing art in {md_file}")

        self.assertGreaterEqual(mermaid_total, 4)

    def test_sql_templates_cnf_and_vsn_integrity(self) -> None:
        # Preserve vsn.sh untouched per upstream DO NOT EDIT notice.
        vsn = (REPO_ROOT / "vsn.sh").read_text(encoding="utf-8")
        self.assertIn("# DO NOT EDIT THIS SCRIPT", vsn)
        self.assertIn("SCRIPT_VERSION='1.0'", vsn)

        cnf = (REPO_ROOT / "xa_settle.cnf").read_text(encoding="utf-8")
        self.assertIn("[mariadb_xa_settle]", cnf)

        setup_sql = (REPO_ROOT / "SQL" / "TEST_SETUP.sql").read_text(encoding="utf-8")
        commit_sql = (REPO_ROOT / "SQL" / "XA_COMMIT.sql").read_text(encoding="utf-8")
        rollback_sql = (REPO_ROOT / "SQL" / "XA_ROLLBACK.sql").read_text(encoding="utf-8")
        self.assertIn("xa start '$ATR1', '$ATR2', $ATR3;", setup_sql)
        self.assertIn("xa prepare '$ATR1', '$ATR2', $ATR3;", setup_sql)
        self.assertIn("xa commit $TRX;", commit_sql)
        self.assertIn("xa rollback $TRX;", rollback_sql)

    def test_bash_syntax_and_cli_behavior_with_mocked_mariadb(self) -> None:
        if os.name == "nt" or not shutil.which("bash"):
            return

        sh_files = sorted(REPO_ROOT.glob("*.sh"))
        self.assertEqual([p.name for p in sh_files], ["cleanup_test_xa_schema.sh", "mariadb_xa_settle.sh", "setup_test_xa_schema.sh", "vsn.sh"])
        for sh_file in sh_files:
            res = subprocess.run(["bash", "-n", str(sh_file)], capture_output=True, text=True, timeout=15)
            self.assertEqual(res.returncode, 0, f"bash -n failed on {sh_file}: {res.stderr}")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            bin_dir = tmp / "bin"
            bin_dir.mkdir()
            sql_log = tmp / "executed_sql.log"

            # Fake mariadb client recording executed SQL and returning 2 prepared XIDs.
            fake_mariadb = bin_dir / "mariadb"
            fake_mariadb.write_text(
                "\n".join(
                    [
                        "#!/usr/bin/env bash",
                        "args=\"$*\"",
                        "if [[ \"$args\" == *\"select user()\"* ]]; then",
                        "  echo \"root@localhost\"",
                        "  exit 0",
                        "fi",
                        "if [[ \"$args\" == *\"xa recover format='SQL'\"* ]]; then",
                        "  if [[ \"$args\" == *\"-ABNe\"* ]]; then",
                        "    printf \"1\\t27\\t25\\t'aaa','bbb',101\\n1\\t27\\t25\\t'ccc','ddd',102\\n\"",
                        "  else",
                        "    echo \"+----------+----+----+-------------------+\"",
                        "    echo \"| formatID | ... | data |\"",
                        "  fi",
                        "  exit 0",
                        "fi",
                        f"printf '%s\\n' \"$args\" >> '{sql_log}'",
                        "exit 0",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            fake_defaults = bin_dir / "my_print_defaults"
            fake_defaults.write_text("#!/usr/bin/env bash\necho ''\n", encoding="utf-8")
            fake_mariadb.chmod(fake_mariadb.stat().st_mode | stat.S_IXUSR)
            fake_defaults.chmod(fake_defaults.stat().st_mode | stat.S_IXUSR)

            env_with_mocks = dict(os.environ)
            env_with_mocks["PATH"] = f"{bin_dir}:{env_with_mocks.get('PATH', '')}"

            # 1. --help works even with empty PATH (no mariadb binary needed).
            env_no_db = dict(os.environ)
            env_no_db["PATH"] = "/usr/bin:/bin"
            help_res = subprocess.run(
                ["bash", str(REPO_ROOT / "mariadb_xa_settle.sh"), "--help"],
                env=env_no_db,
                capture_output=True,
                text=True,
                timeout=15,
            )
            self.assertEqual(help_res.returncode, 0, help_res.stderr)
            self.assertIn("Script version 1.0", help_res.stdout)
            self.assertIn("--pause", help_res.stdout)

            # 2. --rollback_all --pause 0 runs both XA ROLLBACK queries cleanly via envsubst.
            rb_res = subprocess.run(
                ["bash", str(REPO_ROOT / "mariadb_xa_settle.sh"), "--rollback_all", "--pause", "0"],
                env=env_with_mocks,
                capture_output=True,
                text=True,
                timeout=15,
            )
            self.assertEqual(rb_res.returncode, 0, rb_res.stderr)
            self.assertIn("Rollback of 2 XA transactions completed.", rb_res.stdout)
            log_text = sql_log.read_text(encoding="utf-8")
            self.assertIn("xa rollback 'aaa','bbb',101;", log_text)
            self.assertIn("xa rollback 'ccc','ddd',102;", log_text)

            # 3. --pause 0 --commit_all works in reversed flag order too.
            sql_log.unlink()
            cm_res = subprocess.run(
                ["bash", str(REPO_ROOT / "mariadb_xa_settle.sh"), "--pause", "0", "--commit_all"],
                env=env_with_mocks,
                capture_output=True,
                text=True,
                timeout=15,
            )
            self.assertEqual(cm_res.returncode, 0, cm_res.stderr)
            self.assertIn("Commit of 2 XA transactions completed.", cm_res.stdout)
            log_text2 = sql_log.read_text(encoding="utf-8")
            self.assertIn("xa commit 'aaa','bbb',101;", log_text2)
            self.assertIn("xa commit 'ccc','ddd',102;", log_text2)

            # 4. Interactive uppercase 'C' confirmation executes; 'n' aborts cleanly.
            sql_log.unlink()
            int_yes = subprocess.run(
                ["bash", str(REPO_ROOT / "mariadb_xa_settle.sh"), "--interactive", "--commit_all"],
                input="C\n",
                env=env_with_mocks,
                capture_output=True,
                text=True,
                timeout=15,
            )
            self.assertEqual(int_yes.returncode, 0, int_yes.stderr)
            self.assertIn("Commit of 2 XA transactions completed.", int_yes.stdout)

            sql_log.unlink()
            int_no = subprocess.run(
                ["bash", str(REPO_ROOT / "mariadb_xa_settle.sh"), "--interactive", "--rollback_all"],
                input="n\n",
                env=env_with_mocks,
                capture_output=True,
                text=True,
                timeout=15,
            )
            self.assertEqual(int_no.returncode, 0, int_no.stderr)
            self.assertIn("SCRIPT NOT RUN.", int_no.stdout)
            self.assertFalse(sql_log.exists())

            # 5. Reject non-numeric --pause and conflicting action flags.
            bad_pause = subprocess.run(
                ["bash", str(REPO_ROOT / "mariadb_xa_settle.sh"), "--rollback_all", "--pause", "abc"],
                env=env_with_mocks,
                capture_output=True,
                text=True,
                timeout=15,
            )
            self.assertNotEqual(bad_pause.returncode, 0)
            self.assertIn("non-negative numeric argument", bad_pause.stderr)

            conflict = subprocess.run(
                ["bash", str(REPO_ROOT / "mariadb_xa_settle.sh"), "--commit_all", "--rollback_all"],
                env=env_with_mocks,
                capture_output=True,
                text=True,
                timeout=15,
            )
            self.assertNotEqual(conflict.returncode, 0)
            self.assertIn("Choose only one", conflict.stderr)


if __name__ == "__main__":
    unittest.main()
