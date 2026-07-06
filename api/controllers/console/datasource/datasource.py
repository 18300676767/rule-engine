"""
System Datasource Catalog API.

Provides the medical system's data field catalog for the Dify workflow
start node's enhanced data source selector.

Data sources are queried from the zhongxiyi medical database (zhongxiyi-mysql container):
- Patient basic info → patient table
- Lab test indicators → indicator_dictionary table
- Symptoms → symptom_sign_config table
- ICD-10 diagnosis codes → icd10_disease table
- Medical history → inquiry_question (western module, id 10-18)
- Chest pain inquiry → inquiry_question (western module, id 1-9)
- Report types → report_category_config table
"""

import logging
import os
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

# ---- Database config (zhongxiyi medical DB) ----
# Connection from host: localhost:3306 (Docker port mapping, zhongxiyi-mysql container)
# Connection from Docker container: host.docker.internal:3306
_ZHONGXIYI_HOST = os.environ.get("ZHONGXIYI_MYSQL_HOST", "127.0.0.1")
_ZHONGXIYI_PORT = int(os.environ.get("ZHONGXIYI_MYSQL_PORT", "3306"))
_ZHONGXIYI_USER = os.environ.get("ZHONGXIYI_MYSQL_USER", "root")
_ZHONGXIYI_PASSWORD = os.environ.get("ZHONGXIYI_MYSQL_PASSWORD", "root123456")
_ZHONGXIYI_DB = os.environ.get("ZHONGXIYI_MYSQL_DATABASE", "zhongxiyi")


def _get_connection():
    return pymysql.connect(
        host=_ZHONGXIYI_HOST,
        port=_ZHONGXIYI_PORT,
        user=_ZHONGXIYI_USER,
        password=_ZHONGXIYI_PASSWORD,
        database=_ZHONGXIYI_DB,
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
    """Patient basic info: age, gender from patient table."""
    return [
        {"code": "age", "name": "年龄", "type": "number", "unit": "岁"},
        {"code": "gender", "name": "性别", "type": "string", "options": ["男", "女"]},
        {"code": "allergy_history", "name": "过敏史", "type": "string"},
        {"code": "medical_history", "name": "既往病史", "type": "string"},
    ]


def _load_lab_indicator_fields_by_category(category_id: int) -> callable:
    """Return a loader function that fetches indicators for a specific report category."""
    def loader() -> list[dict]:
        try:
            conn = _get_connection()
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT i.indicator_code, i.indicator_name, i.unit "
                    "FROM report_category_indicator_mapping m "
                    "JOIN indicator_dictionary i ON m.indicator_code = i.indicator_code "
                    "WHERE m.report_category_id = %s AND i.is_active = 1 "
                    "ORDER BY m.sort_order, i.indicator_code",
                    (category_id,),
                )
                rows = cur.fetchall()
            conn.close()
            return [
                {
                    "code": r["indicator_code"],
                    "name": r["indicator_name"],
                    "type": "number",
                    "unit": r.get("unit") or None,
                }
                for r in rows
            ]
        except Exception as e:
            logger.error("Failed to load indicators for category %d: %s", category_id, e)
            return []
    return loader


def _load_symptom_fields() -> list[dict]:
    """Symptoms from symptom_sign_config table."""
    try:
        conn = _get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT symptom_code, symptom_name "
                "FROM symptom_sign_config WHERE is_active=1 "
                "ORDER BY sort_order, symptom_code"
            )
            rows = cur.fetchall()
        conn.close()
        return [
            {
                "code": r["symptom_code"],
                "name": r["symptom_name"],
                "type": "boolean",
            }
            for r in rows
        ]
    except Exception as e:
        logger.error("Failed to load symptoms: %s", e)
        return []


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


def _load_western_inquiry_fields(module: str, question_ids: list[int]) -> list[dict]:
    """Load inquiry fields dynamically from inquiry_question + inquiry_question_option.

    Args:
        module: The inquiry_module value, e.g. 'western'.
        question_ids: Ordered list of question IDs for this category.
    """
    try:
        conn = _get_connection()
        with conn.cursor() as cur:
            placeholders = ",".join(["%s"] * len(question_ids))
            cur.execute(
                f"SELECT id, question_title, question_type "
                f"FROM inquiry_question "
                f"WHERE inquiry_module=%s AND id IN ({placeholders}) AND is_active=1 "
                f"ORDER BY FIELD(id, {placeholders})",
                [module] + question_ids + question_ids,
            )
            questions = cur.fetchall()

            # Batch-load options for all questions
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

        # Group options by question_id
        opt_map: dict[int, list[str]] = {}
        for opt in all_options:
            opt_map.setdefault(opt["question_id"], []).append(opt["option_label"])

        result = []
        for q in questions:
            field: dict = {
                "code": f"q_{q['id']}",
                "name": q["question_title"],
                "type": "string" if q["question_type"] == "single_choice" else "list",
            }
            opts = opt_map.get(q["id"])
            if opts:
                field["options"] = opts
            result.append(field)
        return result
    except Exception as e:
        logger.error("Failed to load western inquiry fields (module=%s): %s", module, e)
        return []


