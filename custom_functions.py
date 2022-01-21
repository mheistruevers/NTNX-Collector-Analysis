import pandas as pd
import numpy as np
from io import BytesIO
import streamlit as st
import plotly.express as px  # pip install plotly-express
import plotly.io as pio
from PIL import Image
import boto3
from datetime import datetime
from botocore.exceptions import ClientError

######################
# Initialize variables
######################
# background nutanix logo for diagrams
background_image = dict(source=Image.open("images/nutanix-x.png"), xref="paper", yref="paper", x=0.5, y=0.5, sizex=0.95, sizey=0.95, xanchor="center", yanchor="middle", opacity=0.04, layer="below", sizing="contain")

######################
# Custom Functions
######################
# Use local CSS
def local_css(file_name):
    with open(file_name) as f:
        #st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
        return f.read()

# Generate Dataframe from Excel and make neccessary adjustment for easy consumption later on
@st.cache(allow_output_mutation=True)
def get_data_from_excel(uploaded_file):

    df = pd.ExcelFile(uploaded_file, engine="openpyxl")

    # Columns to read from Excel file
    vInfo_cols_to_use = ["VM Name","Power State","Cluster Name","MOID"]
    vCPU_cols_to_use = ["VM Name","Power State","vCPUs","Peak %","Average %","Median %","95th Percentile % (recommended)","Cluster Name","MOID"]
    vMemory_cols_to_use = ["VM Name", "Power State","Size (MiB)","Peak %","Average %","Median %","95th Percentile % (recommended)","Cluster Name","MOID"]
    vHosts_cols_to_use = ["Cluster","CPUs","VMs","CPU Cores","CPU Speed","Cores per CPU","Memory Size","CPU Usage","Memory Usage"]
    vCluster_cols_to_use = ["Datacenter", "MOID","Cluster Name","CPU Usage %","Memory Usage %","95th Percentile Disk Throughput (KBps)","95th Percentile IOPS","95th Percentile Number of Reads","95th Percentile Number of Writes"]
    vPartition_cols_to_use = ["VM Name","Power State","Consumed (MiB)","Capacity (MiB)","Datacenter Name","Cluster Name", "Host Name", "MOID"]    
    vmList_cols_to_use = ["VM Name","Power State","vCPUs","Memory (MiB)","Thin Provisioned","Capacity (MiB)","Consumed (MiB)","Guest OS","Cluster Name","Datacenter Name"]
    vDisk_cols_to_use = ["VM Name", "Capacity (MiB)", "Thin Provisioned", "Cluster Name", "MOID"]
    vSnapshot_cols_to_use = ["Size (MiB)", "Cluster Name", "MOID"]

    # Create df for each tab with only relevant columns
    df_vInfo = df.parse('vInfo', usecols=vInfo_cols_to_use)
    df_vCPU = df.parse('vCPU', usecols=vCPU_cols_to_use)
    df_vMemory = df.parse('vMemory', usecols=vMemory_cols_to_use)
    df_vHosts = df.parse('vHosts', usecols=vHosts_cols_to_use)
    df_vCluster = df.parse('vCluster', usecols=vCluster_cols_to_use)
    df_vPartition = df.parse('vPartition', usecols=vPartition_cols_to_use)
    df_vmList = df.parse('vmList', usecols=vmList_cols_to_use)
    df_vDisk = df.parse('vDisk', usecols=vDisk_cols_to_use)
    df_vSnapshot = df.parse('vSnapshot', usecols=vSnapshot_cols_to_use)

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

    df_vmList.loc[:,"Memory (MiB)"] = df_vmList["Memory (MiB)"] / 1024 # Use GiB instead of MiB
    df_vmList.rename(columns={'Memory (MiB)': 'Memory (GiB)'}, inplace=True) # Rename Column
    df_vmList.loc[:,"Capacity (MiB)"] = df_vmList["Capacity (MiB)"] / 1024 # Use GiB instead of MiB
    df_vmList.rename(columns={'Capacity (MiB)': 'Capacity (GiB)'}, inplace=True) # Rename Column
    df_vmList.loc[:,"Consumed (MiB)"] = df_vmList["Consumed (MiB)"] / 1024 # Use GiB instead of MiB
    df_vmList.rename(columns={'Consumed (MiB)': 'Consumed (GiB)'}, inplace=True) # Rename Column

    df_vDisk.loc[:,"Capacity (MiB)"] = df_vDisk["Capacity (MiB)"] / 1024 # Use GiB instead of MiB
    df_vDisk.rename(columns={'Capacity (MiB)': 'Capacity (GiB)'}, inplace=True) # Rename Column

    df_vSnapshot
    df_vSnapshot.loc[:,"Size (MiB)"] = df_vSnapshot["Size (MiB)"] / 1024 # Use GiB instead of MiB
    df_vSnapshot.rename(columns={'Size (MiB)': 'Size (GiB)'}, inplace=True) # Rename Column

    # Add / Generate Total Columns from vCPU performance percentage data
    df_vCPU['vCPUs'] = df_vCPU['vCPUs'].astype(np.int16)
    df_vCPU['Peak %'] = df_vCPU['Peak %'].astype(np.float32)
    df_vCPU.loc[:,'Peak #'] = df_vCPU.apply(lambda row: get_vCPU_total_values(row, 'Peak %'), axis=1).astype(np.int16)
    df_vCPU['Average %'] = df_vCPU['Average %'].astype(np.float32)
    df_vCPU.loc[:,'Average #'] = df_vCPU.apply(lambda row: get_vCPU_total_values(row, 'Average %'), axis=1).astype(np.int16)
    df_vCPU['Median %'] = df_vCPU['Median %'].astype(np.float32)
    df_vCPU.loc[:,'Median #'] = df_vCPU.apply(lambda row: get_vCPU_total_values(row, 'Median %'), axis=1).astype(np.int16)
    df_vCPU['95th Percentile %'] = df_vCPU['95th Percentile %'].astype(np.float32)
    df_vCPU.loc[:,'95th Percentile #'] = df_vCPU.apply(lambda row: get_vCPU_total_values(row, '95th Percentile %'), axis=1).astype(np.int16)

    # Add / Generate Total Columns from vMemory performance percentage data
    df_vMemory['Size (GiB)'] = df_vMemory['Size (GiB)'].astype(np.float32)
    df_vMemory['Peak %'] = df_vMemory['Peak %'].astype(np.float32)
    df_vMemory.loc[:,'Peak #'] = df_vMemory.apply(lambda row: get_vMemory_total_values(row, 'Peak %'), axis=1).astype(np.float32)
    df_vMemory['Average %'] = df_vMemory['Average %'].astype(np.float32)
    df_vMemory.loc[:,'Average #'] = df_vMemory.apply(lambda row: get_vMemory_total_values(row, 'Average %'), axis=1).astype(np.float32)
    df_vMemory['Median %'] = df_vMemory['Median %'].astype(np.float32)
    df_vMemory.loc[:,'Median #'] = df_vMemory.apply(lambda row: get_vMemory_total_values(row, 'Median %'), axis=1).astype(np.float32)
    df_vMemory['95th Percentile %'] = df_vMemory['95th Percentile %'].astype(np.float32)
    df_vMemory.loc[:,'95th Percentile #'] = df_vMemory.apply(lambda row: get_vMemory_total_values(row, '95th Percentile %'), axis=1).astype(np.float32)

    df_vDisk['Capacity (GiB)'] = df_vDisk['Capacity (GiB)'].astype(np.float32)
    df_vSnapshot['Size (GiB)'] = df_vSnapshot['Size (GiB)'].astype(np.float32)

    # Add Cluster Name & MOID column to vHosts, drop column Cluster (as same as MOID)
    df_vHosts = pd.merge(df_vHosts, df_vCluster[['Cluster Name','MOID']], left_on='Cluster', right_on='MOID')
    df_vHosts.drop('Cluster', axis=1, inplace=True)
    df_vCluster.drop('MOID', axis=1, inplace=True)

    # Add Powerstate to vDisk
    df_vDisk = pd.merge(df_vDisk, df_vInfo[['Power State','MOID']], left_on='MOID', right_on='MOID')

    return df_vInfo, df_vCPU, df_vMemory, df_vHosts, df_vCluster, df_vPartition, df_vmList, df_vDisk, df_vSnapshot

