# Now import other dependencies
import os, sys, cv2, threading
import numpy as np
import pandas as pd
from datetime import datetime
# Import from user-defined modules
from helper.helper_funcs import Helper_Funcs
from helper.redis_db_connect import Redis_DB
# Insight face
from insightface.app import FaceAnalysis



### Set environment variables ###
os.environ['OMP_NUM_THREADS'] = '1'
# Set Redis connection parameters from environment variables (with defaults)
hostname_endpoint = 'redis-17847.c267.us-east-1-4.ec2.cloud.redislabs.com'
port = 17847
password = ''
hashname = 'Facial_Features_Store'



### Redis Database Global Access ###
# Connect to Redis Client (wrap in try/except so failures don't stop execution)
redis_db_instance = Redis_DB(hostname_endpoint, port, password)
# Module-level wrapper so pages can call face_rec.retrive_data(hashname=...)
def retrive_data(hashname=None, name=None):
    return redis_db_instance.retrive_data(redis_db_instance.r, hashname=hashname, name=name)



### Configure face analysis ###
# """
# * The leading underscore 
#     - is a Python convention signaling these are private/internal variables. 
#     - they're only used for configuring faceapp and aren't meant to be imported or used by other modules.
# * Since face_rec.py 
#     - is imported by other files (pages, etc.), 
#         > anything at module level becomes accessible via import. 
#         > The _ prefix tells other developers "this is an implementation detail, 
#           not part of the public API." 
# * Python's from face_rec import * 
#     - will also skip names starting with _ by default.
# 
# * InsightFace in this app runs entirely on ONNX Runtime, not PyTorch.
#   - providers=['CUDAExecutionProvider', 'CPUExecutionProvider'] 
#     > tells ONNX Runtime: "use CUDA GPU if available, otherwise fall back to CPU. 
# """
# warning: don't set detection threshold, det_thresh < 0.3
_this_dir = os.path.dirname(os.path.abspath(__file__))
_model_root = os.path.join(_this_dir, 'insightface_model')
faceapp = FaceAnalysis(name='buffalo_l',
                        root=_model_root,
                        # ['CUDAExecutionProvider', 'CPUExecutionProvider'] 
                        # - if have GPU, it will automatically connect to GPU else 
                        providers=['CUDAExecutionProvider', 'CPUExecutionProvider']) 
faceapp.prepare(ctx_id=0, det_size=(640, 640))

# Verify the recognition model produces 512-d embeddings (buffalo_l)
# - buffalo_sc produces 256-d which is incompatible with stored data
# """
# * faceapp.models contains multiple sub-models (detection, recognition, gender/age, landmark).
#     - hasattr(m, 'embedding_size') checks whether the model object m has an attribute called embedding_size.
# """
_rec_model = [m for m in faceapp.models if hasattr(m, 'embedding_size')]
if _rec_model:
    _emb_size = _rec_model[0].embedding_size if hasattr(_rec_model[0], 'embedding_size') else None
    print(f"Recognition model embedding size: {_emb_size}")
    if _emb_size and _emb_size != 512:
        print(f"WARNING: Expected 512-d embeddings (buffalo_l) but got {_emb_size}-d. Check model path!")
else:
    # Alternative check: get output shape from the recognition model
    print(f"FaceAnalysis loaded models from: {_model_root}")
    print(f"Models loaded: {[type(m).__name__ for m in faceapp.models]}")

# Thread lock for faceapp — ONNX Runtime sessions are NOT thread-safe
# - This lock ensures that only one thread can call faceapp.get() at a time, 
#   preventing DLL initialization errors and crashes when processing video frames in real-time.
# - if two threads call faceapp.get() simultaneously, 
#   it can crash or produce corrupted results.
faceapp_lock = threading.Lock()



