import face_rec
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
from helper.helper_funcs import Helper_Funcs



st.subheader('Reporting')
st.success('Welcome to my attendance system report!')
### Time range options ###
TIME_RANGE_OPTIONS = {
    '1 Hour': timedelta(hours=1),
    '3 Hours': timedelta(hours=3),
    '6 Hours': timedelta(hours=6),
    '12 Hours': timedelta(hours=12),
    '1 Day': timedelta(days=1),
    '3 Days': timedelta(days=3),
    '7 Days (1 Week)': timedelta(days=7),
}
name = 'attendance:logs'



### Tabs to show the info ###
tab1, tab2 = st.tabs(['Registered Data', 'Logs'])
with tab1:
    if st.button('Refresh Data'):
        st.session_state['reg_data_loaded'] = True

    if st.session_state.get('reg_data_loaded', False):
        with st.spinner('Retriving Data from Redis DB ...'):
            try:
                redis_face_db = face_rec.retrive_data(hashname=face_rec.hashname)
            except Exception as exc:
                st.error(f'Failed to load registered data: {exc}')
                redis_face_db = pd.DataFrame(columns=['Name', 'Role'])

        if redis_face_db.empty:
            st.info('No registered data found in database.')
        else:
            # Build display dataframe with index
            display_df = redis_face_db[['Name', 'Role']].reset_index(drop=True)
            display_df.index.name = 'Index'
            st.dataframe(display_df, use_container_width=True)

            # Dropdown to select entry + Delete button
            entry_options = [
                f"{i} — {row['Name']} ({row['Role']})"
                for i, row in display_df.iterrows()
            ]
            col_sel, col_del = st.columns([3, 1])
            with col_sel:
                selected = st.selectbox(
                    'Select entry to view or delete',
                    options=entry_options,
                    key='entry_selector'
                )
            with col_del:
                # """
                # * It inserts an HTML <br> (line break) 
                #     - to push the DELETE button down 
                #     - so it visually aligns with the selectbox next to it.
                # * Streamlit's 
                #     - st.selectbox renders with a label above it, 
                #         > which adds extra height. 
                #     - st.button in the adjacent column 
                #         > has no label, so it sits higher. 
                # * The <br> 
                #     - adds roughly one line of spacing above the button to compensate, 
                #         > making them appear on the same row.
                # * It's a common Streamlit hack 
                #     - Streamlit doesn't have built-in vertical alignment for columns, 
                #         > so injecting a <br> is a quick workaround. 
                #     - unsafe_allow_html=True 
                #         > is required because Streamlit strips raw HTML by default.
                # """
                st.markdown('<br>', unsafe_allow_html=True)  # vertical align
                delete_clicked = st.button('DELETE', type='primary', key='delete_entry')

            if selected is not None:
                sel_idx = int(selected.split(' — ')[0])
                sel_row = display_df.loc[sel_idx]
                st.info(f"**Index:** {sel_idx}  |  **Name:** {sel_row['Name']}  |  **Role:** {sel_row['Role']}")

                if delete_clicked:
                    # Build the Redis hash key: "Name@Role"
                    redis_key = f"{sel_row['Name']}@{sel_row['Role']}"
                    if face_rec.redis_db_instance.r is not None:
                        face_rec.redis_db_instance.r.hdel(face_rec.hashname, redis_key)
                        st.success(f"Deleted: {sel_row['Name']} ({sel_row['Role']})")
                        st.rerun()
                    else:
                        st.error('Redis is not available. Cannot delete.')

with tab2:
    # ── Controls row ──
    col_range, col_format = st.columns([2, 1])
    with col_range:
        time_range_label = st.selectbox(
            'Time Range',
            options=list(TIME_RANGE_OPTIONS.keys()),
            index=4,  # default: 1 Day
            key='log_time_range'
        )
    with col_format:
        display_format = st.radio(
            'Display Format',
            options=['Table', 'JSON'],
            horizontal=True,
            key='log_display_format'
        )

    if st.button('Refresh Logs'):
        st.session_state['logs_loaded'] = True

    if st.session_state.get('logs_loaded', False):
        raw_logs = Helper_Funcs.load_logs(name=name)
        if len(raw_logs) == 0:
            st.info('No logs found or Redis is unavailable.')
            st.session_state['logs_loaded'] = False
        else:
            logs_df = Helper_Funcs.parse_logs(raw_logs)

            # Filter by selected time range
            cutoff = datetime.now() - TIME_RANGE_OPTIONS[time_range_label]
            if 'Time' in logs_df.columns and logs_df['Time'].notna().any():
                filtered_df = logs_df[logs_df['Time'] >= cutoff].copy()
            else:
                filtered_df = logs_df.copy()

            if filtered_df.empty:
                st.warning(f'No logs found within the last {time_range_label}.')
            else:
                filtered_df = filtered_df.reset_index(drop=True)
                st.caption(f'Showing {len(filtered_df)} log(s) from the last {time_range_label}')

                if display_format == 'Table':
                    st.dataframe(filtered_df, use_container_width=True)
                else:
                    st.json(filtered_df.to_dict(orient='records'))

            ### Clear Logs button ###
            # - only visible when logs exist 
            #   > (inside the if len(raw_logs) > 0 block)
            if st.button('CLEAR LOGS', type='primary', key='clear_logs'):
                if face_rec.redis_db_instance.r is not None:
                    face_rec.redis_db_instance.r.delete(name)
                    st.success('All logs cleared.')
                    st.session_state['logs_loaded'] = False
                    st.rerun()
                else:
                    st.error('Redis is not available. Cannot clear logs.')

