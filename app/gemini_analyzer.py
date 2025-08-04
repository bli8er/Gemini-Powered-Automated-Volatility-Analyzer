import google.generativeai as genai
import os

genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

def analyze_with_gemini(plugin_output: str, plugin_name: str) -> str:
    """
    Analyzes Volatility plugin output with Gemini for suspicious indicators.
    """
    if not plugin_output:
        return "No output to analyze."

    try:
        model = genai.GenerativeModel('models/gemini-2.5-pro')
        
        # New, more detailed prompt for better analysis
        prompt = f"""
        As a senior cybersecurity malware analyst, meticulously analyze the following Volatility 3 plugin output from '{plugin_name}'. Your analysis must be detailed and actionable.

        Perform the following checks:
        1.  **Duplicate System Processes:** Look for multiple instances of critical Windows processes that should normally only have one instance (e.g., lsass.exe, csrss.exe). This is a major red flag.
        2.  **Parent-Child Relationships:** Scrutinize the Parent Process ID (PPID) for each process. Are there any legitimate system processes spawned by unusual parents (e.g., lsass.exe spawned by anything other than wininit.exe)?
        3.  **Suspicious Names:** Identify any processes with names that are misspelled versions of legitimate processes (e.g., "svchost.exe" vs "scvhost.exe").
        4.  **Known Malware Indicators:** Based on the process names and relationships, identify any potential malware families or techniques.

        Provide a summary of your findings, highlighting the most suspicious processes first. If you find a critical indicator, state it clearly. If nothing suspicious is found, explicitly state that the output appears clean.

        **Volatility Plugin Output:**
        ---
        {plugin_output}
        ---
        """
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error during Gemini analysis: {str(e)}"
