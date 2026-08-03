#!/usr/bin/env python3
"""Deterministic Tableau workbook (.twb/.twbx) metadata extractor.

Parses a Tableau workbook XML and emits a single comprehensive JSON document
plus two backward-compatible markdown files (tableau-analysis-output.md and
tableau-visuals-output.md). The JSON is the deterministic source of truth that
every downstream migration agent consumes.

Design goals:
- Cover EVERY documented scenario (datasources, columns, calculated fields,
  parameters, worksheets + visual encodings, dashboards + zone layout,
  navigation/toggle buttons, relationships/joins, sets, groups, bins,
  data blending, field formatting, row-level security).
- Zero third-party dependencies (Python 3.8+ standard library only).
- Never fabricate: absent categories are emitted as empty lists / None.

Usage:
    python tableau_extractor.py <workbook.twb | Data-subfolder | Data/>
        [--out-dir DIR] [--name NAME] [--no-markdown] [--stdout] [--quiet]

If <input> is a directory, every .twb/.twbx found underneath is processed.
By default, artifacts are written to .specify/memory/<SuggestedName>/.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

EXTRACTOR_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"

# ---------------------------------------------------------------------------
# Lookup tables
# ---------------------------------------------------------------------------

# Tableau connection class -> friendly source type + Power BI M query pattern.
CONNECTION_TYPES = {
    "textscan": ("CSV", "Csv.Document(File.Contents(...))"),
    "textclean": ("CSV", "Csv.Document(File.Contents(...))"),
    "excel-direct": ("Excel", "Excel.Workbook(File.Contents(...))"),
    "excel": ("Excel", "Excel.Workbook(File.Contents(...))"),
    "sqlserver": ("SQL Server", "Sql.Database(server, database)"),
    "postgres": ("PostgreSQL", "PostgreSQL.Database(server, database)"),
    "mysql": ("MySQL", "MySQL.Database(server, database)"),
    "oracle": ("Oracle", "Oracle.Database(server)"),
    "snowflake": ("Snowflake", "Snowflake.Databases(server, warehouse)"),
    "databricks": ("Databricks", "Databricks.Catalogs(...)"),
    "bigquery": ("BigQuery", "GoogleBigQuery.Database()"),
    "redshift": ("Amazon Redshift", "AmazonRedshift.Database(server, database)"),
    "hadoophive": ("Hive", "Odbc.DataSource(...)"),
    "spark": ("Spark SQL", "Odbc.DataSource(...)"),
    "google-sheets": ("Google Sheets", "GoogleSheets.Contents(...)"),
    "msaccess": ("Access", "Access.Database(File.Contents(...))"),
}

# Aggregation / date-part prefix codes found in Tableau field-instance pills.
AGG_CODES = {
    "none": None, "sum": "Sum", "cnt": "Count", "ctd": "CountD",
    "avg": "Average", "min": "Min", "max": "Max", "med": "Median",
    "stdev": "StdDev", "stdevp": "StdDevP", "var": "Variance", "varp": "VarianceP",
    "usr": "User", "pcto": "PercentOfTotal", "attr": "Attribute", "agg": "Aggregate",
}
DATE_PART_CODES = {
    "yr": "Year", "qr": "Quarter", "mn": "Month", "wk": "Week", "dy": "Day",
    "hr": "Hour", "mi": "Minute", "sc": "Second", "mdy": "ExactDate", "md": "MonthDay",
    "tyr": "TruncYear", "tqr": "TruncQuarter", "tmn": "TruncMonth",
    "twk": "TruncWeek", "tdy": "TruncDay", "thr": "TruncHour",
}

# Tableau mark class -> Power BI visual type (canonical mapping).
MARK_TO_VISUAL = {
    "bar": "clusteredColumnChart",
    "line": "lineChart",
    "area": "areaChart",
    "pie": "pieChart",
    "square": "treemap",
    "circle": "scatterChart",
    "shape": "scatterChart",
    "text": "tableEx",
    "gantt": "ganttChart",
    "polygon": "shape",
    "map": "filledMap",
    "multipolygon": "filledMap",
    "filledmap": "filledMap",
    "automatic": None,  # inferred
}

USER_FUNCTION_RE = re.compile(
    r"\b(USERNAME|FULLNAME|ISMEMBEROF|ISUSERNAME|ISFULLNAME)\s*\(", re.IGNORECASE
)
USER_COLUMN_RE = re.compile(r"(?i)\b(user\s*name|username|user_id|userid|email|upn|login|user)\b")
ENTITY_DECODE = {"&quot;": '"', "&gt;": ">", "&lt;": "<", "&amp;": "&"}


# ---------------------------------------------------------------------------
# XML helpers (namespace-agnostic)
# ---------------------------------------------------------------------------

def localname(tag: str) -> str:
    """Strip an XML namespace from a tag or attribute key."""
    return tag.split("}", 1)[1] if "}" in tag else tag


def attr(elem, name: str, default=None):
    """Get an attribute by local name, ignoring any XML namespace prefix."""
    if elem is None:
        return default
    val = elem.get(name)
    if val is not None:
        return val
    for key, value in elem.attrib.items():
        if localname(key) == name:
            return value
    return default


def find_local(elem, name: str):
    """Find the first direct child with the given local tag name."""
    if elem is None:
        return None
    for child in elem:
        if localname(child.tag) == name:
            return child
    return None


def findall_local(elem, name: str):
    """Find all direct children with the given local tag name."""
    if elem is None:
        return []
    return [c for c in elem if localname(c.tag) == name]


def iter_local(elem, name: str):
    """Recursively find all descendants with the given local tag name."""
    if elem is None:
        return []
    return [d for d in elem.iter() if localname(d.tag) == name]


def clean(text):
    """Trim text; return None for empty/whitespace."""
    if text is None:
        return None
    t = text.strip()
    return t or None


def strip_brackets(name):
    """Remove the outermost [ ] wrapper from a Tableau identifier."""
    if name is None:
        return None
    n = name.strip()
    if n.startswith("[") and n.endswith("]"):
        return n[1:-1]
    return n


# ---------------------------------------------------------------------------
# Field-instance pill parsing  e.g. [federated.x].[sum:Sales:qk]
# ---------------------------------------------------------------------------

PILL_RE = re.compile(r"\[(?P<ds>[^\]]+)\]\.\[(?P<inner>.+)\]$")


def parse_pill(raw):
    """Parse a single Tableau field reference pill into structured parts."""
    if not raw:
        return None
    raw = raw.strip()
    if raw.startswith("(") and raw.endswith(")"):
        raw = raw[1:-1].strip()
    m = PILL_RE.match(raw)
    if not m:
        return {"raw": raw, "datasource": None, "aggregation": None,
                "date_part": None, "field": strip_brackets(raw), "is_generated": False}
    ds = m.group("ds")
    inner = m.group("inner")
    aggregation = None
    date_part = None
    field = inner
    parts = inner.split(":")
    if len(parts) >= 3:
        prefix = parts[0]
        code = parts[-1]
        middle = ":".join(parts[1:-1])
        if prefix in AGG_CODES:
            aggregation = AGG_CODES[prefix]
            field = middle
        elif prefix in DATE_PART_CODES:
            date_part = DATE_PART_CODES[prefix]
            field = middle
        else:
            field = inner
        _ = code  # nk/qk/ok type code — not needed downstream
    is_generated = "(generated)" in field.lower()
    return {
        "raw": raw,
        "datasource": ds,
        "aggregation": aggregation,
        "date_part": date_part,
        "field": strip_brackets(field),
        "is_generated": is_generated,
    }


def parse_shelf(text):
    """Parse a <rows>/<cols> shelf string into an ordered list of pills."""
    text = clean(text)
    if not text:
        return []
    # Hierarchies/joins are separated by ' / '; parentheses only group them.
    # Split on ' / ' (spaced slash) so field names may safely contain '/'.
    tokens = [t.strip() for t in text.split(" / ") if t.strip()]
    pills = []
    for tok in tokens:
        # Strip grouping parens that wrap pills (they sit outside the [...] ids).
        tok = tok.lstrip("(").rstrip(")").strip()
        if tok:
            pills.append(parse_pill(tok))
    return pills


# ---------------------------------------------------------------------------
# Format-string translation
# ---------------------------------------------------------------------------

def classify_format(fmt):
    """Classify a Tableau format string as Currency/Percent/Date/Number."""
    if not fmt:
        return None
    f = fmt.lower()
    if "%" in f:
        return "Percent"
    if "$" in fmt or "\u20ac" in fmt or "\u00a3" in fmt or "\u20b9" in fmt:
        return "Currency"
    if any(tok in f for tok in ("yyyy", "mmm", "mm/dd", "dd/mm", "hh:mm", "[h]")):
        return "Date/Time"
    if any(ch.isdigit() or ch in "#0.," for ch in fmt):
        return "Number"
    return "Custom"


def tableau_format_to_powerbi(fmt):
    """Best-effort translation of a Tableau format string to a Power BI formatString."""
    if not fmt:
        return None
    # Strip Tableau's leading affinity markers (n, p, *) that are not part of the mask.
    body = fmt
    if body[:1] in ("n", "p") and len(body) > 1 and body[1] in "\"#0*.,-":
        body = body[1:]
    body = body.replace("*", "")
    body = body.replace('"$"', "\\$").replace("$", "\\$")
    return body or fmt


# ---------------------------------------------------------------------------
# Extractor
# ---------------------------------------------------------------------------

class TableauExtractor:
    def __init__(self, twb_bytes: bytes, source_path: Path):
        self.source_path = source_path
        self.root = ET.fromstring(twb_bytes)
        self.warnings = []
        # Global field name -> caption map (resolved across datasources).
        self.field_caption = {}
        # object-id -> physical table name (from metadata-records).
        self.window_uuid_to_dashboard = {}

    # -- top level -------------------------------------------------------
    def extract(self) -> dict:
        wb = {
            "version": attr(self.root, "version"),
            "original_version": attr(self.root, "original-version"),
            "source_build": attr(self.root, "source-build"),
            "source_platform": attr(self.root, "source-platform"),
        }
        self._index_windows()
        datasources = self._extract_datasources()
        parameters = self._extract_parameters()
        worksheets = self._extract_worksheets()
        dashboards = self._extract_dashboards()
        relationships = self._extract_relationships(datasources)
        sets_all = [s for ds in datasources for s in ds["sets"]]
        groups_all = [g for ds in datasources for g in ds["groups"]]
        bins_all = [b for ds in datasources for b in ds["bins"]]
        blending = self._detect_blending(datasources, worksheets)
        formatting = self._collect_field_formatting(datasources, parameters)
        rls = self._detect_rls(datasources)

        calc_fields = [c for ds in datasources for c in ds["columns"] if c["is_calculated"]]
        dimensions = [c for ds in datasources for c in ds["columns"]
                      if c["role"] == "dimension" and not c["is_calculated"]]
        measures = [c for ds in datasources for c in ds["columns"]
                    if c["role"] == "measure" and not c["is_calculated"]]

        connection_types = sorted({ct for ds in datasources for ct in ds["connection_types"]})

        return {
            "schema_version": SCHEMA_VERSION,
            "extractor_version": EXTRACTOR_VERSION,
            "source_file": str(self.source_path).replace("\\", "/"),
            "workbook_name": self.source_path.stem,
            "data_subfolder": self.source_path.parent.name,
            "suggested_output_folder_name": pascal_case(self.source_path.parent.name),
            "workbook": wb,
            "parameters": parameters,
            "datasources": datasources,
            "fields": {
                "dimensions": dimensions,
                "measures": measures,
                "calculated_fields": calc_fields,
            },
            "worksheets": worksheets,
            "dashboards": dashboards,
            "windows": [
                {"class": c, "name": n, "uuid": u}
                for (u, (c, n)) in sorted(self._all_windows.items())
            ],
            "relationships": relationships,
            "sets": sets_all,
            "groups": groups_all,
            "bins": bins_all,
            "data_blending": blending,
            "field_formatting": formatting,
            "row_level_security": rls,
            "summary": {
                "datasource_count": len([d for d in datasources if not d["is_parameters"]]),
                "worksheet_count": len(worksheets),
                "dashboard_count": len(dashboards),
                "parameter_count": len(parameters),
                "calculated_field_count": len(calc_fields),
                "dimension_count": len(dimensions),
                "measure_count": len(measures),
                "set_count": len(sets_all),
                "group_count": len(groups_all),
                "bin_count": len(bins_all),
                "connection_types": connection_types,
                "rls_detected": rls["detected"],
            },
            "warnings": self.warnings,
        }

    # -- windows ---------------------------------------------------------
    def _index_windows(self):
        self._all_windows = {}
        windows = find_local(self.root, "windows")
        for win in findall_local(windows, "window"):
            wclass = attr(win, "class")
            wname = attr(win, "name")
            sid = find_local(win, "simple-id")
            uuid = attr(sid, "uuid") if sid is not None else None
            if uuid:
                self._all_windows[uuid] = (wclass, wname)
                if wclass == "dashboard":
                    self.window_uuid_to_dashboard[uuid] = wname

    # -- parameters ------------------------------------------------------
    def _extract_parameters(self):
        params = []
        datasources = find_local(self.root, "datasources")
        for ds in findall_local(datasources, "datasource"):
            if attr(ds, "name") != "Parameters":
                continue
            for col in findall_local(ds, "column"):
                calc = find_local(col, "calculation")
                rng = find_local(col, "range")
                members_el = find_local(col, "members")
                aliases_el = find_local(col, "aliases")
                members = [{"value": attr(m, "value")}
                           for m in findall_local(members_el, "member")] if members_el is not None else []
                aliases = [{"key": attr(a, "key"), "value": attr(a, "value")}
                           for a in findall_local(aliases_el, "alias")] if aliases_el is not None else []
                params.append({
                    "name": attr(col, "name"),
                    "caption": attr(col, "caption") or strip_brackets(attr(col, "name")),
                    "datatype": attr(col, "datatype"),
                    "role": attr(col, "role"),
                    "type": attr(col, "type"),
                    "domain_type": attr(col, "param-domain-type"),
                    "default_value": attr(col, "value"),
                    "default_formula": attr(calc, "formula") if calc is not None else None,
                    "format": attr(col, "default-format"),
                    "range": ({"min": attr(rng, "min"), "max": attr(rng, "max"),
                               "granularity": attr(rng, "granularity")} if rng is not None else None),
                    "members": members,
                    "aliases": aliases,
                    "powerbi_mapping": self._param_mapping(attr(col, "param-domain-type"),
                                                           attr(col, "datatype")),
                })
        return params

    @staticmethod
    def _param_mapping(domain_type, datatype):
        if domain_type == "range":
            return "What-If parameter (GENERATESERIES disconnected table)"
        if domain_type == "list":
            return "Field parameter or disconnected slicer table"
        if datatype in ("date", "datetime"):
            return "Date slicer on DimDate"
        return "Disconnected slicer / What-If parameter"

    # -- datasources -----------------------------------------------------
    def _extract_datasources(self):
        result = []
        datasources = find_local(self.root, "datasources")
        for ds in findall_local(datasources, "datasource"):
            name = attr(ds, "name")
            is_params = name == "Parameters"
            if is_params:
                continue
            connection = find_local(ds, "connection")
            conns, physical_tables, rel_type, joins = self._parse_connection(connection)
            objects_map, obj_rels = self._parse_object_graph(ds)
            for pt in physical_tables:
                cap = objects_map.get(pt["name"], {}).get("caption")
                if cap:
                    pt["caption"] = cap
            meta_map = self._parse_metadata_records(connection)
            columns, column_instances = self._parse_fields(ds, meta_map)
            sets_, groups_, bins_ = self._parse_groups_and_bins(ds)
            conn_types = sorted({c["connection_type"] for c in conns if c["connection_type"]})
            result.append({
                "name": name,
                "caption": attr(ds, "caption") or strip_brackets(name),
                "is_parameters": False,
                "connections": conns,
                "connection_types": conn_types,
                "m_query_patterns": sorted({c["m_query_pattern"] for c in conns if c["m_query_pattern"]}),
                "relations_type": rel_type,
                "physical_tables": physical_tables,
                "joins": joins,
                "object_relationships": obj_rels,
                "columns": columns,
                "column_instances": column_instances,
                "sets": sets_,
                "groups": groups_,
                "bins": bins_,
            })
        return result

    def _parse_connection(self, connection):
        conns, physical_tables, joins = [], [], []
        rel_type = None
        if connection is None:
            return conns, physical_tables, rel_type, joins
        named = find_local(connection, "named-connections")
        for nc in findall_local(named, "named-connection"):
            inner = find_local(nc, "connection")
            cclass = attr(inner, "class") if inner is not None else None
            friendly, mquery = CONNECTION_TYPES.get(cclass, (None, "Odbc.DataSource(...)"))
            conns.append({
                "caption": attr(nc, "caption"),
                "class": cclass,
                "connection_type": friendly or (cclass.upper() if cclass else "Unknown"),
                "m_query_pattern": mquery,
                "filename": attr(inner, "filename"),
                "directory": attr(inner, "directory"),
                "server": attr(inner, "server"),
                "dbname": attr(inner, "dbname"),
                "schema": attr(inner, "schema"),
                "csv_file": attr(inner, "csvFile"),
            })
        # Physical tables + join structure.
        for rel in iter_local(connection, "relation"):
            rtype = attr(rel, "type")
            if rtype in ("collection", "join") and rel_type is None:
                rel_type = rtype
            if rtype == "table":
                # Skip extract-context duplicate relations ([Extract].[...]).
                if (attr(rel, "table") or "").startswith("[Extract]"):
                    continue
                cols_el = find_local(rel, "columns")
                cols = [{"name": attr(c, "name"), "datatype": attr(c, "datatype"),
                         "ordinal": _to_int(attr(c, "ordinal"))}
                        for c in findall_local(cols_el, "column")] if cols_el is not None else []
                tbl_name = attr(rel, "name")
                if tbl_name and not any(t["name"] == tbl_name for t in physical_tables):
                    physical_tables.append({
                        "name": tbl_name,
                        "caption": None,
                        "table": attr(rel, "table"),
                        "columns": cols,
                    })
            if rtype == "join":
                clauses = []
                for clause in iter_local(rel, "clause"):
                    expr = find_local(clause, "expression")
                    clauses.append({"op": attr(expr, "op") if expr is not None else None,
                                    "raw": _expression_text(expr)})
                joins.append({
                    "join_type": attr(rel, "join") or "inner",
                    "left": _relation_side(rel, 0),
                    "right": _relation_side(rel, 1),
                    "clauses": clauses,
                })
        if rel_type is None and physical_tables:
            rel_type = "table"
        return conns, physical_tables, rel_type, joins

    def _parse_object_graph(self, ds):
        """Parse the modern object-model <objects> + <relationships> graph."""
        objects_map, relationships = {}, []
        graph = None
        for og in iter_local(ds, "object-graph"):
            graph = og
            break
        if graph is None:
            return objects_map, relationships
        objects_el = find_local(graph, "objects")
        for obj in findall_local(objects_el, "object"):
            oid = attr(obj, "id")
            caption = attr(obj, "caption")
            table_name = None
            for props in findall_local(obj, "properties"):
                if (attr(props, "context") or "") == "":
                    rel = find_local(props, "relation")
                    if rel is not None:
                        table_name = attr(rel, "name")
                    break
            objects_map[table_name or oid] = {"caption": caption, "table": table_name, "id": oid}
            objects_map[oid] = {"caption": caption, "table": table_name, "id": oid}
        rels_el = find_local(graph, "relationships")
        for rel in findall_local(rels_el, "relationship"):
            expr = find_local(rel, "expression")
            op = attr(expr, "op")
            col_exprs = findall_local(expr, "expression")
            left_col = strip_brackets(attr(col_exprs[0], "op")) if len(col_exprs) > 0 else None
            right_col = strip_brackets(attr(col_exprs[1], "op")) if len(col_exprs) > 1 else None
            fep = find_local(rel, "first-end-point")
            sep = find_local(rel, "second-end-point")
            left_obj = objects_map.get(attr(fep, "object-id"), {}) if fep is not None else {}
            right_obj = objects_map.get(attr(sep, "object-id"), {}) if sep is not None else {}
            relationships.append({
                "left_table": left_obj.get("caption") or left_obj.get("table"),
                "left_column": _strip_disambiguation(left_col),
                "right_table": right_obj.get("caption") or right_obj.get("table"),
                "right_column": _strip_disambiguation(right_col),
                "operator": op or "=",
            })
        return objects_map, relationships

    def _parse_metadata_records(self, connection):
        """Map local field name -> physical parent table via metadata-records."""
        mapping = {}
        if connection is None:
            return mapping
        records = find_local(connection, "metadata-records")
        for rec in findall_local(records, "metadata-record"):
            if attr(rec, "class") != "column":
                continue
            local = clean(_child_text(rec, "local-name"))
            parent = clean(_child_text(rec, "parent-name"))
            ltype = clean(_child_text(rec, "local-type"))
            agg = clean(_child_text(rec, "aggregation"))
            if local:
                mapping[local] = {
                    "physical_table": strip_brackets(parent) if parent else None,
                    "local_type": ltype,
                    "default_aggregation": agg,
                }
        return mapping

    def _parse_fields(self, ds, meta_map):
        columns, instances = [], []
        for col in findall_local(ds, "column"):
            name = attr(col, "name")
            # Skip internal object-id table columns.
            if name and "__tableau_internal_object_id__" in name:
                continue
            calc = find_local(col, "calculation")
            is_calc = calc is not None
            caption = attr(col, "caption") or strip_brackets(name)
            if name:
                self.field_caption[name] = caption
            meta = meta_map.get(name, {})
            table_calc = None
            if is_calc:
                tc = find_local(calc, "table-calc")
                if tc is not None:
                    table_calc = {"ordering_type": attr(tc, "ordering-type"),
                                  "ordering_field": attr(tc, "ordering-field")}
            fmt = attr(col, "default-format")
            columns.append({
                "name": name,
                "caption": caption,
                "datatype": attr(col, "datatype"),
                "role": attr(col, "role"),
                "type": attr(col, "type"),
                "semantic_role": attr(col, "semantic-role"),
                "data_category": _semantic_to_category(attr(col, "semantic-role")),
                "aggregation": attr(col, "aggregation") or meta.get("default_aggregation"),
                "format": fmt,
                "powerbi_format": tableau_format_to_powerbi(fmt),
                "format_kind": classify_format(fmt),
                "hidden": attr(col, "hidden") == "true",
                "physical_table": meta.get("physical_table"),
                "is_calculated": is_calc,
                "calculation": ({"class": attr(calc, "class"),
                                 "formula": _decode(attr(calc, "formula")),
                                 "table_calc": table_calc} if is_calc else None),
            })
        for inst in findall_local(ds, "column-instance"):
            instances.append({
                "name": attr(inst, "name"),
                "column": attr(inst, "column"),
                "derivation": attr(inst, "derivation"),
                "type": attr(inst, "type"),
                "pivot": attr(inst, "pivot"),
            })
        return columns, instances

    def _parse_groups_and_bins(self, ds):
        sets_, groups_, bins_ = [], [], []
        for grp in findall_local(ds, "group"):
            # Exclude auto-generated dashboard-action groups.
            if attr(grp, "auto-column") == "sheet_link":
                continue
            gname = strip_brackets(attr(grp, "name")) or ""
            members, source_field, is_computed = self._parse_groupfilter(grp)
            record = {
                "name": attr(grp, "caption") or gname,
                "source_field": source_field,
                "members": members,
                "computed": is_computed,
            }
            if gname.endswith(" Set") or gname.endswith("Set") or is_computed:
                record["type"] = "Computed" if is_computed else "Fixed"
                sets_.append(record)
            else:
                groups_.append(record)
        # Bins: columns carrying a <calculation class='bin'>.
        for col in findall_local(ds, "column"):
            calc = find_local(col, "calculation")
            if calc is not None and attr(calc, "class") == "bin":
                bins_.append({
                    "name": attr(col, "caption") or strip_brackets(attr(col, "name")),
                    "source_field": strip_brackets(attr(calc, "column")
                                                   or attr(calc, "decimal-bin-base")),
                    "bin_size": attr(calc, "decimal-bin-size") or attr(calc, "bin-size"),
                })
        return sets_, groups_, bins_

    def _parse_groupfilter(self, grp):
        members, source_field, is_computed = [], None, False
        for gf in iter_local(grp, "groupfilter"):
            fn = attr(gf, "function")
            level = strip_brackets(attr(gf, "level"))
            if level and source_field is None:
                source_field = level
            if fn == "member":
                members.append(_decode(attr(gf, "member")))
            elif fn in ("filter", "top", "end"):
                is_computed = True
        return members, source_field, is_computed

    # -- worksheets ------------------------------------------------------
    def _extract_worksheets(self):
        worksheets = []
        ws_container = find_local(self.root, "worksheets")
        for ws in findall_local(ws_container, "worksheet"):
            worksheets.append(self._extract_one_worksheet(ws))
        return worksheets

    def _extract_one_worksheet(self, ws):
        name = attr(ws, "name")
        table = find_local(ws, "table")
        view = find_local(table, "view")
        title = self._extract_title(find_local(ws, "layout-options"))

        # Datasource in view.
        ds_ref = None
        view_ds = find_local(view, "datasources")
        first_ds = find_local(view_ds, "datasource")
        if first_ds is not None:
            ds_ref = attr(first_ds, "name")

        # Panes / marks / encodings.
        panes_el = find_local(table, "panes")
        panes = findall_local(panes_el, "pane")
        marks, encodings_all = [], {}
        for pane in panes:
            mark_el = find_local(pane, "mark")
            if mark_el is not None:
                marks.append(attr(mark_el, "class"))
            enc = find_local(pane, "encodings")
            for child in (enc if enc is not None else []):
                col = attr(child, "column")
                if col:
                    encodings_all.setdefault(localname(child.tag), col)
        primary_mark = marks[0] if marks else None
        distinct_marks = [m for m in dict.fromkeys(marks) if m]

        rows = parse_shelf(_child_text(table, "rows"))
        cols = parse_shelf(_child_text(table, "cols"))

        encodings = {k: self._resolve_field_ref(v) for k, v in encodings_all.items()}
        inferred = self._infer_visual(primary_mark, rows, cols, encodings, distinct_marks)

        filters = self._extract_worksheet_filters(view)
        deps = self._extract_dependencies(view)
        top_n = self._extract_top_n(view)
        dual_axis = self._detect_dual_axis(rows, cols, distinct_marks)
        ref_lines = self._extract_reference_lines(table)
        style = self._extract_worksheet_style(table)
        color_encoding = self._extract_color_encoding(table)
        hierarchy = self._hierarchy_from_shelf(rows) or self._hierarchy_from_shelf(cols)

        return {
            "name": name,
            "title": title,
            "datasource": ds_ref,
            "mark_type": primary_mark,
            "all_marks": distinct_marks,
            "inferred_powerbi_visual": inferred,
            "rows": rows,
            "cols": cols,
            "hierarchy": hierarchy,
            "encodings": {
                "color": encodings.get("color"),
                "size": encodings.get("size"),
                "text": encodings.get("text"),
                "label": encodings.get("text"),
                "wedge_size": encodings.get("wedge-size"),
                "detail": encodings.get("detail"),
                "lod": encodings.get("lod"),
                "shape": encodings.get("shape"),
                "geometry": encodings.get("geometry"),
                "angle": encodings.get("angle"),
                "path": encodings.get("path"),
            },
            "filters": filters,
            "top_n": top_n,
            "dual_axis": dual_axis,
            "reference_lines": ref_lines,
            "referenced_fields": deps["fields"],
            "referenced_calculations": deps["calculations"],
            "color_encoding": color_encoding,
            "style": style,
        }

    def _extract_title(self, layout_options):
        title_el = find_local(layout_options, "title")
        ft = find_local(title_el, "formatted-text")
        run = find_local(ft, "run")
        if run is None:
            return None
        return {
            "text": clean(run.text),
            "font": attr(run, "fontname"),
            "size": attr(run, "fontsize"),
            "color": attr(run, "fontcolor"),
            "bold": attr(run, "bold") == "true",
            "align": attr(run, "fontalignment"),
        }

    def _resolve_field_ref(self, ref):
        pill = parse_pill(ref)
        if not pill:
            return ref
        caption = self.field_caption.get(f"[{pill['field']}]") if pill["field"] else None
        pill["caption"] = caption or pill["field"]
        return pill

    def _infer_visual(self, mark, rows, cols, encodings, distinct_marks):
        if len(distinct_marks) > 1:
            marks_lower = {m.lower() for m in distinct_marks}
            if "bar" in marks_lower and "line" in marks_lower:
                return "lineClusteredColumnComboChart"
        if not mark:
            return None
        m = mark.lower()
        mapped = MARK_TO_VISUAL.get(m)
        if mapped:
            return mapped
        if m == "automatic":
            return self._infer_automatic(rows, cols, encodings)
        return None

    @staticmethod
    def _infer_automatic(rows, cols, encodings):
        has_color = bool(encodings.get("color"))
        has_size = bool(encodings.get("size"))
        has_text = bool(encodings.get("text"))
        dims = [p for p in rows + cols if p and p.get("aggregation") is None and not p.get("is_generated")]
        measures = [p for p in rows + cols if p and p.get("aggregation")]
        if has_color and has_size:
            return "treemap"
        date_axis = any(p.get("date_part") for p in cols)
        if date_axis and measures:
            return "lineChart"
        if not dims and len(measures) <= 1 and not rows and not cols:
            return "card"
        if not measures and len(dims) == 1 and has_text:
            return "card"
        row_dims = [p for p in rows if p and p.get("aggregation") is None]
        col_dims = [p for p in cols if p and p.get("aggregation") is None]
        if row_dims and col_dims and has_text:
            return "pivotTable"
        if has_text and (row_dims or col_dims):
            return "tableEx"
        if dims and measures:
            # Dimension on rows -> horizontal bars; on cols -> vertical columns.
            if any(p.get("aggregation") is None for p in rows):
                return "clusteredBarChart"
            return "clusteredColumnChart"
        return "tableEx"

    def _extract_worksheet_filters(self, view):
        filters = []
        for filt in findall_local(view, "filter"):
            column = attr(filt, "column")
            pill = self._resolve_field_ref(column)
            field = pill.get("field") if isinstance(pill, dict) else None
            is_action = bool(column and "Action (" in column)
            members, kind = [], None
            top_n = None
            for gf in iter_local(filt, "groupfilter"):
                fn = attr(gf, "function")
                if attr(gf, "ui-action-filter"):
                    is_action = True
                if fn == "member":
                    members.append(_decode(attr(gf, "member")))
                    kind = "include_members"
                elif fn == "level-members" and kind is None:
                    kind = "all_members"
                elif fn == "except":
                    kind = "exclude_members"
                elif fn in ("end", "top"):
                    top_n = {"count": _to_int(attr(gf, "count")),
                             "direction": attr(gf, "end") or "top",
                             "by_field": attr(gf, "ui-top-by-field") == "true"}
            filters.append({
                "class": attr(filt, "class"),
                "column": column,
                "field": field,
                "kind": kind,
                "members": members,
                "top_n": top_n,
                "is_action_filter": is_action,
                "range": self._filter_range(filt),
            })
        return filters

    @staticmethod
    def _filter_range(filt):
        mn = attr(filt, "min")
        mx = attr(filt, "max")
        if mn is None and mx is None:
            return None
        return {"min": mn, "max": mx}

    def _extract_dependencies(self, view):
        fields, calcs = [], []
        deps = find_local(view, "datasource-dependencies")
        for col in findall_local(deps, "column"):
            calc = find_local(col, "calculation")
            nm = attr(col, "name")
            if nm:
                fields.append(strip_brackets(nm))
            if calc is not None:
                calcs.append({
                    "name": nm,
                    "caption": attr(col, "caption"),
                    "formula": _decode(attr(calc, "formula")),
                })
        return {"fields": fields, "calculations": calcs}

    @staticmethod
    def _extract_top_n(view):
        for filt in findall_local(view, "filter"):
            for gf in iter_local(filt, "groupfilter"):
                if attr(gf, "function") in ("end", "top") and attr(gf, "count"):
                    return {
                        "count": _to_int(attr(gf, "count")),
                        "direction": attr(gf, "end") or "top",
                        "by_field": attr(gf, "ui-top-by-field") == "true",
                    }
        return None

    @staticmethod
    def _detect_dual_axis(rows, cols, distinct_marks):
        measures_rows = [p for p in rows if p and p.get("aggregation")]
        measures_cols = [p for p in cols if p and p.get("aggregation")]
        multi = len(measures_rows) > 1 or len(measures_cols) > 1
        if not multi and len(distinct_marks) <= 1:
            return None
        return {
            "detected": True,
            "marks": distinct_marks,
            "measures": [p["field"] for p in (measures_rows + measures_cols) if p.get("field")],
        }

    @staticmethod
    def _extract_reference_lines(table):
        lines = []
        for rl in iter_local(table, "reference-line"):
            lines.append({
                "type": attr(rl, "class") or "constant",
                "value": attr(rl, "value"),
                "aggregation": attr(rl, "reference-type") or attr(rl, "aggregation"),
                "scope": attr(rl, "scope"),
                "label": attr(rl, "label"),
            })
        for tl in iter_local(table, "trend-lines"):
            lines.append({"type": "trend", "model": attr(tl, "model")})
        return lines

    @staticmethod
    def _extract_worksheet_style(table):
        style = {}
        style_el = find_local(table, "style")
        for rule in findall_local(style_el, "style-rule"):
            element = attr(rule, "element")
            for fmt in findall_local(rule, "format"):
                a = attr(fmt, "attr")
                v = attr(fmt, "value")
                if a and v and element:
                    style[f"{element}.{a}"] = v
        return style

    def _extract_color_encoding(self, table):
        style_el = find_local(table, "style")
        for rule in findall_local(style_el, "style-rule"):
            if attr(rule, "element") != "mark":
                continue
            enc = find_local(rule, "encoding")
            if enc is not None and attr(enc, "attr") == "color":
                palette = {}
                for mp in findall_local(enc, "map"):
                    to = attr(mp, "to")
                    bucket = find_local(mp, "bucket")
                    key = clean(bucket.text) if bucket is not None else None
                    if to:
                        palette[key or to] = to
                return {
                    "field": self._resolve_field_ref(attr(enc, "field")),
                    "palette": attr(enc, "palette"),
                    "type": attr(enc, "type"),
                    "colors": palette,
                }
        return None

    @staticmethod
    def _hierarchy_from_shelf(shelf):
        dims = [p["field"] for p in shelf if p and p.get("aggregation") is None
                and not p.get("is_generated") and p.get("field")]
        return dims if len(dims) > 1 else None

    # -- dashboards ------------------------------------------------------
    def _extract_dashboards(self):
        dashboards = []
        container = find_local(self.root, "dashboards")
        for dash in findall_local(container, "dashboard"):
            dashboards.append(self._extract_one_dashboard(dash))
        return dashboards

    def _extract_one_dashboard(self, dash):
        name = attr(dash, "name")
        size_el = find_local(dash, "size")
        width = _to_int(attr(size_el, "maxwidth")) or 1000
        height = _to_int(attr(size_el, "maxheight")) or 800
        size = {
            "width": width,
            "height": height,
            "min_width": _to_int(attr(size_el, "minwidth")),
            "min_height": _to_int(attr(size_el, "minheight")),
            "sizing_mode": attr(size_el, "sizing-mode"),
        }
        zones_root = find_local(dash, "zones")
        visuals, filters, param_controls, images, texts, buttons = [], [], [], [], [], []
        self._walk_zones(zones_root, width, height, visuals, filters,
                         param_controls, images, texts, buttons)
        style = {}
        style_el = find_local(dash, "style")
        for rule in findall_local(style_el, "style-rule"):
            for fmt in findall_local(rule, "format"):
                if attr(fmt, "attr") and attr(fmt, "value"):
                    style[attr(fmt, "attr")] = attr(fmt, "value")
        return {
            "name": name,
            "size": size,
            "style": style,
            "visuals": visuals,
            "filters": filters,
            "parameter_controls": param_controls,
            "images": images,
            "text_zones": texts,
            "buttons": buttons,
        }

    def _walk_zones(self, zone, width, height, visuals, filters,
                    param_controls, images, texts, buttons):
        if zone is None:
            return
        for z in findall_local(zone, "zone"):
            type_v2 = attr(z, "type-v2")
            zname = attr(z, "name")
            pos = self._zone_position(z, width, height)
            if type_v2 in ("layout-basic", "layout-flow"):
                self._walk_zones(z, width, height, visuals, filters,
                                 param_controls, images, texts, buttons)
                continue
            if type_v2 == "dashboard-object" and find_local(z, "button") is not None:
                buttons.append(self._parse_button(z, pos))
            elif type_v2 == "filter":
                pill = self._resolve_field_ref(attr(z, "param"))
                filters.append({
                    "id": attr(z, "id"), "worksheet": zname,
                    "param": attr(z, "param"),
                    "field": pill.get("field") if isinstance(pill, dict) else None,
                    "mode": attr(z, "mode"), "position": pos,
                })
            elif type_v2 == "paramctrl":
                param_controls.append({
                    "id": attr(z, "id"),
                    "parameter": strip_brackets(attr(z, "param")),
                    "param": attr(z, "param"),
                    "mode": attr(z, "mode"), "position": pos,
                })
            elif type_v2 == "bitmap":
                images.append({"id": attr(z, "id"),
                               "image_path": attr(z, "param"), "position": pos})
            elif type_v2 == "text":
                texts.append({"id": attr(z, "id"),
                              "text": self._zone_text(z), "position": pos})
            elif zname:
                # Embedded worksheet (viz) — no layout type-v2.
                visuals.append({"id": attr(z, "id"), "worksheet": zname,
                                "position": pos})
            else:
                # Unknown/container-like — still recurse for safety.
                self._walk_zones(z, width, height, visuals, filters,
                                 param_controls, images, texts, buttons)

    @staticmethod
    def _zone_position(z, width, height):
        x = _to_int(attr(z, "x")) or 0
        y = _to_int(attr(z, "y")) or 0
        w = _to_int(attr(z, "w")) or 0
        h = _to_int(attr(z, "h")) or 0
        return {
            "x": x, "y": y, "w": w, "h": h,
            "x_px": round(x / 100000 * width, 1),
            "y_px": round(y / 100000 * height, 1),
            "w_px": round(w / 100000 * width, 1),
            "h_px": round(h / 100000 * height, 1),
        }

    @staticmethod
    def _zone_text(z):
        run = None
        for r in iter_local(z, "run"):
            run = r
            break
        return clean(run.text) if run is not None else None

    def _parse_button(self, z, pos):
        button = find_local(z, "button")
        action = attr(button, "action") or ""
        states = []
        for st in findall_local(button, "button-visual-state"):
            states.append({
                "tooltip": clean(_child_text(st, "tooltip-text")),
                "image_path": clean(_child_text(st, "image-path")),
            })
        toggle = find_local(button, "toggle-action")
        if "goto-sheet" in action:
            guid = _extract_guid(action)
            return {
                "id": attr(z, "id"),
                "action_type": "goto-sheet",
                "target_window_id": guid,
                "target_dashboard": self.window_uuid_to_dashboard.get(guid),
                "tooltip": states[0]["tooltip"] if states else None,
                "image_path": states[0]["image_path"] if states else None,
                "states": states,
                "position": pos,
                "powerbi_mapping": "actionButton visualLink.type=PageNavigation",
            }
        if toggle is not None:
            toggle_text = clean(toggle.text) or ""
            zone_ids = _extract_zone_ids(toggle_text)
            return {
                "id": attr(z, "id"),
                "action_type": "toggle",
                "target_window_id": _extract_guid(toggle_text),
                "target_zone_ids": zone_ids,
                "active_visual_state_index": _to_int(attr(button, "active-visual-state-index")),
                "tooltip": states[0]["tooltip"] if states else None,
                "states": states,
                "position": pos,
                "powerbi_mapping": "actionButton visualLink.type=Bookmark (Show/Hide pair)",
            }
        return {
            "id": attr(z, "id"),
            "action_type": "unknown",
            "raw_action": action,
            "states": states,
            "position": pos,
        }

    # -- relationships ---------------------------------------------------
    def _extract_relationships(self, datasources):
        rels = []
        for ds in datasources:
            # Modern object-model relationships.
            for r in ds.get("object_relationships", []):
                rels.append({
                    "datasource": ds["caption"],
                    "left_table": r.get("left_table"),
                    "left_column": r.get("left_column"),
                    "right_table": r.get("right_table"),
                    "right_column": r.get("right_column"),
                    "join_type": "relationship",
                    "operator": r.get("operator"),
                })
            # Legacy physical joins.
            for join in ds["joins"]:
                left = join.get("left") or {}
                right = join.get("right") or {}
                for clause in join.get("clauses", []):
                    lc, rc = _split_join_expression(clause.get("raw"))
                    rels.append({
                        "datasource": ds["caption"],
                        "left_table": left.get("table"),
                        "left_column": lc,
                        "right_table": right.get("table"),
                        "right_column": rc,
                        "join_type": join.get("join_type"),
                    })
                if not join.get("clauses"):
                    rels.append({
                        "datasource": ds["caption"],
                        "left_table": left.get("table"),
                        "right_table": right.get("table"),
                        "join_type": join.get("join_type"),
                        "left_column": None, "right_column": None,
                    })
        return rels

    # -- blending --------------------------------------------------------
    def _detect_blending(self, datasources, worksheets):
        real = [d for d in datasources if not d["is_parameters"]]
        if len(real) <= 1:
            return {"is_blended": False, "primary": real[0]["caption"] if real else None,
                    "secondary": [], "linking_fields": [],
                    "note": "Single datasource — no blending"}
        # Multiple datasources: worksheets referencing >1 datasource indicate a blend.
        used = set()
        for ws in worksheets:
            if ws["datasource"]:
                used.add(ws["datasource"])
        primary = real[0]
        secondary = [d["caption"] for d in real[1:]]
        return {
            "is_blended": len(real) > 1,
            "primary": primary["caption"],
            "secondary": secondary,
            "linking_fields": [],
            "note": f"{len(real)} datasources present — verify cross-source field usage",
        }

    # -- formatting ------------------------------------------------------
    def _collect_field_formatting(self, datasources, parameters):
        out = []
        seen = set()
        for ds in datasources:
            for col in ds["columns"]:
                fmt = col.get("format")
                if fmt and col["caption"] not in seen:
                    seen.add(col["caption"])
                    out.append({
                        "field": col["caption"],
                        "format": fmt,
                        "kind": col.get("format_kind"),
                        "powerbi_format": col.get("powerbi_format"),
                    })
        for p in parameters:
            if p.get("format") and p["caption"] not in seen:
                seen.add(p["caption"])
                out.append({
                    "field": p["caption"],
                    "format": p["format"],
                    "kind": classify_format(p["format"]),
                    "powerbi_format": tableau_format_to_powerbi(p["format"]),
                })
        return out

    # -- RLS -------------------------------------------------------------
    def _detect_rls(self, datasources):
        signals = []
        user_functions = set()
        # Scan all calculated field formulas for user functions.
        for ds in datasources:
            for col in ds["columns"]:
                if not col["is_calculated"]:
                    continue
                formula = (col["calculation"] or {}).get("formula") or ""
                for m in USER_FUNCTION_RE.finditer(formula):
                    user_functions.add(m.group(1).upper())
                    signals.append({
                        "kind": "user_function_in_calc",
                        "field": col["caption"],
                        "function": m.group(1).upper(),
                    })
                # Hardcoded per-user predicate or username-column comparison.
                if "username" in formula.lower() or "user@" in formula.lower() \
                        or re.search(r'"[^"]+@[^"]+"', formula):
                    signals.append({"kind": "user_predicate_in_calc",
                                    "field": col["caption"]})

        # Detect user-mapping (entitlement) tables.
        mapping_table = None
        user_column = None
        entitlement_column = None
        for ds in datasources:
            for tbl in ds["physical_tables"]:
                col_names = [c["name"] for c in tbl["columns"]]
                user_cols = [c for c in col_names if c and USER_COLUMN_RE.search(c)]
                if user_cols and len(col_names) >= 2:
                    mapping_table = tbl["name"]
                    user_column = user_cols[0]
                    others = [c for c in col_names if c not in user_cols]
                    entitlement_column = others[0] if others else None
                    signals.append({"kind": "user_mapping_table",
                                    "table": mapping_table,
                                    "user_column": user_column,
                                    "entitlement_column": entitlement_column})

        detected = bool(signals)
        if not detected:
            return {"detected": False, "type": "None", "signals": [],
                    "user_functions": [], "mapping_table": None,
                    "user_column": None, "entitlement_column": None,
                    "secured_table": None, "roles": []}

        # Classify.
        if mapping_table:
            rls_type = "Dynamic"
        elif "ISMEMBEROF" in user_functions:
            rls_type = "Group-based"
        elif any(s["kind"] == "user_predicate_in_calc" for s in signals):
            rls_type = "Static"
        else:
            rls_type = "Dynamic" if user_functions else "Static"

        secured_table = None
        for ds in datasources:
            for tbl in ds["physical_tables"]:
                if tbl["name"] != mapping_table:
                    secured_table = tbl["name"]
                    break
            if secured_table:
                break

        roles = []
        if rls_type == "Dynamic" and mapping_table:
            roles.append({
                "name": f"RLS_{strip_brackets(entitlement_column or 'User')}",
                "rls_type": "Dynamic",
                "secured_table": secured_table,
                "entitlement_column": entitlement_column,
                "mapping_table": mapping_table,
                "user_column": user_column,
                "dax_intent": f"[{user_column}] = USERPRINCIPALNAME()",
            })
        elif rls_type == "Group-based":
            roles.append({"name": "GroupRole", "rls_type": "Group-based",
                          "dax_intent": "Assign Entra/AD group to role in Power BI Service"})

        return {
            "detected": True,
            "type": rls_type,
            "signals": signals,
            "user_functions": sorted(user_functions),
            "mapping_table": mapping_table,
            "user_column": user_column,
            "entitlement_column": entitlement_column,
            "secured_table": secured_table,
            "roles": roles,
        }


# ---------------------------------------------------------------------------
# Small standalone helpers
# ---------------------------------------------------------------------------

def _to_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _decode(text):
    """Decode residual XML entities (ElementTree already handles most)."""
    if text is None:
        return None
    for ent, ch in ENTITY_DECODE.items():
        text = text.replace(ent, ch)
    return text.replace("\r\n", "\n")


def _child_text(elem, name):
    child = find_local(elem, name)
    return child.text if child is not None else None


def _semantic_to_category(semantic_role):
    if not semantic_role:
        return None
    role = semantic_role.strip("[]")
    for key in ("Country", "State", "City", "ZipCode", "County", "Area",
                "CBSA", "Latitude", "Longitude"):
        if key.lower() in role.lower():
            return key
    return None


def _relation_side(rel, index):
    subs = [r for r in findall_local(rel, "relation")]
    if index < len(subs):
        return {"name": attr(subs[index], "name"), "table": attr(subs[index], "table")}
    return {}


def _expression_text(expr):
    if expr is None:
        return None
    parts = []
    op = attr(expr, "op")
    if op:
        parts.append(op)
    for sub in iter_local(expr, "expression"):
        o = attr(sub, "op")
        if o:
            parts.append(o)
    return " ".join(parts) if parts else None


def _split_join_expression(raw):
    if not raw:
        return None, None
    tokens = [t for t in raw.split() if t.startswith("[")]
    if len(tokens) >= 2:
        return strip_brackets(tokens[0]), strip_brackets(tokens[1])
    return None, None


def _strip_disambiguation(col):
    """Remove Tableau's ' (table.ext)' disambiguation suffix from a column name."""
    if not col:
        return col
    return re.sub(r"\s*\([^()]*\.[^()]*\)\s*$", "", col).strip()


