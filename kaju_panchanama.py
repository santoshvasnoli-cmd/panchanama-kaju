import streamlit as st
import pandas as pd
import datetime
import os
import time
from PIL import Image, ImageDraw, ImageFont
from streamlit_js_eval import get_geolocation
from sqlalchemy import create_engine, text

# ---------------------------------------------------------
# १. पेज सेटअप (ही कमांड नेहमी सर्वात वर असायला हवी)
# ---------------------------------------------------------
st.set_page_config(page_title="पीक पंचनामा प्रणाली", layout="centered")

st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stButton>button { width: 100%; border-radius: 10px; height: 3em; background-color: #007bff; color: white; }
    </style>
    """, unsafe_allow_html=True)
# ---------------------------------------------------------
# २. डेटाबेस कनेक्शन सेटअप (Postgres / SQLite Fallback)
# ---------------------------------------------------------
def get_db_engine():
    # Render किंवा Railway वरील DATABASE_URL मधील postgres:// ला postgresql:// मध्ये बदलणे
    db_url = st.secrets.get("DATABASE_URL", os.environ.get("DATABASE_URL", "sqlite:///panchnama_local.db"))
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    return create_engine(db_url)

engine = get_db_engine()

def load_data_from_db():
    try:
        return pd.read_sql("SELECT * FROM panchnama_records", engine)
    except Exception:
        # जर टेबल नसेल तर रिकामी फ्रेम
        return pd.DataFrame()
    
# ---------------------------------------------------------
# २. युजर लॉगिन क्रिडेन्शियल्स व सेटअप
# ---------------------------------------------------------
USER_CREDENTIALS = {
    "officer1": "Sdp*1354",
    "officer2": "sule123",
    "officer3": "vithal456",
    "officer4": "mahadev789"
}

USER_NAMES = {
    "officer1": "संतोष धनाजी पाटील (तलाठी)",
    "officer2": "आर. बी. शिंदे (ग्रामसेवक)",
    "officer3": "एस. एम. जाधव (कृषी सहाय्यक)",
    "officer4": "व्ही. के. कांबळे (मदतनीस)"
}

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    st.session_state['user_id'] = ""

def login_page():
    st.title("🔐 अधिकारी लॉगिन")
    with st.container():
        user = st.text_input("युजर आयडी (User ID)")
        pwd = st.text_input("पासवर्ड (Password)", type="password")
        if st.button("लॉगिन करा"):
            if user in USER_CREDENTIALS and USER_CREDENTIALS[user] == pwd:
                st.session_state['logged_in'] = True
                st.session_state['user_id'] = user
                st.session_state['user_display_name'] = USER_NAMES[user]
                st.rerun()
            else:
                st.error("❌ चुकीचा युजर आयडी किंवा पासवर्ड")

if not st.session_state['logged_in']:
    login_page()
    st.stop()

# लॉगिन यशस्वी झाल्यावर साइडबार
st.sidebar.success(f"लॉगिन: {st.session_state['user_display_name']}")
if st.sidebar.button("Log Out"):
    st.session_state['logged_in'] = False
    st.rerun()

# ---------------------------------------------------------
# ३. GPS लोकेशन मिळवणे
# ---------------------------------------------------------
loc = get_geolocation()
lat, lon = None, None

if loc and isinstance(loc, dict) and 'coords' in loc:
    lat = loc['coords']['latitude']
    lon = loc['coords']['longitude']
elif loc and isinstance(loc, dict) and 'latitude' in loc:
    lat = loc['latitude']
    lon = loc['longitude']

# ---------------------------------------------------------
# ४. वॉटरमार्क फंक्शन
# ---------------------------------------------------------
def add_watermark(image_file, lat, lon, timestamp, village, gat_no, farmer_name):
    img = Image.open(image_file)
    draw = ImageDraw.Draw(img)
    try:
        font_path = "Lohit Marathi Regular.ttf" 
        font = ImageFont.truetype(font_path, 20)
    except:
        font = ImageFont.load_default()
    
    text = (f"दिनांक: {timestamp}\n"
            f"अक्षांश: {lat} | रेखांश: {lon}\n"
            f"गाव: {village} | गट क्र: {gat_no}\n"
            f"खातेदार: {farmer_name}")
    
    draw.text((20, 20), text, fill=(255, 255, 255), font=font, stroke_width=2, stroke_fill=(0,0,0))
    return img

# ---------------------------------------------------------
# ५. डेटा लोड करणे
# ---------------------------------------------------------
@st.cache_data
def load_khatedar_data():
    file_name = "khatedar list.xlsx"
    if os.path.exists(file_name):
        df = pd.read_excel(file_name)
        df.columns = df.columns.str.strip()
        df['गट क्रमांक'] = df['गट क्रमांक'].astype(str).str.strip()
        df['खाते क्रमांक'] = df['खाते क्रमांक'].astype(str).str.strip()
        return df
    else:
        st.error(f"❌ '{file_name}' फाईल सापडली नाही. कृपया फाईल तपासा.")
        return None

df = load_khatedar_data()

if df is not None:
    st.title("🌾 पीक पंचनामा - साझा सुळेरान")
    
    if lat and lon:
        st.success(f"📍 GPS लोकेशन प्राप्त: {lat}, {lon}")
    else:
        st.warning("📍 कृपया लोकेशन (GPS) चालू करा आणि परवानगी द्या.")

    # ---------------------------------------------------------
    # ६. निवड प्रक्रिया (गाव / गट / खातेदार)
    # ---------------------------------------------------------
    st.subheader("शेतकरी माहिती निवडा")
    village_list = df['गाव'].unique()
    village = st.selectbox("गाव निवडा", village_list)
    
    filtered_village = df[df['गाव'] == village]
    gat_list = filtered_village['गट क्रमांक'].unique()
    selected_gat = st.selectbox("गट क्रमांक निवडा", gat_list)
    
    gat_details = filtered_village[filtered_village['गट क्रमांक'] == selected_gat]
    
    farmer_options = []
    mapping = {}

    for _, row in gat_details.iterrows():
        k_no = str(row['खाते क्रमांक']).strip()
        raw_names = str(row['खातेदाराचे नाव'])
        names_in_row = [n.strip() for n in raw_names.split(",")]
        
        for n in names_in_row:
            display_text = f"{k_no} - {n}"
            farmer_options.append(display_text)
            mapping[display_text] = {
                'khata_no': k_no,
                'name': n,
                'area': float(row['खातेदार क्षेत्र'])
            }

    selected_option = st.selectbox("गटातील खातेदार निवडा", farmer_options)
    final_data = mapping[selected_option]
    
    # मागील नोंदी तपासून क्षेत्र काढणे
    already_filled = 0.0
    csv_file = "offline_panchnama_records.csv"
    past_records = pd.DataFrame()

    if os.path.exists(csv_file):
        temp_df = pd.read_csv(csv_file)
        temp_df['खाते_क्र'] = temp_df['खाते_क्र'].astype(str).str.strip()
        temp_df['गट_क्र'] = temp_df['गट_क्र'].astype(str).str.strip()
        
        past_records = temp_df[
            (temp_df['गाव'] == village) & 
            (temp_df['गट_क्र'] == str(selected_gat)) & 
            (temp_df['खाते_क्र'] == str(final_data['khata_no']))
        ]
        already_filled = past_records['नुकसान_क्षेत्र'].sum()

    cell_total = final_data['area']
    remaining_area = round(max(0.0, cell_total - already_filled), 4)

    col1, col2, col3 = st.columns(3)
    col1.metric("एकूण क्षेत्र", f"{cell_total} हे.")
    col2.metric("नोंदणी झालेले", f"{round(already_filled, 4)} हे.")
    col3.metric("शिल्लक उपलब्ध", f"{remaining_area} हे.")

    # मागील नोंदींचा तक्ता
    if not past_records.empty:
        st.markdown("---")
        st.subheader("📋 आधी नोंदवलेली पिके")
        summary_df = past_records[['खातेदार','गट_क्र', 'खाते_क्र', 'पीक','नुकसान_क्षेत्र']].rename(
            columns={
                'खातेदार': 'खातेदाराचे नाव',
                'गट_क्र': 'गट क्रमांक',
                'खाते_क्र': 'खाते क्रमांक',
                'पीक': 'पीक',
                'नुकसान_क्षेत्र': 'नोंदवलेले क्षेत्र (हे.)'
            }
        )
        st.table(summary_df)
    else:
        st.info("ℹ️ या खात्यावर अद्याप कोणतीही पीक नोंदणी झालेली नाही.")

    # ---------------------------------------------------------
    # ७. पंचनामा फॉर्म
    # ---------------------------------------------------------
    st.subheader("नुकसानीचा तपशील")
    with st.form("panchnama_form", clear_on_submit=True):
        selected_crop = st.selectbox("नुकसान झालेले पीक निवडा", 
                                     options=["काजू"])
        
        damage_area = st.number_input(f"नुकसान क्षेत्र भरा (कमाल {remaining_area})", 
                                     min_value=0.0, max_value=float(remaining_area) if remaining_area > 0 else 0.0, 
                                     step=0.0001, format="%.4f")
        
        tree_count = st.number_input("बाधित काजू झाडांची संख्या", 
                                         min_value=1, step=1, value=1)
        photo = st.camera_input("पिकाचा फोटो घ्या")
        remark = st.text_area("शेरा (काही असल्यास)")
        
        submit = st.form_submit_button("पंचनामा जतन करा")

        if submit:
            if selected_crop == "निवडा...":
                st.error("⚠️ कृपया पीक निवडा.")
            elif not photo:
                st.error("❌ कृपया फोटो काढा!")
            elif not lat:
                st.error("❌ GPS लोकेशन मिळाले नाही. कृपया ब्राऊझरमध्ये लोकेशन अलाऊ करा.")
            elif damage_area <= 0:
                st.error("⚠️ कृपया वैध नुकसान क्षेत्र भरा.")
            else:
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # फोटो वॉटरमार्क करणे
                watermarked_img = add_watermark(photo, lat, lon, timestamp, village, selected_gat, final_data['name'])
                
                if not os.path.exists('photos'): 
                    os.makedirs('photos')
                
                photo_filename = f"photos/{village}_{selected_gat}_{datetime.datetime.now().strftime('%H%M%S')}.jpg"
                watermarked_img.save(photo_filename)

                # डेटा सेव्ह करणे
                data_to_save = {
                    "वेळ": timestamp, 
                    "गाव": village, 
                    "गट_क्र": str(selected_gat),
                    "खाते_क्र": str(final_data['khata_no']),
                    "खातेदार": final_data['name'],
                    "पीक": selected_crop, 
                    "नुकसान_क्षेत्र": damage_area,
                    "बाधित_झाडांची_संख्या": int(tree_count),
                    "अक्षांश": lat, 
                    "रेखांश": lon,
                    "फोटो_पाथ": photo_filename,
                    "नोंदणी_अधिकारी": st.session_state['user_display_name'],
                    "शेरा": remark
                }
                
                save_df = pd.DataFrame([data_to_save])
                save_df.to_sql("panchnama_records", engine, if_exists='append', index=False)
                
                st.success("✅ पंचनामा यशस्वीरित्या जतन झाला!")
                st.balloons()
                time.sleep(2)
                st.rerun()

    # ---------------------------------------------------------
    # ८. अहवाल आणि जुन्या नोंदी पाहणे
    # ---------------------------------------------------------
    if os.path.exists(csv_file):
        st.markdown("---")
        st.header("📊 पंचनामा अहवाल तपासणी")

        temp_df = pd.read_csv(csv_file)
        
        view_option = st.radio(
            "कशानुसार माहिती पाहायची आहे?", 
            ["निवडलेल्या गटानुसार", "निवडलेल्या खातेदारानुसार"], 
            horizontal=True
        )

        if view_option == "निवडलेल्या गटानुसार":
            report_df = temp_df[
                (temp_df['गाव'] == village) & 
                (temp_df['गट_क्र'].astype(str) == str(selected_gat))
            ]
            title = f"📍 गट क्र. {selected_gat} मधील सर्व नोंदी"
        else:
            report_df = temp_df[
                (temp_df['गाव'] == village) & 
                (temp_df['गट_क्र'].astype(str) == str(selected_gat)) & 
                (temp_df['खाते_क्र'].astype(str) == str(final_data['khata_no']))
            ]
            title = f"👤 खातेदार: {final_data['name']} यांच्या नोंदी"

        st.subheader(title)
        if not report_df.empty:
            final_report = report_df[['खातेदार', 'गट_क्र', 'खाते_क्र', 'पीक', 'नुकसान_क्षेत्र']].rename(
                columns={
                    'खातेदार': 'खातेदाराचे नाव',
                    'गट_क्र': 'गट',
                    'खाते_क्र': 'खाते',
                    'पीक': 'पीक',
                    'नुकसान_क्षेत्र': 'क्षेत्र (हे.)'
                }
            )
            st.dataframe(final_report, use_container_width=True, hide_index=True)
            
            total_area_sum = round(report_df['नुकसान_क्षेत्र'].sum(), 4)
            st.warning(f"🔎 वरील फिल्टरनुसार एकूण नोंदवलेले क्षेत्र: **{total_area_sum} हे.**")
        else:
            st.info("ℹ️ या निवडीसाठी अद्याप कोणतीही नोंद सापडली नाही.")

    # ---------------------------------------------------------
    # ९. साइडबार - डाऊनलोड आणि एडिट विभाग
    # ---------------------------------------------------------
    if os.path.exists(csv_file):
        st.sidebar.markdown("---")
        st.sidebar.subheader("📥 डेटा डाउनलोड")
        with open(csv_file, "rb") as file:
            st.sidebar.download_button(
                label="रिपोर्ट डाउनलोड करा (CSV)",
                data=file,
                file_name=f"panchnama_report_{datetime.date.today()}.csv",
                mime="text/csv"
            )

        st.sidebar.markdown("---")
        if st.sidebar.checkbox("📝 नोंद दुरुस्त करा (Edit)"):
            all_records = pd.read_csv(csv_file)
            
            st.subheader("🛠️ नोंद दुरुस्ती विभाग")
            selected_idx = st.selectbox(
                "दुरुस्त करण्यासाठी नोंद निवडा:", 
                all_records.index, 
                format_func=lambda x: f"{all_records.iloc[x]['खातेदार']} | गट:{all_records.iloc[x]['गट_क्र']} | {all_records.iloc[x]['पीक']} ({all_records.iloc[x]['नुकसान_क्षेत्र']} हे.)"
            )
            
            record = all_records.iloc[selected_idx]
            
            with st.form("edit_form"):
                st.info(f"नोंद बदलत आहे: {record['खातेदार']} (गट: {record['गट_क्र']})")
                
                crop_options = ["काजू"]
                current_crop_idx = crop_options.index(record['पीक']) if record['पीक'] in crop_options else 0
                
                new_crop = st.selectbox("पीक बदला", crop_options, index=current_crop_idx)
                
                new_area = st.number_input("क्षेत्र दुरुस्त करा (हे.)", 
                                          min_value=0.0, 
                                          value=float(record['नुकसान_क्षेत्र']), 
                                          format="%.4f")
                
                current_trees = int(record['बाधित_झाडांची_संख्या']) if 'बाधित_झाडांची_संख्या' in record and pd.notna(record['बाधित_झाडांची_संख्या']) else 0
                new_trees = st.number_input("बाधित झाडांची संख्या दुरुस्त करा", min_value=0, value=current_trees, step=1)
                
                new_remark = st.text_area("शेरा बदला", value=str(record['शेरा']) if pd.notna(record['शेरा']) else "")
                
                update_btn = st.form_submit_button("माहिती अपडेट करा")
                
                if update_btn:
                    with engine.begin() as conn:
                        query = text("""
                            UPDATE panchnama_records 
                            SET "पीक" = :crop, "नुकसान_क्षेत्र" = :area, "बाधित_झाडांची_संख्या" = :trees, "शेरा" = :remark 
                            WHERE "वेळ" = :time_val AND "खातेदार" = :farmer
                        """)
                        conn.execute(query, {
                            "crop": new_crop,
                            "area": new_area,
                            "trees": new_trees,
                            "remark": new_remark,
                            "time_val": record['वेळ'],
                            "farmer": record['खातेदार']
                        })
                    
                    
                    st.success("✅ नोंद यशस्वीरित्या अपडेट केली आहे!")
                    st.balloons()
                    time.sleep(2)
                    st.rerun()