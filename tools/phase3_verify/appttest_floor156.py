"""Phase 3 步驟 4 驗證腳本（P1R-FLOOR-156-API）。不被 app／tests import。
用法：<獨立 venv 的 python> tools/phase3_verify/appttest_floor156.py
需要 streamlit==1.56.0 的獨立 venv；本腳本只用 AppTest，不碰 repo src。"""
import sys
import streamlit
from streamlit.testing.v1 import AppTest

# AppTest 限制：ButtonGroup.set_value(None) 被 `if self._value is not None` 當成「未設定」而回讀舊值，
# 無法模擬取消選取。以 monkeypatch 讓 `_deselect=True` 時 value 回 None（widget state 送空 array，
# 與前端取消選取送出的內容同形）。
from streamlit.testing.v1.element_tree import ButtonGroup as _BG
_orig_value = _BG.value
def _value(self):
    if getattr(self, "_deselect", False):
        return None
    return _orig_value.fget(self)
_BG.value = property(_value)
def deselect(bg):
    bg._deselect = True
    return bg

R = []
def rec(api, beh, ok, note=""):
    R.append((api, beh, "PASS" if ok else "FAIL", note))
    print(f"[{'PASS' if ok else 'FAIL'}] {api} | {beh} | {note}")

def run(src, **kw):
    at = AppTest.from_string(src, default_timeout=20).run()
    return at

print("streamlit", streamlit.__version__, "python", sys.version.split()[0])

# ---- (1) default / default=
at = run('''
import streamlit as st
a = st.segmented_control("a", ["x","y","z"], key="a")
b = st.segmented_control("b", ["x","y","z"], default="y", key="b")
c = st.pills("c", ["x","y","z"], default="z", key="c")
d = st.radio("d", ["x","y","z"], key="d", horizontal=True)
st.write(f"A={a!r} B={b!r} C={c!r} D={d!r}")
''')
bg = at.button_group
rec("segmented_control", "no default -> None", bg[0].value is None, repr(bg[0].value))
rec("segmented_control", "default='y'", bg[1].value == "y", repr(bg[1].value))
rec("pills", "default='z'", bg[2].value == "z", repr(bg[2].value))
rec("radio", "no default -> options[0]", at.radio[0].value == "x", repr(at.radio[0].value))
assert not at.exception

# ---- (2) deselect
at = run('''
import streamlit as st
v = st.segmented_control("m", ["a","b","c"], default="a", key="m")
st.write(f"V={v!r}")
''')
at.button_group[0].set_value("b").run()
rec("segmented_control", "select b -> 'b'", at.session_state["m"] == "b", repr(at.session_state["m"]))
deselect(at.button_group[0]).run()
rec("segmented_control", "deselect (set None) with default=a -> returns None (NOT default)", at.session_state["m"] is None and "V=None" in at.markdown[0].value, f"{at.session_state['m']!r} / {at.markdown[0].value}")
at.button_group[0].unselect("b").run()  # no-op since None
# fallback pattern: `v = widget or last_valid`
at = run('''
import streamlit as st
OPTS = ["a","b","c"]
if "last" not in st.session_state: st.session_state["last"] = "a"
v = st.segmented_control("m", OPTS, default=st.session_state["last"], key="m")
eff = v if v is not None else st.session_state["last"]
st.session_state["last"] = eff
st.write(f"EFF={eff}")
''')
at.button_group[0].set_value("c").run()
rec("fallback", "select c -> EFF=c", "EFF=c" in at.markdown[0].value, at.markdown[0].value)
deselect(at.button_group[0]).run()
rec("fallback", "deselect -> EFF stays c (last valid), widget stays None", "EFF=c" in at.markdown[0].value and at.session_state["m"] is None, f"{at.markdown[0].value} widget={at.session_state['m']!r}")
# on_change callback + restore widget value
at = run('''
import streamlit as st
OPTS = ["a","b","c"]
st.session_state.setdefault("last","a")
def _cb():
    v = st.session_state["m"]
    if v is None:
        st.session_state["m"] = st.session_state["last"]
    else:
        st.session_state["last"] = v
st.segmented_control("m", OPTS, default="a", key="m", on_change=_cb)
st.write(f"M={st.session_state['m']!r}")
''')
at.button_group[0].set_value("b").run()
deselect(at.button_group[0]).run()
rec("fallback(on_change)", "callback rewrites key to last valid on deselect (AppTest)", at.session_state["m"] == "b" and "M='b'" in at.markdown[0].value, f"{at.session_state['m']!r} {at.markdown[0].value}")
assert not at.exception