def _extract_guid(text):
    if not text:
        return None
    m = re.search(r"\{[0-9A-Fa-f\-]{36}\}", text)
    return m.group(0) if m else None


def _extract_zone_ids(text):
    if not text:
        return []
    m = re.search(r"zone-ids=\[([0-9,\s]*)\]", text)
    if not m:
        return []
    return [int(x) for x in re.findall(r"\d+", m.group(1))]


def pascal_case(text):
    if not text:
        return "Workbook"
    words = re.split(r"[^0-9A-Za-z]+", text)
    return "".join(w[:1].upper() + w[1:] for w in words if w) or "Workbook"


# ---------------------------------------------------------------------------
# TWB / TWBX loading
# ---------------------------------------------------------------------------

def load_twb_bytes(path: Path) -> bytes:
    """Return the .twb XML bytes, unpacking a .twbx (ZIP) if necessary."""
    if path.suffix.lower() == ".twbx":
        with zipfile.ZipFile(path) as zf:
            twb_members = [n for n in zf.namelist() if n.lower().endswith(".twb")]
            if not twb_members:
                raise ValueError(f"No .twb found inside {path}")
            with zf.open(twb_members[0]) as fh:
                return fh.read()
    return path.read_bytes()


def find_workbooks(root: Path):
    if root.is_file():
        return [root]
    return sorted(list(root.rglob("*.twb")) + list(root.rglob("*.twbx")))


