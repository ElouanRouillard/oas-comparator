import json
import re
import copy

from pathlib import Path
import yaml
from openapi_spec_validator import validate_spec


def load_oas_spec(file_or_path) -> dict:
    """
    Loads an OpenAPI / Swagger specification file (JSON or YAML) and parses it into a Python dictionary.

    Args:
        file_or_path (Union[str, Path, Streamlit UploadedFile, TextIO]): A file path 
            or a file-like stream object containing the specification data.

    Returns:
        dict: The parsed OpenAPI specification as a dictionary.
    """
    if hasattr(file_or_path, "name"):
        filename = file_or_path.name
    elif isinstance(file_or_path, (str, Path)):
        filename = Path(file_or_path).name
    else:
        filename = "Unknown file"

    
    if hasattr(file_or_path, "read"):
        content = file_or_path.read()
        if isinstance(content, bytes):
            content = content.decode("utf-8")
        spec_dict = yaml.safe_load(content)
    else:
        with open(file_or_path, "r", encoding="utf-8") as f:
            content = f.read()
            spec_dict = yaml.safe_load(content)

    if not isinstance(spec_dict, dict):
        raise ValueError("Le fichier fourni ne contient pas un dictionnaire valide.")

    try:
        validate_spec(spec_dict)
    except Exception as e:
        raise ValueError(f"File '{filename}' does not comply with official OpenAPI/Swagger standards.")

    return spec_dict





def extract_endpoint_count(json_obj: dict) -> int:
    """
    Extracts the total number of API routes/endpoints defined in the specification.

    Args:
        json_obj (dict): The parsed OpenAPI specification dictionary.

    Returns:
        int: Total number of paths defined under the 'paths' root key.
    """
    paths = json_obj.get("paths")
    if isinstance(paths, dict):
        return len(paths)
    return 0






def extract_metadata_coverage(json_obj: dict) -> int:
    """
    Calculates the completion percentage of key metadata fields in the specification.

    Checks for title, version, description, contact, license, termsOfService, 
    servers/host/basePath, and externalDocs.

    Args:
        json_obj (dict): The parsed OpenAPI specification dictionary.

    Returns:
        int: Percentage (0 to 100) of completed key metadata fields.
    """
    info = json_obj.get("info", {})
    if not isinstance(info, dict):
        info = {}
    fields = [
        info.get("title"),
        info.get("version"),
        info.get("description"),
        info.get("contact"),
        info.get("license"),
        info.get("termsOfService"),
        json_obj.get("servers") or json_obj.get("host") or json_obj.get("basePath"),
        json_obj.get("externalDocs"),
    ]
    present_count = sum(1 for item in fields if item)
    return round((present_count / len(fields)) * 100)






def extract_description_coverage(json_obj: dict) -> int:
    """
    Calculates the percentage of HTTP operations that include a description or summary.

    Args:
        json_obj (dict): The parsed OpenAPI specification dictionary.

    Returns:
        int: Percentage (0 to 100) of HTTP operations having a non-empty 
            description or summary.
    """
    http_methods = {"get", "post", "put", "delete", "patch", "options", "head", "trace"}
    paths = json_obj.get("paths", {})
    if not isinstance(paths, dict):
        return 0
    total_ops = ops_with_desc = 0

    for path_content in paths.values():
        if isinstance(path_content, dict):
            for method, op_content in path_content.items():
                if method.lower() in http_methods and isinstance(op_content, dict):
                    total_ops += 1
                    desc = op_content.get("description") or op_content.get("summary")
                    if desc and str(desc).strip():
                        ops_with_desc += 1

    return round((ops_with_desc / total_ops) * 100) if total_ops > 0 else 0





def extract_example_coverage(json_obj: dict) -> int:
    """
    Calculates the percentage of HTTP operations providing at least one example.

    Args:
        json_obj (dict): The parsed OpenAPI specification dictionary.

    Returns:
        int: Percentage (0 to 100) of HTTP operations containing 
            'example' or 'examples' fields.
    """
    http_methods = {"get", "post", "put", "delete", "patch", "options", "head", "trace"}
    paths = json_obj.get("paths", {})
    if not isinstance(paths, dict):
        return 0
    total_ops = ops_with_ex = 0

    for path_content in paths.values():
        if isinstance(path_content, dict):
            for method, op_content in path_content.items():
                if method.lower() in http_methods and isinstance(op_content, dict):
                    total_ops += 1
                    op_str = json.dumps(op_content).lower()
                    if '"example"' in op_str or '"examples"' in op_str:
                        ops_with_ex += 1

    return round((ops_with_ex / total_ops) * 100) if total_ops > 0 else 0





