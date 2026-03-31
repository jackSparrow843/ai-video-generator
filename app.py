import streamlit as st
import requests
import os
import time
from datetime import datetime

HF_TOKEN = ""
if "HF_TOKEN" in st.secrets:
    HF_TOKEN = st.secrets["HF_TOKEN"]

st.set_page_config(page_title="AI Video Generator", page_icon="🎬", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .main-title { font-size:2.4rem; font-weight:700; text-align:center;
        background:linear-gradient(135deg,#a78bfa,#60a5fa,#34d399);
        -webkit-background-clip:text; -webkit-text-fill-color:transparent; margin-bottom:0.2rem; }
    .sub-title { text-align:center; color:#6b7280; font-size:1rem; margin-bottom:2rem; }
</style>""", unsafe_allow_html=True)

if "history" not in st.session_state:
    st.session_state.history = []

with st.sidebar:
    st.markdown("### ⚙️ Configuration")
    hf_token = st.text_input("HuggingFace Token (optional)", type="password", value=HF_TOKEN, placeholder="hf_...", help="Free token from huggingface.co")
    st.info("👉 [Get free token at huggingface.co](https://huggingface.co/settings/tokens)")
    st.divider()
    st.metric("Videos generated", len(st.session_state.history))
    if st.button("🗑️ Clear history", use_container_width=True):
        st.session_state.history = []
        st.rerun()

STYLE_PRESETS = {
    "None": "",
    "Cinematic": "cinematic film, dramatic lighting, 4K, professional cinematography",
    "Anime": "anime style, vibrant colors, Studio Ghibli aesthetic",
    "Nature documentary": "BBC nature documentary, golden hour, ultra HD",
    "Cyberpunk": "cyberpunk neon lights, rain-slicked streets, futuristic city",
    "Fantasy": "epic fantasy, magical atmosphere, vibrant colors, dreamlike",
}

st.markdown('<h1 class="main-title">🎬 AI Video Generator</h1>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Turn text prompts into motion videos — 100% free via HuggingFace</p>', unsafe_allow_html=True)

col_left, col_right = st.columns([3, 1])
with col_left:
    prompt = st.text_area("Your prompt", placeholder="Describe your video scene...\n\nExample: A majestic eagle soaring above mountains, golden sunrise, cinematic slow motion", height=120, label_visibility="collapsed")
    style_preset = st.selectbox("Style preset", list(STYLE_PRESETS.keys()))
with col_right:
    st.markdown("<br>", unsafe_allow_html=True)
    generate_btn = st.button("🎬 Generate video", use_container_width=True, disabled=not prompt.strip())

with st.expander("💡 Example prompts"):
    examples = [
        "A serene Japanese garden with cherry blossoms falling, koi fish in a pond, soft morning light",
        "Ocean waves crashing against sea cliffs at sunset, golden light, slow motion spray",
        "A cozy café in Paris, rain on windows, warm amber lighting, vintage aesthetic",
        "A lone astronaut walking on Mars, red dust storms in distance, Earth visible in dark sky",
        "Abstract colorful fluid simulation, swirling patterns of blue and gold",
    ]
    for ex in examples:
        if st.button(f"  {ex[:70]}...", key=ex, use_container_width=True):
            st.session_state["set_prompt"] = ex
            st.rerun()

if "set_prompt" in st.session_state:
    prompt = st.session_state.pop("set_prompt")

def generate_video_hf(prompt, token=""):
    API_URL = "https://api-inference.huggingface.co/models/damo-vilab/text-to-video-ms-1.7b"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    payload = {"inputs": prompt, "parameters": {"num_inference_steps": 25, "num_frames": 16}}
    response = requests.post(API_URL, headers=headers, json=payload, timeout=300)
    if response.status_code == 200:
        return response.content, None
    elif response.status_code == 503:
        return None, "Model is loading — wait 20 seconds and try again."
    elif response.status_code == 401:
        return None, "Invalid HuggingFace token."
    else:
        return None, f"Error {response.status_code}: {response.text[:200]}"

if generate_btn and prompt.strip():
    final_prompt = prompt.strip()
    if style_preset != "None":
        final_prompt = f"{final_prompt}, {STYLE_PRESETS[style_preset]}"
    log_entry = {"prompt": prompt.strip(), "style": style_preset, "timestamp": datetime.now().strftime("%H:%M:%S"), "status": "generating", "video_bytes": None, "error": None}
    st.session_state.history.insert(0, log_entry)
    with st.status("🎬 Generating your video...", expanded=True) as status_box:
        st.write(f"**Prompt:** {final_prompt[:100]}")
        st.write("⏳ Sending to HuggingFace (1–3 minutes on free tier)...")
        video_bytes, error = generate_video_hf(final_prompt, hf_token)
        if video_bytes:
            log_entry["status"] = "success"
            log_entry["video_bytes"] = video_bytes
            status_box.update(label="✅ Video generated!", state="complete")
        else:
            log_entry["status"] = "error"
            log_entry["error"] = error
            status_box.update(label="❌ Failed", state="error")
            st.error(error)
    st.rerun()

if st.session_state.history:
    st.markdown("---")
    st.markdown("### 🎥 Generated videos")
    for i, entry in enumerate(st.session_state.history):
        status_icon = {"success": "✅", "error": "❌", "generating": "⏳"}.get(entry["status"], "❓")
        st.markdown(f"**{status_icon} {entry['timestamp']}** — {entry['prompt'][:80]}")
        if entry["status"] == "success" and entry.get("video_bytes"):
            st.video(entry["video_bytes"])
            st.download_button("⬇️ Download video", data=entry["video_bytes"], file_name=f"video_{entry['timestamp'].replace(':','')}.mp4", mime="video/mp4", key=f"dl_{i}")
        elif entry["status"] == "error":
            st.error(entry["error"])
        st.divider()
else:
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div style="text-align:center;color:#4b5563;padding:3rem"><div style="font-size:3rem">🎬</div><div style="font-size:1.1rem;color:#6b7280;margin-top:0.5rem">No videos yet — enter a prompt above!</div></div>', unsafe_allow_html=True)

with st.expander("📘 Tips for better results"):
    st.markdown("""
    - **Be specific** — describe the scene, lighting, camera movement
    - **Add motion words** — "slowly flowing", "gently swaying", "rushing water"
    - **If model is loading** — wait 20 seconds and try again (cold start)
    - **Get HF token** — speeds up generation (free at huggingface.co/settings/tokens)
    """)
```

---

Also update `requirements.txt` — replace everything with just:
```
streamlit>=1.32.0
requests>=2.31.0
