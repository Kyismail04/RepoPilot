import base64
from urllib.parse import quote, urlparse

import requests


GITHUB_API_URL = "https://api.github.com"

# Bir PR çok büyük olabilir.
# İlk aşamada modeli gereksiz yere doldurmamak için
# kontrollü limitler kullanıyoruz.
MAX_CHANGED_FILES = 100
MAX_SAMPLED_FILES = 8

MAX_PATCH_CHARACTERS = 3500
MAX_FILE_CHARACTERS = 3500
MAX_TOTAL_CODE_CHARACTERS = 18000

MAX_PR_BODY_CHARACTERS = 2500


# =========================================================
# EXCEPTIONS
# =========================================================

class GitHubPRError(Exception):
    def __init__(
        self,
        status_code: int,
        message: str,
    ):
        super().__init__(message)

        self.status_code = status_code
        self.message = message


# =========================================================
# URL PARSER
# =========================================================

def parse_pull_request_url(
    pull_request_url: str,
):
    """
    Desteklenen format:

    https://github.com/OWNER/REPO/pull/123

    /files gibi devam eden URL'ler de kabul edilir.
    """

    pull_request_url = (
        pull_request_url.strip()
    )

    parsed = urlparse(
        pull_request_url
    )


    if parsed.hostname not in {
        "github.com",
        "www.github.com",
    }:
        raise ValueError(
            "Geçerli bir GitHub Pull Request URL'si gir."
        )


    parts = [
        part
        for part in parsed.path.split("/")
        if part
    ]


    if len(parts) < 4:
        raise ValueError(
            "Pull Request URL'si geçersiz."
        )


    owner = parts[0]
    repo = parts[1]


    if repo.endswith(".git"):
        repo = repo[:-4]


    if parts[2] != "pull":
        raise ValueError(
            "Bu URL bir GitHub Pull Request adresi değil."
        )


    try:
        pull_number = int(
            parts[3]
        )

    except ValueError as exc:
        raise ValueError(
            "Pull Request numarası geçersiz."
        ) from exc


    if pull_number <= 0:
        raise ValueError(
            "Pull Request numarası geçersiz."
        )


    return (
        owner,
        repo,
        pull_number,
    )


# =========================================================
# GITHUB API
# =========================================================

