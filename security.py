import streamlit as st
import functools

# Hardcoded demo license key
VALID_LICENSE_KEY = "EVAL-PRO-2026"

def check_license(key):
    """
    Validates the provided license key.
    In a real app, this could check an API or a signed file.
    """
    return key == VALID_LICENSE_KEY

def require_license(func):
    """
    Decorator to wrap functions that require a valid license.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if not st.session_state.get("is_licensed", False):
            st.error("🚫 Access Denied: A valid license key is required to use this feature.")
            return None
        return func(*args, **kwargs)
    return wrapper

def license_sidebar():
    """
    Renders the license key input in the Streamlit sidebar.
    """
    st.sidebar.divider()
    st.sidebar.subheader("🔑 Licensing")
    
    if "is_licensed" not in st.session_state:
        st.session_state.is_licensed = False
        
    license_key = st.sidebar.text_input(
        "Enter License Key", 
        type="password", 
        help="Enter your valid license key to unlock full features."
    )
    
    if st.sidebar.button("Activate"):
        if check_license(license_key):
            st.session_state.is_licensed = True
            st.sidebar.success("✅ License Activated!")
            st.rerun()
        else:
            st.session_state.is_licensed = False
            st.sidebar.error("❌ Invalid License Key")

    if st.session_state.is_licensed:
        st.sidebar.caption("Status: PRO Version Active")
    else:
        st.sidebar.caption("Status: Restricted Mode")
