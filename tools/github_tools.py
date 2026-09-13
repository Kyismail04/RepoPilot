import base64
import os
from urllib.parse import quote, urlparse

import requests


GITHUB_API_URL = "https://api.github.com"

MAX_TREE_FILES = 80
MAX_SAMPLED_FILES = 5
MAX_FILE_CHARACTERS = 2500
MAX_TOTAL_CODE_CHARACTERS = 10000


class GitHubAPIError(Exception):
    def __init__(
        self,
        status_code: int,
        message: str,
    ):
        super().__init__(message)

        self.status_code = status_code
        self.message = message


def _parse_github_url(repo_url: str):
    repo_url = repo_url.strip()

    parsed = urlparse(repo_url)

    if parsed.hostname not in {
        "github.com",
        "www.github.com",
    }:
        raise ValueError(
            "Geçerli bir GitHub repository URL'si gir."
        )

    parts = [
        part
        for part in parsed.path.split("/")
        if part
    ]

    if len(parts) < 2:
        raise ValueError(
            "GitHub repository URL'si owner/repository formatında olmalıdır."
        )

    owner = parts[0]
    repo = parts[1]

    if repo.endswith(".git"):
        repo = repo[:-4]

    return owner, repo


def _get_headers(
    access_token: str | None = None,
):
    token = (
        access_token
        or os.getenv("GITHUB_TOKEN")
    )

    headers = {
        "Accept":
            "application/vnd.github+json",

        "X-GitHub-Api-Version":
            "2022-11-28",

        "User-Agent":
            "RepoPilot",
    }

    if token:
        headers["Authorization"] = (
            f"Bearer {token}"
        )

    return headers


def _github_get(
    url: str,
    params=None,
    access_token: str | None = None,
):
    try:
        response = requests.get(
            url,
            headers=_get_headers(
                access_token
            ),
            params=params,
            timeout=25,
        )

    except requests.RequestException as exc:
        raise GitHubAPIError(
            503,
            (
                "GitHub API ile bağlantı "
                "kurulamadı."
            ),
        ) from exc


    if response.status_code == 404:
        raise GitHubAPIError(
            404,
            (
                "Repository veya istenen "
                "GitHub kaynağı bulunamadı."
            ),
        )


    if response.status_code == 401:
        raise GitHubAPIError(
            401,
            (
                "GitHub kimlik doğrulaması "
                "başarısız."
            ),
        )


    if response.status_code == 403:
        remaining = response.headers.get(
            "X-RateLimit-Remaining"
        )

        if remaining == "0":
            message = (
                "GitHub API rate limit "
                "sınırına ulaşıldı."
            )
        else:
            message = (
                "GitHub bu repository için "
                "erişimi reddetti."
            )

        raise GitHubAPIError(
            403,
            message,
        )


    if not response.ok:
        raise GitHubAPIError(
            response.status_code,
            (
                "GitHub API isteği başarısız "
                f"oldu: {response.status_code}"
            ),
        )


    try:
        return response.json()

    except ValueError as exc:
        raise GitHubAPIError(
            502,
            (
                "GitHub geçerli bir JSON "
                "cevabı döndürmedi."
            ),
        ) from exc


def _should_ignore_file(
    path: str,
):
    lower = path.lower()

    ignored_directories = (
        "node_modules/",
        ".git/",
        ".github/",
        ".venv/",
        "venv/",
        "env/",
        "__pycache__/",
        "dist/",
        "build/",
        "coverage/",
        ".next/",
        ".idea/",
        ".vscode/",
        "vendor/",
        "target/",
    )

    if any(
        directory in lower
        for directory in ignored_directories
    ):
        return True


    ignored_extensions = (
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".svg",
        ".ico",
        ".webp",

        ".mp3",
        ".wav",
        ".mp4",
        ".mov",
        ".avi",

        ".zip",
        ".rar",
        ".7z",
        ".tar",
        ".gz",

        ".pdf",
        ".doc",
        ".docx",
        ".ppt",
        ".pptx",

        ".csv",
        ".tsv",
        ".xls",
        ".xlsx",

        ".pkl",
        ".pickle",
        ".joblib",

        ".db",
        ".sqlite",
        ".sqlite3",

        ".exe",
        ".dll",
        ".so",
        ".dylib",

        ".woff",
        ".woff2",
        ".ttf",
        ".otf",
    )

    if lower.endswith(
        ignored_extensions
    ):
        return True

    return False


