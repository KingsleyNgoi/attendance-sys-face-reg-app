import cv2, threading, time, face_rec
import numpy as np
import streamlit as st
from streamlit_webrtc import webrtc_streamer
from helper.helper_funcs import Helper_Funcs
from helper.webrtc_config import get_rtc_configuration



st.subheader('Registration Form')
MAX_SAMPLES = 10
CAPTURE_INTERVAL = 1.0   # seconds between captures (so user sees count climb)

# ═══════════════════  Step 00: Registration Form  ═══════════════════
# """
# * All the defined session state variables 
#     - are stored in st.session_state 
#         > so they persist across Streamlit reruns 
#           (every button click, widget interaction, etc. triggers a full script rerun).
# 
# * Define session state variables with defaults if they don't exist yet:
#     -  sample_store (line 33) 
#         > holds the SampleStore object with collected embeddings and face crops. 
#         > Must survive reruns so samples aren't lost mid-capture.
#     - mode (line 38) 
#         > tracks whether the user selected 'webcam' or 'snapshot' mode. 
#         > Persists so the selection isn't reset on rerun.
#     - show_samples_grid (line 40) 
#         > toggles the sample preview grid on/off. 
#         > Persists so it stays open/closed across reruns.
# 
# * Without st.session_state, 
#     - all three would be re-initialized to their defaults every time the script reruns, 
#       losing all captured data and UI state.
# """
# ── Thread-safe container stored in session_state (survives reruns) ──
class SampleStore:
    # """
    # SampleStore
    # * It's a container 
    #   - that holds collected face embeddings and images in memory. 
    # * It lives in st.session_state 
    #   - so it survives Streamlit reruns. 
    # * The video callback thread 
    #   - writes samples into it, and the main Streamlit thread reads from it to display counts and save to Redis.
    # """
    def __init__(self):
        # """
        # * self.lock
        #   - The video callback runs on a separate thread (from streamlit-webrtc), 
        #       > while the main Streamlit thread reads the same data. 
        #   - Without a lock, 
        #       > both threads could read/write self.samples simultaneously, 
        #       > causing race conditions (corrupted data, crashes). 
        #   - with self.lock: 
        #       > ensures only one thread accesses the data at a time.
        # """
        self.lock = threading.Lock()
        self.samples: list = []   # np.ndarray embeddings (512-d)
        self.images: list = []    # np.ndarray face crops (BGR) for preview
        self.capturing: bool = True
        self.capture_one: bool = False  # manual-capture flag for Camera mode

    def count(self):
        with self.lock:
            return len(self.samples)

    def clear_all(self):
        with self.lock:
            self.samples.clear()
            self.images.clear()
            self.capturing = False   # require explicit RESUME_CAPTURE
            self.capture_one = False

if 'sample_store' not in st.session_state:
    st.session_state.sample_store = SampleStore()
store: SampleStore = st.session_state.sample_store
if 'mode' not in st.session_state:
    st.session_state.mode = 'webcam'
if 'show_samples_grid' not in st.session_state:
    st.session_state.show_samples_grid = False

### Init Registration Form ###
registration_form = face_rec.RegistrationForm()
# ── Styling: light-blue selectbox bar ──
# """
# * div[data-testid="stSelectbox"] div[data-baseweb="select"]
#     - This is a CSS attribute selector (hardcoded in Streamlit) targeting Streamlit's internal DOM structure:
#         > div[data-testid="stSelectbox"] 
#             -> selects the outer <div> that Streamlit tags with data-testid="stSelectbox" 
#                (Streamlit adds these attributes to its components for testing/identification)
#         > div[data-baseweb="select"] 
#             -> selects the inner <div> from the Base Web UI library 
#                (which Streamlit uses under the hood for selectboxes), tagged with data-baseweb="select"
#     - The space between them means "find the second element inside the first" (descendant selector)
#     - You need these specific selectors 
#         > because Streamlit doesn't expose class names or IDs for styling. 
#     - The data-* attributes are the only stable way to target its components.
# 
# * !important
#     - This forces the style to override any existing CSS rules, regardless of specificity. 
#     - Streamlit's built-in styles are applied with their own specificity, 
#         > so without !important, your custom styles would likely be ignored 
#         > because Streamlit's defaults take precedence.
# """
st.markdown("""
            <style>
                div[data-testid="stSelectbox"] div[data-baseweb="select"] {
                    background-color: #cfefff !important;
                    border: 1px solid #7dc3e8 !important;
                    border-radius: 8px !important;
                }
            </style>
            """,
    unsafe_allow_html=True,
)



