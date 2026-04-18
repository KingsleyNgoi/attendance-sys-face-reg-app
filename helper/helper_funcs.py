import cv2, av, time
import numpy as np
import pandas as pd
from sklearn.metrics import pairwise

class Helper_Funcs:
    def  __init__(self):
        pass

    # Resize Image
    def img_resize(img):
        img_arr = cv2.imread(img)      
        new_height = int(img_arr.shape[0]*0.85)
        new_width = int(img_arr.shape[1]*0.85)
        dsize = (new_width, new_height)
        resized_img  = cv2.resize(img_arr, dsize, interpolation=cv2.INTER_AREA)
        return resized_img


    # ML Search Algorithm
    def ml_search_algorithm(test_vector, ori_feature_store_df, 
                            feature_column, name_role=['Name', 'Role'], thresh=0.5):
        """
        cosine similarity base search algorithm
        """
        # Step-1: take the dataframe (collection of data)
        # Create new temporary dataframe and store cosine similarity score
        data_search = ori_feature_store_df.copy()
        
        # Step-2: Index face embeding from the dataframe and convert into array
        X_list = data_search[feature_column].tolist()
        X = np.asarray(X_list, dtype=np.float64)

        # Step-3: Cal. cosine similarity — ensure matching dtype
        test_vec = np.asarray(test_vector, dtype=np.float64).reshape(1, -1)
        # Guard: dimensions must match (e.g. both 512-d)
        if X.shape[1] != test_vec.shape[1]:
            print(f"[ml_search] DIMENSION MISMATCH: stored={X.shape[1]}, live={test_vec.shape[1]}. "
                  f"Likely wrong model loaded (buffalo_sc=256 vs buffalo_l=512).")
            return 'Unknown', ''
        similar = pairwise.cosine_similarity(X, test_vec)
        similar_arr = np.array(similar).flatten()
        data_search['cosine'] = similar_arr

        # Step-4: filter the data
        data_filter = data_search.query(f'cosine >= {thresh}')
        if len(data_filter) > 0:
            # Step-5: get the person name
            data_filter.reset_index(drop=True, inplace=True)
            argmax = data_filter['cosine'].argmax()
            person_name, person_role = data_filter.loc[argmax][name_role]
        else:
            person_name = 'Unknown'
            person_role = ''
        return person_name, person_role
    

    # Retrive logs data and show in Report.py
    # - extract data from redis list
    def load_logs(name, end=-1):
        import face_rec
        if face_rec.redis_db_instance.r is None:
            return []
        logs_list = face_rec.redis_db_instance.r.lrange(name, start=0, end=end)
        return [x.decode() if isinstance(x, bytes) else x for x in logs_list]

    def parse_logs(raw_logs):
        """Parse raw log strings into a DataFrame with Name, Role, Time columns."""
        rows = []
        for entry in raw_logs:
            parts = entry.split('@')
            if len(parts) >= 3:
                rows.append({'Name': parts[0], 'Role': parts[1], 'Time': parts[2]})
            else:
                rows.append({'Name': entry, 'Role': '', 'Time': ''})
        df = pd.DataFrame(rows)
        if not df.empty and 'Time' in df.columns:
            df['Time'] = pd.to_datetime(df['Time'], errors='coerce')
        return df


    # ── WebRTC video callback factories for Registration Form ──
    def make_video_callback(store_ref, reg_form, max_samples, capture_interval):
        # """Auto-capture callback for OnlineStreaming mode."""
        # """
        # * last_capture_time = [0.0] 
        #   - It needs to be mutable so the inner _callback function can update it. 
        #   - In Python, a closure can read a variable from the enclosing scope, 
        #       > but can't reassign it (without nonlocal). 
        #   - By using a list, you mutate the contents (last_capture_time[0] = now) 
        #       > instead of reassigning the variable itself. It's the same trick as global setTime but for closures.
        # 
        # * Alternative: nonlocal last_capture_time with last_capture_time = 0.0 would also work.
        # """
        last_capture_time = [0.0]
        def _callback(frame):
            # """ 
            # * frame 
            #   - is provided by streamlit-webrtc.
            #   - When you pass video_frame_callback=_make_video_callback(...), 
            #       > the WebRTC library calls _callback(frame) automatically for every video frame from the webcam. 
            #   - You don't supply it — the framework does. 
            #   - That's why it's a parameter of _callback, not _make_video_callback.
            # """
            import face_rec
            img = frame.to_ndarray(format='bgr24')
            with face_rec.faceapp_lock:
                results = face_rec.faceapp.get(img, max_num=1)

            with store_ref.lock:
                n = len(store_ref.samples)
                is_capturing = store_ref.capturing

            embedding = None
            for res in results:
                # """
                # * Are fx1, fy1 always 0,0 and fx2, fy2 always w,h?
                #   - No. x1, y1, x2, y2 come from the face bounding box 
                #       > they're the face rectangle coordinates, not the full image. 
                #   - The max(0, ...) and min(w, ...) are just clamping 
                #       > to ensure the box doesn't go outside image boundaries 
                #         (the detector can sometimes return negative coordinates or boxes exceeding the image edge). 
                #   - So:
                #       > fx1, fy1 = face top-left corner (clamped to image bounds)
                #       > fx2, fy2 = face bottom-right corner (clamped to image bounds)
                # * The crop img[fy1:fy2, fx1:fx2] extracts just the face region, not the full image.
                # """
                x1, y1, x2, y2 = res['bbox'].astype(int)
                embedding = res['embedding']

                # Crop face BEFORE drawing annotations
                h, w = img.shape[:2]
                fx1, fy1 = max(0, x1), max(0, y1)
                fx2, fy2 = min(w, x2), min(h, y2)
                face_crop = None
                if fy2 > fy1 and fx2 > fx1:
                    face_crop = img[fy1:fy2, fx1:fx2].copy()
                reg_form.last_face_crop = face_crop

                cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 1)
                label = f"samples = {n}"
                cv2.putText(img, label, (x1, y1 - 10),
                            cv2.FONT_HERSHEY_DUPLEX, 0.6, (255, 255, 0), 2)
                # """
                # * time.monotonic()
                #   - it returns a clock time in seconds that only moves forward 
                #   - it's never affected by system clock changes 
                #     (like NTP adjustments or the user changing the time).
                #   - Unlike time.time(), 
                #       > it can't jump backwards. 
                #       > This makes it reliable for measuring elapsed intervals like now - last_capture_time[0] >= CAPTURE_INTERVAL.
                # """
                now = time.monotonic()
                if (embedding is not None and is_capturing and n < max_samples
                        and now - last_capture_time[0] >= capture_interval):
                    with store_ref.lock:
                        if len(store_ref.samples) < max_samples:
                            store_ref.samples.append(
                                np.asarray(embedding, dtype=np.float64)
                            )
                            if face_crop is not None:
                                store_ref.images.append(face_crop.copy())
                            if len(store_ref.samples) >= max_samples:
                                store_ref.capturing = False
                            last_capture_time[0] = now
            return av.VideoFrame.from_ndarray(img, format='bgr24')
        return _callback

    def make_camera_callback(store_ref, max_samples):
        """Manual single-frame capture callback for Camera/Snapshot mode."""
        def _callback(frame):
            import face_rec
            img = frame.to_ndarray(format='bgr24')
            with face_rec.faceapp_lock:
                results = face_rec.faceapp.get(img, max_num=1)

            with store_ref.lock:
                n = len(store_ref.samples)
                want_capture = store_ref.capture_one

            for res in results:
                x1, y1, x2, y2 = res['bbox'].astype(int)
                embedding = res['embedding']

                h, w = img.shape[:2]
                fx1, fy1 = max(0, x1), max(0, y1)
                fx2, fy2 = min(w, x2), min(h, y2)
                face_crop = None
                if fy2 > fy1 and fx2 > fx1:
                    face_crop = img[fy1:fy2, fx1:fx2].copy()

                cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 1)
                label = f"samples = {n}"
                cv2.putText(img, label, (x1, y1 - 10),
                            cv2.FONT_HERSHEY_DUPLEX, 0.6, (255, 255, 0), 2)

                if want_capture and embedding is not None and n < max_samples:
                    with store_ref.lock:
                        if store_ref.capture_one:
                            store_ref.samples.append(
                                np.asarray(embedding, dtype=np.float64)
                            )
                            if face_crop is not None:
                                store_ref.images.append(face_crop.copy())
                            store_ref.capture_one = False
            return av.VideoFrame.from_ndarray(img, format='bgr24')
        return _callback
