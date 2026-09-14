import json
import sys
from pathlib import Path

import streamlit as st
import yaml
from deepdiff import DeepDiff

from src.analyzer import analyze_diff, extract_metrics, extract_top_differences, load_oas_spec
from src.ui_helpers import (
    CONFIG_PRESENCE,
    extract_data_and_ids,
    extract_modifications,
    extract_unique_value,
)



CONFIG_PATH = Path("config.yaml")
CACHE_FILE = ".cache/temp_data.json"

if CONFIG_PATH.exists():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
            CACHE_FILE = cfg.get("cache_file", CACHE_FILE)
    except Exception:
        pass

DATA_FILE = CACHE_FILE




st.set_page_config(layout="wide")
st.markdown("<style>.block-container { padding-top: 1.5rem; padding-bottom: 1rem; }</style>",unsafe_allow_html=True)

st.title("OAS Documentation Comparator")

is_server_mode = "--server-mode" in sys.argv
is_cli_mode = "--cli-mode" in sys.argv

# =========================================================================
# SESSION STATE INITIALIZATION
# =========================================================================
if "data_json" not in st.session_state:
    st.session_state.data_json = None
    st.session_state.info_dashboard = None
    st.session_state.doc_a_name = "Documentation A"
    st.session_state.doc_b_name = "Documentation B"

if is_cli_mode and Path(DATA_FILE).exists() and st.session_state.data_json is None:
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            payload = json.load(f)
        st.session_state.data_json = payload.get("data_json")
        st.session_state.info_dashboard = payload.get("info_dashboard")
        st.session_state.doc_a_name = payload.get("doc_a_name", "Documentation A")
        st.session_state.doc_b_name = payload.get("doc_b_name", "Documentation B")
    except Exception as e:
        st.warning(f"Error loading analysis file: {e}")


@st.dialog("🔍 Value Inspection", width="large")
def open_value_popup(json_path, value_info):
    name_a = st.session_state.get("doc_a_name", "Documentation A")
    name_b = st.session_state.get("doc_b_name", "Documentation B")

    st.write("**Inspected Path:**")
    st.code(json_path, language="json")
    st.markdown("---")

    if callable(value_info) or isinstance(value_info, Exception) or value_info is None:
        value_info = "Value not found"

    if isinstance(value_info, dict) and ("old_value" in value_info or "new_value" in value_info):
        col_old, col_new = st.columns(2)
        with col_old:
            st.warning(f"**Value from {name_a}:**")
            old_val = value_info.get("old_value")
            if isinstance(old_val, (dict, list)):
                st.json(old_val)
            else:
                st.code(str(old_val) if old_val is not None else "Absent", language="text")
        with col_new:
            st.success(f"**Value from {name_b}:**")
            new_val = value_info.get("new_value")
            if isinstance(new_val, (dict, list)):
                st.json(new_val)
            else:
                st.code(str(new_val) if new_val is not None else "Absent", language="text")
    else:
        st.info("**Value Content:**")
        if isinstance(value_info, (dict, list)):
            st.json(value_info)
        else:
            st.code(str(value_info), language="text")

    if st.button("Close", use_container_width=True):
        st.rerun()


TABS = ["Upload Files", "Executive Dashboard", "Detailed Comparison"]

if is_cli_mode and st.session_state.data_json is not None:
    default_tab = "Executive Dashboard"
else:
    default_tab = "Upload Files"

tab_upload, tab_dashboard, tab_details = st.tabs(TABS, default=default_tab)

# =========================================================================
# TAB 1: FILE UPLOAD (IN-MEMORY)
# =========================================================================
with tab_upload:
    st.subheader("Load OpenAPI / Swagger JSON / YAML files")
    st.caption("Upload two documentation files directly from your browser to execute in-memory analysis (server mode).")

    col_up1, col_up2 = st.columns(2)
    with col_up1:
        file_a = st.file_uploader(
            "Documentation A (JSON or YAML)",
            type=["json", "yaml", "yml"],
            key="uploader_doc_a",
        )
    with col_up2:
        file_b = st.file_uploader(
            "Documentation B (JSON or YAML)",
            type=["json", "yaml", "yml"],
            key="uploader_doc_b",
        )

    if file_a and file_b:
        if st.button("Run in-memory analysis", type="primary", use_container_width=True):
            try:
                doc_a = load_oas_spec(file_a)
                doc_b = load_oas_spec(file_b)

                raw_diff = DeepDiff(doc_a, doc_b, ignore_order=True)
                data_analyzed = analyze_diff(raw_diff, doc_a, doc_b)

                st.session_state.data_json = data_analyzed
                st.session_state.doc_a_name = file_a.name
                st.session_state.doc_b_name = file_b.name
                st.session_state.info_dashboard = {
                    "doc_a_metrics": extract_metrics(doc_a),
                    "doc_b_metrics": extract_metrics(doc_b),
                    "top_3": extract_top_differences(data_analyzed, doc_a_name=file_a.name, doc_b_name=file_b.name, limit=3),
                }

                st.success("Analysis completed successfully! Check the Dashboard and Detailed Comparison tabs.")
            except Exception as e:
                st.error(f"Error processing files: {e}")
    else:
        st.info("Please select two files (JSON or YAML) to start.")

