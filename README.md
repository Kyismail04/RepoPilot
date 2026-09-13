# RepoPilot 🚀

**Yapay Zekâ Destekli GitHub Repository ve Pull Request Analiz Platformu**

RepoPilot; GitHub repository'lerini ve Pull Request'leri analiz ederek kod kalitesi, yazılım mimarisi, güvenlik riskleri, test eksiklikleri ve teknik problemler hakkında yapılandırılmış raporlar oluşturan yapay zekâ destekli bir yazılım mühendisliği aracıdır.

Public repository'ler giriş yapmadan analiz edilebilir. Private repository'ler için GitHub OAuth desteği bulunur.

---

## ✨ Özellikler

- 🔍 Public ve private GitHub repository analizi
- 🔀 Pull Request inceleme
- 🏗️ Mimari değerlendirme
- 🧹 Kod kalitesi analizi
- 🔐 Güvenlik riski tespiti
- 🧪 Test olgunluğu değerlendirmesi
- 📊 0–100 Health Score
- ✅ CONFIRMED ISSUE / POTENTIAL ISSUE ayrımı
- 👤 Guest Mode
- 🔑 GitHub OAuth
- 💬 Analiz bağlamına özel Ask RepoPilot chat

---

## 🔍 Repository Analizi

Kullanıcı bir GitHub repository URL'si girer:

```text
https://github.com/kullanici/proje
```

RepoPilot repository içerisinden önemli dosyaları toplar ve AI Agent ile analiz eder.

Oluşturulan raporda:

```text
Health Score: 78 / 100

Architecture: 7 / 10
Code Quality: 8 / 10
Security: 9 / 10
Testing: 5 / 10
```

gibi sonuçlar gösterilir.

Ayrıca tespit edilen sorunlar için:

- Önem seviyesi
- Dosya
- Satır
- Kanıt
- Problemin etkisi
- Çözüm önerisi

sunulur.

---

## 🔀 Pull Request Review

RepoPilot Pull Request URL'lerini otomatik olarak algılar.

```text
https://github.com/kullanici/proje/pull/12
```

Bu durumda bütün repository yerine yalnızca PR tarafından yapılan değişiklikler incelenir.

Kontrol edilen konular arasında:

- Bug riskleri
- Security sorunları
- Breaking change
- Logic error
- Eksik testler
- Error handling
- Code quality
- Maintainability

bulunur.

PR raporunda ayrıca:

```text
PR #12

feature/login → main

Changed Files: 8
Additions: +214
Deletions: -67

PR Quality Score: 84 / 100
```

gibi bilgiler gösterilir.

---

## 💬 Ask RepoPilot

Analiz tamamlandıktan sonra kullanıcı incelenen repository veya Pull Request hakkında sorular sorabilir.

Örnek:

```text
Bu projedeki en kritik problem nedir?
```

```text
Testing score neden düşük?
```

```text
Bu security problemini nasıl düzeltebilirim?
```

```text
Bu Pull Request merge edilmeye hazır mı?
```

Ask RepoPilot yalnızca aktif analiz bağlamıyla ilgili soruları cevaplar.

Konu dışındaki sorular reddedilir.

---

## 👤 Guest Mode ve Private Repository

GitHub hesabıyla giriş yapmak zorunlu değildir.

```text
Guest Mode
    ↓
Public Repository ✅
Public Pull Request ✅

Private Repository
    ↓
GitHub Login gerekli
```

Kullanıcı GitHub hesabıyla giriş yaptığında yalnızca kendi hesabının erişebildiği private repository'leri analiz edebilir.

---

## 🔐 Güvenlik

GitHub OAuth token hiçbir zaman:

```text
Frontend'e ❌
Gemini'ye ❌
AI Prompt'a ❌

GitHub API'ye ✅
```

gönderilir.

OAuth token yalnızca backend tarafında GitHub API isteklerinde kullanılır.

Ayrıca:

- HTTP-only cookie kullanılır.
- OAuth `state` doğrulaması yapılır.
- Chat context'leri kullanıcılar arasında izole edilir.
- Repository içeriği güvenilmeyen veri olarak değerlendirilir.
- Kaynak kod içerisindeki talimatlar AI komutu olarak çalıştırılmaz.

---

## 🏗️ Mimari

```text
┌───────────────────────┐
│    React + Vite UI    │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│   FastAPI Backend     │
└───────────┬───────────┘
            │
     ┌──────┼─────────┐
     │      │         │
     ▼      ▼         ▼
 GitHub   GitHub   Ask RepoPilot
 OAuth     API       Chat
     │      │
     └──┬───┘
        ▼
┌───────────────────────┐
│   Google ADK Agent    │
│       Gemini          │
└───────────────────────┘
```

---

## 🛠️ Kullanılan Teknolojiler

**Backend**

- Python
- FastAPI
- Google ADK
- Gemini
- GitHub REST API
- GitHub OAuth

**Frontend**

- React
- Vite
- JavaScript
- CSS

---

## 📁 Proje Yapısı

```text
repopilot/
│
├── agent.py
├── auth_server.py
├── chat_service.py
├── __init__.py
│
├── tools/
│   ├── github_tools.py
│   └── github_pr_tools.py
│
├── frontend/
│   └── src/
│       ├── App.jsx
│       ├── App.css
│       ├── index.css
│       └── main.jsx
│
├── .gitignore
└── README.md
```

---

## 🚀 Kurulum

Repository'yi klonla:

```bash
git clone https://github.com/Kyismail04/RepoPilot.git
```

Python sanal ortamını oluştur:

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

Python bağımlılıklarını yükle:

```bash
pip install -r repopilot/requirements.txt
```

Frontend bağımlılıklarını yükle:

```bash
cd repopilot/frontend
npm install
```

---

## 🔑 Ortam Değişkenleri

`repopilot/.env` dosyası oluştur:

```env
GEMINI_API_KEY=your_gemini_api_key

GITHUB_CLIENT_ID=your_github_client_id
GITHUB_CLIENT_SECRET=your_github_client_secret

GITHUB_REDIRECT_URI=http://localhost:8001/auth/github/callback
REPOPILOT_FRONTEND_URL=http://localhost:5174

ADK_API_URL=http://127.0.0.1:8000
```

`.env` dosyası GitHub'a yüklenmemelidir.

---

## ▶️ Çalıştırma

### ADK Backend

```bash
adk api_server --auto_create_session --allow_origins="*" .
```

```text
http://127.0.0.1:8000
```

### RepoPilot Backend

```bash
python -m uvicorn repopilot.auth_server:app --host 127.0.0.1 --port 8001
```

```text
http://127.0.0.1:8001
```

### Frontend

```bash
cd repopilot/frontend
npm run dev -- --port 5174
```

Tarayıcı:

```text
http://localhost:5174
```

---

## ⚠️ Not

RepoPilot bütün repository'yi kontrolsüz şekilde AI modeline göndermez.

Belirli sayıda önemli dosyadan bir snapshot oluşturulur. Bu nedenle özellikle büyük repository'lerde bazı dosyalar analiz dışında kalabilir.

RepoPilot profesyonel security audit, penetration test veya insan code review sürecinin yerine geçmez.

---

## 👨‍💻 Geliştirici

**Kyismail04**

GitHub:

```text
https://github.com/Kyismail04
```

---

## ⭐ RepoPilot

AI destekli repository analizi ve Pull Request review sistemi.