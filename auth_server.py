import json
import os
import secrets
import time
from pathlib import Path
from urllib.parse import urlencode, urlparse

import requests
from dotenv import load_dotenv
from fastapi import (
    FastAPI,
    HTTPException,
    Request,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import (
    JSONResponse,
    RedirectResponse,
)
from pydantic import (
    BaseModel,
    Field,
)


from .tools.github_tools import (
    GitHubAPIError,
    fetch_repository_snapshot_authenticated,
)

from .tools.github_pr_tools import (
    GitHubPRError,
    fetch_pull_request_snapshot,
)

from .chat_service import (
    ContextChatError,
    ContextNotFoundError,
    ask_context_question,
    store_analysis_context,
)


# =========================================================
# ENV
# =========================================================

ENV_PATH = Path(__file__).with_name(
    ".env"
)

load_dotenv(
    ENV_PATH
)


GITHUB_CLIENT_ID = os.getenv(
    "GITHUB_CLIENT_ID"
)

GITHUB_CLIENT_SECRET = os.getenv(
    "GITHUB_CLIENT_SECRET"
)

GITHUB_REDIRECT_URI = os.getenv(
    "GITHUB_REDIRECT_URI",
    "http://localhost:8001/auth/github/callback",
)

REPOPILOT_FRONTEND_URL = os.getenv(
    "REPOPILOT_FRONTEND_URL",
    "http://localhost:5174",
)

ADK_API_URL = os.getenv(
    "ADK_API_URL",
    "http://127.0.0.1:8000",
)


if not GITHUB_CLIENT_ID:
    raise RuntimeError(
        "GITHUB_CLIENT_ID .env dosyasında bulunamadı."
    )

if not GITHUB_CLIENT_SECRET:
    raise RuntimeError(
        "GITHUB_CLIENT_SECRET .env dosyasında bulunamadı."
    )


# =========================================================
# FASTAPI
# =========================================================

app = FastAPI(
    title="RepoPilot Backend",
    version="4.0.0",
)


app.add_middleware(
    CORSMiddleware,

    allow_origins=[
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"],

    # Frontend analizden sonra context id'yi
    # response header'dan okuyacak.
    expose_headers=[
        "X-RepoPilot-Context-Id",
    ],
)


# =========================================================
# CONFIG
# =========================================================

GITHUB_AUTHORIZE_URL = (
    "https://github.com/login/oauth/authorize"
)

GITHUB_TOKEN_URL = (
    "https://github.com/login/oauth/access_token"
)

GITHUB_API_URL = (
    "https://api.github.com"
)


SESSION_COOKIE_NAME = (
    "repopilot_session"
)

GUEST_COOKIE_NAME = (
    "repopilot_guest"
)

STATE_EXPIRATION_SECONDS = 600

DEFAULT_SESSION_SECONDS = (
    8 * 60 * 60
)

GUEST_COOKIE_SECONDS = (
    8 * 60 * 60
)


# =========================================================
# DEVELOPMENT STORAGE
# =========================================================

pending_states = {}

user_sessions = {}


# =========================================================
# REQUEST MODELS
# =========================================================

class AnalysisRequest(BaseModel):
    repo_url: str


class ChatRequest(BaseModel):
    context_id: str = Field(
        min_length=10,
        max_length=256,
    )

    question: str = Field(
        min_length=1,
        max_length=2000,
    )


# =========================================================
# GENERAL HELPERS
# =========================================================

def cleanup_expired_states():
    now = time.time()

    expired_states = [
        state
        for state, created_at
        in pending_states.items()
        if (
            now - created_at
            > STATE_EXPIRATION_SECONDS
        )
    ]

    for state in expired_states:
        pending_states.pop(
            state,
            None,
        )


def is_pull_request_url(
    github_url: str,
) -> bool:
    try:
        parsed = urlparse(
            github_url.strip()
        )

        parts = [
            part
            for part in parsed.path.split("/")
            if part
        ]

        return (
            parsed.hostname
            in {
                "github.com",
                "www.github.com",
            }
            and len(parts) >= 4
            and parts[2] == "pull"
            and parts[3].isdigit()
        )

    except Exception:
        return False


def extract_report_text(
    events,
):
    """
    ADK event listesinden son model cevabını bulur.
    """

    if not isinstance(
        events,
        list,
    ):
        return None


    for event in reversed(
        events
    ):
        if not isinstance(
            event,
            dict,
        ):
            continue


        content = event.get(
            "content"
        )

        if not isinstance(
            content,
            dict,
        ):
            continue


        parts = content.get(
            "parts"
        )

        if not isinstance(
            parts,
            list,
        ):
            continue


        for part in parts:
            if not isinstance(
                part,
                dict,
            ):
                continue


            text = part.get(
                "text"
            )


            if (
                isinstance(
                    text,
                    str,
                )
                and text.strip()
            ):
                return text.strip()


    return None


# =========================================================
# IDENTITY
# =========================================================

def get_request_identity(
    request: Request,
    session=None,
):
    """
    Chat contextlerinin kullanıcılar arasında
    karışmasını engeller.

    GitHub kullanıcısı:
        github:<github-id>

    Guest:
        guest:<random-browser-id>
    """

    if session:
        github_id = session.get(
            "github_id"
        )

        github_login = session.get(
            "login"
        )


        if github_id:
            return (
                f"github:{github_id}",
                None,
            )


        if github_login:
            return (
                f"github-login:{github_login}",
                None,
            )


    guest_id = request.cookies.get(
        GUEST_COOKIE_NAME
    )


    if guest_id:
        return (
            f"guest:{guest_id}",
            None,
        )


    new_guest_id = secrets.token_urlsafe(
        32
    )


    return (
        f"guest:{new_guest_id}",
        new_guest_id,
    )


def attach_guest_cookie(
    response,
    guest_id,
):
    if not guest_id:
        return response


    response.set_cookie(
        key=
            GUEST_COOKIE_NAME,

        value=
            guest_id,

        httponly=True,

        secure=False,

        samesite="lax",

        max_age=
            GUEST_COOKIE_SECONDS,

        path="/",
    )


    return response


# =========================================================
# GITHUB AUTH HELPERS
# =========================================================

def github_headers(
    access_token: str,
):
    return {
        "Accept":
            "application/vnd.github+json",

        "Authorization":
            f"Bearer {access_token}",

        "X-GitHub-Api-Version":
            "2022-11-28",

        "User-Agent":
            "RepoPilot",
    }


def exchange_code_for_token(
    code: str,
):
    response = requests.post(
        GITHUB_TOKEN_URL,

        headers={
            "Accept":
                "application/json",
        },

        data={
            "client_id":
                GITHUB_CLIENT_ID,

            "client_secret":
                GITHUB_CLIENT_SECRET,

            "code":
                code,

            "redirect_uri":
                GITHUB_REDIRECT_URI,
        },

        timeout=20,
    )


    response.raise_for_status()


    data = response.json()


    if "error" in data:
        raise RuntimeError(
            data.get(
                "error_description",
                data["error"],
            )
        )


    access_token = data.get(
        "access_token"
    )


    if not access_token:
        raise RuntimeError(
            "GitHub access token döndürmedi."
        )


    return data


def refresh_github_token(
    session,
):
    refresh_token = session.get(
        "refresh_token"
    )


    if not refresh_token:
        return False


    try:
        response = requests.post(
            GITHUB_TOKEN_URL,

            headers={
                "Accept":
                    "application/json",
            },

            data={
                "client_id":
                    GITHUB_CLIENT_ID,

                "client_secret":
                    GITHUB_CLIENT_SECRET,

                "grant_type":
                    "refresh_token",

                "refresh_token":
                    refresh_token,
            },

            timeout=20,
        )

    except requests.RequestException:
        return False


    if not response.ok:
        return False


    data = response.json()


    if data.get("error"):
        return False


    new_access_token = data.get(
        "access_token"
    )


    if not new_access_token:
        return False


    session["access_token"] = (
        new_access_token
    )


    if data.get(
        "refresh_token"
    ):
        session["refresh_token"] = (
            data["refresh_token"]
        )


    expires_in = data.get(
        "expires_in"
    )


    if expires_in:
        session["expires_at"] = (
            time.time()
            + int(expires_in)
        )

    else:
        session["expires_at"] = None


    return True


def ensure_valid_access_token(
    session,
):
    expires_at = session.get(
        "expires_at"
    )


    if not expires_at:
        return session[
            "access_token"
        ]


    if (
        time.time()
        < expires_at - 60
    ):
        return session[
            "access_token"
        ]


    if not refresh_github_token(
        session
    ):
        raise HTTPException(
            status_code=401,

            detail=(
                "GitHub oturumunun süresi "
                "doldu. Tekrar giriş yap."
            ),
        )


    return session[
        "access_token"
    ]


def get_github_user(
    access_token: str,
):
    response = requests.get(
        f"{GITHUB_API_URL}/user",

        headers=github_headers(
            access_token
        ),

        timeout=20,
    )


    response.raise_for_status()


    return response.json()


def get_current_session(
    request: Request,
):
    session_id = (
        request.cookies.get(
            SESSION_COOKIE_NAME
        )
    )


    if not session_id:
        return None


    return user_sessions.get(
        session_id
    )


def frontend_redirect(
    **params,
):
    query = urlencode(
        params
    )


    if query:
        return (
            f"{REPOPILOT_FRONTEND_URL}"
            f"/?{query}"
        )


    return REPOPILOT_FRONTEND_URL


# =========================================================
# HEALTH
# =========================================================

@app.get("/")
def root():
    return {
        "service":
            "RepoPilot Backend",

        "status":
            "online",

        "features": [
            "repository_analysis",
            "private_repository_analysis",
            "pull_request_review",
            "github_oauth",
            "guest_mode",
            "context_only_chat",
        ],
    }


@app.get("/health")
def health():
    return {
        "status":
            "ok",
    }


# =========================================================
# GITHUB LOGIN
# =========================================================

@app.get(
    "/auth/github/login"
)
def github_login():
    cleanup_expired_states()


    state = secrets.token_urlsafe(
        32
    )


    pending_states[state] = (
        time.time()
    )


    params = {
        "client_id":
            GITHUB_CLIENT_ID,

        "redirect_uri":
            GITHUB_REDIRECT_URI,

        "scope":
            "repo read:user offline_access",

        "state":
            state,

        "prompt":
            "select_account",
    }


    authorization_url = (
        f"{GITHUB_AUTHORIZE_URL}?"
        f"{urlencode(params)}"
    )


    return RedirectResponse(
        authorization_url
    )


# =========================================================
# GITHUB CALLBACK
# =========================================================

@app.get(
    "/auth/github/callback"
)
def github_callback(
    code: str = None,
    state: str = None,
    error: str = None,
    error_description: str = None,
):
    cleanup_expired_states()


    if error:
        return RedirectResponse(
            frontend_redirect(
                github_error=(
                    error_description
                    or error
                )
            )
        )


    if not code:
        return RedirectResponse(
            frontend_redirect(
                github_error=(
                    "GitHub authorization "
                    "code göndermedi."
                )
            )
        )


    if not state:
        return RedirectResponse(
            frontend_redirect(
                github_error=(
                    "OAuth state değeri "
                    "bulunamadı."
                )
            )
        )


    created_at = pending_states.pop(
        state,
        None,
    )


    if created_at is None:
        return RedirectResponse(
            frontend_redirect(
                github_error=(
                    "Geçersiz veya süresi "
                    "dolmuş OAuth isteği."
                )
            )
        )


    if (
        time.time() - created_at
        > STATE_EXPIRATION_SECONDS
    ):
        return RedirectResponse(
            frontend_redirect(
                github_error=(
                    "GitHub giriş isteğinin "
                    "süresi doldu."
                )
            )
        )


    try:
        token_data = (
            exchange_code_for_token(
                code
            )
        )


        access_token = (
            token_data[
                "access_token"
            ]
        )


        github_user = (
            get_github_user(
                access_token
            )
        )


    except requests.RequestException:
        return RedirectResponse(
            frontend_redirect(
                github_error=(
                    "GitHub ile bağlantı "
                    "kurulamadı."
                )
            )
        )


    except RuntimeError as exc:
        return RedirectResponse(
            frontend_redirect(
                github_error=str(
                    exc
                )
            )
        )


    session_id = secrets.token_urlsafe(
        48
    )


    expires_in = token_data.get(
        "expires_in"
    )


    expires_at = (
        time.time()
        + int(expires_in)
        if expires_in
        else None
    )


    user_sessions[
        session_id
    ] = {
        "access_token":
            access_token,

        "refresh_token":
            token_data.get(
                "refresh_token"
            ),

        "expires_at":
            expires_at,

        "github_id":
            github_user.get(
                "id"
            ),

        "login":
            github_user.get(
                "login"
            ),

        "name":
            github_user.get(
                "name"
            ),

        "avatar_url":
            github_user.get(
                "avatar_url"
            ),

        "html_url":
            github_user.get(
                "html_url"
            ),

        "created_at":
            time.time(),
    }


    response = RedirectResponse(
        frontend_redirect(
            github="connected"
        )
    )


    response.set_cookie(
        key=
            SESSION_COOKIE_NAME,

        value=
            session_id,

        httponly=True,

        secure=False,

        samesite="lax",

        max_age=
            DEFAULT_SESSION_SECONDS,

        path="/",
    )


    return response


# =========================================================
# CURRENT USER
# =========================================================

@app.get("/auth/me")
def auth_me(
    request: Request,
):
    session = get_current_session(
        request
    )


    if not session:
        return {
            "authenticated":
                False,

            "user":
                None,
        }


    try:
        access_token = (
            ensure_valid_access_token(
                session
            )
        )


        github_user = get_github_user(
            access_token
        )


    except (
        HTTPException,
        requests.RequestException,
    ):
        return {
            "authenticated":
                False,

            "user":
                None,
        }


    return {
        "authenticated":
            True,

        "user": {
            "id":
                github_user.get(
                    "id"
                ),

            "login":
                github_user.get(
                    "login"
                ),

            "name":
                github_user.get(
                    "name"
                ),

            "avatar_url":
                github_user.get(
                    "avatar_url"
                ),

            "html_url":
                github_user.get(
                    "html_url"
                ),
        },
    }


# =========================================================
# LOGOUT
# =========================================================

@app.post("/auth/logout")
def logout(
    request: Request,
):
    session_id = request.cookies.get(
        SESSION_COOKIE_NAME
    )


    if session_id:
        user_sessions.pop(
            session_id,
            None,
        )


    response = JSONResponse(
        {
            "success": True,

            "message":
                "RepoPilot GitHub oturumu kapatıldı.",
        }
    )


    response.delete_cookie(
        key=
            SESSION_COOKIE_NAME,

        path="/",

        httponly=True,

        samesite="lax",
    )


    return response


# =========================================================
# REPOSITORY SNAPSHOT
# =========================================================

def get_repository_snapshot(
    github_url: str,
    access_token: str | None,
    authenticated: bool,
):
    try:
        return (
            fetch_repository_snapshot_authenticated(
                repo_url=
                    github_url,

                access_token=
                    access_token,
            )
        )


    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


    except GitHubAPIError as exc:

        if exc.status_code == 404:

            if authenticated:
                raise HTTPException(
                    status_code=403,

                    detail=(
                        "GitHub hesabının bu "
                        "repository'ye erişim "
                        "izni bulunmuyor veya "
                        "repository mevcut değil."
                    ),
                )


            raise HTTPException(
                status_code=403,

                detail=(
                    "Bu repository private "
                    "olabilir. Private repository "
                    "analizi için GitHub hesabınla "
                    "giriş yap."
                ),
            )


        if exc.status_code == 401:
            raise HTTPException(
                status_code=401,

                detail=(
                    "GitHub oturumunun yetkisi "
                    "geçersiz. Tekrar giriş yap."
                ),
            )


        if exc.status_code == 403:
            raise HTTPException(
                status_code=403,

                detail=(
                    "GitHub repository erişimini "
                    "reddetti. Repository yetkini "
                    "veya GitHub rate limit "
                    "durumunu kontrol et."
                ),
            )


        raise HTTPException(
            status_code=502,
            detail=exc.message,
        )


# =========================================================
# PULL REQUEST SNAPSHOT
# =========================================================

def get_pull_request_snapshot(
    github_url: str,
    access_token: str | None,
    authenticated: bool,
):
    try:
        return (
            fetch_pull_request_snapshot(
                pull_request_url=
                    github_url,

                access_token=
                    access_token,
            )
        )


    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


    except GitHubPRError as exc:

        if exc.status_code == 404:

            if authenticated:
                raise HTTPException(
                    status_code=403,

                    detail=(
                        "GitHub hesabının bu "
                        "Pull Request'e erişim "
                        "izni bulunmuyor veya "
                        "Pull Request mevcut değil."
                    ),
                )


            raise HTTPException(
                status_code=403,

                detail=(
                    "Bu Pull Request private bir "
                    "repository'ye ait olabilir. "
                    "İncelemek için GitHub "
                    "hesabınla giriş yap."
                ),
            )


        if exc.status_code == 401:
            raise HTTPException(
                status_code=401,

                detail=(
                    "GitHub oturumunun yetkisi "
                    "geçersiz. Tekrar giriş yap."
                ),
            )


        if exc.status_code == 403:
            raise HTTPException(
                status_code=403,

                detail=(
                    "GitHub Pull Request erişimini "
                    "reddetti. Repository yetkini "
                    "veya GitHub rate limit "
                    "durumunu kontrol et."
                ),
            )


        raise HTTPException(
            status_code=502,
            detail=exc.message,
        )


# =========================================================
# ADK
# =========================================================

def send_to_adk(
    agent_message: str,
    github_login: str | None,
):
    adk_session_id = secrets.token_urlsafe(
        24
    )


    if github_login:
        adk_user_id = (
            f"github-{github_login}"
        )

    else:
        adk_user_id = (
            "repopilot-guest-user"
        )


    adk_request = {
        "appName":
            "repopilot",

        "userId":
            adk_user_id,

        "sessionId":
            adk_session_id,

        "newMessage": {
            "role":
                "user",

            "parts": [
                {
                    "text":
                        agent_message,
                }
            ],
        },
    }


    try:
        adk_response = requests.post(
            f"{ADK_API_URL}/run",

            json=
                adk_request,

            timeout=180,
        )


    except requests.RequestException as exc:
        raise HTTPException(
            status_code=503,

            detail=(
                "RepoPilot AI backend "
                "sunucusuna ulaşılamadı."
            ),
        ) from exc


    if not adk_response.ok:
        raise HTTPException(
            status_code=502,

            detail=(
                "RepoPilot AI analiz "
                "sunucusu isteği başarısız: "
                f"{adk_response.status_code}"
            ),
        )


    try:
        return adk_response.json()


    except ValueError as exc:
        raise HTTPException(
            status_code=502,

            detail=(
                "RepoPilot AI backend "
                "geçerli JSON döndürmedi."
            ),
        ) from exc


# =========================================================
# ANALYSIS RESPONSE + CHAT CONTEXT
# =========================================================

def create_analysis_response(
    events,
    snapshot: dict,
    analysis_type: str,
    owner_key: str,
    new_guest_id=None,
):
    report_text = extract_report_text(
        events
    )


    headers = {}


    if report_text:
        context_id = (
            store_analysis_context(
                owner_key=
                    owner_key,

                snapshot=
                    snapshot,

                report_text=
                    report_text,

                analysis_type=
                    analysis_type,
            )
        )


        headers[
            "X-RepoPilot-Context-Id"
        ] = context_id


    response = JSONResponse(
        content=events,
        headers=headers,
    )


    return attach_guest_cookie(
        response,
        new_guest_id,
    )


# =========================================================
# ANALYSIS
# =========================================================

@app.post("/analysis/run")
def run_analysis(
    payload: AnalysisRequest,
    request: Request,
):
    github_url = (
        payload.repo_url.strip()
    )


    if not github_url:
        raise HTTPException(
            status_code=400,

            detail=(
                "GitHub URL boş olamaz."
            ),
        )


    # -----------------------------------------------------
    # AUTH
    # -----------------------------------------------------

    session = get_current_session(
        request
    )


    access_token = None
    github_login = None
    authenticated = False


    if session:
        try:
            access_token = (
                ensure_valid_access_token(
                    session
                )
            )

            github_login = session.get(
                "login"
            )

            authenticated = True

        except HTTPException:
            access_token = None
            github_login = None
            authenticated = False
            session = None


    owner_key, new_guest_id = (
        get_request_identity(
            request=request,
            session=session,
        )
    )


    # =====================================================
    # PR REVIEW
    # =====================================================

    if is_pull_request_url(
        github_url
    ):
        snapshot = (
            get_pull_request_snapshot(
                github_url=
                    github_url,

                access_token=
                    access_token,

                authenticated=
                    authenticated,
            )
        )


        snapshot_json = json.dumps(
            snapshot,
            ensure_ascii=False,
        )


        agent_message = (
            "Bu istek normal repository analizi değildir.\n\n"

            "Bu bir GITHUB PULL REQUEST REVIEW işlemidir.\n\n"

            "Aşağıdaki Pull Request snapshot'ını incele.\n\n"

            "fetch_repository_snapshot aracını ÇAĞIRMA.\n"

            "Sadece verilen Pull Request snapshot'ına dayan.\n\n"

            "Özellikle kontrol et:\n"

            "- Yeni bug riski\n"
            "- Security vulnerability\n"
            "- Breaking change\n"
            "- Logic error\n"
            "- Error handling eksikliği\n"
            "- Code quality problemi\n"
            "- Architecture problemi\n"
            "- Test eksikliği\n"
            "- Edge case problemi\n"
            "- Maintainability riski\n\n"

            "Repository'de daha önceden var olan "
            "bir problemi PR problemi gibi gösterme.\n\n"

            "CONFIRMED ISSUE demek için patch veya "
            "current_file_content içerisinde somut "
            "kanıt bulunmalıdır.\n\n"

            "Mevcut RepoPilot JSON rapor formatını kullan.\n\n"

            'Ek alanlar:\n'
            '"analysis_type": "pull_request"\n'
            '"pull_request_number": PR numarası\n'
            '"pull_request_title": PR başlığı\n'
            '"base_branch": hedef branch\n'
            '"head_branch": kaynak branch\n'
            '"changed_files_count": değişen dosya sayısı\n'
            '"additions": eklenen satır sayısı\n'
            '"deletions": silinen satır sayısı\n\n'

            "REPOSITORY_SNAPSHOT_JSON:\n"
            f"{snapshot_json}"
        )


        events = send_to_adk(
            agent_message=
                agent_message,

            github_login=
                github_login,
        )


        return create_analysis_response(
            events=
                events,

            snapshot=
                snapshot,

            analysis_type=
                "pull_request",

            owner_key=
                owner_key,

            new_guest_id=
                new_guest_id,
        )


    # =====================================================
    # REPOSITORY ANALYSIS
    # =====================================================

    snapshot = (
        get_repository_snapshot(
            github_url=
                github_url,

            access_token=
                access_token,

            authenticated=
                authenticated,
        )
    )


    snapshot_json = json.dumps(
        snapshot,
        ensure_ascii=False,
    )


    agent_message = (
        "Aşağıdaki repository snapshot'ını "
        "ayrıntılı olarak analiz et.\n\n"

        "Bu snapshot RepoPilot backend tarafından "
        "GitHub API üzerinden güvenli şekilde "
        "önceden alınmıştır.\n"

        "Bu istekte fetch_repository_snapshot "
        "aracını tekrar çağırma.\n"

        "Yalnızca aşağıdaki snapshot verilerine dayan.\n"

        "Mevcut RepoPilot JSON rapor formatını "
        "eksiksiz kullan.\n\n"

        "REPOSITORY_SNAPSHOT_JSON:\n"
        f"{snapshot_json}"
    )


    events = send_to_adk(
        agent_message=
            agent_message,

        github_login=
            github_login,
    )


    return create_analysis_response(
        events=
            events,

        snapshot=
            snapshot,

        analysis_type=
            "repository",

        owner_key=
            owner_key,

        new_guest_id=
            new_guest_id,
    )


# =========================================================
# ASK REPOPILOT
# =========================================================

@app.post("/chat/ask")
def chat_ask(
    payload: ChatRequest,
    request: Request,
):
    session = get_current_session(
        request
    )


    if session:
        try:
            ensure_valid_access_token(
                session
            )

        except HTTPException:
            session = None


    owner_key, _ = (
        get_request_identity(
            request=request,
            session=session,
        )
    )


    try:
        result = ask_context_question(
            context_id=
                payload.context_id,

            owner_key=
                owner_key,

            question=
                payload.question,
        )


    except ContextNotFoundError as exc:
        raise HTTPException(
            status_code=404,

            detail=(
                "Analiz bağlamı bulunamadı veya "
                "süresi doldu. Repository/Pull Request'i "
                "yeniden analiz et."
            ),
        ) from exc


    except ContextChatError as exc:
        raise HTTPException(
            status_code=503,

            detail=str(exc),
        ) from exc


    return result