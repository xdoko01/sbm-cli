"""SBM 12.0 JSON API HTTP client."""
from __future__ import annotations

import urllib3
import requests
from requests.auth import HTTPBasicAuth

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class SBMError(Exception):
    """Raised when the SBM API returns result.type == 'ERROR'."""

    def __init__(self, message: str, field: str | None = None) -> None:
        super().__init__(message)
        self.field = field


class SBMClient:
    def __init__(self, host: str, username: str, password: str, verify_ssl: bool = True) -> None:
        self.host = host.rstrip("/")
        self._session = requests.Session()
        self._session.auth = HTTPBasicAuth(username, password)
        self._session.headers.update({
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json",
        })
        self._session.verify = verify_ssl

    def check_auth(self) -> None:
        """Validate credentials. Raises PermissionError on 401."""
        try:
            self._post(f"{self.host}/jsonapi/GetItem/0/0", {})
        except SBMError:
            pass  # API-level error (e.g. item not found) is fine — credentials accepted

    def get_item(self, table_id: int, item_id: int,
                 fields: list[str] | None = None) -> dict:
        url = f"{self.host}/jsonapi/GetItem/{table_id}/{item_id}"
        body: dict = {}
        if fields is not None:
            body["fixedFields"] = False
            body["fields"] = [{"dbname": f} for f in fields]
        return self._post(url, body)

    def get_item_by_display_id(self, display_id: str, table_id: int,
                                fields: list[str] | None = None) -> dict:
        url = f"{self.host}/jsonapi/getitemsbyitemid/{table_id}/{display_id}"
        body: dict = {}
        if fields is not None:
            body["fixedFields"] = False
            body["fields"] = [{"dbname": f} for f in fields]
        data = self._post(url, body)
        items = data.get("items") or []
        if not items:
            raise ValueError(f"No item found with display ID '{display_id}'")
        return {"item": items[0], "result": data.get("result", {})}

    def list_items_by_report(self, report_id: int,
                              fields: list[str] | None = None,
                              page_size: int = 200) -> list[dict]:
        url = f"{self.host}/jsonapi/getitemsbylistingreport/{report_id}"
        body: dict = {}
        if fields is not None:
            body["fixedFields"] = False
            body["fields"] = [{"dbname": f} for f in fields]
        data = self._post(url, body, params={"pagesize": page_size})
        return data.get("items") or []

    def list_items_by_filter(self, filter_id: int | str,
                              fields: list[str] | None = None,
                              page_size: int = 200) -> list[dict]:
        # pagesize MUST be a URL query param — body param is silently ignored
        url = f"{self.host}/jsonapi/getitemsbyreportfilter/{filter_id}"
        body: dict = {}
        if fields is not None:
            body["fixedFields"] = False
            body["fields"] = [{"dbname": f} for f in fields]
        data = self._post(url, body, params={"pagesize": page_size})
        return data.get("items") or []

    def start_transition(self, table_id: int, item_id: int,
                         transition_id: int, break_lock: bool = True) -> int:
        """Call StartTransition and return the itemLockId."""
        url = f"{self.host}/jsonapi/startTransition/{table_id}/{item_id}/{transition_id}"
        body: dict = {}
        if break_lock:
            body["breakLock"] = True
        data = self._post(url, body)
        return data["startTransition"]["item"]["id"]["itemLockId"]

    def update_item(self, table_id: int, item_id: int, field_values: dict,
                    transition_id: int = 0, record_lock_id: int = -1,
                    return_fields: list[str] | None = None) -> dict:
        """
        Update via FinishTransition.
        transition_id=0, record_lock_id=-1 → default update (no lock needed).
        For named transitions use lock from start_transition().
        """
        url = (f"{self.host}/jsonapi/finishTransition"
               f"/{table_id}/{item_id}/{transition_id}/{record_lock_id}")
        body: dict = {"transition": field_values}
        if return_fields is not None:
            body["fixedFields"] = False
            body["fields"] = [{"dbname": f} for f in return_fields]
        return self._post(url, body)

    def probe_table(self, table_id: int, max_probe: int = 500) -> list[dict]:
        """
        Discover items in a relational lookup table by probing IDs 1..max_probe.
        Uses 10 concurrent threads. Intended for sbm field-values discovery.
        Returns sorted list of {id, name} dicts for items that exist.
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        results: list[dict] = []

        def try_item(item_id: int) -> dict | None:
            try:
                data = self.get_item(table_id, item_id, fields=["TITLE"])
                item = data.get("item", {})
                if not item:
                    return None
                iid = item.get("id", {})
                fields = item.get("fields", {})
                name = (fields.get("TITLE", {}).get("value")
                        or iid.get("itemName", ""))
                numeric_id = iid.get("id")
                if numeric_id is None:
                    return None
                return {"id": numeric_id, "name": str(name) if name else ""}
            except (ValueError, SBMError, requests.RequestException):
                return None

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(try_item, i): i for i in range(1, max_probe + 1)}
            for future in as_completed(futures):
                result = future.result()
                if result is not None:
                    results.append(result)

        return sorted(results, key=lambda x: x["id"])

    def get_field_definitions(self, display_id: str, table_id: int) -> list[dict]:
        """Fetch field definitions by inspecting a sample ticket.

        Returns a sorted list of {dbname, type, label} dicts.
        'type' is inferred: 'relational' for {id, name} values,
        'numeric' for ints/floats, 'text' otherwise.
        'label' comes from 'displayName' in the API response if present,
        otherwise falls back to dbname.
        """
        data = self.get_item_by_display_id(display_id, table_id, fields=None)
        item = data.get("item", {})
        result: list[dict] = []
        for dbname, fdata in item.get("fields", {}).items():
            if not isinstance(fdata, dict):
                continue
            value = fdata.get("value")
            if isinstance(value, dict) and "id" in value:
                field_type = "relational"
            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                field_type = "numeric"
            else:
                field_type = "text"
            label = fdata.get("displayName", dbname)
            result.append({"dbname": dbname, "type": field_type, "label": label})
        return sorted(result, key=lambda x: x["dbname"])

    def _post(self, url: str, body: dict, params: dict | None = None) -> dict:
        resp = self._session.post(url, json=body, params=params, timeout=30)
        if resp.status_code == 401:
            raise PermissionError("Authentication failed (HTTP 401)")
        resp.raise_for_status()
        data = resp.json()
        self._check_result(data)
        return data

    def _check_result(self, data: dict) -> None:
        result = data.get("result", {})
        if result.get("type") == "ERROR":
            errors = result.get("errors", {})
            field_errors = errors.get("errorfields", [])
            if field_errors:
                first_field = field_errors[0].get("dbName")
                msg = "; ".join(f"{e['dbName']}: {e['msg']}" for e in field_errors)
                raise SBMError(msg, field=first_field)
            msg = result.get("msg") or result.get("msgLoc") or "Unknown API error"
            raise SBMError(msg)
