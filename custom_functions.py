import pandas as pd
import numpy as np
from io import BytesIO
import streamlit as st


# Generate Dataframe from Excel and make neccessary adjustment for easy consumption later on
@st.cache(allow_output_mutation=True)
def get_data_from_excel(uploaded_file):

    df = pd.ExcelFile(uploaded_file, engine="openpyxl")

    # Columns to read from Excel file
    vInfo_cols_to_use = ["VM Name","Power State","Cluster Name","MOID"]
    vCPU_cols_to_use = ["vCPUs","Peak %","Average %","Median %","95th Percentile % (recommended)","Cluster Name","MOID"]
    vMemory_cols_to_use = ["Size (MiB)","Peak %","Average %","Median %","95th Percentile % (recommended)","Cluster Name","MOID"]
    vHosts_cols_to_use = ["Cluster","CPUs","VMs","CPU Cores","CPU Speed","Cores per CPU","Memory Size","CPU Usage","Memory Usage"]
    vCluster_cols_to_use = ["Datacenter", "MOID","Cluster Name","CPU Usage %","Memory Usage %","95th Percentile Disk Throughput (KBps)","95th Percentile IOPS","95th Percentile Number of Reads","95th Percentile Number of Writes"]
    vPartition_cols_to_use = ["VM Name","Power State","Consumed (MiB)","Capacity (MiB)","Datacenter Name","Cluster Name", "Host Name", "MOID"]


    # Create df for each tab with only relevant columns
    df_vInfo = df.parse('vInfo', usecols=vInfo_cols_to_use)
    df_vCPU = df.parse('vCPU', usecols=vCPU_cols_to_use)
    df_vMemory = df.parse('vMemory', usecols=vMemory_cols_to_use)
    df_vHosts = df.parse('vHosts', usecols=vHosts_cols_to_use)
    df_vCluster = df.parse('vCluster', usecols=vCluster_cols_to_use)
    df_vPartition = df.parse('vPartition', usecols=vPartition_cols_to_use)

    # Rename columns to make it shorter
    df_vCPU.rename(columns={'95th Percentile % (recommended)': '95th Percentile %'}, inplace=True)
    df_vMemory.rename(columns={'95th Percentile % (recommended)': '95th Percentile %'}, inplace=True)
    
    # Calculate from MiB to GiB & rename column
    df_vMemory.loc[:,"Size (MiB)"] = df_vMemory["Size (MiB)"] / 1024 # Use GiB instead of MiB
    df_vMemory.rename(columns={'Size (MiB)': 'Size (GiB)'}, inplace=True) # Rename Column
    df_vPartition.loc[:,"Consumed (MiB)"] = df_vPartition["Consumed (MiB)"] / 1024 # Use GiB instead of MiB
    df_vPartition.rename(columns={'Consumed (MiB)': 'Consumed (GiB)'}, inplace=True) # Rename Column
    df_vPartition.loc[:,"Capacity (MiB)"] = df_vPartition["Capacity (MiB)"] / 1024 # Use GiB instead of MiB
    df_vPartition.rename(columns={'Capacity (MiB)': 'Capacity (GiB)'}, inplace=True) # Rename Column

    # Add / Generate Total Columns from vCPU performance percentage data
    df_vCPU['vCPUs'] = df_vCPU['vCPUs'].astype(int)
    df_vCPU.loc[:,'Peak #'] = df_vCPU.apply(lambda row: get_vCPU_total_values(row, 'Peak %'), axis=1).astype(int)
    df_vCPU.loc[:,'Average #'] = df_vCPU.apply(lambda row: get_vCPU_total_values(row, 'Average %'), axis=1).astype(int)
    df_vCPU.loc[:,'Median #'] = df_vCPU.apply(lambda row: get_vCPU_total_values(row, 'Median %'), axis=1).astype(int)
    df_vCPU.loc[:,'95th Percentile #'] = df_vCPU.apply(lambda row: get_vCPU_total_values(row, '95th Percentile %'), axis=1).astype(int)

    # Add / Generate Total Columns from vMemory performance percentage data
    df_vMemory.loc[:,'Peak #'] = df_vMemory.apply(lambda row: get_vMemory_total_values(row, 'Peak %'), axis=1)
    df_vMemory.loc[:,'Average #'] = df_vMemory.apply(lambda row: get_vMemory_total_values(row, 'Average %'), axis=1)
    df_vMemory.loc[:,'Median #'] = df_vMemory.apply(lambda row: get_vMemory_total_values(row, 'Median %'), axis=1)
    df_vMemory.loc[:,'95th Percentile #'] = df_vMemory.apply(lambda row: get_vMemory_total_values(row, '95th Percentile %'), axis=1)

    # Add Cluster Name & MOID column to vHosts, drop column Cluster (as same as MOID)
    df_vHosts = pd.merge(df_vHosts, df_vCluster[['Cluster Name','MOID']], left_on='Cluster', right_on='MOID')
    df_vHosts.drop('Cluster', axis=1, inplace=True)
    df_vCluster.drop('MOID', axis=1, inplace=True)
    print(df_vHosts)
    
    return df_vInfo, df_vCPU, df_vMemory, df_vHosts, df_vCluster, df_vPartition

