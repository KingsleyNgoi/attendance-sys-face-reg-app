import redis
import numpy as np
import pandas as pd


class Redis_DB:
    def __init__(self, hostname, port, password):
        self.hostname = hostname
        self.port = port
        self.password = password
        self.r = None
        try:
            self.r = redis.StrictRedis(host=self.hostname, port=self.port, password=self.password)
            # quick check
            try:
                self.r.ping()
                print('Connected to Redis successfully')
            except Exception:
                print('Warning: Redis client created but ping failed; continuing without Redis')
                self.r = None
        except Exception as exc:
            print(f'Warning: Could not create Redis client: {exc}')
            self.r = None



    # Retrive Data from database
    def retrive_data(self, redis_connect, hashname=None, name=None):
        # Backward-compatible signature: supports retrive_data(hashname=...) and retrive_data(name=...)
        target_hash = hashname if hashname is not None else name
        if target_hash is None:
            raise ValueError('Missing Redis hash name. Provide hashname or name.')
        if redis_connect is None:
            raise ConnectionError('Redis client is not available.')
        
        retrive_dict = redis_connect.hgetall(target_hash)
        if not retrive_dict:
            return pd.DataFrame(columns=['Name', 'Role', 'Facial_Features'])
        
        # Convert the retrieved data from Redis cloud into Pandas Series
        retrive_series = pd.Series(retrive_dict)
        # Auto-detect dtype: 
        # - old data stored as float32 (2048 bytes for 512-d),
        # - new data stored as float64 (4096 bytes for 512-d).
        # """
        # * For a nested function like _parse_embedding, 
        #     - this benefit is minimal since the scope already communicates "internal." 
        #     - It's more impactful at module level (like _this_dir, _model_root in your face_rec.py) 
        #         > where everything is technically accessible via import.
        # """
        def _parse_embedding(x):
            nbytes = len(x)
            if nbytes == 512 * 4:  # float32
                return np.frombuffer(x, dtype=np.float32).astype(np.float64)
            elif nbytes == 512 * 8:  # float64
                return np.frombuffer(x, dtype=np.float64)
            else:
                # Fallback: try float64 first, then float32
                arr = np.frombuffer(x, dtype=np.float64)
                if arr.shape[0] == 512:
                    return arr
                arr = np.frombuffer(x, dtype=np.float32).astype(np.float64)
                return arr
            
        retrive_series = retrive_series.apply(_parse_embedding)
        # Get the hashed data index's indices
        index = retrive_series.index
        # Decode the hashed data index's indices
        index = list(map(lambda x: x.decode(), index))
        # After decode the Facial feature index, convert the Facial feature's data into index
        retrive_series.index = index
        # Reset the index of the retrieved "Pandas Series data from Redis cloud and Assign columns name to the data
        retrive_df =  retrive_series.to_frame().reset_index()
        retrive_df.columns = ['Name_Role', 'Facial_Features']
        # Split only on first separator and tolerate malformed rows with missing role
        name_role_split = retrive_df['Name_Role'].str.split('@', n=1, expand=True)
        name_role_split = name_role_split.reindex(columns=[0, 1], fill_value='')
        retrive_df[['Name', 'Role']] = name_role_split
        retrive_df.drop(columns=["Name_Role"], inplace=True)
        return retrive_df[['Name', 'Role', 'Facial_Features']]