def _file_priority(
    path: str,
):
    lower = path.lower()

    filename = lower.split("/")[-1]


    if filename.startswith("readme"):
        return 0


    dependency_files = {
        "requirements.txt",
        "pyproject.toml",
        "package.json",
        "package-lock.json",
        "poetry.lock",
        "pipfile",
        "pipfile.lock",
        "environment.yml",
        "environment.yaml",
        "pom.xml",
        "build.gradle",
        "cargo.toml",
        "go.mod",
    }

    if filename in dependency_files:
        return 1


    important_files = {
        "main.py",
        "app.py",
        "server.py",
        "index.py",
        "index.js",
        "index.ts",
        "main.js",
        "main.ts",
        "app.js",
        "app.ts",
    }

    if filename in important_files:
        return 2


    if (
        "test" in filename
        or "/tests/" in lower
        or lower.startswith("tests/")
    ):
        return 3


    source_directories = (
        "src/",
        "app/",
        "lib/",
        "core/",
        "api/",
        "server/",
    )

    if lower.startswith(
        source_directories
    ):
        return 4

    return 5


def _add_line_numbers(
    content: str,
):
    lines = content.splitlines()

    numbered_lines = []

    for number, line in enumerate(
        lines,
        start=1,
    ):
        numbered_lines.append(
            f"{number:04d}: {line}"
        )

    return "\n".join(
        numbered_lines
    )


def _read_repository_file(
    owner: str,
    repo: str,
    path: str,
    branch: str,
    access_token: str | None = None,
):
    encoded_path = quote(
        path,
        safe="/",
    )

    url = (
        f"{GITHUB_API_URL}/repos/"
        f"{owner}/{repo}/contents/"
        f"{encoded_path}"
    )

    data = _github_get(
        url,
        params={
            "ref": branch,
        },
        access_token=access_token,
    )


    if not isinstance(
        data,
        dict,
    ):
        return None


    encoded_content = data.get(
        "content"
    )

    encoding = data.get(
        "encoding"
    )


    if (
        not encoded_content
        or encoding != "base64"
    ):
        return None


    try:
        raw_bytes = base64.b64decode(
            encoded_content
        )

        content = raw_bytes.decode(
            "utf-8"
        )

    except (
        ValueError,
        UnicodeDecodeError,
    ):
        return None


    original_length = len(
        content
    )

    truncated = False


    if (
        original_length
        > MAX_FILE_CHARACTERS
    ):
        content = content[
            :MAX_FILE_CHARACTERS
        ]

        truncated = True


    return {
        "path": path,

        "size_bytes":
            data.get("size"),

        "content":
            _add_line_numbers(
                content
            ),

        "truncated":
            truncated,
    }