# Generate vCPU Values for Peak, Median, Average & 95 Percentile
def get_vCPU_total_values(df_row, compare_value):
    if pd.isna(df_row[compare_value]):
        get_total_value = df_row['vCPUs'] # if no data is available use provisioned vCPU data
    else:
        get_total_value = df_row['vCPUs'] * (df_row[compare_value]/100)* 1.2
        if(get_total_value) < 1:
            get_total_value = 1
        if(get_total_value) > df_row['vCPUs']:
            get_total_value = df_row['vCPUs']
    return np.ceil(get_total_value)

# Generate vMemory Values for Peak, Median, Average & 95 Percentile
def get_vMemory_total_values(df_row, compare_value):
    vMemory_row_value = df_row['Size (GiB)']
    vMemory_perf_value = df_row[compare_value]
    if pd.isna(vMemory_perf_value):
        get_total_value = vMemory_row_value # if no data is available use provisioned vMemory data
    else:
        get_total_value = vMemory_row_value * (vMemory_perf_value/100)* 1.2
        if np.less(get_total_value, 1):
            if np.less(vMemory_row_value, 1):
                get_total_value = vMemory_row_value
            else:
                get_total_value = 1
        elif np.greater(get_total_value, vMemory_row_value):
            get_total_value = vMemory_row_value
        else:
            get_total_value = np.ceil(get_total_value)
    return get_total_value

# Returns a value rounded up to a specific number of decimal places.
def round_decimals_up(number:float, decimals:int=2):
    if not isinstance(decimals, int):
        raise TypeError("decimal places must be an integer")
    elif decimals < 0:
        raise ValueError("decimal places has to be 0 or more")
    elif decimals == 0:
        return math.ceil(number)
    factor = 10 ** decimals
    return np.ceil(number * factor) / factor

# Generate vHost based CPU Information
def generate_CPU_infos(df_vHosts_filtered):

    total_ghz = (df_vHosts_filtered['CPU Cores'] * df_vHosts_filtered['CPU Speed']) / 1000
    consumed_ghz = (df_vHosts_filtered['CPU Cores'] * df_vHosts_filtered['CPU Speed'] * (df_vHosts_filtered['CPU Usage']/100)) / 1000
    cpu_percentage_temp = consumed_ghz.sum() / total_ghz.sum() * 100
    cpu_percentage = [cpu_percentage_temp, (100-cpu_percentage_temp)]

    return  round(total_ghz.sum(),2), round(consumed_ghz.sum(),2), cpu_percentage