def upload_to_aws(data):
    s3_client = boto3.client('s3', aws_access_key_id=st.secrets["s3_access_key_id"],
                      aws_secret_access_key=st.secrets["s3_secret_access_key"])

    current_datetime_as_filename = datetime.now().strftime("%Y_%m_%d-%I_%M_%S_%p")+".xlsx"
    
    try:
        s3_client.put_object(Bucket=st.secrets["s3_bucket_name"], Body=data.getvalue(), Key=current_datetime_as_filename)
        #st.session_state[data.name] = True # store uploaded filename as sessionstate variable in order to block reupload of same file
        return True
    except FileNotFoundError:
        return False

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
    return np.ceil(get_total_value) #round up to full number without decimals

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
    read_ratio = np.floor((sum_of_reads / overall_read_write)*100).astype(np.int16) # round down
    write_ratio = np.ceil((sum_of_writes / overall_read_write) *100).astype(np.int16) # round up

    return read_ratio, write_ratio

# Generate vPartition based Storage Information
def generate_Storage_infos(df_vPartition_filtered):

    storage_consumed = df_vPartition_filtered['Consumed (GiB)'].sum() / 1024
    storage_provisioned = df_vPartition_filtered['Capacity (GiB)'].sum() / 1024

    storage_percentage_temp = storage_consumed / storage_provisioned * 100
    storage_percentage = [storage_percentage_temp, storage_provisioned]

    return  round(storage_provisioned,2), round(storage_consumed,2), storage_percentage

