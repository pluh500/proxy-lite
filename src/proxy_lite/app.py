# streamlit_app.py

import sys
import asyncio
import base64
import subprocess
from io import BytesIO

import streamlit as st
from PIL import Image

from proxy_lite import Runner, RunnerConfig

# Ensure Playwright browser binaries are installed only once
def install_browsers():
    # Use the same Python interpreter to run the Playwright install module
    cmd = [sys.executable, "-m", "playwright", "install", "--with-deps", "chromium"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        st.info("Playwright browsers installed successfully.")
    except subprocess.CalledProcessError as e:
        st.warning(
            f"Failed to install Playwright browsers (exit {e.returncode}):\n{e.stderr}"
        )

# Run installation at startup
install_browsers()

def get_user_config(config_expander):
    config = {
        "environment": {
            "name": "webbrowser",
            "annotate_image": True,
            "screenshot_delay": 2.0,
            "include_html": False,
            "viewport_width": 1280,
            "viewport_height": 1920,
            "include_poi_text": True,
            "homepage": "https://www.google.com",
            "keep_original_image": False,
            "headless": True,
        },
        "solver": {
            "name": "simple",
            "agent": {
                "name": "proxy_lite",
                "client": {
                    "name": "convergence",
                    "model_id": "convergence-ai/proxy-lite-3b",
                    "api_base": "https://convergence-ai-demo-api.hf.space/v1",
                },
            },
        },
        "local_view": False,
        "verbose": True,
        "task_timeout": 1800,
        "action_timeout": 300,
        "environment_timeout": 30,
    }

    with config_expander:
        st.subheader("Environment Settings")
        col1, col2 = st.columns(2)

        with col1:
            config["environment"]["include_html"] = st.checkbox(
                "Include HTML",
                value=config["environment"]["include_html"],
                help="Include HTML in observations",
            )
            config["environment"]["include_poi_text"] = st.checkbox(
                "Include POI Text",
                value=config["environment"]["include_poi_text"],
                help="Include points of interest text in observations",
            )
            config["environment"]["homepage"] = st.text_input(
                "Homepage",
                value=config["environment"]["homepage"],
                help="Homepage to start from",
            )

        with col2:
            config["solver"]["agent"]["client"]["api_base"] = st.text_input(
                "VLLM Server URL",
                value=config["solver"]["agent"]["client"]["api_base"],
                help="URL of a vllm server running proxy-lite",
            )
            config["environment"]["screenshot_delay"] = st.slider(
                "Screenshot Delay (seconds)",
                min_value=0.5,
                max_value=10.0,
                value=config["environment"]["screenshot_delay"],
                step=0.5,
                help="Delay before taking screenshots",
            )

        st.subheader("Advanced Settings")
        config["task_timeout"] = st.number_input(
            "Task Timeout (seconds)",
            min_value=60,
            max_value=3600,
            step=60,
            value=config["task_timeout"],
            help="Maximum time allowed for task completion",
        )
        config["action_timeout"] = st.number_input(
            "Action Timeout (seconds)",
            min_value=10,
            max_value=300,
            step=10,
            value=config["action_timeout"],
            help="Maximum time allowed for an action to complete",
        )
        config["environment_timeout"] = st.number_input(
            "Environment Timeout (seconds)",
            min_value=10,
            max_value=300,
            step=10,
            value=config["environment_timeout"],
            help="Maximum time allowed for environment to respond",
        )

    return config


async def run_task_async(
    task: str,
    status_placeholder,
    action_placeholder,
    environment_placeholder,
    image_placeholder,
    history_placeholder,
    config: dict,
):
    try:
        config = RunnerConfig.from_dict(config)
    except Exception as e:
        st.error(f"Error loading RunnerConfig: {e!s}")
        return

    runner = Runner(config=config)

    status_placeholder.markdown(
        """
        <style>
        @keyframes spin {
            0% { content: "⚡"; }
            25% { content: "⚡."; }
            50% { content: "⚡.."; }
            75% { content: "⚡..."; }
        }
        .spinner::before {
            content: "⚡";
            animation: spin 2s linear infinite;
            display: inline-block;
        }
        </style>
        <div><b>Resolving your task  </b><span class="spinner"></span></div>
        """,
        unsafe_allow_html=True,
    )

    all_steps = []
    all_screenshots = []
    all_soms = []

    async for run in runner.run_generator(task):
        if run.actions:
            latest_step = run.actions[-1].text
            latest_step += "".join(
                [
                    f'<tool_call>{{"name": {tool_call.function["name"]}, "arguments": {tool_call.function["arguments"]}}}</tool_call>'
                    for tool_call in run.actions[-1].tool_calls
                ]
            )
            action_placeholder.write(f"⚡ **Latest Step:** {latest_step}")
            all_steps.append(latest_step)

        if run.observations and run.observations[-1].state.image:
            environment_placeholder.write("🌐 **Environment:**")
            image_bytes = base64.b64decode(run.observations[-1].state.image)
            image = Image.open(BytesIO(image_bytes))
            image_placeholder.image(image, use_container_width=True)
            all_screenshots.append(image)
            som = run.observations[-1].state.text
            all_soms.append(som)

        with history_placeholder, st.expander("🕝 **History**"):
            for idx, (action, img, som) in enumerate(zip(all_steps, all_screenshots, all_soms, strict=False)):
                st.write(f"**Step {idx + 1}**")
                st.image(img, use_container_width=True)
                st.markdown(som)
                st.write(action)
    action_placeholder.write(" ")
    status_placeholder.write(f"✨ **Result:** {latest_step}")


def main():
    st.title("⚡ Proxy-Lite")

    st.markdown("Powered by **Proxy-Lite**", unsafe_allow_html=True)

    if "config_expanded" not in st.session_state:
        st.session_state.config_expanded = False
    if "settings_expanded" not in st.session_state:
        st.session_state.settings_expanded = False

    config_expander = st.expander("⚙️ Proxy-Lite Configuration", expanded=st.session_state.config_expanded)
    config = get_user_config(config_expander)

    with st.form(key="run_task_form"):
        task = st.text_input(
            "Submit a task",
            key="task_input",
            help="Enter a task to be completed",
        )
        submit_button = st.form_submit_button("Submit a task", type="primary", use_container_width=True)

        if submit_button:
            st.session_state.config_expanded = False
            if task:
                status_placeholder = st.empty()
                st.write(" ")
                action_placeholder = st.empty()
                environment_placeholder = st.empty()
                image_placeholder = st.empty()
                history_placeholder = st.empty()

                asyncio.run(
                    run_task_async(
                        task,
                        status_placeholder,
                        action_placeholder,
                        environment_placeholder,
                        image_placeholder,
                        history_placeholder,
                        config,
                    ),
                )

                st.success("Task completed!", icon="✨")
            else:
                st.error("Please give a task first!")

if __name__ == "__main__":
    main()
