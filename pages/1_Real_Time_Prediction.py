import time, av, cv2, face_rec, traceback
import numpy as np
import streamlit as st 
from streamlit_webrtc import webrtc_streamer 
from helper.helper_funcs import Helper_Funcs
from helper.redis_db_connect import Redis_DB
from helper.webrtc_config import get_rtc_configuration



st.subheader('Real-Time Attendance System')
### Retrive the data from Redis Database ###
hashname = face_rec.hashname
with st.spinner('Retriving Data from Redis DB ...'):
    try: 
        redis_face_db = face_rec.retrive_data(hashname=hashname)
    except Exception as exc:
        st.error(f'Redis data retrieval failed: {exc}')
        st.stop()
if redis_face_db.empty:
    st.warning(f'No registered face data found in Redis hash "{hashname}". Please register faces first.')
    st.stop()
# Validate embeddings are properly loaded
try:
    test_features = redis_face_db['Facial_Features'].tolist()
    test_arr = np.asarray(test_features, dtype=np.float64)
    st.success(f"Data retrieved from Redis — {len(redis_face_db)} person(s), embeddings shape: {test_arr.shape}")
except Exception as exc:
    st.error(f'Embedding data is corrupted: {exc}')
    st.stop()
st.dataframe(redis_face_db[['Name', 'Role']])
st.info('Webcam requires a secure origin. Open this app via http://localhost:8501 on the same machine, or use an HTTPS URL when accessing remotely.')



### Time Setup ###
waitTime = 5 # save logs every 5 seconds
setTime = time.time()
realtimepred = face_rec.RealTimePred() # real time prediction class
rtc_configuration = get_rtc_configuration()
### Real Time Prediction ###
# - streamlit webrtc and av for real time video processing and prediction
# - callback function
def _video_frame_callback(frame):
    # """
    # * The global setTime declaration inside the function is needed 
    #     - because the function writes to it (setTime = time.time() on line 62). 
    # * Without the global keyword, 
    #     - Python would treat that assignment as creating a new local variable, 
    #         > shadowing the module-level one — so the timer would never actually reset.
    # """
    global setTime
    try:
        img = frame.to_ndarray(format="bgr24") # 3 dimension numpy array
        h, w = img.shape[:2]
        print(f"[callback] frame received: {w}x{h}")
        # operation that you can perform on the array
        pred_img = realtimepred.face_prediction(img, redis_face_db, 'Facial_Features', 
                                                ['Name','Role'], thresh=0.5)
        # DEBUG: draw a green test rectangle to verify frames reach the browser
        cv2.putText(pred_img, "LIVE", (15, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
    except Exception as e:
        traceback.print_exc()
        # Draw the error on the frame so the user can SEE it in the browser
        pred_img = frame.to_ndarray(format="bgr24")
        err_msg = str(e)[:80]
        cv2.putText(pred_img, f"ERROR: {err_msg}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
    timenow = time.time()
    difftime = timenow - setTime
    if difftime >= waitTime:
        saved = realtimepred.saveLogs_redis()
        setTime = time.time() # reset time        
        if saved:
            print('Save Data to redis database')
        else:
            print('Skip saving logs (Redis unavailable or no data)')
    return av.VideoFrame.from_ndarray(pred_img, format="bgr24")
webrtc_streamer(
    key="realtimePrediction",
    video_frame_callback=_video_frame_callback,
    media_stream_constraints={"video": True, "audio": False},
    rtc_configuration=rtc_configuration,
)