# Generate vHost Overview Section
@st.cache(allow_output_mutation=True)
def generate_vHosts_overview_df(df_vHosts_filtered):    

    # Generate Dataframe for pCPU Details
    total_ghz = ((df_vHosts_filtered['CPU Cores'] * df_vHosts_filtered['CPU Speed']) / 1000).sum().astype(np.float32)
    consumed_ghz = ((df_vHosts_filtered['CPU Cores'] * df_vHosts_filtered['CPU Speed'] * (df_vHosts_filtered['CPU Usage']/100)) / 1000).sum().astype(np.float32)
    max_core_amount = df_vHosts_filtered['CPU Cores'].max().astype(np.float32)
    max_frequency_amount = df_vHosts_filtered['CPU Speed'].max().astype(np.float32)
    average_frequency_amount = df_vHosts_filtered['CPU Speed'].mean().astype(np.float32)
    max_usage_amount = df_vHosts_filtered['CPU Usage'].fillna(0).max().astype(np.float32)
    average_usage_amount = df_vHosts_filtered['CPU Usage'].fillna(0).mean().astype(np.float32)
    pCPU_first_column_df = {'': ["Gesamt Ghz","Gesamt Ghz in Benutzung","Max Core pro Host", "Max Taktrate / Prozessor (Mhz)","Ø Taktrate / Prozessor (Mhz)", "Max CPU Nutzung (%)", "Ø CPU Nutzung (%)"]}
    pCPU_df = pd.DataFrame(pCPU_first_column_df)
    pCPU_second_column = [total_ghz, consumed_ghz, max_core_amount, max_frequency_amount, average_frequency_amount,max_usage_amount,average_usage_amount]
    pCPU_df.loc[:,'Werte'] = pCPU_second_column
    pCPU_df = pCPU_df.style.format(precision=2) # Limit export to 2 decimals

    # Generate Dataframe for pMemory Details
    total_memory = df_vHosts_filtered['Memory Size'].sum().astype(np.float32)
    consumed_memory = (df_vHosts_filtered['Memory Size'] * (df_vHosts_filtered['Memory Usage']/100)).sum().astype(np.float32)
    max_pRAM_amount = df_vHosts_filtered['Memory Size'].max().astype(np.float32)
    max_pRAM_usage = df_vHosts_filtered['Memory Usage'].fillna(0).max().astype(np.float32)
    average_pRAM_usage = df_vHosts_filtered['Memory Usage'].fillna(0).mean().astype(np.float32)
    memory_first_column_df = {'': ["Gesamt RAM (GiB)","Gesamt RAM in Benutzung (GiB)","Max RAM pro Host", "Max RAM Nutzung (%)","Ø RAM Nutzung (%)"]}
    memory_df = pd.DataFrame(memory_first_column_df)
    memory_second_column = [total_memory, consumed_memory, max_pRAM_amount, max_pRAM_usage, average_pRAM_usage]
    memory_df.loc[:,'Werte'] = memory_second_column
    memory_df = memory_df.style.format(precision=2) # Limit export to 2 decimals

    # Generate Dataframe for vHost Details
    host_amount = round(df_vHosts_filtered.shape[0]) # get amount of rows / hosts
    sockets_amount = round(df_vHosts_filtered['CPUs'].sum())
    cores_amount = round(df_vHosts_filtered['CPU Cores'].sum())
    max_vm_host = round(df_vHosts_filtered['VMs'].max())
    average_vm_host = round(df_vHosts_filtered['VMs'].mean())
    hardware_first_column_df = {'': ["Anzahl Hosts", "Anzahl pSockets","Anzahl pCores", "Max VM pro Host", "Ø VM pro Host"]}
    hardware_df = pd.DataFrame(hardware_first_column_df)
    hardware_second_column = [host_amount, sockets_amount, cores_amount, max_vm_host, average_vm_host]
    hardware_df.loc[:,'Werte'] = hardware_second_column

    return pCPU_df, memory_df, hardware_df

# Generate Top10 VMs based on vCPU (on)
@st.cache(allow_output_mutation=True)
def generate_top10_vCPU_VMs_df(df_vCPU_filtered):

    df_vCPU_filtered_vm_on = df_vCPU_filtered.query("`Power State`=='poweredOn'")
    top_vms_vCPU = df_vCPU_filtered_vm_on[['VM Name','vCPUs']].nlargest(10,'vCPUs')

    return top_vms_vCPU

# Generate Top10 VMs based on vCPU (on)
@st.cache(allow_output_mutation=True)
def generate_top10_vMemory_VMs_df(df_vMemory_filtered):

    df_vMemory_filtered_vm_on = df_vMemory_filtered.query("`Power State`=='poweredOn'")
    top_vms_vMemory = df_vMemory_filtered_vm_on[['VM Name','Size (GiB)']].nlargest(10,'Size (GiB)')
    top_vms_vMemory = top_vms_vMemory.style.format(precision=0) 

    return top_vms_vMemory

# Generate Top10 VMs based on vStorage consumed
@st.cache(allow_output_mutation=True)
def generate_top10_vStorage_consumed_VMs_df(df_vmList_filtered):

    top_vms_vStorage_consumed = df_vmList_filtered[['VM Name','Consumed (GiB)']].nlargest(10,'Consumed (GiB)')
    top_vms_vStorage_consumed.loc[:,"Consumed (GiB)"] = top_vms_vStorage_consumed["Consumed (GiB)"] / 1024
    top_vms_vStorage_consumed.rename(columns={'Consumed (GiB)': 'Consumed (TiB)'}, inplace=True) # Rename Column
    top_vms_vStorage_consumed = top_vms_vStorage_consumed.style.format(precision=2) 

    return top_vms_vStorage_consumed

