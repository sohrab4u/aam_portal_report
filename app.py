# (START of app.py)
import streamlit as st
import pandas as pd
import os
from fpdf import FPDF
from io import BytesIO
import base64

st.set_page_config(layout="wide", page_title="Ayushman Arogya Mandir - Summary Reports")
st.title("🩺 Ayushman Arogya Mandir - Footfall Summary Reports")

def clean_columns(df):
    df.columns = [col.strip() for col in df.columns]
    return df

footfall_file = st.file_uploader("Upload Daily_Entry (Footfall Report)", type=["xlsx", "xls", "csv"])
master_file = st.file_uploader("Upload FPE_Entry (Facility Master)", type=["xlsx", "xls", "csv"])

if footfall_file and master_file:
    try:
        if footfall_file.name.endswith(".csv"):
            footfall_df = pd.read_csv(footfall_file)
        else:
            footfall_df = pd.read_excel(footfall_file)

        if master_file.name.endswith(".csv"):
            master_df = pd.read_csv(master_file)
        else:
            master_df = pd.read_excel(master_file)

        footfall_df = clean_columns(footfall_df)
        master_df = clean_columns(master_df)

        footfall_df.rename(columns={
            'Facility Name': 'Facility_Name',
            'AAM Type': 'AAM_Type',
            'District': 'District_Name',
            'Entry Date': 'Entry_Date',
            'Footfall Female': 'Footfall_Female',
            'Footfall Female ': 'Footfall_Female',
            'Footfall Total': 'Footfall_Total'
        }, inplace=True)

        master_df.rename(columns={
            'HFI_Name': 'Facility_Name',
            'FACILITY_TYPE': 'AAM_Type',
            'District_Name': 'District_Name'
        }, inplace=True)

        footfall_df['Entry_Date'] = pd.to_datetime(footfall_df['Entry_Date'], errors='coerce')

        aam_type_filter = st.selectbox("Select AAM Type", options=["AAM-USHC", "AAM-UPHC"])
        footfall_df = footfall_df[footfall_df['AAM_Type'] == aam_type_filter]
        master_df = master_df[master_df['AAM_Type'] == aam_type_filter]

        unique_dates = footfall_df['Entry_Date'].dropna().dt.date.unique()
        if len(unique_dates) > 0:
            selected_date = st.selectbox("Select Date", options=sorted(unique_dates))
            footfall_df = footfall_df[footfall_df['Entry_Date'].dt.date == selected_date]

        footfall_df.fillna(0, inplace=True)
        master_df.fillna(0, inplace=True)

        facility_summary = footfall_df.groupby(['District_Name', 'Facility_Name', 'AAM_Type'], as_index=False)[['Footfall_Total', 'Footfall_Female']].sum()
        facility_summary['% Female Footfall'] = round((facility_summary['Footfall_Female'] / facility_summary['Footfall_Total'].replace(0, 1)) * 100, 2)
        facility_summary.insert(0, 'S.No.', range(1, len(facility_summary) + 1))

        total_footfall = facility_summary['Footfall_Total'].sum()
        total_female = facility_summary['Footfall_Female'].sum()
        total_percent_female = round((total_female / total_footfall) * 100, 2) if total_footfall != 0 else 0
        total_row = {
            'S.No.': '',
            'District_Name': 'Total',
            'Facility_Name': '',
            'AAM_Type': '',
            'Footfall_Total': total_footfall,
            'Footfall_Female': total_female,
            '% Female Footfall': total_percent_female
        }
        facility_summary = pd.concat([facility_summary, pd.DataFrame([total_row])], ignore_index=True)

        total_registered = master_df.groupby('District_Name')['Facility_Name'].count().reset_index(name='Registered_Facilities')
        total_reported = footfall_df.groupby('District_Name')['Facility_Name'].nunique().reset_index(name='Reported_Facilities')
        total_footfall = footfall_df.groupby('District_Name')['Footfall_Total'].sum().reset_index(name='Total_Footfall')

        district_summary = total_registered.merge(total_reported, on='District_Name', how='left') \
                                           .merge(total_footfall, on='District_Name', how='left')

        district_summary['Reported_Facilities'].fillna(0, inplace=True)
        district_summary['Reported_Facilities'] = district_summary['Reported_Facilities'].astype(int)
        district_summary['Unreported_Facilities'] = district_summary['Registered_Facilities'] - district_summary['Reported_Facilities']
        district_summary['Avg_Footfall_Per_Facility'] = round(district_summary['Total_Footfall'] / district_summary['Reported_Facilities'].replace(0, 1), 2)
        district_summary['%_Reported'] = round((district_summary['Reported_Facilities'] / district_summary['Registered_Facilities']) * 100, 2)
        district_summary.insert(0, 'S.No.', range(1, len(district_summary) + 1))

        # 👉 Reorder columns
        district_summary = district_summary[
            ['S.No.', 'District_Name', 'Registered_Facilities', 'Reported_Facilities', 'Unreported_Facilities',
             'Total_Footfall', 'Avg_Footfall_Per_Facility', '%_Reported']
        ]

        sum_row = {
            'S.No.': '',
            'District_Name': 'Total',
            'Registered_Facilities': district_summary['Registered_Facilities'].sum(),
            'Reported_Facilities': district_summary['Reported_Facilities'].sum(),
            'Unreported_Facilities': district_summary['Unreported_Facilities'].sum(),
            'Total_Footfall': district_summary['Total_Footfall'].sum(),
            'Avg_Footfall_Per_Facility': round(district_summary['Total_Footfall'].sum() / district_summary['Reported_Facilities'].sum(), 2) if district_summary['Reported_Facilities'].sum() != 0 else 0,
            '%_Reported': round((district_summary['Reported_Facilities'].sum() / district_summary['Registered_Facilities'].sum()) * 100, 2) if district_summary['Registered_Facilities'].sum() != 0 else 0
        }
        district_summary = pd.concat([district_summary, pd.DataFrame([sum_row])], ignore_index=True)

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("📋 Facility-wise Summary")
            st.dataframe(facility_summary.fillna(0))
        with col2:
            st.subheader("📊 District-wise Summary")
            st.dataframe(district_summary.fillna(0))

        def to_excel(df):
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.fillna(0).to_excel(writer, index=False, sheet_name='Sheet1')
            return output.getvalue()

        st.download_button("📥 Download Facility-wise Excel", to_excel(facility_summary), file_name="FacilityWiseReport.xlsx")
        st.download_button("📥 Download District-wise Excel", to_excel(district_summary), file_name="DistrictWiseReport.xlsx")

        def create_pdf(df, title):
            pdf = FPDF(orientation="L", unit="mm", format="A4")
            pdf.add_page()
            pdf.set_font("Arial", size=8)
            pdf.set_fill_color(220, 220, 220)
            pdf.cell(0, 10, title, ln=1, align='C')

            col_widths = []
            for col in df.columns:
                if col == 'Facility_Name':
                    col_widths.append(60)
                elif col == 'District_Name':
                    col_widths.append(35)
                elif col == 'AAM_Type':
                    col_widths.append(25)
                else:
                    col_widths.append(30)

            for i, col in enumerate(df.columns):
                wrapped_header = col.replace(' ', '\n')
                x, y = pdf.get_x(), pdf.get_y()
                pdf.multi_cell(col_widths[i], 5, wrapped_header, border=1, align='C')
                pdf.set_xy(x + col_widths[i], y)
            pdf.ln()

            for _, row in df.fillna(0).iterrows():
                for i, val in enumerate(row):
                    pdf.cell(col_widths[i], 10, str(val), border=1)
                pdf.ln()

            return pdf.output(dest='S').encode('latin1')

        st.download_button("🧾 Download Facility-wise PDF", create_pdf(facility_summary, "Facility-wise Summary Report"), file_name="FacilityWiseReport.pdf")
        st.download_button("🧾 Download District-wise PDF", create_pdf(district_summary, "District-wise Summary Report"), file_name="DistrictWiseReport.pdf")

        def to_combined_excel(facility_df, district_df):
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                facility_df.fillna(0).to_excel(writer, index=False, sheet_name='Facility-wise Summary')
                district_df.fillna(0).to_excel(writer, index=False, sheet_name='District-wise Summary')
                workbook = writer.book
                for sheet_name, df in {
                    'Facility-wise Summary': facility_df.fillna(0),
                    'District-wise Summary': district_df.fillna(0)
                }.items():
                    worksheet = writer.sheets[sheet_name]
                    for i, width in enumerate(df.columns.astype(str)):
                        col_width = max(df[width].astype(str).map(len).max(), len(width)) + 2
                        worksheet.set_column(i, i, col_width)
            return output.getvalue()

        st.download_button(
            "📤 Download Combined Excel Report",
            to_combined_excel(facility_summary, district_summary),
            file_name="Combined_Footfall_Report.xlsx"
        )

    except Exception as e:
        st.error(f"❌ Error processing files: {e}")
else:
    st.info("👆 Please upload both required files to generate the reports.")
