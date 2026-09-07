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

st.set_page_config(page_title="dockchat", page_icon="🐳", layout="wide")


# --------------------------------------------------------------------------- #
# HTTP helpers
# --------------------------------------------------------------------------- #
def auth_headers() -> Dict[str, str]:
    token = st.session_state.get("access_token")
    return {"Authorization": f"Bearer {token}"} if token else {}


def api_post(path: str, json: Optional[dict] = None, auth: bool = True) -> requests.Response:
    return requests.post(
        f"{API_BASE_URL}{path}", json=json, headers=auth_headers() if auth else {}, timeout=120
    )


def api_get(path: str, auth: bool = True) -> requests.Response:
    return requests.get(f"{API_BASE_URL}{path}", headers=auth_headers() if auth else {}, timeout=60)


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

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    prompt = st.chat_input("e.g. Generate a Dockerfile for /workspace/my-app")
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        history = [
            {"role": m["role"], "content": m["content"]}
            for m in st.session_state.messages[:-1]
            if m["role"] in ("user", "assistant")
        ]
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    resp = api_post("/api/chat", {"message": prompt, "history": history})
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


def render_containers() -> None:
    st.header("📦 Containers")
    try:
        status = api_get("/api/docker/status").json()
    except requests.RequestException:
        status = {"available": False}

    if not status.get("available"):
        st.warning("Docker daemon is not available on the backend host.")
        return

    if st.button("🔄 Refresh"):
        st.rerun()
    try:
        containers = api_get("/api/docker/containers").json()
    except requests.RequestException as exc:
        st.error(f"Failed to list containers: {exc}")
        return

    if not containers:
        st.info("No containers yet.")
        return

    for c in containers:
        col1, col2, col3, col4 = st.columns([3, 2, 2, 3])
        col1.markdown(f"**{c['name']}**")
        col1.caption(c["image"])
        col2.write(c["status"])
        with col3:
            st.code(c["id"], language=None)
        with col4:
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


def render_projects() -> None:
    st.header("🛠 Project Scaffolding")
    path = st.text_input("Project path", placeholder="/workspace/my-app")

    col1, col2 = st.columns(2)
    if col1.button("Analyze"):
        if path:
            resp = api_post("/api/docker/projects/analyze", {"path": path})
            st.json(resp.json()) if resp.status_code == 200 else st.error(
                resp.json().get("detail", "Analysis failed"))

    if col2.button("Generate Dockerfile"):
        if path:
            resp = api_post("/api/docker/projects/generate-dockerfile",
                            {"path": path, "write_to_disk": False})
            if resp.status_code == 200:
                data = resp.json()
                st.subheader("Dockerfile")
                st.code(data["dockerfile"], language="dockerfile")
                st.subheader(".dockerignore")
                st.code(data["dockerignore"], language=None)
            else:
                st.error(resp.json().get("detail", "Generation failed"))


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
