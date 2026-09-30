from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

CODE_EXTENSIONS = (
    ".py", ".pyw", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rs", ".c", ".h",
    ".cc", ".cpp", ".hpp", ".cs", ".rb", ".php", ".swift", ".kt", ".kts", ".scala",
    ".sh", ".bash", ".ps1", ".sql", ".vue", ".svelte", ".dart", ".lua", ".r",
)

PROJECT_MARKERS = (
    ".git", "pyproject.toml", "package.json", "pnpm-lock.yaml", "yarn.lock",
    "cargo.toml", "go.mod", "pom.xml", "build.gradle", "settings.gradle",
    "cmakelists.txt", "makefile", "dockerfile", "compose.yml", "docker-compose.yml",
    "src", "tests", "test",
)

LANGUAGE_PATTERN = re.compile(
    r"(?i)(?:(?<![A-Za-z0-9])python|py(?:\s|$)|javascript|typescript|java(?:\s|$)|"
    r"golang|go(?:\s|$)|rust|c\+\+|c#|\.net|react|vue|svelte|angular|node\.?js|"
    r"django|flask|fastapi|spring(?:\s|$)|sql|postgres|mysql|sqlite|docker|"
    r"kubernetes|terraform|bash|powershell|regex|pytest|unittest)"
)

STRONG_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"```[A-Za-z0-9_+.-]*"),
    re.compile(r"(?im)^\s*(?:def|class|function|const|let|var|async|import|from|package)\s+\w+"),
    re.compile(
        r"(?i)\b(?:traceback|stack trace|segmentation fault|exception|syntaxerror|"
        r"typeerror|valueerror|nullpointer|panic:)\b"
    ),
    re.compile(
        r"(?i)\b(?:fix|debug|refactor|implement|write|add|update|test)\b.{0,40}"
        r"\b(?:code|function|class|api|endpoint|bug|script|module|component|test|"
        r"migration|repository|repo)\b"
    ),
    re.compile(
        r"(?:修复|调试|重构|实现|编写|新增|更新|测试).{0,20}"
        r"(?:代码|函数|类|接口|接口文档|脚本|模块|组件|测试|报错|异常|仓库|迁移)"
    ),
    re.compile(
        r"(?i)\b(?:git|npm|pnpm|yarn|pip|poetry|uv|pytest|cargo|go test|mvn|gradle)\b"
        r".{0,30}\b(?:status|diff|commit|branch|merge|rebase|push|pull|install|run|test)\b"
    ),
    re.compile(r"(?i)\b(?:pull request|code review|unit test|integration test)\b"),
    re.compile(r"(?i)(?:[A-Za-z]:[\\/]|\./|\.\./)[^\s]+?(?:" + "|".join(re.escape(ext) for ext in CODE_EXTENSIONS) + r")\b"),
    re.compile(
        r"(?i)\b(?:build|create|develop|design)\b.{0,40}"
        r"\b(?:api|endpoint|service|backend|frontend|component|module|function|"
        r"class|schema|database|migration|script)\b"
    ),
    re.compile(r"(?i)\b(?:optimize|tune)\b.{0,30}\b(?:sql|query|index|database|performance)\b"),
    re.compile(r"(?i)\b(?:panic|pytest|package\.json)\b"),
    re.compile(r"(?:接口|端点).{0,20}(?:单元测试|测试|用例)|(?:补|写).{0,12}(?:单元测试|测试用例)"),
)

MEDIUM_PATTERNS: tuple[re.Pattern[str], ...] = (
    LANGUAGE_PATTERN,
    re.compile(
        r"(?i)\b(?:compile|deploy|performance|database|terminal|command line|cli|"
        r"crawler|scraper|refactor|backend|frontend|full[- ]stack|devops|ci/cd|"
        r"repository|algorithm|data structure)\b"
    ),
    re.compile(r"(?:编译|部署|性能|数据库|命令行|爬虫|后端|前端|全栈|算法|数据结构|仓库|自动化)"),
)

EXPLICIT_CODING_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)\b(?:enter|enable|start|switch to)\s+(?:the\s+)?(?:coding|developer|programming)\s+mode\b"),
    re.compile(r"(?:进入|开启|切换到|启用)(?:编程|开发|编码)模式"),
)

