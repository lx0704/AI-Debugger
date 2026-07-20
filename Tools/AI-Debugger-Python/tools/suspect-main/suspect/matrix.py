from collections import defaultdict
from .utils import _method_start_line
import math

class Matrix:
    def __init__(self):
        self.rows = defaultdict(dict)  # method_key -> {metric: value}

    def merge(self, d):
        for method, metrics in d.items():
            file_path = method.split(":", 1)[0]

            if _is_test_file(file_path):
                continue
            self.rows[method].update(metrics)



    def fill_missing_mbfl(self):
        metrics = [
            "sbi",
            "tarantula",
            "ochiai",
            "jaccard",
            "dstar",
            "op2",
            "barinel",
            "naish2",
        ]

        for m in self.rows.values():
            for metric in metrics:
                mbfl_key = f"mbfl_{metric}"
                sbfl_key = f"sbfl_{metric}"

                value = m.get(mbfl_key)

                # Skip if this MBFL metric was never produced
                # if mbfl_key not in m:
                #     continue                

                if (value is None
                    or value == ""
                    or (isinstance(value, float) and math.isnan(value))):
                    m[mbfl_key] = m.get(sbfl_key)

    def headers(self):
        cols = set()
        for m in self.rows.values():
            cols |= set(m.keys())

        # Remove columns that are not features
        cols.discard("line_no")
        cols.discard("label")

        feature_cols = sorted(cols)

        return ["line_name"] + feature_cols + ["label"]

    def enrich_line_numbers(self, project_root):
        for method in self.rows:
            try:
                self.rows[method]["line_no"] = _method_start_line(method, project_root)
            except:
                self.rows[method]["line_no"] = None


    def to_rows(self, project_root=None):
        include_line_no = project_root is not None
        headers = self.headers()
        feature_headers = headers[1:-1]
        out = [headers]

        # for method in sorted(self.rows.keys()):
        #     m = self.rows[method]

        #     # Fix line_no
        #     line_no = ""
        #     if project_root:
        #         try:
        #             line_no = _method_start_line(method, project_root)
        #         except Exception:
        #             line_no = ""

        #     row = [method]
            
        #     if include_line_no:
        #         row.append(line_no)
        #         self.rows[method]["line_no"] = line_no  # Add line_no to the metrics for this method, so it can be exported as well
        #     # Fix line_no
        #     
            
        for method in sorted(self.rows.keys()):
            m = self.rows[method]
            
            file_name = method.split(':')[0]
            line_no = m.get("line_no", "")

            line_name = f"{file_name}:{line_no}"

            row = [line_name]
            row.extend(m.get(h, "") for h in feature_headers)
            row.append(m.get("label", 0))
            out.append(row)
        return out
    
    def add_diff_labels(self, diff_set):
        for method, m in self.rows.items():
            file_path, _ = method.split(":", 1)
            

            line_no = m.get("line_no", None)

            if line_no is None or line_no == "":
                m["label"] = 0
                continue

            try:
                line_no = int(line_no)
            except:
                m["label"] = 0
                continue

            if (file_path, line_no) in diff_set:
                m["label"] = 1
            else:
                m["label"] = 0



def _is_test_file(path: str) -> bool:
    p = str(path).replace("\\", "/")
    name = p.rsplit("/", 1)[-1]
    return (
        "/tests/" in p or
        p.startswith("tests/") or
        name.startswith("test_") or
        p.endswith("_test.py")
    )