# ---------------------------------------------------------------------------
# Markdown rendering (backward-compat with existing downstream agents)
# ---------------------------------------------------------------------------

def _md_table(headers, rows):
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join(["---"] * len(headers)) + "|"]
    if not rows:
        out.append("| " + " | ".join(["None"] + [""] * (len(headers) - 1)) + " |")
    for row in rows:
        out.append("| " + " | ".join("" if c is None else str(c).replace("|", "\\|")
                                      for c in row) + " |")
    return "\n".join(out)


def render_analysis_markdown(data: dict) -> str:
    L = [f"# Tableau Workbook Analysis: {data['workbook_name']}",
         "",
         "> Auto-generated by the deterministic tableau_extractor.py — do not hand-edit.",
         f"> Source: `{data['source_file']}`",
         ""]
    wb = data["workbook"]
    L += ["## Workbook Info",
          f"- **Version**: {wb.get('version')}",
          f"- **Source Build**: {wb.get('source_build')}",
          f"- **Platform**: {wb.get('source_platform')}", ""]

    L += ["## Parameters",
          _md_table(["Name", "Data Type", "Domain Type", "Default", "Range/Values"],
                    [[p["caption"], p["datatype"], p["domain_type"], p["default_value"],
                      _param_values(p)] for p in data["parameters"]]), ""]

    L += ["## Data Source Summary",
          _md_table(["Datasource", "Connection Type", "Source Details"],
                    [[ds["caption"], ", ".join(ds["connection_types"]) or "Unknown",
                      _source_detail(ds)] for ds in data["datasources"]]), ""]

    L += ["## Datasources"]
    for ds in data["datasources"]:
        L.append(f"### {ds['caption']} ({', '.join(ds['connection_types']) or 'Unknown'})")
        dims = [c for c in ds["columns"] if c["role"] == "dimension" and not c["is_calculated"]]
        meas = [c for c in ds["columns"] if c["role"] == "measure" and not c["is_calculated"]]
        L += ["", "#### Dimensions",
              _md_table(["Display Name", "Field Name", "Data Type", "Semantic Role", "Table"],
                        [[c["caption"], c["name"], c["datatype"], c["semantic_role"],
                          c["physical_table"]] for c in dims]), ""]
        L += ["#### Measures",
              _md_table(["Display Name", "Field Name", "Data Type", "Table"],
                        [[c["caption"], c["name"], c["datatype"], c["physical_table"]]
                         for c in meas]), ""]

    calcs = data["fields"]["calculated_fields"]
    L += ["## Calculated Fields",
          _md_table(["Name", "Formula", "Data Type", "Role"],
                    [[c["caption"], _one_line((c["calculation"] or {}).get("formula")),
                      c["datatype"], c["role"]] for c in calcs]), ""]

    L += ["## Worksheet Visual Details",
          _md_table(["Worksheet", "Mark Type", "PBI Visual", "Rows (Y)", "Cols (X)",
                     "Color", "Size", "Text/Label"],
                    [[w["name"], w["mark_type"], w["inferred_powerbi_visual"],
                      _pills_str(w["rows"]), _pills_str(w["cols"]),
                      _enc_str(w["encodings"]["color"]), _enc_str(w["encodings"]["size"]),
                      _enc_str(w["encodings"]["text"])] for w in data["worksheets"]]), ""]

    L += ["## Worksheet Filters",
          _md_table(["Worksheet", "Field", "Kind", "Members / Top-N", "Action Filter"],
                    _worksheet_filter_rows(data["worksheets"])), ""]

    L += ["## Aggregations In Use (column-instances)",
          _md_table(["Datasource", "Field", "Aggregation / Derivation"],
                    _aggregation_rows(data["datasources"])), ""]

    L += ["## Dashboard Layout"]
    for d in data["dashboards"]:
        L += [f"### {d['name']}",
              f"- **Size**: {d['size']['width']} × {d['size']['height']} px",
              _md_table(["Zone", "Type", "Worksheet/Field", "x", "y", "w", "h"],
                        _dashboard_rows(d)), ""]

    L += ["## Navigation Buttons"]
    for d in data["dashboards"]:
        if d["buttons"]:
            L += [f"### {d['name']}",
                  _md_table(["#", "Action Type", "Tooltip", "Target", "x", "y", "w", "h"],
                            [[b["id"], b["action_type"], b.get("tooltip"),
                              b.get("target_dashboard") or _zone_ids_str(b),
                              b["position"]["x"], b["position"]["y"],
                              b["position"]["w"], b["position"]["h"]]
                             for b in d["buttons"]]), ""]
    if not any(d["buttons"] for d in data["dashboards"]):
        L += ["None", ""]

    L += ["## Sets",
          _md_table(["Set Name", "Source Field", "Type", "Members / Condition"],
                    [[s["name"], s["source_field"], s.get("type"),
                      ", ".join(s["members"]) or "computed"] for s in data["sets"]]), ""]
    L += ["## Groups",
          _md_table(["Group Field", "Source Dimension", "Members"],
                    [[g["name"], g["source_field"], ", ".join(g["members"])]
                     for g in data["groups"]]), ""]
    L += ["## Bins",
          _md_table(["Bin Field", "Source Field", "Bin Size"],
                    [[b["name"], b["source_field"], b["bin_size"]] for b in data["bins"]]), ""]

    bl = data["data_blending"]
    L += ["## Data Blending",
          _md_table(["Primary Datasource", "Secondary Datasource", "Linking Field(s)"],
                    [[bl["primary"], ", ".join(bl["secondary"]) or "None",
                      ", ".join(bl["linking_fields"]) or bl["note"]]]), ""]

    L += ["## Field Formatting",
          _md_table(["Field", "Tableau Format String", "Kind", "Power BI formatString"],
                    [[f["field"], f["format"], f["kind"], f["powerbi_format"]]
                     for f in data["field_formatting"]]), ""]

    rls = data["row_level_security"]
    L += ["## Row-Level Security (RLS)",
          f"- **Detected**: {'Yes' if rls['detected'] else 'No'}",
          f"- **Type**: {rls['type']}",
          f"- **Secured Table**: {rls.get('secured_table')}",
          f"- **Mapping Table.User Column**: {rls.get('mapping_table')}.{rls.get('user_column')}"
          if rls.get("mapping_table") else "- **Mapping Table.User Column**: None", ""]
    if rls["roles"]:
        L += [_md_table(["Suggested Role", "RLS Type", "Secured Table", "Entitlement Column",
                         "Mapping Table", "User Column", "Power BI Filter (DAX intent)"],
                        [[r.get("name"), r.get("rls_type"), r.get("secured_table"),
                          r.get("entitlement_column"), r.get("mapping_table"),
                          r.get("user_column"), r.get("dax_intent")] for r in rls["roles"]]), ""]

    L += ["## Worksheets"] + [f"{i+1}. {w['name']}" for i, w in enumerate(data["worksheets"])] + [""]
    L += ["## Dashboards"] + [f"{i+1}. {d['name']}" for i, d in enumerate(data["dashboards"])] + [""]

    L += ["## Relationships",
          _md_table(["Left Table", "Left Column", "Right Table", "Right Column", "Join Type"],
                    [[r.get("left_table"), r.get("left_column"), r.get("right_table"),
                      r.get("right_column"), r.get("join_type")]
                     for r in data["relationships"]]), ""]
    return "\n".join(L)


