"""
System Datasource Catalog API.

Provides the medical system's data field catalog for the Dify workflow
start node's enhanced data source selector.

Data sources are queried from the wisdom_diagnosis MySQL database (localhost:3387):
- Patient basic info → patient table (dynamic, read from table columns)
- Lab test indicators → indicator_dictionary table (via report_category_indicator_rel)
- ICD-10 diagnosis codes → icd10_disease table
- Chest pain inquiry → inquiry_question (western module, dynamic — all active questions)
- Report types → report_category_config table

Note: symptom_sign_config is NOT included — symptoms are captured via inquiry
questions, not as direct workflow inputs.
"""

import logging
import os
import re
import time

import pymysql
from flask_restx import Resource
from pydantic import BaseModel, Field

from controllers.console import console_ns
from controllers.console.wraps import account_initialization_required, setup_required

logger = logging.getLogger(__name__)

# Temporary debug file handler for timing diagnosis
_ds_log_path = os.path.join(os.path.dirname(__file__), 'datasource_debug.log')
_fh = logging.FileHandler(_ds_log_path, encoding='utf-8')
_fh.setFormatter(logging.Formatter('%(asctime)s %(message)s', datefmt='%H:%M:%S'))
_fh.setLevel(logging.DEBUG)
logger.addHandler(_fh)
logger.setLevel(logging.DEBUG)

# ---- Database config (wisdom_diagnosis medical DB) ----
# Connection: localhost:3387 (wisdom_diagnosis MySQL)
_WD_HOST = os.environ.get("WISDOM_DIAGNOSIS_MYSQL_HOST", "127.0.0.1")
_WD_PORT = int(os.environ.get("WISDOM_DIAGNOSIS_MYSQL_PORT", "3387"))
_WD_USER = os.environ.get("WISDOM_DIAGNOSIS_MYSQL_USER", "root")
_WD_PASSWORD = os.environ.get("WISDOM_DIAGNOSIS_MYSQL_PASSWORD", "root123")
_WD_DB = os.environ.get("WISDOM_DIAGNOSIS_MYSQL_DATABASE", "wisdom_diagnosis")


def _get_connection():
    return pymysql.connect(
        host=_WD_HOST,
        port=_WD_PORT,
        user=_WD_USER,
        password=_WD_PASSWORD,
        database=_WD_DB,
        charset="utf8mb4",
        connect_timeout=5,
        cursorclass=pymysql.cursors.DictCursor,
    )


# ---- Pydantic models ----

class DataSourceField(BaseModel):
    code: str = Field(..., description="Unique field code, e.g. 'HGB' or 'chest_pain'")
    name: str = Field(..., description="Display name in Chinese, e.g. '血红蛋白'")
    type: str = Field(..., description="Data type: number, string, boolean")
    unit: str | None = Field(default=None, description="Unit for numeric values, e.g. 'g/L'")
    options: list[str] | None = Field(default=None, description="Allowed values for select fields")


# ---- Catalog definitions: category_key → (name, query_fn) ----
# Each query_fn returns list of DataSourceField from zhongxiyi DB.

def _load_patient_basic_fields() -> list[dict]:
    """Patient basic info — dynamically read from patient table columns."""
    try:
        conn = _get_connection()
        with conn.cursor() as cur:
            cur.execute("SHOW FULL COLUMNS FROM patient")
            columns = cur.fetchall()
        conn.close()

        # Skip internal/ID columns that are not useful as workflow inputs
        _skip_cols = {"id", "created_at", "updated_at", "deleted"}

        result = []
        for col in columns:
            col_name = col["Field"]
            if col_name in _skip_cols:
                continue

            comment = col.get("Comment") or col_name
            col_type = (col.get("Type") or "").lower()

            # Determine field type and options based on DB column type
            field: dict = {"code": col_name, "name": comment, "type": "string"}

            if "int" in col_type or "decimal" in col_type or "float" in col_type or "double" in col_type:
                field["type"] = "number"
            elif "enum(" in col_type:
                # Extract enum values, e.g. enum('M','F') → ['M', 'F']
                vals = re.findall(r"'([^']*)'", col_type)
                if vals:
                    field["type"] = "string"
                    field["options"] = vals
            elif "tinyint" in col_type:
                field["type"] = "string"
                field["options"] = ["0", "1"]
            elif col_name == "gender":
                field["options"] = ["M", "F"]

            # Add unit hints for known fields
            if col_name == "age":
                field["unit"] = "岁"

            result.append(field)
        return result
    except Exception as e:
        logger.error("Failed to load patient basic fields: %s", e)
        # Fallback to minimal hardcoded list
        return [
            {"code": "age", "name": "年龄", "type": "number", "unit": "岁"},
            {"code": "gender", "name": "性别", "type": "string", "options": ["M", "F"]},
        ]


# ---- Value type mapping: indicator_dictionary.value_type → Dify frontend type ----
# Design spec: 改造方案 L166 — 检验指标配置包含「字段Code + 单位 + 值类型」
# value_type values from DB: numeric, ordinal, boolean, categorical
_VALUE_TYPE_MAP: dict[str, str] = {
    "numeric": "number",
    "ordinal": "string",
    "boolean": "boolean",
    "categorical": "string",
}