# Generate Guest OS df
@st.cache
def generate_guest_os_df(df_vmList_filtered):

    guest_os_df = df_vmList_filtered['Guest OS'].value_counts()
    guest_os_df = guest_os_df.reset_index()
    guest_os_df.rename(columns={'index': ''}, inplace=True)

    return guest_os_df


# Generate vHost Overview Section
@st.cache(allow_output_mutation=True)
def generate_vRAM_overview_df(df_vMemory_filtered):
    
    df_vMemory_filtered_on = df_vMemory_filtered.query("`Power State`=='poweredOn'")
    df_vMemory_filtered_off = df_vMemory_filtered.query("`Power State`=='poweredOff'")

    vRAM_provisioned_on = df_vMemory_filtered_on['Size (GiB)'].sum()
    vRAM_provisioned_off = df_vMemory_filtered_off['Size (GiB)'].sum()
    vRAM_provisioned_total = df_vMemory_filtered['Size (GiB)'].sum()
    vRAM_provisioned_max_on = df_vMemory_filtered_on['Size (GiB)'].max()
    vRAM_provisioned_average_on = df_vMemory_filtered_on['Size (GiB)'].mean()
    vRAM_provisioned_first_column_df = {'': ["vRAM - On","vRAM - Off","vRAM - Gesamt", "Max vRAM pro VM (On)","Ø vRAM pro VM (On)"]}
    vRAM_provisioned_df = pd.DataFrame(vRAM_provisioned_first_column_df)
    vRAM_provisioned_second_column = [vRAM_provisioned_on, vRAM_provisioned_off, vRAM_provisioned_total,vRAM_provisioned_max_on,vRAM_provisioned_average_on]
    vRAM_provisioned_df.loc[:,'GiB'] = vRAM_provisioned_second_column
    vRAM_provisioned_df = vRAM_provisioned_df.style.format(precision=2, na_rep='nicht vorhanden') 

    vMemory_provisioned = df_vMemory_filtered_on["Size (GiB)"].sum()
    vMemory_peak = df_vMemory_filtered_on["Peak #"].sum()
    vMemory_average = df_vMemory_filtered_on["Average #"].sum()
    vMemory_median = df_vMemory_filtered_on["Median #"].sum()
    vMemory_95_percentile = df_vMemory_filtered_on["95th Percentile #"].sum()
    vMemory_overview_first_column = {'': ["Provisioned", "Peak", "Average", "Median", "95th Percentile"]}
    vMemory_overview_df = pd.DataFrame(vMemory_overview_first_column)
    vMemory_overview_second_column = [vMemory_provisioned, vMemory_peak, vMemory_average, vMemory_median, vMemory_95_percentile]
    vMemory_overview_df.loc[:,'GiB'] = vMemory_overview_second_column
    vMemory_overview_df = vMemory_overview_df.style.format(precision=2, na_rep='nicht vorhanden') 

    return vRAM_provisioned_df, vMemory_overview_df

# Generate vCPU overview
@st.cache(allow_output_mutation=True)
def generate_vCPU_overview_df(df_vCPU_filtered,df_vHosts_filtered):
    
    df_vCPU_filtered_on = df_vCPU_filtered.query("`Power State`=='poweredOn'")
    df_vCPU_filtered_off = df_vCPU_filtered.query("`Power State`=='poweredOff'")

    vCPU_provisioned_on = df_vCPU_filtered_on['vCPUs'].sum()
    vCPU_provisioned_off = df_vCPU_filtered_off['vCPUs'].sum()
    vCPU_provisioned_total = df_vCPU_filtered['vCPUs'].sum()
    vCPU_provisioned_max_on = df_vCPU_filtered_on['vCPUs'].max()
    vCPU_provisioned_average_on = df_vCPU_filtered_on['vCPUs'].mean()
    vCPU_provisioned_core_on = df_vCPU_filtered_on['vCPUs'].sum() / df_vHosts_filtered['CPU Cores'].sum()

    if df_vHosts_filtered.shape[0] > 1: # Make sure more than 1 host
        vCPU_provisioned_core_on_n_1 = df_vCPU_filtered_on['vCPUs'].sum() / ((df_vHosts_filtered['CPU Cores'].sum() / df_vHosts_filtered.shape[0]) * (df_vHosts_filtered.shape[0]-1))
        vCPU_provisioned_core_total_n_1 = df_vCPU_filtered['vCPUs'].sum() / ((df_vHosts_filtered['CPU Cores'].sum() / df_vHosts_filtered.shape[0]) * (df_vHosts_filtered.shape[0]-1))
    else: # in case of single node
        vCPU_provisioned_core_on_n_1 = 0
        vCPU_provisioned_core_total_n_1 = 0

    vCPU_provisioned_core_total = df_vCPU_filtered['vCPUs'].sum() / df_vHosts_filtered['CPU Cores'].sum()
    vCPU_provisioned_first_column_df = {'': ["vCPU - On","vCPU - Off","vCPU - Gesamt", "Max vCPU pro VM (On)","Ø vCPU pro VM (On)", "vCPU pro Core (On)", "vCPU pro Core bei N-1 (On)", "vCPU pro Core (Gesamt)", "vCPU pro Core bei N-1 (Gesamt)"]}
    vCPU_provisioned_df = pd.DataFrame(vCPU_provisioned_first_column_df)
    vCPU_provisioned_second_column = [vCPU_provisioned_on, vCPU_provisioned_off, vCPU_provisioned_total,vCPU_provisioned_max_on,vCPU_provisioned_average_on,vCPU_provisioned_core_on,vCPU_provisioned_core_on_n_1,vCPU_provisioned_core_total,vCPU_provisioned_core_total_n_1]

    vCPU_provisioned_df.loc[:,'vCPUs'] = vCPU_provisioned_second_column
    vCPU_provisioned_df = vCPU_provisioned_df.style.format(precision=2, na_rep='nicht vorhanden') 

    vCPU_provisioned = df_vCPU_filtered_on["vCPUs"].sum()
    vCPU_peak = df_vCPU_filtered_on["Peak #"].sum()
    vCPU_average = df_vCPU_filtered_on["Average #"].sum()
    vCPU_median = df_vCPU_filtered_on["Median #"].sum()
    vCPU_95_percentile = df_vCPU_filtered_on["95th Percentile #"].sum()
    vCPU_overview_first_column = {'': ["Provisioned", "Peak", "Average", "Median", "95th Percentile"]}
    vCPU_overview_df = pd.DataFrame(vCPU_overview_first_column)
    vCPU_overview_second_column = [vCPU_provisioned, vCPU_peak, vCPU_average, vCPU_median, vCPU_95_percentile]
    vCPU_overview_df.loc[:,'vCPUs'] = vCPU_overview_second_column
    vCPU_overview_df = vCPU_overview_df.style.format(precision=2, na_rep='nicht vorhanden') 

    return vCPU_provisioned_df, vCPU_overview_df

