import io
import os
import logging
import requests
from volatility3 import framework
from volatility3.framework import contexts, interfaces, plugins
from volatility3.framework.automagic import automagic
from volatility3.framework.configuration import requirements

# Function to analyze plugin output using Google Gemini
def analyze_with_gemini(plugin_name, plugin_output):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "[Error] GEMINI_API_KEY not set in environment."

    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={api_key}"
    prompt = {
        "contents": [{
            "parts": [{
                "text": f"You are a cybersecurity analyst.\n\nHere is the Volatility plugin output for '{plugin_name}':\n\n{plugin_output}\n\nIdentify any suspicious processes, malware behavior, anomalies, or compromise indicators."
            }]
        }]
    }

    try:
        response = requests.post(endpoint, json=prompt)
        response.raise_for_status()
        return response.json()['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        return f"[Gemini API Error] {str(e)}"

# Main function to run multiple plugins and get AI summary
def run_multiple_plugins(file_path, plugin_list):
    results = {}

    context = contexts.ContextInterface()
    plugin_dir = framework.__path__[0]
    plugin_base = "plugins"

    automagics = automagic.available(context)
    single_location = f"file:{file_path}"

    for plugin_name in plugin_list:
        try:
            plugin_class = framework.plugins.construct_plugin(plugin_name)

            base_config_path = interfaces.configuration.path_join(plugin_base, plugin_name)
            plugin_config = requirements.ConfigContext(context, base_config_path)
            plugin_config["automagic.LayerStacker.single_location"] = single_location

            constructed = plugin_class(context, plugin_config_path=base_config_path, progress_callback=None)
            treegrid = constructed.run()

            output = io.StringIO()
            for row in treegrid.visit():
                output.write(str(row) + "\n")

            raw_output = output.getvalue()
            gemini_summary = analyze_with_gemini(plugin_name, raw_output)

            results[plugin_name] = {
                "volatility_output": raw_output,
                "gemini_summary": gemini_summary
            }

        except Exception as e:
            results[plugin_name] = {
                "volatility_output": f"Plugin '{plugin_name}' failed: {str(e)}",
                "gemini_summary": "AI analysis not available due to plugin failure."
            }

    return results