def render_visuals_markdown(data: dict) -> str:
    L = [f"# Tableau Visual Extraction: {data['workbook_name']}",
         "",
         "> Auto-generated by the deterministic tableau_extractor.py — do not hand-edit.",
         ""]
    for d in data["dashboards"]:
        L += [f"## Dashboard Layout: {d['name']}",
              f"- **Size**: {d['size']['width']} × {d['size']['height']} px",
              f"- **Sizing Mode**: {d['size'].get('sizing_mode')}", ""]
        L += ["## Visual Inventory"]
        ws_by_name = {w["name"]: w for w in data["worksheets"]}
        for i, v in enumerate(d["visuals"], 1):
            w = ws_by_name.get(v["worksheet"], {})
            pos = v["position"]
            L += [f"### Visual {i}: {v['worksheet']}",
                  f"- **Chart Type**: {w.get('mark_type')} → {w.get('inferred_powerbi_visual')}",
                  f"- **Position**: x={pos['x_px']}, y={pos['y_px']}, w={pos['w_px']}, h={pos['h_px']} (px)",
                  f"- **X-Axis (Columns)**: {_pills_str(w.get('cols', []))}",
                  f"- **Y-Axis (Rows)**: {_pills_str(w.get('rows', []))}",
                  f"- **Color**: {_enc_str((w.get('encodings') or {}).get('color'))}",
                  f"- **Size**: {_enc_str((w.get('encodings') or {}).get('size'))}",
                  f"- **Labels**: {_enc_str((w.get('encodings') or {}).get('text'))}",
                  f"- **Secondary Axis / Combo**: {_dual_str(w.get('dual_axis'))}",
                  f"- **Analytics Lines**: {_reflines_str(w.get('reference_lines'))}",
                  f"- **Filters**: {_filters_str(w.get('filters'))}",
                  f"- **Top N**: {_topn_str(w.get('top_n'))}",
                  f"- **Title**: {(w.get('title') or {}).get('text')}", ""]
        L += ["## Filters / Slicers",
              _md_table(["Filter", "Field", "Worksheet", "Position (px)", "Mode"],
                        [[f["id"], f["field"], f["worksheet"],
                          _pos_str(f["position"]), f["mode"]] for f in d["filters"]]), ""]
        L += ["## Parameter Controls",
              _md_table(["Parameter", "Mode", "Position (px)"],
                        [[p["parameter"], p["mode"], _pos_str(p["position"])]
                         for p in d["parameter_controls"]]), ""]
        L += ["## Navigation Buttons",
              _md_table(["#", "Action Type", "Tooltip", "Target", "Position (px)"],
                        [[b["id"], b["action_type"], b.get("tooltip"),
                          b.get("target_dashboard") or _zone_ids_str(b),
                          _pos_str(b["position"])] for b in d["buttons"]]), ""]
        L += ["## Images",
              _md_table(["#", "Image Path", "Position (px)"],
                        [[im["id"], im["image_path"], _pos_str(im["position"])]
                         for im in d["images"]]), ""]
    return "\n".join(L)