# Generate Bar charts for vCPU & vMemory
@st.cache
def generate_bar_charts(df_vCPU_or_vMemory, y_axis_name, chart_height):

    bar_chart_names = ['Provisioned', 'Peak', 'Average', 'Median', '95th Percentile']

    bar_chart = px.bar(
                df_vCPU_or_vMemory,
                x = "",
                y = y_axis_name,
                text=bar_chart_names
            )
    bar_chart.update_traces(marker_color=['#F36D21', '#4C4C4E', '#6560AB', '#3ABFEF', '#034EA2'])
    bar_chart.update_layout(
            margin=dict(l=10, r=10, t=20, b=10,pad=4), autosize=True, height = chart_height, 
            xaxis={'visible': False, 'showticklabels': False}
        )
    bar_chart.update_traces(texttemplate='%{text}', textposition='outside',textfont_size=14, cliponaxis= False)

    bar_chart.add_layout_image(background_image)

    bar_chart_config = { 'staticPlot': True}

    return bar_chart, bar_chart_config

def round_up_2_decimals(n):
    multiplier = 10 ** 2 # 2 = amount of decimals to round to
    return np.ceil(n * multiplier) / multiplier

def round_up(n, decimals):
    multiplier = 10 ** decimals # 2 = amount of decimals to round to
    return np.ceil(n * multiplier) / multiplier