# ---- (3) rerun persistence
at = run('''
import streamlit as st
st.segmented_control("m", ["a","b"], default="a", key="m")
st.button("noop")
''')
at.button_group[0].set_value("b").run()
at.button[0].click().run()
rec("segmented_control", "key persists across unrelated rerun", at.session_state["m"] == "b", repr(at.session_state["m"]))
# widget not rendered one run -> key cleanup?
at = run('''
import streamlit as st
if st.session_state.get("show", True):
    st.segmented_control("m", ["a","b"], default="a", key="m")
st.checkbox("hide", key="hide")
st.session_state["show"] = not st.session_state["hide"]
''')
at.button_group[0].set_value("b").run()
at.checkbox[0].check().run()
at.checkbox[0].uncheck().run()
rec("segmented_control", "skipped-render run drops widget state (key removed from session_state; standard Streamlit cleanup)", at.session_state.filtered_state.get("m") is None, repr(at.session_state.filtered_state.get("m")))

# ---- (4) in st.form
at = run('''
import streamlit as st
if "runs" not in st.session_state: st.session_state["runs"]=0
st.session_state["runs"]+=1
with st.form("f"):
    seg = st.segmented_control("m", ["a","b","c"], default="a", key="seg")
    pl = st.pills("p", ["a","b","c"], default="a", key="pl")
    sub = st.form_submit_button("go")
st.write(f"runs={st.session_state['runs']} sub={sub} seg={seg!r} pl={pl!r}")
''')
r0 = at.session_state["runs"]
at.button_group[0].set_value("c")
at.button_group[1].set_value("b")
# AppTest: staging a value without run then submit
at.button[0].click().run()
rec("segmented_control/pills in st.form", "value only applied at submit; submit returns staged values", "seg='c'" in at.markdown[0].value and "pl='b'" in at.markdown[0].value and "sub=True" in at.markdown[0].value, at.markdown[0].value)
deselect(at.button_group[0])
at.button[0].click().run()
rec("segmented_control in st.form", "deselect staged then submit -> None", "seg=None" in at.markdown[0].value, at.markdown[0].value)
rec("segmented_control in st.form", "NOTE AppTest cannot prove 'no immediate rerun on click' (frontend behaviour)", True, "see Playwright section")
# form_id on proto
at = run('''
import streamlit as st
with st.form("f"):
    st.segmented_control("m", ["a","b"], key="s")
    st.form_submit_button("go")
''')
rec("segmented_control in st.form", "proto form_id non-empty (widget is form-batched)", bool(at.button_group[0].form_id), at.button_group[0].form_id)
# expander in form
at = run('''
import streamlit as st
with st.form("f"):
    with st.expander("opts", expanded=False, icon=":material/tune:"):
        st.segmented_control("m", ["a","b"], default="a", key="s")
    st.form_submit_button("go")
st.write(st.session_state["s"])
''')
rec("expander(icon=) in form + segmented_control inside", "renders, no exception", not at.exception, f"expander count={len(at.expander)} exc={len(at.exception)}")
at.button_group[0].set_value("b"); at.button[0].click().run()
rec("expander in form", "collapsed-expander widget value submitted", at.session_state["s"] == "b", repr(at.session_state["s"]))