def extract_security_coverage(json_obj: dict) -> int:
    """
    Calculates the percentage of HTTP operations covered by security definitions.

    An operation is considered secure if it specifies its own 'security' field 
    or relies on global security definitions.

    Args:
        json_obj (dict): The parsed OpenAPI specification dictionary.

    Returns:
        int: Percentage (0 to 100) of secured HTTP operations.
    """

    http_methods = {"get", "post", "put", "delete", "patch", "options", "head", "trace"}
    global_security = json_obj.get("security", [])
    has_global_security = isinstance(global_security, list) and len(global_security) > 0
    paths = json_obj.get("paths", {})
    if not isinstance(paths, dict):
        return 0
    total_ops = secured_ops = 0

    for path_content in paths.values():
        if isinstance(path_content, dict):
            for method, op_content in path_content.items():
                if method.lower() in http_methods and isinstance(op_content, dict):
                    total_ops += 1
                    if (
                        "security" in op_content
                        and isinstance(op_content.get("security"), list)
                        and len(op_content.get("security")) > 0
                    ):
                        secured_ops += 1
                    elif has_global_security:
                        secured_ops += 1

    return round((secured_ops / total_ops) * 100) if total_ops > 0 else 0




def extract_metrics(json_obj: dict) -> dict:
    """
    Aggregates all qualitative and quantitative coverage metrics for a specification file.

    Args:
        json_obj (dict): The parsed OpenAPI specification dictionary.

    Returns:
        dict: A dictionary containing:
            - 'endpoint_count' (int): Total number of endpoints.
            - 'metadata_coverage' (int): Metadata completeness percentage.
            - 'description_coverage' (int): Description coverage percentage.
            - 'example_coverage' (int): Example coverage percentage.
            - 'security_coverage' (int): Security coverage percentage.
    """
    return {
        "endpoint_count": extract_endpoint_count(json_obj),
        "metadata_coverage": extract_metadata_coverage(json_obj),
        "description_coverage": extract_description_coverage(json_obj),
        "example_coverage": extract_example_coverage(json_obj),
        "security_coverage": extract_security_coverage(json_obj),
    }





def init_data_structure() -> dict:
    """
    Generates a fresh data skeleton for categorizing additions, deletions, and modifications.

    Args:
        None

    Returns:
        dict: A dictionary containing 'doc_a_only', 'doc_b_only', and 'modified' sections, 
            each initialized with 'presence', 'count', 'id', and 'values' sub-dictionaries.
    """
    template = {
        "presence": {
            "title": False,
            "termsOfService": False,
            "contact": False,
            "license": False,
            "servers": False,
            "externalDocs": False,
            "version": False,
        },
        "count": {
            "description": 0,
            "summary": 0,
            "endpoints": 0,
            "methods": 0,
            "example_tot": 0,
            "component_example": 0,
            "schemas": 0,
            "responses": 0,
            "request_body": 0,
            "parameters": 0,
            "security": 0,
            "tags": 0,
            "other": 0,
        },
        "id": {
            "description": [],
            "summary": [],
            "endpoints": [],
            "methods": [],
            "example_tot": [],
            "component_example": [],
            "schemas": [],
            "responses": [],
            "request_body": [],
            "parameters": [],
            "security": [],
            "tags": [],
            "other": [],
        },
        "values": {
            "title": None,
            "termsOfService": None,
            "contact": None,
            "license": None,
            "servers": None,
            "externalDocs": None,
            "version": None,
            "description": [],
            "summary": [],
            "endpoints": [],
            "methods": [],
            "example_tot": [],
            "component_example": [],
            "schemas": [],
            "responses": [],
            "request_body": [],
            "parameters": [],
            "security": [],
            "tags": [],
            "other": [],
        },
    }
    return {
        "doc_b_only": copy.deepcopy(template),
        "doc_a_only": copy.deepcopy(template),
        "modified": copy.deepcopy(template)
    }