def _build_repository_snapshot(
    repo_url: str,
    access_token: str | None = None,
):
    owner, repo = (
        _parse_github_url(
            repo_url
        )
    )


    repository_url = (
        f"{GITHUB_API_URL}/repos/"
        f"{owner}/{repo}"
    )


    repository_data = _github_get(
        repository_url,
        access_token=access_token,
    )


    default_branch = (
        repository_data.get(
            "default_branch"
        )
        or "main"
    )


    encoded_branch = quote(
        default_branch,
        safe="",
    )


    branch_data = _github_get(
        (
            f"{GITHUB_API_URL}/repos/"
            f"{owner}/{repo}/branches/"
            f"{encoded_branch}"
        ),
        access_token=access_token,
    )


    try:
        tree_sha = (
            branch_data["commit"]
            ["commit"]
            ["tree"]
            ["sha"]
        )

    except (
        KeyError,
        TypeError,
    ) as exc:
        raise GitHubAPIError(
            502,
            (
                "Repository tree bilgisi "
                "alınamadı."
            ),
        ) from exc


    tree_data = _github_get(
        (
            f"{GITHUB_API_URL}/repos/"
            f"{owner}/{repo}/git/trees/"
            f"{tree_sha}"
        ),
        params={
            "recursive": "1",
        },
        access_token=access_token,
    )


    tree_items = tree_data.get(
        "tree",
        [],
    )


    file_paths = [
        item.get("path")
        for item in tree_items
        if (
            item.get("type") == "blob"
            and item.get("path")
        )
    ]


    analyzable_files = [
        path
        for path in file_paths
        if not _should_ignore_file(
            path
        )
    ]


    sorted_files = sorted(
        analyzable_files,
        key=lambda path: (
            _file_priority(path),
            path.lower(),
        ),
    )


    visible_tree = (
        analyzable_files[
            :MAX_TREE_FILES
        ]
    )


    sampled_files = []

    total_code_characters = 0


    for path in sorted_files:
        if (
            len(sampled_files)
            >= MAX_SAMPLED_FILES
        ):
            break


        file_data = (
            _read_repository_file(
                owner=owner,
                repo=repo,
                path=path,
                branch=default_branch,
                access_token=access_token,
            )
        )


        if not file_data:
            continue


        content = (
            file_data["content"]
        )


        remaining = (
            MAX_TOTAL_CODE_CHARACTERS
            - total_code_characters
        )


        if remaining <= 0:
            break


        if len(content) > remaining:
            content = content[
                :remaining
            ]

            file_data["content"] = (
                content
            )

            file_data["truncated"] = (
                True
            )


        sampled_files.append(
            file_data
        )


        total_code_characters += len(
            content
        )


    return {
        "status": "success",

        "repository":
            f"{owner}/{repo}",

        "description":
            repository_data.get(
                "description"
            ),

        "primary_language":
            repository_data.get(
                "language"
            ),

        "default_branch":
            default_branch,

        "stars":
            repository_data.get(
                "stargazers_count",
                0,
            ),

        "forks":
            repository_data.get(
                "forks_count",
                0,
            ),

        "open_issues":
            repository_data.get(
                "open_issues_count",
                0,
            ),

        "repository_size_kb":
            repository_data.get(
                "size"
            ),

        "topics":
            repository_data.get(
                "topics",
                [],
            ),

        "private":
            repository_data.get(
                "private",
                False,
            ),

        "total_analyzable_files":
            len(
                analyzable_files
            ),

        "file_tree":
            visible_tree,

        "sampled_file_count":
            len(
                sampled_files
            ),

        "sampled_files":
            sampled_files,

        "snapshot_limits": {
            "max_tree_files":
                MAX_TREE_FILES,

            "max_sampled_files":
                MAX_SAMPLED_FILES,

            "max_characters_per_file":
                MAX_FILE_CHARACTERS,

            "max_total_code_characters":
                MAX_TOTAL_CODE_CHARACTERS,

            "github_tree_truncated":
                tree_data.get(
                    "truncated",
                    False,
                ),
        },

        "important_note": (
            "Snapshot repository'nin tamamını "
            "içermeyebilir. sampled_files alanındaki "
            "kod satırları 0001, 0002, 0003 gibi "
            "gerçek satır numaralarıyla verilmiştir."
        ),
    }


# =========================================================
# ADK TOOL
# =========================================================

def fetch_repository_snapshot(
    repo_url: str,
) -> dict:
    """
    Public GitHub repository snapshot tool.

    ADK agent tarafından kullanılır.
    """

    try:
        return _build_repository_snapshot(
            repo_url=repo_url,
            access_token=None,
        )

    except ValueError as exc:
        return {
            "status": "error",
            "error_type":
                "invalid_repository_url",
            "message":
                str(exc),
        }

    except GitHubAPIError as exc:
        return {
            "status": "error",
            "error_type":
                "github_api_error",

            "http_status":
                exc.status_code,

            "message":
                exc.message,
        }


# =========================================================
# AUTHENTICATED BACKEND HELPER
# =========================================================

def fetch_repository_snapshot_authenticated(
    repo_url: str,
    access_token: str | None,
) -> dict:
    """
    Auth server tarafından kullanılır.

    access_token frontend'e veya Gemini'ye
    gönderilmez.

    Token yalnızca GitHub API isteğinde
    kullanılır.
    """

    return _build_repository_snapshot(
        repo_url=repo_url,
        access_token=access_token,
    )