# ═══════════════════  Step 1: Name & Role  ═══════════════════
person_name = st.text_input(label='Name', placeholder='First & Last Name')
try:
    role_df = face_rec.retrive_data(hashname=face_rec.hashname)
    roles = sorted([x for x in role_df['Role'].dropna().astype(str).unique().tolist() if x.strip() != ''])
except Exception:
    roles = []
role_options = ['Me Yorrr'] + [x for x in roles if x != 'Me Yorrr']
selected_role = st.selectbox(label='Select your Role', options=role_options, index=0)
new_role = st.text_input(label='Add a new Role', placeholder='Type a new role if not listed above')
# Use the custom role if provided, otherwise use the selected one
role = new_role.strip() if new_role.strip() else selected_role



# ═══════════════════  Step 2: Mode Selection  ═══════════════════
st.info('Webcam requires a secure origin. Use http://localhost:8501 on this machine, or an HTTPS URL when opening from another device.')
rtc_configuration = get_rtc_configuration()
mode_ui = st.selectbox(
    label='MODE SELECTION',
    options=['OnlineStreaming', 'Camera'],
    index=0 if st.session_state.mode == 'webcam' else 1,
)
st.session_state.mode = 'webcam' if mode_ui == 'OnlineStreaming' else 'snapshot'
st.caption(f"Current mode: {'Online Camera Video Streaming' if st.session_state.mode == 'webcam' else 'Manual Camera Snapshot'}")



# ════════════════════ Step 3: Capture ═══════════════════
### ──────────────────── Step 3a: OnlineStreaming mode ──────────────────── ###
if st.session_state.mode == 'webcam':
    webrtc_ctx = webrtc_streamer(
        key='registration',
        video_frame_callback=Helper_Funcs.make_video_callback(store, registration_form, MAX_SAMPLES, CAPTURE_INTERVAL),
        media_stream_constraints={"video": True, "audio": False},
        rtc_configuration=rtc_configuration,
    )

    # ────────── Live-updating placeholders ────────── #
    status_ph = st.empty()
    info_ph = st.empty()

    is_playing = webrtc_ctx.state.playing
    if is_playing:
        n = store.count()
        with store.lock:
            is_cap = store.capturing

        if n >= MAX_SAMPLES:
            # Done — stop polling, show result
            status_ph.success(f'Done capturing {MAX_SAMPLES} samples!')
            info_ph.info(
                'Please review and if all samples collected are valid, '
                'please click **SAVE_REGISTRATION** button below.'
            )
        elif not is_cap:
            # Paused — show RESUME_CAPTURE button
            if n == 0:
                status_ph.warning('Capture is paused. Press **RESUME_CAPTURE** to start collecting samples.')
            else:
                status_ph.warning(f'Capture paused. {n} samples collected.')
            info_ph.empty()
            if st.button('RESUME_CAPTURE', key='resume_capture'):
                with store.lock:
                    store.capturing = True
                st.rerun()
        else:
            # Actively capturing — poll with live counter
            counter_ph = st.empty()
            while webrtc_ctx.state.playing:
                n = store.count()
                with store.lock:
                    is_cap = store.capturing
                if n >= MAX_SAMPLES or not is_cap:
                    # Done or paused — rerun to show correct UI state
                    st.rerun()
                counter_ph.info(f'Capturing face samples … {n} / {MAX_SAMPLES}\n\n'
                                f'{n} sample(s) collected so far. Need {MAX_SAMPLES - n} more.')
                time.sleep(0.3)
            # Stream was stopped mid-capture
            st.rerun()
    else:
        # Stream not playing
        n = store.count()
        if n == 0:
            status_ph.error('Camera is OFF — click START above to begin capturing samples.')
        else:
            status_ph.warning(f'Camera stopped. {n} sample(s) collected  — click START above to continue capturing samples.')
            info_ph.caption(f'{n} sample(s) available for registration.')
    pass  # save/show buttons rendered in shared section below