def categorize_key(key: str) -> tuple[str, str]:
    """
    Maps a DeepDiff JSON path string to a section type and feature category.

    Supports both OpenAPI 3.x and Swagger 2.0 structures.

    Args:
        key (str): DeepDiff path string (e.g., "root['paths']['/pets']['get']").

    Returns:
        tuple[str, str]: A tuple where:
            - First element is section type: "presence" or "count".
            - Second element is feature name: e.g., "termsOfService", "endpoints", "schemas", etc.
    """
    HTTP_METHODS = {"get", "post", "put", "delete", "patch", "options", "head", "trace"}

    elements = re.findall(r"\[['\"](.*?)['\"]\]", key)
    match elements:
        # --- PRESENCE / METADATA ---
        case ["info", "title", *_]:
            return "presence", "title"
        case ["info", "termsOfService", *_]:
            return "presence", "termsOfService"
        case ["info", "contact", *_]:
            return "presence", "contact"
        case ["info", "license", *_]:
            return "presence", "license"
        case ["info", "version", *_]:
            return "presence", "version"
        case ["externalDocs", *_]:
            return "presence", "externalDocs"
        case ["servers", *_] | ["host", *_] | ["basePath", *_] | ["schemes", *_]:
            return "presence", "servers"

        # --- DESCRIPTION & SUMMARY ---
        case [*_, "description"]:
            return "count", "description"
        case [*_, "summary"]:
            return "count", "summary"

        # --- EXAMPLES ---
        case _ if "example" in elements or "examples" in elements:
            return "count", "example_tot"

        # --- COMPONENTS & DEFINITIONS ---
        case ["components", "schemas", *_] | ["definitions", *_]:
            return "count", "schemas"
        case ["components", "responses", *_] | ["responses", *_]:
            return "count", "responses"
        case ["components", "parameters", *_] | ["parameters", *_]:
            return "count", "parameters"
        case ["components", "requestBodies", *_]:
            return "count", "request_body"
        case ["components", "securitySchemes", *_] | ["securityDefinitions", *_]:
            return "count", "security"
        
        # --- ENDPOINTS & PATH SUB-ELEMENTS ---
        case ["paths"] | ["paths", _]:
            # Complete endpoint route added or removed (e.g., ["paths", "/pets"])
            return "count", "endpoints"

        case ["paths", _, method] if method.lower() in HTTP_METHODS:
            return "count", "methods"

        case ["paths", _, _, *sub_path]:
            # Targeted modifications within an existing HTTP method operation
            if "requestBody" in sub_path:
                return "count", "request_body"
            if "responses" in sub_path:
                return "count", "responses"
            if "parameters" in sub_path:
                return "count", "parameters"
            if "security" in sub_path:
                return "count", "security"
            if "tags" in sub_path:
                return "count", "tags"
            return "count", "methods"

        # --- GLOBAL TAGS / GLOBAL SECURITY ---
        case ["tags", *_] | [*_, "tags"]:
            return "count", "tags"
        case ["security", *_]:
            return "count", "security"

        # --- FALLBACK DEFAULT ---
        case _:
            return "count", "other"





def extract_value_by_path(json_obj: dict, deepdiff_path: str) -> any:
    """
    Navigates a nested JSON dictionary using a DeepDiff path string to retrieve the target value.

    Args:
        json_obj (dict): The target JSON specification structure.
        deepdiff_path (str): DeepDiff formatted path string (e.g., "root['info']['title']").

    Returns:
        Any: The value found at the specified path, or "Value not found" if inaccessible.
    """

    keys = re.findall(r"\[(?:['\"](.*?)['\"]|(\d+))\]", deepdiff_path)
    current = json_obj
    try:
        for text_key, index_key in keys:
            current = current[int(index_key)] if index_key else current[text_key]
        return current
    except (KeyError, IndexError, TypeError):
        return "Value not found"