### Real Time Prediction ###
# - It is suggested to use logs dict to save the logs data in real time 
#   and then push the logs data to Redis database (in-memory DB) every 1 mins.
# - We need to save logs for every 1 mins
#   > it is suggested to use class module instead of functions.
# """
# * Redis cloud database 
#     - is in-memory database which stores data in RAM and use cache technique 
#     - functions are "stateless"
#         > once a function finishes running, all the variables inside it disappear.
# * With a Function: 
#     - You would have to define your logs dictionary globally 
#       or pass it back and forth as an argument every single time you process a frame. 
#         > This makes your code messy and prone to bugs.
# * With a Class: 
#     - The self.logs dictionary lives inside the instance of the class. 
#     - It acts as a persistent buffer. 
#     - It stays in memory while your camera is running, 
#         > allowing you to collect data over hundreds of frames 
#           and only "dump" it to Redis when you are ready.
# * Local RAM (Your Python Class)
#     - Role: The "Waiting Room."
# * Remote RAM (Redis Cloud Database)
#     - Role: The "Permanent Record."
# """
class RealTimePred:
    def __init__(self):
        self.logs = dict(Name=[], Role=[], Current_Time=[])

    def reset_dict(self):
        self.logs = dict(Name=[], Role=[], Current_Time=[])
    
    # This function is called for every video frame processed by the webcam stream.
    # - It updates the self.logs dictionary with the recognized person's name, role, and timestamp.
    def saveLogs_redis(self):
        if redis_db_instance.r is None:
            self.reset_dict()
            return False
        
        # Step-1: create a logs dataframe
        dataframe = pd.DataFrame(self.logs)        
        if dataframe.empty:
            self.reset_dict()
            return False
        
        # Step-2: drop the duplicate information (distinct name)
        dataframe.drop_duplicates('Name', inplace=True) 

        # Step-3: push data to redis database (list)
        #         - encode the data
        name_list = dataframe['Name'].tolist()
        role_list = dataframe['Role'].tolist()
        ctime_list = dataframe['Current_Time'].tolist()
        encoded_data = []
        for name, role, ctime in zip(name_list, role_list, ctime_list):
            if name != 'Unknown':
                concat_string = f"{name}@{role}@{ctime}"
                encoded_data.append(concat_string)
        if len(encoded_data) > 0:
            redis_db_instance.r.lpush('attendance:logs', *encoded_data)
        self.reset_dict()     
        return True

    # Real-time prediction function 
    def face_prediction(self, img_file, ori_feature_store_df, feature_column, name_role=['Name', 'Role'], thresh=0.5):
        # Step-0: find the time
        current_time = str(datetime.now())

        # Step-1: take the test image and normalize input and apply to insight face
        #           - support both file path and ndarray inputs
        if isinstance(img_file, str):
            img_arr = cv2.imread(img_file)
            if img_arr is None:
                raise ValueError(f'Could not read image from path: {img_file}')
        elif isinstance(img_file, np.ndarray):
            img_arr = img_file.copy()
        else:
            raise TypeError('img_file must be a file path or numpy.ndarray')
        
        with faceapp_lock:
            results = faceapp.get(img_arr)
        print(f'[RealTimePred] faces detected: {len(results)}')
        if not results:
            print('[RealTimePred] No face detected in frame')

        # Step-2: use for loop and extract each embedding and pass to ml_search_algorithm
        for res in results:
            x1, y1, x2, y2 = res['bbox'].astype(int)
            embeddings = res.get('embedding')
            print(f'[RealTimePred] bbox=({x1},{y1})-({x2},{y2}), has_embedding={embeddings is not None}')
            if embeddings is None:
                continue
            person_name, person_role = Helper_Funcs.ml_search_algorithm(embeddings, ori_feature_store_df, feature_column, 
                                                                        name_role=name_role, thresh=thresh)
            # Step-3: Define display name
            if person_name == "Hilary Chong":
                display_name = "<3 " + person_name
            else:
                display_name = person_name

            # Step-4: Define color for detection "succeed" or 'fail'
            if person_name == 'Unknown':
                color =(0, 0, 255) # bgr
            else:
                color = (0, 255, 0)

            # Step-5: Draw name above box, role below box
            cv2.putText(img_arr, display_name, (x1, y1 - 10), cv2.FONT_HERSHEY_DUPLEX, 0.7, color, 2)
            cv2.putText(img_arr, person_role, (x1, y2 + 25), cv2.FONT_HERSHEY_DUPLEX, 0.6, color, 1)
            cv2.rectangle(img_arr, (x1, y1), (x2, y2), color, 2)
            print(f'[RealTimePred] drew box for {person_name}, img_arr id={id(img_arr)}, shape={img_arr.shape}')
            # Step-6: Save info in logs dict.
            self.logs['Name'].append(person_name)
            self.logs['Role'].append(person_role)
            self.logs['Current_Time'].append(current_time)
        return img_arr



### Registration Form ###
class RegistrationForm:
    def __init__(self):
        self.sample = 0
        self.last_face_crop = None

    def reset(self):
        self.sample = 0
        self.last_face_crop = None
        
    def get_embedding(self, frame, show_counter=True):
        # Get results from insightface model
        with faceapp_lock:
            results = faceapp.get(frame, max_num=1)
        embeddings = None
        self.last_face_crop = None
        for res in results:
            self.sample += 1
            x1, y1, x2, y2 = res['bbox'].astype(int)
            # Crop face BEFORE drawing annotations
            h, w = frame.shape[:2]
            fx1, fy1 = max(0, x1), max(0, y1)
            fx2, fy2 = min(w, x2), min(h, y2)
            if fy2 > fy1 and fx2 > fx1:
                self.last_face_crop = frame[fy1:fy2, fx1:fx2].copy()
            cv2.rectangle(frame, (x1,y1), (x2,y2), (0, 255, 0), 1)
            if show_counter:
                # Put text samples info
                text = f"samples = {self.sample}"
                cv2.putText(frame, text, (x1, y1), cv2.FONT_HERSHEY_DUPLEX, 0.6, (255, 255, 0), 2)
            # Facial features
            embeddings = res.get('embedding')
        return frame, embeddings
    
    def save_data_in_redis_db(self, name, role, embeddings=None):
        # Validation name
        if name is not None:
            if name.strip() != '':
                key = f'{name}@{role}'
            else:
                return 'name_false'
        else:
            return 'name_false'
        # Step-1: collect embeddings from in-memory samples only.
        x_array = np.asarray(embeddings, dtype=np.float64) if embeddings is not None else np.asarray([])
        if x_array.size == 0:
            return 'samples_false'
        if x_array.ndim == 1:
            x_array = x_array.reshape(1, -1)
        if x_array.shape[1] != 512:
            return 'samples_false'
        # Step-3: cal. mean embeddings
        x_mean = x_array.mean(axis=0)
        x_mean = x_mean.astype(np.float64)
        x_mean_bytes = x_mean.tobytes()
        # Step-4: save this into redis database
        # Redis hashes
        if redis_db_instance.r is None:
            return 'redis_false'
        redis_db_instance.r.hset(name=hashname, key=key, value=x_mean_bytes)
        self.reset() 
        return True