# -- markdown value formatters ------------------------------------------

def _param_values(p):
    if p["range"]:
        return f"min={p['range']['min']} max={p['range']['max']} step={p['range']['granularity']}"
    if p["members"]:
        return ", ".join(str(m["value"]) for m in p["members"])
    if p["aliases"]:
        return ", ".join(f"{a['key']}={a['value']}" for a in p["aliases"])
    return "any"


def _source_detail(ds):
    parts = []
    for c in ds["connections"]:
        if c.get("filename"):
            parts.append(c["filename"])
        elif c.get("server"):
            parts.append(f"{c['server']}/{c.get('dbname') or ''}")
    return ", ".join(dict.fromkeys(parts)) or "—"


def _one_line(text):
    if not text:
        return None
    return text.replace("\n", " ").replace("\r", " ").strip()


def _pills_str(pills):
    if not pills:
        return "None"
    out = []
    for p in pills:
        if not p:
            continue
        label = p.get("caption") or p.get("field")
        if p.get("aggregation"):
            label = f"{p['aggregation']}({label})"
        elif p.get("date_part"):
            label = f"{p['date_part']}({label})"
        out.append(label)
    return " / ".join(out) or "None"


def _enc_str(enc):
    if not enc:
        return "None"
    if isinstance(enc, dict):
        return enc.get("caption") or enc.get("field") or "None"
    return str(enc)