# Generate vHost based Memory Information
def generate_Memory_infos(df_vHosts_filtered):

    total_memory = df_vHosts_filtered['Memory Size']
    consumed_memory = (df_vHosts_filtered['Memory Size'] * (df_vHosts_filtered['Memory Usage']/100))
    memory_percentage_temp = df_vHosts_filtered["Memory Usage"].mean()
    memory_percentage = [memory_percentage_temp, (100-memory_percentage_temp)]

    return  round(total_memory.sum(),2), round(consumed_memory.sum(),2), memory_percentage

# Generate vCluster based Read Write Ratio Information
def generate_read_write_ratio_infos(df_vCluster_filtered):

    sum_of_reads = df_vCluster_filtered['95th Percentile Number of Reads'].sum()
    sum_of_writes = df_vCluster_filtered['95th Percentile Number of Writes'].sum()
    overall_read_write = sum_of_reads + sum_of_writes
    read_ratio = (sum_of_reads / overall_read_write)*100
    write_ratio = (sum_of_writes / overall_read_write) *100

    return round(read_ratio), round(write_ratio)

# Generate vPartition based Storage Information
def generate_Storage_infos(df_vPartition_filtered):

    storage_consumed = df_vPartition_filtered['Consumed (GiB)'].sum() / 1024
    storage_provisioned = df_vPartition_filtered['Capacity (GiB)'].sum() / 1024

    storage_percentage_temp = storage_consumed / storage_provisioned * 100
    storage_percentage = [storage_percentage_temp, storage_provisioned]

    return  round(storage_provisioned,2), round(storage_consumed,2), storage_percentage

# Generate vHost Overview Section
def generate_vHosts_overview_df(df_vHosts_filtered):

    host_amount = round(df_vHosts_filtered.shape[0])
    sockets_amount = round(df_vHosts_filtered['CPUs'].sum())
    cores_amount = round(df_vHosts_filtered['CPU Cores'].sum())
    max_vm_host = round(df_vHosts_filtered['VMs'].max())
    average_vm_host = round(df_vHosts_filtered['VMs'].mean())
    hardware_first_column_df = {'': ["# Hosts", "# pSockets","# pCores", "Max VM pro Host", "Ø VM pro Host"]}
    hardware_df = pd.DataFrame(hardware_first_column_df)
    hardware_second_column = [host_amount, sockets_amount, cores_amount, max_vm_host, average_vm_host]
    hardware_df.loc[:,'Werte'] = hardware_second_column


    max_core_amount = round(df_vHosts_filtered['CPU Cores'].max())
    max_frequency_amount = round(df_vHosts_filtered['CPU Speed'].max())
    average_frequency_amount = round(df_vHosts_filtered['CPU Speed'].mean())
    max_usage_amount = round(df_vHosts_filtered['CPU Usage'].max())
    average_usage_amount = round(df_vHosts_filtered['CPU Usage'].mean())
    pCPU_first_column_df = {'': ["Max Core pro Host", "Max Taktrate / Prozessor (Ghz)","Ø Taktrate / Prozessor (Ghz)", "Max CPU Nutzung (%)", "Ø CPU Nutzung (%)"]}
    pCPU_df = pd.DataFrame(pCPU_first_column_df)
    pCPU_second_column = [max_core_amount, max_frequency_amount, average_frequency_amount,max_usage_amount,average_usage_amount]
    pCPU_df.loc[:,'Werte'] = pCPU_second_column


    max_pRAM_amount = round(df_vHosts_filtered['Memory Size'].max())
    max_pRAM_usage = round(df_vHosts_filtered['Memory Usage'].max())
    average_pRAM_usage = round(df_vHosts_filtered['Memory Usage'].mean())
    memory_first_column_df = {'': ["Max pRAM pro Host", "Max pRAM Nutzung (%)","Ø pRAM Nutzung (%)"]}
    memory_df = pd.DataFrame(memory_first_column_df)
    memory_second_column = [max_pRAM_amount, max_pRAM_usage, average_pRAM_usage]
    memory_df.loc[:,'Werte'] = memory_second_column

    return hardware_df, pCPU_df, memory_df


