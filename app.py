import io
from datetime import datetime
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

# ==========================================
# PAGE CONFIGURATION & STYLING
# ==========================================
st.set_page_config(
    page_title="Cardstel Solutions - Financial Card Perso Production",
    page_icon="💳",
    layout="wide",
)

st.title("💳 Cardstel Solutions Ltd - Financial Card Perso Production & KPI Dashboard")
st.markdown(
    "Daily production tracking, target variance analysis, and performance output metrics."
)


# ==========================================
# INITIALIZE SESSION STATE & DEMO DATA
# ==========================================
def get_demo_data():
  """Generates demo production records for initial app loading."""
  np.random.seed(42)
  dates = pd.date_range(end=datetime.today(), periods=30, freq="D")
  shifts = ["Morning", "Afternoon", "Night"]
  clients = ["Opay", "Polaris", "Access", "UBA", "Zenith"]
  card_types = ["Verve", "Afrigo", "Mastercard", "Visa"]
  machines = ["MS-1", "MS-2", "PT-1", "PT-2"]
  operators = ["Adanna", "Damilola", "Godson", "Chidi", "Aisha"]
  supervisors = ["Vivian Iyaha", "Michael O.", "Grace E."]

  data = []
  for i in range(120):
    date = np.random.choice(dates)
    data.append({
        "Production Date": date.strftime("%Y-%m-%d"),
        "Shift Type": np.random.choice(shifts),
        "Client": np.random.choice(clients),
        "Card Type": np.random.choice(card_types),
        "Quantity Produced": int(np.random.randint(3500, 8500)),
        "Machine Used": np.random.choice(machines),
        "Operator Name": np.random.choice(operators),
        "Supervisor Name": np.random.choice(supervisors),
    })
  return pd.DataFrame(data)


if "production_df" not in st.session_state:
  st.session_state.production_df = get_demo_data()

if "targets" not in st.session_state:
  st.session_state.targets = {
      "Daily Target": 6000,
      "Monthly Target": 180000,
      "Yearly Target": 2160000,
  }

df = st.session_state.production_df
df["Production Date"] = pd.to_datetime(df["Production Date"])


# ==========================================
# SIDEBAR NAVIGATION & FILTERS
# ==========================================
st.sidebar.header("Navigation & Filters")

view_selection = st.sidebar.radio(
    "Select View",
    [
        "Daily Entry & Tracking",
        "Monthly Summary",
        "Quarterly Summary",
        "Yearly Performance Summary",
    ],
)

st.sidebar.divider()
st.sidebar.subheader("Filter Records")

# Date Filters
min_date = df["Production Date"].min().date()
max_date = df["Production Date"].max().date()

date_filter_option = st.sidebar.selectbox(
    "Filter Range", ["All Time", "Custom Date Range"]
)

if date_filter_option == "Custom Date Range":
  start_date, end_date = st.sidebar.date_input(
      "Select Date Range", [min_date, max_date]
  )
  mask = (df["Production Date"].dt.date >= start_date) & (
      df["Production Date"].dt.date <= end_date
  )
  filtered_df = df.loc[mask]
else:
  filtered_df = df.copy()

# Additional Sidebar Filters
selected_machine = st.sidebar.multiselect(
    "Machine Used",
    options=df["Machine Used"].unique(),
    default=df["Machine Used"].unique(),
)
selected_operator = st.sidebar.multiselect(
    "Operator",
    options=df["Operator Name"].unique(),
    default=df["Operator Name"].unique(),
)

if selected_machine:
  filtered_df = filtered_df[filtered_df["Machine Used"].isin(selected_machine)]
if selected_operator:
  filtered_df = filtered_df[
      filtered_df["Operator Name"].isin(selected_operator)
  ]


