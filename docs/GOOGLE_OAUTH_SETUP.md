# ADFIP — Google OAuth 2.0 / OpenID Connect Setup Guide

This document outlines the step-by-step configuration required in the Google Cloud Console to enable production Google OAuth authentication for the Autonomous Digital Forensics Investigation Platform (ADFIP).

---

## 1. Google Cloud Project Setup

1. Open the [Google Cloud Console](https://console.cloud.google.com/).
2. Select an existing project or create a new project (e.g., `adfip-forensics`).
3. Navigate to **APIs & Services** &rarr; **Credentials**.

---

## 2. Configure OAuth Consent Screen

1. In the left navigation, select **OAuth consent screen**.
2. Select **User Type**:
   * **Internal**: Recommended if your organization uses Google Workspace (restricts login to authorized enterprise investigators).
   * **External**: If external investigators or agency partners require access (starts in Testing mode).
3. Click **Create** and complete the App Information:
   * **App name**: `ADFIP Forensic Platform`
   * **User support email**: Your support or admin email.
   * **Developer contact information**: Your administration contact email.
4. **Scopes**:
   Click **Add or Remove Scopes** and select the three standard OpenID Connect scopes:
   * `.../auth/userinfo.email` (`openid`, `email`): View user's email address.
   * `.../auth/userinfo.profile` (`profile`): View user's basic profile (name, profile picture).
   * `openid`: Associate you with your personal info on Google.
5. If in **Testing** mode with External user type, add the email addresses of designated test investigators under **Test users**.
6. Save and continue.

---

## 3. Create OAuth 2.0 Client Credentials

1. Navigate to **APIs & Services** &rarr; **Credentials**.
2. Click **Create Credentials** &rarr; **OAuth client ID**.
3. Select **Application type**: **Web application**.
4. Set **Name**: `ADFIP Desktop / Web Workstation`.
5. **Authorized JavaScript origins**:
   * `http://localhost:5173` (Vite dev server)
   * `http://localhost:8000` (FastAPI backend)
   * `http://127.0.0.1:5173`
   * `http://127.0.0.1:8000`
   * `tauri://localhost` (Tauri v2 desktop shell)
   * `http://tauri.localhost`
   * `https://tauri.localhost`
6. **Authorized redirect URIs**:
   Add the canonical ADFIP backend callback endpoint:
   * `http://localhost:8000/api/v1/auth/google/callback`
   * `http://127.0.0.1:8000/api/v1/auth/google/callback`
   *(For remote or cloud production deployments, replace `localhost:8000` with your canonical backend authority, e.g. `https://adfip.agency.gov/api/v1/auth/google/callback`)*
7. Click **Create**.
8. Copy the **Client ID** and **Client Secret**.

---

## 4. Server Configuration (`.env`)

Add the Google OAuth credentials to your local or server `.env` file (located in repository root):

```bash
# Google OAuth 2.0 Credentials
GOOGLE_CLIENT_ID="<YOUR_CLIENT_ID>.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET="<YOUR_CLIENT_SECRET>"
GOOGLE_REDIRECT_URI="http://localhost:8000/api/v1/auth/google/callback"
```

> **Security Note:** Never commit `.env` or client secrets to version control. The repository ignores `.env` by default and provides safe placeholders in `.env.example`.

---

## 5. Architectural Security Highlights

* **PKCE Enforcement:** ADFIP implements Proof Key for Code Exchange (RFC 7636) with SHA-256 (`S256`) challenges on all authorization requests.
* **Anti-CSRF Protection:** Cryptographically secure 32-byte state tokens are tracked in `oauth_states`, enforced for single use, and strictly expire after 10 minutes.
* **Single-Use Exchange Tickets:** Google tokens are never exposed in browser URLs, redirect fragments, or browser history. Upon successful callback, ADFIP issues a high-entropy, 60-second exchange code (`OAuthExchangeCode`) that the frontend exchanges for a signed Bearer JWT via POST.
* **Account Takeover Prevention (Scenario C):** If an existing password-authenticated account matches a Google email but is not yet linked, automated account takeover is blocked with HTTP 409 Conflict. The investigator must authenticate with their password and link their Google account from Settings.
* **Least Privilege:** New users authenticated via Google default strictly to the `INVESTIGATOR` role. Administrative privileges can only be elevated by an existing Administrator.
* **Lockout Protection:** An account cannot be unlinked from Google if no password has been configured, preventing permanent investigator lockout.