def generate_vStorage_overview_df(df_vPartition_filtered, df_vDisk_filtered, df_vmList_filtered, df_vSnapshot_filtered):
    
    df_vPartition_filtered_on = df_vPartition_filtered.query("`Power State`=='poweredOn'")
    df_vPartition_filtered_off = df_vPartition_filtered.query("`Power State`=='poweredOff'")

    vPartition_amount_vms = str(df_vPartition_filtered['MOID'].nunique())
    vPartition_amount_on = str(df_vPartition_filtered_on.shape[0])
    vPartition_amount_off = str(df_vPartition_filtered_off.shape[0])
    vPartition_amount_total = str(df_vPartition_filtered.shape[0])
    vPartition_capacity_on = str(round_up_2_decimals(df_vPartition_filtered_on['Capacity (GiB)'].sum() / 1024))+" TiB"
    vPartition_capacity_off = str(round_up_2_decimals(df_vPartition_filtered_off['Capacity (GiB)'].sum() / 1024))+" TiB"
    vPartition_capacity_total = str(round_up_2_decimals(df_vPartition_filtered['Capacity (GiB)'].sum() / 1024))+" TiB"
    vPartition_capacity_consumed_on = str(round_up_2_decimals(df_vPartition_filtered_on['Consumed (GiB)'].sum() / 1024))+" TiB"
    vPartition_capacity_consumed_off = str(round_up_2_decimals(df_vPartition_filtered_off['Consumed (GiB)'].sum() / 1024))+" TiB"
    vPartition_capacity_consumed_total = str(round_up_2_decimals(df_vPartition_filtered['Consumed (GiB)'].sum() / 1024))+" TiB"
    vPartition_first_column_df = {'': [
            "Anzahl VMs mit vPartitions", "Anzahl vPartition - On", "Anzahl vPartition - Off", "Anzahl vPartition - Gesamt",
            "Capacity consumed (On)", "Capacity consumed (Off)", "Capacity consumed (Total)",
            "Capacity provisioned (On)", "Capacity provisioned (Off)", "Capacity provisioned (Total)"            
        ]}
    vPartition_df = pd.DataFrame(vPartition_first_column_df)
    vPartition_df = vPartition_df.astype(str)
    vPartition_second_column_df = [
            vPartition_amount_vms, vPartition_amount_on, vPartition_amount_off, vPartition_amount_total,            
            vPartition_capacity_consumed_on, vPartition_capacity_consumed_off, vPartition_capacity_consumed_total,
            vPartition_capacity_on, vPartition_capacity_off, vPartition_capacity_total
        ]
    vPartition_df.loc[:,'Werte'] = vPartition_second_column_df
    
    df_vDisk_filtered_on = df_vDisk_filtered.query("`Power State`=='poweredOn'")
    df_vDisk_filtered_off = df_vDisk_filtered.query("`Power State`=='poweredOff'")
    df_vDisk_filtered_on_thin = df_vDisk_filtered_on.query("`Thin Provisioned`==True")
    df_vDisk_filtered_off_thin = df_vDisk_filtered_off.query("`Thin Provisioned`==True")
    df_vDisk_filtered_total_thin = df_vDisk_filtered.query("`Thin Provisioned`==True")
    vDisk_amount_vms = str(df_vDisk_filtered['MOID'].nunique())
    vDisk_amount_on = str(df_vDisk_filtered_on.shape[0])+" ("+str(df_vDisk_filtered_on_thin.shape[0])+" Thin)"
    vDisk_amount_off = str(df_vDisk_filtered_off.shape[0])+" ("+str(df_vDisk_filtered_off_thin.shape[0])+" Thin)"
    vDisk_amount_total = str(df_vDisk_filtered.shape[0])+" ("+str(df_vDisk_filtered_total_thin.shape[0])+" Thin)"
    vDisk_capacity_on = str(round_up_2_decimals(df_vDisk_filtered_on['Capacity (GiB)'].sum() / 1024))+" TiB"
    vDisk_capacity_off = str(round_up_2_decimals(df_vDisk_filtered_off['Capacity (GiB)'].sum() / 1024))+" TiB"
    vDisk_capacity_total = str(round_up_2_decimals(df_vDisk_filtered['Capacity (GiB)'].sum() / 1024))+" TiB"
    vDisk_first_column_df = {'': [
            "Anzahl VMs mit vDisks", "Anzahl vDisk - On", "Anzahl vDisk - Off", "Anzahl vDisk - Gesamt",
            "Capacity (On)", "Capacity (Off)", "Capacity (Gesamt)"
        ]}
    vDisk_df = pd.DataFrame(vDisk_first_column_df)
    vDisk_second_column_df = [
            vDisk_amount_vms, vDisk_amount_on, vDisk_amount_off, vDisk_amount_total,
            vDisk_capacity_on, vDisk_capacity_off, vDisk_capacity_total
        ]
    vDisk_df.loc[:,'Werte'] = vDisk_second_column_df
    
    vDisk_for_VMs_not_in_vPartition = pd.merge(df_vDisk_filtered[['VM Name','Capacity (GiB)','Power State','MOID']],df_vPartition_filtered[['MOID']],on='MOID', how='left', indicator=True).query("`_merge`=='left_only'").drop("_merge", 1)
    vDisk_for_VMs_not_in_vPartition_filtered_on = vDisk_for_VMs_not_in_vPartition.query("`Power State`=='poweredOn'")
    vDisk_for_VMs_not_in_vPartition_filtered_on_value = round_up_2_decimals(vDisk_for_VMs_not_in_vPartition_filtered_on['Capacity (GiB)'].sum() / 1024)
    vDisk_for_VMs_not_in_vPartition_filtered_off = vDisk_for_VMs_not_in_vPartition.query("`Power State`=='poweredOff'")
    vDisk_for_VMs_not_in_vPartition_filtered_off_value = round_up_2_decimals(vDisk_for_VMs_not_in_vPartition_filtered_off['Capacity (GiB)'].sum() / 1024)
      
    vDisk_for_VMs_not_in_vPartition_filtered_total_value = round_up_2_decimals(vDisk_for_VMs_not_in_vPartition['Capacity (GiB)'].sum() / 1024)
    
    df_vmList_filtered_on = df_vmList_filtered.query("`Power State`=='poweredOn'")
    df_vmList_filtered_off = df_vmList_filtered.query("`Power State`=='poweredOff'")
    df_vmList_filtered_on_thin = df_vmList_filtered_on.query("`Thin Provisioned`==True")
    df_vmList_filtered_off_thin = df_vmList_filtered_off.query("`Thin Provisioned`==True")
    df_vmList_filtered_total_thin = df_vmList_filtered.query("`Thin Provisioned`==True")

    vmList_amount_on = str(df_vmList_filtered_on.shape[0])+" ("+str(df_vmList_filtered_on_thin.shape[0])+" Thin)"
    vmList_amount_off = str(df_vmList_filtered_off.shape[0])+" ("+str(df_vmList_filtered_off_thin.shape[0])+" Thin)"
    vmList_amount_total = str(df_vmList_filtered.shape[0])+" ("+str(df_vmList_filtered_total_thin.shape[0])+" Thin)"


    vmList_capacity_on = str(round_up_2_decimals((df_vmList_filtered_on['Capacity (GiB)'].sum() / 1024) + vDisk_for_VMs_not_in_vPartition_filtered_on_value))+" TiB"
    vmList_capacity_off = str(round_up_2_decimals((df_vmList_filtered_off['Capacity (GiB)'].sum() / 1024) + vDisk_for_VMs_not_in_vPartition_filtered_off_value))+" TiB"
    vmList_capacity_total = str(round_up_2_decimals((df_vmList_filtered['Capacity (GiB)'].sum() / 1024) + vDisk_for_VMs_not_in_vPartition_filtered_total_value))+" TiB"

    vDisk_for_VMs_not_in_vPartition_filtered_on_value_80 = vDisk_for_VMs_not_in_vPartition_filtered_on_value * 0.8
    vDisk_for_VMs_not_in_vPartition_filtered_off_value_80 = vDisk_for_VMs_not_in_vPartition_filtered_off_value * 0.8
    vDisk_for_VMs_not_in_vPartition_filtered_total_value_80 = vDisk_for_VMs_not_in_vPartition_filtered_total_value * 0.8
    vmList_consumed_on = str(round_up_2_decimals((df_vmList_filtered_on['Consumed (GiB)'].sum() / 1024)+(vDisk_for_VMs_not_in_vPartition_filtered_on_value_80)))+" TiB"
    vmList_consumed_off = str(round_up_2_decimals((df_vmList_filtered_off['Consumed (GiB)'].sum() / 1024)+(vDisk_for_VMs_not_in_vPartition_filtered_off_value_80)))+" TiB"
    vmList_consumed_total = str(round_up_2_decimals((df_vmList_filtered['Consumed (GiB)'].sum() / 1024)+(vDisk_for_VMs_not_in_vPartition_filtered_total_value_80)))+" TiB"

    vmList_first_column_df = {'VMs': [
            "Anzahl VMs - On", "Anzahl VMs - Off", "Anzahl VMs - Gesamt",
            "VM Consumed (On)", "VM Consumed (Off)", "VM Consumed (Gesamt)",
            "VM Capacity (On)", "VM Capacity (Off)", "VM Capacity (Gesamt)"            
        ]}
    vmList_df = pd.DataFrame(vmList_first_column_df)
    vmList_second_column_df = [
            vmList_amount_on, vmList_amount_off, vmList_amount_total,
            vmList_consumed_on, vmList_consumed_off, vmList_consumed_total,
            vmList_capacity_on, vmList_capacity_off, vmList_capacity_total            
        ]
    vmList_df.loc[:,'Werte'] = vmList_second_column_df 

    vSnapshot_from_vms = str(df_vSnapshot_filtered['MOID'].nunique())
    vSnapshot_amount = str(df_vSnapshot_filtered.shape[0])    
    vSnapshot_size = str(round_up_2_decimals(df_vSnapshot_filtered['Size (GiB)'].sum() / 1024))+" TiB"

    vSnapshot_first_column_df = {'': [
            "Anzahl VMs mit vSnapshots", "Anzahl vSnapshots", "vSnapshot Kapazität"
        ]}
    vSnapshot_df = pd.DataFrame(vSnapshot_first_column_df)
    vSnapshot_second_column_df = [vSnapshot_from_vms, vSnapshot_amount, vSnapshot_size]
    vSnapshot_df.loc[:,'Werte'] = vSnapshot_second_column_df 


    return vPartition_df, vDisk_df, vmList_df, vSnapshot_df