def _dual_str(dual):
    if not dual:
        return "None"
    return f"{', '.join(dual.get('marks', []))} on {', '.join(dual.get('measures', []))}"


def _reflines_str(lines):
    if not lines:
        return "None"
    return "; ".join(f"{l['type']}={l.get('value') or l.get('aggregation')}" for l in lines)


def _filters_str(filters):
    if not filters:
        return "None"
    parts = []
    for f in filters:
        if f.get("is_action_filter"):
            continue
        desc = f.get("field") or f.get("column")
        if f.get("members"):
            desc += f" in [{', '.join(f['members'])}]"
        if f.get("top_n"):
            desc += f" (Top {f['top_n']['count']})"
        parts.append(desc)
    return "; ".join(parts) or "None"


def _topn_str(topn):
    if not topn:
        return "None"
    return f"Top {topn['count']} ({topn['direction']})"


def _pos_str(pos):
    return f"x={pos['x_px']}, y={pos['y_px']}, w={pos['w_px']}, h={pos['h_px']}"


def _zone_ids_str(b):
    ids = b.get("target_zone_ids")
    return f"zones {ids}" if ids else None


def _dashboard_rows(d):
    rows = []
    for v in d["visuals"]:
        p = v["position"]
        rows.append([v["id"], "viz", v["worksheet"], p["x"], p["y"], p["w"], p["h"]])
    for f in d["filters"]:
        p = f["position"]
        rows.append([f["id"], "filter", f["field"], p["x"], p["y"], p["w"], p["h"]])
    for pc in d["parameter_controls"]:
        p = pc["position"]
        rows.append([pc["id"], "paramctrl", pc["parameter"], p["x"], p["y"], p["w"], p["h"]])
    for im in d["images"]:
        p = im["position"]
        rows.append([im["id"], "image", im["image_path"], p["x"], p["y"], p["w"], p["h"]])
    return rows


