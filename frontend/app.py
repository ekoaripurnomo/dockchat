"""dockchat Streamlit frontend.

Run with:
    streamlit run frontend/app.py

Requires the backend running (default http://localhost:8080). Configure the
backend URL via the API_BASE_URL environment variable.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import requests
import streamlit as st

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8080")

# Maximum number of chat messages to keep and send as context to the model.
MAX_HISTORY = 50

st.set_page_config(page_title="dockchat", page_icon="🐳", layout="wide")


# --------------------------------------------------------------------------- #
# HTTP helpers
# --------------------------------------------------------------------------- #
def auth_headers() -> Dict[str, str]:
    token = st.session_state.get("access_token")
    return {"Authorization": f"Bearer {token}"} if token else {}


def api_post(path: str, json: Optional[dict] = None, auth: bool = True,
             timeout: int = 120) -> requests.Response:
    return requests.post(
        f"{API_BASE_URL}{path}", json=json, headers=auth_headers() if auth else {}, timeout=timeout
    )


def api_get(path: str, auth: bool = True) -> requests.Response:
    return requests.get(f"{API_BASE_URL}{path}", headers=auth_headers() if auth else {}, timeout=60)


def api_delete(path: str, auth: bool = True) -> requests.Response:
    return requests.delete(f"{API_BASE_URL}{path}", headers=auth_headers() if auth else {}, timeout=60)


def load_chat_history() -> None:
    """Load persisted chat history from the backend into the session."""
    try:
        resp = api_get("/api/chat/history")
        if resp.status_code == 200:
            msgs = resp.json()
            st.session_state.messages = [
                {"role": m["role"], "content": m["content"]} for m in msgs
            ]
    except requests.RequestException:
        pass


def parse_json(resp: requests.Response) -> Any:
    """Parse a response body as JSON, returning None if it isn't valid JSON.

    The backend always returns JSON, so a non-JSON body means the request hit
    something else (wrong URL, a proxy, an unhandled error). Callers use the
    None result to show a clear message instead of a raw JSON decode error.
    """
    try:
        return resp.json()
    except ValueError:
        return None


def show_response_error(resp: requests.Response, fallback: str) -> None:
    """Render a helpful error for a non-200 or non-JSON response."""
    body = parse_json(resp)
    if isinstance(body, dict) and body.get("detail"):
        st.error(f"{fallback}: {body['detail']}")
    else:
        snippet = (resp.text or "").strip()[:200]
        st.error(
            f"{fallback} (HTTP {resp.status_code}). "
            f"The backend at {API_BASE_URL} returned an unexpected response."
            + (f"\n\n{snippet}" if snippet else "")
        )


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #
def render_auth() -> None:
    st.title("🐳 dockchat")
    st.caption("Chat-controlled Docker container management with AI-powered scaffolding")

    tab_login, tab_register = st.tabs(["🔐 Login", "📝 Register"])

    with tab_login:
        username = st.text_input("Username", key="login_username")
        password = st.text_input("Password", type="password", key="login_password")
        if st.button("Login", type="primary"):
            if not (username and password):
                st.error("Please fill in all fields")
            else:
                try:
                    resp = api_post("/api/auth/login",
                                    {"username": username, "password": password}, auth=False)
                    if resp.status_code == 200:
                        _store_session(resp.json())
                        st.rerun()
                    else:
                        st.error(resp.json().get("detail", "Login failed"))
                except requests.RequestException as exc:
                    st.error(f"Cannot reach backend: {exc}")

    with tab_register:
        r_username = st.text_input("Username", key="reg_username")
        r_email = st.text_input("Email", key="reg_email")
        r_password = st.text_input("Password", type="password", key="reg_password",
                                   help="Min 8 chars, upper + lower + digit")
        r_confirm = st.text_input("Confirm Password", type="password", key="reg_confirm")
        if st.button("Register", type="primary"):
            if not all([r_username, r_email, r_password, r_confirm]):
                st.error("Please fill in all fields")
            elif r_password != r_confirm:
                st.error("Passwords do not match")
            else:
                try:
                    resp = api_post("/api/auth/register", {
                        "username": r_username, "email": r_email,
                        "password": r_password, "full_name": r_username,
                    }, auth=False)
                    if resp.status_code == 200:
                        _store_session(resp.json())
                        st.success("Account created!")
                        st.rerun()
                    else:
                        st.error(resp.json().get("detail", "Registration failed"))
                except requests.RequestException as exc:
                    st.error(f"Cannot reach backend: {exc}")


def _store_session(data: Dict[str, Any]) -> None:
    st.session_state.authenticated = True
    st.session_state.access_token = data["access_token"]
    st.session_state.refresh_token = data["refresh_token"]
    st.session_state.user = data["user"]
    st.session_state.username = data["user"]["username"]
    # Restore the user's persisted conversation on login/registration.
    load_chat_history()


def logout() -> None:
    refresh = st.session_state.get("refresh_token")
    if refresh:
        try:
            api_post("/api/auth/logout", {"refresh_token": refresh})
        except requests.RequestException:
            pass
    for key in ("authenticated", "access_token", "refresh_token", "user", "username", "messages"):
        st.session_state.pop(key, None)


# --------------------------------------------------------------------------- #
# Sidebar: AI provider config
# --------------------------------------------------------------------------- #
def render_sidebar() -> None:
    st.sidebar.success(f"Logged in as **{st.session_state.username}**")
    if st.sidebar.button("🚪 Logout"):
        logout()
        st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.header("🤖 AI Configuration")

    try:
        providers = api_get("/api/config/providers").json()
    except requests.RequestException:
        providers = []
    if not providers:
        st.sidebar.warning("No AI providers available")
        return

    names = [p["name"] for p in providers]
    try:
        current = api_get("/api/config/providers/current").json()
        idx = names.index(current["name"]) if current.get("name") in names else 0
    except (requests.RequestException, ValueError):
        current, idx = None, 0

    selected = st.sidebar.selectbox("Provider", names, index=idx)
    if current and selected != current.get("name"):
        api_post("/api/config/providers/switch", {"provider_name": selected})
        st.rerun()

    cfg = next((p for p in providers if p["name"] == selected), {})
    with st.sidebar.expander("⚙️ Model Parameters"):
        temp = st.slider("Temperature", 0.0, 2.0, float(cfg.get("temperature", 0.7)), 0.1)
        max_tokens = st.slider("Max Tokens", 100, 32000, int(cfg.get("max_tokens", 4096)), 100)
        top_p = st.slider("Top P", 0.0, 1.0, float(cfg.get("top_p", 0.95)), 0.05)
        if st.button("Apply Parameters"):
            requests.put(
                f"{API_BASE_URL}/api/config/providers/{selected}/parameters",
                json={"temperature": temp, "max_tokens": max_tokens, "top_p": top_p},
                headers=auth_headers(), timeout=30,
            )
            st.success("Parameters updated")

    with st.sidebar.expander("🔌 Connection"):
        if st.button("Test Connection"):
            with st.spinner("Testing..."):
                try:
                    res = api_get(f"/api/config/providers/{selected}/test").json()
                    st.success("Connected") if res.get("connected") else st.error("Failed")
                except requests.RequestException:
                    st.error("Failed")


# --------------------------------------------------------------------------- #
# Main views
# --------------------------------------------------------------------------- #
def render_chat() -> None:
    st.header("💬 Chat")
    st.caption("Ask me to analyze projects, generate Dockerfiles, or manage containers.")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Render the conversation so far.
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # NOTE: st.chat_input cannot be used inside an st.tabs container (raises a
    # StreamlitAPIException in several versions), which would blank out this tab.
    # A form with a text input + button works inside tabs and across versions.
    with st.form("chat_form", clear_on_submit=True):
        prompt = st.text_area(
            "Message",
            placeholder="e.g. Generate a Dockerfile for /home/eko/data/hextris",
            height=80,
            label_visibility="collapsed",
        )
        cols = st.columns([1, 1, 6])
        submitted = cols[0].form_submit_button("Send", type="primary")
        clear = cols[1].form_submit_button("Clear")

    if clear:
        try:
            api_delete("/api/chat/history")
        except requests.RequestException:
            pass
        st.session_state.messages = []
        st.rerun()

    if submitted and prompt and prompt.strip():
        prompt = prompt.strip()
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Send only the most recent MAX_HISTORY messages as context to bound the
        # model's context window and keep requests fast.
        history = [
            {"role": m["role"], "content": m["content"]}
            for m in st.session_state.messages[:-1]
            if m["role"] in ("user", "assistant")
        ][-MAX_HISTORY:]
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    # Chat can trigger a build via deploy_project, which is slow.
                    resp = api_post("/api/chat", {"message": prompt, "history": history},
                                    timeout=900)
                    if resp.status_code == 200:
                        data = resp.json()
                        reply = data.get("reply", "")
                        st.markdown(reply or "_(no response)_")
                        if data.get("tool_calls"):
                            with st.expander("🔧 Tool calls"):
                                st.json(data["tool_calls"])
                        st.session_state.messages.append({"role": "assistant", "content": reply})
                    else:
                        detail = resp.json().get("detail", resp.text)
                        st.error(f"Error: {detail}")
                except requests.RequestException as exc:
                    st.error(f"Request failed: {exc}")

        # The full conversation is kept in session and displayed. Only the last
        # MAX_HISTORY messages are sent to the model as context (above); the UI
        # shows everything the user has stored.


def render_containers() -> None:
    st.header("📦 Containers")
    try:
        status = api_get("/api/docker/status").json()
    except requests.RequestException:
        status = {"available": False}

    if not status.get("available"):
        st.warning("Docker daemon is not available on the backend host.")
        return

    st.caption(
        "This tab shows containers created through dockchat (isolated per user). "
        "Containers started outside the app are not listed here."
    )
    if st.button("🔄 Refresh"):
        st.rerun()
    try:
        containers = api_get("/api/docker/containers").json()
    except requests.RequestException as exc:
        st.error(f"Failed to list containers: {exc}")
        return

    if not containers:
        st.info("You haven't created any containers through dockchat yet.")
    else:
        for c in containers:
            _render_container_row(c, manageable=True)

    # Admin-only: show every container on the host (including ones started
    # outside dockchat). Only rendered for superusers.
    user = st.session_state.get("user") or {}
    if user.get("is_superuser"):
        with st.expander("🛡 Admin: all host containers"):
            resp = api_get("/api/docker/containers/all")
            if resp.status_code == 200:
                all_containers = resp.json()
                if not all_containers:
                    st.info("No containers on the host.")
                for c in all_containers:
                    _render_container_row(c, manageable=False)
            elif resp.status_code == 403:
                st.warning("Admin privileges required.")
            else:
                show_response_error(resp, "Failed to list host containers")


def _format_ports(ports: Dict[str, Any]) -> str:
    """Turn Docker's raw port mapping into readable 'internal -> external' lines.

    Docker shape: {"80/tcp": [{"HostIp": "0.0.0.0", "HostPort": "34185"}], "9000/tcp": None}
    - published:   80/tcp -> 34185
    - unpublished: 9000/tcp (internal only)
    """
    if not ports:
        return "—"
    lines = []
    for container_port, bindings in ports.items():
        if container_port == "_remapped_from":
            continue
        if bindings:
            host_ports = sorted({b.get("HostPort") for b in bindings if b.get("HostPort")})
            for hp in host_ports:
                lines.append(f"{container_port} → {hp}")
        else:
            lines.append(f"{container_port} (internal only)")
    return "\n".join(lines) if lines else "—"


def _render_container_row(c: Dict[str, Any], manageable: bool) -> None:
    col1, col2, col3, col4, col5 = st.columns([3, 1.5, 2, 2, 2.5])
    col1.markdown(f"**{c['name']}**")
    col1.caption(c["image"])
    col2.write(c["status"])
    with col3:
        st.markdown("**Ports** (internal → external)")
        st.text(_format_ports(c.get("ports") or {}))
    with col4:
        st.code(c["id"], language=None)
    if manageable:
        with col5:
            a1, a2, a3 = st.columns(3)
            if a1.button("▶", key=f"start_{c['id']}"):
                api_post(f"/api/docker/containers/{c['id']}/start")
                st.rerun()
            if a2.button("⏹", key=f"stop_{c['id']}"):
                api_post(f"/api/docker/containers/{c['id']}/stop")
                st.rerun()
            if a3.button("🗑", key=f"rm_{c['id']}"):
                api_post(f"/api/docker/containers/{c['id']}/remove")
                st.rerun()
    else:
        col5.caption("read-only")


def render_projects() -> None:
    st.header("🛠 Project Scaffolding")
    st.caption(
        "Add a project directory to analyze it, generate a Dockerfile, build an "
        "image, and run it as a container. The path must be inside the backend's "
        "ALLOWED_PATHS."
    )

    path = st.text_input("Project directory", placeholder="/home/eko/my-app",
                         key="proj_path")

    colo1, colo2, colo3 = st.columns(3)
    base_image = colo1.text_input("Base image (optional)", key="proj_base",
                                  placeholder="auto-detected")
    exposed_port = colo2.number_input("Container port", min_value=0, max_value=65535,
                                      value=0, key="proj_port",
                                      help="0 = auto-detect from project type")
    host_port = colo3.number_input("Host port", min_value=0, max_value=65535,
                                   value=0, key="proj_hostport",
                                   help="0 = same as container port")

    # Step buttons
    b1, b2, b3, b4 = st.columns(4)
    do_analyze = b1.button("🔍 Analyze")
    do_generate = b2.button("📄 Generate Dockerfile")
    do_write = b3.button("💾 Write to disk")
    do_deploy = b4.button("🚀 Build & Run", type="primary")

    def _opt_int(v):
        return int(v) if v else None

    if do_analyze and path:
        resp = api_post("/api/docker/projects/analyze", {"path": path})
        if resp.status_code == 200:
            st.subheader("Analysis")
            st.json(resp.json())
        else:
            show_response_error(resp, "Analysis failed")

    if (do_generate or do_write) and path:
        resp = api_post("/api/docker/projects/generate-dockerfile", {
            "path": path,
            "base_image": base_image or None,
            "exposed_port": _opt_int(exposed_port),
            "write_to_disk": bool(do_write),
        })
        if resp.status_code == 200:
            data = resp.json()
            if data.get("written_path"):
                st.success(f"Wrote {data['written_path']} and .dockerignore")
            st.subheader("Dockerfile")
            st.code(data["dockerfile"], language="dockerfile")
            st.subheader(".dockerignore")
            st.code(data["dockerignore"], language=None)
        else:
            show_response_error(resp, "Generation failed")

    if do_deploy and path:
        with st.spinner("Analyzing, generating Dockerfile, building image, and starting container..."):
            resp = api_post("/api/docker/projects/deploy", {
                "path": path,
                "base_image": base_image or None,
                "exposed_port": _opt_int(exposed_port),
                "host_port": _opt_int(host_port),
            }, timeout=900)
        if resp.status_code == 200:
            data = resp.json()
            c = data["container"]
            img_tags = ", ".join(data["image"].get("tags") or []) or data["image"]["id"]
            st.success(f"Running container '{c['name']}' ({c['status']}) from image {img_tags}")
            with st.expander("Analysis"):
                st.json(data["analysis"])
            with st.expander("Dockerfile"):
                st.code(data["dockerfile"], language="dockerfile")
            with st.expander("Build logs"):
                st.code("\n".join(data.get("build_logs") or []), language=None)
            st.info("Manage it in the 📦 Containers tab.")
        else:
            show_response_error(resp, "Deploy failed")

    # Show images the user has built
    with st.expander("🧱 Your images"):
        resp = api_get("/api/docker/images")
        if resp.status_code == 200:
            images = resp.json()
            if not images:
                st.caption("No images built yet.")
            for img in images:
                tags = ", ".join(img.get("tags") or []) or img["id"]
                size = img.get("size")
                size_str = f" · {round(size / 1e6)} MB" if size else ""
                st.markdown(f"- `{tags}`{size_str}")
        else:
            show_response_error(resp, "Failed to list images")


def render_activity() -> None:
    st.header("📊 Activity")
    try:
        logs = api_get("/api/audit/logs").json()
    except requests.RequestException:
        logs = []
    if not logs:
        st.info("No activity recorded yet.")
        return
    for log in logs[:50]:
        c1, c2 = st.columns([1, 4])
        c1.caption(str(log.get("created_at", ""))[:19])
        c2.markdown(f"**{log['action']}** {log.get('resource_type') or ''} {log.get('resource_id') or ''}")


# --------------------------------------------------------------------------- #
# Entry
# --------------------------------------------------------------------------- #
def main() -> None:
    if not st.session_state.get("authenticated"):
        render_auth()
        return

    render_sidebar()
    tab_chat, tab_containers, tab_projects, tab_activity = st.tabs(
        ["💬 Chat", "📦 Containers", "🛠 Projects", "📊 Activity"]
    )
    with tab_chat:
        render_chat()
    with tab_containers:
        render_containers()
    with tab_projects:
        render_projects()
    with tab_activity:
        render_activity()


if __name__ == "__main__":
    main()