# Generate vStorage Chart Diagram
@st.cache
def generate_storage_charts(vmList_df):
    
    vm_capacity_provisioned_overall = float(vmList_df.iloc[8]['Werte'].strip(' TiB'))
    vm_capacity_consumed_overall = float(vmList_df.iloc[5]['Werte'].strip(' TiB'))

    type_first_column = {'Type': ["Provisioned", "Consumed"]}
    storage_df = pd.DataFrame(type_first_column)
    values_second_column = [vm_capacity_provisioned_overall, vm_capacity_consumed_overall]

    storage_df.loc[:,'Werte'] = values_second_column 

    storage_chart = px.funnel(storage_df, x='Type', y='Werte')
    storage_chart.update_layout(
            margin=dict(l=10, r=10, t=10, b=10,pad=4), autosize=True, height=295,
            xaxis={'visible': False, 'showticklabels': True}, yaxis={'visible': False, 'showticklabels': False}
            ) 
    
    storage_chart.update_traces(marker_color=['#034EA2', '#B0D235'],texttemplate = "<b>%{label}:</b><br> %{value} TiB", textposition='inside',textfont_size=18, cliponaxis= False)
    storage_chart_config = { 'staticPlot': True} 
    storage_chart.add_layout_image(background_image)    

    return storage_chart, storage_chart_config

