import os
import streamlit as st



# """
# * STUN 
#     - helps the browser discover its public-facing network address.
# * TURN 
#     - acts as a relay server when direct peer-to-peer connection fails.
#     - TURN is used when:
#       > the laptop is behind strict NAT or firewall rules
#       > company Wi‑Fi or VPN blocks direct WebRTC paths
#       > browser-to-app media traffic cannot connect directly
# """
DEFAULT_STUN_URLS = ["stun:stun.l.google.com:19302"]

def _read_secret(*path):
    try:
        value = st.secrets
        for key in path:
            value = value[key]
        return value
    except Exception:
        return None


def _first_config_value(secret_paths, env_names):
    for secret_path in secret_paths:
        value = _read_secret(*secret_path)
        if value not in (None, "", []):
            return value
    for env_name in env_names:
        value = os.getenv(env_name)
        if value not in (None, ""):
            return value
    return None


def _normalize_urls(value):
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def get_rtc_configuration():
    ice_servers = [{"urls": DEFAULT_STUN_URLS}]

    turn_urls = _normalize_urls(
        _first_config_value(
            secret_paths=[(("webrtc", "turn_urls")), (("TURN_URLS",))],
            env_names=["TURN_URLS"],
        )
    )
    turn_username = _first_config_value(
        secret_paths=[(("webrtc", "turn_username")), (("TURN_USERNAME",))],
        env_names=["TURN_USERNAME"],
    )
    turn_credential = _first_config_value(
        secret_paths=[(("webrtc", "turn_credential")), (("TURN_CREDENTIAL",))],
        env_names=["TURN_CREDENTIAL"],
    )

    if turn_urls and turn_username and turn_credential:
        ice_servers.append(
            {
                "urls": turn_urls,
                "username": str(turn_username),
                "credential": str(turn_credential),
            }
        )
    return {"iceServers": ice_servers}