if st.session_state.data_json is None:
    with tab_dashboard:
        st.warning("Please upload 2 files in the 'Upload Files' tab first.")
    with tab_details:
        st.warning("Please upload 2 files in the 'Upload Files' tab first.")
    st.stop()

data_json = st.session_state.data_json
info_dashboard = st.session_state.info_dashboard or {}
doc_a_name = st.session_state.doc_a_name
doc_b_name = st.session_state.doc_b_name

added_rows = extract_data_and_ids(data_json)
modified_rows = extract_modifications(data_json)
doc_b_values = data_json.get("doc_b_only", {}).get("values", {})
doc_a_values = data_json.get("doc_a_only", {}).get("values", {})
updated_values = data_json.get("modified", {}).get("values", {})

# =========================================================================
# TAB 2: EXECUTIVE DASHBOARD
# =========================================================================
with tab_dashboard:
    st.subheader("Documentation Statistics")
    d_a = info_dashboard.get("doc_a_metrics", {})
    d_b = info_dashboard.get("doc_b_metrics", {})

    delta_ep = d_b.get("endpoint_count", 0) - d_a.get("endpoint_count", 0)
    delta_desc = d_b.get("description_coverage", 0) - d_a.get("description_coverage", 0)
    delta_ex = d_b.get("example_coverage", 0) - d_a.get("example_coverage", 0)
    delta_meta = d_b.get("metadata_coverage", 0) - d_a.get("metadata_coverage", 0)
    delta_sec = d_b.get("security_coverage", 0) - d_a.get("security_coverage", 0)

    col_doc_a, col_doc_b = st.columns(2)
    with col_doc_a:
        with st.container(border=True):
            st.markdown(f"### {doc_a_name}")
            m1, m2, m3 = st.columns(3)
            m1.metric(label="Endpoints", value=f"{d_a.get('endpoint_count', 0)}")
            m2.metric(label="Desc. Coverage",value=f"{d_a.get('description_coverage', 0)}%")
            m3.metric(label="Example Coverage", value=f"{d_a.get('example_coverage', 0)}%")
            st.write(" ")
            m4, m5 = st.columns(2)
            m4.metric(label="Metadata", value=f"{d_a.get('metadata_coverage', 0)}%")
            m5.metric(label="Security Rate", value=f"{d_a.get('security_coverage', 0)}%")

    with col_doc_b:
        with st.container(border=True):
            st.markdown(f"### {doc_b_name}")
            m1, m2, m3 = st.columns(3)
            m1.metric(label="Endpoints",value=f"{d_b.get('endpoint_count', 0)}",delta=f"{delta_ep:+d}")
            m2.metric(label="Desc. Coverage",value=f"{d_b.get('description_coverage', 0)}%",delta=f"{delta_desc:+d}%")
            m3.metric(label="Example Coverage",value=f"{d_b.get('example_coverage', 0)}%",delta=f"{delta_ex:+d}%")
            st.write(" ")
            m4, m5 = st.columns(2)
            m4.metric(label="Metadata",value=f"{d_b.get('metadata_coverage', 0)}%",delta=f"{delta_meta:+d}%")
            m5.metric(label="Security Rate",value=f"{d_b.get('security_coverage', 0)}%",delta=f"{delta_sec:+d}%")

    top_3 = info_dashboard.get("top_3", [])
    if top_3:
        st.subheader("Top Critical Differences")
        cols = st.columns(len(top_3))
        for idx, (col, diff) in enumerate(zip(cols, top_3)):
            with col:
                with st.container(border=True):
                    st.markdown(f"**{idx + 1}. {diff['title']}**")
                    if diff["type"] == "error":
                        st.error(diff["target"])
                    elif diff["type"] == "warning":
                        st.warning(diff["target"])
                    else:
                        st.info(diff["target"])
                    st.caption(diff["description"])

                    if st.button("Inspect value",key=f"btn_dash_top_{idx}",use_container_width=True,):
                        category_type = (
                            "presence"
                            if diff["feature"] in CONFIG_PRESENCE
                            else "count"
                        )
                        if diff["section"] == "doc_a_only" or (diff["section"] == "presence" and doc_a_values.get(diff["feature"]) is not None):
                            target_dict = doc_a_values
                        elif diff["section"] == "doc_b_only" or (diff["section"] == "presence" and doc_b_values.get(diff["feature"]) is not None):
                            target_dict = doc_b_values
                        else:
                            target_dict = updated_values

                        key_path_arg = None if category_type == "presence" else diff["target"]
                        
                        targeted_val = extract_unique_value(
                            target_dict,
                            diff["feature"],
                            category_type,
                            key_path=diff["target"],
                        )
                        open_value_popup(diff["target"], targeted_val)

