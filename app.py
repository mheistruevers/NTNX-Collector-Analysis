import plotly.express as px  # pip install plotly-express
import plotly.graph_objs as go
import streamlit as st  # pip install streamlit
import custom_functions
import pandas as pd
import numpy as np
import warnings
import time

######################
# Page Config
######################
st.set_page_config(page_title="Nutanix Collector Analyse", page_icon='favicon.ico', layout="wide")
hide_streamlit_style = """
            <style>
            header {visibility: hidden;}
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            table td:nth-child(1) {display: none}
            table th:nth-child(1) {display: none}
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True) 
df_vInfo = pd.DataFrame() # Initialize Main Dataframe as Empty in order to check whether it has been filled
df_vCPU = pd.DataFrame() # Initialize Main Dataframe as Empty in order to check whether it has been filled
df_vMemory = pd.DataFrame() # Initialize Main Dataframe as Empty in order to check whether it has been filled
df_vHosts = pd.DataFrame() # Initialize Main Dataframe as Empty in order to check whether it has been filled
warnings.simplefilter("ignore") # Ignore openpyxl Excile File Warning while reading (no default style)

######################
# Page sections
######################
header_section = st.container() # Description of page & what it is about
content_section = st.container() # Content of page - either error message if wrong excel file or analysis content

######################
# Page content
######################

with st.sidebar:
    st.markdown('# **Upload**')
    uploaded_file = st.sidebar.file_uploader(label="Laden Sie Ihre Excel basierte Collector Auswertung hier hoch.", type=['xlsx'])

    if uploaded_file is not None:
        try:
            # load excel, filter our relevant tabs and columns, merge all in one dataframe
            df_vInfo, df_vCPU, df_vMemory, df_vHosts = custom_functions.get_data_from_excel(uploaded_file)            

            #st.sidebar.markdown('---')
            #st.sidebar.markdown('## **Filter**')

            with st.sidebar.form(key ='filter_form'):
                #user_word = st.text_input("Enter a keyword", "habs")    
                #select_language = st.radio('Tweet language', ('All', 'English', 'French'))
                #include_retweets = st.checkbox('Include retweets in data')
                #num_of_tweets = st.number_input('Maximum number of tweets', 100)
                

                vCluster_selected = st.multiselect(
                    "vCluster selektieren:",
                    options=sorted(df_vInfo["Cluster Name"].unique()),
                    default=sorted(df_vInfo["Cluster Name"].unique())
                )

                powerstate_selected = st.multiselect(
                    "VM Status selektieren:",
                    options=sorted(df_vInfo["Power State"].unique()),
                    default=sorted(df_vInfo["Power State"].unique())
                )

                vCPU_selected = st.selectbox('Sizing vCPU Werte:', ('95th Percentile','Provisioned','Peak','Average','Median'))
                vMemory_selected = st.selectbox('Sizing vMemory Werte:', ('95th Percentile','Provisioned','Peak','Average','Median'))
                vStorage_selected = st.selectbox('Sizing vStorage Werte:', ('in Use','Provisioned'))
                vCPU_growth_selected = st.slider('Wieviel % vCPU Wachstum?', 0, 100, 10)
                vMemory_growth_selected = st.slider('Wieviel % vMemory Wachstum?', 0, 100, 30)
                vStorage_growth_selected = st.slider('Wieviel % Storage Wachstum?', 0, 100, 20)

                filter_form_submitted = st.form_submit_button(label = 'Auswertung starten ✔️')

            # Apply Multiselect Filter to dataframe
            #df_vInfo.query("`Cluster Name`==@vCluster_selected").query("`Power State`==@powerstate_selected")

        except Exception as e:
            content_section.error("##### FEHLER: Die hochgeladene Excel Datei konnte leider nicht ausgelesen werden.")
            content_section.markdown("**Bitte stellen Sie sicher, dass folgende Tabs mit den jeweiligen Spalten hinterlegt sind:**")
            content_section.markdown("""  """)
            content_section.markdown("---")
            content_section.markdown("Im folgenden die genaue Fehlermeldung für ein Troubleshooting:")
            content_section.exception(e)

with header_section:
    st.markdown("<h1 style='text-align: left; color:#034ea2;'>Nutanix Collector Analyse</h1>", unsafe_allow_html=True)
    st.markdown('Ein Hobby-Projekt von [**Martin Stenke**](https://www.linkedin.com/in/mstenke/) zur einfachen Analyse einer Nutanix Collector Auswertung.')
    st.info('***Disclaimer: Hierbei handelt es sich lediglich um ein Hobby Projekt - keine Garantie auf Vollständigkeit oder Korrektheit der Auswertung / Daten.***')
    st.markdown("---")

with content_section: 

    if filter_form_submitted:
        st.success("##### Die Nutanix Collector Auswertung konnte erfolgreich ausgewertet werden:")

        overall_expander = st.expander(label='Gesamt Übersicht')
        with overall_expander:
            st.write('Hi')

        vHosts_expander = st.expander(label='vHosts Details')
        with vHosts_expander:
            st.write('Hinweis: Bei der vHosts Auswertung kann nur der Filter auf vCluster Ebene angewendet werden.')
            # Generate Overview Dataframe for vHosts
            vHosts_overview = custom_functions.generate_vHosts_overview_df(df_vHosts.query("Cluster==@vCluster_selected"))
            #st.table(vHosts_overview)
        
        
        VM_expander = st.expander(label='VM Details')
        with VM_expander:
            st.write('Hi')
        vCPU_expander = st.expander(label='vCPU Details')
        with vCPU_expander:
            st.write('Hi')
        vRAM_expander = st.expander(label='vRAM Details')
        with vRAM_expander:
            st.write('Hi')
        vStorage_expander = st.expander(label='vStorage Details')
        with vStorage_expander:
            st.write('Hi')
        

        