def analyze_diff(diff, doc_a: dict, doc_b: dict) -> dict:
    """
    Processes raw DeepDiff results and organizes differences into a structured report.

    Args:
        diff (DeepDiff): Raw comparison object generated by DeepDiff.
        doc_a (dict): First OpenAPI specification (Document A).
        doc_b (dict): Second OpenAPI specification (Document B).

    Returns:
        dict: Structured comparison payload containing 'doc_a_only', 'doc_b_only', and 'modified' 
            categorized metrics and values.
    """

    data = init_data_structure()

    def record_item(section: str, key: str, value: dict):
        rule_type, sub_key = categorize_key(key)
        if rule_type == "presence":
            data[section]["presence"][sub_key] = True
            data[section]["values"][sub_key] = value
        else:
            data[section]["count"][sub_key] += 1
            data[section]["id"][sub_key].append(key)
            data[section]["values"][sub_key].append(value)

    # Mapping table associating DeepDiff addition/deletion keys to report sections ('doc_b_only' / 'doc_a_only') 
    # and their corresponding source JSON specifications.
    blocks_to_process = [
        ("dictionary_item_added", "doc_b_only", doc_b),
        ("iterable_item_added", "doc_b_only", doc_b),
        ("set_item_added", "doc_b_only", doc_b),
        ("dictionary_item_removed", "doc_a_only", doc_a),
        ("iterable_item_removed", "doc_a_only", doc_a),
        ("set_item_removed", "doc_a_only", doc_a),
    ]

    # --- STRUCTURAL ADDITIONS & DELETIONS ---
    for diff_key, section, source_json in blocks_to_process:
        if diff_key in diff:
            for key in diff[diff_key]:
                value = extract_value_by_path(source_json, key)
                record_item(section, key, value)

    # --- VALUE & TYPE MODIFICATIONS ---
    for diff_key in ["values_changed", "type_changes", "repetition_change"]:
        if diff_key in diff:
            for key, details in diff[diff_key].items():

                if key == "root['paths']":
                    old_paths = details.get("old_value", {})
                    new_paths = details.get("new_value", {})

                    old_routes = set(old_paths.keys()) if isinstance(old_paths, dict) else set()
                    new_routes = set(new_paths.keys()) if isinstance(new_paths, dict) else set()

                    for route in old_routes - new_routes:
                        route_key = f"root['paths']['{route}']"
                        record_item("doc_a_only", route_key, old_paths[route])

                    for route in new_routes - old_routes:
                        route_key = f"root['paths']['{route}']"
                        record_item("doc_b_only", route_key, new_paths[route])

                    for route in old_routes & new_routes:
                        if old_paths[route] != new_paths[route]:
                            route_key = f"root['paths']['{route}']"
                            modified_val = {
                                "old_value": old_paths[route],
                                "new_value": new_paths[route],
                            }
                            record_item("modified", route_key, modified_val)

                else:
                    modified_value = {
                        "old_value": details.get("old_value"),
                        "new_value": details.get("new_value"),
                    }
                    
                    if "old_type" in details:
                        modified_value["old_value"] = str(details.get("old_type"))
                        modified_value["new_value"] = str(details.get("new_type"))

                    record_item("modified", key, modified_value)

    return data