# ---- (5) format_func / options types / label_visibility / key
at = run('''
import streamlit as st
LAB = {"1y":"一年","3y":"三年","5y":"五年"}
a = st.segmented_control("a", list(LAB), format_func=lambda k: LAB[k], default="1y", key="a")
b = st.segmented_control("b", [("x",1),("y",2)], format_func=lambda t: t[0], key="b")
c = st.segmented_control("c", ["a","b"], label_visibility="collapsed", key="c")
d = st.segmented_control("d", ["a","b"], label_visibility="hidden", key="d")
st.write(f"a={a!r} b={b!r}")
''')
rec("segmented_control", "format_func str options: labels shown, value = raw key", at.button_group[0].options == ["一年","三年","五年"] and at.button_group[0].value == "1y", f"{at.button_group[0].options} {at.button_group[0].value!r}")
rec("segmented_control", "tuple options + format_func (no default)", not at.exception and at.button_group[1].value is None and at.button_group[1].options == ["x","y"], f"{at.button_group[1].value!r} opts={at.button_group[1].options} exc={at.exception}")
at2 = run('''
import streamlit as st
st.segmented_control("b", [("x",1),("y",2)], format_func=lambda t: t[0], default=("x",1), key="b")
''')
rec("segmented_control", "tuple options + default=<tuple> (tuple read as a SEQUENCE of defaults) -> raises", bool(at2.exception), (at2.exception[0].message[:90] if at2.exception else ""))
at2 = run('''
import streamlit as st
st.segmented_control("b", [("x",1),("y",2)], format_func=lambda t: t[0], default=[("x",1)], key="b")
st.write(repr(st.session_state["b"]))
''')
rec("segmented_control", "tuple options + default=[<tuple>] (list-wrapped) -> value is the tuple", (not at2.exception) and at2.session_state["b"] == ("x",1), (at2.exception[0].message[:90] if at2.exception else repr(at2.session_state["b"])))
at.button_group[1].set_value(("y",2)).run()
rec("segmented_control", "tuple options select -> returns the tuple", at.session_state["b"] == ("y",2), repr(at.session_state["b"])) if not at.exception else rec("segmented_control","tuple select",False,str(at.exception))
rec("segmented_control", "label_visibility collapsed/hidden accepted", not at.exception, "")
at = run('''
import streamlit as st
st.segmented_control("a", ["x","y"], default="nope", key="a")
''')
rec("segmented_control", "default not in options -> raises (fail loud)", bool(at.exception), (at.exception[0].message[:100] if at.exception else ""))
at = run('''
import streamlit as st
st.segmented_control("a", [], key="a")
''')
rec("segmented_control", "empty options -> ", True, "exception=%s" % bool(at.exception) + (" "+at.exception[0].message[:80] if at.exception else ""))
at = run('''
import streamlit as st
st.segmented_control("a", ["x","y"], key="a")
st.segmented_control("a2", ["x","y"], key="a")
''')
rec("segmented_control", "duplicate key -> DuplicateWidgetID/Key exception", bool(at.exception), (at.exception[0].value if at.exception else ""))
at = run('''
import streamlit as st
st.session_state["k"] = "b"
st.segmented_control("a", ["a","b"], key="k")
st.segmented_control("a", ["a","b"], default="a", key="k2")
st.session_state["k3"]="a"
''')
rec("segmented_control", "pre-seeded session_state[key] honored without default=", at.session_state["k"] == "b", repr(at.session_state["k"]))
at = run('''
import streamlit as st
st.session_state["k"] = "a"
st.segmented_control("a", ["a","b"], default="b", key="k")
''')
print("INFO preset+default both:", bool(at.exception), at.exception[0].message[:120] if at.exception else at.session_state["k"])
rec("segmented_control", "session_state preset AND default= both -> (info)", True, "exception=%s value=%r" % (bool(at.exception), None if at.exception else at.session_state["k"]))
# options change under same key
at = run('''
import streamlit as st
n = st.session_state.get("n", 0)
st.session_state["n"] = n+1
opts = ["a","b","c"] if n == 0 else ["a","b"]
st.segmented_control("m", opts, default="a", key="m")
''')
at.button_group[0].set_value("c").run()
rec("segmented_control", "stored value no longer in options after options change -> ", True, f"exc={bool(at.exception)} value={at.session_state['m'] if not at.exception else None!r}")