### ──────────────────── Step 3b: Manual Camera Snapshot mode ──────────────────── ###
if st.session_state.mode == 'snapshot':
    st.info('Manual Camera mode — live preview with bounding box. '
            'Click **TAKE_SNAPSHOT** to capture one sample at a time.')
    cam_ctx = webrtc_streamer(
        key='registration_camera',
        video_frame_callback=Helper_Funcs.make_camera_callback(store, MAX_SAMPLES),
        media_stream_constraints={"video": True, "audio": False},
        rtc_configuration=rtc_configuration,
    )

    # ────────── Status indicator ────────── #
    cam_status_ph = st.empty()
    cam_info_ph = st.empty()
    is_cam_playing = cam_ctx.state.playing

    if is_cam_playing:
        cam_status_ph.success('Camera is ON')
        n = store.count()
        cam_info_ph.info(f'Samples collected: {n} / {MAX_SAMPLES}')

        if n >= MAX_SAMPLES:
            st.success(f'Done capturing {MAX_SAMPLES} samples! '
                       'Review them with **SHOW_SAMPLES** and click **SAVE_REGISTRATION**.')
        else:
            if st.button('TAKE_SNAPSHOT', type='primary', key='take_snap'):
                with store.lock:
                    store.capture_one = True
                # Wait briefly for callback thread to capture the frame
                for _ in range(30):  # up to ~1.5 s
                    time.sleep(0.05)
                    with store.lock:
                        if not store.capture_one:
                            break
                st.rerun()
    else:
        n = store.count()
        if n == 0:
            cam_status_ph.error('Camera is OFF  — click START above to begin capturing samples.')
        else:
            cam_status_ph.warning(f'Camera stopped. {n} sample(s) collected — click START above to continue capturing samples.')
    pass  # save/show buttons rendered in shared section below



### ──────────────────── Step 3c: Shared save/show UI (both modes) ──────────────────── ###
n = store.count()
can_save = (n == MAX_SAMPLES and person_name.strip() != '')

if n > 0 and n < MAX_SAMPLES:
    st.warning(f'Need exactly {MAX_SAMPLES} samples to save. Currently: {n}. Please collect {MAX_SAMPLES - n} more.')
elif n > MAX_SAMPLES:
    st.error(f'Too many samples ({n}). Please CLEAR_SAMPLES and recapture exactly {MAX_SAMPLES}.')
elif n == MAX_SAMPLES and person_name.strip() == '':
    st.warning('Please enter your name above before saving.')

if st.button('SAVE_REGISTRATION', type='primary', key='save_reg', disabled=not can_save):
    with store.lock:
        samples = list(store.samples)
    return_val = registration_form.save_data_in_redis_db(
        person_name, role, embeddings=samples
    )
    if return_val is True:
        store.clear_all()
        st.session_state.show_samples_grid = False
        st.balloons()
        st.success(f"✅ Registration successful for **{person_name}**!")
        time.sleep(3)
        st.rerun()
    elif return_val == 'redis_false':
        st.error('Redis is not available. Please check connection and try again.')
    elif return_val == 'name_false':
        st.error('Please enter the name: Name cannot be empty or spaces')
    elif return_val == 'samples_false':
        st.error('No valid embedding samples found.')

if n > 0:
    if st.button('SHOW_SAMPLES', key='show_samples_btn'):
        st.session_state.show_samples_grid = not st.session_state.show_samples_grid

    if st.session_state.show_samples_grid:
        with store.lock:
            imgs = [img.copy() for img in store.images]
        if imgs:
            st.subheader('Captured Samples')
            rows, cols = 2, 5
            for r in range(rows):
                row_cols = st.columns(cols)
                for c in range(cols):
                    idx = r * cols + c
                    if idx < len(imgs):
                        row_cols[c].image(
                            cv2.cvtColor(imgs[idx], cv2.COLOR_BGR2RGB),
                            caption=f'Sample {idx + 1}',
                            use_column_width=True,
                        )
        else:
            st.warning('No face images captured for preview.')



### ═══════════════════ Step 4: Clear all samples ═══════════════════ ###
if st.button('CLEAR_SAMPLES'):
    store.clear_all()
    st.session_state.show_samples_grid = False
    st.rerun()
        