def extract_top_differences(analysis_result: dict, doc_a_name="Doc A", doc_b_name="Doc B", limit=3) -> list:
    """
    Extracts and ranks the most critical differences between two specifications based on priority.

    Priority order:
    1. Route mismatches (Exclusive endpoints in A or B)
    2. Schema divergences
    3. Metadata differences
    4. Textual modifications

    Args:
        analysis_result (dict): The structured diff payload returned by analyze_diff.
        doc_a_name (str, optional): Name or label of Document A. Defaults to "Doc A".
        doc_b_name (str, optional): Name or label of Document B. Defaults to "Doc B".
        limit (int, optional): Maximum number of top differences to return. Defaults to 3.

    Returns:
        list[dict]: List of top critical difference dictionaries containing title, target path, description, priority, and section.
    """
    candidates = []

    # =========================================================================
    # PRIORITY 1: Breaking Changes (Routes, Methods, Security, Servers)
    # =========================================================================
    for path in analysis_result.get("doc_a_only", {}).get("id", {}).get("endpoints", []):
        candidates.append({
            "title": f"Exclusive Route to {doc_a_name}",
            "target": path,
            "description": f"Route only present in {doc_a_name}.",
            "type": "error",
            "priority": 1,
            "section": "doc_a_only",
            "feature": "endpoints",
        })

    for path in analysis_result.get("doc_b_only", {}).get("id", {}).get("endpoints", []):
        candidates.append({
            "title": f"Exclusive Route to {doc_b_name}",
            "target": path,
            "description": f"Route only present in {doc_b_name}.",
            "type": "error",
            "priority": 1,
            "section": "doc_b_only",
            "feature": "endpoints",
        })

    for key_srv in ["servers", "host", "basePath", "schemes"]:
        if (analysis_result.get("modified", {}).get("presence", {}).get(key_srv)
            or analysis_result.get("doc_a_only", {}).get("presence", {}).get(key_srv)
            or analysis_result.get("doc_b_only", {}).get("presence", {}).get(key_srv)):
            candidates.append({
                "title": f"Base Server / Host Difference ({key_srv})",
                "target": f"root['{key_srv}']",
                "description": f"Target host or server configuration differs.",
                "type": "error",
                "priority": 1,
                "section": "presence",
                "feature": "servers",
            })

    for key_sec in ["security", "securitySchemes"]:
        if (analysis_result.get("modified", {}).get("presence", {}).get(key_sec)
            or analysis_result.get("doc_a_only", {}).get("presence", {}).get(key_sec)
            or analysis_result.get("doc_b_only", {}).get("presence", {}).get(key_sec)):
            candidates.append({
                "title": "Security / Auth Configuration Difference",
                "target": f"root['{key_sec}']",
                "description": f"Security schemes or requirements differ between {doc_a_name} and {doc_b_name}.",
                "type": "error",
                "priority": 1,
                "section": "presence",
                "feature": "security",
            })

    # =========================================================================
    # PRIORITY 2: Data Structure Divergences (Schemas, Parameters, Payloads)
    # =========================================================================
    P2_FEATURES = ["schemas", "parameters", "request_body", "responses"]
    for feature in P2_FEATURES:
        for path in analysis_result.get("modified", {}).get("id", {}).get(feature, []):
            candidates.append({
                "title": f"Data Model Divergence: {feature.capitalize()}",
                "target": path,
                "description": f"Structure or data type for {feature} differs between {doc_a_name} and {doc_b_name}.",
                "type": "warning",
                "priority": 2,
                "section": "modified",
                "feature": feature,
            })

    # =========================================================================
    # PRIORITY 3: Metadata & Environment Info
    # =========================================================================
    META_KEYS = ["version", "title", "contact", "termsOfService", "license", "externalDocs"]
    for key in META_KEYS:
        if (analysis_result.get("modified", {}).get("presence", {}).get(key)
            or analysis_result.get("doc_a_only", {}).get("presence", {}).get(key)
            or analysis_result.get("doc_b_only", {}).get("presence", {}).get(key)):

            target_path = f"root['info']['{key}']" if key in ["version", "title", "contact", "termsOfService", "license"] else f"root['{key}']"

            candidates.append({
                "title": f"Metadata Difference: {key}",
                "target": target_path,
                "description": f"Field '{key}' is different or missing in one of the docs.",
                "type": "info",
                "priority": 3,
                "section": "presence",
                "feature": key,
            })

    # =========================================================================
    # PRIORITY 4: Textual Modifications & Documentation
    # =========================================================================
    P1_P2_SET = set(["endpoints", "methods", "schemas", "parameters", "request_body", "responses"])
    for key_cat, paths in analysis_result.get("modified", {}).get("id", {}).items():
        if key_cat not in P1_P2_SET:
            for path in paths:
                candidates.append({
                    "title": f"Documentation Text Changed: {key_cat}",
                    "target": path,
                    "description": f"Textual content of {key_cat} differs between {doc_a_name} and {doc_b_name}.",
                    "type": "info",
                    "priority": 4,
                    "section": "modified",
                    "feature": key_cat,
                })

    candidates.sort(key=lambda x: x["priority"])
    return candidates[:limit]