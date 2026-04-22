from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..profile.schema import Profile
from .tailor import TailoredResume

_TEMPLATE_DIR = Path(__file__).parent / "templates"


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(_TEMPLATE_DIR),
        autoescape=select_autoescape(["html"]),
    )


def render_html(profile: Profile, tailored: TailoredResume) -> str:
    env = _env()
    tmpl = env.get_template("resume.html.j2")
    css = (_TEMPLATE_DIR / "resume.css").read_text(encoding="utf-8")
    p = profile.personal
    location = ", ".join([x for x in (p.city, p.state) if x])
    return tmpl.render(
        name=p.full_name,
        email=p.email,
        phone=p.phone,
        location=location,
        linkedin_url=p.linkedin_url,
        github_url=p.github_url,
        tailored=tailored,
        css=css,
    )


def render_pdf(profile: Profile, tailored: TailoredResume, out_path: Path) -> Path:
    # Import lazily — weasyprint pulls in heavy native deps.
    from weasyprint import HTML

    html = render_html(profile, tailored)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html).write_pdf(target=str(out_path))
    return out_path