# =========================================================================
# TAB 3: DETAILED COMPARISON
# =========================================================================
with tab_details:
    st.subheader("Added Elements")
    st.markdown("---")
    header_cols = st.columns([2, 5, 5])
    header_cols[0].markdown("**Features**")
    header_cols[1].markdown(f"**{doc_a_name}**")
    header_cols[2].markdown(f"**{doc_b_name}**")
    st.markdown("---")

    for index, row in enumerate(added_rows):
        row_cols = st.columns([2, 5, 5])
        row_cols[0].write(f"**{row['feature'].capitalize()}**")
        key_state_a, key_state_b = f"show_A_{index}", f"show_B_{index}"
        if key_state_a not in st.session_state:
            st.session_state[key_state_a] = False
        if key_state_b not in st.session_state:
            st.session_state[key_state_b] = False

        with row_cols[1]:
            col_a1, col_a2 = st.columns([1, 4])
            col_a1.write("✅"if row["val_a"] is True else ("❌" if row["val_a"] is False else str(row["val_a"])))
            if row["type"] == "presence" and row["val_a"]:
                if col_a2.button("🔍 View value", key=f"btn_pres_A_{index}"):
                    targeted_val = extract_unique_value(doc_a_values, row["feature"], "presence")
                    open_value_popup(f"root['info']['{row['feature']}']", targeted_val)
            if row["ids_a"]:
                if col_a2.button("🔍 Details", key=f"btn_A_{index}"):
                    st.session_state[key_state_a] = not st.session_state[key_state_a]
                if st.session_state[key_state_a]:
                    for sub_idx, item in enumerate(row["ids_a"]):
                        if st.button(f" {item}",key=f"ln_A_{index}_{sub_idx}",use_container_width=True):
                            targeted_val = extract_unique_value(doc_a_values,row["feature"],"count",sub_idx,item)
                            open_value_popup(item, targeted_val)

        with row_cols[2]:
            col_b1, col_b2 = st.columns([1, 4])
            col_b1.write(
                "✅"if row["val_b"] is True else ("❌" if row["val_b"] is False else str(row["val_b"])))
            if row["type"] == "presence" and row["val_b"]:
                if col_b2.button("🔍 View value", key=f"btn_pres_B_{index}"):
                    targeted_val = extract_unique_value(doc_b_values, row["feature"], "presence")
                    open_value_popup(f"root['info']['{row['feature']}']", targeted_val)
            if row["ids_b"]:
                if col_b2.button("🔍 Details", key=f"btn_B_{index}"):
                    st.session_state[key_state_b] = not st.session_state[key_state_b]
                if st.session_state[key_state_b]:
                    for sub_idx, item in enumerate(row["ids_b"]):
                        if st.button(f" {item}",key=f"ln_B_{index}_{sub_idx}",use_container_width=True):
                            targeted_val = extract_unique_value(doc_b_values,row["feature"],"count",sub_idx,item)
                            open_value_popup(item, targeted_val)
        st.markdown("---")

    st.subheader("Modified Elements")
    st.markdown("---")
    if modified_rows:
        for index, row in enumerate(modified_rows):
            row_cols2 = st.columns([3, 9])
            row_cols2[0].write(f"**{row['feature'].capitalize()}**")
            key_state_mod = f"show_mod_{index}"
            if key_state_mod not in st.session_state:
                st.session_state[key_state_mod] = False

            with row_cols2[1]:
                col_m1, col_m2 = st.columns([1, 8])
                col_m1.write("✅" if row["val_mod"] is True else ("❌" if row["val_mod"] is False else str(row["val_mod"])))
                if row["type"] == "presence" and row["val_mod"]:
                    if col_m2.button("🔍 View changes", key=f"btn_pres_mod_{index}"):
                        targeted_val = extract_unique_value(updated_values, row["feature"], "presence")
                        open_value_popup(f"root['info']['{row['feature']}']", targeted_val)
                if row["ids_mod"]:
                    if col_m2.button("🔍 Change details", key=f"btn_mod_{index}"):
                        st.session_state[key_state_mod] = (not st.session_state[key_state_mod])
                if st.session_state[key_state_mod]:
                    for sub_idx, item in enumerate(row["ids_mod"]):
                        if st.button(f" {item}",key=f"ln_mod_{index}_{sub_idx}",use_container_width=True,):
                            targeted_val = extract_unique_value(updated_values,row["feature"],"count",sub_idx,item)
                            open_value_popup(item, targeted_val)
            st.markdown("---")