def _load_lab_indicator_fields_by_category(category_id: int, category_code: str = None) -> callable:
    """Return a loader function that fetches indicators for a specific report category."""
    def loader() -> list[dict]:
        try:
            conn = _get_connection()
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT i.indicator_code, i.indicator_name, i.unit, i.value_type "
                    "FROM report_category_indicator_rel m "
                    "JOIN indicator_dictionary i ON m.indicator_id = i.id "
                    "WHERE m.category_id = %s AND i.is_active = 1 "
                    "ORDER BY m.sort_order, i.indicator_code",
                    (category_id,),
                )
                rows = cur.fetchall()
            conn.close()
            return [
                {
                    "code": f"{category_code}_{r['indicator_code']}" if category_code else r["indicator_code"],
                    "name": r["indicator_name"],
                    "type": _VALUE_TYPE_MAP.get(r.get("value_type") or "numeric", "number"),
                    "unit": r.get("unit") or None,
                }
                for r in rows
            ]
        except Exception as e:
            logger.error("Failed to load indicators for category %d: %s", category_id, e)
            return []
    return loader


def _load_icd10_fields() -> list[dict]:
    """ICD-10 diagnosis codes from icd10_disease table (leaf entries by level)."""
    try:
        conn = _get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT icd_code, disease_name FROM icd10_disease "
                "WHERE is_active=1 AND level = (SELECT MAX(level) FROM icd10_disease WHERE is_active=1) "
                "ORDER BY chapter, icd_code"
            )
            rows = cur.fetchall()
        conn.close()
        return [
            {
                "code": r["icd_code"],
                "name": r["disease_name"],
                "type": "boolean",
            }
            for r in rows
        ]
    except Exception as e:
        logger.error("Failed to load ICD-10 codes: %s", e)
        return []


def _load_inquiry_fields(module: str, catalog_name: str) -> callable:
    """Return a loader function that fetches inquiry questions for a specific module."""
    def loader() -> list[dict]:
        """Inquiry questions — dynamically load all active questions for the given module."""
        try:
            conn = _get_connection()
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, question_code, question_title, question_type "
                    "FROM inquiry_question "
                    "WHERE inquiry_module=%s AND is_active=1 "
                    "ORDER BY sort_order, id",
                    (module,),
                )
                questions = cur.fetchall()

                if questions:
                    q_ids = [q["id"] for q in questions]
                    ph = ",".join(["%s"] * len(q_ids))
                    cur.execute(
                        f"SELECT question_id, option_label, option_value "
                        f"FROM inquiry_question_option "
                        f"WHERE question_id IN ({ph}) ORDER BY question_id, sort_order",
                        q_ids,
                    )
                    all_options = cur.fetchall()
                else:
                    all_options = []
            conn.close()

            opt_map: dict[int, list[str]] = {}
            for opt in all_options:
                opt_map.setdefault(opt["question_id"], []).append(opt["option_label"])

            result = []
            for q in questions:
                # Use question_code if available, fallback to id
                code = q.get("question_code") or str(q["id"])
                field: dict = {
                    "code": f"q_{code}",
                    "name": q["question_title"],
                    "type": "string" if q["question_type"] == "single_choice" else "list",
                }
                opts = opt_map.get(q["id"])
                if opts:
                    field["options"] = opts
                result.append(field)
            return result
        except Exception as e:
            logger.error("Failed to load %s inquiry fields: %s", module, e)
            return []
    return loader


def _load_report_type_fields() -> list[dict]:
    """Report types from report_category_config table."""
    try:
        conn = _get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT category_name, category_code FROM report_category_config "
                "WHERE is_active=1 ORDER BY sort_order, category_name"
            )
            rows = cur.fetchall()
        conn.close()
        return [
            {
                "code": f"report_{r.get('category_code') or r['category_name']}",
                "name": r["category_name"],
                "type": "boolean",
            }
            for r in rows
        ]
    except Exception as e:
        logger.error("Failed to load report types: %s", e)
        return []


def _load_clinical_param_fields() -> list[dict]:
    """Clinical parameters from encounter_clinical_param table (e.g. PTP)."""
    try:
        conn = _get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT param_key, param_type "
                "FROM encounter_clinical_param "
                "ORDER BY param_key"
            )
            rows = cur.fetchall()
        conn.close()
        return [
            {
                "code": r["param_key"],
                "name": r["param_key"].upper(),
                "type": "number" if r.get("param_type") == "decimal" else "string",
            }
            for r in rows
        ]
    except Exception as e:
        logger.error("Failed to load clinical params: %s", e)
        return []


# ---- Build catalog definitions (static + dynamic report categories) ----

# TTL cache for catalog definitions to avoid rebuilding on every request
_CATALOG_CACHE_TTL = 60  # seconds
_catalog_cache: dict = {"ts": 0.0, "defs": None, "meta": None}


