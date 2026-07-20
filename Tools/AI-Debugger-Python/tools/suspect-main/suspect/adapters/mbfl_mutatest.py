"""Clean minimal MBFL adapter (re-written)."""
from __future__ import annotations

import ast, fnmatch, json, os, pathlib, random, subprocess, sys, time
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple, Any

from .base import MetricAdapter
from ..mapping import MethodIndex
from ..plugins import register_adapter
from ..formulas import mbfl as F
from ..formulas import sbfl as F_sbfl


@dataclass
class Mutant:
    file_rel: str
    line: int
    original: str
    mutated: str
    kind: str


class MBFLMutatestAdapter(MetricAdapter):
    name = 'mbfl'

    def collect(self, ctx: dict) -> Dict[str, Dict[str, float]]:  # noqa: C901
        project = pathlib.Path(ctx['project_root']).resolve()
        test_cmd: str = ctx['test_cmd']
        include: List[str] = ctx.get('mbfl_include') or []
        exclude: List[str] = ctx.get('mbfl_exclude') or []
        allow_failing: bool = bool(ctx.get('mbfl_allow_failing'))
        survivor_fallback: str = str(ctx.get('mbfl_survivor_fallback') or 'on').lower()
        sample_rate = float(ctx.get('mbfl_sample') or 0.0)
        diag_level = os.environ.get('SUSPECT_MBFL_DIAG', 'full')

        diag: Dict[str, Any] = {
            'status': 'running',  # will flip to 'ok' at end
            'config': {'include': include, 'exclude': exclude, 'sample_rate': sample_rate},
            'baseline': {}, 'runs': [], 'aggregate': {}, 'mbfl': {}
        }
        out_path = project / '.suspect.mutatest.json'
        # Write an initial skeleton so user can tail progress
        try:
            self._write(out_path, diag)
        except Exception:
            pass

        print("Processing mbfl")    
        
        targets: List[str] = []
        for root, dirs, files in os.walk(project):
            dirs[:] = [d for d in dirs if d not in {'.git','__pycache__','venv','.venv','env','build','dist'}]
            for fn in files:
                if not fn.endswith('.py'): continue
                ap = pathlib.Path(root) / fn
                rel = ap.relative_to(project).as_posix()
                # Skip mutating the tool's own implementation to avoid self-modification hangs
                if rel.startswith('suspect/'):
                    continue
                if rel.startswith('tests/') or '/tests/' in rel or fn.startswith('test_') or rel.endswith('_test.py'): continue
                if include and not any(fnmatch.fnmatch(rel,g) or fnmatch.fnmatch(fn,g) for g in include): continue
                if exclude and any(fnmatch.fnmatch(rel,g) or fnmatch.fnmatch(fn,g) for g in exclude): continue
                targets.append(rel)
        if not targets:
            diag['status']='no_targets'; self._write(out_path, diag); return {}

        Nf, Np, failing_nodeids, passing_nodeids = self._baseline(project, test_cmd)
        diag['baseline']={'Nf':Nf,'Np':Np,'failing_nodeids':failing_nodeids[:100],'passing_nodeids':passing_nodeids[:100]}
        failing_nodeids_set = set(failing_nodeids)
        if Nf>0:
            # Record baseline failure but proceed unless explicitly disallowed (changed default behavior)
            if not allow_failing:
                # Proceed anyway but mark status so report doesn’t short-circuit (avoid exact 'baseline_failed')
                diag['status'] = 'baseline_failed_proceeding'
            else:
                diag['status'] = 'ok'

        print("Processing mbfl 2") 

        mindex = MethodIndex()
        for rel in targets:
            try: mindex.add_file(rel,(project/rel).read_text(encoding='utf-8'))
            except Exception: continue

        mutants: List[Mutant] = []
        rng = random.Random(0)
        for rel in targets:
            p = project/rel
            try:
                src = p.read_text(encoding='utf-8'); tree = ast.parse(src)
            except Exception: continue
            used: Set[int] = set()
            for node in ast.walk(tree):
                ln = getattr(node,'lineno',None)
                if not isinstance(ln,int) or ln in used: continue
                mutated=None; kind=None
                if isinstance(node, ast.Compare) and node.ops:
                    repl=self._flip_cmp(node.ops[0])
                    if repl:
                        nl=self._replace_op_line(src, ln, node.ops[0], repl)
                        if nl: mutated=self._apply_line(src,ln,nl); kind='cmp_flip'
                elif isinstance(node, ast.BoolOp):
                    if isinstance(node.op, ast.And):
                        nl=self._replace_token_line(src,ln,'and','or')
                        if nl: mutated=self._apply_line(src,ln,nl); kind='and_to_or'
                    elif isinstance(node.op, ast.Or):
                        nl=self._replace_token_line(src,ln,'or','and')
                        if nl: mutated=self._apply_line(src,ln,nl); kind='or_to_and'
                elif isinstance(node, ast.Constant) and isinstance(node.value,bool):
                    old='True' if node.value else 'False'; new='False' if node.value else 'True'
                    nl=self._replace_token_line(src,ln,old,new)
                    if nl: mutated=self._apply_line(src,ln,nl); kind='bool_flip'
                if mutated and kind:
                    mutants.append(Mutant(rel,ln,src,mutated,kind)); used.add(ln)

        if sample_rate and 0.0<sample_rate<1.0 and mutants:
            k=max(1,int(len(mutants)*sample_rate)); mutants=rng.sample(mutants,k)
        if len(mutants)>400: mutants=mutants[:400]
        diag['aggregate']['total_locations_identified']=len(mutants)

        print("Processing mbfl 3")

        py = sys.executable or 'python'
        per_run_timeout = 0
        try:
            per_run_timeout = int(ctx.get('mbfl_timeout') or 0)
        except Exception:
            per_run_timeout = 0
        fail_kills: Dict[Tuple[str,int],int]={}; pass_kills: Dict[Tuple[str,int],int]={}; survived: Dict[Tuple[str,int],int]={}
        detected_total=0; survived_total=0; t0=time.time()

        print("Processing mbfl 4")
        # Per-test attribution (testid -> {"file:line": count})
        kills_by_test: Dict[str, Dict[str,int]] = {}
        for idx, m in enumerate(mutants, start=1):
            path=project/m.file_rel
            try: original=path.read_text(encoding='utf-8')
            except Exception: continue
            try:
                path.write_text(m.mutated,encoding='utf-8')
                junit=project/'.suspect.mbfl.mutant.xml'
                cmd=f"{py} -m {test_cmd} --junitxml={junit} ."
                try:
                    proc=subprocess.run(
                        cmd,
                        shell=True,
                        cwd=str(project),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        timeout=per_run_timeout if per_run_timeout>0 else None,
                    )
                    timed_out = False
                except subprocess.TimeoutExpired as te:
                    # Treat timeout as a survived mutant (conservative) but record diagnostic
                    proc = te  # use for stdout access if any partial
                    timed_out = True
                    m_fail, m_pass = [], []
                    killed = False
                    bucket = 'timeout'
                    key=(m.file_rel,m.line)
                    survived_total+=1; survived[key]=survived.get(key,0)+1
                    diag['runs'].append({'id': idx, 'mutant':{'file':m.file_rel,'line':m.line,'kind':m.kind},'killed':False,'bucket':'timeout','killers':[], 'timeout_sec':per_run_timeout,'stdout_truncated':(getattr(te,'stdout','') or '')[:1800]})
                    # Periodic flush
                    if len(diag['runs']) % 10 == 0:
                        try: self._write(out_path, diag)
                        except Exception: pass
                    continue
                m_fail, m_pass = self._parse_mutant_junit(junit)
                m_fail_set = {str(t) for t in m_fail}
                m_pass_set = {str(t) for t in m_pass}
                repair_tests = {t for t in failing_nodeids_set if t in m_pass_set}
                regress_tests = {t for t in m_fail_set if t not in failing_nodeids_set}
                killed = bool(repair_tests or regress_tests)
                if killed:
                    if repair_tests and not regress_tests:
                        bucket = 'fail'
                    elif regress_tests and not repair_tests:
                        bucket = 'pass'
                    else:
                        bucket = 'mixed'
                else:
                    bucket = 'survived'
                key=(m.file_rel,m.line)
                killers: List[str] = sorted(repair_tests | regress_tests)
                if killed:
                    detected_total+=1
                    if repair_tests:
                        fail_kills[key]=fail_kills.get(key,0)+1
                    if regress_tests:
                        pass_kills[key]=pass_kills.get(key,0)+1
                    loc_key = f"{m.file_rel}:{m.line}"
                    for tid in killers:
                        td = kills_by_test.setdefault(tid, {})
                        td[loc_key] = td.get(loc_key, 0) + 1
                else:
                    survived_total+=1; survived[key]=survived.get(key,0)+1
                diag['runs'].append({
                    'id': idx,
                    'mutant':{'file':m.file_rel,'line':m.line,'kind':m.kind},
                    'killed':killed,
                    'bucket':bucket,
                    'killers': killers,
                    'repair_tests': sorted(repair_tests),
                    'regress_tests': sorted(regress_tests),
                    'stdout_truncated':(getattr(proc,'stdout','') or '')[:1800]
                })
                # Periodic flush so user sees incremental progress
                if len(diag['runs']) % 10 == 0:
                    try: self._write(out_path, diag)
                    except Exception: pass
            finally:
                try: path.write_text(original,encoding='utf-8')
                except Exception: pass

        print("Done processing for mbfl")

        # Post-processing aggregation inside collect()
        diag['aggregate'].update({'detected':detected_total,'survived':survived_total,'total_runs':len(mutants),'mutation_time_sec':round(time.time()-t0,2)})
        if diag.get('status') == 'running':  # preserve earlier baseline_failed_proceeding if set
            diag['status'] = 'ok'

        per_method_fail: Dict[str,int] = {}
        per_method_pass: Dict[str,int] = {}
        per_method_surv: Dict[str,int] = {}
        for (f, ln), c in fail_kills.items():
            mk = self._method_for_line(mindex, f, ln)
            if mk:
                per_method_fail[mk] = per_method_fail.get(mk, 0) + c
        for (f, ln), c in pass_kills.items():
            mk = self._method_for_line(mindex, f, ln)
            if mk:
                per_method_pass[mk] = per_method_pass.get(mk, 0) + c
        for (f, ln), c in survived.items():
            mk = self._method_for_line(mindex, f, ln)
            if mk:
                per_method_surv[mk] = per_method_surv.get(mk, 0) + c

        if survivor_fallback=='on' and survived_total>0 and not per_method_surv:
            total_kills=sum(per_method_fail.values())+sum(per_method_pass.values())
            if total_kills>0:
                remaining=survived_total; methods=list({*per_method_fail.keys(),*per_method_pass.keys()})
                for i,mk in enumerate(methods):
                    kills=per_method_fail.get(mk,0)+per_method_pass.get(mk,0)
                    if i < len(methods)-1:
                        share=int(round((kills/total_kills)*survived_total)) if total_kills else 0
                        per_method_surv[mk]=per_method_surv.get(mk,0)+share; remaining-=share
                    else:
                        per_method_surv[mk]=per_method_surv.get(mk,0)+max(0,remaining)
                diag['mbfl']['survivor_fallback']={'strategy':'proportional_detected','enabled':True,'total_survivors':survived_total}
        elif survivor_fallback=='off' and survived_total>0 and not per_method_surv:
            diag['mbfl']['survivor_fallback']={'strategy':'none','enabled':False,'total_survivors':survived_total}

        # Build killers_by_method from kills_by_test via method index mapping
        killers_by_method: Dict[str, Dict[str,int]] = {}
        try:
            for testid, locs in kills_by_test.items():
                for loc, cnt in locs.items():
                    try:
                        fpart, lpart = loc.rsplit(':',1)
                        ln = int(lpart)
                    except Exception:
                        continue
                    mk = self._method_for_line(mindex, fpart, ln)
                    if not mk:
                        continue
                    md = killers_by_method.setdefault(mk, {})
                    md[testid] = md.get(testid, 0) + cnt
        except Exception:
            killers_by_method = {}

        print("Done build killers by method for mbfl")

        # Attach PTA diagnostics
        try:
            diag_mbfl = diag.setdefault('mbfl', {})  # type: ignore[arg-type]
            diag_mbfl['per_test_attribution'] = {
                'enabled': True,
                'strategy': 'simple_kill_tests',
                'kills_by_test': kills_by_test,
                'notes': 'Counts how many mutants each test killed at each file:line.'
            }
            if killers_by_method:
                diag_mbfl['killers_by_method'] = killers_by_method
        except Exception:
            pass

        out: Dict[str,Dict[str,float]]={}
        for mk in {*per_method_fail.keys(),*per_method_pass.keys(),*per_method_surv.keys()}:
            kf=float(per_method_fail.get(mk,0)); kp=float(per_method_pass.get(mk,0))
            detected=kf+kp; surv=float(per_method_surv.get(mk,0)); total=detected+surv
            mut_score=(detected/total) if total else 0.0
            out[mk]={
                'mbfl_sbi':F.mbfl_sbi(kf,kp),
                'mbfl_tarantula':F.mbfl_tarantula(kf, kp, Nf, Np),
                'mbfl_ochiai':F.mbfl_ochiai(kf, kp, Nf, Np),
                'mbfl_jaccard':F.mbfl_jaccard(kf, kp, Nf, Np),
                'mbfl_dstar':F.mbfl_dstar(kf, kp, Nf, Np),
                'mbfl_op2':F.mbfl_op2(kf, kp, Nf, Np),
                'mbfl_barinel':F.mbfl_barinel(kf, kp, Nf, Np),
                'mbfl_naish2':F.mbfl_naish2(kf, kp, Nf, Np)
            }

        print("Done build out for mbfl")

        try:
            payload={'mutatest':diag}
            if diag_level=='min':
                for r in payload['mutatest'].get('runs', []) or []: # type: ignore
                    if isinstance(r,dict) and 'stdout_truncated' in r: r['stdout_truncated']=''
            with open(out_path,'w',encoding='utf-8') as f: json.dump(payload,f,indent=2)
        except Exception: pass
        return out

    # helpers
    def _write(self, path: pathlib.Path, data: dict):
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump({'mutatest': data}, f, indent=2)
        except Exception:
            pass

    def _baseline(self, project: pathlib.Path, test_cmd: str) -> Tuple[int,int,List[str],List[str]]:
        py=sys.executable or 'python'; junit=project/'.suspect.mbfl.baseline.xml'
        subprocess.run(f"{py} -m {test_cmd} --junitxml={junit} .",shell=True,cwd=str(project),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        try:
            import xml.etree.ElementTree as ET
            tree=ET.parse(str(junit)); root=tree.getroot(); failing=[]; passing=[]; nf=np=0
            for tc in root.iter('testcase'):
                failed=(tc.find('failure') is not None) or (tc.find('error') is not None)
                if failed: nf+=1
                else: np+=1
                name=tc.attrib.get('name','').strip(); classname=tc.attrib.get('classname','').strip(); file_attr=tc.attrib.get('file') or ''
                rel_file=pathlib.Path(file_attr).name if file_attr else ''
                nodeid=None
                if rel_file and name:
                    cls_part=''
                    if classname:
                        last=classname.split('.')[-1]
                        if last and last[0].isupper(): cls_part=f"::{last}"
                    nodeid=f"{rel_file}{cls_part}::{name}"
                elif name:
                    # Fallback: no file attribute in junit (e.g., for some pytest plugins)
                    if classname:
                        last=classname.split('.')[-1]
                        nodeid=f"{last}::{name}" if last else name
                    else:
                        nodeid=name
                if failed and nodeid:
                    failing.append(nodeid)
                elif (not failed) and nodeid:
                    passing.append(nodeid)
            return nf,np,failing,passing
        except Exception: return 0,0,[],[]

    def _parse_mutant_junit(self, junit: pathlib.Path) -> Tuple[List[str],List[str]]:
        try:
            import xml.etree.ElementTree as ET
            tree=ET.parse(str(junit)); root=tree.getroot(); failing=[]; passing=[]
            for tc in root.iter('testcase'):
                failed=(tc.find('failure') is not None) or (tc.find('error') is not None)
                name=tc.attrib.get('name','').strip(); classname=tc.attrib.get('classname','').strip(); file_attr=tc.attrib.get('file') or ''
                rel_file=pathlib.Path(file_attr).name if file_attr else ''
                nodeid=None
                if rel_file and name:
                    cls_part=''
                    if classname:
                        last=classname.split('.')[-1]
                        if last and last[0].isupper(): cls_part=f"::{last}"
                    nodeid=f"{rel_file}{cls_part}::{name}"
                elif name:
                    if classname:
                        last=classname.split('.')[-1]
                        nodeid=f"{last}::{name}" if last else name
                    else:
                        nodeid=name
                if nodeid:
                    if failed: failing.append(nodeid)
                    else: passing.append(nodeid)
            return failing, passing
        except Exception: return [], []

    def _flip_cmp(self, op):
        import ast
        mapping={ast.Eq:ast.NotEq(),ast.NotEq:ast.Eq(),ast.Lt:ast.GtE(),ast.GtE:ast.Lt(),ast.Gt:ast.LtE(),ast.LtE:ast.Gt(),ast.Is:ast.IsNot(),ast.IsNot:ast.Is()}
        for k,v in mapping.items():
            if isinstance(op,k): return v
        return None

    def _apply_line(self, src: str, line: int, new_line: Optional[str]) -> Optional[str]:
        if not new_line: return None
        lines=src.splitlines();
        if 1<=line<=len(lines): lines[line-1]=new_line; return '\n'.join(lines)+('\n' if src.endswith('\n') else '')
        return None

    def _replace_op_line(self, src: str, line: int, op_node, new_op) -> Optional[str]:
        import ast
        text=self._get_line(src,line)
        if text is None or isinstance(new_op,type(op_node)): return None
        mapping={ast.Eq:("==","!="),ast.NotEq:("!=","=="),ast.Lt:("<",">="),ast.Gt:(">","<="),ast.LtE:("<=",">"),ast.GtE:(">=","<"),ast.Is:(" is "," is not "),ast.IsNot:(" is not "," is ")}
        for k,(before,after) in mapping.items():
            if isinstance(op_node,k) and before in text: return text.replace(before,after,1)
        return None

    def _replace_token_line(self, src: str, line: int, old: str, new: str) -> Optional[str]:
        text=self._get_line(src,line)
        if text is None or old not in text: return None
        return text.replace(old,new,1)

    def _get_line(self, src: str, line: int) -> Optional[str]:
        lines=src.splitlines(); return lines[line-1] if 1<=line<=len(lines) else None

    def _method_for_line(self, mindex: MethodIndex, file_rel: str, line: int) -> Optional[str]:
        for ln in range(line,0,-1):
            mk=mindex.index.get((file_rel,ln))
            if mk: return mk
        return None

try:
    register_adapter('mbfl', MBFLMutatestAdapter)
except Exception:
    pass