# ---- (6) radio parity + horizontal
at = run('''
import streamlit as st
st.radio("r", ["a","b","c"], horizontal=True, key="r")
''')
at.radio[0].set_value("b").run()
rec("radio(horizontal=True)", "A fallback works", at.session_state["r"] == "b", repr(at.session_state["r"]))

# ---- (7) other API
def chk(api, beh, src, extra=None):
    at = run(src)
    ok = not at.exception
    note = str(at.exception[0].message[:120]) if at.exception else ""
    if ok and extra: ok, note = extra(at)
    rec(api, beh, ok, note)
    return at
chk("st.badge", "badge('x', color='green', icon=':material/check:')", '''
import streamlit as st
st.badge("OK", color="green", icon=":material/check:")
st.markdown("inline :green-badge[x] :red-badge[y]")''')
chk("st.html", "html str with <style>/<svg>", '''
import streamlit as st
st.html("<div class='a'>hi</div><svg width='10' height='10'><circle cx='5' cy='5' r='4'/></svg>")''')
at = chk("st.html", "unsafe_allow_javascript kwarg exists?", '''
import streamlit as st
st.html("<b>x</b>", unsafe_allow_javascript=False)''')
chk("st.metric(chart_data=)", "line sparkline, chart_type=line, delta", '''
import streamlit as st
st.metric("m", "1.2", delta="0.3", chart_data=[1.0,2.0,1.5,3.0], chart_type="line", border=True)
st.metric("m2", "1", chart_data=[1,2,3], chart_type="area")
st.metric("m3", "1", chart_data=[1,2,3], chart_type="bar")''')
chk("st.metric(chart_data=)", "empty list", '''
import streamlit as st
st.metric("m", "1", chart_data=[])''')
chk("st.metric(chart_data=)", "NaN inside data (raw)", '''
import streamlit as st
st.metric("m", "1", chart_data=[1.0, float("nan"), 3.0])''')
chk("st.metric(chart_data=)", "inside st.form", '''
import streamlit as st
with st.form("f"):
    st.metric("m", "1", chart_data=[1,2,3])
    st.form_submit_button("go")''')
chk("st.bar_chart(horizontal=)", "horizontal=True DataFrame", '''
import streamlit as st, pandas as pd
st.bar_chart(pd.DataFrame({"v":[3,1,2]}, index=["a","b","c"]), horizontal=True, height=200)''')
chk("st.line_chart(height=)", "height=160", '''
import streamlit as st, pandas as pd
st.line_chart(pd.DataFrame({"v":[3,1,2]}), height=160)''')
chk("st.expander(icon=)", "icon material", '''
import streamlit as st
with st.expander("t", icon=":material/info:"): st.write("x")''')
chk("st.container(height=)", "height=200 scroll + border", '''
import streamlit as st
with st.container(height=200, border=True): st.write("x")''')
chk("st.container(height='content')", "string height (info)", '''
import streamlit as st
with st.container(height="content"): st.write("x")''')
chk("st.expander in st.form", "plain", '''
import streamlit as st
with st.form("f"):
    with st.expander("e"): st.write("x")
    st.form_submit_button("go")''')
chk("st.bar_chart(horizontal=) in st.form", "plain", '''
import streamlit as st, pandas as pd
with st.form("f"):
    st.bar_chart(pd.DataFrame({"v":[3,1,2]}), horizontal=True)
    st.form_submit_button("go")''')

print("\nSUMMARY", len(R), "rows;", sum(1 for r in R if r[2]=="FAIL"), "FAIL")