def _get_catalog_definitions() -> tuple[list[tuple[str, str, object, str | None]], dict[str, tuple[str, object]]]:
    """Get the current catalog definitions with TTL cache.

    Static categories are always present. Dynamic report categories are loaded
    from DB on each cache refresh to handle late-available MySQL connections.

    Returns:
        (definitions_list, meta_dict)
    """
    now = time.time()
    if _catalog_cache["defs"] is not None and (now - _catalog_cache["ts"]) < _CATALOG_CACHE_TTL:
        return _catalog_cache["defs"], _catalog_cache["meta"]

    defs, meta = _build_catalog_definitions()
    _catalog_cache["ts"] = now
    _catalog_cache["defs"] = defs
    _catalog_cache["meta"] = meta
    return defs, meta


def _build_catalog_definitions() -> tuple[list[tuple[str, str, object, str | None]], dict[str, tuple[str, object]]]:
    """Build the full catalog: static categories + dynamic report-type categories from DB.

    Returns:
        (definitions_list, meta_dict)
        Each definition is a 4-tuple: (key, name, loader, category_code).
        category_code is None for static categories.
    """
    # Static categories (always present)
    # Note: symptom_sign_config is NOT a workflow input — symptoms are captured
    # via inquiry questions (chest_pain etc.), so it's excluded from the catalog.
    static_defs: list[tuple[str, str, object, str | None]] = [
        ("patient_basic", "病人基本信息", _load_patient_basic_fields, None),
        ("western_inquiry", "西医问诊", _load_inquiry_fields("western", "西医问诊"), None),
        ("tcm_inquiry", "中医问诊", _load_inquiry_fields("tcm", "中医问诊"), None),
        ("clinical_params", "临床参数", _load_clinical_param_fields, None),
        ("icd10", "ICD-10 诊断编码", _load_icd10_fields, None),
        ("exam_results", "检查报告类型", _load_report_type_fields, None),
    ]

    # Dynamic categories: report types with indicator mappings from DB
    dynamic_defs: list[tuple[str, str, object, str | None]] = []
    try:
        conn = _get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT rc.id, rc.category_name, rc.category_code "
                "FROM report_category_config rc "
                "WHERE rc.is_active = 1 "
                "AND EXISTS (SELECT 1 FROM report_category_indicator_rel m "
                "            WHERE m.category_id = rc.id) "
                "ORDER BY rc.sort_order"
            )
            categories = cur.fetchall()
        conn.close()
        for cat in categories:
            key = f"report_cat_{cat['id']}"
            name = cat["category_name"]
            code = cat.get("category_code")
            loader = _load_lab_indicator_fields_by_category(cat["id"], category_code=code)
            dynamic_defs.append((key, name, loader, code))
        logger.info("[datasource] Loaded %d dynamic report categories from DB", len(dynamic_defs))
    except Exception as e:
        logger.error("[datasource] Failed to load dynamic report categories: %s", e)

    all_defs = static_defs + dynamic_defs
    meta = {key: (name, loader) for key, name, loader, _code in all_defs}
    return all_defs, meta


def _resolve_fields(loader_or_list: object) -> list[dict]:
    """Call loader function or return static list."""
    if callable(loader_or_list):
        return loader_or_list()  # type: ignore[operator]
    if isinstance(loader_or_list, list):
        return loader_or_list  # type: ignore[return-value]
    return []


# ---- API routes ----

@console_ns.route("/system/datasource/catalog")
class DataSourceCatalogApi(Resource):
    """GET /console/api/system/datasource/catalog — return all categories with field count."""

    @setup_required
    @account_initialization_required
    def get(self):
        t0 = time.perf_counter()
        catalog_definitions, _ = _get_catalog_definitions()
        catalog = []
        for key, name, loader, cat_code in catalog_definitions:
            t1 = time.perf_counter()
            fields = _resolve_fields(loader)
            dt = (time.perf_counter() - t1) * 1000
            logger.info("[datasource] catalog loader '%s' (%s): %d fields, %.1f ms", key, name, len(fields), dt)
            catalog.append({
                "key": key,
                "name": name,
                "code": cat_code,
                "field_count": len(fields),
            })
        total = (time.perf_counter() - t0) * 1000
        logger.info("[datasource] catalog TOTAL: %.1f ms (%d categories)", total, len(catalog))
        return {"categories": catalog}


@console_ns.route("/system/datasource/<string:category_key>/fields")
class DataSourceFieldsApi(Resource):
    """GET /console/api/system/datasource/{category}/fields — return fields in a category."""

    @setup_required
    @account_initialization_required
    def get(self, category_key: str):
        t0 = time.perf_counter()
        _, catalog_meta = _get_catalog_definitions()
        entry = catalog_meta.get(category_key)
        if not entry:
            return {"error": f"Category '{category_key}' not found"}, 404
        name, loader = entry
        fields = _resolve_fields(loader)
        total = (time.perf_counter() - t0) * 1000
        logger.info("[datasource] fields '%s' (%s): %d fields, %.1f ms", category_key, name, len(fields), total)
        return {"category": name, "fields": fields}
