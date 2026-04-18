import streamlit as st

st.set_page_config(page_title='Attendance System', layout='wide')
st.header('Attendance System using Face Recognition')
# Apply Spinner for reducing loading time of the model and connecting to Redis database automatically.
with st.spinner("Loading Models and Conneting to Redis db ..."):
    import face_rec
st.success('Model loaded sucesfully')
st.success('Redis db sucessfully connected')