def _worksheet_filter_rows(worksheets):
    rows = []
    for w in worksheets:
        for f in w.get("filters", []):
            members = ", ".join(f.get("members") or [])
            if f.get("top_n"):
                members = f"Top {f['top_n']['count']} ({f['top_n']['direction']})"
            if f.get("range"):
                members = f"range {f['range'].get('min')}..{f['range'].get('max')}"
            rows.append([w["name"], f.get("field") or f.get("column"), f.get("kind"),
                         members, "Yes" if f.get("is_action_filter") else "No"])
    return rows


def _aggregation_rows(datasources):
    rows = []
    for ds in datasources:
        for inst in ds.get("column_instances", []):
            deriv = inst.get("derivation")
            if not deriv or deriv == "None":
                continue
            rows.append([ds["caption"], strip_brackets(inst.get("column")), deriv])
    return rows


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def process(path: Path, out_dir: Path, name: str, emit_markdown: bool, quiet: bool):
    twb_bytes = load_twb_bytes(path)
    extractor = TableauExtractor(twb_bytes, path)
    data = extractor.extract()

    folder_name = name or data["suggested_output_folder_name"]
    target = out_dir if out_dir else Path(".specify/memory") / folder_name
    target.mkdir(parents=True, exist_ok=True)

    json_path = target / "tableau-extraction.json"
    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    written = [json_path]

    if emit_markdown:
        analysis_path = target / "tableau-analysis-output.md"
        analysis_path.write_text(render_analysis_markdown(data), encoding="utf-8")
        visuals_path = target / "tableau-visuals-output.md"
        visuals_path.write_text(render_visuals_markdown(data), encoding="utf-8")
        written += [analysis_path, visuals_path]

    if not quiet:
        s = data["summary"]
        print(f"[extracted] {path.name} -> {target}")
        print(f"  datasources={s['datasource_count']} worksheets={s['worksheet_count']} "
              f"dashboards={s['dashboard_count']} params={s['parameter_count']} "
              f"calcs={s['calculated_field_count']} rls={s['rls_detected']}")
        for w in written:
            print(f"  wrote {w}")
    return data


