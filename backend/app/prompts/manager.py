import os
from functools import lru_cache
from typing import Any
import yaml
from jinja2 import Template

PROMPTS_DIR = os.path.dirname(os.path.abspath(__file__))

@lru_cache(maxsize=128)
def _load_raw_template(relative_path: str) -> str:
    """Loads the raw prompt template from YAML file and caches it."""
    full_path = os.path.join(PROMPTS_DIR, relative_path)
    with open(full_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    
    if not isinstance(data, dict) or "system_prompt" not in data:
        raise ValueError(f"Prompt YAML file at {relative_path} must have a top-level 'system_prompt' key.")
        
    return data["system_prompt"]

def render_prompt(relative_path: str, **kwargs: Any) -> str:
    """Loads a prompt template and renders it with Jinja2 using the provided variables."""
    raw_template = _load_raw_template(relative_path)
    template = Template(raw_template)
    return template.render(**kwargs).strip()