def _get_headers(
    access_token: str | None = None,
):
    headers = {
        "Accept":
            "application/vnd.github+json",

        "X-GitHub-Api-Version":
            "2022-11-28",

        "User-Agent":
            "RepoPilot",
    }


    if access_token:
        headers[
            "Authorization"
        ] = (
            f"Bearer {access_token}"
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
        raise GitHubPRError(
            503,
            (
                "GitHub API ile bağlantı "
                "kurulamadı."
            ),
        ) from exc


    if response.status_code == 404:
        raise GitHubPRError(
            404,
            (
                "Pull Request bulunamadı "
                "veya GitHub hesabının "
                "erişim izni yok."
            ),
        )


    if response.status_code == 401:
        raise GitHubPRError(
            401,
            (
                "GitHub kimlik doğrulaması "
                "başarısız."
            ),
        )


    if response.status_code == 403:
        remaining = (
            response.headers.get(
                "X-RateLimit-Remaining"
            )
        )


        if remaining == "0":
            message = (
                "GitHub API rate limit "
                "sınırına ulaşıldı."
            )

        else:
            message = (
                "GitHub bu Pull Request "
                "için erişimi reddetti."
            )


        raise GitHubPRError(
            403,
            message,
        )


    if not response.ok:
        raise GitHubPRError(
            response.status_code,

            (
                "GitHub Pull Request API "
                "isteği başarısız oldu: "
                f"{response.status_code}"
            ),
        )


    try:
        return response.json()

    except ValueError as exc:
        raise GitHubPRError(
            502,
            (
                "GitHub geçerli bir JSON "
                "cevabı döndürmedi."
            ),
        ) from exc


# =========================================================
# FILE HELPERS
# =========================================================

def _is_binary_or_unsupported(
    filename: str,
):
    lower = filename.lower()


    ignored_extensions = (
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".ico",

        ".mp3",
        ".wav",
        ".mp4",
        ".avi",
        ".mov",

        ".zip",
        ".rar",
        ".7z",
        ".gz",
        ".tar",

        ".pdf",

        ".woff",
        ".woff2",
        ".ttf",
        ".otf",

        ".exe",
        ".dll",
        ".so",
        ".dylib",

        ".pkl",
        ".pickle",
        ".joblib",

        ".db",
        ".sqlite",
        ".sqlite3",
    )


    return lower.endswith(
        ignored_extensions
    )


def _file_priority(
    file_data: dict,
):
    filename = (
        file_data
        .get(
            "filename",
            "",
        )
        .lower()
    )


    basename = filename.split(
        "/"
    )[-1]


    # Security açısından önemli dosyalar.
    security_files = {
        ".env.example",
        "dockerfile",
        "docker-compose.yml",
        "docker-compose.yaml",
    }


    if basename in security_files:
        return 0


    dependency_files = {
        "requirements.txt",
        "pyproject.toml",
        "package.json",
        "package-lock.json",
        "poetry.lock",
        "pipfile",
        "pipfile.lock",
        "pom.xml",
        "build.gradle",
        "cargo.toml",
        "go.mod",
    }


    if basename in dependency_files:
        return 1


    # Test değişikliklerini özellikle görmek istiyoruz.
    if (
        "/tests/" in filename
        or filename.startswith(
            "tests/"
        )
        or "test_" in basename
        or basename.endswith(
            "_test.py"
        )
        or basename.endswith(
            ".test.js"
        )
        or basename.endswith(
            ".test.jsx"
        )
        or basename.endswith(
            ".test.ts"
        )
        or basename.endswith(
            ".test.tsx"
        )
    ):
        return 2


    source_extensions = (
        ".py",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".java",
        ".cs",
        ".cpp",
        ".c",
        ".h",
        ".hpp",
        ".go",
        ".rs",
        ".php",
        ".rb",
        ".kt",
        ".swift",
    )


    if filename.endswith(
        source_extensions
    ):
        return 3


    return 4


def _add_line_numbers(
    content: str,
):
    lines = content.splitlines()

    numbered = []


    for number, line in enumerate(
        lines,
        start=1,
    ):
        numbered.append(
            f"{number:04d}: {line}"
        )


    return "\n".join(
        numbered
    )


# =========================================================
# READ CURRENT FILE AT PR HEAD
# =========================================================

def _read_file_at_ref(
    owner: str,
    repo: str,
    filename: str,
    git_ref: str,
    access_token: str | None,
):
    encoded_path = quote(
        filename,
        safe="/",
    )


    url = (
        f"{GITHUB_API_URL}/repos/"
        f"{owner}/{repo}/contents/"
        f"{encoded_path}"
    )


    try:
        data = _github_get(
            url,

            params={
                "ref":
                    git_ref,
            },

            access_token=
                access_token,
        )

    except GitHubPRError:
        # Örneğin silinen veya özel bir dosya olabilir.
        # PR'ın tamamını bu yüzden başarısız yapmıyoruz.
        return None


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
        raw_bytes = (
            base64.b64decode(
                encoded_content
            )
        )

        content = (
            raw_bytes.decode(
                "utf-8"
            )
        )

    except (
        ValueError,
        UnicodeDecodeError,
    ):
        return None


    truncated = False


    if (
        len(content)
        > MAX_FILE_CHARACTERS
    ):
        content = content[
            :MAX_FILE_CHARACTERS
        ]

        truncated = True


    return {
        "content":
            _add_line_numbers(
                content
            ),

        "truncated":
            truncated,
    }


# =========================================================
# MAIN PR SNAPSHOT
# =========================================================

def fetch_pull_request_snapshot(
    pull_request_url: str,
    access_token: str | None = None,
) -> dict:
    """
    Pull Request metadata + changed files + patches +
    selected current file contents.

    GitHub access token is used only while talking to
    GitHub API and is never included in the returned
    snapshot.
    """

    (
        owner,
        repo,
        pull_number,
    ) = parse_pull_request_url(
        pull_request_url
    )


    # -----------------------------------------------------
    # PR METADATA
    # -----------------------------------------------------

    pull_data = _github_get(
        (
            f"{GITHUB_API_URL}/repos/"
            f"{owner}/{repo}/pulls/"
            f"{pull_number}"
        ),

        access_token=
            access_token,
    )


    head_data = (
        pull_data.get("head")
        or {}
    )

    base_data = (
        pull_data.get("base")
        or {}
    )


    head_sha = (
        head_data.get("sha")
    )


    # -----------------------------------------------------
    # CHANGED FILES
    # -----------------------------------------------------

    changed_files = _github_get(
        (
            f"{GITHUB_API_URL}/repos/"
            f"{owner}/{repo}/pulls/"
            f"{pull_number}/files"
        ),

        params={
            "per_page":
                MAX_CHANGED_FILES,

            "page":
                1,
        },

        access_token=
            access_token,
    )


    if not isinstance(
        changed_files,
        list,
    ):
        changed_files = []


    # Modelin bütün dosya isimlerini görebilmesi
    # faydalı fakat içeriklerin hepsini göndermiyoruz.
    changed_file_summary = []


    for file_data in changed_files:
        changed_file_summary.append(
            {
                "filename":
                    file_data.get(
                        "filename"
                    ),

                "status":
                    file_data.get(
                        "status"
                    ),

                "additions":
                    file_data.get(
                        "additions",
                        0,
                    ),

                "deletions":
                    file_data.get(
                        "deletions",
                        0,
                    ),

                "changes":
                    file_data.get(
                        "changes",
                        0,
                    ),

                "previous_filename":
                    file_data.get(
                        "previous_filename"
                    ),
            }
        )


    # -----------------------------------------------------
    # SELECT IMPORTANT FILES
    # -----------------------------------------------------

    analyzable_files = [
        file_data
        for file_data in changed_files
        if (
            file_data.get(
                "filename"
            )
            and not _is_binary_or_unsupported(
                file_data[
                    "filename"
                ]
            )
        )
    ]


    analyzable_files = sorted(
        analyzable_files,
        key=_file_priority,
    )


    sampled_files = []

    total_code_characters = 0


    for file_data in analyzable_files:

        if (
            len(sampled_files)
            >= MAX_SAMPLED_FILES
        ):
            break


        if (
            total_code_characters
            >= MAX_TOTAL_CODE_CHARACTERS
        ):
            break


        filename = file_data.get(
            "filename"
        )

        status = file_data.get(
            "status",
            "modified",
        )


        # -------------------------------------------------
        # DIFF PATCH
        # -------------------------------------------------

        patch = file_data.get(
            "patch"
        )


        patch_truncated = False


        if patch:
            if (
                len(patch)
                > MAX_PATCH_CHARACTERS
            ):
                patch = patch[
                    :MAX_PATCH_CHARACTERS
                ]

                patch_truncated = True

        else:
            patch = (
                "GitHub bu dosya için text patch "
                "verisi döndürmedi."
            )


        # -------------------------------------------------
        # CURRENT FILE CONTENT
        # -------------------------------------------------

        current_file = None


        if (
            status != "removed"
            and head_sha
        ):
            current_file = (
                _read_file_at_ref(
                    owner=owner,
                    repo=repo,
                    filename=filename,
                    git_ref=head_sha,
                    access_token=
                        access_token,
                )
            )


        current_content = None
        current_content_truncated = False


        if current_file:
            current_content = (
                current_file.get(
                    "content"
                )
            )

            current_content_truncated = (
                current_file.get(
                    "truncated",
                    False,
                )
            )


        # -------------------------------------------------
        # GLOBAL CHARACTER LIMIT
        # -------------------------------------------------

        remaining = (
            MAX_TOTAL_CODE_CHARACTERS
            - total_code_characters
        )


        combined_length = (
            len(patch or "")
            + len(
                current_content
                or ""
            )
        )


        if (
            combined_length
            > remaining
        ):
            if current_content:
                allowed_content = max(
                    0,
                    remaining
                    - len(
                        patch or ""
                    ),
                )

                current_content = (
                    current_content[
                        :allowed_content
                    ]
                )

                current_content_truncated = (
                    True
                )


        sampled_file = {
            "filename":
                filename,

            "previous_filename":
                file_data.get(
                    "previous_filename"
                ),

            "status":
                status,

            "additions":
                file_data.get(
                    "additions",
                    0,
                ),

            "deletions":
                file_data.get(
                    "deletions",
                    0,
                ),

            "changes":
                file_data.get(
                    "changes",
                    0,
                ),

            "patch":
                patch,

            "patch_truncated":
                patch_truncated,

            "current_file_content":
                current_content,

            "current_file_content_truncated":
                current_content_truncated,
        }


        sampled_files.append(
            sampled_file
        )


        total_code_characters += (
            len(
                patch or ""
            )
            + len(
                current_content
                or ""
            )
        )


    # -----------------------------------------------------
    # PR BODY
    # -----------------------------------------------------

    pull_body = (
        pull_data.get("body")
        or ""
    )


    body_truncated = False


    if (
        len(pull_body)
        > MAX_PR_BODY_CHARACTERS
    ):
        pull_body = pull_body[
            :MAX_PR_BODY_CHARACTERS
        ]

        body_truncated = True


    user_data = (
        pull_data.get("user")
        or {}
    )


    # -----------------------------------------------------
    # SNAPSHOT
    # -----------------------------------------------------

    return {
        "analysis_type":
            "pull_request",

        "repository":
            f"{owner}/{repo}",

        "pull_request_number":
            pull_number,

        "title":
            pull_data.get(
                "title"
            ),

        "description":
            pull_body,

        "description_truncated":
            body_truncated,

        "author":
            user_data.get(
                "login"
            ),

        "state":
            pull_data.get(
                "state"
            ),

        "draft":
            pull_data.get(
                "draft",
                False,
            ),

        "created_at":
            pull_data.get(
                "created_at"
            ),

        "updated_at":
            pull_data.get(
                "updated_at"
            ),

        "base_branch":
            base_data.get(
                "ref"
            ),

        "head_branch":
            head_data.get(
                "ref"
            ),

        "head_sha":
            head_sha,

        "commits":
            pull_data.get(
                "commits",
                0,
            ),

        "total_changed_files":
            pull_data.get(
                "changed_files",
                len(
                    changed_files
                ),
            ),

        "retrieved_changed_files":
            len(
                changed_files
            ),

        "additions":
            pull_data.get(
                "additions",
                0,
            ),

        "deletions":
            pull_data.get(
                "deletions",
                0,
            ),

        "changed_files":
            changed_file_summary,

        "sampled_files":
            sampled_files,

        "sampled_file_count":
            len(
                sampled_files
            ),

        "review_instructions": [
            (
                "Sadece bu Pull Request tarafından "
                "eklenen veya değiştirilen kodla ilgili "
                "bulgular üret."
            ),

            (
                "Repository'nin PR ile ilgisi olmayan "
                "mevcut sorunlarını PR'a yükleme."
            ),

            (
                "Bir problemi confirmed issue olarak "
                "işaretlemek için patch veya current "
                "file content içerisinde kanıt bulunmalı."
            ),

            (
                "Security, bug risk, breaking change, "
                "code quality, architecture ve testing "
                "risklerini değerlendir."
            ),

            (
                "Değişen davranış için test eklenmemişse "
                "testing riskini ayrıca değerlendir."
            ),
        ],

        "snapshot_limits": {
            "max_retrieved_changed_files":
                MAX_CHANGED_FILES,

            "max_sampled_files":
                MAX_SAMPLED_FILES,

            "max_patch_characters":
                MAX_PATCH_CHARACTERS,

            "max_file_characters":
                MAX_FILE_CHARACTERS,

            "max_total_code_characters":
                MAX_TOTAL_CODE_CHARACTERS,
        },

        "important_note": (
            "Bu veri bir Pull Request snapshot'ıdır. "
            "sampled_files içindeki patch alanı PR diff'ini, "
            "current_file_content alanı ise PR head commitindeki "
            "dosyanın satır numaralı güncel halini içerir. "
            "Repository'nin PR dışında kalan tamamı incelenmiş "
            "kabul edilmemelidir."
        ),
    }