# ==========================================
# VIEW 1: DAILY ENTRY & TRACKING
# ==========================================
if view_selection == "Daily Entry & Tracking":
  st.subheader("📝 Daily Production Log & Data Entry")

  with st.expander(
      "➕ Add New Production Record (or Upload CSV Demo Template)", expanded=True
  ):
    col1, col2 = st.columns(2)

    with col1:
      with st.form("production_entry_form"):
        prod_date = st.date_input(
            "Production Date", value=datetime.today().date()
        )
        shift_type = st.selectbox(
            "Shift Type", ["Morning", "Afternoon", "Night"]
        )
        client = st.text_input("Client", placeholder="e.g., Opay, Polaris")
        card_type = st.text_input("Card Type", placeholder="e.g., Verve, Afrigo")
        qty_produced = st.number_input(
            "Quantity Produced", min_value=0, step=100, value=5000
        )
        machine_used = st.selectbox("Machine Used", ["MS-1", "MS-2", "PT-1", "PT-2"])
        operator_name = st.selectbox(
            "Operator Name", df["Operator Name"].unique()
        )
        supervisor_name = st.text_input("Supervisor Name", value="Vivian Iyaha")

        submit_btn = st.form_submit_button("Save Production Record")

        if submit_btn:
          new_record = pd.DataFrame([{
              "Production Date": pd.to_datetime(prod_date),
              "Shift Type": shift_type,
              "Client": client if client else "General",
              "Card Type": card_type if card_type else "Standard",
              "Quantity Produced": qty_produced,
              "Machine Used": machine_used,
              "Operator Name": operator_name,
              "Supervisor Name": supervisor_name,
          }])
          st.session_state.production_df = pd.concat(
              [st.session_state.production_df, new_record], ignore_index=True
          )
          st.success("Production record saved successfully!")
          st.rerun()

    with col2:
      st.markdown("#### 📁 CSV Data Import / Export")
      st.markdown(
          "Upload a completed CSV log file or download the template/current dataset."
      )

      # CSV Upload
      uploaded_file = st.file_uploader(
          "Upload Production CSV File", type=["csv"]
      )
      if uploaded_file is not None:
        uploaded_df = pd.read_csv(uploaded_file)
        # Ensure date format is parsed
        uploaded_df["Production Date"] = pd.to_datetime(
            uploaded_df["Production Date"]
        )
        st.session_state.production_df = pd.concat(
            [st.session_state.production_df, uploaded_df], ignore_index=True
        )
        st.success("CSV file successfully imported!")
        st.rerun()

      # CSV Download Template / Data
      csv_data = st.session_state.production_df.to_csv(index=False).encode(
          "utf-8"
      )
      st.download_button(
          label="Download Complete Production Dataset (CSV)",
          data=csv_data,
          file_name=f"cardstel_production_log_{datetime.today().strftime('%Y-%m-%d')}.csv",
          mime="text/csv",
      )

  st.divider()
  st.markdown("### 📊 Filtered Production Records")
  st.dataframe(filtered_df, use_container_width=True)