#----------------------------------------------------------------------------------------------------------------------------------------------------------------

# Generate vCPU Overview Section for streamlit column 1+2
def generate_vCPU_overview_df(custom_df):

    vCPU_provisioned = int(custom_df["vCPUs"].sum())
    vCPU_peak = int(custom_df["vCPU Peak #"].sum())
    vCPU_average = int(custom_df["vCPU Average #"].sum())
    vCPU_median = int(custom_df["vCPU Median #"].sum())
    vCPU_95_percentile = int(custom_df["vCPU 95th Percentile #"].sum())
    vCPU_overview_first_column = {'': ["# vCPUs (provisioned)", "# vCPUs (Peak)", "# vCPUs (Average)", "# vCPUs (Median)", "# vCPUs (95th Percentile)"]}
    vCPU_overview_df = pd.DataFrame(vCPU_overview_first_column)
    vCPU_overview_second_column = [vCPU_provisioned, vCPU_peak, vCPU_average, vCPU_median, vCPU_95_percentile]
    vCPU_overview_df.loc[:,'vCPU'] = vCPU_overview_second_column

    return vCPU_overview_df

# Generate vMemory Overview Section for streamlit column 1+2
def generate_vMemory_overview_df(custom_df):

    vMemory_provisioned = custom_df["vMemory Size (GiB)"].sum()
    vMemory_peak = custom_df["vMemory Peak #"].sum()
    vMemory_average = custom_df["vMemory Average #"].sum()
    vMemory_median = custom_df["vMemory Median #"].sum()
    vMemory_95_percentile = custom_df["vMemory 95th Percentile #"].sum()
    vMemory_overview_first_column = {'': ["# vMemory (provisioned)", "# vMemory (Peak)", "# vMemory (Average)", "# vMemory (Median)", "# vMemory (95th Percentile)"]}
    vMemory_overview_df = pd.DataFrame(vMemory_overview_first_column)
    vMemory_overview_second_column = [vMemory_provisioned, vMemory_peak, vMemory_average, vMemory_median, vMemory_95_percentile]
    vMemory_overview_df.loc[:,'GiB'] = vMemory_overview_second_column

     # Style data values to two decimals and set default value in case of NAN
    vMemory_overview_df = vMemory_overview_df.style.format(precision=2, na_rep='nicht vorhanden') 
   
    return vMemory_overview_df

# Generate df for output on streamlit dataframe
def generate_results_df_for_output(custom_df, vm_detail_columns_to_show):

    # Style data values to two decimals and set default value in case of NAN
    custom_df = custom_df.style.format(precision=2, na_rep='nicht vorhanden') 

    # drop columns based on multiselect
    custom_df.data = drop_columns_based_on_multiselect(custom_df.data, vm_detail_columns_to_show)

    return custom_df

# drop columns based on multiselect
def drop_columns_based_on_multiselect(new_df, vm_detail_columns_to_show): 

    for column in new_df.columns.values:
        if column not in vm_detail_columns_to_show:
            new_df.drop(columns=column, inplace=True)
    
    return new_df

