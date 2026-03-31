import streamlit as st
import replicate
import requests
import os
import time
import json
from datetime import datetime
from pathlib import Path

# ─── Load API key from Streamlit Cloud secrets (if deployed) ─────────────────
if "REPLICATE_API_TOKEN" in st.secrets:
    os.environ["REPLICATE_API_TOKEN"] = st.secrets["REPLICATE_API_TOKEN"]

# ─── Page config ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Video Generator",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Custom CSS ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .stApp { background: #0e0e11; }
    .main-title {
        font-size: 2.4rem; font-weight: 700; text-align: center;
        background: linear-gradient(135deg, #a78bfa, #60a5fa, #34d399);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        text-align: center; color: #6b7280; font-size: 1rem;
        margin-bottom: 2rem;
    }
    .video-card {
        background: #1a1a2e; border-radius: 12px; padding: 1rem;
        border: 1px solid #2d2d44; margin-bottom: 1rem;
    }
    .stat-pill {
        display: inline-block; background: #2d2d44; color: #a78bfa;
        padding: 2px 10px; border-radius: 20px; font-size: 0.78rem;
        margin: 2px;
    }
    .model-badge {
        background: #1e1b4b; color: #a78bfa; padding: 4px 12px;
        border-radius: 20px; font-size: 0.8rem; border: 1px solid #4c1d95;
    }
    div[data-testid="stButton"] > button {
        background: linear-gradient(135deg, #7c3aed, #3b82f6);
        color: white; border: none; border-radius: 8px;
        font-weight: 600; padding: 0.6rem 1.5rem;
        transition: opacity 0.2s;
    }
    div[data-testid="stButton"] > button:hover { opacity: 0.85; }
    .stTextArea textarea {
        background: #1a1a2e !important; border-color: #2d2d44 !important;
        color: #e5e7eb !important; border-radius: 10px !important;
    }
    .prompt-tip {
        background: #1a1a2e; border-left: 3px solid #7c3aed;
        padding: 0.6rem 1rem; border-radius: 0 8px 8px 0;
        font-size: 0.85rem; color: #9ca3af; margin: 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)

# ─── Session state setup ─────────────────────────────────────────────────────
if "history" not in st.session_state:
    st.session_state.history = []
if "generating" not in st.session_state:
    st.session_state.generating = False

# ─── Available models on Replicate (free-tier friendly) ─────────────────────
MODELS = {
    "Wan 2.1 — 480p (fast, great quality)": {
        "id": "wavespeedai/wan-2.1-t2v-480p",
        "params": {"fps": 16, "num_frames": 81},
        "cost": "~$0.03/video",
        "speed": "30–60 sec",
    },
    "Wan 2.1 — 720p (higher res, slower)": {
        "id": "wavespeedai/wan-2.1-t2v-720p",
        "params": {"fps": 16, "num_frames": 81},
        "cost": "~$0.07/video",
        "speed": "60–90 sec",
    },
    "MiniMax Video-01 (cinematic quality)": {
        "id": "minimax/video-01",
        "params": {},
        "cost": "~$0.06/video",
        "speed": "60–120 sec",
    },
    "CogVideoX-5B (open-source, creative)": {
        "id": "lucataco/cogvideox-5b",
        "params": {"num_inference_steps": 50, "fps": 8},
        "cost": "~$0.04/video",
        "speed": "60–90 sec",
    },
}

# ─── Style presets ───────────────────────────────────────────────────────────
STYLE_PRESETS = {
    "None": "",
    "Cinematic": "cinematic film, dramatic lighting, 4K, professional cinematography, shallow depth of field",
    "Anime": "anime style, vibrant colors, Studio Ghibli aesthetic, beautiful animation",
    "Nature documentary": "BBC nature documentary style, golden hour lighting, ultra HD, atmospheric",
    "Cyberpunk": "cyberpunk neon lights, rain-slicked streets, futuristic city, dark atmosphere",
    "Fantasy": "epic fantasy, magical atmosphere, vibrant colors, dreamlike, ethereal lighting",
    "Horror": "horror film atmosphere, dark shadows, eerie lighting, suspenseful, desaturated",
    "Vintage film": "vintage 1970s film, grain, warm tones, nostalgic, 16mm film look",
}

# ─── Sidebar ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Configuration")

    api_key = st.text_input(
        "Replicate API Key",
        type="password",
        placeholder="r8_...",
        help="Get your free key at replicate.com — you receive ~$5 free credits",
    )
    if api_key:
        os.environ["REPLICATE_API_TOKEN"] = api_key
        st.success("API key set ✓")
    else:
        st.info("👉 [Get free API key at replicate.com](https://replicate.com)")

    st.divider()

    selected_model_name = st.selectbox("Model", list(MODELS.keys()))
    model_info = MODELS[selected_model_name]

    col1, col2 = st.columns(2)
    col1.markdown(f'<span class="stat-pill">💰 {model_info["cost"]}</span>', unsafe_allow_html=True)
    col2.markdown(f'<span class="stat-pill">⏱ {model_info["speed"]}</span>', unsafe_allow_html=True)

    st.divider()
    st.markdown("### 🎨 Style")
    style_preset = st.selectbox("Style preset", list(STYLE_PRESETS.keys()))

    st.divider()
    st.markdown("### 📊 Generation stats")
    total = len(st.session_state.history)
    st.metric("Videos generated", total)
    if total > 0:
        successful = sum(1 for h in st.session_state.history if h.get("status") == "success")
        st.metric("Successful", f"{successful}/{total}")

    if st.button("🗑️ Clear history", use_container_width=True):
        st.session_state.history = []
        st.rerun()

# ─── Main content ─────────────────────────────────────────────────────────────
st.markdown('<h1 class="main-title">🎬 AI Video Generator</h1>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Turn text prompts into motion videos — powered by open AI models</p>', unsafe_allow_html=True)

# ─── Prompt input section ────────────────────────────────────────────────────
col_left, col_right = st.columns([3, 1])

with col_left:
    prompt = st.text_area(
        "Your prompt",
        placeholder="Describe your video scene in detail...\n\nExample: A majestic eagle soaring above snow-capped mountains, golden sunrise, cinematic slow motion",
        height=120,
        label_visibility="collapsed",
    )

    # Style tips
    if style_preset != "None":
        st.markdown(
            f'<div class="prompt-tip">✨ Style will be appended: <em>{STYLE_PRESETS[style_preset][:60]}...</em></div>',
            unsafe_allow_html=True,
        )

with col_right:
    st.markdown("<br>", unsafe_allow_html=True)
    generate_btn = st.button(
        "🎬 Generate video",
        use_container_width=True,
        disabled=(not api_key or not prompt.strip()),
    )
    if not api_key:
        st.caption("⬅️ Add API key first")
    elif not prompt.strip():
        st.caption("⬅️ Enter a prompt")

# Example prompts
with st.expander("💡 Example prompts to try"):
    examples = [
        "A serene Japanese garden with cherry blossoms falling gently in the breeze, koi fish swimming in a stone pond, soft morning light",
        "A futuristic city at night with flying cars and neon hologram advertisements, rain falling, cyberpunk aesthetic",
        "A lone astronaut walking on the surface of Mars, red dust storms in the distance, Earth visible in the dark sky",
        "Ocean waves crashing against dramatic sea cliffs at sunset, golden light, slow motion spray",
        "A cozy café interior in Paris, rain on windows, people reading, warm amber lighting, vintage aesthetic",
        "Abstract colorful fluid simulation, swirling patterns of blue and gold, mesmerizing motion",
    ]
    for ex in examples:
        if st.button(f"  {ex[:75]}...", key=ex, use_container_width=True):
            st.session_state["set_prompt"] = ex
            st.rerun()

# Handle example prompt selection
if "set_prompt" in st.session_state:
    prompt = st.session_state.pop("set_prompt")

# ─── Generation logic ────────────────────────────────────────────────────────
if generate_btn and prompt.strip() and api_key:
    # Build final prompt
    final_prompt = prompt.strip()
    if style_preset != "None" and STYLE_PRESETS[style_preset]:
        final_prompt = f"{final_prompt}, {STYLE_PRESETS[style_preset]}"

    log_entry = {
        "id": f"video_{int(time.time())}",
        "prompt": prompt.strip(),
        "style": style_preset,
        "model": selected_model_name,
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "status": "generating",
        "video_url": None,
        "error": None,
    }
    st.session_state.history.insert(0, log_entry)

    with st.status("🎬 Generating your video...", expanded=True) as status_box:
        try:
            st.write(f"**Model:** {selected_model_name}")
            st.write(f"**Prompt:** {final_prompt[:100]}...")
            st.write("⏳ Submitting to Replicate...")

            model_id = model_info["id"]
            extra_params = model_info["params"].copy()

            # Run prediction
            client = replicate.Client(api_token=api_key)

            st.write("🔄 Processing (this takes 30–120 seconds)...")

            # Build input dict based on model
            input_data = {"prompt": final_prompt}

            # Model-specific params
            if "wan" in model_id.lower():
                input_data.update({
                    "fps": extra_params.get("fps", 16),
                    "num_frames": extra_params.get("num_frames", 81),
                })
            elif "cogvideo" in model_id.lower():
                input_data.update({
                    "num_inference_steps": extra_params.get("num_inference_steps", 50),
                    "fps": extra_params.get("fps", 8),
                })

            # Run the model
            output = client.run(model_id, input=input_data)

            # Handle output (can be URL string or FileOutput object)
            video_url = None
            if isinstance(output, str):
                video_url = output
            elif isinstance(output, list) and len(output) > 0:
                video_url = str(output[0])
            elif hasattr(output, "url"):
                video_url = output.url
            else:
                video_url = str(output)

            if video_url:
                log_entry["status"] = "success"
                log_entry["video_url"] = video_url
                status_box.update(label="✅ Video generated!", state="complete")
                st.write(f"✅ Done! [View video]({video_url})")
            else:
                raise ValueError("No video URL returned from model")

        except replicate.exceptions.ReplicateError as e:
            error_msg = str(e)
            log_entry["status"] = "error"
            log_entry["error"] = error_msg
            status_box.update(label="❌ Generation failed", state="error")
            if "401" in error_msg or "authentication" in error_msg.lower():
                st.error("Invalid API key. Check your Replicate API key.")
            elif "model" in error_msg.lower() and "not found" in error_msg.lower():
                st.error(f"Model not found. Try a different model. Details: {error_msg}")
            else:
                st.error(f"Replicate error: {error_msg}")

        except Exception as e:
            error_msg = str(e)
            log_entry["status"] = "error"
            log_entry["error"] = error_msg
            status_box.update(label="❌ Error", state="error")
            st.error(f"Error: {error_msg}")
            st.info("💡 If the model name changed, check replicate.com/explore for latest model IDs")

    st.rerun()

# ─── Display history ─────────────────────────────────────────────────────────
if st.session_state.history:
    st.markdown("---")
    st.markdown("### 🎥 Generated videos")

    for entry in st.session_state.history:
        with st.container():
            st.markdown(f'<div class="video-card">', unsafe_allow_html=True)

            col1, col2 = st.columns([3, 1])

            with col1:
                status_icon = {"success": "✅", "error": "❌", "generating": "⏳"}.get(entry["status"], "❓")
                st.markdown(f"**{status_icon} {entry['timestamp']}** — {entry['prompt'][:80]}{'...' if len(entry['prompt']) > 80 else ''}")
                st.markdown(
                    f'<span class="stat-pill">{entry["model"].split("—")[0].strip()}</span>'
                    f'<span class="stat-pill">🎨 {entry["style"]}</span>',
                    unsafe_allow_html=True,
                )

            with col2:
                if entry["status"] == "success" and entry.get("video_url"):
                    st.link_button("▶️ Open video", entry["video_url"], use_container_width=True)

            if entry["status"] == "success" and entry.get("video_url"):
                st.video(entry["video_url"])

            elif entry["status"] == "error" and entry.get("error"):
                st.error(f"Error: {entry['error'][:200]}")

            st.markdown("</div>", unsafe_allow_html=True)

else:
    # Empty state
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("""
        <div style="text-align:center; color:#4b5563; padding: 3rem 1rem;">
            <div style="font-size:3rem">🎬</div>
            <div style="font-size:1.1rem; font-weight:600; color:#6b7280; margin-top:0.5rem">No videos yet</div>
            <div style="font-size:0.9rem; color:#4b5563; margin-top:0.3rem">Enter a prompt above and hit Generate</div>
        </div>
        """, unsafe_allow_html=True)

# ─── Footer tips ─────────────────────────────────────────────────────────────
with st.expander("📘 Tips for better videos"):
    st.markdown("""
    **Prompt writing tips:**
    - **Be specific** — "a red fox running through autumn forest at golden hour" beats "fox in forest"
    - **Add camera directions** — "slow pan", "close-up", "aerial shot", "tracking shot"
    - **Mention lighting** — "golden hour", "neon lights", "moonlight", "studio lighting"
    - **Include motion** — "gently swaying", "rushing water", "dramatic explosion", "floating"
    - **Set the mood** — "peaceful", "intense", "mysterious", "joyful"

    **Model guide:**
    - **Wan 2.1 480p** → Best value, fast, reliable for most prompts
    - **Wan 2.1 720p** → Higher resolution, good for landscapes and detailed scenes
    - **MiniMax Video-01** → Cinematic quality, best for realistic scenes
    - **CogVideoX-5B** → Great for creative/artistic prompts

    **Save money:**
    - Use 480p for drafting, upgrade to 720p only for final versions
    - Wan 2.1 480p gives best cost/quality ratio
    - Replicate charges only when the model runs — no monthly fees
    """)