def _load_medical_history_fields() -> list[dict]:
    """Medical history / risk factors from inquiry_question (western module, id 10-18)."""
    return _load_western_inquiry_fields("western", [10, 11, 12, 13, 14, 15, 16, 17, 18])


def _load_chest_pain_fields() -> list[dict]:
    """Chest pain inquiry fields from inquiry_question (western module, id 1-9)."""
    return _load_western_inquiry_fields("western", [1, 2, 3, 4, 5, 6, 7, 8, 9])


def _load_report_type_fields() -> list[dict]:
    """Report types from report_category_config table."""
    try:
        conn = _get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT category_name FROM report_category_config "
                "WHERE is_active=1 ORDER BY sort_order, category_name"
            )
            rows = cur.fetchall()
        conn.close()
        return [
            {
                "code": f"report_{r['category_name']}",
                "name": r["category_name"],
                "type": "boolean",
            }
            for r in rows
        ]
    except Exception as e:
        logger.error("Failed to load report types: %s", e)
        return []


# ---- Build catalog definitions (static + dynamic report categories) ----

def _build_catalog_definitions() -> tuple[list[tuple[str, str, object]], dict[str, tuple[str, object]]]:
    """Build the full catalog: static categories + dynamic report-type categories from DB.

    Returns:
        (definitions_list, meta_dict)
    """
    # Static categories (always present)
    static_defs: list[tuple[str, str, object]] = [
        ("patient_basic", "病人基本信息", _load_patient_basic_fields),
        ("symptoms", "症状", _load_symptom_fields),
        ("medical_history", "病史与危险因素", _load_medical_history_fields),
        ("chest_pain", "胸痛问诊", _load_chest_pain_fields),
        ("icd10", "ICD-10 诊断编码", _load_icd10_fields),
        ("exam_results", "检查报告类型", _load_report_type_fields),
    ]

    # Dynamic categories: report types with indicator mappings from DB
    dynamic_defs: list[tuple[str, str, object]] = []
    try:
        conn = _get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT rc.id, rc.category_name "
                "FROM report_category_config rc "
                "WHERE rc.is_active = 1 "
                "AND EXISTS (SELECT 1 FROM report_category_indicator_mapping m "
                "            WHERE m.report_category_id = rc.id) "
                "ORDER BY rc.sort_order"
            )
            categories = cur.fetchall()
        conn.close()
        for cat in categories:
            key = f"report_cat_{cat['id']}"
            name = cat["category_name"]
            loader = _load_lab_indicator_fields_by_category(cat["id"])
            dynamic_defs.append((key, name, loader))
        logger.info("[datasource] Loaded %d dynamic report categories from DB", len(dynamic_defs))
    except Exception as e:
        logger.error("[datasource] Failed to load dynamic report categories: %s", e)

    all_defs = static_defs + dynamic_defs
    meta = {key: (name, loader) for key, name, loader in all_defs}
    return all_defs, meta


_CATALOG_DEFINITIONS, _CATALOG_META = _build_catalog_definitions()


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
        catalog = []
        for key, name, loader in _CATALOG_DEFINITIONS:
            t1 = time.perf_counter()
            fields = _resolve_fields(loader)
            dt = (time.perf_counter() - t1) * 1000
            logger.info("[datasource] catalog loader '%s' (%s): %d fields, %.1f ms", key, name, len(fields), dt)
            catalog.append({
                "key": key,
                "name": name,
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
        entry = _CATALOG_META.get(category_key)
        if not entry:
            return {"error": f"Category '{category_key}' not found"}, 404
        name, loader = entry
        fields = _resolve_fields(loader)
        total = (time.perf_counter() - t0) * 1000
        logger.info("[datasource] fields '%s' (%s): %d fields, %.1f ms", category_key, name, len(fields), total)
        return {"category": name, "fields": fields}