EXPLICIT_NON_CODING_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)\b(?:exit|disable|stop|leave)\s+(?:the\s+)?(?:coding|developer|programming)\s+mode\b"),
    re.compile(r"(?:退出|关闭|停止|离开)(?:编程|开发|编码)模式"),
    re.compile(r"(?i)\b(?:non[- ]coding|general chat|writing mode)\b"),
    re.compile(r"(?:非编程模式|普通聊天模式|写作模式)"),
)

CONTINUATION_PATTERN = re.compile(r"(?i)^(?:继续|接着|然后|继续做|go on|continue|keep going|next)(?:吧|它|这个|一下)?[\s。！？!?]*$")


@dataclass(frozen=True)
class Classification:
    mode: str
    score: float
    evidence: tuple[str, ...]

    @property
    def is_coding(self) -> bool:
        return self.mode == "coding"


def _matches(patterns: Iterable[re.Pattern[str]], text: str) -> list[str]:
    hits: list[str] = []
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            hits.append(match.group(0)[:120])
    return hits


def _compile_extra(patterns: object) -> tuple[re.Pattern[str], ...]:
    if not isinstance(patterns, list):
        return ()
    compiled: list[re.Pattern[str]] = []
    for raw in patterns:
        if not isinstance(raw, str) or not raw.strip():
            continue
        try:
            compiled.append(re.compile(raw, re.IGNORECASE))
        except re.error:
            continue
    return tuple(compiled)


def _project_marker_hits(cwd: Path) -> list[str]:
    hits: list[str] = []
    for marker in PROJECT_MARKERS:
        if (cwd / marker).exists():
            hits.append(marker)
    return hits


def classify(
    prompt: str,
    *,
    recent_messages: list[str] | None = None,
    cwd: Path | None = None,
    classifier_config: dict[str, Any] | None = None,
) -> Classification:
    config = classifier_config or {}
    prompt = prompt or ""
    history = recent_messages or []
    cwd = (cwd or Path.cwd()).resolve()

    if _matches(EXPLICIT_NON_CODING_PATTERNS, prompt):
        return Classification("non_coding", -100.0, ("explicit non-coding request",))
    if _matches(EXPLICIT_CODING_PATTERNS, prompt):
        return Classification("coding", 100.0, ("explicit coding request",))

    extra_strong = _compile_extra(config.get("extra_strong_patterns"))
    extra_medium = _compile_extra(config.get("extra_medium_patterns"))

    strong_hits = _matches((*STRONG_PATTERNS, *extra_strong), prompt)
    medium_hits = _matches((*MEDIUM_PATTERNS, *extra_medium), prompt)
    marker_hits = _project_marker_hits(cwd)

    score = 0.0
    evidence: list[str] = []

    if strong_hits:
        score += 6.0
        evidence.extend(f"strong:{hit}" for hit in strong_hits[:4])
    if medium_hits:
        medium_score = min(4.5, len(medium_hits) * 1.5)
        score += medium_score
        evidence.extend(f"medium:{hit}" for hit in medium_hits[:4])
    if marker_hits:
        marker_score = min(2.0, len(marker_hits))
        score += marker_score
        evidence.extend(f"cwd:{hit}" for hit in marker_hits[:3])

    history_hits = [hit for message in history for hit in _matches(STRONG_PATTERNS, message)]
    history_medium = [hit for message in history for hit in _matches(MEDIUM_PATTERNS, message)]
    if history_hits:
        score += 2.0
        evidence.append(f"history-strong:{history_hits[0][:80]}")
        if CONTINUATION_PATTERN.fullmatch(prompt.strip()):
            score += 2.5
            evidence.append("history-continuation")
    elif history_medium:
        score += min(2.0, float(len(history_medium)))
        evidence.extend(f"history-medium:{hit}" for hit in history_medium[:2])

    threshold = float(config.get("threshold", 4.0))
    mode = "coding" if score >= threshold else "non_coding"
    if not evidence:
        evidence.append("default-non-coding")
    return Classification(mode, score, tuple(evidence))