# ==========================================
# VIEWS 2, 3 & 4: SUMMARIES & ANALYTICS
# ==========================================
else:
  # Determine aggregation frequency based on view
  if view_selection == "Monthly Summary":
    st.subheader("📅 Monthly Performance Summary")
    filtered_df["Period"] = filtered_df["Production Date"].dt.to_period(
        "M"
    ).astype(str)
  elif view_selection == "Quarterly Summary":
    st.subheader("📈 Quarterly Performance Summary")
    filtered_df["Period"] = filtered_df["Production Date"].dt.to_period(
        "Q"
    ).astype(str)
  else:
    st.subheader("🏆 Yearly Performance Summary")
    filtered_df["Period"] = filtered_df["Production Date"].dt.year.astype(str)

  # KPI Summary Calculations
  total_cards = filtered_df["Quantity Produced"].sum()
  total_shifts = len(filtered_df)

  top_operator = (
      filtered_df.groupby("Operator Name")["Quantity Produced"]
      .sum()
      .idxmax()
      if not filtered_df.empty
      else "N/A"
  )

  # Target & Variance Calculation
  target_val = st.session_state.targets["Daily Target"] * total_shifts
  achievement_rate = (
      (total_cards / target_val) * 100 if target_val > 0 else 0.0
  )

  # Display KPI Cards
  kpi1, kpi2, kpi3, kpi4 = st.columns(4)
  kpi1.metric(
      label="Total Cards Produced", value=f"{total_cards:,.0f} cards"
  )
  kpi2.metric(
      label="Target Achievement Rate",
      value=f"{achievement_rate:.1f}%",
      delta=f"{achievement_rate - 100:.1f}% vs Target",
  )
  kpi3.metric(label="Total Shifts Completed", value=total_shifts)
  kpi4.metric(label="Top Performing Operator", value=top_operator)

  st.divider()

  # ==========================================
  # KPI & TARGET MANAGEMENT SECTION
  # ==========================================
  with st.expander("⚙️ Manage KPI Production Targets"):
    tcol1, tcol2, tcol3 = st.columns(3)
    with tcol1:
      st.session_state.targets["Daily Target"] = st.number_input(
          "Daily Target (Cards / Shift)",
          value=st.session_state.targets["Daily Target"],
          step=500,
      )
    with tcol2:
      st.session_state.targets["Monthly Target"] = st.number_input(
          "Monthly Target",
          value=st.session_state.targets["Monthly Target"],
          step=10000,
      )
    with tcol3:
      st.session_state.targets["Yearly Target"] = st.number_input(
          "Yearly Target",
          value=st.session_state.targets["Yearly Target"],
          step=50000,
      )

  # ==========================================
  # PLOTLY VISUALIZATIONS
  # ==========================================
  col_chart1, col_chart2 = st.columns(2)

  with col_chart1:
    st.markdown("#### Total Production by Operator")
    if not filtered_df.empty:
      op_summary = (
          filtered_df.groupby("Operator Name")["Quantity Produced"]
          .sum()
          .reset_index()
      )
      fig_op = px.bar(
          op_summary,
          x="Operator Name",
          y="Quantity Produced",
          color="Operator Name",
          text_auto=".2s",
          template="plotly_white",
      )
      st.plotly_chart(fig_op, use_container_width=True)
    else:
      st.info("No data available for selected filters.")

  with col_chart2:
    st.markdown("#### Machine Utilization & Output Breakdown")
    if not filtered_df.empty:
      machine_summary = (
          filtered_df.groupby(["Machine Used", "Shift Type"])["Quantity Produced"]
          .sum()
          .reset_index()
      )
      fig_mach = px.bar(
          machine_summary,
          x="Machine Used",
          y="Quantity Produced",
          color="Shift Type",
          barmode="group",
          template="plotly_white",
      )
      st.plotly_chart(fig_mach, use_container_width=True)
    else:
      st.info("No data available for selected filters.")

  st.markdown("#### Production Output Trend vs Target")
  if not filtered_df.empty:
    trend_df = (
        filtered_df.groupby("Period")["Quantity Produced"].sum().reset_index()
    )
    trend_df["Target Reference"] = st.session_state.targets["Daily Target"] * (
        len(filtered_df) / max(len(trend_df), 1)
    )

    fig_trend = px.line(
        trend_df,
        x="Period",
        y=["Quantity Produced", "Target Reference"],
        markers=True,
        template="plotly_white",
        labels={"value": "Quantity (Cards)", "variable": "Metric"},
    )
    st.plotly_chart(fig_trend, use_container_width=True)
  else:
    st.info("No data available for trend analysis.")

  # Export Filtered Report Button
  st.divider()
  summary_csv = filtered_df.to_csv(index=False).encode("utf-8")
  st.download_button(
      label=f"📥 Download {view_selection} Report (CSV)",
      data=summary_csv,
      file_name=f"cardstel_{view_selection.lower().replace(' ', '_')}_report.csv",
      mime="text/csv",
  )
