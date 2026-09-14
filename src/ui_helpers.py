FEATURES_LIST = [
    "termsOfService",
    "contact",
    "license",
    "servers",
    "externalDocs",
    "version",
    "description",
    "summary",
    "endpoints",
    "methods",
    "example_tot",
    "component_example",
    "schemas",
    "responses",
    "request_body",
    "parameters",
    "security",
    "tags",
    "other",
]

CONFIG_PRESENCE = [
    "title",
    "termsOfService",
    "contact",
    "license",
    "servers",
    "externalDocs",
    "version",
]


def extract_data_and_ids(data_json: dict) -> list:
    """
    Extracts and formats added and deleted elements for the Streamlit detailed view table.

    Iterates over predefined features, evaluates whether each feature is measured by boolean 
    presence or element count, and pulls values/IDs from the 'doc_a_only' and 'doc_b_only' diff sections.

    Args:
        data_json (dict): The structured OpenAPI comparison JSON payload containing 
            'doc_a_only', 'doc_b_only', and 'modified' sections.

    Returns:
        list[dict]: A list of dictionaries containing for each active feature:
            - 'feature' (str): Feature key name.
            - 'type' (str): "presence" or "count".
            - 'val_a' (Union[bool, int]): Document A presence/count value (deletions).
            - 'ids_a' (list): Target JSON path IDs deleted from Document A.
            - 'val_b' (Union[bool, int]): Document B presence/count value (additions).
            - 'ids_b' (list): Target JSON path IDs added in Document B.
    """
    result = []
    for feature in FEATURES_LIST:
        is_presence = feature in CONFIG_PRESENCE
        section_type = "presence" if is_presence else "count"

        val_a = (data_json.get("doc_a_only", {}).get(section_type, {}).get(feature, 0 if section_type == "count" else False))
        ids_a = data_json.get("doc_a_only", {}).get("id", {}).get(feature, [])

        val_b = ( data_json.get("doc_b_only", {}).get(section_type, {}).get(feature, 0 if section_type == "count" else False))
        ids_b = data_json.get("doc_b_only", {}).get("id", {}).get(feature, [])

        if val_a in (0, [], "", False) and val_b in (0, [], "", False):
            continue

        result.append({
            "feature": feature,
            "type": section_type,
            "val_a": val_a,
            "ids_a": ids_a,
            "val_b": val_b,
            "ids_b": ids_b,
        })
    return result




def extract_modifications(data_json: dict) -> list:
    """
        Extracts and formats modified elements for the Streamlit detailed view table.
    
        Iterates over predefined features to collect modified elements and their associated 
        JSON paths from the 'modified' diff section.
    
        Args:
            data_json (dict): The structured OpenAPI comparison JSON payload.
    
        Returns:
            list[dict]: A list of dictionaries containing for each modified feature:
                - 'feature' (str): Feature key name.
                - 'type' (str): "presence" or "count".
                - 'val_mod' (Union[bool, int]): Presence flag or modification count.
                - 'ids_mod' (list): Target JSON path IDs modified between specifications.
        """
    result = []
    modified_section = data_json.get("modified", {})

    for feature in FEATURES_LIST:
        is_presence = feature in CONFIG_PRESENCE
        section_type = "presence" if is_presence else "count"

        val_mod = modified_section.get(section_type, {}).get( feature, 0 if section_type == "count" else False)
        ids_mod = modified_section.get("id", {}).get(feature, [])

        if val_mod in (0, [], "", False):
            continue

        result.append({
            "feature": feature,
            "type": section_type,
            "val_mod": val_mod,
            "ids_mod": ids_mod,
        })
    return result


def extract_unique_value(section_dict: dict, category: str, category_type: str, element_index: int = 0, key_path: str = "") -> any:
    """
    Retrieves a specific value or diff payload to display inside the inspection pop-up modal.

    Handles resolution across presence metadata, indexed list items, and direct key path references.

    Args:
        section_dict (dict): Target dictionary section containing extracted values (e.g., 'new.values').
        category (str): Feature category name (e.g., "termsOfService", "endpoint", "schemas").
        category_type (str): Category type designation ("presence" or "count").
        element_index (int, optional): List index when inspecting array items. Defaults to 0.
        key_path (str, optional): DeepDiff JSON path string used as fallback dict key. Defaults to "".

    Returns:
        Any: The extracted value payload (dict, list, or scalar), or "Value not found" if missing.
    """

    if not isinstance(section_dict, dict):
        return "Value not found"
    
    category_content = section_dict.get(category)

    if category_type == "presence" and category_content is not None:
        return category_content

    if isinstance(category_content, list) and 0 <= element_index < len(category_content):
        return category_content[element_index]

    if isinstance(category_content, dict) and key_path in category_content:
        return category_content[key_path]

    if key_path in section_dict:
        return section_dict[key_path]

    return "Value not found"