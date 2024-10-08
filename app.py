import plotly.express as px
import plotly.graph_objs as go
import streamlit as st
import custom_functions
import pandas as pd
import numpy as np
import warnings
from PIL import Image
import time
import base64

######################
# Page Config
######################
st.set_page_config(page_title="Nutanix Collector Analyse", page_icon='./style/favicon.png', layout="wide")
# Use CSS Modifications stored in CSS file            
st.markdown(f"<style>{custom_functions.local_css('style/style.css')}</style>", unsafe_allow_html=True)

######################
# Initialize variables
######################
filter_form_submitted = False
uploaded_file_valid = False
warnings.simplefilter("ignore") # Ignore openpyxl Excile File Warning while reading (no default style)

######################
# Page sections
######################
header_section = st.container() # Description of page & what it is about
upload_filter_section = st.container() # File Upload & Filter section
analysis_section = st.container() # Analysis section - either error message if wrong excel file or analysis content
sizing_section = st.container() # Sizing section

######################
# Page content
######################
with header_section:
    st.markdown("<h1 style='text-align: left; color:#000000;'>Nutanix Collector Analyse - by Martin Stenke - Modded by Michael Heistruevers</h1>", unsafe_allow_html=True)
    st.markdown('DEV-BRANCH - Ein Hobby-Projekt von [**Martin Stenke**](https://www.linkedin.com/in/mstenke/) zur einfachen Analyse einer [**Nutanix Collector**](https://collector.nutanix.com/) Auswertung. (Zuletzt aktualisiert: 08.10.2024)')
    st.info('***Disclaimer: Hierbei handelt es sich lediglich um ein Hobby Projekt - keine Garantie auf Vollständigkeit oder Korrektheit der Auswertung / Daten.***')
    st.markdown("---")

with upload_filter_section:
    st.markdown('### **Upload & Filter**')
    column_upload, column_filter = st.columns(2)
            
    with column_upload:
        uploaded_file = st.file_uploader(label="Laden Sie Ihre Excel basierte Collector Auswertung hier hoch.", type=['xlsx'], help='Diesen Excel Export können Sie entweder direkt aus der Collector Anwendung heraus erzeugen oder über das Collector Portal mittels "Export as .XLS". ')

    if uploaded_file is not None:
        with column_filter:            
                try:

                    # load excel, filter our relevant tabs and columns, merge all in one dataframe
                    df_vInfo, df_vCPU, df_vMemory, df_vHosts, df_vCluster, df_vPartition, df_vmList, df_vDisk, df_vSnapshot = custom_functions.get_data_from_excel(uploaded_file)            

                    vCluster_selected = st.multiselect(
                        "vCluster selektieren:",
                        options=sorted(df_vInfo["Cluster Name"].unique()),
                        default=sorted(df_vInfo["Cluster Name"].unique())
                    )

                    uploaded_file_valid = True
                    st.success("Die Nutanix Collector Auswertung wurde erfolgreich hochgeladen. Filtern Sie bei Bedarf nach einzelnen Clustern.")

                except Exception as e:
                    uploaded_file_valid = False
                    analysis_section.error("##### FEHLER: Die hochgeladene Nutanix Collector Excel Datei konnte leider nicht ausgelesen werden.")
                    analysis_section.markdown("Im folgenden die genaue Fehlermeldung für ein Troubleshooting:")
                    analysis_section.exception(e)
                    st.session_state[uploaded_file.name] = True 

