"""st.html／markdown 對 svg、style、data-URI 的實際渲染（1.56.0）。不被 repo import。"""
import base64
import streamlit as st
SVG = "<svg xmlns='http://www.w3.org/2000/svg' width='40' height='12' viewBox='0 0 40 12'><polyline points='0,10 10,4 20,6 40,1' fill='none' stroke='#c00' stroke-width='2'/></svg>"
st.html("<div id='h_svg'>A" + SVG + "</div>")
st.html("<style>#h_style{color:rgb(1,2,3)}</style><div id='h_style'>B</div>")
st.html("<div id='h_inline_style' style='color:rgb(4,5,6);display:flex;gap:4px'><span class='c'>C</span></div>")
st.html("<div id='h_img'>D<img alt='spark' src='data:image/svg+xml;base64," + base64.b64encode(SVG.encode()).decode() + "'/></div>")
st.markdown("<div id='m_svg'>E" + SVG + "</div>", unsafe_allow_html=True)
st.markdown("<div id='m_img'>F<img alt='spark' src='data:image/svg+xml;base64," + base64.b64encode(SVG.encode()).decode() + "'/></div>", unsafe_allow_html=True)
st.markdown("<style>#m_style{color:rgb(7,8,9)}</style><div id='m_style'>G</div>", unsafe_allow_html=True)
st.badge("BADGE_OK", color="green", icon=":material/check:")
st.markdown(":green-badge[MD_BADGE]")
