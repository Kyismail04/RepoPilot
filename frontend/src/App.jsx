import {
  useEffect,
  useRef,
  useState,
} from "react";

import "./App.css";


const AUTH_SERVER = "http://localhost:8001";


function App() {
  const [repoUrl, setRepoUrl] = useState("");

  const [loading, setLoading] =
    useState(false);

  const [report, setReport] =
    useState(null);

  const [error, setError] =
    useState("");


  const [
    privateAccessRequired,
    setPrivateAccessRequired,
  ] = useState(false);


  const [
    githubUser,
    setGithubUser,
  ] = useState(null);

  const [
    authLoading,
    setAuthLoading,
  ] = useState(true);

  const [
    authError,
    setAuthError,
  ] = useState("");


  // =====================================================
  // CHAT STATE
  // =====================================================

  const [
    analysisContextId,
    setAnalysisContextId,
  ] = useState(null);


  const [
    chatMessages,
    setChatMessages,
  ] = useState([]);


  const [
    chatInput,
    setChatInput,
  ] = useState("");


  const [
    chatLoading,
    setChatLoading,
  ] = useState(false);


  const [
    chatError,
    setChatError,
  ] = useState("");


  const chatBottomRef = useRef(null);


  // =====================================================
  // INITIAL AUTH CHECK
  // =====================================================

  useEffect(() => {
    checkGithubLogin();


    const params =
      new URLSearchParams(
        window.location.search
      );


    const githubConnected =
      params.get("github");


    const githubError =
      params.get("github_error");


    if (
      githubConnected ===
      "connected"
    ) {
      setAuthError("");


      window.history.replaceState(
        {},
        document.title,
        window.location.pathname
      );
    }


    if (githubError) {
      setAuthError(
        githubError
      );


      window.history.replaceState(
        {},
        document.title,
        window.location.pathname
      );
    }
  }, []);


  // Chat yeni mesaj geldiğinde aşağı kaydır.
  useEffect(() => {
    chatBottomRef.current
      ?.scrollIntoView({
        behavior: "smooth",
      });
  }, [
    chatMessages,
    chatLoading,
  ]);


  // =====================================================
  // AUTH
  // =====================================================

  const checkGithubLogin =
    async () => {

      setAuthLoading(true);


      try {
        const response =
          await fetch(
            `${AUTH_SERVER}/auth/me`,
            {
              method: "GET",

              credentials:
                "include",
            }
          );


        if (!response.ok) {
          setGithubUser(null);

          return;
        }


        const data =
          await response.json();


        if (
          data.authenticated &&
          data.user
        ) {
          setGithubUser(
            data.user
          );

        } else {
          setGithubUser(null);
        }

      } catch (err) {
        console.error(
          "GitHub auth check error:",
          err
        );


        setGithubUser(null);

      } finally {
        setAuthLoading(false);
      }
    };


  const signInWithGithub =
    () => {

      window.location.href =
        `${AUTH_SERVER}/auth/github/login`;
    };


  const logoutGithub =
    async () => {

      try {
        await fetch(
          `${AUTH_SERVER}/auth/logout`,
          {
            method: "POST",

            credentials:
              "include",
          }
        );


        setGithubUser(null);

        setReport(null);

        setRepoUrl("");

        setError("");

        setAuthError("");

        setPrivateAccessRequired(
          false
        );


        resetChat();


        window.scrollTo({
          top: 0,

          behavior: "smooth",
        });

      } catch (err) {
        console.error(
          "GitHub logout error:",
          err
        );


        setAuthError(
          "GitHub oturumu kapatılırken bir hata oluştu."
        );
      }
    };


  // =====================================================
  // URL HELPERS
  // =====================================================

  const isValidGitHubRepository =
    (url) => {

      try {
        const parsedUrl =
          new URL(
            url.trim()
          );


        if (
          parsedUrl.protocol
            !== "https:" &&
          parsedUrl.protocol
            !== "http:"
        ) {
          return false;
        }


        if (
          parsedUrl.hostname
            !== "github.com" &&
          parsedUrl.hostname
            !== "www.github.com"
        ) {
          return false;
        }


        const parts =
          parsedUrl.pathname
            .split("/")
            .filter(Boolean);


        return parts.length >= 2;

      } catch {
        return false;
      }
    };


  const isPullRequestUrl =
    (url) => {

      try {
        const parsedUrl =
          new URL(
            url.trim()
          );


        const parts =
          parsedUrl.pathname
            .split("/")
            .filter(Boolean);


        return (
          (
            parsedUrl.hostname
              === "github.com" ||

            parsedUrl.hostname
              === "www.github.com"
          )

          &&

          parts.length >= 4

          &&

          parts[2] === "pull"

          &&

          /^\d+$/.test(
            parts[3]
          )
        );

      } catch {
        return false;
      }
    };


  // =====================================================
  // BACKEND ERROR
  // =====================================================

  const getBackendError =
    async (response) => {

      try {
        const data =
          await response.json();


        if (data?.detail) {
          return data.detail;
        }


        if (data?.message) {
          return data.message;
        }

      } catch {
        // Varsayılan hata mesajı.
      }


      return null;
    };


  // =====================================================
  // CHAT HELPERS
  // =====================================================

  const resetChat = () => {
    setAnalysisContextId(
      null
    );

    setChatMessages([]);

    setChatInput("");

    setChatLoading(false);

    setChatError("");
  };


  const initializeChat =
    (isPullRequest) => {

      setChatInput("");

      setChatError("");


      setChatMessages([
        {
          id:
            crypto.randomUUID(),

          role:
            "assistant",

          type:
            "normal",

          text:
            isPullRequest
              ? (
                "Pull Request incelemesi tamamlandı. " +
                "Bu PR'ın değişiklikleri, riskleri, testleri " +
                "ve rapordaki bulgular hakkında soru sorabilirsin."
              )
              : (
                "Repository analizi tamamlandı. " +
                "Bu proje, incelenen kodlar, mimari, güvenlik, " +
                "testler ve rapordaki bulgular hakkında soru sorabilirsin."
              ),
        },
      ]);
    };


  // =====================================================
  // REPOSITORY / PR ANALYSIS
  // =====================================================

  const analyzeRepository =
    async () => {

      const trimmedUrl =
        repoUrl.trim();


      if (!trimmedUrl) {
        setError(
          "Lütfen analiz etmek istediğin GitHub repository veya Pull Request URL'sini gir."
        );

        return;
      }


      if (
        !isValidGitHubRepository(
          trimmedUrl
        )
      ) {
        setError(
          "Geçerli bir GitHub adresi gir. Örnek: https://github.com/username/repository veya https://github.com/username/repository/pull/1"
        );

        return;
      }


      const currentAnalysisIsPR =
        isPullRequestUrl(
          trimmedUrl
        );


      setLoading(true);

      setError("");

      setReport(null);

      setPrivateAccessRequired(
        false
      );


      // Yeni analiz başladığında eski
      // chat context'i kullanılamaz.
      resetChat();


      try {
        const response =
          await fetch(
            `${AUTH_SERVER}/analysis/run`,
            {
              method: "POST",

              credentials:
                "include",

              headers: {
                "Content-Type":
                  "application/json",
              },

              body:
                JSON.stringify({
                  repo_url:
                    trimmedUrl,
                }),
            }
          );


        if (!response.ok) {
          const backendMessage =
            await getBackendError(
              response
            );


          if (
            response.status === 401
          ) {
            setGithubUser(null);


            throw new Error(
              backendMessage ||
              (
                "GitHub oturumunun süresi doldu. " +
                "Private içerik analizi için tekrar GitHub hesabınla giriş yap."
              )
            );
          }


          if (
            response.status === 403
          ) {
            if (!githubUser) {
              setPrivateAccessRequired(
                true
              );


              throw new Error(
                backendMessage ||
                (
                  "Bu repository veya Pull Request private olabilir. " +
                  "GitHub hesabınla giriş yap."
                )
              );
            }


            throw new Error(
              backendMessage ||
              (
                "Bağlı GitHub hesabının bu içeriğe erişim izni bulunmuyor."
              )
            );
          }


          if (
            response.status === 400
          ) {
            throw new Error(
              backendMessage ||
              "GitHub adresi geçersiz."
            );
          }


          if (
            response.status >= 500
          ) {
            throw new Error(
              backendMessage ||
              "RepoPilot backend tarafında bir hata oluştu."
            );
          }


          throw new Error(
            backendMessage ||
            `Backend hatası: ${response.status}`
          );
        }


        // =================================================
        // CHAT CONTEXT ID
        // =================================================

        const contextId =
          response.headers.get(
            "X-RepoPilot-Context-Id"
          );


        const events =
          await response.json();


        let reportText =
          null;


        for (
          let i =
            events.length - 1;

          i >= 0;

          i--
        ) {
          const event =
            events[i];


          if (
            event.errorMessage
          ) {
            throw new Error(
              event.errorMessage
            );
          }


          if (
            !event.content?.parts
          ) {
            continue;
          }


          for (
            const part
            of event.content.parts
          ) {
            if (
              typeof part.text
                === "string" &&

              part.text.trim()
            ) {
              reportText =
                part.text;

              break;
            }
          }


          if (reportText) {
            break;
          }
        }


        if (!reportText) {
          throw new Error(
            "RepoPilot analiz sonucunu döndürmedi."
          );
        }


        const cleanedText =
          reportText
            .replace(
              /^```json\s*/i,
              ""
            )
            .replace(
              /^```\s*/i,
              ""
            )
            .replace(
              /\s*```$/i,
              ""
            )
            .trim();


        let parsedReport;


        try {
          parsedReport =
            JSON.parse(
              cleanedText
            );

        } catch {
          console.error(
            "Geçersiz JSON:",
            cleanedText
          );


          throw new Error(
            "RepoPilot raporu oluşturdu fakat cevap geçerli JSON formatında değildi."
          );
        }


        if (
          typeof (
            parsedReport
              .health_score
          ) !== "number" ||

          !parsedReport.repository
        ) {
          throw new Error(
            "RepoPilot eksik bir analiz raporu döndürdü."
          );
        }


        setPrivateAccessRequired(
          false
        );


        setReport(
          parsedReport
        );


        if (contextId) {
          setAnalysisContextId(
            contextId
          );


          initializeChat(
            currentAnalysisIsPR
          );

        } else {
          setAnalysisContextId(
            null
          );


          setChatError(
            "Chat bağlamı oluşturulamadı. Analizi yeniden çalıştırmayı dene."
          );
        }


      } catch (err) {
        console.error(err);


        setError(
          err.message ||
          "Analiz sırasında beklenmeyen bir hata oluştu."
        );


      } finally {
        setLoading(false);
      }
    };


  // =====================================================
  // ASK REPOPILOT
  // =====================================================

  const askRepoPilot =
    async (
      customQuestion = null
    ) => {

      const question =
        (
          customQuestion ??
          chatInput
        ).trim();


      if (!question) {
        return;
      }


      if (!analysisContextId) {
        setChatError(
          "Aktif analiz bağlamı bulunamadı. Repository veya Pull Request'i yeniden analiz et."
        );

        return;
      }


      if (chatLoading) {
        return;
      }


      const userMessage = {
        id:
          crypto.randomUUID(),

        role:
          "user",

        type:
          "normal",

        text:
          question,
      };


      setChatMessages(
        (current) => [
          ...current,
          userMessage,
        ]
      );


      setChatInput("");

      setChatError("");

      setChatLoading(true);


      try {
        const response =
          await fetch(
            `${AUTH_SERVER}/chat/ask`,
            {
              method:
                "POST",

              credentials:
                "include",

              headers: {
                "Content-Type":
                  "application/json",
              },

              body:
                JSON.stringify({
                  context_id:
                    analysisContextId,

                  question:
                    question,
                }),
            }
          );


        if (!response.ok) {
          const backendMessage =
            await getBackendError(
              response
            );


          if (
            response.status === 404
          ) {
            setAnalysisContextId(
              null
            );


            throw new Error(
              backendMessage ||
              (
                "Analiz bağlamının süresi doldu. " +
                "Repository/Pull Request'i yeniden analiz et."
              )
            );
          }


          throw new Error(
            backendMessage ||
            "Ask RepoPilot şu anda cevap veremiyor."
          );
        }


        const data =
          await response.json();


        const assistantMessage = {
          id:
            crypto.randomUUID(),

          role:
            "assistant",

          type:
            data.in_scope
              ? "normal"
              : "out-of-scope",

          text:
            data.answer,
        };


        setChatMessages(
          (current) => [
            ...current,
            assistantMessage,
          ]
        );


      } catch (err) {
        console.error(
          "Chat error:",
          err
        );


        setChatError(
          err.message ||
          "Ask RepoPilot sırasında bir hata oluştu."
        );


      } finally {
        setChatLoading(false);
      }
    };


  const handleChatKeyDown =
    (event) => {

      if (
        event.key === "Enter" &&
        !event.shiftKey
      ) {
        event.preventDefault();


        askRepoPilot();
      }
    };


  // =====================================================
  // OTHER UI HELPERS
  // =====================================================

  const startNewAnalysis =
    () => {

      setRepoUrl("");

      setReport(null);

      setError("");

      setPrivateAccessRequired(
        false
      );


      resetChat();


      window.scrollTo({
        top: 0,

        behavior: "smooth",
      });
    };


  const handleKeyDown =
    (event) => {

      if (
        event.key === "Enter" &&
        !loading
      ) {
        analyzeRepository();
      }
    };


  const getHealthClass =
    (score) => {

      if (score >= 90) {
        return "excellent";
      }


      if (score >= 80) {
        return "very-good";
      }


      if (score >= 70) {
        return "good";
      }


      if (score >= 60) {
        return "warning";
      }


      return "danger";
    };


  const getSeverityClass =
    (severity) => {

      return (
        severity?.toLowerCase()
        ||
        "info"
      );
    };


  const inputIsPullRequest =
    isPullRequestUrl(
      repoUrl
    );


  const reportIsPullRequest =
    Boolean(
      report &&
      (
        report.analysis_type
          === "pull_request"

        ||

        report.pull_request_number
      )
    );


  const scoreItems =
    report
      ? [
          {
            title:
              "Architecture",

            value:
              report.scores
                ?.architecture
              ?? 0,

            description:
              "Structure & maintainability",
          },

          {
            title:
              "Code Quality",

            value:
              report.scores
                ?.code_quality
              ?? 0,

            description:
              "Readability & reliability",
          },

          {
            title:
              "Security",

            value:
              report.scores
                ?.security
              ?? 0,

            description:
              "Security posture",
          },

          {
            title:
              "Testing",

            value:
              report.scores
                ?.testing
              ?? 0,

            description:
              "Test maturity",
          },
        ]

      : [];


  const chatSuggestions =
    reportIsPullRequest
      ? [
          "Bu PR'ın en kritik riski nedir?",
          "Bu PR merge edilmeye hazır mı?",
          "Hangi değişiklikler için test eklenmeli?",
        ]

      : [
          "Bu projedeki en kritik sorun nedir?",
          "Önce hangi problemi düzeltmeliyim?",
          "Testing score neden bu seviyede?",
        ];


  // =====================================================
  // RENDER
  // =====================================================

  return (
    <div className="app">

      {/* =================================================
          NAVBAR
      ================================================= */}

      <header className="navbar">

        <div className="brand">

          <div className="logo">
            RP
          </div>


          <div>

            <h2>
              RepoPilot
            </h2>


            <span>
              AI Repository Intelligence
            </span>

          </div>

        </div>


        <div className="navbar-actions">

          {authLoading ? (

            <div className="github-auth-loading">
              Checking GitHub...
            </div>

          ) : githubUser ? (

            <div className="github-user">

              <img
                src={
                  githubUser
                    .avatar_url
                }

                alt={
                  githubUser.login
                }
              />


              <div className="github-user-info">

                <span>
                  GitHub connected
                </span>


                <strong>
                  @{githubUser.login}
                </strong>

              </div>


              <button
                className="logout-button"

                onClick={
                  logoutGithub
                }
              >
                Logout
              </button>

            </div>

          ) : (

            <>
              <div
                style={{
                  padding:
                    "7px 10px",

                  border:
                    "1px solid #252d39",

                  borderRadius:
                    "999px",

                  color:
                    "#697487",

                  fontSize:
                    "10px",

                  fontWeight:
                    "700",

                  background:
                    "#0d1219",
                }}
              >
                Guest Mode
              </div>


              <button
                className="github-login-button"

                onClick={
                  signInWithGithub
                }
              >

                <span className="github-mark">
                  GH
                </span>

                Sign in with GitHub

              </button>
            </>

          )}

        </div>

      </header>


      <main>

        {/* =================================================
            HERO
        ================================================= */}

        <section className="hero">

          <div className="hero-badge">
            AI SOFTWARE ENGINEERING AGENT
          </div>


          <h1>

            Understand your codebase

            <span>
              {" "}
              before it becomes a problem.
            </span>

          </h1>


          <p className="hero-description">

            Analyze complete GitHub repositories
            or review individual Pull Requests for
            architecture, code quality, security,
            testing and engineering risks.

          </p>


          {githubUser ? (

            <div className="github-connected-message">

              <span className="connected-dot">
              </span>

              Connected as

              <strong>
                @{githubUser.login}
              </strong>

              · Public & private access

            </div>

          ) : (

            <div className="github-public-message">

              You're using RepoPilot in Guest Mode.

              {" "}

              Public repositories and Pull Requests
              work without an account.

              {" "}

              Connect GitHub for private access.

            </div>

          )}


          {authError && (

            <div className="error-box auth-error">
              {authError}
            </div>

          )}


          <div className="search-box">

            <div className="input-wrapper">

              <span className="github-icon">
                &lt;/&gt;
              </span>


              <input
                type="text"

                value={
                  repoUrl
                }

                onChange={(
                  event
                ) => {

                  setRepoUrl(
                    event.target.value
                  );


                  if (error) {
                    setError("");
                  }


                  if (
                    privateAccessRequired
                  ) {
                    setPrivateAccessRequired(
                      false
                    );
                  }
                }}

                onKeyDown={
                  handleKeyDown
                }

                placeholder=
                  "Repository URL or Pull Request URL"

                disabled={
                  loading
                }
              />

            </div>


            <button
              onClick={
                analyzeRepository
              }

              disabled={
                loading
              }
            >

              {loading
                ? (
                  inputIsPullRequest
                    ? "Reviewing PR..."
                    : "Analyzing..."
                )
                : (
                  inputIsPullRequest
                    ? "Review Pull Request"
                    : "Analyze Repository"
                )}

            </button>

          </div>


          {inputIsPullRequest &&
            !loading && (

            <div
              style={{
                width:
                  "fit-content",

                margin:
                  "12px auto 0",

                padding:
                  "7px 11px",

                border:
                  "1px solid rgba(139, 92, 246, 0.25)",

                borderRadius:
                  "999px",

                background:
                  "rgba(139, 92, 246, 0.06)",

                color:
                  "#9585c7",

                fontSize:
                  "10px",

                fontWeight:
                  "700",
              }}
            >

              Pull Request detected ·
              RepoPilot will review only
              the proposed changes

            </div>
          )}


          {loading && (

            <div className="loading-box">

              <div className="spinner">
              </div>


              <div>

                <strong>

                  {inputIsPullRequest
                    ? "RepoPilot is reviewing the Pull Request"
                    : "RepoPilot is analyzing the repository"}

                </strong>


                <p>

                  {inputIsPullRequest
                    ? (
                      "Reading changed files, diffs, bug risks, " +
                      "security issues and missing tests..."
                    )
                    : (
                      "Reading source files, architecture, " +
                      "engineering risks and testing maturity..."
                    )}

                </p>

              </div>

            </div>

          )}


          {error && (

            privateAccessRequired &&
            !githubUser

              ? (

                <div
                  className="error-box"

                  style={{
                    maxWidth:
                      "620px",

                    margin:
                      "25px auto 0",

                    padding:
                      "20px",

                    textAlign:
                      "left",
                  }}
                >

                  <strong
                    style={{
                      display:
                        "block",

                      marginBottom:
                        "7px",

                      color:
                        "#f0f2f5",

                      fontSize:
                        "13px",
                    }}
                  >

                    Private GitHub access required

                  </strong>


                  <p
                    style={{
                      margin:
                        "0 0 15px",

                      lineHeight:
                        "1.6",
                    }}
                  >

                    {error}

                  </p>


                  <button
                    className="github-login-button"

                    onClick={
                      signInWithGithub
                    }
                  >

                    <span className="github-mark">
                      GH
                    </span>

                    Sign in with GitHub

                  </button>

                </div>

              )

              : (

                <div className="error-box">
                  {error}
                </div>

              )
          )}

        </section>


        {/* =================================================
            REPORT
        ================================================= */}

        {report && (

          <section className="dashboard">

            <div className="new-analysis-wrapper">

              <button
                className="new-analysis-button"

                onClick={
                  startNewAnalysis
                }
              >
                + New Analysis
              </button>

            </div>


            {/* =============================================
                REPORT HEADER
            ============================================= */}

            <div className="report-header">

              <div>

                <p className="section-label">

                  {reportIsPullRequest
                    ? "PULL REQUEST REVIEW"
                    : "REPOSITORY ANALYSIS"}

                </p>


                <h2>

                  {report.repository}


                  {reportIsPullRequest &&
                    report
                      .pull_request_number

                    ? (
                      ` · PR #${report.pull_request_number}`
                    )

                    : ""}

                </h2>


                {reportIsPullRequest &&
                  report
                    .pull_request_title && (

                  <h3
                    style={{
                      margin:
                        "12px 0 8px",

                      color:
                        "#e3e6eb",

                      fontSize:
                        "18px",
                    }}
                  >

                    {
                      report
                        .pull_request_title
                    }

                  </h3>

                )}


                <p className="project-summary">

                  {
                    report
                      .project_summary
                  }

                </p>


                <div className="metadata">

                  {!reportIsPullRequest &&
                    report
                      .primary_language && (

                    <span>

                      Language:{" "}

                      {
                        report
                          .primary_language
                      }

                    </span>

                  )}


                  {!reportIsPullRequest &&
                    report.maturity && (

                    <span>

                      Maturity:{" "}

                      {
                        report
                          .maturity
                      }

                    </span>

                  )}


                  {reportIsPullRequest &&
                    report
                      .base_branch && (

                    <span>

                      Target:{" "}

                      {
                        report
                          .base_branch
                      }

                    </span>

                  )}


                  {reportIsPullRequest &&
                    report
                      .head_branch && (

                    <span>

                      Source:{" "}

                      {
                        report
                          .head_branch
                      }

                    </span>

                  )}

                </div>

              </div>


              <div
                className={
                  `health-score ${getHealthClass(
                    report.health_score
                  )}`
                }
              >

                <span className="health-number">

                  {
                    report
                      .health_score
                  }

                </span>


                <span className="health-total">
                  /100
                </span>


                <p>

                  {reportIsPullRequest
                    ? "PR Quality Score"
                    : "Health Score"}

                </p>


                <strong>
                  {report.rating}
                </strong>

              </div>

            </div>


            {/* =============================================
                PR SUMMARY
            ============================================= */}

            {reportIsPullRequest && (

              <div
                style={{
                  display:
                    "grid",

                  gridTemplateColumns:
                    "repeat(auto-fit, minmax(150px, 1fr))",

                  gap:
                    "12px",

                  margin:
                    "18px 0 26px",
                }}
              >

                <div className="score-card">

                  <div
                    style={{
                      color:
                        "#737f91",

                      fontSize:
                        "10px",

                      marginBottom:
                        "7px",
                    }}
                  >
                    BRANCH
                  </div>


                  <strong
                    style={{
                      color:
                        "#e2e6ec",

                      fontSize:
                        "12px",
                    }}
                  >

                    {
                      report
                        .head_branch
                      || "Unknown"
                    }

                    {" → "}

                    {
                      report
                        .base_branch
                      || "Unknown"
                    }

                  </strong>

                </div>


                <div className="score-card">

                  <div
                    style={{
                      color:
                        "#737f91",

                      fontSize:
                        "10px",

                      marginBottom:
                        "7px",
                    }}
                  >
                    CHANGED FILES
                  </div>


                  <strong
                    style={{
                      fontSize:
                        "20px",
                    }}
                  >

                    {
                      report
                        .changed_files_count
                      ?? 0
                    }

                  </strong>

                </div>


                <div className="score-card">

                  <div
                    style={{
                      color:
                        "#737f91",

                      fontSize:
                        "10px",

                      marginBottom:
                        "7px",
                    }}
                  >
                    ADDITIONS
                  </div>


                  <strong
                    style={{
                      color:
                        "#58d68d",

                      fontSize:
                        "20px",
                    }}
                  >

                    +

                    {
                      report
                        .additions
                      ?? 0
                    }

                  </strong>

                </div>


                <div className="score-card">

                  <div
                    style={{
                      color:
                        "#737f91",

                      fontSize:
                        "10px",

                      marginBottom:
                        "7px",
                    }}
                  >
                    DELETIONS
                  </div>


                  <strong
                    style={{
                      color:
                        "#ff8181",

                      fontSize:
                        "20px",
                    }}
                  >

                    -

                    {
                      report
                        .deletions
                      ?? 0
                    }

                  </strong>

                </div>

              </div>

            )}


            {/* =============================================
                TECHNOLOGIES
            ============================================= */}

            {report
              .technologies
              ?.length > 0 && (

              <div className="technologies">

                {
                  report
                    .technologies
                    .map(
                      (
                        technology,
                        index
                      ) => (

                        <span key={index}>
                          {technology}
                        </span>

                      )
                    )
                }

              </div>

            )}


            {/* =============================================
                SCORES
            ============================================= */}

            <div className="score-grid">

              {
                scoreItems.map(
                  (score) => (

                    <div
                      className="score-card"

                      key={
                        score.title
                      }
                    >

                      <div className="score-card-header">

                        <div>

                          <h3>
                            {score.title}
                          </h3>


                          <p>
                            {
                              score
                                .description
                            }
                          </p>

                        </div>


                        <strong>

                          {
                            score.value
                          }

                          /10

                        </strong>

                      </div>


                      <div className="progress-track">

                        <div
                          className="progress-bar"

                          style={{
                            width:
                              `${score.value * 10}%`,
                          }}
                        >
                        </div>

                      </div>

                    </div>

                  )
                )
              }

            </div>


            {/* =============================================
                POSITIVE FINDINGS
            ============================================= */}

            {report
              .positive_findings
              ?.length > 0 && (

              <section className="report-section positive-section">

                <div className="section-heading">

                  <div>

                    <p className="section-label">
                      STRENGTHS
                    </p>


                    <h2>
                      Positive Findings
                    </h2>

                  </div>


                  <span className="count">

                    {
                      report
                        .positive_findings
                        .length
                    }

                  </span>

                </div>


                <div className="positive-grid">

                  {
                    report
                      .positive_findings
                      .map(
                        (
                          finding,
                          index
                        ) => (

                          <div
                            className="positive-card"

                            key={index}
                          >

                            <div className="check">
                              ✓
                            </div>


                            <p>
                              {finding}
                            </p>

                          </div>

                        )
                      )
                  }

                </div>

              </section>

            )}


            {/* =============================================
                ISSUES
            ============================================= */}

            <section className="report-section">

              <div className="section-heading">

                <div>

                  <p className="section-label">

                    {reportIsPullRequest
                      ? "CODE REVIEW"
                      : "ENGINEERING REVIEW"}

                  </p>


                  <h2>
                    Issues & Risks
                  </h2>

                </div>


                <span className="count">

                  {
                    report
                      .issues
                      ?.length
                    || 0
                  }

                </span>

              </div>


              <div className="issues-list">

                {report
                  .issues
                  ?.length > 0

                  ? (

                    report
                      .issues
                      .map(
                        (
                          issue,
                          index
                        ) => (

                          <article
                            className="issue-card"

                            key={index}
                          >

                            <div className="issue-top">

                              <div className="issue-badges">

                                <span
                                  className={
                                    `severity ${getSeverityClass(
                                      issue.severity
                                    )}`
                                  }
                                >

                                  {
                                    issue
                                      .severity
                                  }

                                </span>


                                <span className="issue-type">

                                  {
                                    issue
                                      .issue_type
                                  }

                                </span>


                                <span className="category">

                                  {
                                    issue
                                      .category
                                  }

                                </span>

                              </div>


                              <span className="issue-number">

                                #

                                {
                                  String(
                                    index + 1
                                  ).padStart(
                                    2,
                                    "0"
                                  )
                                }

                              </span>

                            </div>


                            <h3>
                              {
                                issue
                                  .problem
                              }
                            </h3>


                            {(issue.file ||
                              issue.line) && (

                              <div className="location">

                                {issue.file && (

                                  <span>
                                    {
                                      issue.file
                                    }
                                  </span>

                                )}


                                {issue.line && (

                                  <span>

                                    Line{" "}

                                    {
                                      issue.line
                                    }

                                  </span>

                                )}

                              </div>

                            )}


                            <div className="issue-detail">

                              <span className="detail-title">
                                Evidence
                              </span>


                              <code>
                                {
                                  issue
                                    .evidence
                                }
                              </code>

                            </div>


                            {issue
                              .why_it_matters && (

                              <div className="issue-detail">

                                <span className="detail-title">
                                  Why it matters
                                </span>


                                <p>
                                  {
                                    issue
                                      .why_it_matters
                                  }
                                </p>

                              </div>

                            )}


                            <div className="recommendation">

                              <span className="detail-title">
                                Recommendation
                              </span>


                              <p>
                                {
                                  issue
                                    .recommendation
                                }
                              </p>

                            </div>

                          </article>

                        )
                      )

                  ) : (

                    <div className="empty-state">

                      No significant issues detected
                      in the analyzed changes.

                    </div>

                  )}

              </div>

            </section>


            {/* =============================================
                RECOMMENDATIONS
            ============================================= */}

            {report
              .top_recommendations
              ?.length > 0 && (

              <section className="report-section">

                <div className="section-heading">

                  <div>

                    <p className="section-label">
                      ACTION PLAN
                    </p>


                    <h2>
                      Top Recommendations
                    </h2>

                  </div>

                </div>


                <div className="recommendations-list">

                  {
                    report
                      .top_recommendations
                      .map(
                        (
                          recommendation,
                          index
                        ) => (

                          <div
                            className="recommendation-card"

                            key={index}
                          >

                            <span className="recommendation-number">

                              {
                                String(
                                  index + 1
                                ).padStart(
                                  2,
                                  "0"
                                )
                              }

                            </span>


                            <p>
                              {
                                recommendation
                              }
                            </p>

                          </div>

                        )
                      )
                  }

                </div>

              </section>

            )}


            {/* =============================================
                CAVEATS
            ============================================= */}

            {report
              .caveats
              ?.length > 0 && (

              <section className="caveats">

                <h3>
                  Analysis Notes
                </h3>


                {
                  report
                    .caveats
                    .map(
                      (
                        caveat,
                        index
                      ) => (

                        <p key={index}>
                          {caveat}
                        </p>

                      )
                    )
                }

              </section>

            )}


            {/* =================================================
                ASK REPOPILOT
            ================================================= */}

            <section
              style={{
                marginTop:
                  "50px",

                marginBottom:
                  "30px",

                border:
                  "1px solid #242d3a",

                borderRadius:
                  "18px",

                overflow:
                  "hidden",

                background:
                  "linear-gradient(180deg, #0e141d 0%, #0b1017 100%)",

                boxShadow:
                  "0 25px 70px rgba(0, 0, 0, 0.20)",
              }}
            >

              {/* CHAT HEADER */}

              <div
                style={{
                  padding:
                    "22px 24px",

                  borderBottom:
                    "1px solid #222a36",

                  display:
                    "flex",

                  alignItems:
                    "center",

                  justifyContent:
                    "space-between",

                  gap:
                    "20px",
                }}
              >

                <div>

                  <p
                    className="section-label"

                    style={{
                      marginBottom:
                        "5px",
                    }}
                  >
                    CONTEXT-AWARE AI
                  </p>


                  <h2
                    style={{
                      margin:
                        "0",

                      fontSize:
                        "20px",

                      color:
                        "#eef1f6",
                    }}
                  >
                    Ask RepoPilot
                  </h2>


                  <p
                    style={{
                      margin:
                        "7px 0 0",

                      color:
                        "#667185",

                      fontSize:
                        "11px",

                      lineHeight:
                        "1.6",
                    }}
                  >

                    {reportIsPullRequest
                      ? (
                        "Ask questions only about this Pull Request and its analyzed changes."
                      )
                      : (
                        "Ask questions only about this repository and the analyzed codebase."
                      )}

                  </p>

                </div>


                <div
                  style={{
                    display:
                      "flex",

                    alignItems:
                      "center",

                    gap:
                      "7px",

                    padding:
                      "7px 10px",

                    border:
                      "1px solid rgba(72, 209, 130, 0.18)",

                    borderRadius:
                      "999px",

                    color:
                      "#64c98f",

                    background:
                      "rgba(72, 209, 130, 0.05)",

                    fontSize:
                      "9px",

                    fontWeight:
                      "700",

                    whiteSpace:
                      "nowrap",
                  }}
                >

                  <span
                    style={{
                      width:
                        "6px",

                      height:
                        "6px",

                      borderRadius:
                        "50%",

                      background:
                        "#48d182",

                      boxShadow:
                        "0 0 9px rgba(72, 209, 130, 0.7)",
                    }}
                  >
                  </span>

                  CONTEXT LOCKED

                </div>

              </div>


              {/* SCOPE INFORMATION */}

              <div
                style={{
                  margin:
                    "18px 20px 0",

                  padding:
                    "12px 14px",

                  border:
                    "1px solid rgba(139, 92, 246, 0.16)",

                  borderRadius:
                    "11px",

                  background:
                    "rgba(139, 92, 246, 0.035)",

                  color:
                    "#7e7793",

                  fontSize:
                    "10px",

                  lineHeight:
                    "1.6",
                }}
              >

                <strong
                  style={{
                    color:
                      "#9b8bc4",
                  }}
                >
                  Scope protection:
                </strong>

                {" "}

                Ask RepoPilot will only answer
                questions supported by this analysis.

                {" "}

                Unrelated questions or information
                not found in the analyzed context
                will be rejected.

              </div>


              {/* SUGGESTIONS */}

              {analysisContextId && (

                <div
                  style={{
                    display:
                      "flex",

                    flexWrap:
                      "wrap",

                    gap:
                      "8px",

                    padding:
                      "17px 20px 0",
                  }}
                >

                  {
                    chatSuggestions.map(
                      (
                        suggestion,
                        index
                      ) => (

                        <button
                          key={index}

                          type="button"

                          disabled={
                            chatLoading
                          }

                          onClick={() =>
                            askRepoPilot(
                              suggestion
                            )
                          }

                          style={{
                            border:
                              "1px solid #293341",

                            borderRadius:
                              "999px",

                            background:
                              "#111822",

                            color:
                              "#8895a7",

                            padding:
                              "8px 11px",

                            cursor:
                              chatLoading
                                ? "not-allowed"
                                : "pointer",

                            fontSize:
                              "10px",

                            fontWeight:
                              "600",

                            opacity:
                              chatLoading
                                ? 0.6
                                : 1,
                          }}
                        >

                          {suggestion}

                        </button>

                      )
                    )
                  }

                </div>

              )}


              {/* CHAT MESSAGES */}

              <div
                style={{
                  minHeight:
                    "220px",

                  maxHeight:
                    "520px",

                  overflowY:
                    "auto",

                  padding:
                    "22px 20px",

                  display:
                    "flex",

                  flexDirection:
                    "column",

                  gap:
                    "14px",
                }}
              >

                {!analysisContextId &&
                  chatMessages.length === 0 && (

                  <div
                    style={{
                      padding:
                        "25px",

                      textAlign:
                        "center",

                      color:
                        "#657083",

                      fontSize:
                        "11px",
                    }}
                  >

                    Chat context is unavailable.
                    Run the analysis again to enable
                    Ask RepoPilot.

                  </div>

                )}


                {
                  chatMessages.map(
                    (message) => {

                      const isUser =
                        message.role
                          === "user";


                      const isOutOfScope =
                        message.type
                          === "out-of-scope";


                      return (

                        <div
                          key={
                            message.id
                          }

                          style={{
                            alignSelf:
                              isUser
                                ? "flex-end"
                                : "flex-start",

                            width:
                              "fit-content",

                            maxWidth:
                              "82%",

                            padding:
                              "12px 14px",

                            borderRadius:
                              isUser
                                ? "14px 14px 4px 14px"
                                : "14px 14px 14px 4px",

                            border:
                              isOutOfScope
                                ? (
                                  "1px solid rgba(255, 180, 80, 0.24)"
                                )
                                : (
                                  isUser
                                    ? "1px solid rgba(139, 92, 246, 0.28)"
                                    : "1px solid #28313e"
                                ),

                            background:
                              isOutOfScope
                                ? (
                                  "rgba(255, 170, 60, 0.045)"
                                )
                                : (
                                  isUser
                                    ? "rgba(126, 87, 194, 0.13)"
                                    : "#121923"
                                ),

                            color:
                              isOutOfScope
                                ? "#c7a56f"
                                : "#cdd3dd",

                            fontSize:
                              "12px",

                            lineHeight:
                              "1.7",

                            whiteSpace:
                              "pre-wrap",

                            overflowWrap:
                              "anywhere",
                          }}
                        >

                          {!isUser && (

                            <div
                              style={{
                                marginBottom:
                                  "5px",

                                color:
                                  isOutOfScope
                                    ? "#d1a45e"
                                    : "#9381c4",

                                fontSize:
                                  "9px",

                                fontWeight:
                                  "800",

                                letterSpacing:
                                  "0.07em",
                              }}
                            >

                              {isOutOfScope
                                ? "OUT OF SCOPE"
                                : "REPOPILOT"}

                            </div>

                          )}


                          {message.text}

                        </div>

                      );
                    }
                  )
                }


                {chatLoading && (

                  <div
                    style={{
                      alignSelf:
                        "flex-start",

                      padding:
                        "12px 15px",

                      border:
                        "1px solid #28313e",

                      borderRadius:
                        "14px 14px 14px 4px",

                      background:
                        "#121923",

                      color:
                        "#788496",

                      fontSize:
                        "11px",
                    }}
                  >

                    RepoPilot is reading the
                    analysis context...

                  </div>

                )}


                <div
                  ref={
                    chatBottomRef
                  }
                >
                </div>

              </div>


              {/* CHAT ERROR */}

              {chatError && (

                <div
                  style={{
                    margin:
                      "0 20px 14px",

                    padding:
                      "10px 12px",

                    border:
                      "1px solid rgba(255, 100, 100, 0.22)",

                    borderRadius:
                      "9px",

                    background:
                      "rgba(255, 80, 80, 0.04)",

                    color:
                      "#c98282",

                    fontSize:
                      "10px",
                  }}
                >

                  {chatError}

                </div>

              )}


              {/* CHAT INPUT */}

              <div
                style={{
                  padding:
                    "16px 20px 20px",

                  borderTop:
                    "1px solid #202834",
                }}
              >

                <div
                  style={{
                    display:
                      "flex",

                    alignItems:
                      "flex-end",

                    gap:
                      "10px",

                    padding:
                      "9px",

                    border:
                      "1px solid #293341",

                    borderRadius:
                      "13px",

                    background:
                      "#0b1119",
                  }}
                >

                  <textarea
                    value={
                      chatInput
                    }

                    onChange={(
                      event
                    ) =>
                      setChatInput(
                        event.target.value
                      )
                    }

                    onKeyDown={
                      handleChatKeyDown
                    }

                    disabled={
                      chatLoading ||
                      !analysisContextId
                    }

                    placeholder={
                      reportIsPullRequest
                        ? "Ask about this Pull Request..."
                        : "Ask about this repository..."
                    }

                    rows={1}

                    maxLength={2000}

                    style={{
                      flex:
                        "1",

                      minHeight:
                        "38px",

                      maxHeight:
                        "130px",

                      resize:
                        "vertical",

                      border:
                        "none",

                      outline:
                        "none",

                      background:
                        "transparent",

                      color:
                        "#dbe0e8",

                      fontFamily:
                        "inherit",

                      fontSize:
                        "12px",

                      lineHeight:
                        "1.6",

                      padding:
                        "9px 10px",
                    }}
                  />


                  <button
                    type="button"

                    onClick={() =>
                      askRepoPilot()
                    }

                    disabled={
                      chatLoading ||
                      !analysisContextId ||
                      !chatInput.trim()
                    }

                    style={{
                      minWidth:
                        "76px",

                      height:
                        "38px",

                      border:
                        "1px solid rgba(139, 92, 246, 0.4)",

                      borderRadius:
                        "9px",

                      background:
                        (
                          chatLoading ||
                          !analysisContextId ||
                          !chatInput.trim()
                        )
                          ? "#171d27"
                          : "rgba(126, 87, 194, 0.19)",

                      color:
                        (
                          chatLoading ||
                          !analysisContextId ||
                          !chatInput.trim()
                        )
                          ? "#525d6e"
                          : "#b9a7ec",

                      cursor:
                        (
                          chatLoading ||
                          !analysisContextId ||
                          !chatInput.trim()
                        )
                          ? "not-allowed"
                          : "pointer",

                      fontSize:
                        "10px",

                      fontWeight:
                        "800",
                    }}
                  >

                    {chatLoading
                      ? "Thinking..."
                      : "Ask"}

                  </button>

                </div>


                <div
                  style={{
                    display:
                      "flex",

                    justifyContent:
                      "space-between",

                    gap:
                      "15px",

                    marginTop:
                      "8px",

                    color:
                      "#4e5969",

                    fontSize:
                      "9px",
                  }}
                >

                  <span>
                    Enter to send ·
                    Shift + Enter for new line
                  </span>


                  <span>
                    {
                      chatInput.length
                    }
                    /2000
                  </span>

                </div>

              </div>

            </section>

          </section>

        )}

      </main>


      <footer>
        RepoPilot AI · Software Engineering Intelligence
      </footer>

    </div>
  );
}


export default App;