# Generate dataframe as excel file for downloads
#@st.cache - I do not think cache helps here, as it gets regenerated after a change / download
def download_as_excel(output_to_show, vCPU_overview, vMemory_overview):
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    output_to_show.to_excel(writer, index=False, sheet_name='VM Details', startrow=4, startcol=0)
    workbook = writer.book
    worksheet_vm_details = writer.sheets['VM Details']
    header_format = workbook.add_format({'bold': True, 'font_color': '#034EA2','font_size':18})
    subheader_format = workbook.add_format({'bold': True, 'font_color': '#000000','font_size':14})
    
    for col in range(21): #set column width for cells
        worksheet_vm_details.set_column(col, col, 25)
    worksheet_vm_details.write(0, 0, "VM Right Sizing Analyse - VM Details",header_format)
    worksheet_vm_details.write(2, 0, "Bitte Anmerkungen auf gesondertem Tabellenblatt beachten.")
    worksheet_vm_details.freeze_panes(5, 0)
    format_dataframe_as_table(writer, 'VM Details', output_to_show.data)

    vCPU_overview.to_excel(writer, index=False, sheet_name='Uebersicht', startrow=4, startcol=0)
    vMemory_overview.to_excel(writer, index=False, sheet_name='Uebersicht', startrow=21, startcol=0)
    worksheet_uebersicht = writer.sheets['Uebersicht']
    
    for col in range(2): #set column width for cells
        worksheet_uebersicht.set_column(col, col, 25)
    worksheet_uebersicht.write(0, 0, "VM Right Sizing Analyse - Uebersicht",header_format)
    worksheet_uebersicht.write(2, 0, "vCPU Gesamt-Auswertung:", subheader_format)
    worksheet_uebersicht.write(19, 0, "vMemory Gesamt-Auswertung:", subheader_format)

    # Charts are independent of worksheets
    chart_vcpu = workbook.add_chart({'type': 'column'})
    chart_vcpu.set_legend({'none': True})
    chart_vram = workbook.add_chart({'type': 'column'})
    chart_vram.set_legend({'none': True})
    diff_color_list = list([{ 'fill': { 'color':'#F36D21' }}, { 'fill': { 'color':'#4C4C4E' }}, { 'fill': { 'color':'#6560AB' }}, { 'fill': { 'color':'#3ABFEF' }}, { 'fill': { 'color':'#034EA2' }}])

    chart_vcpu.add_series({'categories': '=Uebersicht!$A$6:$A$10','values': '=Uebersicht!$B$6:$B$10', 'points':diff_color_list })
    worksheet_uebersicht.insert_chart('D3', chart_vcpu)

    chart_vram.add_series({'categories': '=Uebersicht!$A$23:$A$27','values': '=Uebersicht!$B$23:$B$27', 'points':diff_color_list })
    worksheet_uebersicht.insert_chart('D20', chart_vram)

    worksheet_anmerkungen = workbook.add_worksheet('Anmerkungen')
    worksheet_anmerkungen.write(0, 0, "Anmerkungen",header_format)
    worksheet_anmerkungen.set_column('A:A', 150)
    cell_format = workbook.add_format({'text_wrap': True,'align':'top'})
    worksheet_anmerkungen.write(2, 0, "Diese Analyse basiert auf einer Nutanix Collector Auswertung. Diese kann neben den zugewiesenen vCPU & vMemory Ressourcen an die VMs ebenfalls die Performance Werte der letzten 7 Tage in 30 Minuten Intervallen aus vCenter / Nutanix Prism auslesen und bietet anhand dessen eine Möglichkeit für VM Right-Sizing Empfehlungen.", cell_format)
    worksheet_anmerkungen.write(3, 0, "Stellen Sie bitte sicher, dass die Auswertung für einen repräsentativen Zeitraum durchgeführt wurde. Für die ausgeschalteten VMs stehen (abhängig davon, wie lange diese bereits ausgeschaltet sind) i.d.R. keine Performance Werte (Peak, Average, Median oder 95th Percentile) zur Verfügung - in diesem Fall werden die provisionierten / zugewiesenen Werte verwendet.", cell_format)
    worksheet_anmerkungen.write(4, 0, "Auch werden bei allen Performance-basierten Werten 20% zusätzlicher Puffer mit eingerechnet. Generell ist die Empfehlung sich bei den Performance Werten an den 95th Percentile Werten zu orientieren, da diese die tatsächliche Auslastung am besten repräsentieren und nicht durch ggf. kurzzeitige Lastspitzen verfälscht werden.", cell_format)
    worksheet_anmerkungen.write(5, 0, "Die gezeigten Empfehlungen orientieren sich rein an der vCPU & vMemory Auslastung der VM – ohne die darin laufenden Anwendungen & deren Anforderungen zu berücksichtigen. Daher obliegt Ihnen eine abschließende Bewertung, ob die getroffenen Right Sizing Empfehlungen bei Ihnen durchführbar bzw. supported sind.", cell_format)
    worksheet_anmerkungen.write(6, 0, "Solch ein VM Right Sizing bietet sich vor der Beschaffung einer neuen Infrastruktur an, sollte aber auch darüber hinaus regelmäßig und wiederkehrend durchgeführt werden. Nutanix bietet diese Funktionalität ebenfalls bereits als einen integrierten Bestandteil des Prism PRO Funktionsumfanges. Hierbei werden umfangreichere Analysen durchgeführt die sich über einen längeren Zeitraum erstrecken und weitere Mehrwerte bieten.", cell_format)
    worksheet_anmerkungen.write(8, 0, "Disclaimer: Die automatische Auswertung basiert auf einem Hobby Projekt und dient primär als Anhaltspunkt für ein mögliches Right Sizing - keine Garantie auf Vollständigkeit oder Korrektheit der Auswertung / Daten.", cell_format) 

    writer.save()
    processed_data = output.getvalue()
    return processed_data