if uploaded_file is not None and uploaded_file_valid is True and len(vCluster_selected) != 0:

    # Check is Nutanix CVMs are included in analysis which could lead to misinterpretations
    check_for_cvms = df_vInfo[(df_vInfo['VM Name'].str.match('^NTNX-.*-CVM$')==True)]
    if not check_for_cvms.empty:
        upload_filter_section.warning('Achtung: Die Collector Auswertung scheint Nutanix CVMs zu enthalten welche die Auswertung (insbesondere im Storage Bereich) stark verfälschen können. Es ist empfohlen Auswertungen von Nutanix Umgebungen über Prism abzuziehen und nicht über den Hypervisor. Entweder neue Nutanix Auswertung abziehen (empfohlen) oder CVMs manuell aus der Collector Excel Datei entfernen.')

    with analysis_section: 
        st.markdown("---")
        st.markdown('### Auswertung')
        
        # Declare new df for filtered vCluster selection
        df_vInfo_filtered = df_vInfo.query("`Cluster Name`==@vCluster_selected")
        df_vCPU_filtered = df_vCPU.query("`Cluster Name`==@vCluster_selected")
        df_vMemory_filtered = df_vMemory.query("`Cluster Name`==@vCluster_selected")
        df_vHosts_filtered = df_vHosts.query("`Cluster Name`==@vCluster_selected")
        df_vCluster_filtered = df_vCluster.query("`Cluster Name`==@vCluster_selected")
        df_vPartition_filtered = df_vPartition.query("`Cluster Name`==@vCluster_selected")
        df_vmList_filtered = df_vmList.query("`Cluster Name`==@vCluster_selected")
        df_vDisk_filtered = df_vDisk.query("`Cluster Name`==@vCluster_selected")
        df_vSnapshot_filtered = df_vSnapshot.query("`Cluster Name`==@vCluster_selected")

        # Set bar chart setting to static for both  charts
        chart_config = {'staticPlot': True}
        chart_marker_colors = ['#034EA2','#BBE3F3']
        
        vCluster_expander = st.expander(label='vCluster Übersicht')
        with vCluster_expander:
            st.markdown(f"<h4 style='text-align: center;'>Die Auswertung umfasst <b>{ df_vCluster_filtered['Datacenter'].nunique() } Rechenzentren</b>, <b>{ df_vCluster_filtered['Cluster Name'].nunique() } Cluster</b>, <b>{ df_vHosts_filtered['Cluster Name'].shape[0] } Host</b> und <b>{ df_vInfo_filtered.shape[0] } VMs</b>.</h4>", unsafe_allow_html=True)

            column_cpu, column_memory, column_storage = st.columns(3)
            
            with column_cpu:
                st.markdown("<h4 style='text-align: center; color:#000000;'>pCPU:</h4>", unsafe_allow_html=True)

                total_ghz, consumed_ghz, cpu_percentage = custom_functions.generate_CPU_infos(df_vHosts_filtered)

                donut_chart_cpu = go.Figure(data = go.Pie(values = cpu_percentage, hole = 0.9, marker_colors=chart_marker_colors, sort=False,textinfo='none', hoverinfo='skip'))
                donut_chart_cpu.add_annotation(x= 0.5, y = 0.5, text = str(round(cpu_percentage[0],2))+' %',
                                    font = dict(size=20,family='Arial Black', color='black'), showarrow = False)
                donut_chart_cpu.update(layout_showlegend=False)
                donut_chart_cpu.update_layout(margin=dict(l=10, r=10, t=10, b=10,pad=4), autosize=True, height = 150)

                st.plotly_chart(donut_chart_cpu, use_container_width=True, config=chart_config)
                st.markdown(f"<p style='text-align: center;'>{consumed_ghz} GHz verwendet</p>", unsafe_allow_html=True)
                st.markdown(f"<p style='text-align: center;'>{total_ghz} GHz verfügbar</p>", unsafe_allow_html=True)                

            with column_memory:
                st.markdown("<h4 style='text-align: center; color:#000000;'>pMemory:</h4>", unsafe_allow_html=True)

                total_memory, consumed_memory, memory_percentage = custom_functions.generate_Memory_infos(df_vHosts_filtered)

                donut_chart_memory = go.Figure(data = go.Pie(values = memory_percentage, hole = 0.9, marker_colors=chart_marker_colors, sort=False,textinfo='none', hoverinfo='skip'))
                donut_chart_memory.add_annotation(x= 0.5, y = 0.5, text = str(round(memory_percentage[0],2))+' %',
                                    font = dict(size=20,family='Arial Black', color='black'), showarrow = False)
                donut_chart_memory.update(layout_showlegend=False)
                donut_chart_memory.update_layout(margin=dict(l=10, r=10, t=10, b=10,pad=4), autosize=True, height = 150)

                st.plotly_chart(donut_chart_memory, use_container_width=True, config=chart_config)
                st.markdown(f"<p style='text-align: center;'>{consumed_memory} GiB verwendet</p>", unsafe_allow_html=True)
                st.markdown(f"<p style='text-align: center;'>{total_memory} GiB verfügbar</p>", unsafe_allow_html=True)                

            with column_storage:
                st.markdown("<h4 style='text-align: center; color:#000000;'>vStorage:</h4>", unsafe_allow_html=True)

                storage_provisioned, storage_consumed, storage_percentage = custom_functions.generate_Storage_infos(df_vPartition_filtered)

                donut_chart_storage = go.Figure(data = go.Pie(values = storage_percentage, hole = 0.9, marker_colors=chart_marker_colors, sort=False,textinfo='none', hoverinfo='skip'))
                donut_chart_storage.add_annotation(x= 0.5, y = 0.5, text = str(round(storage_percentage[0],2))+' %',
                                    font = dict(size=20,family='Arial Black', color='black'), showarrow = False)
                donut_chart_storage.update(layout_showlegend=False)
                donut_chart_storage.update_layout(margin=dict(l=10, r=10, t=10, b=10,pad=4), autosize=True, height = 150)

                st.plotly_chart(donut_chart_storage, use_container_width=True, config=chart_config)
                st.markdown(f"<p style='text-align: center;'>{storage_consumed} TiB verwendet</p>", unsafe_allow_html=True)
                st.markdown(f"<p style='text-align: center;'>{storage_provisioned} TiB zugewiesen</p>", unsafe_allow_html=True)
                
            st.write('---')

            column_IOPS, column_read_write_ratio = st.columns(2)
            with column_IOPS:
                    st.markdown("<h4 style='text-align: center; color:#000000;'>IOPS:</h4>", unsafe_allow_html=True)
                    st.markdown(f"<h5 style='text-align: center;'>{round(df_vCluster_filtered['95th Percentile IOPS'].sum(),2)}</h5>", unsafe_allow_html=True)
            with column_read_write_ratio:
                    read_ratio, write_ratio = custom_functions.generate_read_write_ratio_infos(df_vCluster_filtered)
                    st.markdown("<h4 style='text-align: center; color:#000000;'>Read / Write Verhältnis:</h4>", unsafe_allow_html=True)
                    st.markdown(f"<h5 style='text-align: center;'>{read_ratio} % / {write_ratio} %</h5>", unsafe_allow_html=True)      

        vHosts_expander = st.expander(label='vHosts Details')
        with vHosts_expander:

            pCPU_df, memory_df, hardware_df = custom_functions.generate_vHosts_overview_df(df_vHosts_filtered)            
            column_pCPU, column_pRAM, column_hardware = st.columns(3)
            
            with column_pCPU:
                st.markdown("<h5 style='text-align: center; color:#000000;'>pCPU Details:</h5>", unsafe_allow_html=True)
                st.table(pCPU_df)
            with column_pRAM:
                st.markdown("<h5 style='text-align: center; color:#000000;'> pMemory Details:</h5>", unsafe_allow_html=True)
                st.table(memory_df)
            with column_hardware:
                st.markdown("<h5 style='text-align: center; color:#000000;'>vHost Details:</h5>", unsafe_allow_html=True)
                st.table(hardware_df)
                
        VM_expander = st.expander(label='VM Details')
        with VM_expander:

            df_vInfo_filtered_vm_on = df_vInfo_filtered.query("`Power State`=='poweredOn'")    
            df_vInfo_filtered_vm_off = df_vInfo_filtered.query("`Power State`=='poweredOff'")

            column_vm_on, column_vm_off, column_vm_total = st.columns(3)            

            with column_vm_on:                    
                st.markdown(f"<h5 style='text-align: center; color:#000000;'>VMs On: { df_vInfo_filtered_vm_on['MOID'].shape[0] }</h5>", unsafe_allow_html=True)

            with column_vm_off:                
                st.markdown(f"<h5 style='text-align: center; color:#000000;'>VMs Off: { df_vInfo_filtered_vm_off['MOID'].shape[0] }</h5>", unsafe_allow_html=True)

            with column_vm_total:
                st.markdown(f"<h5 style='text-align: center; color:#000000;'>VMs Gesamt: { df_vInfo_filtered['MOID'].shape[0] }</h5>", unsafe_allow_html=True)

            st.write('---')
            
            column_top10_vCPU, column_top10_vRAM, column_top10_vStorage = st.columns(3)            

            with column_top10_vCPU:        
                st.markdown(f"<h6 style='text-align: center; color:#000000;'>Top 10 VMs: vCPU (On)</h6>", unsafe_allow_html=True)                
                top_vms_vCPU = custom_functions.generate_top10_vCPU_VMs_df(df_vCPU_filtered)
                st.table(top_vms_vCPU)
            with column_top10_vRAM:
                st.markdown(f"<h6 style='text-align: center; color:#000000;'>Top 10 VMs: vMemory (On)</h6>", unsafe_allow_html=True)
                top_vms_vMemory = custom_functions.generate_top10_vMemory_VMs_df(df_vMemory_filtered)
                st.table(top_vms_vMemory)
            with column_top10_vStorage:
                st.markdown(f"<h6 style='text-align: center; color:#000000;'>Top 10 VMs: vStorage consumed</h6>", unsafe_allow_html=True)
                top_vms_vStorage_consumed = custom_functions.generate_top10_vStorage_consumed_VMs_df(df_vmList_filtered)
                st.table(top_vms_vStorage_consumed)

        guest_os_expander = st.expander(label='VM Gastbetriebssystem Details')
        with guest_os_expander:
            guest_os_df = custom_functions.generate_guest_os_df(df_vmList_filtered)
            st.table(guest_os_df)
            st.write('Ein Auslesen der Gastbetriebssysteme setzt u.A. vorraus dass die passenden Guest Tools in den VMs installiert sind und diese eingeschaltet sind/waren. Dies ist i.d.R. nicht überall der Fall daher zeigt die obige Tabelle nur die Gastbetriebssysteme von den VMs bei welchen solch ein Auslesen möglich war.')


        vCPU_expander = st.expander(label='vCPU Details')
        with vCPU_expander:
            column_vCPU_overview, column_vCPU_performance_based = st.columns([1,2])
            with column_vCPU_overview:
                st.markdown("<h5 style='text-align: left; color:#000000; '><u>Generelle vCPU Auswertung</u></h5>", unsafe_allow_html=True)

            with column_vCPU_performance_based:
                st.markdown("<h5 style='text-align: left; color:#000000; '><u>Nutzungs-basierte vCPU Auswertung (On)</u></h5>", unsafe_allow_html=True)

            vCPU_provisioned_df, vCPU_overview_df = custom_functions.generate_vCPU_overview_df(df_vCPU_filtered,df_vHosts_filtered)
            
            column_vCPU_overview_table, column_vCPU_performance_based_table, column_vCPU_performance_based_chart = st.columns([2,1.5,2.5])                            

            with column_vCPU_overview_table:
                st.table(vCPU_provisioned_df)
                
            with column_vCPU_performance_based_table:
                st.table(vCPU_overview_df)

            with column_vCPU_performance_based_chart:
                bar_chart_vCPU, vCPU_bar_chart_config = custom_functions.generate_bar_charts(vCPU_overview_df.data, "vCPUs", 350)
                st.plotly_chart(bar_chart_vCPU,use_container_width=True, config=vCPU_bar_chart_config)                

            st.write('Der Nutanix Collector kann neben den zugewiesenen vCPU Ressourcen an die VMs ebenfalls die Performance Werte der letzten 7 Tage in 30 Minuten Intervallen aus vCenter/Prism auslesen und bietet anhand dessen eine Möglichkeit für Rückschlüsse auf tatsächlich verwendete / benötigte vCPU Ressourcen. Bei den hier rechts gezeigten Nutzungs-basierten Auswertung wird die jeweils prozentuale Auslastung pro angeschalteter VM mit den zugewiesenen vCPU Werten multipliziert und mit zusätzlich 20% Puffer versehen. **Da vCPU überprovisioniert werden kann, bietet es sich an die tatsächlich benötigten vCPU Werte zu verwenden (95th Percentile empfohlen).**')

        vRAM_expander = st.expander(label='vRAM Details')
        with vRAM_expander:
            column_vRAM_overview, column_vRAM_performance_based = st.columns([1,2])
            with column_vRAM_overview:
                st.markdown("<h5 style='text-align: left; color:#000000; '><u>Generelle vMemory Auswertung</u></h5>", unsafe_allow_html=True)

            with column_vRAM_performance_based:
                st.markdown("<h5 style='text-align: left; color:#000000; '><u>Nutzungs-basierte vMemory Auswertung (On)</u></h5>", unsafe_allow_html=True)

            vRAM_provisioned_df, vMemory_overview_df = custom_functions.generate_vRAM_overview_df(df_vMemory_filtered)
            
            column_vRAM_overview_table, column_vRAM_performance_based_table, column_vRAM_performance_based_chart = st.columns([2,1.5,2.5])                            

            with column_vRAM_overview_table:
                st.table(vRAM_provisioned_df)
                
            with column_vRAM_performance_based_table:
                st.table(vMemory_overview_df)

            with column_vRAM_performance_based_chart:
                bar_chart_vMemory, vMemory_bar_chart_config = custom_functions.generate_bar_charts(vMemory_overview_df.data, "GiB", 250)
                st.plotly_chart(bar_chart_vMemory,use_container_width=True, config=vMemory_bar_chart_config)                

            st.write('Der Nutanix Collector kann neben den zugewiesenen vMemory Ressourcen an die VMs ebenfalls die Performance Werte der letzten 7 Tage in 30 Minuten Intervallen aus vCenter/Prism auslesen und bietet anhand dessen eine Möglichkeit für Rückschlüsse auf tatsächlich verwendete / benötigte vMemory Ressourcen. Bei den hier rechts gezeigten Nutzungs-basierten Auswertung wird die jeweils prozentuale Auslastung pro angeschalteter VM mit den zugewiesenen vMemory Werten multipliziert und mit zusätzlich 20% Puffer versehen. **Da vMemory nicht überprovisioniert werden sollte, sollte beim Sizing lediglich die konfigurierten/provisioned Werte verwendet werden.** Die tatsächliche Auslastung kann aber Rückschlüsse auf ein potenzielles Optimierungspotenzial und und damit verbundenen Kosteneinsparungen aufzeigen.')

        vStorage_expander = st.expander(label='vStorage Details')
        with vStorage_expander:
            column_vPartition, column_vDisk, column_vSnapshot = st.columns(3)                            
            vPartition_df, vDisk_df, vmList_df, vSnapshot_df = custom_functions.generate_vStorage_overview_df(df_vPartition_filtered, df_vDisk_filtered, df_vmList_filtered, df_vSnapshot_filtered)

            with column_vPartition:
                st.markdown("<h5 style='text-align: left; color:#000000; '><u>vPartition Auswertung</u></h5>", unsafe_allow_html=True)            
                st.table(vPartition_df)

            with column_vDisk:
                st.markdown("<h5 style='text-align: left; color:#000000; '><u>vDisk Auswertung</u></h5>", unsafe_allow_html=True)
                st.table(vDisk_df)

            with column_vSnapshot:
                st.markdown("<h5 style='text-align: left; color:#000000; '><u>vSnapshot Auswertung</u></h5>", unsafe_allow_html=True)
                st.table(vSnapshot_df)
                st.write('Die vSnapshots werden beim Sizing nicht berücksichtigt und dienen nur als Zusatzinformation.')

            st.markdown("<h5 style='text-align: left; color:#000000; '><u>VM Storage Auswertung</u></h5>", unsafe_allow_html=True)
            st.write('In der Regel werden bei einer Auswertung die vPartition Daten herangezogen. Jedoch kann es sein, dass nicht für alle VMs die vPartition Daten vorliegen (z.B. durch fehlende Guest Tools), daher wird für diese VMs auf die vDisk Daten zurückgegriffen um so für alle VMs den Storage Bedarf bestmöglich erfassen zu können. Für eine `provisioned` Storage Berechnung wird 100% der vDisk Kapazität angenommen, für eine `consumed` Storage Berechnung wird 80% der vDisk Kapazität angenommen.')

            storage_chart, storage_chart_config = custom_functions.generate_storage_charts(vmList_df)
            column_vm_storage_table, column_vm_storage_chart = st.columns(2)            
            with column_vm_storage_table:
                st.table(vmList_df)
            with column_vm_storage_chart:
                st.markdown("<h5 style='text-align: center; color:#000000; '>VM Capacity - Gesamt:</h5>", unsafe_allow_html=True)
                st.plotly_chart(storage_chart,use_container_width=True, config=storage_chart_config)    
    

    with sizing_section: 
        st.markdown("---")            
        st.markdown('### Sizing-Eckdaten-Berechnung')
          
        form_column_vCPU, form_column_vRAM, form_column_vStorage = st.columns(3)
        with form_column_vCPU:
            st.markdown("<h4 style='text-align: center; color:#000000; '><u>vCPU Sizing:</u></h4>", unsafe_allow_html=True)

            if 'vCPU_selectbox' not in st.session_state:
                st.session_state['vCPU_selectbox'] = 'On VMs - 95th Percentile vCPUs *'
            if 'vCPU_slider' not in st.session_state:
                st.session_state['vCPU_slider'] = 10

            form_vCPU_selected = st.selectbox('vCPU Sizing Grundlage wählen:', ('On VMs - 95th Percentile vCPUs *', 'On VMs - Peak vCPUs', 'On VMs - Provisioned vCPUs','On und Off VMs - Provisioned vCPUs','On VMs - Average vCPUs', 'On VMs - Median vCPUs'), key='vCPU_selectbox', on_change=custom_functions.calculate_sizing_result_vCPU(vCPU_provisioned_df, vCPU_overview_df))
            form_vCPU_growth_selected = st.slider('Wieviel % vCPU Wachstum?', 0, 100, key='vCPU_slider', on_change=custom_functions.calculate_sizing_result_vCPU(vCPU_provisioned_df, vCPU_overview_df))
            
        with form_column_vRAM:
            st.markdown("<h4 style='text-align: center; color:#000000; '><u>vMemory Sizing:</u></h4>", unsafe_allow_html=True)

            if 'vRAM_selectbox' not in st.session_state:
                st.session_state['vRAM_selectbox'] = 'On VMs - Provisioned vMemory *'
            if 'vRAM_slider' not in st.session_state:
                st.session_state['vRAM_slider'] = 30

            form_vMemory_selected = st.selectbox('vMemory Sizing Grundlage wählen:', ('On VMs - Provisioned vMemory *', 'On und Off VMs - Provisioned vMemory', 'On VMs - Peak vMemory', 'On VMs - 95th Percentile vMemory', 'On VMs - Average vMemory', 'On VMs - Median vMemory'), key='vRAM_selectbox', on_change=custom_functions.calculate_sizing_result_vRAM(vRAM_provisioned_df, vMemory_overview_df))
            form_vMemory_growth_selected = st.slider('Wieviel % vMemory Wachstum?', 0, 100, key='vRAM_slider', on_change=custom_functions.calculate_sizing_result_vRAM(vRAM_provisioned_df, vMemory_overview_df))

        with form_column_vStorage:
            st.markdown("<h4 style='text-align: center; color:#000000; '><u>vStorage Sizing:</u></h4>", unsafe_allow_html=True)

            if 'vStorage_selectbox' not in st.session_state:
                st.session_state['vStorage_selectbox'] = 'On und Off VMs - Consumed VM Storage *'
            if 'vStorage_slider' not in st.session_state:
                st.session_state['vStorage_slider'] = 20

            form_vStorage_selected = st.selectbox('vStorage Sizing Grundlage wählen:', ('On und Off VMs - Consumed VM Storage *', 'On VMs - Consumed VM Storage', 'On und Off VMs - Provisioned VM Storage', 'On VMs - Provisioned VM Storage'), key='vStorage_selectbox', on_change=custom_functions.calculate_sizing_result_vRAM(vCPU_provisioned_df, vCPU_overview_df))
            form_vStorage_growth_selected = st.slider('Wieviel % Storage Wachstum?', 0, 100, key='vStorage_slider', on_change=custom_functions.calculate_sizing_result_vRAM(vCPU_provisioned_df, vCPU_overview_df))
        st.markdown("""<p><u>Hinweis:</u> Die mit * markierten Optionen stellen die jeweilige Empfehlung für vCPU, vRAM und vStorage dar.</p>""", unsafe_allow_html=True)

      
        st.write('---')
        st.markdown('### Sizing-Eckdaten-Ergebnis')
        st.write('')

        type_column, result_column_vCPU, result_column_vRAM, result_column_vStorage = st.columns(4)

        with type_column:
            st.markdown(f"""<div class="container"><img class="logo-img" src="data:image/png;base64,{base64.b64encode(open("images/blank.png", "rb").read()).decode()}"></div>""", unsafe_allow_html=True)
            st.markdown("<h4 style='color:#FFFFFF;'>_</h4>", unsafe_allow_html=True)
            st.write('')
            st.markdown("<h4 style='text-align: left; color:#000000;'>Ausgangswert</h4>", unsafe_allow_html=True)
            st.write('')
            st.write('')
            st.markdown("<h4 style='text-align: left; color:#000000;'>Endwert</h4>", unsafe_allow_html=True)


        with result_column_vCPU:
            st.markdown(f"""<div class="container"><img class="logo-img" src="data:image/png;base64,{base64.b64encode(open("images/vCPU.png", "rb").read()).decode()}"></div>""", unsafe_allow_html=True)
            st.markdown("<h4 style='text-align: left; color:#000000;'>vCPU</h4>", unsafe_allow_html=True)

            custom_functions.calculate_sizing_result_vCPU(vCPU_provisioned_df, vCPU_overview_df)
            st.metric(label="", value=st.session_state['vCPU_basis']+ ' vCPUs')
            st.metric(label="", value=st.session_state['vCPU_final']+ ' vCPUs', delta=st.session_state['vCPU_growth']+ ' vCPUs')

        with result_column_vRAM:
            st.markdown(f"""<div class="container"><img class="logo-img" src="data:image/png;base64,{base64.b64encode(open("images/vRAM.png", "rb").read()).decode()}"></div>""", unsafe_allow_html=True)
            st.markdown("<h4 style='text-align: left; color:#000000;'>vRAM</h4>", unsafe_allow_html=True)

            custom_functions.calculate_sizing_result_vRAM(vRAM_provisioned_df, vMemory_overview_df)            
            st.metric(label="", value=st.session_state['vRAM_basis']+" GiB")
            st.metric(label="", value=st.session_state['vRAM_final']+" GiB", delta=st.session_state['vRAM_growth']+" GiB")

        with result_column_vStorage:
            st.markdown(f"""<div class="container"><img class="logo-img" src="data:image/png;base64,{base64.b64encode(open("images/vStorage.png", "rb").read()).decode()}"></div>""", unsafe_allow_html=True)
            st.markdown("<h4 style='text-align: left; color:#000000;'>vStorage</h4>", unsafe_allow_html=True)            

            custom_functions.calculate_sizing_result_vStorage(vmList_df)  
            st.metric(label="", value=st.session_state['vStorage_basis']+" TiB")
            st.metric(label="", value=st.session_state['vStorage_final']+" TiB", delta=st.session_state['vStorage_growth']+" TiB")