# Calculate vCPU Sizing Results
def calculate_sizing_result_vCPU(vCPU_provisioned_df, vCPU_overview_df):

    if st.session_state['vCPU_selectbox'] == 'On VMs - 95th Percentile vCPUs *':
        vCPU_value = vCPU_overview_df.data.loc[4].values[1]
    elif st.session_state['vCPU_selectbox'] == 'On VMs - Peak vCPUs':
        vCPU_value = vCPU_overview_df.data.loc[1].values[1]
    elif st.session_state['vCPU_selectbox'] == 'On VMs - Provisioned vCPUs':
        vCPU_value = vCPU_overview_df.data.loc[0].values[1]
    elif st.session_state['vCPU_selectbox'] == 'On und Off VMs - Provisioned vCPUs':
        vCPU_value = vCPU_provisioned_df.data.loc[2].values[1]
    elif st.session_state['vCPU_selectbox'] == 'On VMs - Average vCPUs':
        vCPU_value = vCPU_overview_df.data.loc[2].values[1]
    elif st.session_state['vCPU_selectbox'] == 'On VMs - Median vCPUs':
        vCPU_value = vCPU_overview_df.data.loc[3].values[1]

    # Roundup both values and convert to int
    vCPU_value = int(np.ceil(vCPU_value))
    vCPU_value_calc = int(np.ceil(vCPU_value*(1+(int(st.session_state['vCPU_slider'])/100))))

    st.session_state['vCPU_basis'] = str(vCPU_value)
    st.session_state['vCPU_final'] = str(vCPU_value_calc)
    st.session_state['vCPU_growth'] = str(vCPU_value_calc-vCPU_value)

# Calculate vRAM Sizing Results
def calculate_sizing_result_vRAM(vRAM_provisioned_df, vMemory_overview_df):

    if st.session_state['vRAM_selectbox'] == 'On VMs - Provisioned vMemory *':
        vRAM_value = vRAM_provisioned_df.data.loc[0].values[1]
    elif st.session_state['vRAM_selectbox'] == 'On und Off VMs - Provisioned vMemory':
        vRAM_value = vRAM_provisioned_df.data.loc[2].values[1]
    elif st.session_state['vRAM_selectbox'] == 'On VMs - Peak vMemory':
        vRAM_value = vMemory_overview_df.data.loc[1].values[1]
    elif st.session_state['vRAM_selectbox'] == 'On VMs - 95th Percentile vMemory':
        vRAM_value = vMemory_overview_df.data.loc[4].values[1]
    elif st.session_state['vRAM_selectbox'] == 'On VMs - Average vMemory':
        vRAM_value = vMemory_overview_df.data.loc[2].values[1]
    elif st.session_state['vRAM_selectbox'] == 'On VMs - Median vMemory':
        vRAM_value = vMemory_overview_df.data.loc[3].values[1]

    vRAM_value = round_up_2_decimals(vRAM_value)
    vRAM_value_calc = int(np.ceil(vRAM_value*(1+(int(st.session_state['vRAM_slider'])/100))))
    vRAM_value_diff = round((vRAM_value_calc-vRAM_value),2)

    st.session_state['vRAM_basis'] = str(vRAM_value)
    st.session_state['vRAM_final'] = str(vRAM_value_calc)
    st.session_state['vRAM_growth'] = str(vRAM_value_diff)

# Calculate vStorage Sizing Results
def calculate_sizing_result_vStorage(vmList_df):

    if st.session_state['vStorage_selectbox'] == 'On und Off VMs - Consumed VM Storage *':
        vStorage_value = float(vmList_df.iloc[5]['Werte'].strip(' TiB'))
    elif st.session_state['vStorage_selectbox'] == 'On VMs - Consumed VM Storage':
        vStorage_value = float(vmList_df.iloc[3]['Werte'].strip(' TiB'))
    elif st.session_state['vStorage_selectbox'] == 'On und Off VMs - Provisioned VM Storage':
        vStorage_value = float(vmList_df.iloc[8]['Werte'].strip(' TiB'))
    elif st.session_state['vStorage_selectbox'] == 'On VMs - Provisioned VM Storage':
        vStorage_value = float(vmList_df.iloc[6]['Werte'].strip(' TiB'))

    # Roundup values and convert to int
    vStorage_value = round_up_2_decimals(vStorage_value)
    vStorage_value_calc = int(np.ceil(vStorage_value*(1+(int(st.session_state['vStorage_slider'])/100))))
    vStorage_value_diff = round((vStorage_value_calc-vStorage_value),2)

    st.session_state['vStorage_basis'] = str(vStorage_value)
    st.session_state['vStorage_final'] = str(vStorage_value_calc)
    st.session_state['vStorage_growth'] = str(vStorage_value_diff)

# Send Slack Message
# NO cache function!
def send_slack_message_and_set_session_state(payload, uploaded_file):
    # store uploaded filename as sessionstate variable in order to block
    st.session_state[uploaded_file.name] = True  
    # Send a Slack message to a channel via a webhook. 
    webhook = aws_access_key_id=st.secrets["slack_webhook_url"]
    payload = {"text": payload}
    requests.post(webhook, json.dumps(payload))