# Format dataframe as table in excel
def format_dataframe_as_table(writer, sheet_name, output_to_show):
    outcols = output_to_show.columns
    if len(outcols) > 25:
        raise ValueError('table width out of range for current logic')
    tbl_hdr = [{'header':c} for c in outcols]
    bottom_num = len(output_to_show)+1
    right_letter = chr(65-1+len(outcols))
    tbl_corner = right_letter + str(bottom_num+4)
    worksheet = writer.sheets[sheet_name]
    worksheet.add_table('A5:' + tbl_corner,  {'columns':tbl_hdr})

# generate the values required for the savings text string
def get_savings_value(performance_type_selected,vCPU_overview,vMemory_overview):

    if performance_type_selected == '95th Percentile':
        savings_vCPU = int(vCPU_overview.iat[0,1])-int(vCPU_overview.iat[4,1])
        savings_vMemory = int(vMemory_overview.iat[0,1])-int(vMemory_overview.iat[4,1])
    elif performance_type_selected == "Peak":
        savings_vCPU = int(vCPU_overview.iat[0,1])-int(vCPU_overview.iat[1,1])
        savings_vMemory = int(vMemory_overview.iat[0,1])-int(vMemory_overview.iat[1,1])
    elif performance_type_selected == "Average":
        savings_vCPU = int(vCPU_overview.iat[0,1])-int(vCPU_overview.iat[2,1])
        savings_vMemory = int(vMemory_overview.iat[0,1])-int(vMemory_overview.iat[2,1])
    elif performance_type_selected == "Median":
        savings_vCPU = int(vCPU_overview.iat[0,1])-int(vCPU_overview.iat[3,1])
        savings_vMemory = int(vMemory_overview.iat[0,1])-int(vMemory_overview.iat[3,1])

    return savings_vCPU, savings_vMemory

# generates the default columns to show of the tables based on selectbox value
def get_default_columns_to_show(performance_type_selected):

    if performance_type_selected == '95th Percentile':
        columns_to_show = [0,1,2,3,10,11,12,19,20]
    elif performance_type_selected == "Peak":
        columns_to_show = [0,1,2,3,4,5,12,13,14]
    elif performance_type_selected == "Average":
        columns_to_show = [0,1,2,3,6,7,12,15,16]
    elif performance_type_selected == "Median":
        columns_to_show = [0,1,2,3,8,9,12,17,18]

    return columns_to_show