def main(argv=None):
    parser = argparse.ArgumentParser(description="Deterministic Tableau .twb/.twbx extractor")
    parser.add_argument("input", help="Path to a .twb/.twbx file or a folder to scan")
    parser.add_argument("--out-dir", help="Explicit output directory for artifacts")
    parser.add_argument("--name", help="Output folder name (defaults to PascalCase subfolder)")
    parser.add_argument("--no-markdown", action="store_true",
                        help="Emit only JSON (skip the two markdown files)")
    parser.add_argument("--stdout", action="store_true",
                        help="Print the JSON to stdout instead of writing files")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.input)
    if not root.exists():
        print(f"ERROR: input not found: {root}", file=sys.stderr)
        return 3

    workbooks = find_workbooks(root)
    if not workbooks:
        print(f"ERROR: no .twb/.twbx found under {root}", file=sys.stderr)
        return 3

    if args.stdout:
        results = [TableauExtractor(load_twb_bytes(wb), wb).extract() for wb in workbooks]
        print(json.dumps(results if len(results) > 1 else results[0],
                         indent=2, ensure_ascii=False))
        return 0

    out_dir = Path(args.out_dir) if args.out_dir else None
    for wb in workbooks:
        # When scanning multiple, never share one --out-dir/name across them.
        this_out = out_dir if (out_dir and len(workbooks) == 1) else None
        this_name = args.name if len(workbooks) == 1 else None
        process(wb, this_out, this_name, not args.no_markdown, args.quiet)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
